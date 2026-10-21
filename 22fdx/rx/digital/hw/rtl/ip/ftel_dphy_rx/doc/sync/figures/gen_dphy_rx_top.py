#!/usr/bin/env python3
"""Write the drawio sources of the D-PHY RX top figures for the AFE team and the GPIO options.

dphy_rx_top.drawio shows the analog front-end (AFE) and ftel_dphy_rx with one clock lane and four
data lanes, and the whole PPI taken out of the chip through GPIO pins (direction of 2026-10-20: no
CSI-2 controller on the chip). dphy_rx_top_opt1..4.drawio keep the same AFE and ftel_dphy_rx and
show four ways to need fewer GPIO pins, options 1 to 3 each built on the one before:
  1. only the PPI signals that a CSI-2 controller needs in real time go to pins; the enables, the
     slow status and the configuration go through an SPI slave with registers at the chip top;
  2. option 1, with the five HS flags of each lane encoded in a 3-bit code and the LP errors
     counted in the SPI registers;
  3. option 2, with the data and the code of each lane on DDR pins;
  4. plain GPIOs of at most 50 MHz (direction of 2026-10-21: the pins are for debug, the FPGA does
     the rest), so up to 400 Mb/s per lane: the data pins of a lane carry its LP flags between HS
     bursts, its HS flags and rxskewcalhs_x are encoded in 3 bits, stopstate_x keeps a pin, and the
     clock-lane flags go through the SPI with the configuration and the enables. The figure draws
     the encoder and the multiplexer of each lane, the table of the code, and one HS burst on the
     pins of a lane.
ftel_dphy_rx keeps its standard PPI in every option: the SPI registers, the encoders, the
multiplexers and the DDR outputs are chip-top logic outside it.

The figures follow the rules of ../../figures/README.md, with the helpers of
fpga/figures/gen_figures.py, and keep the text short: the clock lane and data lane 0 carry the
signal names, data lanes 1 to 3 repeat their arrows without names (as HAS Figure 2-3 does). Signal
names are those of the HAS (doc/spec.md, Tables 5-1 and 5-2); the pin counts are computed from
Table 5-1, and the script stops when a group no longer matches the table.

The .drawio files are generated: edit this script, then run it, render the figures and check them.
  python3 hw/rtl/ip/ftel_dphy_rx/doc/sync/figures/gen_dphy_rx_top.py
  python3 hw/rtl/ip/ftel_dphy_rx/doc/figures/render_drawio.py \
          hw/rtl/ip/ftel_dphy_rx/doc/sync/figures/dphy_rx_top*.drawio
  python3 hw/rtl/ip/ftel_dphy_rx/doc/sync/figures/gen_dphy_rx_top.py --check
--check runs the rules F-XML, F-ASCII, F-FONT, F-SHAPE, F-NAME (names against doc/spec.md) and
F-STALE of check_figures.py on every figure. F-REF does not apply: the figures are not in the HAS.
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DOC = os.path.dirname(os.path.dirname(HERE))
SPEC = os.path.join(DOC, "spec.md")
HAS_FIGURES = os.path.join(DOC, "figures")
LANES = 4
SPI_PINS = 4  # SCK, CS_N, MOSI, MISO
GPIO_MHZ = 50  # option 4: one PPI byte per pin and byte clock, so the line rate is at most 8 x GPIO_MHZ

BOX = ("rounded=0;whiteSpace=wrap;html=1;fontSize=18;strokeWidth=2;fillColor={fill};"
       "align=center;verticalAlign=middle;spacing=4;")
CONT = ("rounded=0;whiteSpace=wrap;html=1;fontSize=18;strokeWidth=2;fillColor=none;"
        "verticalAlign=top;align={align};spacingLeft=10;spacingTop=2;")
FRAME = ("rounded=1;whiteSpace=wrap;html=1;fontSize=20;fontStyle=1;verticalAlign=top;"
         "strokeWidth=2;fillColor=none;arcSize=2;spacingTop=6;")
TEXT = ("text;html=1;whiteSpace=wrap;fontSize=18;align={align};verticalAlign=middle;"
        "strokeColor=none;fillColor=none;spacing=2;")
EDGE = ("endArrow=block;endFill=1;html=1;fontSize=18;edgeStyle=orthogonalEdgeStyle;rounded=0;"
        "jumpStyle=arc;jumpSize=12;labelBackgroundColor=#FFFFFF;")
E_DATA = EDGE + "strokeWidth=4;"
E_CTRL = EDGE + "strokeWidth=2;"
E_BIDIR = E_CTRL + "startArrow=block;startFill=1;"
E_CLK = EDGE + "strokeWidth=2;dashed=1;dashPattern=8 4;strokeColor=#666666;fontColor=#666666;"
E_CFG = EDGE + "strokeWidth=2;dashed=1;dashPattern=2 4;strokeColor=#2D7600;fontColor=#2D7600;"
WIRE = EDGE + "strokeWidth=2;endArrow=none;"
CROSS = WIRE + "jumpStyle=none;"  # pad diagonals: they cross, without an arc jump
RAIL = EDGE + "strokeWidth=4;endArrow=none;"
GREY, PURPLE, BLUE, ORANGE, GREEN, WHITE = "#F5F5F5", "#E1D5E7", "#DAE8FC", "#FFE6CC", "#D5E8D4", "#FFFFFF"

# PPI groups of the figures. Every signal of HAS Table 5-1 is in exactly one group.
GROUPS = {
    "cl_clk": ["rxbyteclkhs"],
    "cl_rt": ["cl_stopstate", "cl_ulpsclknot"],
    "cl_slow": ["cl_ulpsactivenot", "cl_rxclkactivehs"],
    "init": ["init_done"],
    "cl_en": ["cl_enable"],
    "rst": ["phy_core_rst"],
    "dl_data": ["rxdatahs_x"],
    "dl_hs": ["rxvalidhs_x", "rxactivehs_x", "rxsynchs_x", "errsoths_x", "errsotsynchs_x"],
    "dl_skew": ["rxskewcalhs_x"],
    "dl_lp": ["stopstate_x", "rxulpsesc_x"],
    "dl_err": ["erresc_x", "errcontrol_x"],
    "dl_slow": ["ulpsactivenot_x", "rxtriggeresc_x"],
    "dl_clkesc": ["rxclkesc_x"],
    "dl_en": ["dl_enable_x", "forcerxmode_x"],
    "lpdt": ["rxlpdtesc_x", "rxdataesc_x", "rxvalidesc_x", "errsyncesc_x"],
    "system": ["core_clk"],
}
INPUT_GROUPS = {"cl_en", "rst", "dl_en", "system"}
# Combinations of the HS flags of group dl_hs that ftel_dphy_rx produces (HAS 5.1). Option 2 sends
# their number in a code, with one more code for any other combination.
HS_STATES = ["idle", "active", "active + SoT sync error", "valid", "valid + sync", "valid + sync + SoT error"]
CODE_W = len(HS_STATES).bit_length()
# Option 4: the LP flags that share the data pins of a lane between HS bursts (stopstate_x keeps its
# pin), and the code of the HS flags with rxskewcalhs_x: the combinations of HS_STATES, deskew, and one
# code for any other, which fill the 3 bits; bit 2 of the code is rxvalidhs_x.
LP_VIEW = ["ulpsactivenot_x", "rxulpsesc_x", "rxtriggeresc_x", "erresc_x", "errcontrol_x"]
FLAG_WORDS = {"rxactivehs_x": "active", "rxvalidhs_x": "valid", "rxsynchs_x": "sync", "errsoths_x": "SoT error",
              "errsotsynchs_x": "SoT sync error", "rxskewcalhs_x": "deskew"}
CODES4 = [("000", []), ("001", ["rxactivehs_x"]), ("010", ["rxskewcalhs_x"]),
          ("011", ["rxactivehs_x", "errsotsynchs_x"]), ("100", ["rxactivehs_x", "rxvalidhs_x"]),
          ("101", ["rxactivehs_x", "rxvalidhs_x", "rxsynchs_x"]),
          ("110", ["rxactivehs_x", "rxvalidhs_x", "rxsynchs_x", "errsoths_x"]), ("111", None)]
CODE_W4 = len(CODES4[0][0])
MUX = ("shape=trapezoid;perimeter=trapezoidPerimeter;whiteSpace=wrap;html=1;fixedSize=1;rotation=90;"
       "strokeWidth=2;size=12;")  # 2:1 multiplexer of the HAS figures, inputs on the left

OPTIONS = {
    0: ("dphy_rx_top", "DphyRxTop0", "D-PHY RX top  --  AFE and ftel_dphy_rx, PPI out through GPIO"),
    1: ("dphy_rx_top_opt1", "DphyRxTopOpt1", "D-PHY RX top, GPIO option 1  --  {total} pins: real-time PPI on pins, the rest over SPI"),
    2: ("dphy_rx_top_opt2", "DphyRxTopOpt2", "D-PHY RX top, GPIO option 2  --  {total} pins: option 1 with encoded HS flags, "
        "LP errors over SPI"),
    3: ("dphy_rx_top_opt3", "DphyRxTopOpt3", "D-PHY RX top, GPIO option 3  --  {total} pins: option 2 with data and code on DDR pins"),
    4: ("dphy_rx_top_opt4", "DphyRxTopOpt4", f"D-PHY RX top, GPIO option 4  --  {{total}} pins at {GPIO_MHZ} MHz, "
        f"up to {8 * GPIO_MHZ} Mb/s per lane"),
}


def ppi_table():
    """Rows of HAS Table 5-1: name -> (direction, width, R1 column)."""
    text = open(SPEC, encoding="utf-8").read()
    body = text[text.index("**Table 5-1"):text.index("**Timing at the PPI.**")]
    rows = {}
    for line in body.splitlines():
        if line.startswith("| `"):
            name, d, w, _dom, _src, _inact, r1 = [c.strip() for c in line.strip("|").split("|")]
            rows[name.strip("`")] = (d, int(w), r1)
    return rows


def ppi_counts():
    """Width of every group (per lane for the _x groups), checked against HAS Table 5-1."""
    rows = ppi_table()
    named = [s for sigs in GROUPS.values() for s in sigs]
    if len(named) != len(set(named)) or set(named) != set(rows):
        sys.exit(f"PPI groups do not match HAS Table 5-1: {sorted(set(named) ^ set(rows))}")
    for group, sigs in GROUPS.items():
        want = "In" if group in INPUT_GROUPS else "Out"
        if any(rows[s][0] != want for s in sigs):
            sys.exit(f"group {group}: direction differs from HAS Table 5-1")
    if {s for s, (_, _, r1) in rows.items() if r1.startswith("Tied")} != set(GROUPS["lpdt"]):
        sys.exit("group lpdt: not the tied-off outputs of HAS Table 5-1")
    return {g: sum(rows[s][1] for s in sigs) for g, sigs in GROUPS.items()}


def pins(opt):
    """GPIO pins of option opt: clock lane, one data lane, SPI, total; and the per-lane LP flags."""
    w = ppi_counts()
    if opt == 0:
        clock = w["cl_clk"] + w["cl_rt"] + w["cl_slow"] + w["init"] + w["cl_en"] + w["rst"]
        lane = sum(w[g] for g in ("dl_data", "dl_hs", "dl_skew", "dl_lp", "dl_err", "dl_slow", "dl_clkesc",
                                  "dl_en"))
        lp, spi = 0, 0
    elif opt == 4:
        lp_groups = GROUPS["dl_lp"] + GROUPS["dl_err"] + GROUPS["dl_slow"]
        lp = sum(ppi_table()[s][1] for s in LP_VIEW)
        if lp != w["dl_data"] or set(LP_VIEW) | {"stopstate_x"} != set(lp_groups):
            sys.exit("option 4: the LP flags other than stopstate_x no longer fill the data pins")
        legal = [(c, s) for c, s in CODES4 if s is not None]
        if (set(FLAG_WORDS) != set(GROUPS["dl_hs"] + GROUPS["dl_skew"]) or len(legal) != len(HS_STATES) + 1
                or sorted(c for c, _ in CODES4) != [f"{i:0{CODE_W4}b}" for i in range(2 ** CODE_W4)]
                or any((c[0] == "1") != ("rxvalidhs_x" in s) for c, s in legal)):
            sys.exit("option 4: the code no longer matches the HS flags")
        clock, lane, spi = w["cl_clk"] + w["rst"], w["dl_data"] + CODE_W4 + 1, SPI_PINS  # 1: stopstate_x
    else:
        clock = w["cl_clk"] + w["cl_rt"] + w["rst"]
        lp = w["dl_lp"] + (w["dl_err"] if opt == 1 else 0)
        hs = {1: w["dl_data"] + w["dl_hs"], 2: w["dl_data"] + CODE_W, 3: -(-(w["dl_data"] + CODE_W) // 2)}[opt]
        lane, spi = hs + lp, SPI_PINS
    return clock, lane, spi, clock + LANES * lane + spi, lp


class Fig:
    """One single-page drawio figure built from boxes, containers, texts and edges."""

    def __init__(self, name, did):
        self.name = name
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
        return self.vertex(cid, value, BOX.format(fill=fill), x, y, w, h)

    def cont(self, cid, value, x, y, w, h, align="left"):
        return self.vertex(cid, value, CONT.format(align=align), x, y, w, h)

    def text(self, cid, value, x, y, w, h, align="left"):
        return self.vertex(cid, value, TEXT.format(align=align), x, y, w, h)

    def _port(self, cid, px, py):
        x, y, w, h = self.rect[cid]
        if not (x <= px <= x + w and y <= py <= y + h):
            raise ValueError(f"{self.name}: port ({px},{py}) outside {cid} {self.rect[cid]}")
        return round((px - x) / w, 4), round((py - y) / h, 4)

    def edge(self, cid, value, style, src, p_src, dst, p_dst, points=(), off=(0, -14), pos=0.0):
        """Edge from point p_src on the border of src to p_dst on the border of dst.

        pos places the label along the path (-1 at the source, 0 in the middle, 1 at the target),
        off shifts it in pixels.
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

    def wire(self, cid, value, style, p0, p1, off=(0, -14), pos=0.0):
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
        """Free line: pad wires, rails and legend keys (the same form as in the HAS figures)."""
        cell = self._cell(cid, "", style + "edgeStyle=none;", edge="1")
        geo = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(geo, "mxPoint", x=str(x0), y=str(y0), **{"as": "sourcePoint"})
        ET.SubElement(geo, "mxPoint", x=str(x1), y=str(y1), **{"as": "targetPoint"})

    def pad(self, cid, x, y, size=28):
        """Pad glyph of HAS Figure 2-1: a square with both diagonals."""
        self.box(cid, "", x, y, size, size)
        self.line(cid + "_d1", CROSS, x, y, x + size, y + size)
        self.line(cid + "_d2", CROSS, x + size, y, x, y + size)

    def legend(self, x, y, w, fills, lines, col_w):
        self.vertex("leg_frame", "", BOX.format(fill="none"), x, y, w, 130)
        self.text("leg_title", "<b>Legend</b>", x + 10, y + 4, 100, 32)
        for i, (fill, label) in enumerate(fills):
            xx = x + 10 + i * col_w
            self.box(f"leg_f{i}", "", xx, y + 46, 40, 24, fill)
            self.text(f"leg_ft{i}", label, xx + 48, y + 40, col_w - 56, 36)
        for i, (style, label) in enumerate(lines):
            xx = x + 10 + i * col_w
            self.line(f"leg_k{i}", style, xx, y + 102, xx + 40, y + 102)
            self.text(f"leg_kt{i}", label, xx + 48, y + 84, col_w - 56, 36)

    def write(self):
        ET.indent(self.mx, space="  ")
        xml = ET.tostring(self.mx, encoding="unicode") + "\n"
        xml.encode("ascii")  # rule 9 of the figure rules: ASCII-only XML
        path = os.path.join(HERE, self.name + ".drawio")
        with open(path, "w", encoding="ascii") as f:
            f.write(xml)
        return path


