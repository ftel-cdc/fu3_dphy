#!/usr/bin/env python3
"""Render .drawio files to standalone .svg + .png, offline, with a pinned drawio build.

Pipeline (after ip-dev ftel_intctl doc/figures/render_drawio.py):
  drawio XML -> HTML page embedding the drawio GraphViewer
  -> chrome --headless --dump-dom -> extract the rendered <svg> -> .svg
  -> chrome --headless --screenshot of the same page -> .png (@2x)

Differences from the ftel_intctl script (measurements: RTL_FLOW_PLAN.md, Track Doc, Doc0):
  1. viewer-static.min.js + stencils.min.js. viewer.min.js alone fetches mxElectrical.js and
     stencils/electrical/logic_gates.xml from viewer.diagrams.net at render time; offline, the
     logic gates and flip-flops of FTEL_DRAWIO_LIB_V1 then become empty rectangles. The page
     defines window.onDrawioViewerLoad, so the viewer does not draw on load;
     GraphViewer.processElements() runs once stencils.min.js has registered the stencil sets.
  2. Chrome sends every http(s) request to a dead proxy, so the render is offline whatever
     proxy the shell exports.
  3. A render fails when a page message reports a stencil or shape load error or names an
     http(s) URL: a missing glyph can no longer turn into a plain rectangle silently.
  4. The viewer files are pinned by drawio_lock.json (drawio version + sha256). They are taken
     from $FTEL_DPHY_RX_DRAWIO_DIR, from .drawio_cache/<version>/ beside this script (filled by
     --fetch), or from the VSCode extension hediet.vscode-drawio, in that order, and only when
     their sha256 matches the lock.
  5. The SVG records the sha256 of its .drawio source; check_figures.py uses it to find stale
     renders.
  6. The labels are HTML inside <foreignObject>. --dump-dom serializes them without the XHTML
     namespace, and a standalone SVG (markdown preview, <img>) then shows no text at all. The
     namespace is added back, and every render displays the SVG through <img> and compares it
     with the PNG (the check needs numpy and Pillow; without them it is reported as skipped).

Usage:
  render_drawio.py <in.drawio> [<in.drawio> ...]  write <base>.svg and <base>.png beside each input
  render_drawio.py --fetch     download the locked files from the drawio release tag (needs network)
  render_drawio.py --selftest  render selftest/ftel_lib_glyphs.drawio and require no differing
                               pixel against selftest/ftel_lib_glyphs.png
Env:
  FTEL_DPHY_RX_DRAWIO_DIR  directory that holds the locked files (optional)
  CHROME                   chrome binary (default: google-chrome)
Exit status: 0 on success, 1 on any lock, render or selftest failure.
"""
import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, "drawio_lock.json")
CHROME = os.environ.get("CHROME", "google-chrome")
CHROME_ARGS = [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
               "--enable-logging=stderr", "--v=0",
               "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=<-loopback>"]
LOAD_ERROR = re.compile(r"error in (getStencil|loadStencil)|Failed to load|net::ERR_|https?://")
# Standalone-SVG check (calibrated 2026-09-29 on the top-level figure: a correct SVG leaves at most
# 29 unmatched pixels per 40x40 tile, one missing "LP state" label about 250 per tile).
SVG_CHECK_RADIUS, SVG_CHECK_TILE, SVG_CHECK_LIMIT = 3, 40, 150
EXTENSION_DIRS = ("~/.vscode/extensions/hediet.vscode-drawio-*/drawio/src/main/webapp/js",
                  "~/.vscode-server/extensions/hediet.vscode-drawio-*/drawio/src/main/webapp/js")


