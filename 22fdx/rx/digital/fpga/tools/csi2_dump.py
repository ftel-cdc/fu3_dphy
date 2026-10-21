#!/usr/bin/env python3
"""Check the CSI-2 traffic in ILA captures of the FPGA prototype (fpga/FPGA_PROTO_PLAN.md).

A capture is the CSV file that Vivado writes with write_hw_ila_data -csv_file: a line of probe names,
a "Radix - ..." line, then one line per sample.

  csi2_dump.py ppi  CAP.csv --lanes 4 --data dl{n}_rxdatahs --valid dl{n}_rxvalidhs \\
                    --active dl{n}_rxactivehs [--dt 0x2B] [--pgm lines.pgm]
  csi2_dump.py axis CAP.csv --tdata tdata --tvalid tvalid [--tready tready] --tuser tuser \\
                    --tlast tlast [--ppc 4] [--bpp 10] [--pgm lines.pgm]
  csi2_dump.py compare {ppi|axis} A.csv B.csv <options of that mode> [--headers-only]
  csi2_dump.py bursts --truth TRUTH.txt [--lanes 4] A.csv [B.csv ...]
  csi2_dump.py selftest [--tx-model]

A column is chosen by a part of its name; "{n}" stands for the lane number.
PPI mode:
  - one packet per HS burst (CSI-2 v1.3 9.7: the lanes go to LPS between packets);
  - bytes after the packet in a burst are counted as trailer;
  - the ECC (single-bit correction) and the CRC-16 are checked.
Bursts mode (TN1/TN2 of fpga/PLAN_TN1_TN3.md, dummy data, no CSI-2 packets):
  - per lane, a burst is a run of rxactivehs; its bytes are the samples with rxvalidhs;
  - burst k of a lane pairs with burst k of that lane in the truth file of the line generator
    (fpga/exp1/dphy_line_gen.sv) and must start with its payload; bytes after the payload are counted as
    trailer, and are an error only beyond --max-trailer (one limit for every capture, or a comma list in
    capture order, "-" for no limit);
  - errsoths, errsotsynchs, rxvalidhs outside a burst and a missing or extra burst are errors;
  - with a sim_time_ps column, the pairing must also hold in time (the payloads may repeat): the last byte
    of a burst up to its payload length must reach the PPI after it left the pad (truth times), and as long
    after it as the median of the capture, within half the smallest gap between two bursts of a lane. The
    latency of the last payload byte (sample time minus the end of its last bit at the pad) is reported.
"""
import argparse
import csv
import os
import random
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
REPO = os.path.dirname(FPGA)

# ---------------------------------------------------------------------------------------------------
# CSI-2 header ECC and payload CRC (CSI-2 v1.3 9.5 and 9.6)

# Syndrome of data bits 0..23 (Table 4, 24-bit subset), as P5..P0
ECC_SYN = [0x07, 0x0B, 0x0D, 0x0E, 0x13, 0x15, 0x16, 0x19,
           0x1A, 0x1C, 0x23, 0x25, 0x26, 0x29, 0x2A, 0x2C,
           0x31, 0x32, 0x34, 0x38, 0x1F, 0x2F, 0x37, 0x3B]


def ecc24(d):
    """6-bit ECC of the 24 header bits d = DI | WC_LS << 8 | WC_MS << 16."""
    p = 0
    for i in range(24):
        if (d >> i) & 1:
            p ^= ECC_SYN[i]
    return p


def ecc_check(h0, h1, h2, ecc):
    """Return (status, (h0, h1, h2)); status is 'ok', 'corrected' or 'error' (two or more bits)."""
    d = h0 | (h1 << 8) | (h2 << 16)
    s = (ecc & 0x3F) ^ ecc24(d)
    if s == 0:
        return 'ok', (h0, h1, h2)
    if s in ECC_SYN:                       # one data bit flipped
        d ^= 1 << ECC_SYN.index(s)
        return 'corrected', (d & 0xFF, (d >> 8) & 0xFF, d >> 16)
    if s & (s - 1) == 0:                   # one ECC bit flipped
        return 'corrected', (h0, h1, h2)
    return 'error', (h0, h1, h2)


def crc16_bitwise(data, crc=0xFFFF):
    """CRC-16 of the payload exactly as Figure 54 (LSB first, 0x8408, seed 0xFFFF)."""
    for b in data:
        for i in range(8):
            fb = (crc ^ (b >> i)) & 1
            crc >>= 1
            if fb:
                crc ^= 0x8408
    return crc


_CRC_TAB = [crc16_bitwise([b], 0) for b in range(256)]


def crc16(data, crc=0xFFFF):
    """Same as crc16_bitwise, table driven."""
    for b in data:
        crc = (crc >> 8) ^ _CRC_TAB[(crc ^ b) & 0xFF]
    return crc


def raw10_unpack(payload):
    """RAW10 payload (5 bytes per 4 pixels, CSI-2 v1.3 11.4.4) to pixel values."""
    px = []
    for i in range(0, len(payload) - 4, 5):
        b0, b1, b2, b3, b4 = payload[i:i + 5]
        px += [(b0 << 2) | (b4 & 3), (b1 << 2) | ((b4 >> 2) & 3),
               (b2 << 2) | ((b4 >> 4) & 3), (b3 << 2) | (b4 >> 6)]
    return px


def raw10_pack(px):
    out = bytearray()
    for i in range(0, len(px), 4):
        p = px[i:i + 4]
        out += bytes([v >> 2 for v in p])
        out.append(sum((v & 3) << (2 * k) for k, v in enumerate(p)))
    return bytes(out)


def write_pgm(path, lines, maxval):
    """Lines of pixels as a 16-bit PGM; short lines are padded with 0."""
    w = max(len(line) for line in lines)
    with open(path, 'wb') as f:
        f.write(f'P5\n{w} {len(lines)}\n{maxval}\n'.encode())
        for line in lines:
            f.write(b''.join(v.to_bytes(2, 'big') for v in line + [0] * (w - len(line))))

# ---------------------------------------------------------------------------------------------------
# ILA capture


