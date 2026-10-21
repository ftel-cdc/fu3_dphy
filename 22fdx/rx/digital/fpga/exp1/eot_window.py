#!/usr/bin/env python3
"""Table of the eot_skip_bytes window (fpga/exp1/run_exp1.sh window, fpga/PLAN_TN1_FIX.md §5).

  eot_window.py [<dir>]      (default: fpga/work/exp1/window)

One row per rate, trail and junk; one column per eot_skip_bytes value, from the value of the configuration
model (config/validate_config.py) - 1 to + 2. A cell gives the skip value,
then "0" when no burst had trailer bytes, "<max> (<bursts>/<all>)" when some had, or "LOST <bursts>/<all>"
when the payload of a burst did not arrive intact.
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
CONFIG = os.path.join(os.path.dirname(FPGA), 'config')
sys.path.insert(0, CONFIG)
import validate_config as vc  # noqa: E402

NAME = re.compile(r'W_(\d+)_(min|max)_n(\d+)_s(\d+)$')
LINE = re.compile(r'^A \S+: \d+ lane\(s\), (\d+)/(\d+) bursts carry the payload sent, trailer bytes (\S+)'
                  r' \(in (\d+) bursts\)', re.M)


def cell(path):
    m = LINE.search(open(path).read())
    if not m:
        return 'no result'
    ok, tot, span, n_tr = int(m[1]), int(m[2]), m[3], int(m[4])
    if ok < tot:
        return f'LOST {tot - ok}/{tot}'
    return '0' if n_tr == 0 else f'{span.split("..")[-1]} ({n_tr}/{tot})'


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FPGA, 'work', 'exp1', 'window')
    with open(vc.YAML_DEFAULT, 'rb') as f:
        model = vc.Model(vc.yaml.safe_load(f.read()))
    runs = {}
    for c in glob.glob(os.path.join(d, 'W_*', 'check.txt')):
        m = NAME.match(os.path.basename(os.path.dirname(c)))
        if m:
            runs[(int(m[1]), m[2], int(m[3]), int(m[4]))] = cell(c)
    print('| Rate (Mb/s) | Trail | Junk (ns) | model - 1 | model | model + 1 | model + 2 |')
    print('|---|---|---|---|---|---|---|')
    for r, t, n in sorted({k[:3] for k in runs}, key=lambda k: (k[0], k[1] == 'max', k[2])):
        s = model.eot_skip(r)
        cols = [f'{v}: {runs[(r, t, n, v)]}' if (r, t, n, v) in runs else '-' for v in range(s - 1, s + 3)]
        print(f'| {r} | {t} | {n} | ' + ' | '.join(cols) + ' |')


if __name__ == '__main__':
    main()
