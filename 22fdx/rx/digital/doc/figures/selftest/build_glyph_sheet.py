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
# Created Date    : 2026-09-29
# Description     : Lay every entry of the FTEL drawio library out on one page, each with an index
#                   label.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-09-29   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Lay every entry of the FTEL drawio library out on one page, each with an index label.

The sheet is the selftest input of render_drawio.py: when the renderer draws every glyph of the
library the way the drawio server does, the PNG matches ftel_lib_glyphs.png pixel for pixel.

Cells of an entry keep their structure; only cells whose parent is the root layer ("1") are
moved (vertices by their geometry, edges by all their points). Ids are prefixed per entry.

Usage: build_glyph_sheet.py [<FTEL_DRAWIO_LIB_V1.drawio>] [<out.drawio>]
Defaults: $FTEL_DRAWIO_LIB or ~/Documents/FX1_ips/Common_Info/FTEL_DRAWIO_LIB_V1.drawio,
          ftel_lib_glyphs.drawio beside this script.
"""
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

COLS, CELL_W, CELL_H = 6, 280, 250


def build(lib_path, out_path):
    lib = json.loads(re.search(r"<mxlibrary>(.*)</mxlibrary>",
                               open(lib_path, encoding="utf-8").read(), re.S).group(1))
    root = ET.Element("root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    for i, entry in enumerate(lib):
        model = ET.fromstring(html.unescape(entry["xml"]))
        cells = [c for c in model.iter("mxCell") if c.get("id") not in ("0", "1")]
        dx, dy = 30 + (i % COLS) * CELL_W, 30 + (i // COLS) * CELL_H
        prefix = f"e{i}-"
        shapes = []
        for c in cells:
            for key in ("id", "source", "target"):
                if c.get(key):
                    c.set(key, prefix + c.get(key))
            if c.get("parent") not in ("0", "1"):
                c.set("parent", prefix + c.get("parent"))
            else:
                c.set("parent", "1")
                g = c.find("mxGeometry")
                if g is not None:
                    if c.get("edge") == "1":
                        for p in g.iter("mxPoint"):
                            p.set("x", str(float(p.get("x", 0)) + dx))
                            p.set("y", str(float(p.get("y", 0)) + dy))
                    else:
                        g.set("x", str(float(g.get("x", 0)) + dx))
                        g.set("y", str(float(g.get("y", 0)) + dy))
            m = re.search(r"shape=([^;]+)", c.get("style", ""))
            if m:
                shapes.append(m.group(1).split(".")[-1])
            root.append(c)
        label = ET.SubElement(root, "mxCell", id=f"lbl{i}", parent="1", vertex="1",
                              value=f"#{i} " + (",".join(sorted(set(shapes)))[:24] if shapes else ""),
                              style="text;html=1;align=left;verticalAlign=top;fontSize=14;")
        ET.SubElement(label, "mxGeometry", x=str(dx), y=str(dy + 165), width="250", height="40",
                      **{"as": "geometry"})
    model = ET.Element("mxGraphModel", grid="1", gridSize="10", page="0")
    model.append(root)
    mxfile = ET.Element("mxfile", host="app.diagrams.net")
    diagram = ET.SubElement(mxfile, "diagram", name="ftel_lib_glyphs", id="ftelLibGlyphs0")
    diagram.append(model)
    ET.ElementTree(mxfile).write(out_path, encoding="utf-8", xml_declaration=False)
    print(f"{len(lib)} library entries -> {out_path}")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    lib_default = os.environ.get("FTEL_DRAWIO_LIB", os.path.expanduser(
        "~/Documents/FX1_ips/Common_Info/FTEL_DRAWIO_LIB_V1.drawio"))
    build(sys.argv[1] if len(sys.argv) > 1 else lib_default,
          sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "ftel_lib_glyphs.drawio"))
