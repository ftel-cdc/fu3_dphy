#!/usr/bin/env python3
"""Rule checks for the figures of ftel_dphy_rx (the rules are listed in README.md beside this file).

Every doc/figures/*.drawio is checked against its render and against doc/spec.md:
  F-XML    the .drawio parses as XML (compressed diagrams are inflated first)
  F-ASCII  only ASCII characters; U+00A0, which the drawio editor writes, is accepted
  F-FONT   every cell that shows text sets fontSize >= 18, and inline HTML font sizes are >= 18
  F-SHAPE  shapes come from FTEL_DRAWIO_LIB_V1 (SHAPES, NAMED_STYLES), plain rectangles or edges
  F-NAME   every port, parameter or run-time field name in a label occurs in doc/spec.md
  F-STALE  <base>.svg exists and records the sha256 of the current .drawio (render_drawio.py stamp)
  F-REF    every figures/ image embedded in spec.md exists, has a "Figure N-M -- ..." caption
           (em dash in the spec), and every .drawio is embedded as <base>.svg
Usage:
  check_figures.py [--figures DIR] [--spec FILE]
  check_figures.py --selftest-negative   inject one fault per rule into a copy; each must be caught
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
PORT_LIKE = re.compile(r"^(afe_\w+|PARA_\w+|rx\w+|err\w+|cl_\w+|dl_\w+|\w+_x|\w+_cyc|"
                       r"init_done|phy_core_rst|core_clk|deskew_bypass)$")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FIG_REF = re.compile(r"!\[([^\]]*)\]\((figures/[^)\s]+)\)")
CAPTION = re.compile(r"^Figure \d+-\d+ — \S")


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


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
    return html.unescape(text).replace(" ", " ").strip()


def check_drawio(path, spec_words):
    out = []
    name = os.path.basename(path)
    raw = open(path, "rb").read()
    try:
        text = raw.decode("utf-8")
        root = ET.fromstring(text)
    except (UnicodeDecodeError, ET.ParseError) as e:
        return [("F-XML", name, f"not valid XML: {e}")]
    bad = sorted({c for c in text if ord(c) > 127 and c != " "})
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
                if PORT_LIKE.match(tok) and tok not in spec_words:
                    out.append(("F-NAME", name, f"cell {cid}: '{tok}' does not occur in spec.md"))
    svg = os.path.splitext(path)[0] + ".svg"
    if not os.path.isfile(svg):
        out.append(("F-STALE", name, "no .svg render; run render_drawio.py"))
    else:
        m = re.search(r"sha256=([0-9a-f]{64})", open(svg, encoding="utf-8").read(4096))
        if not m or m.group(1) != sha256(path):
            out.append(("F-STALE", name, "the .svg was not rendered from the current .drawio; run render_drawio.py"))
    return out


def check(figures, spec):
    spec_text = open(spec, encoding="utf-8").read()
    spec_words = set(IDENT.findall(spec_text))
    out = []
    drawios = sorted(glob.glob(os.path.join(figures, "*.drawio")))
    for path in drawios:
        out += check_drawio(path, spec_words)
    doc = os.path.dirname(os.path.abspath(spec))
    embedded = set()
    for caption, ref in FIG_REF.findall(spec_text):
        embedded.add(os.path.normpath(os.path.join(doc, ref)))
        if not os.path.isfile(os.path.join(doc, ref)):
            out.append(("F-REF", os.path.basename(spec), f"{ref} does not exist"))
        if not CAPTION.match(caption):
            out.append(("F-REF", os.path.basename(spec), f"caption of {ref} should read 'Figure N-M — ...'"))
    for path in drawios:
        svg = os.path.normpath(os.path.splitext(path)[0] + ".svg")
        if svg not in embedded:
            out.append(("F-REF", os.path.basename(path), "not embedded in spec.md as its .svg"))
    return out


def report(out):
    for code, where, msg in out:
        print(f"{code:8s} {where}: {msg}")
    print(f"check_figures: {len(out)} violation(s)")
    return 1 if out else 0


def selftest_negative(figures, spec):
    drawios = sorted(glob.glob(os.path.join(figures, "*.drawio")))
    if not drawios:
        sys.exit("--selftest-negative needs at least one figure")
    victim = os.path.basename(drawios[0])

    def add_cell(xml, cell):
        return xml.replace("</root>", cell + "</root>", 1)

    faults = {
        "F-XML": lambda x, s: (x[:-40], s),
        "F-ASCII": lambda x, s: (add_cell(x, '<mxCell id="neg1" value="x ≥ 1" style="text;fontSize=18;" '
                                             'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-FONT": lambda x, s: (add_cell(x, '<mxCell id="neg2" value="tiny" style="text;fontSize=11;" '
                                            'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-SHAPE": lambda x, s: (add_cell(x, '<mxCell id="neg3" value="" style="shape=mxgraph.aws4.lambda_function;" '
                                             'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-NAME": lambda x, s: (add_cell(x, '<mxCell id="neg4" value="afe_hs_wrod_x" style="text;fontSize=18;" '
                                            'vertex="1" parent="1"><mxGeometry as="geometry"/></mxCell>'), s),
        "F-STALE": lambda x, s: (x.replace("</mxfile>", "<!-- edited --></mxfile>", 1), s),
        "F-REF": lambda x, s: (x, re.sub(r"!\[[^\]]*\]\(figures/" + re.escape(victim[:-7]) + r"\.svg\)", "", s)),
    }
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for code, inject in [("clean", None)] + list(faults.items()):
            case = os.path.join(tmp, code)
            fig = os.path.join(case, "figures")
            shutil.copytree(figures, fig, ignore=shutil.ignore_patterns("*.png", "selftest", ".drawio_cache"))
            spec_copy = os.path.join(case, "spec.md")
            shutil.copy(spec, spec_copy)
            if inject:
                x, s = inject(open(os.path.join(fig, victim), encoding="utf-8").read(),
                              open(spec_copy, encoding="utf-8").read())
                open(os.path.join(fig, victim), "w", encoding="utf-8").write(x)
                open(spec_copy, "w", encoding="utf-8").write(s)
            codes = {c for c, _, _ in check(fig, spec_copy)}
            ok = not codes if code == "clean" else code in codes
            failures += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {code:8s} -> {sorted(codes) or 'no violation'}")
    print(f"selftest-negative: {len(faults) + 1 - failures}/{len(faults) + 1} PASS")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--figures", default=HERE)
    ap.add_argument("--spec", default=os.path.join(os.path.dirname(HERE), "spec.md"))
    ap.add_argument("--selftest-negative", action="store_true")
    a = ap.parse_args()
    if a.selftest_negative:
        sys.exit(selftest_negative(a.figures, a.spec))
    sys.exit(report(check(a.figures, a.spec)))


if __name__ == "__main__":
    main()
