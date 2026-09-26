#!/usr/bin/env python3
"""Deterministic inventory of a HAS spec.md — the pre-registered answer key of the req flow.

Every table of the spec is recognised by its HEADER SIGNATURE (the tuple of header cells), not by
its section number, so the inventory survives a restructure of the document (e.g. the move to the
FTEL HDS section order). Each row of a gradable table becomes one inventory item; the requirement
extraction must trace every item to at least one REQ (see validate_req.py).

Usage:
  spec_inventory.py <spec.md> [--json out.json] [--selftest]

  --json      write the inventory as JSON (deterministic: no timestamps)
  --selftest  compare the item counts with EXPECTED (pre-registered on spec v0.2, 2026-09-26)
              and exit 1 on any mismatch
"""
import argparse
import hashlib
import json
import re
import sys

# Header signature -> inventory kind. Cells are compared after stripping markdown emphasis/code.
TABLE_KINDS = {
    ("#", "Parameter", "Value / formula", "Type", "Description"): "param",
    ("Field", "Default", "Basis"): "runtime",
    ("Clock", "Source", "Frequency", "Used by", "Notes"): "clock",
    ("From → To", "Signals", "Method"): "cdc",
    ("Control", "Type", "Scope", "Behaviour"): "reset",
    ("State", "Line state", "Exit condition → next state", "Outputs"): "fsm_cl",
    ("State", "Line state", "Exit condition → next state", "Outputs / actions"): "fsm_dl",
    ("Signal", "Dir", "Width", "Domain", "Source", "Inactive value", "R1"): "ppi",
    ("Signal", "Dir", "Width", "Domain", "Description"): "afe",
    ("ID", "Item", "Default in this draft", "Owner / with"): "open",
    ("Parameter", "Specification", "Implementation"): "timing",
    # vocabulary tables: not graded for coverage, used to validate enum-like fields
    ("Block", "Name", "Instances", "Clock domain", "Release"): "block",
}
GRADED_KINDS = ("param", "runtime", "clock", "cdc", "reset", "fsm_cl", "fsm_dl",
                "ppi", "afe", "open", "timing")
# Column holding the item name, where it is not the first one (the parameter table starts with '#').
KEY_COLUMN = {"param": 1}

# Pre-registered answer key (counted on spec.md v0.2 before any extraction prompt was written;
# the v0.3 rename changed names only). C1 is not referenced by the spec; C7 is only reached
# through the range "C6–C9" of Appendix A.
EXPECTED = {
    "param": 10, "runtime": 5, "clock": 3, "cdc": 5, "reset": 3,
    "fsm_cl": 10, "fsm_dl": 16, "ppi": 29, "afe": 8, "open": 10, "timing": 9,
    "q_ids": 9, "c_ids": 15,
}

OPEN_RE = re.compile(r"\bOPEN\b")
ASSUME_MARK = "⚠️"
RANGE_RE = re.compile(r"\b([QCKSV])(\d+)\s*[–-]\s*\1?(\d+)\b")
ID_RE = re.compile(r"\b([QC])(\d+)\b")


def split_row(line):
    """Split a markdown table row on unescaped pipes; returns stripped cells."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells, cur, i = [], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def clean(cell):
    return re.sub(r"[*`]", "", cell).strip()


def is_separator(line):
    return bool(re.match(r"^\s*\|?\s*:?-{3,}", line))


def item_key(kind, first_cell):
    """Stable key of an inventory item from its first cell."""
    key = clean(first_cell)
    if kind == "open":
        key = key.split("/")[0].strip()          # "K3 / ADR-005" -> "K3"
    return f"{kind}:{key}"


def expand_ids(text):
    """All Q and C ids of the text, with ranges like 'C6–C9' / 'C14–C16' expanded."""
    ids = set()
    for m in RANGE_RE.finditer(text):
        pfx, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        if pfx in "QC" and lo <= hi:
            ids.update(f"{pfx}{n}" for n in range(lo, hi + 1))
    for m in ID_RE.finditer(text):
        ids.add(f"{m.group(1)}{int(m.group(2))}")
    return ids


def build(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")
    lines = text.splitlines()
    inv = {
        "spec_path": path,
        "spec_sha256": hashlib.sha256(raw).hexdigest(),
        "items": [],
        "blocks": [],
        "unrecognised_tables": [],
        "open_lines": [],
        "assume_lines": [],
    }
    section = ""
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            in_code = not in_code
            i += 1
            continue
        if not in_code and line.startswith("#"):
            section = line.lstrip("#").strip()
        if not in_code and line.lstrip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            header = tuple(clean(c) for c in split_row(line))
            kind = TABLE_KINDS.get(header)
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = split_row(lines[j])
                if kind == "block":
                    inv["blocks"].append(clean(cells[0]))
                elif kind:
                    inv["items"].append({
                        "kind": kind,
                        "key": item_key(kind, cells[KEY_COLUMN.get(kind, 0)]),
                        "line": j + 1,
                        "section": section,
                        "text": lines[j].strip(),
                    })
                j += 1
            if not kind:
                inv["unrecognised_tables"].append({"line": i + 1, "section": section, "header": list(header)})
            i = j
            continue
        i += 1
    # Tag lines are scanned over the WHOLE file (prose, table rows, diagrams): the consistency
    # rules of validate_req.py apply to whatever line a REQ is sourced from.
    for n, l in enumerate(lines, 1):
        if OPEN_RE.search(l):
            inv["open_lines"].append(n)
        if ASSUME_MARK in l:
            inv["assume_lines"].append(n)
    ids = expand_ids(text)
    inv["q_ids"] = sorted((x for x in ids if x[0] == "Q"), key=lambda s: int(s[1:]))
    inv["c_ids"] = sorted((x for x in ids if x[0] == "C"), key=lambda s: int(s[1:]))
    counts = {k: 0 for k in GRADED_KINDS}
    for it in inv["items"]:
        counts[it["kind"]] += 1
    counts["q_ids"] = len(inv["q_ids"])
    counts["c_ids"] = len(inv["c_ids"])
    inv["counts"] = counts
    dup = sorted({it["key"] for it in inv["items"] if sum(1 for x in inv["items"] if x["key"] == it["key"]) > 1})
    inv["duplicate_keys"] = dup
    return inv


def selftest(inv):
    ok = True
    print(f"{'kind':<8} {'expected':>8} {'actual':>7}  result")
    for k, exp in EXPECTED.items():
        act = inv["counts"].get(k, 0)
        res = "PASS" if act == exp else "FAIL"
        ok &= act == exp
        print(f"{k:<8} {exp:>8} {act:>7}  {res}")
    if inv["duplicate_keys"]:
        ok = False
        print("FAIL duplicate item keys:", ", ".join(inv["duplicate_keys"]))
    print(f"blocks (vocabulary): {', '.join(inv['blocks'])}")
    print(f"unrecognised tables (not graded): {len(inv['unrecognised_tables'])}")
    print(f"lines tagged OPEN: {len(inv['open_lines'])}, lines tagged ⚠️: {len(inv['assume_lines'])}")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    inv = build(a.spec)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(inv, f, ensure_ascii=False, indent=1)
            f.write("\n")
    if a.selftest:
        sys.exit(0 if selftest(inv) else 1)
    if not a.json:
        print(json.dumps(inv["counts"], indent=1))


if __name__ == "__main__":
    main()