class Capture:
    """Columns of a Vivado ILA CSV file."""

    BASE = {'HEX': 16, 'BIN': 2, 'BINARY': 2, 'OCT': 8, 'UNSIGNED': 10, 'DEC': 10, 'SIGNED': 10}

    def __init__(self, path):
        with open(path, newline='') as f:
            rows = [r for r in csv.reader(f) if r]
        self.path = path
        self.names = [c.strip() for c in rows[0]]
        self.radix = ['HEX'] * len(self.names)
        start = 1
        if len(rows) > 1 and rows[1][0].strip().startswith('Radix'):
            self.radix = [c.strip() for c in rows[1]]
            self.radix[0] = self.radix[0].split('-', 1)[1].strip()
            start = 2
        self.rows = rows[start:]
        self._cache = {}

    def col(self, part):
        """Index of the one column whose name contains part (an exact leaf match wins)."""
        hits = [i for i, n in enumerate(self.names) if part in n]
        if len(hits) > 1:
            exact = [i for i in hits if self.names[i].split('[')[0].split('/')[-1] == part.split('/')[-1]]
            hits = exact if len(exact) == 1 else hits
        if len(hits) != 1:
            sys.exit(f"{self.path}: column '{part}' matches {len(hits)} names: "
                     f"{[self.names[i] for i in hits][:6]}")
        return hits[0]

    def values(self, part):
        """Column values; an X or Z of a simulation capture (no digit of the radix) reads as -1."""
        i = self.col(part)
        if i not in self._cache:
            base = self.BASE.get(self.radix[i].upper(), 16)
            self._cache[i] = [self._int(r[i].strip(), base) for r in self.rows]
        return self._cache[i]

    @staticmethod
    def _int(text, base):
        try:
            return int(text, base)
        except ValueError:
            if text and set(text.lower()) <= set('0123456789abcdef_xz'):
                return -1
            raise

    def window_starts(self):
        """Samples where a new trigger window begins (column 'Sample in Window' restarts)."""
        if 'Sample in Window' not in self.names:
            return {0}
        w = self.values('Sample in Window')
        return {0} | {s for s in range(1, len(w)) if w[s] < w[s - 1]}

# ---------------------------------------------------------------------------------------------------
# PPI: per-lane bytes -> packets


def parse_packet(b):
    """One CSI-2 packet from the merged bytes of a burst."""
    if len(b) < 4:
        return {'error': f'burst of {len(b)} bytes'}
    st, (h0, h1, h2) = ecc_check(b[0], b[1], b[2], b[3])
    pk = {'vc': h0 >> 6, 'dt': h0 & 0x3F, 'wc': h1 | (h2 << 8), 'ecc': st}
    if st == 'error':
        pk['error'] = 'ECC'
        return pk
    if pk['dt'] <= 0x0F:                    # short packet: WC is the data field
        pk['trailer'] = len(b) - 4
        return pk
    wc = pk['wc']
    if len(b) < 4 + wc + 2:
        pk['error'] = f'truncated ({len(b) - 4} of {wc + 2} bytes)'
        return pk
    pk['payload'] = bytes(b[4:4 + wc])
    pk['crc_ok'] = crc16(pk['payload']) == b[4 + wc] | (b[5 + wc] << 8)
    pk['trailer'] = len(b) - (wc + 6)
    if not pk['crc_ok']:
        pk['error'] = 'CRC'
    return pk


def decode_ppi(cap, lanes, data, valid, active):
    d = [cap.values(data.format(n=i)) for i in range(lanes)]
    v = [cap.values(valid.format(n=i)) for i in range(lanes)]
    a = [cap.values(active.format(n=i)) for i in range(lanes)]
    starts = cap.window_starts()
    packets, lane_bytes, burst, partial = [], None, None, False

    def finish(truncated):
        merged = []
        while True:                         # byte k of the packet is on lane k % lanes
            lane, idx = len(merged) % lanes, len(merged) // lanes
            if idx >= len(lane_bytes[lane]):
                break
            merged.append(lane_bytes[lane][idx])
        pk = parse_packet(merged)
        pk['sample'] = burst
        pk['lane_bytes'] = [len(x) for x in lane_bytes]
        if partial or truncated:
            pk['partial'] = 'start' if partial else 'end'
        packets.append(pk)

    for s in range(len(cap.rows)):
        act = any(a[i][s] for i in range(lanes))
        if burst is not None and (s in starts or not act):
            finish(truncated=s in starts and act)
            burst = None
        if burst is None and act:
            burst, partial = s, s in starts
            lane_bytes = [[] for _ in range(lanes)]
        if burst is not None:
            for i in range(lanes):
                if v[i][s]:
                    lane_bytes[i].append(d[i][s])
    if burst is not None:
        finish(truncated=True)
    return packets


def ppi_lines(packets, image_dt):
    """Image lines (pixels) of the complete, error-free long packets of data type image_dt."""
    return [raw10_unpack(p['payload']) for p in packets
            if 'partial' not in p and 'error' not in p and p.get('dt') == image_dt]


def report_ppi(packets, image_dt):
    full = [p for p in packets if 'partial' not in p]
    errors = [p for p in full if 'error' in p]
    names = {0x00: 'FS', 0x01: 'FE', 0x02: 'LS', 0x03: 'LE', 0x2B: 'RAW10'}
    kinds = {}
    for p in full:
        if 'dt' in p:
            k = names.get(p['dt'], f"DT 0x{p['dt']:02X}")
            kinds[k] = kinds.get(k, 0) + 1
    wcs = sorted({p['wc'] for p in full if p.get('dt') == image_dt})
    print(f"bursts {len(packets)} (partial {len(packets) - len(full)}), packets {kinds}")
    print(f"ECC corrected {sum(p.get('ecc') == 'corrected' for p in full)}, errors {len(errors)}"
          f", CRC ok {sum(1 for p in full if p.get('crc_ok'))}"
          f", trailer bytes max {max([p.get('trailer', 0) for p in full], default=0)}")
    if wcs:
        print(f"image lines: WC {wcs} -> {[w * 8 // 10 for w in wcs]} pixels")
    for p in errors[:10]:
        print(f"  sample {p['sample']}: {p['error']} {({k: p[k] for k in ('vc', 'dt', 'wc') if k in p})}")
    return len(errors)