def label_pos(x_src, x_dst, x_lo, x_hi):
    """pos that centres the label of a horizontal edge from x_src to x_dst between x_lo and x_hi."""
    mid, half = (x_src + x_dst) / 2, abs(x_dst - x_src) / 2
    return round(((x_lo + x_hi) / 2 - mid) / half * (1 if x_dst > x_src else -1), 3)


def fig_top(opt):
    """D-PHY RX top: pins, AFE, ftel_dphy_rx and the PPI on GPIO pins, one row per lane."""
    name, did, title = OPTIONS[opt]
    w, rows = ppi_counts(), ppi_table()
    clock_pins, lane_pins, spi_pins, total, lp_pins = pins(opt)
    lpdt = LANES * w["lpdt"]
    flags = sum(w[g] for g in ("dl_hs", "dl_skew", "dl_lp", "dl_err", "dl_slow", "dl_clkesc"))
    # the options count their flags out of the same sets: the HS flags and the LP flags of a lane
    hs_names = GROUPS["dl_hs"] + GROUPS["dl_skew"]
    lp_names = GROUPS["dl_lp"] + GROUPS["dl_err"] + GROUPS["dl_slow"]
    hs_all, lp_all = (sum(rows[n][1] for n in names) for names in (hs_names, lp_names))
    gx = {0: 1940, 4: 2200}.get(opt, 2060)  # x of the GPIO pins
    ax, aw = 1830, 160                       # chip-top encoders and DDR outputs (options 2 and 3)
    f = Fig(name, did)
    f.vertex("frame", title.format(total=total), FRAME, 140, 0, 1490, 1020)
    f.text("t_pins", "<b>MIPI pins</b>", 0, 110, 130, 30, align="center")
    f.text("t_gpio", "<b>GPIO pins</b><br>(PPI)" if opt == 0 else "<b>GPIO pins</b>", gx - 50, 95, 200, 56,
           align="center")
    f.cont("afe", "<b>AFE</b> (analog)", 160, 60, 225, 830)
    f.cont("dig", "<b>ftel_dphy_rx</b> (digital D-PHY)", 700, 60, 910, 945)
    f.cont("n1", "<b>AFE Adapter</b>", 715, 95, 295, 795)
    f.box("big", "<b>Lane control and<br>HS datapath</b><br>line-state FSMs, sync search,<br>EoT, timers, PPI output",
          1270, 160, 320, 720)
    if opt >= 2:
        f.text("t_top", "<b>chip top</b>", *((1780, 110, 170, 30) if opt == 4 else (ax, 110, aw, 30)), align="center")
    lanes = [("clock lane", "C", None)] + [(f"data lane {i}", f"D{i}", i) for i in range(LANES)]
    for r, (lane_title, pin, lane) in enumerate(lanes):
        y = 160 + 150 * r
        cl = lane is None
        s = "c" if cl else str(lane)
        named = r <= 1  # names on the clock lane and data lane 0 only

        def lbl(text):
            return text if named else ""

        # pins: pad glyphs, wires and the rail of the lane pair (as in HAS Figure 2-1)
        f.text(f"t_{s}p", f"{pin}p", 0, y + 36, 60, 28, align="right")
        f.text(f"t_{s}n", f"{pin}n", 0, y + 72, 60, 28, align="right")
        f.pad(f"pad_{s}p", 66, y + 36)
        f.pad(f"pad_{s}n", 66, y + 72)
        f.line(f"w_{s}p", WIRE, 94, y + 50, 118, y + 50)
        f.line(f"w_{s}n", WIRE, 94, y + 86, 118, y + 86)
        f.line(f"rail_{s}", RAIL, 118, y + 35, 118, y + 100)
        f.line(f"tap_{s}h", WIRE, 118, y + 35, 185, y + 35)
        f.line(f"tap_{s}l", WIRE, 118, y + 100, 185, y + 100)
        # AFE of the lane, AFE Adapter (HAS Block No. 1) of the lane, GPIO pins of the lane
        f.box(f"hs_{s}", f"<b>{lane_title}</b><br>HS-RX + RT", 185, y, 175, 70, GREY)
        f.box(f"lp_{s}", "LP-RX", 185, y + 80, 175, 40, GREY)
        f.box(f"n1h_{s}", "byte clock, /4" if cl else "samplers, 1:8 deserializer", 730, y, 265, 42, PURPLE)
        f.box(f"n1l_{s}", "LP path, clock activity,<br>AFE enables" if cl else "LP path, AFE enables",
              730, y + 50, 265, 70, BLUE)
        f.box(f"gpio_{s}", f"{clock_pins if cl else lane_pins} pins", gx, y, 100, 120)
        pre, sfx = ("afe_cl_", "") if cl else ("afe_", "_x")
        # AFE interface (HAS Table 5-2)
        f.edge(f"a_{s}_hs", lbl("afe_cl_hs_clk" if cl else "afe_hs_bit_x"), E_CLK if cl else E_DATA,
               f"hs_{s}", (360, y + 21), f"n1h_{s}", (730, y + 21))
        f.edge(f"a_{s}_en", lbl(f"{pre}hs_en{sfx}, {pre}term_en{sfx}"), E_CTRL,
               f"n1l_{s}", (730, y + 62), f"hs_{s}", (360, y + 62))
        f.edge(f"a_{s}_lp", lbl(f"{pre}lp_dp{sfx}, {pre}lp_dn{sfx}"), E_CTRL,
               f"lp_{s}", (360, y + 100), f"n1l_{s}", (730, y + 100))
        # AFE Adapter (HAS Block No. 1) to lane control and HS datapath (HAS Blocks No. 2 to No. 7)
        f.edge(f"i_{s}_hs", lbl("rxbyteclkhs" if cl else "words [7:0]"), E_CLK if cl else E_DATA,
               f"n1h_{s}", (995, y + 21), "big", (1270, y + 21))
        f.edge(f"i_{s}_lp", lbl("LP state, clock active" if cl else "LP state"), E_CTRL,
               f"n1l_{s}", (995, y + 75), "big", (1270, y + 75))
        f.edge(f"i_{s}_en", lbl("cl_hs_en, cl_term_en" if cl else "hs_en_x, term_en_x"), E_CTRL,
               "big", (1270, y + 105), f"n1l_{s}", (995, y + 105))
        # PPI to the GPIO pins (HAS Table 5-1); labels centred between the frame and what they reach
        if opt == 0:
            f.edge(f"o_{s}_hs", lbl("rxbyteclkhs" if cl else "rxdatahs_x [7:0]"), E_CLK if cl else E_DATA,
                   "big", (1590, y + 21), f"gpio_{s}", (1940, y + 21), pos=0.11)
            f.edge(f"o_{s}_st", lbl("status flags, init_done" if cl else f"status flags ({flags})"), E_CTRL,
                   "big", (1590, y + 62), f"gpio_{s}", (1940, y + 62), pos=0.11)
            f.edge(f"o_{s}_in", lbl("cl_enable, phy_core_rst" if cl else "dl_enable_x, forcerxmode_x"), E_CTRL,
                   f"gpio_{s}", (1940, y + 100), "big", (1590, y + 100), pos=-0.11)
            continue
        to_gpio, to_chip_top = label_pos(1590, gx, 1630, gx), label_pos(1590, ax, 1630, ax)
        if cl:
            f.edge("o_c_hs", lbl("rxbyteclkhs"), E_CLK, "big", (1590, y + 21), "gpio_c", (gx, y + 21), pos=to_gpio)
            if opt != 4:  # option 4: the clock-lane flags go through the SPI
                f.edge("o_c_st", lbl("cl_stopstate, cl_ulpsclknot"), E_CTRL, "big", (1590, y + 62),
                       "gpio_c", (gx, y + 62), pos=to_gpio)
            f.edge("o_c_in", lbl("phy_core_rst"), E_CLK, "gpio_c", (gx, y + 100), "big", (1590, y + 100),
                   pos=label_pos(gx, 1590, 1630, gx))
            continue
        if opt == 4:
            # the HS flags go through the encoder to the code pins; the code also tells the multiplexer
            # whether a burst is on, so that the data pins carry the bytes in a burst and the LP flags
            # between bursts; stopstate_x goes straight to its pin
            ex, ey, ew, eh = 1800, y - 8, 112, 28  # encoder, input and code output at y + 6
            mx, my, mw, mh = 1880, y + 40, 44, 60  # multiplexer, inputs at my + 14 and my + 46
            lab = {x: label_pos(1590, x, 1630, 1790) for x in (ex, mx, gx)}
            f.box(f"enc_{s}", "encoder", ex, ey, ew, eh, ORANGE)
            f.mux(f"mux_{s}", mx, my, mw, mh)
            f.text(f"t_{s}_m1", "1", mx + 2, my + 3, 18, 22, align="center")
            f.text(f"t_{s}_m0", "0", mx + 2, my + 35, 18, 22, align="center")
            f.edge(f"o_{s}_fl", lbl(f"HS flags ({hs_all} of {hs_all})"), E_CTRL, "big", (1590, y + 6),
                   f"enc_{s}", (ex, y + 6), pos=lab[ex])
            f.wire(f"o_{s}_hs", lbl("rxdatahs_x [7:0]"), E_DATA, (1590, my + 14), (mx, my + 14), pos=lab[mx])
            f.wire(f"o_{s}_lp", lbl(f"LP flags ({lp_pins} of {lp_all})"), E_CTRL, (1590, my + 46), (mx, my + 46), pos=lab[mx])
            f.wire(f"o_{s}_sel", "", E_CTRL, (mx + mw // 2, ey + eh), (mx + mw // 2, my + 6))
            f.edge(f"o_{s}_cd", lbl(str(CODE_W4)), E_CTRL, f"enc_{s}", (ex + ew, y + 6), f"gpio_{s}", (gx, y + 6))
            f.wire(f"o_{s}_dp", lbl(str(w["dl_data"])), E_DATA, (mx + mw, my + mh // 2), (gx, my + mh // 2))
            f.edge(f"o_{s}_ss", lbl("stopstate_x"), E_CTRL, "big", (1590, y + 116), f"gpio_{s}", (gx, y + 116),
                   pos=lab[gx])
            if named:
                f.text(f"t_{s}_sel", "in burst", ex + ew + 2, ey + eh + 1, 84, 22)
                f.text(f"t_{s}_ss", str(lane_pins - w["dl_data"] - CODE_W4), gx - 50, y + 92, 30, 22, align="center")
            continue
        hs_flags = f"HS flags ({w['dl_hs']} of {hs_all})"
        if opt == 3:
            f.box(f"ad_{s}", f"encoder, DDR<br>{w['dl_data'] + CODE_W} -> {lane_pins - lp_pins}",
                  ax, y + 5, aw, 75, ORANGE)
            f.edge(f"o_{s}_hs", lbl("rxdatahs_x [7:0]"), E_DATA, "big", (1590, y + 21), f"ad_{s}", (ax, y + 21),
                   pos=to_chip_top)
            f.edge(f"o_{s}_fl", lbl(hs_flags), E_CTRL, "big", (1590, y + 62), f"ad_{s}", (ax, y + 62),
                   pos=to_chip_top)
            f.edge(f"o_{s}_ad", lbl(str(lane_pins - lp_pins)), E_DATA, f"ad_{s}", (ax + aw, y + 42),
                   f"gpio_{s}", (gx, y + 42))
        else:
            f.edge(f"o_{s}_hs", lbl("rxdatahs_x [7:0]"), E_DATA, "big", (1590, y + 21), f"gpio_{s}", (gx, y + 21),
                   pos=to_gpio)
            if opt == 2:
                f.box(f"ad_{s}", f"encoder {w['dl_hs']} -> {CODE_W}", ax, y + 44, aw, 36, ORANGE)
                f.edge(f"o_{s}_fl", lbl(hs_flags), E_CTRL, "big", (1590, y + 62), f"ad_{s}", (ax, y + 62),
                       pos=to_chip_top)
                f.edge(f"o_{s}_ad", lbl(str(CODE_W)), E_CTRL, f"ad_{s}", (ax + aw, y + 62), f"gpio_{s}", (gx, y + 62))
            else:
                f.edge(f"o_{s}_fl", lbl(hs_flags), E_CTRL, "big", (1590, y + 62), f"gpio_{s}", (gx, y + 62),
                       pos=to_gpio)
        f.edge(f"o_{s}_lp", lbl(f"LP flags ({lp_pins} of {lp_all})"), E_CTRL, "big", (1590, y + 100), f"gpio_{s}", (gx, y + 100),
               pos=to_gpio if opt == 1 else label_pos(1590, gx, 1630, ax))  # clear of the chip-top boxes
    if opt == 0:
        f.text("t_total", f"<b>{total} pins</b><br>+{lpdt} LPDT (tied 0)", 1890, 895, 200, 56, align="center")
    # configuration and the system clock
    f.box("n8", "<b>Configuration &amp; Status</b>", 730, 930, 400, 60, GREEN)
    f.edge("c_big", "timers", E_CFG, "n8", (1130, 960), "big", (1350, 880), points=[(1350, 960)], pos=-0.3)
    if opt == 0:
        f.text("t_cfg", "configuration bus (to be defined)", 730, 1040, 400, 30, align="center")
        f.edge("c_bus", "", E_CFG, "t_cfg", (930, 1040), "n8", (930, 990))
        f.text("t_core", "core_clk (200 MHz)", 1400, 1040, 220, 30, align="center")
        f.edge("k_core", "", E_CLK, "t_core", (1510, 1040), "big", (1510, 880))
    else:
        # SPI slave and registers at the chip top: configuration, enables and the PPI not on pins
        f.box("spi", "<b>SPI slave + registers</b> (chip top)<br>configuration, enables, slow PPI flags",
              730, 1060, 400, 70, GREEN)
        f.edge("c_spi", "", E_CFG, "spi", (930, 1060), "n8", (930, 990))
        f.edge("s_ppi", "slow PPI signals", E_BIDIR, "spi", (1130, 1095), "big", (1440, 880),
               points=[(1440, 1095)], pos=-0.4)
        f.text("t_core", "core_clk (200 MHz)", 1460, 1040, 220, 30, align="center")
        f.edge("k_core", "", E_CLK, "t_core", (1560, 1040), "big", (1560, 880))
        f.box("gpio_spi", f"{spi_pins} pins", gx, 1160, 100, 40)
        f.edge("o_spi", "SPI", E_BIDIR, "spi", (930, 1130), "gpio_spi", (gx, 1180), points=[(930, 1180)])
        f.text("t_total", f"<b>{total} pins</b>", gx - 50, 1210, 200, 30, align="center")
    f.text("t_note", "x: data lane 0 to 3<br>RT: switched HS termination", 160, 925, 520, 60)
    if opt == 0:
        f.legend(0, 1100, 2090,
                 [(GREY, "analog (AFE)"), (PURPLE, "DDR clock domain (afe_cl_hs_clk)"), (BLUE, "core_clk domain"),
                  (GREEN, "configuration"), (WHITE, "mixed clock domains, pins")],
                 [(E_DATA, "HS data (bus)"), (E_CTRL, "control / status"), (E_CLK, "clock / reset"),
                  (E_CFG, "configuration")], col_w=414)
        return f.write()
    def bits(sig):
        return f"{sig} [{rows[sig][1] - 1}:0]" if rows[sig][1] > 1 else sig

    hs_def = f"HS flags ({hs_all}): {', '.join(hs_names)}."
    lp_def = f"LP flags ({lp_all}): {', '.join(bits(n) for n in lp_names)}."
    notes = {
        1: f"{hs_def}<br>{lp_def}<br>Over SPI: the other HS and LP flags, the enables, forcerxmode_x, init_done, "
           "cl_ulpsactivenot, cl_rxclkactivehs. Not pinned: rxclkesc_x, LPDT outputs (tied 0).",
        2: f"{hs_def}<br>{lp_def}<br>HS flags on pins encoded in {CODE_W} bits: {len(HS_STATES)} legal combinations "
           "and 1 code for any other. Over SPI: as option 1, with erresc_x and errcontrol_x as counters.",
        3: f"{hs_def}<br>{lp_def}<br>As option 2. Data and code, {w['dl_data'] + CODE_W} bits per lane, on "
           f"{lane_pins - lp_pins} pins with both edges of rxbyteclkhs: each pin runs at line rate / 4, 375 Mb/s "
           "at 1500 Mb/s.",
        4: f"HS flags ({hs_all}): " + ", ".join(f"{word} = {sig}" for sig, word in FLAG_WORDS.items())
           + f".<br>{lp_def}<br>Over SPI: configuration, enables, init_done, clock-lane flags. Not pinned: "
           "rxclkesc_x, LPDT outputs (tied 0).",
    }
    f.text("t_opt", notes[opt], 0, 1045, 700, 190)
    if opt == 4:
        code_panel(f, 0, 1250)
        burst_panel(f, 700, 1250)
    fills = [(GREY, "analog (AFE)"), (PURPLE, "DDR clock domain (afe_cl_hs_clk)"), (BLUE, "core_clk domain")]
    fills += [(ORANGE, "rxbyteclkhs domain")] if opt >= 2 else []
    fills += [(GREEN, "configuration"), (WHITE, "mixed clock domains, pins")]
    ly, lw = (1590, 2300) if opt == 4 else (1260, 2210)
    f.legend(0, ly, lw, fills,
             [(E_DATA, "HS data (bus)"), (E_CTRL, "control / status"), (E_CLK, "clock / reset"),
              (E_CFG, "configuration")], col_w=lw // len(fills))
    return f.write()


def code_panel(f, x, y):
    """Option 4: the code on the code pins of a lane, the HS flags it stands for, and what the data pins
    carry with it."""
    f.text("t_code", f"<b>Code on the {CODE_W4} code pins</b>", x, y, 580, 30)
    n = ppi_counts()["dl_data"]
    lp8 = f"{n} LP flags"  # the LP flags other than stopstate_x, as many as the data pins
    table = [("<b>code</b>", "<b>HS flags High</b>", f"<b>{n} data pins</b>")]
    for code, sigs in CODES4:
        words = "any other" if sigs is None else ", ".join(FLAG_WORDS[s] for s in sigs) or "none"
        carry = lp8 if sigs == [] else "byte" if sigs and "rxvalidhs_x" in sigs else "-"
        table.append((code, words, carry))
    for i, row in enumerate(table):
        cx = x
        for j, (cw, val) in enumerate(zip((80, 330, 170), row)):
            fill = {lp8: BLUE, "byte": ORANGE}.get(val, WHITE)
            f.box(f"tc_{i}_{j}", val, cx, y + 35 + 30 * i, cw, 30, fill)
            cx += cw


def burst_panel(f, x, y):
    """Option 4: one data lane over one HS burst, on its data pins and its code pins (not to scale)."""
    f.text("t_burst", "<b>One data lane over one HS burst</b> (not to scale)", x, y, 780, 30)
    n = ppi_counts()["dl_data"]
    lp8 = f"{n} LP flags"
    f.text("t_bd", f"{n} data pins", x, y + 35, 140, 40)
    f.text("t_bc", f"{CODE_W4} code pins", x, y + 85, 140, 40)
    segs = [(lp8, "000"), ("-", "001"), ("B1", "101"), ("B2", "100"), ("...", "100"), ("Bn", "100"), (lp8, "000")]
    sx = x + 150
    for k, (data, code) in enumerate(segs):
        sw = 140 if data == lp8 else 70
        f.box(f"bd_{k}", data, sx, y + 35, sw, 40, BLUE if data == lp8 else ORANGE)
        f.box(f"bc_{k}", code, sx, y + 85, sw, 40, ORANGE)
        sx += sw
    f.text("t_rule", f"FPGA side: code 1xx -> the data pins are a byte; code 000 -> they are the {lp8}.",
           x, y + 135, 900, 30)


def check(paths):
    sys.path.insert(0, HAS_FIGURES)
    import check_figures as cf
    words = set(cf.IDENT.findall(open(SPEC, encoding="utf-8").read()))
    out = [v for p in paths for v in cf.check_drawio(p, words)]
    for code, where, msg in out:
        print(f"{code:8s} {where}: {msg}")
    print(f"check: {len(out)} violation(s) of F-XML, F-ASCII, F-FONT, F-SHAPE, F-NAME, F-STALE "
          f"in {len(paths)} figure(s)")
    return 1 if out else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="check the drawio sources and their renders")
    a = ap.parse_args()
    if a.check:
        sys.exit(check([os.path.join(HERE, OPTIONS[o][0] + ".drawio") for o in OPTIONS]))
    for o in OPTIONS:
        clock_pins, lane_pins, spi_pins, total, _ = pins(o)
        print(f"wrote {fig_top(o)}: clock lane {clock_pins}, data lane {lane_pins} x {LANES}, SPI {spi_pins}, "
              f"total {total} GPIO pins")
