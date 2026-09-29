#!/usr/bin/env python3
"""Render WaveJSON (.json5) timing diagrams to .svg + .png.

Pipeline (after ip-dev ftel_intctl doc/figures/render_wave.py): wavedrom-cli via npx -> SVG,
then chrome --headless --screenshot -> PNG (@2x), with the offline Chrome flags of
render_drawio.py. wavedrom-cli is pinned (WAVEDROM_CLI), so a render does not change when npm
publishes a new release; npx needs network only the first time it installs that version.
The SVG records the sha256 of its .json5 source, which check_figures.py uses to find stale renders.

Usage: render_wave.py <in.json5> [<in.json5> ...]
Env:   CHROME  chrome binary (default: google-chrome)
"""
import hashlib
import os
import re
import subprocess
import sys

WAVEDROM_CLI = "wavedrom-cli@3.2.0"
CHROME = os.environ.get("CHROME", "google-chrome")
CHROME_ARGS = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
               "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>"]


def render(src):
    base = os.path.splitext(src)[0]
    subprocess.run(["npx", "-y", WAVEDROM_CLI, "-i", src, "-s", base + ".svg"], check=True, timeout=600)
    svg = open(base + ".svg", encoding="utf-8").read()
    m = re.search(r'width="(\d+)"[^>]*viewBox', svg) or re.search(r'width="(\d+)"', svg)
    w, h = int(m.group(1)), int(re.search(r'height="(\d+)"', svg).group(1))
    digest = hashlib.sha256(open(src, "rb").read()).hexdigest()
    stamp = (f"<!-- rendered by render_wave.py: source={os.path.basename(src)} "
             f"sha256={digest} {WAVEDROM_CLI} -->")
    svg = re.sub(r"(<svg[^>]*>)", lambda t: t.group(1) + stamp, svg, count=1)
    open(base + ".svg", "w", encoding="utf-8").write(svg)
    print(f"[render] svg  : {base}.svg ({w}x{h})")
    subprocess.run(CHROME_ARGS + ["--hide-scrollbars", "--force-device-scale-factor=2",
                                  f"--window-size={w + 8},{h + 8}", f"--screenshot={base}.png",
                                  f"file://{os.path.abspath(base)}.svg"],
                   capture_output=True, text=True, timeout=120, check=True)
    print(f"[render] png  : {base}.png ({(w + 8) * 2}x{(h + 8) * 2} @2x)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for src in sys.argv[1:]:
        render(os.path.abspath(src))


if __name__ == "__main__":
    main()