# ---------------------------------------------------------------------------------------------------
# AXI4-Stream video of the CSI-2 Rx Subsystem -> lines


def decode_axis(cap, tdata, tvalid, tready, tuser, tlast, ppc, bpp):
    td, tv, tu, tl = (cap.values(x) for x in (tdata, tvalid, tuser, tlast))
    tr = cap.values(tready) if tready else [1] * len(td)
    starts = cap.window_starts()
    lines, cur, partial, sof = [], [], True, []
    mask = (1 << bpp) - 1
    for s in range(len(td)):
        if s in starts and s:
            if cur:
                lines.append((cur, 'end'))
            cur, partial = [], True
        if not (tv[s] and tr[s]):
            continue
        if tu[s] & 1:                        # start of frame: the line before it is cut
            if cur:
                lines.append((cur, 'cut'))
            cur, partial = [], False
            sof.append(len(lines))
        cur += [(td[s] >> (k * bpp)) & mask for k in range(ppc)]
        if tl[s]:
            lines.append((cur, 'start' if partial else ''))
            cur, partial = [], False
    if cur:
        lines.append((cur, 'end'))
    return lines, sof


def report_axis(lines, sof):
    full = [x for x, flag in lines if not flag]
    lens = sorted({len(x) for x in full})
    print(f"lines {len(lines)} (partial {len(lines) - len(full)}), pixels per line {lens}, SOF at {sof[:8]}")
    return 0

# ---------------------------------------------------------------------------------------------------
# compare two captures


def compare_seq(a, b, what, fields=None):
    """First difference of two sequences; fields names the parts of tuple elements."""
    def show(x, y, label):
        if isinstance(x, (bytes, list)) and isinstance(y, (bytes, list)):
            j = next((k for k, (u, w) in enumerate(zip(x, y)) if u != w), min(len(x), len(y)))
            print(f"  {label} differs at offset {j}: {list(x[j:j + 8])} vs {list(y[j:j + 8])}"
                  f" (lengths {len(x)}, {len(y)})")
        else:
            print(f"  {label}: {x} vs {y}")

    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            print(f"first difference: {what} {i}")
            if isinstance(x, tuple):
                for k, (u, w) in enumerate(zip(x, y)):
                    if u != w:
                        show(u, w, fields[k] if fields else f'field {k}')
            else:
                show(x, y, what)
            return 1
    print(f"{min(len(a), len(b))} {what}s identical (A has {len(a)}, B has {len(b)})")
    return 0


def first_frame(seq, is_fs):
    """Start at the first frame start when both captures have one, else at the first element."""
    idx = next((i for i, x in enumerate(seq) if is_fs(x)), None)
    return seq[idx:] if idx is not None else seq

# ---------------------------------------------------------------------------------------------------
# bursts: per-lane dummy data against the truth file of the TN1 line generator


def read_truth(path):
    """{lane: [(burst, payload, t_first_ps, t_end_ps)]} from the lines 'B <burst> <lane> <n> <t0> <t1> <hex>'."""
    truth = {}
    with open(path) as f:
        for line in f:
            t = line.split()
            if len(t) < 6 or t[0] != 'B':
                continue
            bid, lane, n, t0, t1 = (int(x) for x in t[1:6])
            data = bytes.fromhex(t[6]) if len(t) > 6 else b''
            if len(data) != n:
                sys.exit(f"{path}: burst {bid} lane {lane} has {len(data)} bytes, its header says {n}")
            truth.setdefault(lane, []).append((bid, data, t0, t1))
    return truth


def has_col(cap, part):
    return any(part in n for n in cap.names)


def decode_bursts(cap, lanes, data, valid, active, flags, time_col):
    """Per lane, the runs of rxactivehs: bytes and sample times of rxvalidhs, rising edges of each flag
    column. Also, per lane, the events outside a run: rxvalidhs samples and flag rising edges."""
    tm = cap.values(time_col) if time_col and has_col(cap, time_col) else None
    runs_all, stray_all = [], []
    for i in range(lanes):
        d, v, a = (cap.values(x.format(n=i)) for x in (data, valid, active))
        fl = {k: cap.values(c.format(n=i)) for k, c in flags.items()}
        runs, cur = [], None
        stray = {'rxvalidhs': 0, **{k: 0 for k in fl}, 'X on rxvalidhs, rxactivehs or a flag': 0}
        for s in range(len(cap.rows)):
            if v[s] < 0 or a[s] < 0 or any(fl[k][s] < 0 for k in fl):
                stray['X on rxvalidhs, rxactivehs or a flag'] += 1
                v[s], a[s] = max(v[s], 0), max(a[s], 0)
                for k in fl:
                    fl[k][s] = max(fl[k][s], 0)
            rise = {k: int(fl[k][s] and (s == 0 or not fl[k][s - 1])) for k in fl}
            if a[s]:
                if cur is None:
                    cur = {'bytes': [], 'times': [], 'flags': {k: 0 for k in fl}, 'sample': s}
                if v[s]:
                    cur['bytes'].append(d[s])
                    cur['times'].append(tm[s] if tm else None)
                for k in fl:
                    cur['flags'][k] += rise[k]
            else:
                if cur is not None:
                    runs.append(cur)
                    cur = None
                stray['rxvalidhs'] += v[s]
                for k in fl:
                    stray[k] += rise[k]
        if cur is not None:
            cur['open'] = True
            runs.append(cur)
        runs_all.append(runs)
        stray_all.append(stray)
    return runs_all, stray_all


