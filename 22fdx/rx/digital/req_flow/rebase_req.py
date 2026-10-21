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
# Created Date    : 2026-09-26
# Description     : Carry P1 chunks over to a new spec revision without re-extracting the unchanged
#                   parts.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-09-26   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Carry P1 chunks over to a new spec revision without re-extracting the unchanged parts.

A full extraction regenerates every REQ (about 20 minutes of LLM output for this spec). When the
spec changes locally, most quotes are still verbatim and have only moved. This script:

  1. aligns the old and the new spec line by line (difflib) to find changed and inserted lines;
  2. for every requirement and finding of the chunks, locates its quote in the new spec:
       rebased  the quote and its whole text unit (table row, bullet item or paragraph) are
                unchanged -> source_line is moved to the new line, the item is kept as it is
       stale    the quote is gone, or its text unit contains a changed line -> the item is removed
                from the chunk and listed for regeneration (a finding may simply be resolved)
  3. lists the changed / inserted lines of the new spec that no rebased item covers, grouped
     by section, so the extraction step reads only those parts.

Nothing is guessed: an item is rebased only when its quote is found verbatim at the line that
difflib maps its old line to. Derived fields are recomputed later by assemble_req.py.

Ids: a rebased item keeps its id at assembly (same quote and text). With --old-json, every stale
item of the worklist carries the id it had ("prev_id"); the regenerated item copies it as
"prev_req_id" / "prev_finding_id" when it states the same requirement, so the id survives the
rewording (assemble_req.py). An item that is dropped or replaced by a different one retires its id.

Usage:
  rebase_req.py --chunks <old chunk dir> --old-spec <old spec.md> --new-spec <new spec.md>
                --out <new chunk dir> --worklist <worklist.json> [--old-json <structured_spec.json>]
Exit status: 0 always when the files are written; the summary says what must be regenerated.
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def quote_span(lines, ln, q):
    """Lines (1-based) that the quote occupies starting at ln, or None when it is not there."""
    for k in (1, 2, 3):
        if ln - 1 + k <= len(lines) and q in norm(" ".join(lines[ln - 1: ln - 1 + k])):
            return list(range(ln, ln + k))
    return None


def code_lines(lines):
    out, inside = set(), False
    for n, l in enumerate(lines, 1):
        if l.strip().startswith("```"):
            inside = not inside
            out.add(n)
        elif inside:
            out.add(n)
    return out


def unit(lines, ln):
    """Text unit around line ln: a table row alone, else the bullet item or paragraph."""
    if lines[ln - 1].lstrip().startswith("|"):
        return [ln]

    def starts_unit(n):
        s = lines[n - 1]
        return (not s.strip()) or s.lstrip().startswith(("- ", "#", "|")) or s.startswith("**")

    a = ln
    while a > 1 and not starts_unit(a) and lines[a - 2].strip() and not lines[a - 2].lstrip().startswith("|"):
        a -= 1
    b = ln
    while b < len(lines) and lines[b].strip() and not starts_unit(b + 1):
        b += 1
    return list(range(a, b + 1))


def section_of(lines, n):
    for k in range(n, 0, -1):
        if lines[k - 1].startswith("#"):
            return lines[k - 1].lstrip("#").strip()
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--old-spec", required=True)
    ap.add_argument("--new-spec", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--worklist", required=True)
    ap.add_argument("--old-json", help="structured_spec.json of the old revision: stale items get their old id")
    a = ap.parse_args()
    old = open(a.old_spec, encoding="utf-8").read().splitlines()
    new = open(a.new_spec, encoding="utf-8").read().splitlines()
    if os.path.abspath(a.out) == os.path.abspath(a.chunks):
        sys.exit("--out must differ from --chunks (the old chunks are the record of the old revision)")
    old_ids = {}
    if a.old_json:
        od = json.load(open(a.old_json, encoding="utf-8"))
        for key, idk in (("requirements", "req_id"), ("findings", "finding_id")):
            for x in od.get(key, []):
                old_ids[(key, norm(x["source_quote"]), norm(x["text"]))] = x[idk]

    mapping, changed = {}, set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                mapping[i1 + k + 1] = j1 + k + 1
        else:
            changed.update(range(j1 + 1, j2 + 1))
    in_code = code_lines(new)

    os.makedirs(a.out, exist_ok=True)
    stale, covered, kept = [], set(), {"requirements": 0, "findings": 0}
    for f in sorted(glob.glob(os.path.join(a.chunks, "*.json"))):
        ch = json.load(open(f, encoding="utf-8"))
        out = {"section": ch.get("section", ""), "requirements": [], "findings": []}
        for key in ("requirements", "findings"):
            for idx, item in enumerate(ch.get(key, [])):
                q = norm(item["source_quote"])
                target = mapping.get(item["source_line"])
                span = quote_span(new, target, q) if target else None
                touched = span is not None and any(n in changed for n in unit(new, target))
                if span and not touched:
                    moved = dict(item, source_line=target)
                    out[key].append(moved)
                    covered.update(unit(new, target))
                    kept[key] += 1
                    continue
                hits = [n for n in range(1, len(new) + 1) if quote_span(new, n, q)]
                stale.append({
                    "chunk": os.path.basename(f), "kind": key[:-1], "index": idx,
                    "prev_id": old_ids.get((key, q, norm(item.get("text", "")))),
                    "old_source_line": item["source_line"], "mapped_line": target,
                    "reason": ("quote found but its text unit changed" if span else
                               "quote not at the mapped line" if hits else "quote no longer in the spec"),
                    "quote_found_at": hits[:5], "item": item,
                })
        with open(os.path.join(a.out, os.path.basename(f)), "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
            fh.write("\n")

    todo = sorted(n for n in changed if n not in covered and n not in in_code and new[n - 1].strip()
                  and not re.match(r"^\s*\|?\s*:?-{3,}", new[n - 1]))
    ranges = []
    for n in todo:
        if ranges and n - ranges[-1][1] <= 2 and section_of(new, n) == ranges[-1][2]:
            ranges[-1][1] = n
        else:
            ranges.append([n, n, section_of(new, n)])
    extract = [{"section": s, "lines": [x, y], "text": new[x - 1: y]} for x, y, s in ranges]
    wl = {"old_spec": a.old_spec, "new_spec": a.new_spec, "kept": kept,
          "stale": stale, "extract": extract}
    with open(a.worklist, "w", encoding="utf-8") as fh:
        json.dump(wl, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"rebased: {kept['requirements']} requirements, {kept['findings']} findings kept with new line numbers")
    print(f"stale:   {sum(s['kind'] == 'requirement' for s in stale)} requirements, "
          f"{sum(s['kind'] == 'finding' for s in stale)} findings -> regenerate or drop (see worklist)")
    print(f"extract: {len(extract)} changed/new text ranges not covered by a rebased item")
    for e in extract:
        print(f"  lines {e['lines'][0]}-{e['lines'][1]}  [{e['section'][:50]}]  {norm(e['text'][0])[:70]}")


if __name__ == "__main__":
    main()
