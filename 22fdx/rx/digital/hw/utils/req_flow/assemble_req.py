#!/usr/bin/env python3
"""Assemble per-section requirement chunks into structured_spec.json (req_flow phase P1).

The extraction step (an LLM following .claude/commands/dphy_spec_parse.md) writes one JSON chunk
per spec section:  {"section": str, "requirements": [...], "findings": [...]}
Requirement and finding objects carry every schema field EXCEPT the ids. This script does the
deterministic part: orders everything by source line, assigns REQ-NNN / F-NNN, and fills the
metadata (spec sha256 and revision are read from the spec itself, never typed by hand).

Usage:
  assemble_req.py --chunks <dir> --spec <spec.md> --ip <ip_name> --mode review|gate --out <json>
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys


def spec_revision(text):
    m = re.search(r"\*\*DRAFT (v[0-9.]+)\*\*", text)
    if m:
        return f"{m.group(1)} (draft)"
    rows = re.findall(r"^\|\s*(v[0-9.]+[^|]*)\|\s*(\d{4}-\d{2}-\d{2})", text, re.M)
    return rows[-1][0].strip() if rows else "unknown"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--ip", required=True)
    ap.add_argument("--mode", choices=["review", "gate"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    a = ap.parse_args()

    raw = open(a.spec, "rb").read()
    reqs, finds = [], []
    files = sorted(glob.glob(os.path.join(a.chunks, "*.json")))
    if not files:
        sys.exit(f"no chunk files in {a.chunks}")
    for f in files:
        try:
            ch = json.load(open(f, encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{f}: invalid JSON: {e}")
        for key in ("requirements", "findings"):
            if not isinstance(ch.get(key, []), list):
                sys.exit(f"{f}: '{key}' must be a list")
        for n, r in enumerate(ch.get("requirements", [])):
            if "req_id" in r:
                sys.exit(f"{f}: requirement {n} carries req_id — ids are assigned by this script")
            reqs.append((r.get("source_line", 0), os.path.basename(f), n, r))
        for n, x in enumerate(ch.get("findings", [])):
            if "finding_id" in x:
                sys.exit(f"{f}: finding {n} carries finding_id — ids are assigned by this script")
            finds.append((x.get("source_line", 0), os.path.basename(f), n, x))
    reqs.sort(key=lambda t: (t[0], t[1], t[2]))
    finds.sort(key=lambda t: (t[0], t[1], t[2]))
    out_reqs = []
    for i, (_, _, _, r) in enumerate(reqs, 1):
        out_reqs.append({"req_id": f"REQ-{i:03d}", **r})
    out_finds = []
    for i, (_, _, _, x) in enumerate(finds, 1):
        out_finds.append({"finding_id": f"F-{i:03d}", **x})
    doc = {
        "metadata": {
            "ip_name": a.ip,
            "spec_path": os.path.relpath(os.path.abspath(a.spec), a.repo),
            "spec_sha256": hashlib.sha256(raw).hexdigest(),
            "spec_revision": spec_revision(raw.decode("utf-8")),
            "mode": a.mode,
            "generated_by": "dphy_spec_parse (assembled by assemble_req.py)",
            "gate_1": {"status": "draft", "by": None, "at": None},
        },
        "requirements": out_reqs,
        "findings": out_finds,
    }
    if len(out_reqs) > 999 or len(out_finds) > 999:
        sys.exit("more than 999 items: widen the id format first")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"assembled {len(out_reqs)} requirements, {len(out_finds)} findings from {len(files)} chunks -> {a.out}")


if __name__ == "__main__":
    main()