def check_bursts(label, runs, stray, truth, lanes, show=8, max_trailer=None):
    """Print one capture against the truth; return the number of errors. max_trailer: trailer bytes
    allowed after the payload of a burst (None: any number).
    Burst k of a lane pairs with burst k of that lane in the truth. A lost and an added burst on one lane keep
    the count, and the bursts between them then pair with their neighbours; when the payloads repeat, only the
    time shows it. So, with sample times, each pair must also hold in time: the last byte of the burst up to its
    payload length reaches the PPI after it left the pad, as long after it as the median of the capture,
    within half the smallest gap between two bursts of a lane. Lane-level messages come first."""
    errs, head, msgs, n_ok, n_tot, trailers, lat, late = 0, [], [], 0, 0, [], [], []

    def bad(msg, lane_level=False, n=1):
        nonlocal errs
        errs += n
        (head if lane_level else msgs).append(msg)

    for i in range(lanes):
        tr = truth.get(i, [])
        got = [r for r in runs[i] if not r.get('open')]
        if runs[i] and runs[i][-1].get('open'):
            bad(f"lane {i}: still in a burst at the end of the capture", True)
        if len(got) != len(tr):
            bad(f"lane {i}: {len(got)} bursts, the truth has {len(tr)}", True)
        for k, (bid, pay, t0, t1) in enumerate(tr):
            n_tot += 1
            if k >= len(got):
                continue
            r = got[k]
            b, pay = r['bytes'], list(pay)
            m = min(len(b), len(pay)) - 1
            if m >= 0 and r['times'][m] is not None:
                # time the byte m left the pad: the burst is the sync byte and the payload, t0 to t1
                late.append((i, bid, (r['times'][m] - (t0 + (m + 2) * (t1 - t0) / (len(pay) + 1))) / 1000.0))
            if b[:len(pay)] == pay:
                n_ok += 1
                trailers.append(len(b) - len(pay))
                if max_trailer is not None and len(b) - len(pay) > max_trailer:
                    bad(f"lane {i} burst {bid}: {len(b) - len(pay)} trailer bytes after the payload"
                        f" (at most {max_trailer}): {list(b[len(pay):len(pay) + 6])}")
                if pay and r['times'][len(pay) - 1] is not None:
                    lat.append((r['times'][len(pay) - 1] - t1) / 1000.0)
            else:
                j = next((x for x in range(min(len(b), len(pay))) if b[x] != pay[x]), min(len(b), len(pay)))
                bad(f"lane {i} burst {bid}: {len(b)} bytes for {len(pay)} sent, first difference at byte {j}:"
                    f" got {list(b[j:j + 6])}, sent {list(pay[j:j + 6])}")
            for fk, cnt in r['flags'].items():
                exp = 1 if fk == 'rxsynchs' else 0
                if cnt != exp:
                    bad(f"lane {i} burst {bid}: {fk} {cnt} times (expected {exp})")
        for fk, cnt in stray[i].items():
            if cnt:
                bad(f"lane {i}: {fk} {cnt} times outside a burst", True)
    if late:
        med = statistics.median(x for _, _, x in late)
        gaps = [b[3] - a[3] for i in range(lanes) for a, b in zip(truth.get(i, []), truth.get(i, [])[1:])]
        tol = min(gaps) / 2000.0 if gaps else float('inf')
        for i in range(lanes):
            off = [(bid, x) for li, bid, x in late if li == i and (x <= 0 or abs(x - med) > tol)]
            if off:
                bad(f"lane {i}: {len(off)} bursts out of time, the first is burst {off[0][0]} ({off[0][1]:.1f} ns"
                    f" after it left the pad; capture median {med:.1f} ns, tolerance {tol:.1f} ns): paired with"
                    f" another burst", True, len(off))
    span = (lambda x, f: f"{min(x):{f}}..{max(x):{f}}" if x else "-")
    print(f"{label}: {lanes} lane(s), {n_ok}/{n_tot} bursts carry the payload sent, trailer bytes"
          f" {span(trailers, 'd')} (in {sum(1 for t in trailers if t)} bursts), latency of the last payload"
          f" byte {span(lat, '.1f')} ns, errors {errs}")
    for x in (head + msgs)[:show]:
        print(f"  {x}")
    if len(head + msgs) > show:
        print(f"  ... {len(head + msgs) - show} more")
    return errs


def trailer_limits(spec, n):
    """--max-trailer: None, one value for all captures, or a comma list ('-' = no limit) of n values."""
    if spec is None:
        return [None] * n
    vals = [None if v.strip() == '-' else int(v) for v in spec.split(',')]
    if len(vals) == 1:
        return vals * n
    if len(vals) != n:
        sys.exit(f"--max-trailer: {len(vals)} values for {n} captures")
    return vals


def run_bursts(a):
    truth = read_truth(a.truth)
    total = []
    limits = trailer_limits(a.max_trailer, len(a.csv))
    for k, path in enumerate(a.csv):
        cap = Capture(path)
        flags = {name: col for name, col in (('rxsynchs', a.sync), ('errsoths', a.errsot),
                                             ('errsotsynchs', a.errsotsync))
                 if col and has_col(cap, col.format(n=0))}
        runs, stray = decode_bursts(cap, a.lanes, a.data, a.valid, a.active, flags, a.time)
        total.append(check_bursts(f"{chr(65 + k)} {os.path.basename(path)}", runs, stray, truth, a.lanes,
                                  max_trailer=limits[k]))
    print(f"RESULT: {'PASS' if not any(total) else 'FAIL'} "
          f"({', '.join(f'{chr(65 + k)} {e} errors' for k, e in enumerate(total))})")
    return int(any(total))

# ---------------------------------------------------------------------------------------------------
# self test


def ila_csv(path, cols, radix):
    """Write samples {name: [values]} in the CSV layout of write_hw_ila_data."""
    names = list(cols)
    n = len(cols[names[0]])
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Sample in Buffer', 'Sample in Window', 'TRIGGER'] + names)
        w.writerow(['Radix - UNSIGNED', 'UNSIGNED', 'UNSIGNED'] + [radix[x] for x in names])
        for s in range(n):
            vals = [format(cols[x][s], 'x' if radix[x] == 'HEX' else 'b') for x in names]
            w.writerow([s, s, int(s == 8)] + vals)


