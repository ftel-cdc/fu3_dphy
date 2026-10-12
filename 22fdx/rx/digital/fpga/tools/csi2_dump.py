#!/usr/bin/env python3
"""Check the CSI-2 traffic in ILA captures of the FPGA prototype (fpga/FPGA_PROTO_PLAN.md).

A capture is the CSV file that Vivado writes with write_hw_ila_data -csv_file: a line of probe names,
a "Radix - ..." line, then one line per sample.

  csi2_dump.py ppi  CAP.csv --lanes 4 --data dl{n}_rxdatahs --valid dl{n}_rxvalidhs \\
                    --active dl{n}_rxactivehs [--dt 0x2B] [--pgm lines.pgm]
  csi2_dump.py axis CAP.csv --tdata tdata --tvalid tvalid [--tready tready] --tuser tuser \\
                    --tlast tlast [--ppc 4] [--bpp 10] [--pgm lines.pgm]
  csi2_dump.py compare {ppi|axis} A.csv B.csv <options of that mode> [--headers-only]
  csi2_dump.py selftest [--tx-model]

A column is chosen by a part of its name; "{n}" stands for the lane number.
PPI mode:
  - one packet per HS burst (CSI-2 v1.3 9.7: the lanes go to LPS between packets);
  - bytes after the packet in a burst are counted as trailer;
  - the ECC (single-bit correction) and the CRC-16 are checked.
"""
import argparse
import csv
import os
import random
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

    BASE = {'HEX': 16, 'BIN': 2, 'OCT': 8, 'UNSIGNED': 10, 'DEC': 10, 'SIGNED': 10}

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
        i = self.col(part)
        if i not in self._cache:
            base = self.BASE.get(self.radix[i].upper(), 16)
            self._cache[i] = [int(r[i].strip(), base) for r in self.rows]
        return self._cache[i]

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

    if tx_model:
        fails += tx_model_check(work, rnd)
    print(f"selftest: {'PASS' if fails == 0 else f'{fails} FAIL'}")
    return int(fails > 0)


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
    p = sub.add_parser('selftest')
    p.add_argument('--tx-model', action='store_true', help='also check against the Tx model with XSIM')
    a = ap.parse_args()

    if a.cmd == 'selftest':
        return selftest(a.tx_model)
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
