#!/usr/bin/env python3
# Vendored from ftel_doc_kit 1.0.1 (skills/ftel-block-diagram/scripts/check_figures.py); edit the kit, then run kit.py vendor.
#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-09-29
# Description     : Rule checks for the figures of a spec (rules B1-B17 of ftel-block-diagram and
#                   W1-W8 of ftel-waveform in ftel_doc_kit).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-09-29   0.1        Ho Khanh Linh Initial creation (ftel_dphy_rx).
# 2026-11-02   1.0        Ho Khanh Linh Moved into ftel_doc_kit: names to check from doc_kit.yaml,
#                                       captions with a colon, generic negative-test names.
# 2026-11-02   1.0.1      Ho Khanh Linh names optional again in check_drawio, check_wave and check (the
#                                       API that figure generators import).
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Rule checks for the figures of a spec (ftel_doc_kit, skills ftel-block-diagram and ftel-waveform).

Every figures/*.drawio and every WaveJSON timing diagram (*.json5) is checked against its render
and against spec.md:
  F-XML    the .drawio parses as XML (compressed diagrams are inflated first)
  F-ASCII  only ASCII characters; U+00A0, which the drawio editor writes, is accepted
  F-FONT   every cell that shows text sets fontSize >= 18, and inline HTML font sizes are >= 18
  F-SHAPE  shapes come from FTEL_DRAWIO_LIB_V1 (SHAPES, NAMED_STYLES), plain rectangles or edges
  F-NAME   every name of a label that matches figure_names of doc_kit.yaml occurs in spec.md
           (default: PARA_* and every snake_case name)
  F-STALE  <base>.svg exists and records the sha256 of the current source (render_drawio.py and
           render_wave.py stamps)
  F-COLS   in a .json5, every wave and node string has the same number of columns
  F-REF    every figures/ image embedded in spec.md exists, has a "Figure N-M: ..." caption
           (the older "Figure N-M <em dash> ..." is accepted), and every .drawio and .json5 is
           embedded as <base>.svg
The .json5 checks are F-ASCII, F-NAME (every identifier of the file), F-STALE, F-COLS and F-REF.
Usage:
  check_figures.py [--figures DIR] [--spec FILE] [--config FILE]
  check_figures.py --selftest-negative   inject one fault per rule into a copy; each must be caught
Defaults: --figures = the folder of this script, --spec = ../spec.md, --config = ../doc_kit.yaml
(the layout of a doc folder that uses the vendored scripts).
Exit status: 0 when there is no violation, 1 otherwise.
"""
import argparse
import base64
import glob
import hashlib
import html
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
# Styles used by FTEL_DRAWIO_LIB_V1 (extracted from the library, 2026-09-29).
SHAPES = {"cloud", "curlyBracket", "or", "xor", "partialRectangle", "trapezoid",
          "mxgraph.electrical.logic_gates.logic_gate",
          "mxgraph.electrical.logic_gates.d_type_flip-flop",
          "mxgraph.electrical.logic_gates.d_type_flip-flop_with_clear_2",
          "mxgraph.electrical.logic_gates.d_type_rs_flip-flop"}
# edgeLabel is the text cell the drawio editor creates for a label placed on an edge.
NAMED_STYLES = {"ellipse", "group", "rhombus", "text", "triangle", "edgeLabel"}
MIN_FONT = 18
DEFAULT_NAMES = r"^(PARA_\w+|[a-z][a-z0-9]*(?:_[a-z0-9]+)+)$"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FIG_REF = re.compile(r"!\[([^\]]*)\]\((figures/[^)\s]+)\)")
CAPTION = re.compile(r"^Figure \d+-\d+(?::| \N{EM DASH}) \S")
WAVE_STR = re.compile(r"\b(?:wave|node)\s*:\s*'([^']*)'")
# Names injected by the negative test: the first one that the figure_names pattern selects is used.
NEG_NAMES = ["zz_not_in_spec_x", "PARA_ZZ_NOT_IN_SPEC", "zz_not_in_spec"]


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_names(config):
    """figure_names of doc_kit.yaml as a compiled pattern (the default when there is no setting)."""
    pattern = DEFAULT_NAMES
    if config and os.path.isfile(config):
        try:
            import yaml
        except ImportError:
            sys.exit(f"check_figures: reading {config} needs PyYAML")
        pattern = (yaml.safe_load(open(config, encoding="utf-8")) or {}).get("figure_names") or DEFAULT_NAMES
    return re.compile(pattern)


_NAMES = []


def default_names():
    """figure_names of the doc_kit.yaml of the doc folder above this script (the vendored layout), so that
    a generator that imports this module can call check_drawio(path, words) as before."""
    if not _NAMES:
        _NAMES.append(load_names(os.path.join(os.path.dirname(HERE), "doc_kit.yaml")))
    return _NAMES[0]


def diagrams(root):
    """mxGraphModel elements of every page, inflating compressed pages."""
    for d in root.iter("diagram"):
        model = d.find("mxGraphModel")
        if model is None and (d.text or "").strip():
            raw = zlib.decompress(base64.b64decode(d.text.strip()), -15).decode("utf-8")
            model = ET.fromstring(urllib.parse.unquote(raw))
        if model is not None:
            yield model


def label_text(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    return html.unescape(text).replace("\xa0", " ").strip()


def check_drawio(path, spec_words, names=None):
    names = names or default_names()
    out = []
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
        root = ET.fromstring(text)
    except (UnicodeDecodeError, ET.ParseError) as e:
        return [("F-XML", name, f"not valid XML: {e}")]
    bad = sorted({c for c in text if ord(c) > 127 and c != "\xa0"})
    if bad:
        out.append(("F-ASCII", name, "non-ASCII characters " + " ".join(f"U+{ord(c):04X}" for c in bad)))
    for model in diagrams(root):
        for cell in model.iter("mxCell"):
            cid = cell.get("id")
            style = cell.get("style") or ""
            tokens = [t for t in style.split(";") if t]
            keys = dict(t.split("=", 1) for t in tokens if "=" in t)
            if "shape" in keys and keys["shape"] not in SHAPES:
                out.append(("F-SHAPE", name, f"cell {cid}: shape={keys['shape']} is not in the FTEL library"))
            if tokens and "=" not in tokens[0] and tokens[0] not in NAMED_STYLES:
                out.append(("F-SHAPE", name, f"cell {cid}: style {tokens[0]} is not in the FTEL library"))
            shown = label_text(cell.get("value"))
            if not shown:
                continue
            size = float(keys.get("fontSize", 11))
            inline = [float(s) for s in re.findall(r"font-size:\s*([\d.]+)", html.unescape(cell.get("value")))]
            if size < MIN_FONT or any(s < MIN_FONT for s in inline):
                out.append(("F-FONT", name, f"cell {cid} '{shown[:30]}': font {min([size] + inline):g} < {MIN_FONT}"))
            for tok in IDENT.findall(shown):
                if names.match(tok) and tok not in spec_words:
                    out.append(("F-NAME", name, f"cell {cid}: '{tok}' does not occur in spec.md"))
    return out + check_stale(path, name)


def check_stale(path, name):
    svg = os.path.splitext(path)[0] + ".svg"
    if not os.path.isfile(svg):
        return [("F-STALE", name, "no .svg render; run render_drawio.py or render_wave.py")]
    m = re.search(r"sha256=([0-9a-f]{64})", open(svg, encoding="utf-8").read(4096))
    if not m or m.group(1) != sha256(path):
        return [("F-STALE", name, "the .svg was not rendered from the current source")]
    return []


def check_wave(path, spec_words, names=None):
    names = names or default_names()
    out = []
    name = os.path.basename(path)
    text = open(path, "rb").read().decode("utf-8", errors="replace")
    bad = sorted({c for c in text if ord(c) > 127})
    if bad:
        out.append(("F-ASCII", name, "non-ASCII characters " + " ".join(f"U+{ord(c):04X}" for c in bad)))
    for tok in sorted(set(IDENT.findall(text))):
        if names.match(tok) and tok not in spec_words:
            out.append(("F-NAME", name, f"'{tok}' does not occur in spec.md"))
    widths = {len(s) for s in WAVE_STR.findall(text) if s}
    if len(widths) > 1:
        out.append(("F-COLS", name, f"wave/node strings of {sorted(widths)} columns"))
    return out + check_stale(path, name)


def check(figures, spec, names=None):
    spec_text = open(spec, encoding="utf-8").read()
    spec_words = set(IDENT.findall(spec_text))
    out = []
    drawios = sorted(glob.glob(os.path.join(figures, "*.drawio")))
    for path in drawios:
        out += check_drawio(path, spec_words, names)
    waves = sorted(glob.glob(os.path.join(figures, "*.json5")))
    for path in waves:
        out += check_wave(path, spec_words, names)
    doc = os.path.dirname(os.path.abspath(spec))
    embedded = set()
    for caption, ref in FIG_REF.findall(spec_text):
        embedded.add(os.path.normpath(os.path.join(doc, ref)))
        if not os.path.isfile(os.path.join(doc, ref)):
            out.append(("F-REF", os.path.basename(spec), f"{ref} does not exist"))
        if not CAPTION.match(caption):
            out.append(("F-REF", os.path.basename(spec), f"caption of {ref} should read 'Figure N-M: ...'"))
    for path in drawios + waves:
        svg = os.path.normpath(os.path.splitext(path)[0] + ".svg")
        if svg not in embedded:
            out.append(("F-REF", os.path.basename(path), "not embedded in spec.md as its .svg"))
    return out


def report(out):
    for code, where, msg in out:
        print(f"{code:8s} {where}: {msg}")
    print(f"check_figures: {len(out)} violation(s)")
    return 1 if out else 0


def selftest_negative(figures, spec, names):
    drawios = sorted(glob.glob(os.path.join(figures, "*.drawio")))
    waves = sorted(glob.glob(os.path.join(figures, "*.json5")))
    if not drawios or not waves:
        sys.exit("--selftest-negative needs at least one .drawio and one .json5 figure")
    victim = os.path.basename(drawios[0])
    wave_victim = os.path.basename(waves[0])
    bad_name = next((n for n in NEG_NAMES if names.match(n)), None)

    def add_cell(xml, cell):
        return xml.replace("</root>", cell + "</root>", 1)

    faults = {
        "F-XML": lambda x, s: (x[:-40], s),
        "F-ASCII": lambda x, s: (add_cell(x, '<mxCell id="neg1" value="x \N{GREATER-THAN OR EQUAL TO} 1" '
                                             'style="text;fontSize=18;" vertex="1" parent="1">'
                                             '<mxGeometry as="geometry"/></mxCell>'), s),
        "F-FONT": lambda x, s: (add_cell(x, '<mxCell id="neg2" value="tiny" style="text;fontSize=11;" '
                                            'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-SHAPE": lambda x, s: (add_cell(x, '<mxCell id="neg3" value="" style="shape=mxgraph.aws4.lambda_function;" '
                                             'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-NAME": lambda x, s: (add_cell(x, f'<mxCell id="neg4" value="{bad_name}" style="text;fontSize=18;" '
                                            'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-STALE": lambda x, s: (x.replace("</mxfile>", "<!-- edited --></mxfile>", 1), s),
        "F-REF": lambda x, s: (x, re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(victim[:-7]) + r"\.svg\)", "", s)),
    }
    wave_faults = {
        "F-ASCII": lambda x, s: (x.replace("signal: [", "signal: [ // \N{GREATER-THAN OR EQUAL TO}", 1), s),
        "F-NAME": lambda x, s: (x.replace("signal: [", f"signal: [ {{ name: '{bad_name}' }},", 1), s),
        "F-STALE": lambda x, s: (x + "\n// edited\n", s),
        "F-COLS": lambda x, s: (re.sub(r"(wave\s*:\s*')([^']*)'", lambda m: m.group(1) + m.group(2) + ".'", x, count=1), s),
        "F-REF": lambda x, s: (x, re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(wave_victim[:-6]) + r"\.svg\)", "", s)),
    }
    if bad_name is None:
        print("SKIP  F-NAME: figure_names selects none of " + ", ".join(NEG_NAMES))
        del faults["F-NAME"], wave_faults["F-NAME"]
    cases = [("clean", None, None)] + [(c, victim, f) for c, f in faults.items()] + \
            [(c, wave_victim, f) for c, f in wave_faults.items()]
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for code, target, inject in cases:
            case = os.path.join(tmp, f"{code}_{target}")
            fig = os.path.join(case, "figures")
            shutil.copytree(figures, fig, ignore=shutil.ignore_patterns("*.png", "selftest", ".drawio_cache",
                                                                         "__pycache__"))
            spec_copy = os.path.join(case, "spec.md")
            shutil.copy(spec, spec_copy)
            if inject:
                x, s = inject(open(os.path.join(fig, target), encoding="utf-8").read(),
                              open(spec_copy, encoding="utf-8").read())
                open(os.path.join(fig, target), "w", encoding="utf-8").write(x)
                open(spec_copy, "w", encoding="utf-8").write(s)
            found = check(fig, spec_copy, names)
            codes = {c for c, _, _ in found}
            ok = not codes if code == "clean" else any(c == code and w == target for c, w, _ in found)
            failures += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {code:8s} {target or '':44s} -> {sorted(codes) or 'no violation'}")
    print(f"selftest-negative: {len(cases) - failures}/{len(cases)} PASS")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--figures", default=HERE)
    ap.add_argument("--spec", help="default: spec.md beside the figures folder")
    ap.add_argument("--config", help="doc_kit.yaml (default: beside the figures folder)")
    ap.add_argument("--selftest-negative", action="store_true")
    a = ap.parse_args()
    figures = os.path.abspath(a.figures)
    doc = os.path.dirname(figures)
    spec = a.spec or os.path.join(doc, "spec.md")
    names = load_names(a.config or os.path.join(doc, "doc_kit.yaml"))
    if a.selftest_negative:
        sys.exit(selftest_negative(figures, spec, names))
    sys.exit(report(check(figures, spec, names)))


if __name__ == "__main__":
    main()