def fail(msg):
    print(f"[render] ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_lock():
    return json.load(open(LOCK, encoding="utf-8"))


def resolve(lock):
    """Paths of the locked files, from the first source whose files all match the lock."""
    dirs = [os.environ["FTEL_DPHY_RX_DRAWIO_DIR"]] if os.environ.get("FTEL_DPHY_RX_DRAWIO_DIR") else []
    dirs.append(os.path.join(HERE, ".drawio_cache", lock["drawio_version"]))
    for pattern in EXTENSION_DIRS:
        dirs += sorted(glob.glob(os.path.expanduser(pattern)), reverse=True)
    for d in dirs:
        paths = {name: os.path.join(d, name) for name in lock["files"]}
        if all(os.path.isfile(p) and sha256(p) == lock["files"][n] for n, p in paths.items()):
            return paths
    fail(f"no source holds the drawio {lock['drawio_version']} files of drawio_lock.json "
         f"(checked: {', '.join(dirs)}). Run 'render_drawio.py --fetch' (needs network) "
         "or set FTEL_DPHY_RX_DRAWIO_DIR.")


def fetch(lock):
    dest = os.path.join(HERE, ".drawio_cache", lock["drawio_version"])
    os.makedirs(dest, exist_ok=True)
    for name, digest in lock["files"].items():
        part = os.path.join(dest, name + ".part")
        with urllib.request.urlopen(lock["url"] + name, timeout=300) as r, open(part, "wb") as f:
            shutil.copyfileobj(r, f)
        if sha256(part) != digest:
            os.unlink(part)
            fail(f"sha256 of {lock['url'] + name} does not match drawio_lock.json")
        os.replace(part, os.path.join(dest, name))
        print(f"[render] fetched {name} (drawio {lock['drawio_version']}, sha256 ok)")


def page_html(xml, files):
    cfg = json.dumps({"xml": xml, "page": 0, "highlight": "none", "lightbox": False,
                      "nav": False, "toolbar": None, "resize": False, "border": 0})
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{margin:0;background:#ffffff;}}</style></head><body>
<div class="mxgraph" style="border:none;" data-mxgraph="{html.escape(cfg)}"></div>
<script>window.onDrawioViewerLoad = function () {{}};</script>
<script src="file://{files['viewer-static.min.js']}"></script>
<script src="file://{files['stencils.min.js']}"></script>
<script>GraphViewer.processElements();</script>
</body></html>"""


def chrome(args, src):
    r = subprocess.run(CHROME_ARGS + args, capture_output=True, text=True, timeout=120)
    bad = [line for line in r.stderr.splitlines() if ":CONSOLE" in line and LOAD_ERROR.search(line)]
    if bad:
        fail(f"{src}: the viewer could not draw every shape offline:\n  "
             + "\n  ".join(line[:220] for line in bad[:5]))
    return r


def render(src, files, lock):
    base = os.path.splitext(src)[0]
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(page_html(open(src, encoding="utf-8").read(), files))
        page = f.name
    try:
        dom = chrome(["--virtual-time-budget=4000", "--dump-dom", f"file://{page}"], src).stdout
        m = re.search(r"<svg[^>]*>.*</svg>", dom, re.S)
        if not m:
            fail(f"no <svg> in the rendered DOM of {src}")
        svg = m.group(0)
        if "xmlns" not in svg[:200]:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg" '
                              'xmlns:xlink="http://www.w3.org/1999/xlink"', 1)
        # GraphViewer puts the size in style min-width/min-height; promote it to
        # width/height/viewBox so the SVG renders standalone.
        wm = re.search(r"min-width:\s*(\d+)px;\s*min-height:\s*(\d+)px", svg)
        if not wm:
            fail(f"svg of {src} has no min-width/height: {svg[:300]}")
        w, h = int(wm.group(1)), int(wm.group(2))
        svg = re.sub(r'(<svg[^>]*?)\s*style="[^"]*"',
                     rf'\1 width="{w}px" height="{h}px" viewBox="0 0 {w} {h}" '
                     rf'style="background-color:#ffffff;"', svg, count=1)
        # --dump-dom serializes HTML: self-close void elements, replace HTML-only entities, and
        # declare the XHTML namespace of the label markup inside every <foreignObject>.
        svg = re.sub(r"<(br|hr|img)([^>/]*)>", r"<\1\2/>", svg).replace("&nbsp;", "&#160;")
        svg = re.sub(r"(<foreignObject[^>]*>\s*<[a-zA-Z]+)(?![^>]*xmlns=)",
                     r'\1 xmlns="http://www.w3.org/1999/xhtml"', svg)
        stamp = (f"<!-- rendered by render_drawio.py: source={os.path.basename(src)} "
                 f"sha256={sha256(src)} drawio={lock['drawio_version']} -->")
        svg = re.sub(r"(<svg[^>]*>)", lambda t: t.group(1) + stamp, svg, count=1)
        open(base + ".svg", "w", encoding="utf-8").write(svg)
        print(f"[render] svg  : {base}.svg ({w}x{h})")
        chrome(["--hide-scrollbars", "--force-device-scale-factor=2", "--virtual-time-budget=4000",
                f"--window-size={w + 8},{h + 8}", f"--screenshot={base}.png", f"file://{page}"], src)
        if not os.path.isfile(base + ".png"):
            fail(f"chrome wrote no screenshot for {src}")
        print(f"[render] png  : {base}.png ({(w + 8) * 2}x{(h + 8) * 2} @2x)")
        check_svg(base, w, h, src)
    finally:
        os.unlink(page)


def check_svg(base, w, h, src):
    """Display the standalone SVG through <img> and require it to look like the PNG."""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        print("[render] WARNING: standalone-SVG check skipped (needs numpy and Pillow)")
        return
    with tempfile.TemporaryDirectory() as d:
        page = os.path.join(d, "img.html")
        shot = os.path.join(d, "img.png")
        open(page, "w", encoding="utf-8").write(
            f'<!DOCTYPE html><html><body style="margin:0;background:#ffffff">'
            f'<img src="file://{base}.svg" width="{w}" height="{h}"></body></html>')
        chrome(["--hide-scrollbars", "--force-device-scale-factor=2", f"--window-size={w + 8},{h + 8}",
                f"--screenshot={shot}", f"file://{page}"], src)
        a = np.asarray(Image.open(base + ".png").convert("L")) < 128
        b = np.asarray(Image.open(shot).convert("L")) < 128
    if a.shape != b.shape:
        fail(f"{src}: standalone SVG size {b.shape[::-1]} differs from the PNG {a.shape[::-1]}")

    def dilate(m, r=SVG_CHECK_RADIUS):
        out = np.zeros_like(m)
        rows, cols = m.shape
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                out[max(0, dy):rows + min(0, dy), max(0, dx):cols + min(0, dx)] |= \
                    m[max(0, -dy):rows + min(0, -dy), max(0, -dx):cols + min(0, -dx)]
        return out

    def worst_tile(mask, t=SVG_CHECK_TILE):
        rows, cols = mask.shape
        pad = np.zeros((-(-rows // t) * t, -(-cols // t) * t), dtype=bool)
        pad[:rows, :cols] = mask
        return int(pad.reshape(pad.shape[0] // t, t, pad.shape[1] // t, t).sum(axis=(1, 3)).max())

    # Text is laid out 1-2 px apart in the two renderings, so ink is compared with a tolerance:
    # a label missing on either side leaves hundreds of unmatched pixels in one tile.
    missing = worst_tile(a & ~dilate(b))
    extra = worst_tile(b & ~dilate(a))
    if max(missing, extra) > SVG_CHECK_LIMIT:
        fail(f"{src}: the standalone SVG does not show what the PNG shows (worst {SVG_CHECK_TILE}px tile: "
             f"{missing} px missing, {extra} px extra); labels may be lost")
    print(f"[render] svg check: standalone SVG matches the PNG (worst tile: {missing} px missing, "
          f"{extra} px extra, limit {SVG_CHECK_LIMIT})")


def selftest(files, lock):
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        fail("--selftest needs numpy and Pillow")
    src = os.path.join(HERE, "selftest", "ftel_lib_glyphs.drawio")
    golden = os.path.join(HERE, "selftest", "ftel_lib_glyphs.png")
    with tempfile.TemporaryDirectory() as d:
        copy = os.path.join(d, "ftel_lib_glyphs.drawio")
        shutil.copy(src, copy)
        render(copy, files, lock)
        a = np.asarray(Image.open(golden).convert("L"), dtype=np.int16)
        b = np.asarray(Image.open(os.path.join(d, "ftel_lib_glyphs.png")).convert("L"), dtype=np.int16)
    if a.shape != b.shape:
        fail(f"selftest: size {b.shape[::-1]} differs from the golden {a.shape[::-1]}")
    differing = int((np.abs(a - b) > 48).sum())
    exact = int((a != b).sum())
    print(f"[render] selftest: {differing} differing pixels (|delta| > 48), {exact} not bit-exact")
    if differing:
        fail("selftest: the render of the FTEL library glyphs differs from the golden image")
    print("[render] selftest PASS")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    lock = load_lock()
    if args == ["--fetch"]:
        fetch(lock)
        return
    files = resolve(lock)
    if args == ["--selftest"]:
        selftest(files, lock)
        return
    for src in args:
        render(os.path.abspath(src), files, lock)


if __name__ == "__main__":
    main()
