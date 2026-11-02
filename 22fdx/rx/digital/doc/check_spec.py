#!/usr/bin/env python3
# Vendored from ftel_doc_kit 1.0.1 (skills/ftel-spec/scripts/check_spec.py); edit the kit, then run kit.py vendor.
#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-11-02
# Description     : Rule checks of a spec.md (rules S1-S16 of the skill ftel-spec, ftel_doc_kit).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-11-02   1.0        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Rule checks of a spec.md (skill ftel-spec of ftel_doc_kit).

  S-DASH  no em dash and no en dash anywhere (rule S6)
  S-MARK  never the magnifying glass; with --release no grounding marker at all (rule S5)
  S-VER   the "**DRAFT vX.Y**" line matches the last row of "## Revision and History" (rule S10)
  S-CAP   "![Figure N-M: Title](figures/<stem>.svg)" and "**Table N-M: Title**": N is the chapter
          (or appendix letter), M counts from 1 in each chapter; the figure file exists (rule S9)
  S-TBL   every table from chapter 1 to the Acronyms appendix has a caption right above it (rule S9)
  S-ID    every id of the families in `ids` (doc_kit.yaml; default ADR-nnn) is defined in the spec:
          as the first cell of a table row or at the start of a heading (rule S3)
  S-OPEN  every "OPEN <id>" appears in the Open Items chapter (`open_items`, default "Open Items")
  S-REF   with `standalone: true` (the default): no file path and none of the `forbidden` patterns
          (rules S1, S2)
Usage:
  check_spec.py [--doc DIR] [--release]       DIR holds spec.md and doc_kit.yaml (default: this folder)
  check_spec.py --doc DIR --selftest-negative  inject one fault per rule into a copy; each must be caught
Exit status: 0 when there is no violation, 1 otherwise.
"""
import argparse
import os
import re
import shutil
import sys
import tempfile

DASHES = {"\N{EM DASH}": "em dash", "\N{EN DASH}": "en dash"}
SEARCH = "\N{LEFT-POINTING MAGNIFYING GLASS}"
MARKERS = {"\N{WHITE HEAVY CHECK MARK}": "check mark", "\N{WARNING SIGN}": "warning sign",
           "\N{GLOBE WITH MERIDIANS}": "globe", SEARCH: "magnifying glass"}
CAP_SEP = r"(?::| \N{EM DASH})"
FIG_LINE = re.compile(r"^!\[Figure ([A-Z0-9]+)-(\d+)" + CAP_SEP + r" .+\]\((figures/[^)\s]+)\)\s*$")
TBL_LINE = re.compile(r"^\*\*Table ([A-Z0-9]+)-(\d+)" + CAP_SEP + r" .+\*\*\s*$")
CHAPTER = re.compile(r"^##\s+(?:(\d+)\.|Appendix ([A-Z])\.)\s+(.*?)\s*$")
HEADING = re.compile(r"^#{2,6}\s+(?:\d+(?:\.\d+)*\.?\s+)?(.*)$")
OPEN_REF = re.compile(r"\bOPEN\s+([A-Z][A-Za-z0-9-]*\d[a-z]?)\b")
PATH = re.compile(r"(?<![\w/])(?:[\w.-]+/)+[\w.-]+\.(?:md|py|sv|svh|v|vh|docx|xlsx|pdf|json|ya?ml|tcl|sdc|txt)\b"
                  r"|\b[\w.-]+\.(?:docx|xlsx|pdf)\b")
FIG_LINK = re.compile(r"\]\(figures/[^)\s]+\)")
ID_RANGE = re.compile(r"^([A-Z][A-Za-z]*-?)(\d+)\s*(?:to|-)\s*(?:\1)?(\d+)\b")


def load_config(doc):
    path = os.path.join(doc, "doc_kit.yaml")
    if not os.path.isfile(path):
        return {}
    try:
        import yaml
    except ImportError:
        sys.exit(f"check_spec: reading {path} needs PyYAML")
    return yaml.safe_load(open(path, encoding="utf-8")) or {}


def fenced(lines):
    """Indexes of the lines inside fenced code blocks (``` or ~~~), fences included."""
    inside, out = False, set()
    for i, line in enumerate(lines):
        if re.match(r"^\s*(```|~~~)", line):
            inside = not inside
            out.add(i)
        elif inside:
            out.add(i)
    return out