def make_packet(dt, wc_or_data, payload=b'', vc=0, flip_hdr_bit=None, bad_crc=False):
    di = (vc << 6) | dt
    wc = len(payload) if dt > 0x0F else wc_or_data
    h = [di, wc & 0xFF, wc >> 8]
    ecc = ecc24(h[0] | h[1] << 8 | h[2] << 16)
    if flip_hdr_bit is not None:
        h[flip_hdr_bit // 8] ^= 1 << (flip_hdr_bit % 8)
    b = bytes(h + [ecc])
    if dt > 0x0F:
        crc = crc16(payload) ^ (1 if bad_crc else 0)
        b += payload + bytes([crc & 0xFF, crc >> 8])
    return b


def synth_ppi(packets, lanes, rnd):
    """Lane samples of a capture that starts inside a burst and ends inside one."""
    cols = {}
    for i in range(lanes):
        cols.update({f'u_ppi/dl{i}_rxdatahs[7:0]': [], f'u_ppi/dl{i}_rxvalidhs': [], f'u_ppi/dl{i}_rxactivehs': []})

    def emit(lane_bytes, skew, keep_from=0):
        length = max(skew[i] + len(lane_bytes[i]) for i in range(lanes)) + 2
        for t in range(keep_from, length):
            for i in range(lanes):
                k = t - skew[i] - 1
                on = 0 <= k < len(lane_bytes[i])
                cols[f'u_ppi/dl{i}_rxdatahs[7:0]'].append(lane_bytes[i][k] if on else rnd.randrange(256))
                cols[f'u_ppi/dl{i}_rxvalidhs'].append(int(on))
                cols[f'u_ppi/dl{i}_rxactivehs'].append(int(skew[i] <= t <= skew[i] + len(lane_bytes[i])))

    def idle(n):
        for _ in range(n):
            for i in range(lanes):
                cols[f'u_ppi/dl{i}_rxdatahs[7:0]'].append(rnd.randrange(256))
                cols[f'u_ppi/dl{i}_rxvalidhs'].append(0)
                cols[f'u_ppi/dl{i}_rxactivehs'].append(0)

    def lanes_of(b):
        lb = [list(b[i::lanes]) for i in range(lanes)]
        for x in lb:                         # bytes of the HS trail that some receivers pass on
            x += [rnd.randrange(256) for _ in range(rnd.randrange(3))]
        return lb

    emit(lanes_of(packets[0]), [0] * lanes, keep_from=5)   # capture starts inside this burst
    for b in packets[1:-1]:
        idle(rnd.randrange(3, 9))
        emit(lanes_of(b), [rnd.randrange(3) for _ in range(lanes)])
    idle(4)
    lb = lanes_of(packets[-1])
    emit([x[:3] for x in lb], [0] * lanes)                  # capture ends inside this burst
    for i in range(lanes):                                   # still active at the last sample
        cols[f'u_ppi/dl{i}_rxactivehs'][-1] = 1
    return cols


def selftest(tx_model):
    fails = 0

    def check(cond, what):
        nonlocal fails
        print(f"{'PASS' if cond else 'FAIL'}: {what}")
        fails += not cond

    # CSI-2 v1.3 9.6: CRC examples (checksum LS byte, MS byte)
    for hexs, ls, ms in (("FF 00 00 02 B9 DC F3 72 BB D4 B8 5A C8 75 C2 7C 81 F8 05 DF FF 00 00 01", 0xF0, 0x00),
                         ("FF 00 00 00 1E F0 1E C7 4F 82 78 C5 82 E0 8C 70 D2 3C 78 E9 FF 00 00 01", 0x69, 0xE5)):
        c = crc16(bytes.fromhex(hexs))
        check((c & 0xFF, c >> 8) == (ls, ms), f"CRC example of CSI-2 v1.3 9.6 -> {c & 0xFF:02X} {c >> 8:02X}")
    rnd = random.Random(1)
    data = bytes(rnd.randrange(256) for _ in range(4096))
    check(crc16(data) == crc16_bitwise(data), "table CRC equals the bitwise CRC of Figure 54")
    # CSI-2 v1.3 Figure 46: DI 0x37, WC 0x01F0 -> ECC 0x3F
    check(ecc24(0x37 | 0xF0 << 8 | 0x01 << 16) == 0x3F, "ECC example of CSI-2 v1.3 Figure 46 (0x3F)")
    h, e = (0x37, 0xF0, 0x01), 0x3F
    one = all(ecc_check(*[x ^ ((1 << (bit % 8)) if bit // 8 == k else 0) for k, x in enumerate(h)], e)
              == ('corrected', h) for bit in range(24))
    one &= all(ecc_check(*h, e ^ (1 << bit)) == ('corrected', h) for bit in range(6))
    check(one, "every single-bit error of the 30-bit header code word is corrected")
    word = h[0] | h[1] << 8 | h[2] << 16 | e << 24
    two = True
    for i in range(30):
        for j in range(i + 1, 30):
            w = word ^ (1 << i) ^ (1 << j)
            two &= ecc_check(w & 0xFF, (w >> 8) & 0xFF, (w >> 16) & 0xFF, w >> 24)[0] == 'error'
    check(two, "every double-bit error is detected")
    px = [rnd.randrange(1024) for _ in range(64)]
    check(raw10_unpack(raw10_pack(px)) == px, "RAW10 pack and unpack")

    # PPI round trip: 4 lanes, skewed valid, HS-trail bytes, one corrected header, one CRC error
    work = os.path.join(FPGA, 'work', 'csi2_dump_selftest')
    os.makedirs(work, exist_ok=True)
    width, height = 64, 6
    img = [[(x * 16 + y * 3) & 0x3FF for x in range(width)] for y in range(height)]
    pk = [make_packet(0x2B, 0, raw10_pack(img[-1]))]                       # cut by the capture start
    pk += [make_packet(0x00, 1)]
    pk += [make_packet(0x2B, 0, raw10_pack(line), flip_hdr_bit=5 if y == 2 else None) for y, line in enumerate(img)]
    pk += [make_packet(0x2B, 0, raw10_pack(img[0]), bad_crc=True), make_packet(0x01, 1)]
    pk += [make_packet(0x00, 2)]                                            # cut by the capture end
    for lanes in (1, 2, 4):
        cols = synth_ppi(pk, lanes, rnd)
        path = os.path.join(work, f'ppi_{lanes}l.csv')
        ila_csv(path, cols, {k: 'HEX' if 'data' in k else 'BIN' for k in cols})
        got = decode_ppi(Capture(path), lanes, 'dl{n}_rxdatahs', 'dl{n}_rxvalidhs', 'dl{n}_rxactivehs')
        full = [p for p in got if 'partial' not in p]
        ok = [p.get('partial') for p in got] == ['start'] + [None] * (len(pk) - 2) + ['end']
        ok &= [p.get('dt') for p in full] == [0x00] + [0x2B] * (height + 1) + [0x01]
        ok &= ppi_lines(got, 0x2B) == img
        ok &= [p.get('error') for p in full].count('CRC') == 1 and full[3]['ecc'] == 'corrected'
        check(ok, f"PPI round trip on {lanes} lane(s): packets, image, one ECC correction, one CRC error")

    # AXIS round trip: 4 pixels per beat, a capture that starts inside a line
    ppc, bpp = 4, 10
    td, tv, tu, tl = [], [], [], []
    for y, line in enumerate(img):
        for x in range(0, width, ppc):
            while rnd.random() < 0.3:
                td.append(rnd.randrange(1 << 40)), tv.append(0), tu.append(0), tl.append(0)
            td.append(sum(v << (k * bpp) for k, v in enumerate(line[x:x + ppc])))
            tv.append(1), tu.append(int(y == 0 and x == 0)), tl.append(int(x + ppc == width))
    pre = 7                                          # a capture that starts 7 beats into the last line
    line = img[-1]
    td = [sum(v << (k * bpp) for k, v in enumerate(line[x:x + ppc])) for x in range(pre * ppc, width, ppc)] + td
    tv = [1] * (len(td) - len(tv)) + tv
    tu = [0] * (len(td) - len(tu)) + tu
    tl = [0] * (width // ppc - pre - 1) + [1] + tl
    path = os.path.join(work, 'axis.csv')
    ila_csv(path, {'u_csi/video_out_tdata[39:0]': td, 'u_csi/video_out_tvalid': tv,
                   'u_csi/video_out_tuser[0:0]': tu, 'u_csi/video_out_tlast': tl},
            {'u_csi/video_out_tdata[39:0]': 'HEX', 'u_csi/video_out_tvalid': 'BIN',
             'u_csi/video_out_tuser[0:0]': 'BIN', 'u_csi/video_out_tlast': 'BIN'})
    lines, sof = decode_axis(Capture(path), 'tdata', 'tvalid', None, 'tuser', 'tlast', ppc, bpp)
    check([x for x, f in lines if not f] == img and lines[0][1] == 'start' and sof == [1],
          "AXIS round trip: lines, partial first line, start of frame")

    bursts_selftest(work, rnd, check)
    if tx_model:
        fails += tx_model_check(work, rnd)
    print(f"selftest: {'PASS' if fails == 0 else f'{fails} FAIL'}")
    return int(fails > 0)


SYNTH_PS = 5556     # sample period of the synthetic captures (byte clock of 1440 Mb/s)
SYNTH_IDLE = 4      # idle samples at the start of each slot


def synth_times(k, n, slot, lat_ps=20000):
    """Truth times (t0, t1) of an n-byte burst whose first byte is sample k * slot + SYNTH_IDLE of a synthetic
    capture, as if it had left the pad lat_ps earlier: t0 is the start of the sync byte, t1 the end of the
    last payload byte."""
    t0 = (k * slot + SYNTH_IDLE) * SYNTH_PS - lat_ps - 2 * SYNTH_PS
    return t0, t0 + (n + 1) * SYNTH_PS


def synth_bursts(truth, lanes, rnd, faults, slot):
    """Lane samples of the truth bursts, burst k in samples k * slot to (k + 1) * slot - 1: SYNTH_IDLE idle
    samples, the payload plus 0..2 trailer bytes (rxsynchs with the first byte, rxactivehs one sample longer
    than rxvalidhs), then idle samples to the end of the slot. Idle samples carry random data.
    faults: {(kind, lane, burst index)}, kind 'flip' (one payload byte), 'drop' (no burst), 'errsot'
    (errsoths pulse), 'resync' (a second rxsynchs) or 'again' (the burst once more, in a slot after the last
    one)."""
    names = ['sim_time_ps']
    for i in range(lanes):
        names += [f'u_rx/dl{i}_rxdatahs[7:0]', f'u_rx/dl{i}_rxvalidhs', f'u_rx/dl{i}_rxactivehs',
                  f'u_rx/dl{i}_rxsynchs', f'u_rx/dl{i}_errsoths', f'u_rx/dl{i}_errsotsynchs']
    cols = {n: [] for n in names}

    def sample(vals):
        cols['sim_time_ps'].append(len(cols['sim_time_ps']) * SYNTH_PS)
        for i in range(lanes):
            for name, x in zip(names[1 + 6 * i:7 + 6 * i], vals[i] + (0,)):
                cols[name].append(x)

    def idle():
        return [(rnd.randrange(256), 0, 0, 0, 0) for _ in range(lanes)]

    def stream(pay):
        return list(pay) + [rnd.randrange(256) for _ in range(rnd.randrange(3))]

    slots = []      # (burst index, stream per lane or None, copy)
    for k in range(len(truth[0])):
        streams = []
        for i in range(lanes):
            pay = bytearray(truth[i][k][1])
            if ('flip', i, k) in faults:
                pay[len(pay) // 2] ^= 0x10
            streams.append(None if ('drop', i, k) in faults else stream(pay))
        slots.append((k, streams, False))
    for kind, i, k in sorted(faults):
        if kind == 'again':
            slots.append((k, [stream(truth[i][k][1]) if x == i else None for x in range(lanes)], True))
    for k, streams, copy in slots:
        start = len(cols['sim_time_ps'])
        for _ in range(SYNTH_IDLE):
            sample(idle())
        live = [x for x in streams if x is not None]
        for s in range(max(map(len, live)) + 2 if live else 0):
            vals = []
            for i, st in enumerate(streams):
                if st is None:
                    vals.append((rnd.randrange(256), 0, 0, 0, 0))
                    continue
                on = s < len(st)
                sync = int(on and (s == 0 or (not copy and ('resync', i, k) in faults and s == 2)))
                vals.append((st[s] if on else rnd.randrange(256), int(on), int(s <= len(st)), sync,
                             int(not copy and ('errsot', i, k) in faults and s == 1)))
            sample(vals)
        if len(cols['sim_time_ps']) - start > slot:
            sys.exit(f"synth_bursts: burst {k} needs more than {slot} samples")
        while len(cols['sim_time_ps']) - start < slot:
            sample(idle())
    return cols


def write_truth(path, truth, lanes):
    """A truth file in the line generator's format from {lane: [(burst, payload, t0, t1)]}."""
    with open(path, 'w') as f:
        for k in range(len(truth[0])):
            for i in range(lanes):
                bid, pay, t0, t1 = truth[i][k]
                f.write(f"B {bid} {i} {len(pay)} {t0} {t1} {pay.hex()}\n")


def bursts_selftest(work, rnd, check):
    """Bursts mode against a truth file of the line generator's format: a clean capture, one with four
    planted faults, and one lane that loses a burst and repeats another with the same payload."""
    lanes, lens, slot = 2, (1, 5, 64, 3), 80
    truth = {i: [(k, bytes(rnd.randrange(256) for _ in range(n)), *synth_times(k, n, slot))
                 for k, n in enumerate(lens)] for i in range(lanes)}
    tpath = os.path.join(work, 'bursts_truth.txt')
    write_truth(tpath, truth, lanes)
    flags = {'rxsynchs': 'dl{n}_rxsynchs', 'errsoths': 'dl{n}_errsoths', 'errsotsynchs': 'dl{n}_errsotsynchs'}
    errs, decoded = [], {}
    for name, faults in (('clean', set()),
                         ('faults', {('flip', 1, 2), ('drop', 0, 3), ('errsot', 0, 1), ('resync', 1, 1)})):
        cols = synth_bursts(truth, lanes, rnd, faults, slot)
        path = os.path.join(work, f'bursts_{name}.csv')
        ila_csv(path, cols, {c: 'HEX' if 'data' in c else 'BIN' for c in cols})
        runs, stray = decode_bursts(Capture(path), lanes, 'dl{n}_rxdatahs', 'dl{n}_rxvalidhs',
                                    'dl{n}_rxactivehs', flags, 'sim_time_ps')
        decoded[name] = (runs, stray)
        errs.append(check_bursts(f"  bursts {name}", runs, stray, read_truth(tpath), lanes))
    check(errs[0] == 0, "bursts: a clean capture with trailer bytes matches the truth")
    check(errs[1] == 4, f"bursts: the four planted faults are found ({errs[1]} errors: flipped byte,"
                        " missing burst, errsoths, second rxsynchs)")
    # Pairing in time: eight bursts with the same payload on one lane; burst 5 is lost and burst 7 comes once
    # more. Count and payloads still match in order, bursts 5..7 pair with their neighbours: three errors.
    same = bytes(rnd.randrange(256) for _ in range(3))
    truth1 = {0: [(k, same, *synth_times(k, len(same), slot)) for k in range(8)]}
    tpath1 = os.path.join(work, 'bursts_truth_same.txt')
    write_truth(tpath1, truth1, 1)
    path = os.path.join(work, 'bursts_shifted.csv')
    cols = synth_bursts(truth1, 1, rnd, {('drop', 0, 5), ('again', 0, 7)}, slot)
    ila_csv(path, cols, {c: 'HEX' if 'data' in c else 'BIN' for c in cols})
    runs, stray = decode_bursts(Capture(path), 1, 'dl{n}_rxdatahs', 'dl{n}_rxvalidhs', 'dl{n}_rxactivehs',
                                flags, 'sim_time_ps')
    in_order = len(runs[0]) == 8 and all(r['bytes'][:3] == list(same) for r in runs[0])
    e_shift = check_bursts("  bursts shifted", runs, stray, read_truth(tpath1), 1)
    check(in_order and e_shift == 3, f"bursts: a lost and a repeated burst with the same payload are found by"
                                     f" their time ({e_shift} errors; count and payloads match in order:"
                                     f" {in_order})")
    # trailer limit on the clean capture (0..2 trailer bytes per burst): every burst over the limit is one
    # error, and the limit of 2 passes
    runs, stray = decoded['clean']
    over = sum(1 for i in range(lanes) for r, (_b, pay, _t0, _t1) in zip(runs[i], truth[i])
               if len(r['bytes']) - len(pay) > 0)
    e0 = check_bursts("  bursts clean, at most 0 trailer bytes", runs, stray, read_truth(tpath), lanes,
                      show=0, max_trailer=0)
    e2 = check_bursts("  bursts clean, at most 2 trailer bytes", runs, stray, read_truth(tpath), lanes,
                      show=0, max_trailer=2)
    check(over > 0 and e0 == over and e2 == 0,
          f"bursts: --max-trailer flags each burst over the limit ({e0} errors for {over} bursts with"
          f" trailer bytes at limit 0, {e2} at limit 2)")
    check(trailer_limits('-,0', 2) == [None, 0] and trailer_limits('1', 3) == [1, 1, 1],
          "bursts: --max-trailer lists ('-,0' and one value for all captures)")


def tx_model_check(work, rnd):
    """ECC and CRC of random vectors against csi2_ecc and csi2_crc_byte of the repo Tx model (XSIM)."""
    rtl = os.path.join(REPO, 'ref', 'mipi_tx_dphy_model', 'rtl')
    xbin = '/opt/xilinx/2025.2/Vivado/bin'
    hdr = [rnd.randrange(1 << 24) for _ in range(200)]
    pay = [rnd.randrange(256) for _ in range(1000)]
    with open(os.path.join(work, 'hdr.hex'), 'w') as f:
        f.write('\n'.join(f'{x:06x}' for x in hdr) + '\n')
    with open(os.path.join(work, 'pay.hex'), 'w') as f:
        f.write('\n'.join(f'{x:02x}' for x in pay) + '\n')
    with open(os.path.join(work, 'tb_func.v'), 'w') as f:
        f.write(f"""module tb_func;
`include "mipi_csi2_func.v"
  reg [23:0] hdr [0:{len(hdr) - 1}];
  reg [7:0]  pay [0:{len(pay) - 1}];
  reg [15:0] c;
  integer i;
  initial begin
    $readmemh("hdr.hex", hdr);
    $readmemh("pay.hex", pay);
    for (i = 0; i < {len(hdr)}; i = i + 1) $display("ECC %h %h", hdr[i], csi2_ecc(hdr[i]));
    c = 16'hFFFF;
    for (i = 0; i < {len(pay)}; i = i + 1) c = csi2_crc_byte(c, pay[i]);
    $display("CRC %h", c);
    $finish;
  end
endmodule
""")
    log = os.path.join(work, 'xsim_func.log')
    with open(log, 'w') as lf:
        for cmd in ([f'{xbin}/xvlog', '-i', rtl, 'tb_func.v'], [f'{xbin}/xelab', 'tb_func', '-s', 'tb_func'],
                    [f'{xbin}/xsim', 'tb_func', '-R']):
            if subprocess.run(cmd, cwd=work, stdout=lf, stderr=subprocess.STDOUT).returncode:
                print(f"FAIL: {os.path.basename(cmd[0])} (see {log})")
                return 1
    ecc_tx, crc_tx = {}, None
    for line in open(log):
        t = line.split()
        if len(t) == 3 and t[0] == 'ECC':
            ecc_tx[int(t[1], 16)] = int(t[2], 16)
        elif len(t) == 2 and t[0] == 'CRC':
            crc_tx = int(t[1], 16)
    ok = len(ecc_tx) == len(set(hdr)) and all(ecc24(x) == ecc_tx[x] for x in hdr) and crc_tx == crc16(pay)
    print(f"{'PASS' if ok else 'FAIL'}: ECC of {len(hdr)} headers and CRC of {len(pay)} bytes equal the Tx model"
          f" (ref/mipi_tx_dphy_model/rtl/mipi_csi2_func.v, XSIM)")
    return int(not ok)

# ---------------------------------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def ppi_opts(p):
        p.add_argument('--lanes', type=int, default=4)
        p.add_argument('--data', default='dl{n}_rxdatahs')
        p.add_argument('--valid', default='dl{n}_rxvalidhs')
        p.add_argument('--active', default='dl{n}_rxactivehs')
        p.add_argument('--dt', type=lambda x: int(x, 0), default=0x2B, help='image data type (RAW10 0x2B)')

    def axis_opts(p):
        for k in ('tdata', 'tvalid', 'tuser', 'tlast'):
            p.add_argument(f'--{k}', default=k)
        p.add_argument('--tready', default=None)
        p.add_argument('--ppc', type=int, default=4)
        p.add_argument('--bpp', type=int, default=10)

    p = sub.add_parser('ppi')
    p.add_argument('csv')
    ppi_opts(p)
    p.add_argument('--pgm')
    p = sub.add_parser('axis')
    p.add_argument('csv')
    axis_opts(p)
    p.add_argument('--pgm')
    p = sub.add_parser('compare')
    p.add_argument('mode', choices=('ppi', 'axis'))
    p.add_argument('a')
    p.add_argument('b')
    ppi_opts(p)
    axis_opts(p)
    p.add_argument('--headers-only', action='store_true', help='PPI: compare VC/DT/WC only (live scene)')
    p = sub.add_parser('bursts')
    p.add_argument('csv', nargs='+')
    p.add_argument('--truth', required=True, help='truth file of fpga/exp1/dphy_line_gen.sv')
    p.add_argument('--lanes', type=int, default=4)
    p.add_argument('--data', default='dl{n}_rxdatahs')
    p.add_argument('--valid', default='dl{n}_rxvalidhs')
    p.add_argument('--active', default='dl{n}_rxactivehs')
    p.add_argument('--sync', default='dl{n}_rxsynchs')
    p.add_argument('--errsot', default='dl{n}_errsoths')
    p.add_argument('--errsotsync', default='dl{n}_errsotsynchs')
    p.add_argument('--time', default='sim_time_ps')
    p.add_argument('--max-trailer', default=None,
                   help='trailer bytes allowed per burst: one value, or a comma list per capture ("-": no limit)')
    p = sub.add_parser('selftest')
    p.add_argument('--tx-model', action='store_true', help='also check against the Tx model with XSIM')
    a = ap.parse_args()

    if a.cmd == 'selftest':
        return selftest(a.tx_model)
    if a.cmd == 'bursts':
        return run_bursts(a)
    if a.cmd == 'ppi':
        pk = decode_ppi(Capture(a.csv), a.lanes, a.data, a.valid, a.active)
        bad = report_ppi(pk, a.dt)
        if a.pgm and ppi_lines(pk, a.dt):
            write_pgm(a.pgm, ppi_lines(pk, a.dt), 1023)
        return int(bad > 0)
    if a.cmd == 'axis':
        lines, sof = decode_axis(Capture(a.csv), a.tdata, a.tvalid, a.tready, a.tuser, a.tlast, a.ppc, a.bpp)
        report_axis(lines, sof)
        if a.pgm and lines:
            write_pgm(a.pgm, [x for x, f in lines if not f] or [x for x, _ in lines], (1 << a.bpp) - 1)
        return 0
    if a.mode == 'ppi':
        seqs = []
        for path in (a.a, a.b):
            pk = [p for p in decode_ppi(Capture(path), a.lanes, a.data, a.valid, a.active) if 'partial' not in p]
            pk = first_frame(pk, lambda p: p.get('dt') == 0x00)
            seqs.append([(p.get('vc'), p.get('dt'), p.get('wc'), p.get('error'))
                         + (() if a.headers_only else (p.get('payload'),)) for p in pk])
        return compare_seq(seqs[0], seqs[1], 'packet', ('vc', 'dt', 'wc', 'error', 'payload'))
    seqs = []
    for path in (a.a, a.b):
        lines, sof = decode_axis(Capture(path), a.tdata, a.tvalid, a.tready, a.tuser, a.tlast, a.ppc, a.bpp)
        full = [x for x, f in lines if not f]
        seqs.append(full[sof[0]:] if sof and not lines[sof[0]][1] else full)
    return compare_seq(seqs[0], seqs[1], 'line')


if __name__ == '__main__':
    sys.exit(main())
