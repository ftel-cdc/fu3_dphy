#!/usr/bin/env python3
# Vendored from ftel_doc_kit 1.0.1 (skills/ftel-waveform/scripts/render_wave.py); edit the kit, then run kit.py vendor.
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
# Description     : Render WaveJSON (.json5) timing diagrams to .svg + .png.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-09-29   0.1        Ho Khanh Linh Initial creation (ftel_dphy_rx).
# 2026-11-02   1.0        Ho Khanh Linh Moved into ftel_doc_kit: environment variable
#                                       FTEL_WAVEDROM_CLI (FTEL_DPHY_RX_WAVEDROM_CLI still read);
#                                       Chrome runs without LD_LIBRARY_PATH and LD_PRELOAD.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Render WaveJSON (.json5) timing diagrams to .svg + .png.

Pipeline (skill ftel-waveform of ftel_doc_kit; first built for ftel_intctl): wavedrom-cli -> SVG, then
chrome --headless --screenshot -> PNG (@2x), with the offline Chrome flags of render_drawio.py.
wavedrom-cli is pinned (WAVEDROM_CLI_VERSION), so a render does not change when npm publishes a new
release. The render is offline: a wavedrom-cli of the pinned version is taken from
$FTEL_WAVEDROM_CLI (path of wavedrom-cli.js) or from the npx cache (~/.npm/_npx); npx
(network, first install only) is the fallback. The SVG records the sha256 of its .json5 source and
the wavedrom-cli and wavedrom versions, which check_figures.py uses to find stale renders.

Usage: render_wave.py <in.json5> [<in.json5> ...]
Env:   CHROME                      chrome binary (default: google-chrome)
       FTEL_WAVEDROM_CLI           path of a local wavedrom-cli.js of the pinned version (the older
                                   name FTEL_DPHY_RX_WAVEDROM_CLI is read too)
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

WAVEDROM_CLI_VERSION = "3.2.0"
CHROME = os.environ.get("CHROME", "google-chrome")
CHROME_ARGS = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
               "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>"]
# Chrome must not inherit a library path set by the wrapper of another tool (the python3 of an EDA
# suite, for one): a foreign libpango or libharfbuzz makes it exit with a symbol lookup error.
CHROME_ENV = {k: v for k, v in os.environ.items() if k not in ("LD_LIBRARY_PATH", "LD_PRELOAD")}


def package_version(pkg_dir):
    try:
        return json.load(open(os.path.join(pkg_dir, "package.json"), encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


def wavedrom_cli():
    """(command, version stamp) of the pinned wavedrom-cli: a local copy first, npx otherwise."""
    candidates = [os.environ.get(n, "") for n in ("FTEL_WAVEDROM_CLI", "FTEL_DPHY_RX_WAVEDROM_CLI")]
    candidates += sorted(glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/wavedrom-cli/wavedrom-cli.js")))
    for js in candidates:
        cli_dir = os.path.dirname(js)
        if js and os.path.isfile(js) and package_version(cli_dir) == WAVEDROM_CLI_VERSION:
            engine = package_version(os.path.join(os.path.dirname(cli_dir), "wavedrom"))
            return ["node", js], f"wavedrom-cli@{WAVEDROM_CLI_VERSION} wavedrom@{engine}"
    return ["npx", "-y", f"wavedrom-cli@{WAVEDROM_CLI_VERSION}"], f"wavedrom-cli@{WAVEDROM_CLI_VERSION}"


def render(src):
    base = os.path.splitext(src)[0]
    cli, version = wavedrom_cli()
    subprocess.run(cli + ["-i", src, "-s", base + ".svg"], check=True, timeout=600)
    svg = open(base + ".svg", encoding="utf-8").read()
    m = re.search(r'width="(\d+)"[^>]*viewBox', svg) or re.search(r'width="(\d+)"', svg)
    w, h = int(m.group(1)), int(re.search(r'height="(\d+)"', svg).group(1))
    digest = hashlib.sha256(open(src, "rb").read()).hexdigest()
    stamp = (f"<!-- rendered by render_wave.py: source={os.path.basename(src)} "
             f"sha256={digest} {version} -->")
    svg = re.sub(r"(<svg[^>]*>)", lambda t: t.group(1) + stamp, svg, count=1)
    open(base + ".svg", "w", encoding="utf-8").write(svg)
    print(f"[render] svg  : {base}.svg ({w}x{h}, {version})")
    subprocess.run(CHROME_ARGS + ["--hide-scrollbars", "--force-device-scale-factor=2",
                                  f"--window-size={w + 8},{h + 8}", f"--screenshot={base}.png",
                                  f"file://{os.path.abspath(base)}.svg"],
                   capture_output=True, text=True, timeout=120, check=True, env=CHROME_ENV)
    print(f"[render] png  : {base}.png ({(w + 8) * 2}x{(h + 8) * 2} @2x)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for src in sys.argv[1:]:
        render(os.path.abspath(src))


if __name__ == "__main__":
    main()