def table_blocks(lines):
    """(first line index, last line index) of every Markdown table outside code blocks."""
    out, start = [], None
    code = fenced(lines)
    for i, line in enumerate(lines + [""]):
        is_row = line.lstrip().startswith("|") and i not in code
        if is_row and start is None:
            start = i
        elif not is_row and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def first_cells(lines):
    """First cells of the table rows; a range "D1 to D7" or "D1-D7" defines every id in it."""
    cells = set()
    for line in lines:
        s = line.strip()
        if s.startswith("|") and not re.match(r"^\|\s*:?-", s):
            cell = re.sub(r"[*`]", "", s.strip("|").split("|")[0]).strip()
            cells.add(cell)
            m = ID_RANGE.match(cell)
            if m and int(m.group(2)) <= int(m.group(3)) <= int(m.group(2)) + 200:
                width = len(m.group(2)) if m.group(2).startswith("0") else 0
                cells.update(f"{m.group(1)}{n:0{width}d}" for n in range(int(m.group(2)), int(m.group(3)) + 1))
    return cells


def check(doc, spec_name=None, release=False, cfg=None):
    cfg = load_config(doc) if cfg is None else cfg
    spec = os.path.join(doc, spec_name or cfg.get("spec", "spec.md"))
    text = open(spec, encoding="utf-8").read()
    lines = text.splitlines()
    name = os.path.basename(spec)
    out = []

    def add(code, i, msg):
        out.append((code, f"{name}:{i + 1}" if i is not None else name, msg))

    # S-DASH, S-MARK
    for i, line in enumerate(lines):
        for ch, what in DASHES.items():
            if ch in line:
                add("S-DASH", i, f"{what} (use a colon, a comma, parentheses or a new sentence; a hyphen in ranges)")
        if SEARCH in line:
            add("S-MARK", i, "magnifying glass: an open check never goes into the spec")
        if release:
            for ch, what in MARKERS.items():
                if ch != SEARCH and ch in line:
                    add("S-MARK", i, f"{what}: a release carries no grounding marker")

    # S-VER
    draft = next((i for i, l in enumerate(lines) if re.search(r"\*\*DRAFT v\d+\.\d+\*\*", l)), None)
    rev = next((i for i, l in enumerate(lines) if l.startswith("## Revision and History")), None)
    rows = []
    if rev is not None:
        for line in lines[rev + 1:]:
            if line.startswith("|"):
                if not re.match(r"^\|\s*:?-", line):
                    rows.append(line)
            elif rows:
                break
    if draft is None:
        add("S-VER", None, "no '**DRAFT vX.Y**' line")
    elif len(rows) < 2:
        add("S-VER", rev, "no '## Revision and History' table with a row per version")
    else:
        v_line = re.search(r"\*\*DRAFT v(\d+\.\d+)\*\*", lines[draft]).group(1)
        m = re.search(r"v(\d+\.\d+)", rows[-1].strip("|").split("|")[0])
        if not m or m.group(1) != v_line:
            add("S-VER", draft, f"DRAFT v{v_line} but the last revision row is "
                                f"{m.group(0) if m else rows[-1].split('|')[1].strip()}")

    # S-CAP, S-TBL
    body = next((i for i, l in enumerate(lines) if re.match(r"^##\s+1\.\s+\S", l)), None)
    acronyms = next((i for i, l in enumerate(lines) if re.match(r"^##\s+Appendix [A-Z]\.\s+Acronyms\s*$", l)),
                    len(lines))
    if body is None:
        add("S-CAP", None, "no '## 1. <title>' chapter")
        body = len(lines)
    chapter, figs, tbls = None, 0, 0
    for i in range(body, len(lines)):
        line = lines[i].strip()
        m = CHAPTER.match(lines[i])
        if m:
            chapter, figs, tbls = m.group(1) or m.group(2), 0, 0
            continue
        if line.startswith("!["):
            mf = FIG_LINE.match(line)
            if not mf:
                add("S-CAP", i, "figure without a '![Figure N-M: Title](figures/<stem>.svg)' caption")
                continue
            figs += 1
            if (mf.group(1), int(mf.group(2))) != (chapter, figs):
                add("S-CAP", i, f"Figure {mf.group(1)}-{mf.group(2)} should be Figure {chapter}-{figs}")
            if not os.path.isfile(os.path.join(doc, mf.group(3))):
                add("S-CAP", i, f"{mf.group(3)} does not exist")
        elif line.startswith("**Table"):
            mt = TBL_LINE.match(line)
            if not mt:
                add("S-CAP", i, "table caption should read '**Table N-M: Title**'")
                continue
            tbls += 1
            if (mt.group(1), int(mt.group(2))) != (chapter, tbls):
                add("S-CAP", i, f"Table {mt.group(1)}-{mt.group(2)} should be Table {chapter}-{tbls}")
    for start, _ in table_blocks(lines):
        if not body <= start < acronyms:
            continue
        prev = next((lines[j].strip() for j in range(start - 1, -1, -1) if lines[j].strip()), "")
        if not TBL_LINE.match(prev):
            add("S-TBL", start, "table without a '**Table N-M: Title**' caption right above it")

    # S-ID, S-OPEN
    defined = first_cells(lines)
    for line in lines:
        h = HEADING.match(line)
        if h:
            defined.add(h.group(1).strip())
    for pattern in cfg.get("ids") or [r"\bADR-\d{3}\b"]:
        seen = set()
        for i, line in enumerate(lines):
            for m in re.finditer(pattern, line):
                ident = m.group(0)
                if ident in seen:
                    continue
                seen.add(ident)
                if not any(re.match(re.escape(ident) + r"(?![\w-])", d) for d in defined):
                    add("S-ID", i, f"{ident} is used but not defined (first cell of a table row or a heading)")
    title = cfg.get("open_items", "Open Items")
    oi = next((i for i, l in enumerate(lines) if re.match(r"^##\s+(?:\d+\.\s+)?" + re.escape(title) + r"\s*$", l)),
              None)
    refs = [(i, m.group(1)) for i, l in enumerate(lines) for m in OPEN_REF.finditer(l)]
    if refs and oi is None:
        add("S-OPEN", refs[0][0], f"OPEN items are cited but there is no '## <n>. {title}' chapter")
    elif refs:
        end = next((j for j in range(oi + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
        chapter_text = "\n".join(lines[oi:end])
        for ident in dict.fromkeys(r[1] for r in refs):
            where = [i for i, r in refs if r == ident]
            if not re.search(r"(?<![\w-])" + re.escape(ident) + r"(?![\w-])", chapter_text):
                add("S-OPEN", where[0], f"OPEN {ident} is not listed in the {title} chapter "
                                        f"(cited {len(where)} time(s))")

    # S-REF
    if cfg.get("standalone", True):
        extra = [re.compile(p) for p in cfg.get("forbidden") or []]
        for i, line in enumerate(lines):
            bare = FIG_LINK.sub("]", line)
            for m in PATH.finditer(bare):
                add("S-REF", i, f"'{m.group(0)}': a standalone spec names no file")
            for p in extra:
                for m in p.finditer(bare):
                    add("S-REF", i, f"'{m.group(0)}' is forbidden by doc_kit.yaml")
    return out


def report(out):
    for code, where, msg in out:
        print(f"{code:7s} {where}: {msg}")
    print(f"check_spec: {len(out)} violation(s)")
    return 1 if out else 0


def selftest_negative(doc):
    """Inject one fault per rule into a copy of a clean spec; each must be caught by its own rule."""
    cfg = load_config(doc)
    spec_name = cfg.get("spec", "spec.md")
    clean = check(doc, spec_name, cfg=cfg)
    if clean:
        report(clean)
        sys.exit("--selftest-negative needs a spec without violations")
    lines = open(os.path.join(doc, spec_name), encoding="utf-8").read().splitlines()
    body = next(i for i, l in enumerate(lines) if re.match(r"^##\s+1\.\s+\S", l))
    para = next(i for i in range(body + 1, len(lines)) if lines[i].strip() and lines[i][0] not in "#|!*-")
    fig = next((i for i, l in enumerate(lines) if FIG_LINE.match(l.strip())), None)

    def append(text):
        return lambda ls: ls[:para] + [ls[para] + text] + ls[para + 1:]

    def sub(i, old, new):
        return lambda ls: ls[:i] + [ls[i].replace(old, new, 1)] + ls[i + 1:]

    draft = next(i for i, l in enumerate(lines) if "**DRAFT v" in l)
    cases = [
        ("S-DASH", False, append(" A \N{EM DASH} B.")),
        ("S-DASH", False, append(" Ranges 1\N{EN DASH}4.")),
        ("S-MARK", False, append(" To check " + SEARCH + ".")),
        ("S-MARK", True, append(" Assumed \N{WARNING SIGN}.")),
        ("S-VER", False, sub(draft, "**DRAFT v", "**DRAFT v9")),
        ("S-TBL", False, lambda ls: ls[:para + 1] + ["", "| a | b |", "|---|---|", "| 1 | 2 |", ""] + ls[para + 1:]),
        ("S-ID", False, append(" See ADR-999.")),
        ("S-OPEN", False, append(" Default value (OPEN ZZ9).")),
        ("S-REF", False, append(" See doc/notes.md.")),
    ]
    if fig is not None:
        m = FIG_LINE.match(lines[fig].strip())
        cases += [("S-CAP", False, sub(fig, f"Figure {m.group(1)}-{m.group(2)}", f"Figure {m.group(1)}-9")),
                  ("S-CAP", False, sub(fig, m.group(3), m.group(3).replace(".svg", "_missing.svg")))]
    failures = 0
    print(f"PASS  clean     -> no violation")
    with tempfile.TemporaryDirectory() as tmp:
        for code, release, inject in cases:
            for f in os.listdir(doc):
                src = os.path.join(doc, f)
                if f == "figures":
                    os.symlink(src, os.path.join(tmp, f))
                elif os.path.isfile(src) and f in (spec_name, "doc_kit.yaml"):
                    shutil.copy(src, tmp)
            open(os.path.join(tmp, spec_name), "w", encoding="utf-8").write("\n".join(inject(lines)) + "\n")
            found = {c for c, _, _ in check(tmp, spec_name, release=release, cfg=cfg)}
            ok = code in found
            failures += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {code:8s}{' --release' if release else ''} -> {sorted(found) or 'no violation'}")
            for f in os.listdir(tmp):
                p = os.path.join(tmp, f)
                os.unlink(p) if os.path.islink(p) or os.path.isfile(p) else shutil.rmtree(p)
    print(f"selftest-negative: {len(cases) + 1 - failures}/{len(cases) + 1} PASS")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--spec", help="spec file name inside --doc (default: spec of doc_kit.yaml, or spec.md)")
    ap.add_argument("--release", action="store_true", help="release check: no grounding marker at all")
    ap.add_argument("--selftest-negative", action="store_true")
    a = ap.parse_args()
    doc = os.path.abspath(a.doc)
    if a.selftest_negative:
        sys.exit(selftest_negative(doc))
    sys.exit(report(check(doc, a.spec, release=a.release)))


if __name__ == "__main__":
    main()
