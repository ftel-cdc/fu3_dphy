#!/usr/bin/env python3
"""Deterministic inventory of a HAS spec.md — the pre-registered answer key of the req flow.

Every table of the spec is recognised by its HEADER SIGNATURE (the tuple of header cells), not by
its section number, so the inventory survives a restructure of the document (e.g. the move to the
FTEL HDS section order). Each row of a gradable table becomes one inventory item; the requirement
extraction must trace every item to at least one REQ (see validate_req.py).

Usage:
  spec_inventory.py <spec.md> [--json out.json] [--selftest]

  --json      write the inventory as JSON (deterministic: no timestamps)
  --selftest  compare the item counts with EXPECTED[<revision of the spec>] and exit 1 on any
              mismatch (the revision is read from the "**DRAFT vX.Y**" line)
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
    ("Path", "Direction", "Signals", "Reference"): "path",
    ("Release", "Line rate per lane", "Deskew", "Target use"): "release",
    # vocabulary tables: not graded for coverage, used to validate enum-like fields
    ("Block", "Name", "Instances", "Clock domain", "Release"): "block",
    ("ULM function", "Data lane (CIL-SFEN)", "Clock lane (CIL-SCNN)"): "ulm",
}
GRADED_KINDS = ("param", "runtime", "clock", "cdc", "reset", "fsm_cl", "fsm_dl",
                "ppi", "afe", "open", "timing", "path", "release")
# Column holding the item name, where it is not the first one (the parameter table starts with '#').
KEY_COLUMN = {"param": 1}

# Deterministic fields of a graded row (spec_review §5.4, option 1: rules RC3 and RC4).
# category follows the table kind; block follows the row (see row_block).
CATEGORY_BY_KIND = {
    "param": "parameter", "runtime": "parameter", "clock": "clocking", "cdc": "clocking",
    "reset": "reset", "fsm_cl": "functional", "fsm_dl": "functional", "ppi": "interface",
    "afe": "interface", "open": "decision", "timing": "timing", "path": "interface",
    "release": "constraint",
}
FIXED_BLOCK = {"fsm_cl": "No.2", "fsm_dl": "No.3", "afe": "No.1", "path": "top", "release": "all"}
PPI_SOURCE_COLUMN = 4
BLOCK_RE = re.compile(r"\bNo\.\s?([1-8])\b")
OPEN_ID_RE = re.compile(r"\b(K[0-9]+|S[0-9]+|T[0-9]+|ADR-[0-9]{3})\b")
TBD_RE = re.compile(r"\bTo be determined\b|\bTBD\b")
HEADING_RE = re.compile(r"^(#{1,6})\s")
CAPTION_RE = re.compile(r"^\*\*[^|]*\*\*\s*$")

# Pre-registered answer key per spec revision. Never edit a count to make a run pass: a count
# changes only when the spec changes, and the new count is written here BEFORE the spec is edited.
#  2026-09-26  v0.2/v0.3 counted by hand on v0.2 before any extraction prompt was written (the v0.3
#              rename changed names only). C1 is not referenced; C7 is only reached through "C6–C9".
#  2026-09-26  path/release added (spec_review D5): the §1.3 and §1.4 tables carry [CSI] rows but were
#              not graded. Counted by hand on v0.2 and v0.3 (5 and 2 rows). This also enlarges the
#              anchor set of compare_req.py: the A6 result of 2026-09-26 (79.6 %) used 108 anchors.
#  2026-09-26  v0.4 written before the spec edit (spec_review D3/D4): cdc +1 (enable gating of the
#              rxbyteclkhs-domain PPI outputs), open +2 (K8, ADR-004), c_ids +1 (C1 in Appendix A).
#  2026-09-29  v0.5 written before the spec edit (Track Doc, figures): cdc +1 (synchronizer of
#              afe_cl_clk_active, a gap found while drawing Figure 2-4). The §2.1 table mapping the
#              D-PHY Universal Lane Module to the blocks is a vocabulary table ("ulm"), not graded.
#  2026-09-29  v0.6 (Track Doc, block figures 4-1 to 4-13): runtime +1 (eot_skip_bytes), cdc +1 (status
#              crossing into the configuration clock), fsm_cl +1 (CL_WAIT), open +1 (ADR-006 reopened).
#              Counted from the change list. Registered after the spec edits, which came out of the
#              drawing, but before the inventory was run on v0.6.
#  2026-09-29  v0.7 written before the spec edit (HAS document format): no graded count changes. The §1
#              ASCII sketches become Figures 1-1 to 1-3, every table gets a bold caption line (a caption
#              that already carried OPEN keeps it), the signal-naming note moves into §1, and Appendix C
#              lists acronyms in a table that is not graded.
#  2026-09-30  v0.8 written before the spec edit (Track Doc batch 3, timing diagrams): open +1 (ADR-007,
#              start of the sync search, found while drawing Figure 5-9). The ADR-007 option matrix
#              (Table 7-4) is not a graded table; the CL_HS_TERM row of the clock-lane FSM changes its
#              exit condition only, so fsm_cl keeps 11 rows.
#  2026-10-02  v0.9 written before the spec edit (ADR-007 decided: the sync search starts at DL_HS_RX):
#              no graded count changes. Table 7-4 is rewritten (options A to E) and Table 7-5 (events
#              and fallbacks) is added, neither graded; the core_clk -> rxbyteclkhs CDC row lists one
#              more signal, so cdc keeps 8 rows; the ADR-007 open-item row stays (AFE word latency).
_V03 = {
    "param": 10, "runtime": 5, "clock": 3, "cdc": 5, "reset": 3,
    "fsm_cl": 10, "fsm_dl": 16, "ppi": 29, "afe": 8, "open": 10, "timing": 9,
    "path": 5, "release": 2, "q_ids": 9, "c_ids": 15,
}
EXPECTED = {
    "v0.2": _V03,
    "v0.3": _V03,
    "v0.4": dict(_V03, cdc=6, open=12, c_ids=16),
    "v0.5": dict(_V03, cdc=7, open=12, c_ids=16),
    "v0.6": dict(_V03, runtime=6, cdc=8, fsm_cl=11, open=13, c_ids=16),
    "v0.7": dict(_V03, runtime=6, cdc=8, fsm_cl=11, open=13, c_ids=16),
    "v0.8": dict(_V03, runtime=6, cdc=8, fsm_cl=11, open=14, c_ids=16),
    "v0.9": dict(_V03, runtime=6, cdc=8, fsm_cl=11, open=14, c_ids=16),
}
REVISION_RE = re.compile(r"\*\*DRAFT (v[0-9]+\.[0-9]+)\*\*")

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


def row_block(kind, cells, text):
    """RC3: block of a graded row. Fixed per kind for FSM / AFE / path / release tables; the Source
    column for the PPI table (no block source, i.e. an input or a tie-off at the IP boundary -> 'top');
    otherwise the single block the row names, and 'all' when it names none or several."""
    if kind in FIXED_BLOCK:
        return FIXED_BLOCK[kind]
    if kind == "ppi":
        src = clean(cells[PPI_SOURCE_COLUMN]) if len(cells) > PPI_SOURCE_COLUMN else ""
        found = set(BLOCK_RE.findall(src))
        return f"No.{found.pop()}" if len(found) == 1 else "top"
    if re.search(r"\bBlocks\b", text):
        return "all"
    found = set(BLOCK_RE.findall(text))
    return f"No.{found.pop()}" if len(found) == 1 else "all"


def open_scope(lines, open_table_lines, open_ids):
    """RC1 + RC2: every line whose content depends on an open item, mapped to the open ids involved.
    A line is open when it (a) carries the word OPEN, (b) is a row of the Open Items table, (c) lies in
    the scope of a heading that carries OPEN (until the next heading of the same or a higher level),
    (d) is a row of the table introduced by a bold caption that carries OPEN, (e) cites the id of an
    open item, or (f) gives a value as 'To be determined'."""
    out = {}

    def add(n, text):
        out.setdefault(n, set()).update(i for i in OPEN_ID_RE.findall(text) if i in open_ids)

    in_code, headings = False, []
    for n, l in enumerate(lines, 1):
        if l.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            m = HEADING_RE.match(l)
            if m:
                headings.append((n, len(m.group(1)), l))
    for idx, (n, level, text) in enumerate(headings):
        if not OPEN_RE.search(text):
            continue
        end = next((h[0] for h in headings[idx + 1:] if h[1] <= level), len(lines) + 1)
        for k in range(n, end):
            add(k, text)
    for n, l in enumerate(lines, 1):
        if CAPTION_RE.match(l.strip()) and OPEN_RE.search(l):
            k = n + 1
            while k <= len(lines) and not lines[k - 1].strip():
                k += 1
            while k <= len(lines) and lines[k - 1].lstrip().startswith("|"):
                add(k, l)
                k += 1
    for n, l in enumerate(lines, 1):
        if OPEN_RE.search(l) or n in open_table_lines or TBD_RE.search(l) or \
                any(i in open_ids for i in OPEN_ID_RE.findall(l)):
            add(n, l)
    return {n: sorted(v) for n, v in sorted(out.items())}


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
        "ulm_functions": [],
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
                elif kind == "ulm":
                    inv["ulm_functions"].append(clean(cells[0]))
                elif kind:
                    inv["items"].append({
                        "kind": kind,
                        "key": item_key(kind, cells[KEY_COLUMN.get(kind, 0)]),
                        "line": j + 1,
                        "section": section,
                        "text": lines[j].strip(),
                        "block": row_block(kind, cells, lines[j]),
                        "category": CATEGORY_BY_KIND.get(kind),
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
    open_rows = [it for it in inv["items"] if it["kind"] == "open"]
    open_ids = set()
    for it in open_rows:
        open_ids.update(OPEN_ID_RE.findall(clean(split_row(it["text"])[0])))
    inv["open_ids"] = sorted(open_ids)
    # JSON object keys are strings; users convert back with int()
    inv["open_derived"] = {str(n): v for n, v in open_scope(lines, {it["line"] for it in open_rows}, open_ids).items()}
    ids = expand_ids(text)
    inv["q_ids"] = sorted((x for x in ids if x[0] == "Q"), key=lambda s: int(s[1:]))
    inv["c_ids"] = sorted((x for x in ids if x[0] == "C"), key=lambda s: int(s[1:]))
    counts = {k: 0 for k in GRADED_KINDS}
    for it in inv["items"]:
        counts[it["kind"]] += 1
    counts["q_ids"] = len(inv["q_ids"])
    counts["c_ids"] = len(inv["c_ids"])
    inv["counts"] = counts
    m = REVISION_RE.search(text)
    inv["revision"] = m.group(1) if m else None
    dup = sorted({it["key"] for it in inv["items"] if sum(1 for x in inv["items"] if x["key"] == it["key"]) > 1})
    inv["duplicate_keys"] = dup
    return inv


def selftest(inv):
    rev = inv.get("revision")
    if rev not in EXPECTED:
        print(f"SELFTEST FAIL: no pre-registered counts for revision {rev!r} (known: {', '.join(EXPECTED)})")
        return False
    ok = True
    print(f"revision {rev}")
    print(f"{'kind':<8} {'expected':>8} {'actual':>7}  result")
    for k, exp in EXPECTED[rev].items():
        act = inv["counts"].get(k, 0)
        res = "PASS" if act == exp else "FAIL"
        ok &= act == exp
        print(f"{k:<8} {exp:>8} {act:>7}  {res}")
    if inv["duplicate_keys"]:
        ok = False
        print("FAIL duplicate item keys:", ", ".join(inv["duplicate_keys"]))
    print(f"blocks (vocabulary): {', '.join(inv['blocks'])}")
    print(f"ULM functions (vocabulary): {len(inv['ulm_functions'])}")
    print(f"unrecognised tables (not graded): {len(inv['unrecognised_tables'])}")
    print(f"lines tagged OPEN: {len(inv['open_lines'])}, lines tagged ⚠️: {len(inv['assume_lines'])}, "
          f"lines depending on an open item (derived): {len(inv['open_derived'])}")
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
