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
# Created Date    : 2026-11-04
# Description     : Copy the runs of a bench aside, and compare them with the same runs made again.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-11-04   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Copy the runs of a bench aside, and compare them with the same runs made again.

A regression gate for a change that must not change what a bench captures (fpga/PLAN_EOT_NOWAIT.md §3,
fpga/PLAN_RENAME_FPT.md). A run is a folder with an args.txt; a folder without one whose subfolders have
one (exp1/window) is a group of runs.

  --copy: copies every run of <work> whose args.txt is newer than --since into <work>/<pre>/runs and
          writes the time of the copy into <work>/<pre>/.copied.
  default: compares every run of <work>/<pre>/runs with the run of the same name in <work>.
    - Every file of the copied run is compared, except --skip (logs with times, paths or memory sizes),
      or only --files.
    - A .csv file is compared without the columns that match --ignore-cols.
    - Another file that differs is compared again with --drop-lines removed from both sides and --subst
      applied to the copy (a name changed on purpose).
    - A run whose args.txt is not newer than .copied was not made again; it fails the gate unless
      --allow-stale, since its comparison would prove nothing.
  Prints one line per kind of difference; exit 1 on any difference, missing or stale run.

Usage: compare_runs.py <work> --pre <name> --copy --since 'YYYY-MM-DD HH:MM'
       compare_runs.py <work> --pre <name> [--files F ...] [--skip GLOB ...] [--ignore-cols REGEX]
                       [--drop-lines REGEX] [--subst OLD=NEW ...] [--allow-stale]
"""
import argparse
import csv
import datetime
import fnmatch
import os
import re
import shutil
import sys

SKIP = ['xsim.log', 'rss.txt', '*.vcd']


def run_dirs(root):
    out = []
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name.startswith('_pre') or name.startswith('build'):
            continue
        if os.path.exists(os.path.join(d, 'args.txt')):
            out.append(name)
        else:
            out += [os.path.join(name, s) for s in sorted(os.listdir(d))
                    if os.path.exists(os.path.join(d, s, 'args.txt'))]
    return out


def copy_runs(work, pre, since):
    t0 = datetime.datetime.strptime(since, '%Y-%m-%d %H:%M').timestamp()
    dst_root = os.path.join(work, pre, 'runs')
    if os.path.exists(dst_root):
        sys.exit(f'{dst_root} exists: not overwritten')
    runs = [r for r in run_dirs(work) if os.path.getmtime(os.path.join(work, r, 'args.txt')) > t0]
    for r in runs:
        shutil.copytree(os.path.join(work, r), os.path.join(dst_root, r), symlinks=True)
    with open(os.path.join(work, pre, '.copied'), 'w') as f:
        f.write(datetime.datetime.now().isoformat(timespec='seconds') + '\n')
    print(f'{work}: {len(runs)} runs newer than {since} copied to {dst_root}')


def csv_cmp(a, b, ignore):
    ra, rb = list(csv.reader(open(a))), list(csv.reader(open(b)))
    if not ra or not rb or ra[0] != rb[0]:
        return 'header differs', 0
    if len(ra) != len(rb):
        return f'{len(ra) - 1} vs {len(rb) - 1} rows', 0
    keep = [i for i, h in enumerate(ra[0]) if not (ignore and ignore.match(h))]
    bad = sum(1 for x, y in zip(ra[1:], rb[1:]) if [x[i] for i in keep] != [y[i] for i in keep])
    other = sum(1 for x, y in zip(ra[1:], rb[1:]) if x != y) - bad
    return (f'{bad} rows differ outside the ignored columns' if bad else None), other


def text_cmp(a, b, drop, subst):
    def lines(p, sub):
        out = []
        for line in open(p, errors='replace').read().splitlines():
            if sub:
                for old, new in subst:
                    line = line.replace(old, new)
            if not (drop and drop.search(line)):
                out.append(line)
        return out
    la, lb = lines(a, True), lines(b, False)
    if la == lb:
        return None
    n = sum(1 for x, y in zip(la, lb) if x != y) + abs(len(la) - len(lb))
    return f'{n} lines differ'


def compare(args):
    pre_root = os.path.join(args.work, args.pre, 'runs')
    stamp = os.path.join(args.work, args.pre, '.copied')
    t_copy = os.path.getmtime(stamp) if os.path.exists(stamp) else None
    ignore = re.compile(args.ignore_cols) if args.ignore_cols else None
    drop = re.compile(args.drop_lines) if args.drop_lines else None
    subst = [tuple(s.split('=', 1)) for s in args.subst]
    runs = run_dirs(pre_root)
    diffs, missing, stale, ignored_runs, files_cmp = [], [], [], 0, 0
    for r in runs:
        pre, now = os.path.join(pre_root, r), os.path.join(args.work, r)
        if not os.path.isdir(now):
            missing.append(r)
            continue
        if t_copy is not None and os.path.getmtime(os.path.join(now, 'args.txt')) <= t_copy:
            stale.append(r)
        names = args.files or sorted(f for f in os.listdir(pre) if os.path.isfile(os.path.join(pre, f))
                                     and not any(fnmatch.fnmatch(f, g) for g in args.skip))
        ignored = 0
        for f in names:
            a, b = os.path.join(pre, f), os.path.join(now, f)
            if not os.path.exists(a) and not os.path.exists(b):
                continue
            if not (os.path.exists(a) and os.path.exists(b)):
                diffs.append(f'{r}/{f}: present in one run only')
                continue
            files_cmp += 1
            if open(a, 'rb').read() == open(b, 'rb').read():
                continue
            if f.endswith('.csv'):
                msg, other = csv_cmp(a, b, ignore)
                ignored += other
            else:
                msg = text_cmp(a, b, drop, subst) if (drop or subst) else 'differs'
            if msg:
                diffs.append(f'{r}/{f}: {msg}')
        ignored_runs += ignored > 0
    note = '' if t_copy is not None else ' (no .copied stamp: not checked whether the runs were made again)'
    print(f'{args.work}: {len(runs)} runs, {files_cmp} files compared, {len(missing)} missing, '
          f'{len(stale)} not made again{note}, {len(diffs)} differences'
          + (f', ignored columns differ in {ignored_runs} runs' if ignore else ''))
    for m in missing:
        print('  missing:', m)
    for s in stale[:10]:
        print('  not made again:', s)
    for d in diffs[:40]:
        print('  ', d)
    return 1 if diffs or missing or (stale and not args.allow_stale) else 0


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('work')
    p.add_argument('--pre', required=True, help='name of the copy under <work>, e.g. _pre_rename')
    p.add_argument('--copy', action='store_true')
    p.add_argument('--since', help="with --copy: runs whose args.txt is newer, 'YYYY-MM-DD HH:MM'")
    p.add_argument('--files', nargs='+', help='compare only these files of each run')
    p.add_argument('--skip', nargs='+', default=SKIP, help=f'file patterns not compared (default {SKIP})')
    p.add_argument('--ignore-cols', help='regex of .csv columns not compared')
    p.add_argument('--drop-lines', help='regex of lines removed from both sides of a text file')
    p.add_argument('--subst', nargs='+', default=[], help='OLD=NEW applied to the copy of a text file')
    p.add_argument('--allow-stale', action='store_true', help='runs not made again do not fail the gate')
    args = p.parse_args()
    if args.copy:
        if not args.since:
            p.error('--copy needs --since')
        copy_runs(args.work, args.pre, args.since)
        return 0
    return compare(args)


if __name__ == '__main__':
    sys.exit(main())
