#!/usr/bin/env python3
#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-12
# Description     : Timing of AMD's D-PHY RX on Versal, from the VCD of fpga/probe/dphy_exdes_sim.tcl
#                   (step F2).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-12   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Timing of AMD's D-PHY RX on Versal, from the VCD of fpga/probe/dphy_exdes_sim.tcl (step F2).

Answers, for fpga/FPGA_PROTO_PLAN.md:
  FP-2  order of PHY reset, PLL lock, interface ready, bitslice reset and HS-RX disable
        (at start-up and around each HS burst)
  FP-3  latency from the pad to the wizard word and to the PPI, in ns and in byte-clock cycles
  FP-4  bit order of the wizard word: which bit of rx_dl0_hs_dp_w is received first
  FP-6  whether the byte clock keeps running while the clock lane is in LP

  f2_timing.py fpga/work/dphy_exdes_sim/f2.vcd [--bursts 3]

Lane 0 only. Pad bits are taken from data_rxp[0] at both edges of clk_rxp (the HS data is centred
on the DDR clock edges). The sync byte 0xB8 is sent LSB first: 0 0 0 1 1 1 0 1.
"""
import argparse
import bisect
import statistics
import sys

SYNC = [0, 0, 0, 1, 1, 1, 0, 1]


class Vcd:
    """Value changes of the signals of a VCD file, by full path."""

    def __init__(self, path):
        self.codes, self.width, self.times, self.vals = {}, {}, {}, {}
        unit = {'s': 10**12, 'ms': 10**9, 'us': 10**6, 'ns': 10**3, 'ps': 1, 'fs': 1e-3}
        scope, scale, header = [], 1, ''
        with open(path) as f:
            for line in f:
                header += line
                if '$enddefinitions' in line:
                    break
            toks = header.replace('\n', ' ').split()
            i = 0
            while i < len(toks):
                t = toks[i]
                if t == '$timescale':
                    spec = ''.join(toks[i + 1:toks.index('$end', i)])
                    num = ''.join(c for c in spec if c.isdigit())
                    scale = int(num or 1) * unit[spec[len(num):]]
                elif t == '$scope':
                    scope.append(toks[i + 2])
                elif t == '$upscope':
                    scope.pop()
                elif t == '$var':
                    width, code, name = int(toks[i + 2]), toks[i + 3], toks[i + 4]
                    full = '/'.join(scope + [name])
                    self.codes[full] = code
                    self.width[code] = width
                    self.times.setdefault(code, [])
                    self.vals.setdefault(code, [])
                i += 1
            now = 0
            for line in f:
                c = line[:1]
                if c == '#':
                    now = int(line[1:]) * scale
                elif c in '01xzXZ' and len(line) > 1:
                    self._add(line[1:].strip(), now, line[0])
                elif c in 'bB':
                    v, code = line[1:].split()
                    self._add(code, now, v)

    def _add(self, code, t, v):
        if code in self.times:
            try:
                val = int(v, 2)
            except ValueError:
                val = None                   # x or z
            if self.times[code] and self.times[code][-1] == t:
                self.vals[code][-1] = val
            else:
                self.times[code].append(t)
                self.vals[code].append(val)

    def sig(self, leaf):
        """Code of the one signal whose path ends with /leaf, or None."""
        hits = [c for p, c in self.codes.items() if p.split(' ')[0].endswith('/' + leaf)]
        return hits[0] if len(hits) == 1 else None

    def at(self, code, t):
        """Value at time t (after the changes at t)."""
        i = bisect.bisect_right(self.times[code], t) - 1
        return self.vals[code][i] if i >= 0 else None

    def changes(self, code, t0=0, t1=float('inf')):
        ts, vs = self.times[code], self.vals[code]
        i = bisect.bisect_left(ts, t0)
        out = []
        while i < len(ts) and ts[i] <= t1:
            out.append((ts[i], vs[i]))
            i += 1
        return out

    def edges(self, code, rising=True, t0=0, t1=float('inf')):
        prev, out = (self.at(code, t0 - 1) if t0 > 0 else None), []
        for t, v in self.changes(code, t0, t1):
            if v is not None and prev is not None and v != prev and (v == 1) == rising:
                out.append(t)
            prev = v
        return out


def ns(ps):
    return f"{ps / 1000:10.3f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('vcd')
    ap.add_argument('--bursts', type=int, default=3, help='HS bursts of lane 0 to report')
    a = ap.parse_args()
    v = Vcd(a.vcd)
    s = {n: v.sig(n) for n in (
        'phy_reset_w', 'pll_locked_w', 'phy_rdy_out', 'bit_slc_rst_w', 'fifo_rd_clk_t', 'fifo_empty_w',
        'rx_cl_disable_ibuf_w', 'rx_dl0_disable_ibuf_w', 'rx_dl0_lp_dp_w', 'rx_dl0_lp_dn_w',
        'rx_dl0_hs_dp_w', 'clk_rxp', 'data_rxp', 'rxbyteclkhs', 'cl_stopstate', 'cl_rxclkactivehs',
        'cl_enable', 'dl0_enable', 'dl0_stopstate', 'dl0_rxactivehs', 'dl0_rxvalidhs', 'dl0_rxsynchs',
        'dl0_rxdatahs', 'dl0_errsoths', 'dl0_errsotsynchs', 'dl0_txrequesths')}
    missing = [n for n, c in s.items() if c is None]
    if missing:
        print(f"missing in the VCD: {missing}")
    end = max((ts[-1] for ts in v.times.values() if ts), default=0)
    print(f"VCD: {len(v.codes)} signals, {end / 1e6:.1f} us")

    # byte clock period inside the HS bursts of lane 0 (before intf_rdy the clock runs from another source)
    byte_edges = v.edges(s['rxbyteclkhs']) if s['rxbyteclkhs'] else []
    act_on = []
    if s['dl0_rxactivehs']:
        rises, falls = v.edges(s['dl0_rxactivehs'], True), v.edges(s['dl0_rxactivehs'], False)
        act_on = [(r, next((x for x in falls if x > r), end)) for r in rises]
    in_hs = [b - a for a, b in zip(byte_edges, byte_edges[1:]) if any(r <= a and b <= f for r, f in act_on)]
    tbyte = statistics.median(in_hs) if in_hs else None
    if tbyte:
        print(f"rxbyteclkhs period in the HS bursts (median of {len(in_hs)}) {tbyte / 1000:.3f} ns")
    other = [b - a for a, b in zip(byte_edges, byte_edges[1:]) if b < (act_on[0][0] if act_on else end)]
    if other:
        print(f"rxbyteclkhs before the first burst: {len(other) + 1} edges, median period"
              f" {statistics.median(other) / 1000:.3f} ns, last at {byte_edges[len(other)] / 1000:.1f} ns")
    if s['clk_rxp']:
        ce = v.edges(s['clk_rxp'])
        if len(ce) > 2:
            tddr = statistics.median([b - a for a, b in zip(ce, ce[1:])])
            print(f"clk_rxp period (median) {tddr / 1000:.3f} ns -> line rate {2e6 / tddr:.0f} Mb/s")

    # FP-2 start-up: first changes of the control signals
    print("\n== FP-2 start-up: first changes (time in ns)")
    rows = []
    for n in ('phy_reset_w', 'pll_locked_w', 'phy_rdy_out', 'bit_slc_rst_w', 'rx_cl_disable_ibuf_w',
              'rx_dl0_disable_ibuf_w', 'cl_enable', 'dl0_enable', 'cl_stopstate', 'dl0_stopstate',
              'cl_rxclkactivehs'):
        if s[n]:
            rows += [(t, n, val) for t, val in v.changes(s[n])[:4]]
    for t, n, val in sorted(rows):
        print(f"  {ns(t)}  {n:24s} -> {val}")

    # FP-2 and FP-3 per burst of lane 0
    act = s['dl0_rxactivehs']
    bursts = []
    if act:
        rise = v.edges(act, True)
        fall = v.edges(act, False)
        for r in rise:
            f = next((x for x in fall if x > r), end)
            bursts.append((r, f))
    print(f"\n== Bursts of lane 0: {len(bursts)} (dl0_rxactivehs)")
    lp = (s['rx_dl0_lp_dp_w'], s['rx_dl0_lp_dn_w'])
    first_full = None
    for k, (r, f) in enumerate(bursts[:a.bursts]):
        prev_f = bursts[k - 1][1] if k else 0
        print(f"-- burst {k}: rxactivehs {ns(r)} .. {ns(f)}")
        t00 = None
        if all(lp):
            states = sorted({t for t, _ in v.changes(lp[0], prev_f, r)} | {t for t, _ in v.changes(lp[1], prev_f, r)})
            for t in states:
                st = (v.at(lp[0], t), v.at(lp[1], t))
                if st == (0, 0):
                    t00 = t
            for t in states:
                print(f"     {ns(t)}  LP (dp, dn) = ({v.at(lp[0], t)}, {v.at(lp[1], t)})")
        for n in ('rx_dl0_disable_ibuf_w', 'bit_slc_rst_w', 'rx_cl_disable_ibuf_w', 'cl_stopstate',
                  'dl0_rxsynchs', 'dl0_rxvalidhs', 'dl0_errsoths', 'dl0_errsotsynchs', 'dl0_txrequesths'):
            if s[n]:
                ch = v.changes(s[n], prev_f + 1, f + 200_000)
                if ch:
                    rel = '' if t00 is None else ' '.join(f"{(t - t00) / 1000:+.1f}" for t, _ in ch[:6])
                    print(f"     {n:24s} {' '.join(f'{t / 1000:.3f}={val}' for t, val in ch[:6])}"
                          + (f"   (ns after LP-00: {rel})" if rel else ''))
        if t00 is not None and first_full is None and k > 0:
            first_full = (t00, r, f)

    # FP-3 and FP-4 from the pad bits of the first complete burst
    print("\n== FP-3 / FP-4: pad bits, wizard words and PPI of one burst")
    if first_full and s['clk_rxp'] and s['data_rxp'] and s['rx_dl0_hs_dp_w']:
        t00, r, f = first_full
        clk = v.edges(s['clk_rxp'], True, t00, f) + v.edges(s['clk_rxp'], False, t00, f)
        clk.sort()
        bits = [(t, (v.at(s['data_rxp'], t) or 0) & 1) for t in clk]
        seq = [b for _, b in bits]
        i = next((j for j in range(8, len(seq) - 8) if seq[j:j + 8] == SYNC and not any(seq[j - 8:j])), None)
        if i is None:
            print("  sync byte not found on the pad")
        else:
            t_sync_last = bits[i + 7][0]
            pad = seq[i:i + 64]
            print(f"  sync 0xB8 on the pad: bits {i}..{i + 7}, last bit at {ns(t_sync_last)} ns")
            # words: the FIFO is read at a rising edge of its read clock when it is not empty; the word
            # read at edge e0 is taken just before the next edge, and dated e0 (when it appears)
            rclk = s['fifo_rd_clk_t'] or s['rxbyteclkhs']
            ed = v.edges(rclk, True, t00 - 200_000, f + 200_000)
            words = []
            for e0, e1 in zip(ed, ed[1:]):
                if s['fifo_empty_w'] is None or v.at(s['fifo_empty_w'], e0 - 1) == 0:
                    words.append((e0, v.at(s['rx_dl0_hs_dp_w'], e1 - 1)))
            found = []
            for order in ('LSB first', 'MSB first'):
                stream = []
                for _, w in words:
                    b = [((w or 0) >> k) & 1 for k in range(8)]
                    stream += b if order == 'LSB first' else b[::-1]
                p = next((j for j in range(len(stream) - 32) if stream[j:j + 32] == pad[:32]), None)
                if p is not None:
                    w_last = (p + 7) // 8
                    found.append((order, p, words[w_last][0]))
            for order, p, t_w in found:
                lat = t_w - t_sync_last
                cyc = f" = {lat / tbyte:.2f} byte clocks" if tbyte else ''
                print(f"  FP-4: words match the pad with {order}; sync starts at bit {p % 8} of word {p // 8}")
                print(f"  FP-3: last sync bit on the pad -> FIFO read edge of its wizard word: {lat / 1000:.3f} ns{cyc}")
            if not found:
                print("  the pad bits were not found in the wizard words (neither bit order)")
            if s['dl0_rxvalidhs']:
                tv = next((t for t in v.edges(s['dl0_rxvalidhs'], True, r - 1, f)), None)
                if tv is not None:
                    lat = tv - t_sync_last
                    cyc = f" = {lat / tbyte:.2f} byte clocks" if tbyte else ''
                    first_byte = sum(b << k for k, b in enumerate(seq[i + 8:i + 16]))
                    d0 = v.at(s['dl0_rxdatahs'], tv) if s['dl0_rxdatahs'] else None
                    print(f"  FP-3: last sync bit on the pad -> first dl0_rxvalidhs: {lat / 1000:.3f} ns{cyc}")
                    print(f"        first byte after sync on the pad 0x{first_byte:02X}, dl0_rxdatahs at that"
                          f" valid 0x{(d0 or 0):02X}")
    else:
        print("  needs a complete burst after the first one, with clk_rxp, data_rxp and rx_dl0_hs_dp_w")

    # FP-6 byte clock while the clock lane is in LP
    print("\n== FP-6: byte clock while the clock lane is in stop state")
    if byte_edges and s['cl_stopstate']:
        in_stop = sum(1 for t in byte_edges if v.at(s['cl_stopstate'], t) == 1)
        gaps = sorted(((b - a, a) for a, b in zip(byte_edges, byte_edges[1:])), reverse=True)[:3]
        stop_time = sum(t1 - t0 for (t0, v0), (t1, _) in zip(v.changes(s['cl_stopstate']),
                                                             v.changes(s['cl_stopstate'])[1:]) if v0 == 1)
        print(f"  rxbyteclkhs rising edges: {len(byte_edges)}, of which {in_stop} while cl_stopstate = 1")
        print(f"  time with cl_stopstate = 1: {stop_time / 1e6:.2f} us")
        print(f"  longest gaps between byte-clock edges: "
              + ', '.join(f"{g / 1000:.1f} ns at {t / 1000:.1f} ns" for g, t in gaps))
    else:
        print("  needs rxbyteclkhs and cl_stopstate")
    return 0


if __name__ == '__main__':
    sys.exit(main())
