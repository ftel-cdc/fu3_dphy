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
# Created Date    : 2026-10-15
# Description     : Summarize Vivado block designs (.bd JSON) without opening them in Vivado.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-15   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Summarize Vivado block designs (.bd JSON) without opening them in Vivado.

Useful for a design in a directory we may not write: open_bd_design needs write access to the IP
directories, so the .bd files are read as JSON instead.

For each .bd file it prints
  - every cell (hierarchical path, VLNV), and the user-set parameters of the cells whose VLNV matches
    --params (default: the PS, CSI-2, clocking, I2C, GPIO, debug and reset IPs);
  - the external ports and interface ports;
  - the address segments (master address space, slave segment, offset, range);
  - the nets attached to the cells whose name matches --nets-of (default: the CSI-2 subsystem).

Usage: bd_summary.py [--params REGEX] [--nets-of REGEX] file.bd [file.bd ...]
"""
import argparse
import json
import re

DEFAULT_PARAMS = r"versal_cips|ps_wizard|mipi_csi2_rx|clk_wiz|axi_iic|axi_gpio|axis_ila|axis_vio|ila|vio|proc_sys_reset"
DEFAULT_NETS_OF = r"csi"


def walk(components, prefix=""):
    """Yield (path, component) for every cell, descending into hierarchical cells."""
    for name, comp in components.items():
        path = f"{prefix}/{name}"
        yield path, comp
        if "components" in comp:
            yield from walk(comp["components"], path)


def param_value(p):
    return p.get("value", "") if isinstance(p, dict) else str(p)


def summarize(path, params_re, nets_re):
    with open(path) as fh:
        design = json.load(fh)["design"]
    name = design.get("design_info", {}).get("design_name", path)
    print(f"=== BD {name} ({path})")

    for cell, comp in walk(design.get("components", {})):
        vlnv = comp.get("vlnv", "(hierarchy)")
        print(f"cell {cell} {vlnv}")
        if re.search(params_re, vlnv):
            for pname, pval in sorted(comp.get("parameters", {}).items()):
                print(f"  param {pname} = {param_value(pval)}")

    for pname, port in sorted(design.get("ports", {}).items()):
        print(f"port {pname} {port.get('direction', '?')} type={port.get('type', '')}")
    for pname, port in sorted(design.get("interface_ports", {}).items()):
        print(f"intf_port {pname} {port.get('mode', '?')} {port.get('vlnv_bus_definition', port.get('vlnv', ''))}")

    def print_addressing(owner, addressing):
        for space, sdata in addressing.items():
            segs = sdata.get("address_spaces", sdata).get("segments", {}) if isinstance(sdata, dict) else {}
            for seg, s in segs.items():
                print(f"addr {owner}/{space} {seg} offset={s.get('address_block', '')} "
                      f"base={s.get('offset', '')} range={s.get('range', '')}")
    for cell, comp in walk(design.get("components", {})):
        if "addressing" in comp:
            print_addressing(cell, comp["addressing"])

    def print_nets(owner, container, everything):
        for kind in ("interface_nets", "nets"):
            for net, ndata in sorted(container.get(kind, {}).items()):
                ports = ndata.get("interface_ports", ndata.get("ports", []))
                if everything or any(re.search(nets_re, p.split("/")[0]) for p in ports):
                    print(f"{kind[:-1]} {owner}{net}: {' '.join(ports)}")
    print_nets("", design, False)
    # inside a hierarchical cell whose name matches, every net is of interest
    for cell, comp in walk(design.get("components", {})):
        if "components" in comp and re.search(nets_re, cell.rsplit("/", 1)[-1]):
            print_nets(f"{cell}/", comp, True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--params", default=DEFAULT_PARAMS, help="regex on VLNV: print the parameters of these cells")
    ap.add_argument("--nets-of", default=DEFAULT_NETS_OF, help="regex on cell name: print the nets of these cells")
    ap.add_argument("bd", nargs="+")
    args = ap.parse_args()
    for path in args.bd:
        summarize(path, args.params, args.nets_of)


if __name__ == "__main__":
    main()
