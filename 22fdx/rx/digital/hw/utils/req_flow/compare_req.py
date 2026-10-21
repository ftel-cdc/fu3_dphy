#!/usr/bin/env python3
"""Stability metric between two independent extractions of the same spec (RTL_FLOW_PLAN A6).

Pre-registered on 2026-09-26, before the second extraction was looked at:
  * anchors   = every graded inventory row of the spec (spec_inventory.GRADED_KINDS)
  * per anchor, take the first REQ (lowest req_id) whose source_line is the anchor line, in each
    extraction, and compare category, block, spec_status and needs_human_decision
  * an anchor AGREES when all four fields are equal (a missing REQ on either side disagrees)
  * agreement = agreeing anchors / anchors; pass threshold 0.90
Also reported (not graded): per-field agreement, REQ / finding counts, and the Jaccard overlap of
the source lines of the non-anchor (prose) REQs.

Since 2026-09-26 (spec_review §5.4) category, block, needs_human_decision and the 'open' part of
spec_status of table rows are computed by derive_rules.py when a chunk set is assembled, so they agree
by construction; the anchor metric then measures whether both extractions cover each row and the
non-open spec_status the extraction chooses (assumed / contract / verified / design).
--kinds restricts the anchors to some inventory kinds (e.g. the 11 kinds of the first A6 run).

Usage: compare_req.py <a.json> <b.json> --spec <spec.md> [--threshold 0.90] [--kinds k1,k2,...]
Exit status: 0 = agreement >= threshold, 1 = below.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_inventory  # noqa: E402

FIELDS = ("category", "block", "spec_status", "needs_human_decision")


def first_by_line(doc):
    out = {}
    for r in doc["requirements"]:
        out.setdefault(r["source_line"], r)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--threshold", type=float, default=0.90)
    ap.add_argument("--kinds", help="comma-separated inventory kinds to use as anchors (default: all graded)")
    a = ap.parse_args()
    da, db = json.load(open(a.a, encoding="utf-8")), json.load(open(a.b, encoding="utf-8"))
    inv = spec_inventory.build(a.spec)
    kinds = a.kinds.split(",") if a.kinds else spec_inventory.GRADED_KINDS
    unknown = set(kinds) - set(spec_inventory.GRADED_KINDS)
    if unknown:
        ap.error(f"unknown kinds: {sorted(unknown)}")
    anchors = [it for it in inv["items"] if it["kind"] in kinds]
    fa, fb = first_by_line(da), first_by_line(db)
    agree, field_ok, diffs = 0, {f: 0 for f in FIELDS}, []
    for it in anchors:
        ra, rb = fa.get(it["line"]), fb.get(it["line"])
        if ra is None or rb is None:
            diffs.append((it["key"], "missing in " + ("A" if ra is None else "B"), "", ""))
            continue
        same = True
        for f in FIELDS:
            if ra[f] == rb[f]:
                field_ok[f] += 1
            else:
                same = False
                diffs.append((it["key"], f, ra[f], rb[f]))
        agree += same
    n = len(anchors)
    anchor_lines = {it["line"] for it in anchors}
    pa = {r["source_line"] for r in da["requirements"]} - anchor_lines
    pb = {r["source_line"] for r in db["requirements"]} - anchor_lines
    jac = len(pa & pb) / len(pa | pb) if pa | pb else 1.0
    ratio = agree / n if n else 0.0
    print(f"anchors: {n}   agreeing: {agree}   agreement: {ratio:.1%}   threshold: {a.threshold:.0%}")
    print("per field: " + ", ".join(f"{f} {field_ok[f]}/{n}" for f in FIELDS))
    print(f"REQs: A={len(da['requirements'])}  B={len(db['requirements'])}   "
          f"findings: A={len(da['findings'])}  B={len(db['findings'])}")
    print(f"prose source lines: A={len(pa)}  B={len(pb)}  Jaccard={jac:.2f}")
    if diffs:
        print("\n| Anchor | Field | A | B |\n|---|---|---|---|")
        for k, f, va, vb in diffs:
            print(f"| {k} | {f} | {va} | {vb} |")
    print("\nRESULT:", "PASS" if ratio >= a.threshold else "FAIL")
    sys.exit(0 if ratio >= a.threshold else 1)


if __name__ == "__main__":
    main()
