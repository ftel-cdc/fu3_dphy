#!/usr/bin/env python3
# Vendored from ftel_doc_kit 1.0.1 (skills/ftel-block-diagram/scripts/drawio_fig.py); edit the kit, then run kit.py vendor.
#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-12
# Description     : Builder of drawio figures from Python, with the FTEL figure styles.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-12   0.1        Ho Khanh Linh Initial creation (class Fig of two figure generators of
#                                       ftel_dphy_rx).
# 2026-11-02   1.0        Ho Khanh Linh Moved into ftel_doc_kit: the two Fig classes merged.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Builder of drawio figures from Python, with the FTEL figure styles (skill ftel-block-diagram).

A generator script lays a figure out in code, so a set of related figures (options of one block,
one figure per lane count, ...) keeps the same geometry, labels and legend, and a change is one edit
plus a run. The .drawio it writes is the source that render_drawio.py and check_figures.py take, and
it can still be opened and finished by hand in the drawio editor (then the script is no longer the
source: say so in the figure README).

    from drawio_fig import Fig, E_DATA, E_CTRL, E_CLK, BLUE
    f = Fig("ftel_x_top", "x-top")
    f.cont("top", "<b>ftel_x</b>", 200, 40, 600, 300)
    f.box("cnt", "counter", 260, 120, 160, 80, fill=BLUE)
    f.box("cmp", "compare", 520, 120, 160, 80, fill=BLUE)
    f.edge("e1", "count[31:0]", E_DATA, "cnt", (420, 160), "cmp", (520, 160))
    f.legend(200, 380, [(BLUE, "pclk domain")], [(E_DATA, "data"), (E_CTRL, "control")])
    f.write("doc/figures")

