#!/usr/bin/env python3
"""Validator and package generator of config/ftel_dphy_rx.yaml.

Checks the configuration against the HAS (doc/spec.md): Table 3-1 (synthesis parameters), Table 3-2
(run-time timing fields) and the formulas of §4.3, §4.6 and Appendix B, then writes
logical/ftel_dphy_rx_config_pkg.sv, the only place where these values enter the RTL.

Every error starts with its constraint id:
  CFG-01  release is R1 (R2 needs Block No. 5, not in this RTL)
  CFG-02  NUM_LANES in {1, 2, 4}
  CFG-03  locked values: DESER_RATIO 8, CORE_CLK_MHZ 200, LPDT_EN 0, LP_SYNC_STAGES 2, DESKEW_EN 0
  CFG-04  LP_FILTER_CYC: termination-enable budget of the AFE >= 0 in the worst case (data and clock
          lane), and a TLPX state passes the filter
  CFG-05  EOT_DELAY_BYTES >= TEOT,max + LP-11 detection latency + crossing, at the top rate of the release
  CFG-06  SYNC_SEARCH_BYTES >= 2 (the leader can straddle two words)
  CFG-07  DLY_TAP_WIDTH >= 1
  CFG-08  run-time field: reset value and width present, reset value fits the width
  CFG-09  hs_settle_cyc: the reset value and the Appendix B value of every rate of the release place
          DL_HS_RX inside the THS-SETTLE window; every value fits the width
  CFG-10  clk_settle_cyc: CL_HS_TERM ends inside TCLK-SETTLE
  CFG-11  tinit_cyc covers TINIT,SLAVE >= 100 us
  CFG-12  hs_rx_timeout_cyc longer than the longest burst (K8)
  CFG-13  esc_timeout_cyc >= 1
  CFG-14  eot_skip_bytes: reset value = Table 3-2 formula at rate_ref; every value < EOT_DELAY_BYTES and fits
  CFG-15  assumptions: word latency >= 1, rate_ref inside the release, rate points positive
  CFG-16  unknown or missing keys
  CFG-90  formula self-check: the formulas reproduce the values printed in the HAS (answer key)

Usage:
  validate_config.py <yaml> [--emit <pkg.sv>] [--check-pkg <pkg.sv>]
  validate_config.py --selftest-negative
Exit status: 0 = valid (and package written / up to date), 1 = invalid or stale, 2 = selftest failure.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML is required")

HERE = os.path.dirname(os.path.abspath(__file__))
IP_DIR = os.path.dirname(HERE)
SPEC = os.path.join(IP_DIR, "doc", "spec.md")
STRUCTURED = os.path.join(IP_DIR, "req", "structured_spec.json")
YAML_DEFAULT = os.path.join(HERE, "ftel_dphy_rx.yaml")
PKG_DEFAULT = os.path.join(IP_DIR, "logical", "ftel_dphy_rx_config_pkg.sv")
PKG_NAME = "ftel_dphy_rx_config_pkg"

RELEASES = {"R1": (80, 1500), "R2": (80, 1792)}  # Table 1-3
SYN_KEYS = ["NUM_LANES", "DESER_RATIO", "CORE_CLK_MHZ", "DESKEW_EN", "LPDT_EN", "LP_SYNC_STAGES",
            "LP_FILTER_CYC", "EOT_DELAY_BYTES", "SYNC_SEARCH_BYTES", "DLY_TAP_WIDTH"]
RT_KEYS = ["hs_settle_cyc", "clk_settle_cyc", "tinit_cyc", "hs_rx_timeout_cyc", "esc_timeout_cyc",
           "eot_skip_bytes"]
ASSUMPTION_KEYS = ["afe_word_latency", "rate_ref_mbps", "rate_points_mbps", "longest_burst_bytes",
                   "longest_burst_rate_mbps"]
LOCKED = {"DESER_RATIO": 8, "CORE_CLK_MHZ": 200, "LPDT_EN": 0, "LP_SYNC_STAGES": 2, "DESKEW_EN": 0}

# D-PHY [1] values as the HAS states them (Appendix B, §4.6), in ns and UI
TD_TERM_EN = (35.0, 4)        # <= 35 ns + 4 UI
TCLK_TERM_EN = 38.0           # <= 38 ns
TLPX = 50.0                   # >= 50 ns
THS_SETTLE_MIN = (85.0, 6)    # 85 ns + 6 UI
LEADER_FIRST_ONE = (145.0, 13)  # first 1 of a leader sent at the minimum THS-PREPARE + THS-ZERO
TCLK_SETTLE = (95.0, 300.0)
TEOT_MAX = (105.0, 12)
TINIT_NS = 100_000.0
CUT_WINDOW = (40.0, 60.0, 4)  # THS-SKIP,min .. THS-TRAIL,min (60 ns + 4 UI)
SYNC_CROSSING_MAX = 3         # byte clocks of the 2-flop crossing (2-3, §5.2)

# Answer key: values printed in the HAS for the defaults (S = 2, F = 2, Λ = 2, 200 MHz)
ANSWER_KEY = {
    "hs_settle_cyc": {80: 70, 750: 22, 1500: 19, 1792: 18},    # Appendix B, THS-SETTLE row
    "clk_settle_cyc": 33,                                     # Appendix B, TCLK-SETTLE row
    "eot_skip_bytes": {1500: 16},                             # Table 3-2
    "eot_delay_need": {1500: 30, 1792: 35},                   # Table 3-1 #8, §4.6 design note
    "tclk_post_ui": {"R1": 288, "R2": 320},                   # §4.6 design note, Appendix B TCLK-POST
    "term_budget_ns": {"data": (5.0, 10.0), "clock": (8.0, 13.0), "late_less": 5.0},  # §4.3, + 4 UI on a data lane
}


def ui(rate):
    return 1000.0 / rate


def rnd(x):
    return int(math.floor(x + 0.5))


class Model:
    """Timing formulas of the HAS for one configuration."""

    def __init__(self, cfg):
        s, a = cfg["synthesis"], cfg["assumptions"]
        self.T = 1000.0 / s["CORE_CLK_MHZ"]
        self.S, self.F = s["LP_SYNC_STAGES"], s["LP_FILTER_CYC"]
        self.lam = a["afe_word_latency"]

    def lp_latency(self):
        """§4.3: (S + F) cycles plus a sampling delay of 0-1 cycle; one more when the first flop resolves late."""
        return (self.S + self.F) * self.T, (self.S + self.F + 1) * self.T, (self.S + self.F + 2) * self.T

    def term_enable(self):
        """Termination enable: register of the FSM state entered on LP-00, one cycle after the LP state."""
        lo, hi, late = self.lp_latency()
        return lo + self.T, hi + self.T, late + self.T

    def hs_term_entry(self):
        """Entry into DL_HS_TERM / CL_HS_TERM, one state after the termination enable."""
        lo, hi, late = self.term_enable()
        return lo + self.T, hi + self.T, late + self.T

    def term_budget(self, rate):
        """AFE share of TD-TERM-EN (data lane, at `rate`) and TCLK-TERM-EN (clock lane), worst case."""
        late = self.term_enable()[2]
        return TD_TERM_EN[0] + TD_TERM_EN[1] * ui(rate) - late, TCLK_TERM_EN - late

    def settle_window(self, rate):
        """Appendix B: entry into DL_HS_RX between THS-SETTLE,min + Λ words and the first leader 1 + (Λ-1) words."""
        u = ui(rate)
        return (THS_SETTLE_MIN[0] + THS_SETTLE_MIN[1] * u + self.lam * 8 * u,
                LEADER_FIRST_ONE[0] + LEADER_FIRST_ONE[1] * u + (self.lam - 1) * 8 * u)

    def hs_settle(self, rate):
        """Appendix B: centre of the window minus the latest entry into DL_HS_TERM, in core_clk cycles."""
        u = ui(rate)
        latest = (self.S + self.F + 3) * self.T
        return rnd((115.0 + 9.5 * u + (self.lam - 0.5) * 8 * u - latest) / self.T)

    def hs_rx_entry(self, hs):
        lo, _, late = self.hs_term_entry()
        return lo + hs * self.T, late + hs * self.T

    def clk_settle(self):
        """Appendix B: centre of TCLK-SETTLE minus the centre of the entry into CL_HS_TERM."""
        lo, hi, _ = self.hs_term_entry()
        return rnd(((TCLK_SETTLE[0] + TCLK_SETTLE[1]) / 2 - (lo + hi) / 2) / self.T)

    def clk_settle_end(self, clk):
        lo, _, late = self.hs_term_entry()
        return lo + clk * self.T, late + clk * self.T

    def eot_skip(self, rate):
        """Table 3-2: (LP-11 detection latency + 2.5 byte clocks + centre of the cut window) / byte period."""
        u, b = ui(rate), 8 * ui(rate)
        centre = (CUT_WINDOW[0] + CUT_WINDOW[1] + CUT_WINDOW[2] * u) / 2
        return rnd(((self.S + self.F) * self.T + 2.5 * b + centre) / b)

    def eot_delay_need(self, rate):
        """§4.6: TEOT,max + LP-11 detection latency (worst case) + crossing, in byte clocks."""
        u, b = ui(rate), 8 * ui(rate)
        return math.ceil((TEOT_MAX[0] + TEOT_MAX[1] * u + self.lp_latency()[2]) / b + SYNC_CROSSING_MAX)


def err(errs, cid, msg):
    errs.append({"id": cid, "msg": f"{cid} {msg}"})


def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def validate(cfg):
    """Return (errors, info). errors: [{"id": "CFG-nn", "msg": ...}]."""
    errs, info = [], {}
    if not isinstance(cfg, dict):
        err(errs, "CFG-16", "top level must be a mapping")
        return errs, info
    for k in ("meta", "release", "synthesis", "runtime", "assumptions"):
        if k not in cfg:
            err(errs, "CFG-16", f"missing section '{k}'")
    for k in cfg:
        if k not in ("meta", "release", "synthesis", "runtime", "assumptions"):
            err(errs, "CFG-16", f"unknown section '{k}'")
    if errs:
        return errs, info
    s, r, a = cfg["synthesis"], cfg["runtime"], cfg["assumptions"]
    for sec, keys, name in ((s, SYN_KEYS, "synthesis"), (r, RT_KEYS, "runtime"), (a, ASSUMPTION_KEYS, "assumptions")):
        for k in keys:
            if k not in sec:
                err(errs, "CFG-16", f"{name}.{k} missing")
        for k in sec:
            if k not in keys:
                err(errs, "CFG-16", f"unknown key {name}.{k}")
    for k in ("author", "email", "created"):
        if not cfg["meta"].get(k):
            err(errs, "CFG-16", f"meta.{k} missing")
    if errs:
        return errs, info
    for k in SYN_KEYS:
        if not is_int(s[k]):
            err(errs, "CFG-16", f"synthesis.{k} must be an integer")
    if errs:
        return errs, info

    # ---- release, locked and enumerated values
    rel = cfg["release"]
    if rel != "R1":
        err(errs, "CFG-01", f"release {rel!r}: this RTL implements R1 only (R2 needs Block No. 5, ADR-004)")
    lo_rate, hi_rate = RELEASES.get(rel, RELEASES["R1"])
    if s["NUM_LANES"] not in (1, 2, 4):
        err(errs, "CFG-02", f"NUM_LANES {s['NUM_LANES']} not in 1, 2, 4 (Table 3-1 #1)")
    for k, v in LOCKED.items():
        if s[k] != v:
            err(errs, "CFG-03", f"{k} is locked to {v} (Table 3-1), got {s[k]}")

    # ---- assumptions
    lam = a["afe_word_latency"]
    if not is_int(lam) or lam < 1:
        err(errs, "CFG-15", f"afe_word_latency must be an integer >= 1, got {lam!r}")
    pts = a["rate_points_mbps"]
    if not isinstance(pts, list) or not pts or not all(is_int(x) and x > 0 for x in pts):
        err(errs, "CFG-15", "rate_points_mbps must be a list of positive integers")
    if not is_int(a["rate_ref_mbps"]) or not lo_rate <= a["rate_ref_mbps"] <= hi_rate:
        err(errs, "CFG-15", f"rate_ref_mbps {a['rate_ref_mbps']} outside the {rel} range {lo_rate}-{hi_rate} Mb/s")
    for k in ("longest_burst_bytes", "longest_burst_rate_mbps"):
        if not is_int(a[k]) or a[k] < 1:
            err(errs, "CFG-15", f"{k} must be a positive integer")
    if s["CORE_CLK_MHZ"] <= 0 or s["LP_FILTER_CYC"] < 0 or s["LP_SYNC_STAGES"] < 1:
        err(errs, "CFG-04", "CORE_CLK_MHZ > 0, LP_SYNC_STAGES >= 1 and LP_FILTER_CYC >= 0 are required")
    if any(e["id"] in ("CFG-04", "CFG-15") for e in errs):
        return errs, info

    m = Model(cfg)
    rates = [x for x in pts if lo_rate <= x <= hi_rate]
    info["rates_checked"] = rates

    # ---- CFG-04 LP filter
    bd, bc = m.term_budget(hi_rate)
    info["afe_term_budget_ns"] = {"data_lane_worst": round(bd, 2), "clock_lane_worst": round(bc, 2)}
    if bd < 0 or bc < 0:
        err(errs, "CFG-04", f"LP_FILTER_CYC {s['LP_FILTER_CYC']}: termination enable at {m.term_enable()[2]:.1f} ns "
                            f"in the worst case leaves the AFE {bd:.2f} ns (TD-TERM-EN) / {bc:.2f} ns (TCLK-TERM-EN)")
    if (s["LP_FILTER_CYC"] + 1) * m.T > TLPX:
        err(errs, "CFG-04", f"LP_FILTER_CYC {s['LP_FILTER_CYC']}: a TLPX state ({TLPX} ns) would be filtered out")

    # ---- CFG-05 delay line depth
    need = m.eot_delay_need(hi_rate)
    info["eot_delay_need_bytes"] = need
    if s["EOT_DELAY_BYTES"] < need:
        err(errs, "CFG-05", f"EOT_DELAY_BYTES {s['EOT_DELAY_BYTES']} < {need} bytes needed at {hi_rate} Mb/s (§4.6)")
    info["tclk_post_need_ui"] = (s["EOT_DELAY_BYTES"] + lam + 2) * 8

    # ---- CFG-06/07
    if s["SYNC_SEARCH_BYTES"] < 2:
        err(errs, "CFG-06", f"SYNC_SEARCH_BYTES {s['SYNC_SEARCH_BYTES']} < 2")
    if s["DLY_TAP_WIDTH"] < 1:
        err(errs, "CFG-07", f"DLY_TAP_WIDTH {s['DLY_TAP_WIDTH']} < 1")

    # ---- CFG-08 run-time fields
    ok_fields = True
    for k in RT_KEYS:
        f = r[k]
        if not isinstance(f, dict) or set(f) != {"reset", "width"} or not is_int(f["reset"]) or not is_int(f["width"]):
            err(errs, "CFG-08", f"runtime.{k} must be {{reset: <int>, width: <int>}}")
            ok_fields = False
            continue
        if f["width"] < 1 or f["reset"] < 0 or f["reset"] >= 1 << f["width"]:
            err(errs, "CFG-08", f"runtime.{k}: reset {f['reset']} does not fit {f['width']} bits")
    if not ok_fields:
        return errs, info

    def fits(k, v):
        return 0 <= v < 1 << r[k]["width"]

    # ---- CFG-09 hs_settle_cyc
    table = {x: m.hs_settle(x) for x in pts}
    info["hs_settle_cyc_per_rate"] = table
    for x in rates:
        lo, hi = m.settle_window(x)
        a0, a1 = m.hs_rx_entry(table[x])
        if not (lo <= a0 and a1 <= hi):
            err(errs, "CFG-09", f"hs_settle_cyc {table[x]} at {x} Mb/s: DL_HS_RX at {a0:.1f}-{a1:.1f} ns, "
                                f"window {lo:.1f}-{hi:.1f} ns")
        if not fits("hs_settle_cyc", table[x]):
            err(errs, "CFG-09", f"hs_settle_cyc {table[x]} at {x} Mb/s does not fit {r['hs_settle_cyc']['width']} bits")
    ref = a["rate_ref_mbps"]
    lo, hi = m.settle_window(ref)
    a0, a1 = m.hs_rx_entry(r["hs_settle_cyc"]["reset"])
    if not (lo <= a0 and a1 <= hi):
        err(errs, "CFG-09", f"reset value {r['hs_settle_cyc']['reset']} at {ref} Mb/s: DL_HS_RX at {a0:.1f}-{a1:.1f} ns, "
                            f"window {lo:.1f}-{hi:.1f} ns")

    # ---- CFG-10 clk_settle_cyc
    c0, c1 = m.clk_settle_end(r["clk_settle_cyc"]["reset"])
    info["clk_settle_end_ns"] = [c0, c1]
    if not (TCLK_SETTLE[0] <= c0 and c1 <= TCLK_SETTLE[1]):
        err(errs, "CFG-10", f"clk_settle_cyc {r['clk_settle_cyc']['reset']}: CL_HS_TERM ends at {c0:.1f}-{c1:.1f} ns, "
                            f"TCLK-SETTLE {TCLK_SETTLE[0]}-{TCLK_SETTLE[1]} ns")

    # ---- CFG-11..13
    if r["tinit_cyc"]["reset"] * m.T < TINIT_NS:
        err(errs, "CFG-11", f"tinit_cyc {r['tinit_cyc']['reset']} x {m.T} ns < TINIT,SLAVE 100 us")
    burst_ns = a["longest_burst_bytes"] * 8 * 1000.0 / a["longest_burst_rate_mbps"]
    info["longest_burst_us"] = round(burst_ns / 1000, 1)
    if r["hs_rx_timeout_cyc"]["reset"] * m.T <= burst_ns:
        err(errs, "CFG-12", f"hs_rx_timeout_cyc {r['hs_rx_timeout_cyc']['reset']} x {m.T} ns <= longest burst "
                            f"{burst_ns / 1000:.1f} us (K8)")
    if r["esc_timeout_cyc"]["reset"] < 1:
        err(errs, "CFG-13", "esc_timeout_cyc must be >= 1")

    # ---- CFG-14 eot_skip_bytes
    skip = {x: m.eot_skip(x) for x in pts}
    info["eot_skip_bytes_per_rate"] = skip
    if r["eot_skip_bytes"]["reset"] != m.eot_skip(ref):
        err(errs, "CFG-14", f"eot_skip_bytes reset {r['eot_skip_bytes']['reset']} != {m.eot_skip(ref)}, "
                            f"the Table 3-2 value at {ref} Mb/s")
    for x in rates + [ref]:
        v = skip.get(x, m.eot_skip(x))
        if not 1 <= v < s["EOT_DELAY_BYTES"] or not fits("eot_skip_bytes", v):
            err(errs, "CFG-14", f"eot_skip_bytes {v} at {x} Mb/s must be 1..EOT_DELAY_BYTES-1 and fit the width")
    if not 1 <= r["eot_skip_bytes"]["reset"] < s["EOT_DELAY_BYTES"]:
        err(errs, "CFG-14", f"eot_skip_bytes reset {r['eot_skip_bytes']['reset']} must be 1..EOT_DELAY_BYTES-1")

    # ---- CFG-90 formula self-check against the values printed in the HAS
    if (s["LP_SYNC_STAGES"], s["LP_FILTER_CYC"], lam, s["CORE_CLK_MHZ"]) == (2, 2, 2, 200):
        for x, v in ANSWER_KEY["hs_settle_cyc"].items():
            if m.hs_settle(x) != v:
                err(errs, "CFG-90", f"hs_settle formula gives {m.hs_settle(x)} at {x} Mb/s, Appendix B prints {v}")
        if m.clk_settle() != ANSWER_KEY["clk_settle_cyc"]:
            err(errs, "CFG-90", f"clk_settle formula gives {m.clk_settle()}, Appendix B prints 33")
        for x, v in ANSWER_KEY["eot_skip_bytes"].items():
            if m.eot_skip(x) != v:
                err(errs, "CFG-90", f"eot_skip formula gives {m.eot_skip(x)} at {x} Mb/s, Table 3-2 prints {v}")
        for x, v in ANSWER_KEY["eot_delay_need"].items():
            if m.eot_delay_need(x) != v:
                err(errs, "CFG-90", f"delay-line formula gives {m.eot_delay_need(x)} at {x} Mb/s, the HAS prints {v}")
        for rr, depth in (("R1", 32), ("R2", 36)):
            if (depth + lam + 2) * 8 != ANSWER_KEY["tclk_post_ui"][rr]:
                err(errs, "CFG-90", f"TCLK-POST need for {rr} differs from the HAS")
        lo, hi, late = m.term_enable()
        key = ANSWER_KEY["term_budget_ns"]
        got = {"data": (TD_TERM_EN[0] - hi, TD_TERM_EN[0] - lo), "clock": (TCLK_TERM_EN - hi, TCLK_TERM_EN - lo),
               "late_less": late - hi}
        if any(abs(a - b) > 1e-9 for k in ("data", "clock") for a, b in zip(got[k], key[k])) \
                or abs(got["late_less"] - key["late_less"]) > 1e-9:
            err(errs, "CFG-90", f"termination budget {got} differs from §4.3 {key}")
    return errs, info


# ---------------------------------------------------------------------- package generation
def spec_revision(spec_text):
    rows = re.findall(r"^\| v(\d+\.\d+) \((\w+)\)", spec_text, re.M)
    return f"{rows[-1][1]} v{rows[-1][0]}" if rows else "unknown"


def row_lines(spec_text):
    """Line of each Table 3-1 parameter row and Table 3-2 field row."""
    lines, out, table = spec_text.splitlines(), {}, None
    for n, l in enumerate(lines, 1):
        if l.startswith("**Table 3-1"):
            table = "3-1"
        elif l.startswith("**Table 3-2"):
            table = "3-2"
        elif l.startswith("**Table") or l.startswith("#"):
            table = None
        if table == "3-1":
            m = re.match(r"^\| \d+ \| `PARA_(\w+)` \|", l)
            if m:
                out[m.group(1)] = n
        elif table == "3-2":
            m = re.match(r"^\| `(\w+)` \|", l)
            if m:
                out[m.group(1)] = n
    return out


def req_map(spec_text, structured):
    rows = row_lines(spec_text)
    by_line = {}
    for q in structured["requirements"]:
        by_line.setdefault(q["source_line"], []).append(q)
    return {k: by_line.get(n, []) for k, n in rows.items()}


def sv_value(width, v):
    return f"{width}'d{v}"


def emit(cfg, yaml_bytes, spec_text, structured):
    s, r, meta = cfg["synthesis"], cfg["runtime"], cfg["meta"]
    reqs = req_map(spec_text, structured)
    tagged, opens = [], set()
    body = []

    def tags(key, default):
        out = []
        qs = reqs.get(key, [])
        if qs:
            ids = ", ".join(q["req_id"] for q in qs)
            out.append(f"  // {ids}")
            tagged.extend(q["req_id"] for q in qs)
            dec = [q for q in qs if q.get("needs_human_decision")]
            if dec:
                oids = sorted({o for q in dec for o in q.get("open_item_ref", [])})
                opens.update(oids)
                out.append(f"  // OPEN {', '.join(oids)} {', '.join(q['req_id'] for q in dec)}: {default}")
        return out

    body.append("  // ---- Table 3-1: synthesis parameters, defaults of PARA_* ----")
    for k in SYN_KEYS:
        body += tags(k, s[k])
        body.append(f"  localparam int C_{k} = {s[k]};")
    body.append("")
    body.append("  // ---- Table 3-2: run-time timing fields, width and reset value ----")
    for k in RT_KEYS:
        f = r[k]
        up = k.upper()
        body += tags(k, f["reset"])
        body.append(f"  localparam int C_{up}_W = {f['width']};")
        body.append(f"  localparam logic [C_{up}_W-1:0] C_{up}_RST = {sv_value(f['width'], f['reset'])};")
    sha = hashlib.sha256(yaml_bytes).hexdigest()
    req_ids = sorted(set(tagged), key=lambda x: int(x.split("-")[1]))
    req_lines = wrap_list(req_ids)
    head = [
        "//------------------------------------------------------------------------------",
        "// Copyright (c) 2026 FPT Telecom. All rights reserved.",
        "//",
        "// This RTL source code and the associated design are the proprietary",
        "// and confidential information of FPT Telecom.",
        "// Any unauthorized use, reproduction, or disclosure is strictly prohibited.",
        "//------------------------------------------------------------------------------",
        f"// Author          : {meta['author']}",
        f"// Email           : {meta['email']}",
        f"// Created Date    : {meta['created']}",
        f"// Module          : {PKG_NAME}",
        "// Description     : Defaults of the synthesis parameters (HAS Table 3-1), and width and",
        f"//                   reset value of each run-time timing field (Table 3-2), release {cfg['release']}.",
        "//                   Generated by validate_config.py -- DO NOT EDIT.",
        f"//                   Source: config/ftel_dphy_rx.yaml, sha256 {sha[:16]}",
        "// Parent          : ftel_dphy_rx_pkg",
        f"// HAS             : {spec_revision(spec_text)}, §3, Appendix B",
        "// Clock domains   : none",
        f"// REQ-IDs         : {req_lines[0]}",
    ] + [f"//                   {x}" for x in req_lines[1:]] + [
        f"// OPEN            : {', '.join(sorted(opens)) if opens else 'none'}",
        "//",
        "// Evolution History:",
        "// -----------------------------------------------------------------------------",
        "// Date         Version    Author        Description",
        f"// {meta['created']}   0.1        {meta['author']:<13} Draft against HAS {spec_revision(spec_text).split()[-1]}; "
        "open items at their defaults.",
        "//",
        "// This section is not intended for routine updates or minor design changes.",
        "// A new version is strictly reserved for major architectural shifts",
        "// that require software modifications across different chip generations.",
        "//------------------------------------------------------------------------------",
        "`timescale 1ns/1ps",
        "`default_nettype none",
        f"package {PKG_NAME};",
        "",
    ]
    return "\n".join(head + body + ["", "endpackage", "`default_nettype wire", ""])


def wrap_list(ids, width=60):
    lines, cur = [], ""
    for i in ids:
        nxt = (cur + ", " + i) if cur else i
        if len(nxt) > width and cur:
            lines.append(cur + ",")
            cur = i
        else:
            cur = nxt
    lines.append(cur)
    return lines


def expected_pkg(yaml_path, spec=SPEC, structured=STRUCTURED):
    yb = open(yaml_path, "rb").read()
    cfg = yaml.safe_load(yb)
    errs, info = validate(cfg)
    if errs:
        return None, errs, info
    st = json.load(open(structured, encoding="utf-8"))
    return emit(cfg, yb, open(spec, encoding="utf-8").read(), st), errs, info


def summarize(cfg, info):
    s, r = cfg["synthesis"], cfg["runtime"]
    print("=" * 88)
    print(f" release {cfg['release']}   " + "  ".join(f"{k}={s[k]}" for k in SYN_KEYS))
    print(" runtime: " + "  ".join(f"{k}={r[k]['reset']}/{r[k]['width']}b" for k in RT_KEYS))
    print(f" AFE termination budget (worst case): {info['afe_term_budget_ns']} ns (+4 UI on a data lane)")
    print(f" EoT delay line: need {info['eot_delay_need_bytes']} bytes at the top rate; "
          f"TCLK-POST need {info['tclk_post_need_ui']} UI (S12)")
    print(f" hs_settle_cyc per rate (Appendix B): {info['hs_settle_cyc_per_rate']}")
    print(f" eot_skip_bytes per rate (Table 3-2): {info['eot_skip_bytes_per_rate']}")
    print(f" CL_HS_TERM ends at {info['clk_settle_end_ns'][0]:.1f}-{info['clk_settle_end_ns'][1]:.1f} ns; "
          f"longest burst {info['longest_burst_us']} us")
    print("=" * 88)


# ---------------------------------------------------------------------- negative selftest
NEGATIVE = [  # pre-registered: (name, mutation, expected constraint id)
    ("release R2", lambda c: c.update(release="R2"), "CFG-01"),
    ("NUM_LANES 3", lambda c: c["synthesis"].update(NUM_LANES=3), "CFG-02"),
    ("DESER_RATIO 16", lambda c: c["synthesis"].update(DESER_RATIO=16), "CFG-03"),
    ("CORE_CLK_MHZ 250", lambda c: c["synthesis"].update(CORE_CLK_MHZ=250), "CFG-03"),
    ("LPDT_EN 1", lambda c: c["synthesis"].update(LPDT_EN=1), "CFG-03"),
    ("LP_SYNC_STAGES 3", lambda c: c["synthesis"].update(LP_SYNC_STAGES=3), "CFG-03"),
    ("DESKEW_EN 1", lambda c: c["synthesis"].update(DESKEW_EN=1), "CFG-03"),
    ("LP_FILTER_CYC 3 breaks the termination budget", lambda c: c["synthesis"].update(LP_FILTER_CYC=3), "CFG-04"),
    ("EOT_DELAY_BYTES 29", lambda c: c["synthesis"].update(EOT_DELAY_BYTES=29), "CFG-05"),
    ("SYNC_SEARCH_BYTES 1", lambda c: c["synthesis"].update(SYNC_SEARCH_BYTES=1), "CFG-06"),
    ("DLY_TAP_WIDTH 0", lambda c: c["synthesis"].update(DLY_TAP_WIDTH=0), "CFG-07"),
    ("tinit_cyc width 14", lambda c: c["runtime"]["tinit_cyc"].update(width=14), "CFG-08"),
    ("hs_settle_cyc without width", lambda c: c["runtime"].update(hs_settle_cyc={"reset": 19}), "CFG-08"),
    ("hs_settle_cyc reset 40", lambda c: c["runtime"]["hs_settle_cyc"].update(reset=40), "CFG-09"),
    ("hs_settle_cyc width 6 (70 at 80 Mb/s)", lambda c: c["runtime"]["hs_settle_cyc"].update(width=6), "CFG-09"),
    ("clk_settle_cyc reset 10", lambda c: c["runtime"]["clk_settle_cyc"].update(reset=10), "CFG-10"),
    ("tinit_cyc 19999", lambda c: c["runtime"]["tinit_cyc"].update(reset=19999), "CFG-11"),
    ("hs_rx_timeout_cyc 100000", lambda c: c["runtime"]["hs_rx_timeout_cyc"].update(reset=100000), "CFG-12"),
    ("esc_timeout_cyc 0", lambda c: c["runtime"]["esc_timeout_cyc"].update(reset=0), "CFG-13"),
    ("eot_skip_bytes reset 12", lambda c: c["runtime"]["eot_skip_bytes"].update(reset=12), "CFG-14"),
    ("eot_skip_bytes reset 32 >= depth", lambda c: c["runtime"]["eot_skip_bytes"].update(reset=32), "CFG-14"),
    ("afe_word_latency 0", lambda c: c["assumptions"].update(afe_word_latency=0), "CFG-15"),
    ("rate_ref_mbps 1792 outside R1", lambda c: c["assumptions"].update(rate_ref_mbps=1792), "CFG-15"),
    ("typo synthesis.NUM_LANE", lambda c: c["synthesis"].update(NUM_LANE=4), "CFG-16"),
    ("unknown section", lambda c: c.update(extra={}), "CFG-16"),
]


def selftest_negative(yaml_path):
    base = yaml.safe_load(open(yaml_path, "rb").read())
    results = []
    e, _ = validate(copy.deepcopy(base))
    results.append(("baseline config is valid", not e, [x["msg"] for x in e][:3]))
    for name, mut, cid in NEGATIVE:
        c = copy.deepcopy(base)
        mut(c)
        e, _ = validate(c)
        results.append((f"{name} -> {cid}", any(x["id"] == cid for x in e), sorted({x["id"] for x in e})))
    ids = set(re.findall(r"^\s+(CFG-\d\d)\s", __doc__, re.M)) - {"CFG-90"}
    covered = {cid for _, _, cid in NEGATIVE}
    results.append(("every constraint has a negative test", ids <= covered, f"untested {sorted(ids - covered)}"))
    # pkg staleness: a hand edit of the generated package must be seen
    exp, e, _ = expected_pkg(yaml_path)
    edited = exp.replace("C_NUM_LANES = 4", "C_NUM_LANES = 2") if exp else ""
    results.append(("hand-edited package differs from the generated one", bool(exp) and edited != exp, ""))
    print("NEGATIVE SELFTEST (validate_config)")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}   ({detail})")
    allok = all(ok for _, ok, _ in results)
    print("RESULT:", f"{sum(ok for _, ok, _ in results)}/{len(results)}", "PASS" if allok else "FAIL")
    return 0 if allok else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("yaml", nargs="?", default=YAML_DEFAULT)
    ap.add_argument("--emit", help="write the configuration package")
    ap.add_argument("--check-pkg", help="compare an existing package with the one this YAML generates")
    ap.add_argument("--selftest-negative", action="store_true")
    a = ap.parse_args()
    if a.selftest_negative:
        sys.exit(selftest_negative(a.yaml))
    cfg = yaml.safe_load(open(a.yaml, "rb").read())
    errs, info = validate(cfg)
    if errs:
        print(f"INVALID config ({len(errs)} error(s)):")
        for e in errs:
            print(f"  - {e['msg']}")
        sys.exit(1)
    summarize(cfg, info)
    print("VALID config")
    exp, _, _ = expected_pkg(a.yaml)
    if a.emit:
        # write only when the content changes, so the file time stays the time of its content
        if os.path.exists(a.emit) and open(a.emit, encoding="utf-8").read() == exp:
            print(f"{a.emit} unchanged")
        else:
            with open(a.emit, "w", encoding="utf-8") as fh:
                fh.write(exp)
            print(f"wrote {a.emit}")
    if a.check_pkg:
        cur = open(a.check_pkg, encoding="utf-8").read() if os.path.exists(a.check_pkg) else None
        if cur != exp:
            print(f"STALE: {a.check_pkg} differs from the package generated by this YAML")
            sys.exit(1)
        print(f"{a.check_pkg} is up to date")
    sys.exit(0)


if __name__ == "__main__":
    main()