Coordinates are absolute pixels. An edge leaves its source at the point p_src and enters its target
at p_dst; both points must lie on (or inside) the rectangles of the two cells, and they become
exitX/exitY and entryX/entryY, so the edge stays attached when a block is moved in the editor.
Every style keeps the figure rules: fontSize 18 (20 for frame titles), strokeWidth 2 (4 for data
buses), orthogonal edges with arc jumps, ASCII-only XML.
"""
import os
import xml.etree.ElementTree as ET

BOX = ("rounded=0;whiteSpace=wrap;html=1;fontSize=18;strokeWidth=2;fillColor={fill};"
       "align=center;verticalAlign=middle;spacing=4;")
BOX_UNUSED = ("rounded=0;whiteSpace=wrap;html=1;fontSize=18;strokeWidth=2;fillColor=#FFFFFF;"
              "align=center;verticalAlign=middle;spacing=4;dashed=1;dashPattern=8 4;"
              "strokeColor=#B3B3B3;fontColor=#808080;")
CONT = ("rounded=0;whiteSpace=wrap;html=1;fontSize=18;strokeWidth=2;fillColor=none;"
        "verticalAlign=top;align={align};spacingLeft=10;spacingTop=2;")
FRAME = ("rounded=1;whiteSpace=wrap;html=1;fontSize=20;fontStyle=1;verticalAlign=top;"
         "strokeWidth=2;fillColor=none;arcSize=2;spacingTop=6;")
TEXT = ("text;html=1;whiteSpace=wrap;fontSize=18;align={align};verticalAlign=middle;"
        "strokeColor=none;fillColor=none;spacing=2;")
EDGE = ("endArrow=block;endFill=1;html=1;fontSize=18;edgeStyle=orthogonalEdgeStyle;rounded=0;"
        "jumpStyle=arc;jumpSize=12;labelBackgroundColor=#FFFFFF;")
E_DATA = EDGE + "strokeWidth=4;"                       # data bus: thick
E_CTRL = EDGE + "strokeWidth=2;"                       # control and status: thin
E_BIDIR = E_CTRL + "startArrow=block;startFill=1;"     # control in both directions
E_CLK = EDGE + "strokeWidth=2;dashed=1;dashPattern=8 4;strokeColor=#666666;fontColor=#666666;"   # clock, reset
E_CFG = EDGE + "strokeWidth=2;dashed=1;dashPattern=2 4;strokeColor=#2D7600;fontColor=#2D7600;"   # configuration
WIRE = EDGE + "strokeWidth=2;endArrow=none;"           # connection without a direction
CROSS = WIRE + "jumpStyle=none;"                       # lines that cross on purpose (pad diagonals)
RAIL = EDGE + "strokeWidth=4;endArrow=none;"           # supply or bus rail
MUX = ("shape=trapezoid;perimeter=trapezoidPerimeter;whiteSpace=wrap;html=1;fixedSize=1;rotation=90;"
       "strokeWidth=2;size=12;")                       # 2:1 multiplexer, inputs on the left
# Fills. One clock domain = one fill, named in the legend (rule B13); analog parts grey.
GREY, PURPLE, BLUE, ORANGE, GREEN, WHITE = "#F5F5F5", "#E1D5E7", "#DAE8FC", "#FFE6CC", "#D5E8D4", "#FFFFFF"


class Fig:
    """One single-page drawio figure built from boxes, containers, texts and edges."""

    def __init__(self, name, did, out_dir=None):
        self.name = name
        self.out_dir = out_dir
        self.mx = ET.Element("mxfile", host="app.diagrams.net")
        diagram = ET.SubElement(self.mx, "diagram", name=name, id=did)
        model = ET.SubElement(diagram, "mxGraphModel", dx="1600", dy="1000", grid="1", gridSize="10",
                              guides="1", tooltips="1", connect="1", arrows="1", fold="1", page="0",
                              pageScale="1", math="0", shadow="0")
        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.rect = {}

    def _cell(self, cid, value, style, **kw):
        if cid in self.rect or self.root.find(f"mxCell[@id='{cid}']") is not None:
            raise ValueError(f"duplicate cell id {cid}")
        return ET.SubElement(self.root, "mxCell", id=cid, value=value, style=style, parent="1", **kw)

    def vertex(self, cid, value, style, x, y, w, h):
        cell = self._cell(cid, value, style, vertex="1")
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h),
                      **{"as": "geometry"})
        self.rect[cid] = (x, y, w, h)
        return cid

    def box(self, cid, value, x, y, w, h, fill=WHITE):
        """Block: a rectangle with its name centred."""
        return self.vertex(cid, value, BOX.format(fill=fill), x, y, w, h)

    def unused(self, cid, value, x, y, w, h):
        """Block or pin that exists but is not used here: light grey dashed."""
        return self.vertex(cid, value, BOX_UNUSED, x, y, w, h)

    def cont(self, cid, value, x, y, w, h, align="center"):
        """Container: a module boundary with its name at the top."""
        return self.vertex(cid, value, CONT.format(align=align), x, y, w, h)

    def frame(self, cid, value, x, y, w, h):
        """Rounded frame with a bold title: a chip, a board or a group of blocks."""
        return self.vertex(cid, value, FRAME, x, y, w, h)

    def text(self, cid, value, x, y, w, h, align="left"):
        return self.vertex(cid, value, TEXT.format(align=align), x, y, w, h)

    def _port(self, cid, px, py):
        x, y, w, h = self.rect[cid]
        if not (x <= px <= x + w and y <= py <= y + h):
            raise ValueError(f"{self.name}: port ({px},{py}) outside {cid} {self.rect[cid]}")
        return round((px - x) / w, 4), round((py - y) / h, 4)

    def edge(self, cid, value, style, src, p_src, dst, p_dst, points=(), off=(0, -16), pos=0.0):
        """Edge from point p_src on the border of src to p_dst on the border of dst.

        pos places the label along the path (-1 at the source, 0 in the middle, 1 at the target),
        off shifts it in pixels; points are the corners of the path.
        """
        ex, ey = self._port(src, *p_src)
        nx, ny = self._port(dst, *p_dst)
        st = (style + f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
              f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;")
        cell = self._cell(cid, value, st, edge="1", source=src, target=dst)
        geo_attr = {"relative": "1", "as": "geometry"}
        if pos:
            geo_attr["x"] = str(pos)
        geo = ET.SubElement(cell, "mxGeometry", **geo_attr)
        if points:
            arr = ET.SubElement(geo, "Array", **{"as": "points"})
            for px, py in points:
                ET.SubElement(arr, "mxPoint", x=str(px), y=str(py))
        if value:
            ET.SubElement(geo, "mxPoint", x=str(off[0]), y=str(off[1]), **{"as": "offset"})

    def mux(self, cid, x, y, w, h):
        """Multiplexer filling the box (x, y, w, h): inputs on the left side, output in the middle of the
        right side, the select on the top edge at x + w / 2, y + 6."""
        cell = self._cell(cid, "", MUX, vertex="1")
        ET.SubElement(cell, "mxGeometry", x=str(x + (w - h) // 2), y=str(y + (h - w) // 2), width=str(h),
                      height=str(w), **{"as": "geometry"})

    def wire(self, cid, value, style, p0, p1, off=(0, -16), pos=0.0):
        """Straight edge from p0 to p1 with free ends: the inputs, the select and the output of a
        multiplexer, which has no ports to attach to."""
        cell = self._cell(cid, value, style + "edgeStyle=none;", edge="1")
        geo_attr = {"relative": "1", "as": "geometry"}
        if pos:
            geo_attr["x"] = str(pos)
        geo = ET.SubElement(cell, "mxGeometry", **geo_attr)
        for (px, py), role in ((p0, "sourcePoint"), (p1, "targetPoint")):
            ET.SubElement(geo, "mxPoint", x=str(px), y=str(py), **{"as": role})
        if value:
            ET.SubElement(geo, "mxPoint", x=str(off[0]), y=str(off[1]), **{"as": "offset"})

    def line(self, cid, style, x0, y0, x1, y1):
        """Free line without a label: pad wires, rails and the keys of a legend."""
        cell = self._cell(cid, "", style + "edgeStyle=none;", edge="1")
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(geo, "mxPoint", x=str(x0), y=str(y0), **{"as": "sourcePoint"})
        ET.SubElement(geo, "mxPoint", x=str(x1), y=str(y1), **{"as": "targetPoint"})

    def pad(self, cid, x, y, size=28):
        """Pad glyph: a square with both diagonals."""
        self.box(cid, "", x, y, size, size)
        self.line(cid + "_d1", CROSS, x, y, x + size, y + size)
        self.line(cid + "_d2", CROSS, x + size, y, x, y + size)

    def legend(self, x, y, fills, lines, col_w=340, frame_w=None):
        """Legend: one row of fill samples, one row of line samples, col_w apart.

        fills: (fill, label) or (fill, label, unused); lines: (style, label). With frame_w the
        legend sits in a frame of that width, its content shifted 10 px to the right.
        """
        dx = 0
        if frame_w:
            self.vertex("leg_frame", "", BOX.format(fill="none"), x, y, frame_w, 130)
            self.text("leg_title", "<b>Legend</b>", x + 10, y + 4, 100, 32)
            dx = 10
        else:
            self.text("leg_title", "<b>Legend</b>", x, y, 100, 32)
        for i, entry in enumerate(fills):
            fill, label = entry[0], entry[1]
            xx = x + dx + i * col_w
            if len(entry) > 2 and entry[2]:
                self.unused(f"leg_f{i}", "", xx, y + 46, 40, 24)
            else:
                self.box(f"leg_f{i}", "", xx, y + 46, 40, 24, fill)
            self.text(f"leg_ft{i}", label, xx + 48, y + 40, col_w - 56, 36)
        for i, (style, label) in enumerate(lines):
            xx = x + dx + i * col_w
            self.line(f"leg_k{i}", style, xx, y + 102, xx + 40, y + 102)
            self.text(f"leg_kt{i}", label, xx + 48, y + 84, col_w - 56, 36)

    def xml(self):
        ET.indent(self.mx, space="  ")
        text = ET.tostring(self.mx, encoding="unicode") + "\n"
        text.encode("ascii")  # rule B9: ASCII-only XML
        return text

    def write(self, out_dir=None):
        """Write <name>.drawio into out_dir (or the folder given at construction, or the current
        folder) and return its path."""
        path = os.path.join(out_dir or self.out_dir or os.getcwd(), self.name + ".drawio")
        with open(path, "w", encoding="ascii") as f:
            f.write(self.xml())
        return path
