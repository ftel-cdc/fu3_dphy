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
# Created Date    : 2026-10-20
# Description     : Evidence for the TN1 results (fpga/exp1/README.md §7): re-checks the outputs of
#                   run_exp1.sh in fpga/work/exp1.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-20   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Evidence for the TN1 results (fpga/exp1/README.md §7): re-checks the outputs of run_exp1.sh in fpga/work/exp1.

  tn1_evidence.py [<dir>]              the checks below over the runs in <dir> (default: fpga/work/exp1)
  tn1_evidence.py evselftest [<dir>]   the checks with one planted fault at a time (the runs of <dir> linked into a
                                       temporary folder, the one changed copied there): exactly the checks named
                                       for that fault must fail, and none without a fault

Checks, one result line each:
  checker   fpga/tools/csi2_dump.py selftest passes: planted faults are found, a clean capture passes.
  decode    every PPI capture is decoded again by code written apart from csi2_dump.py (bursts = runs of
            rxactivehs, bytes = rxdatahs where rxvalidhs) and compared with truth.txt, in order and in time
            (each burst reaches the PPI after it left the pad, as long after it as the median of the capture,
            within half the smallest gap between bursts), with the timing at the PPI of the HAS (Table A-2):
            rxsynchs High in one sample of each burst, in the cycle of the first byte for ftel_dphy_rx (C6) and one
            cycle before it for AMD's D-PHY, and each byte of a burst on all lanes within LANE_SPREAD samples (C10).
            The bursts with an intact payload, the trailer span and the verdict must equal check.txt. The decoder is
            first tried on synthetic captures: a clean one must pass; one where a lane loses a burst and repeats
            another with the same payload (count and payloads still match in order) must show the three bursts out
            of time; rxsynchs High for three cycles, rxsynchs with the third byte and a lane eight cycles later must
            each be found, and must pass without the timing checks.
  runs      every scenario was run (the 113 of run_exp1.sh all, their M_ runs, R-80, E1-6a, E1-6b and NEG-skew);
            every run ended with "TB DONE OK", and truth.txt has one line per burst and lane; check.txt passed in
            every run but NEG-skew, which must fail at the lane spread only: lane 3 is 7.5 byte times late at the
            pads, the payloads pass, every burst is wider than LANE_SPREAD on both receivers.
  front     both receivers had the same front end (fpga/PLAN_TN1_FAIR.md): in every run of both, the LP outputs
            of AMD's buffers and of the IBUFDS_DPHY buffers of ftel_dphy_rx were equal at every change, and
            ftel_dphy_rx sat behind those buffers unless the scenario set +AFE=model.
  afe       the AFE model saw no line-state error, and term_en was never late or missing.
  config    the run-time fields of ftel_dphy_rx printed by the testbench equal the configuration model at the
            rate (cfg_for_rate.py), or the values the scenario set.
  sources   the source hash of every build equals the current sources (RTL filelist and exp1/*.sv), so the
            results belong to the RTL in the repo.
  margin    (when run_exp1.sh window was run) with the minimum trail, eot_skip_bytes one above the model value
            loses no payload, and two above loses some, at every rate.
Exit status 1 when a check fails.
"""
import contextlib
import csv
import glob
import hashlib
import io
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
IP = os.path.dirname(FPGA)   # the IP files sit in the folder that holds fpga/
CSI2_DUMP = os.path.join(FPGA, 'tools', 'csi2_dump.py')
sys.path.insert(0, os.path.join(IP, 'config'))
import validate_config as vc  # noqa: E402

FIELDS = (('hs_settle_cyc', 'HS_SETTLE'), ('clk_settle_cyc', 'CLK_SETTLE'), ('eot_skip_bytes', 'EOT_SKIP'),
          ('tinit_cyc', 'TINIT'))
# the scenarios of run_exp1.sh, as it names them
RATES = (260, 400, 600, 800, 1000, 1200, 1440, 1500)
SCENARIOS = (['E1-1', 'E1-2a', 'E1-2b', 'E1-2c'] + [f'E1-3{s}' for s in 'abcdefg']
             + ['E1-4a', 'E1-4a_min', 'E1-4b', 'E1-4c', 'E1-4d', 'E1-4e']
             + [f'E1-5_{r}_{t}_j{j}_n{n}' for r in RATES for t in ('min', 'def', 'max') for j in (0, 1)
                for n in (0, 40)])
OTHERS = ('R-80', 'E1-6a', 'E1-6b')
NEGATIVE = ('NEG-skew',)
# timing at the PPI (HAS Table A-2): rxsynchs from the first byte per capture (C6), inter-lane byte divergence (C10)
SYNC_AT = {'xil_ppi.csv': -1, 'ftel_ppi.csv': 0}
LANE_SPREAD = 6


def read_truth(path):
    """{lane: [(payload, t0, t1) of burst 0, 1, ...]} from the truth file of the line generator (t0: start of
    the sync byte at the pad, t1: end of the last payload byte, ps)."""
    t = {}
    for line in open(path):
        f = line.split()
        if f and f[0] == 'B':
            t.setdefault(int(f[2]), []).append((int(f[1]), bytes.fromhex(f[6]) if len(f) > 6 else b'',
                                                int(f[4]), int(f[5])))
    return {lane: [(p, t0, t1) for _, p, t0, t1 in sorted(v)] for lane, v in t.items()}


def decode(path, truth, lanes, limit, sync_at=None, max_spread=None, stats=None):
    """Bursts of one capture against the truth: (bursts with an intact payload, all bursts, trailer span, errors).
    Errors: X on a control signal, rxvalidhs or a flag outside a burst, a burst open at the end, a missing or
    extra burst, a payload difference, rxsynchs not seen once (sync_at None) or not High in exactly one sample
    sync_at samples from the first byte (C6), errsoths or errsotsynchs, a trailer over limit, a burst out of time,
    a burst k whose bytes reach the PPI more than max_spread samples apart on the lanes (C10). stats, when given,
    gets the sync offsets seen, the widest spread and the bursts over max_spread."""
    rows = list(csv.reader(open(path)))
    col = {name: i for i, name in enumerate(rows[0])}
    tcol = col['sim_time_ps']
    n_ok = n_all = errs = 0
    trailers, delays, gaps, offsets, paired = [], [], [], [], []
    for lane in range(lanes):
        d, v, a = (col[f'dl{lane}_rxdatahs[7:0]'], col[f'dl{lane}_rxvalidhs'], col[f'dl{lane}_rxactivehs'])
        fl = {k: col[f'dl{lane}_{k}'] for k in ('rxsynchs', 'errsoths', 'errsotsynchs')}
        bursts, cur, prev_sync = [], None, '0'
        for n, r in enumerate(rows[2:]):
            if any(r[c] not in '01' for c in (a, v, *fl.values())):
                errs += 1
                continue
            if r[a] == '1':
                if cur is None:
                    cur = {'bytes': bytearray(), 'times': [], 'rows': [], 'syncs': [], 'sync': 0, 'err': 0}
                if r[v] == '1':
                    cur['bytes'].append(int(r[d], 16))
                    cur['times'].append(int(r[tcol]))
                    cur['rows'].append(n)
                if r[fl['rxsynchs']] == '1':
                    cur['syncs'].append(n)
                cur['sync'] += r[fl['rxsynchs']] == '1' and prev_sync == '0'
                cur['err'] += (r[fl['errsoths']] == '1') + (r[fl['errsotsynchs']] == '1')
            else:
                if cur is not None:
                    bursts.append(cur)
                    cur = None
                errs += r[v] == '1' or any(r[c] == '1' for c in fl.values())
            prev_sync = r[fl['rxsynchs']]
        errs += cur is not None
        sent = truth.get(lane, [])
        errs += len(bursts) != len(sent)
        gaps += [b[2] - a[2] for a, b in zip(sent, sent[1:])]
        for k, (pay, t0, t1) in enumerate(sent):
            n_all += 1
            if k >= len(bursts):
                continue
            b = bursts[k]
            got = b['bytes']
            last = min(len(got), len(pay)) - 1     # the last byte of the burst within the payload length
            if last >= 0:
                # its byte period on the line: the sync byte and the payload span t0..t1
                delays.append(b['times'][last] - (t0 + (last + 2) * (t1 - t0) / (len(pay) + 1)))
            if bytes(got[:len(pay)]) == pay:
                n_ok += 1
                trailers.append(len(got) - len(pay))
                errs += limit is not None and len(got) - len(pay) > limit
            else:
                errs += 1
            first = b['syncs'][0] - b['rows'][0] if len(b['syncs']) == 1 and b['rows'] else None
            if first is not None:
                offsets.append(first)
            errs += (b['sync'] != 1) if sync_at is None else (first != sync_at)
            errs += b['err'] > 0
        paired.append(bursts[:len(sent)])
    widest, over = [], 0
    for k in range(min(len(p) for p in paired)) if lanes > 1 else []:
        rws = [p[k]['rows'] for p in paired]   # burst k of every lane is one burst of the line
        n = min(len(x) for x in rws)
        if n:
            widest.append(max(max(x[j] for x in rws) - min(x[j] for x in rws) for j in range(n)))
            over += max_spread is not None and widest[-1] > max_spread
    errs += over
    if delays:
        # pairing in time: after it left the pad, and within half the smallest gap of the median delay
        mid = statistics.median(delays)
        half_gap = min(gaps) / 2 if gaps else float('inf')
        errs += sum(1 for x in delays if x <= 0 or abs(x - mid) > half_gap)
    if stats is not None:
        stats.update(offsets=sorted(set(offsets)), spread=max(widest, default=None), over=over, bursts=len(widest))
    span = f'{min(trailers)}..{max(trailers)}' if trailers else '-'
    return n_ok, n_all, span, errs


_DEC = {}    # decode results by capture (real path) and options: evselftest links the runs it does not change
_SELF = {}   # results that do not change while evselftest plants faults: the two selftests


def decode_cached(path, truth, lanes, limit, sync_at, max_spread, stats=None):
    key = (os.path.realpath(path), lanes, limit, sync_at, max_spread)
    if key not in _DEC:
        st = {}
        _DEC[key] = (decode(path, truth, lanes, limit, sync_at, max_spread, st), st)
    res, st = _DEC[key]
    if stats is not None:
        stats.update(st)
    return res


def write_capture(path, cols):
    """Columns of csi2_dump.py's synthetic captures in the layout of ppi_csv_mon.sv."""
    names = [n.split('/')[-1] for n in cols]
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(names)
        w.writerow(['Radix - UNSIGNED'] + ['HEX' if 'data' in n else 'BIN' for n in names[1:]])
        for vals in zip(*cols.values()):
            w.writerow([f'{v:02x}' if 'data' in n else str(v) for n, v in zip(names, vals)])


def decode_selftest():
    """decode() on synthetic captures from the selftest generator of csi2_dump.py, written in the layout of
    ppi_csv_mon.sv. Eight bursts with the same payload on one lane: clean, no error; with burst 5 lost and burst 7
    once more, the three bursts from 5 on are out of time. Four lanes: clean, no error with the timing checks;
    rxsynchs High for three cycles, rxsynchs with the third byte and lane 3 eight cycles later are found with
    them (one burst, one burst, every burst) and pass without them. True when all of it holds."""
    sys.path.insert(0, os.path.join(FPGA, 'tools'))
    import csi2_dump as cd
    rnd = random.Random(1)
    slot = 80
    same = bytes(rnd.randrange(256) for _ in range(3))
    times = [cd.synth_times(k, len(same), slot) for k in range(8)]
    errs = []
    with tempfile.TemporaryDirectory() as work:
        path = os.path.join(work, 'ftel_ppi.csv')
        for faults in (set(), {('drop', 0, 5), ('again', 0, 7)}):
            write_capture(path, cd.synth_bursts({0: [(k, same, *t) for k, t in enumerate(times)]}, 1, rnd, faults,
                                                slot))
            errs.append(decode(path, {0: [(same, *t) for t in times]}, 1, None)[3])
        lanes, lens = 4, (5, 64, 3, 9)
        truth = {i: [(k, bytes(rnd.randrange(256) for _ in range(n)), *cd.synth_times(k, n, slot))
                     for k, n in enumerate(lens)] for i in range(lanes)}
        mine = {i: [(p, t0, t1) for _, p, t0, t1 in v] for i, v in truth.items()}
        timing = []
        for faults, delay in ((set(), None), ({('sync3', 0, 1)}, None), ({('synclate', 1, 1)}, None), (set(), 3)):
            cols = cd.synth_bursts(truth, lanes, rnd, faults, slot)
            if delay is not None:
                cd.delay_lane(cols, delay, 8, rnd)
            write_capture(path, cols)
            timing.append((decode(path, mine, lanes, None, 0, LANE_SPREAD)[3], decode(path, mine, lanes, None)[3]))
    return errs == [0, 3] and timing == [(0, 0), (1, 0), (1, 0), (len(lens), 0)]


def sources_hash():
    """The hash run_exp1.sh keeps in build_*/src.sha: sha256sum of the RTL filelist sources and exp1/*.sv."""
    files = [IP + line.strip()[len('${FTEL_DPHY_RX_PATH}'):] for line in open(os.path.join(IP, 'logical', 'filelist.f'))
             if line.startswith('${FTEL_DPHY_RX_PATH}')]
    files += sorted(glob.glob(os.path.join(HERE, '*.sv')))
    text = ''.join(f'{hashlib.sha256(open(f, "rb").read()).hexdigest()}  {f}\n' for f in files)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def captures(args):
    """The PPI captures of a run: ftel_dphy_rx alone in a stub run, else AMD's receiver and ftel_dphy_rx."""
    return ['ftel_ppi.csv'] if ' stub lane(s)' in args else ['xil_ppi.csv', 'ftel_ppi.csv']


def evidence(w):
    """The checks over the runs in w ({check: passed}), printed one line each."""
    with open(vc.YAML_DEFAULT, 'rb') as f:
        model = vc.Model(vc.yaml.safe_load(f.read()))
    runs = sorted(os.path.dirname(c) for c in glob.glob(os.path.join(w, '*', 'check.txt')))
    results = {}

    def report(name, ok, text):
        results[name] = ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:8s} {text}")

    if 'checker' not in _SELF:
        st = subprocess.run([sys.executable, CSI2_DUMP, 'selftest'], capture_output=True, text=True)
        _SELF['checker'] = st.returncode == 0 and 'selftest: PASS' in st.stdout
        _SELF['decode'] = decode_selftest()
    report('checker', _SELF['checker'], 'csi2_dump.py selftest (planted faults found, clean capture passes)')

    n_cap = same = 0
    bad = []
    n_done = n_truth = 0
    n_pair = n_same_fe = n_changes = 0
    fe_bad, fe_model = [], []
    afe_bad = []
    cfg_bad = []
    verdict_bad, neg_text = [], {}
    offsets, widest = set(), []
    for run in runs:
        name = os.path.basename(run)
        args = open(os.path.join(run, 'args.txt')).read()
        tb = open(os.path.join(run, 'tb.txt')).read()
        check = open(os.path.join(run, 'check.txt')).read()
        truth = read_truth(os.path.join(run, 'truth.txt'))
        lanes = int(re.search(r'^TB START: NL (\d+)', tb, re.M)[1])
        stub = ' stub lane(s)' in args
        caps = captures(args)
        lim = re.search(r'^trailer limit .*: (\S+)$', args, re.M)   # runs before the limit existed have none
        limits = lim[1].split(',') if lim else ['-']
        limits = [None if x == '-' else int(x) for x in (limits if len(limits) == len(caps) else limits[-1:] * len(caps))]
        lines = re.findall(r'^[AB] \S+: \d+ lane\(s\), (\d+)/(\d+) bursts carry the payload sent, trailer bytes ([-0-9.]+)'
                           r'.*errors (\d+)$', check, re.M)
        neg = {}
        for cap, lim, ref in zip(caps, limits, lines):
            st = {}
            n_ok, n_all, span, errs = decode_cached(os.path.join(run, cap), truth, lanes, lim, SYNC_AT[cap],
                                                    LANE_SPREAD, st)
            n_cap += 1
            offsets |= {(cap, x) for x in st['offsets']}
            if st['spread'] is not None and name not in NEGATIVE:
                widest.append(st['spread'])
            if (n_ok, n_all, span, errs == 0) == (int(ref[0]), int(ref[1]), ref[2], ref[3] == '0'):
                same += 1
            else:
                bad.append(f'{name}/{cap}: {n_ok}/{n_all} trailer {span} errors {errs}; check.txt {ref[0]}/{ref[1]}'
                           f' trailer {ref[2]} errors {ref[3]}')
            if name in NEGATIVE:
                plain = decode_cached(os.path.join(run, cap), truth, lanes, lim, SYNC_AT[cap], None)[3]
                neg[cap] = (st['over'] == st['bursts'] > 0 and plain == 0,
                            f'{cap} {st["over"]}/{st["bursts"]} bursts wider than {LANE_SPREAD} (widest'
                            f' {st["spread"]}), {plain} errors without the lane spread')
        result = re.search(r'^RESULT: (PASS|FAIL)', check, re.M)
        if name in NEGATIVE:
            ok = bool(result) and result[1] == 'FAIL' and len(neg) == len(caps) and all(x for x, _ in neg.values())
            neg_text[name] = (ok, f'{name}: check.txt {result[1] if result else "no RESULT"}; '
                                  + '; '.join(t for _, t in neg.values()))
        elif not result or result[1] != 'PASS':
            verdict_bad.append(f'{name}: {result[0] if result else "no RESULT"}')
        done = re.search(r'^TB DONE\s+OK: NL (\d+), .*?, (\d+) bursts,', tb, re.M)
        n_done += done is not None
        n_truth += done is not None and int(done[1]) * int(done[2]) == sum(len(v) for v in truth.values())
        fe = re.search(r'^TB FRONT END: ftel_dphy_rx behind\s+(\S+)', tb, re.M)   # %s pads the shorter text
        want_fe = 'afe_model' if '+AFE=model' in args else 'IBUFDS_DPHY'
        if not fe or fe[1] != want_fe:
            fe_bad.append(f'{name}: behind {fe[1] if fe else "?"}, expected {want_fe}')
        if want_fe == 'afe_model':
            fe_model.append(name)
        if not stub:
            n_pair += 1
            chk = re.search(r'^TB FRONT END CHECK: .* differ at (\d+) of (\d+) changes', tb, re.M)
            if chk and chk[1] == '0' and int(chk[2]) > 0:
                n_same_fe += 1
                n_changes += int(chk[2])
            else:
                fe_bad.append(f'{name}: {chk[0] if chk else "no front-end check"}')
        afe = re.search(r'\((?:limit [\d.]+, )?(\d+) late, (\d+) missing\)', tb)
        state = re.search(r'AFE line-state errors (\d+)', tb)
        if not (afe and state and afe[1] == afe[2] == state[1] == '0'):
            afe_bad.append(name)
        rate = float(re.search(r'^\S+: (\d+) Mb/s', args, re.M)[1])
        cfg = re.search(r'^TB FTEL CFG: hs_settle_cyc (\d+), clk_settle_cyc (\d+), eot_skip_bytes (\d+), '
                        r'tinit_cyc (\d+)', tb, re.M)
        want = {'hs_settle_cyc': model.hs_settle(rate), 'clk_settle_cyc': model.clk_settle(),
                'eot_skip_bytes': model.eot_skip(rate), 'tinit_cyc': None}
        for i, (field, plus) in enumerate(FIELDS):
            m = re.search(rf'\+{plus}=(\d+)', args)
            exp = int(m[1]) if m else want[field]
            if exp is not None and int(cfg[i + 1]) != exp:
                cfg_bad.append(f'{name} {field} {cfg[i + 1]} (expected {exp})')
    own = _SELF['decode']
    seen = ', '.join(f'{c.split("_")[0]} {x:+d}' for c, x in sorted(offsets))
    report('decode', n_cap > 0 and same == n_cap and own,
           f'{same}/{n_cap} captures of {len(runs)} runs decoded again with the same result as check.txt (rxsynchs'
           f' from the first byte: {seen or "-"}; lane spread {min(widest, default="-")}..{max(widest, default="-")}'
           f' outside NEG-skew, at most {LANE_SPREAD}); decoder selftest {"PASS" if own else "FAIL"} (a clean'
           f' synthetic capture passes, a lost and a repeated burst with the same payload are found by their time,'
           f' the three faults of the tester are found)')
    for b in bad:
        print(f'          {b}')
    names = [os.path.basename(r) for r in runs]
    want_runs = [*SCENARIOS, *('M_' + s for s in SCENARIOS), *OTHERS, *NEGATIVE]
    missing = [n for n in want_runs if n not in names]
    neg_ok = all(neg_text.get(n, (False,))[0] for n in NEGATIVE)
    report('runs', n_done == n_truth == len(runs) and not missing and not verdict_bad and neg_ok,
           f'{len(runs)} runs ({len(SCENARIOS)} scenarios, their M_ runs, {", ".join(OTHERS + NEGATIVE)}:'
           f' {"all there" if not missing else "missing " + str(missing[:6])}); {n_done} ended with TB DONE OK,'
           f' {n_truth} with one truth line per burst and lane; check.txt PASS in'
           f' {len(runs) - len(verdict_bad) - len(neg_text)}/{len(runs) - len(neg_text)} runs outside NEG-skew'
           f' {verdict_bad[:4] if verdict_bad else ""}; '
           + '; '.join(t for _, t in neg_text.values()))
    n_m = sum(1 for r in fe_model if r.startswith('M_'))
    report('front', n_pair > 0 and not fe_bad,
           f'{n_same_fe}/{n_pair} runs of both receivers with equal LP outputs of the two front ends at every change'
           f' ({n_changes} changes); ftel_dphy_rx behind IBUFDS_DPHY in {len(runs) - len(fe_model)} runs, behind'
           f' afe_model in the {len(fe_model)} that set +AFE=model ({n_m} M_ runs and'
           f' {[r for r in fe_model if not r.startswith("M_")]})')
    for b in fe_bad:
        print(f'          {b}')
    report('afe', not afe_bad, f'{len(runs) - len(afe_bad)}/{len(runs)} runs without AFE line-state error or late or'
           f' missing term_en {afe_bad if afe_bad else ""}')
    report('config', not cfg_bad, f'{len(runs)} runs with the configuration of the model or of the scenario'
           f' {cfg_bad if cfg_bad else ""}')
    cur = sources_hash()
    builds = sorted(glob.glob(os.path.join(w, 'build_*', 'src.sha')))
    stale = [os.path.basename(os.path.dirname(b)) for b in builds
             if open(b).read().strip() not in (cur, '')]
    used = [b for b in builds if open(b).read().strip()]
    report('sources', bool(used) and not stale, f'{len(used) - len(stale)}/{len(used)} builds compiled from the'
           f' current sources (hash {cur}) {stale if stale else ""}')

    win = glob.glob(os.path.join(w, 'window', 'W_*', 'check.txt'))
    if win:
        loss = {}
        for c in win:
            m = re.match(r'W_(\d+)_min_n\d+_s(\d+)$', os.path.basename(os.path.dirname(c)))
            if m:
                a = re.search(r'^A .*?(\d+)/(\d+) bursts', open(c).read(), re.M)
                key = (int(m[1]), int(m[2]))
                loss[key] = loss.get(key, 0) + int(a[2]) - int(a[1])
        rates = sorted({r for r, _ in loss})
        ok = all(loss.get((r, model.eot_skip(r) + 1)) == 0 and loss.get((r, model.eot_skip(r) + 2), 0) > 0
                 for r in rates)
        report('margin', ok, f'minimum trail at {rates} Mb/s: model + 1 loses no payload, model + 2 loses some'
               f' (bursts lost at + 2: {[loss.get((r, model.eot_skip(r) + 2)) for r in rates]})')
    print(f"EVIDENCE: {'PASS' if all(results.values()) else 'FAIL'} ({sum(results.values())}/{len(results)} checks)")
    return results


# Faults of a PPI capture (ppi_csv_mon.sv layout: names, radix, samples), in the first burst of a lane with at
# least three bytes, or of the whole capture
def _lines(text):
    lines = text.split('\n')
    return lines, {n: i for i, n in enumerate(lines[0].split(','))}


def _burst(lines, col, lane):
    """Line numbers of the bytes and of rxsynchs in the first burst of the lane with three bytes or more."""
    a, v, s = (col[f'dl{lane}_{x}'] for x in ('rxactivehs', 'rxvalidhs', 'rxsynchs'))
    rows, syncs = [], []
    for i in range(2, len(lines) + 1):
        f = lines[i].split(',') if i < len(lines) else []
        if len(f) > a and f[a] == '1':
            rows += [i] if f[v] == '1' else []
            syncs += [i] if f[s] == '1' else []
        elif rows:
            if len(rows) >= 3:
                return rows, syncs
            rows, syncs = [], []
    return None, None


def _set(lines, i, c, value):
    f = lines[i].split(',')
    f[c] = value
    lines[i] = ','.join(f)


def sync_wide(text, lane=0):
    """rxsynchs High with the first three bytes (a fault a tester of the FPGA team planted, 2026-10-26)."""
    lines, col = _lines(text)
    rows, _ = _burst(lines, col, lane)
    for i in rows[:3]:
        _set(lines, i, col[f'dl{lane}_rxsynchs'], '1')
    return '\n'.join(lines)


def sync_late(text, lane=0):
    """rxsynchs with the third byte instead of the first (a fault the tester planted)."""
    lines, col = _lines(text)
    rows, syncs = _burst(lines, col, lane)
    for i in syncs:
        _set(lines, i, col[f'dl{lane}_rxsynchs'], '0')
    _set(lines, rows[2], col[f'dl{lane}_rxsynchs'], '1')
    return '\n'.join(lines)


def lane_late(text, lane=3, n=8):
    """Every column of the lane n samples later, its first samples repeated (a fault the tester planted)."""
    lines, col = _lines(text)
    cs = [i for name, i in col.items() if name.startswith(f'dl{lane}_')]
    rows = [r.split(',') for r in lines[2:] if r]
    new = [list(r) for r in rows]
    for k in range(len(rows)):
        for c in cs:
            new[k][c] = rows[max(k - n, 0)][c]
    return '\n'.join(lines[:2] + [','.join(r) for r in new]) + ('\n' if text.endswith('\n') else '')


def flip_capture(text, lane=0):
    """The lowest bit of the first byte of the first burst with three bytes inverted."""
    lines, col = _lines(text)
    rows, _ = _burst(lines, col, lane)
    c = col[f'dl{lane}_rxdatahs[7:0]']
    _set(lines, rows[0], c, f'{int(lines[rows[0]].split(",")[c], 16) ^ 1:02x}')
    return '\n'.join(lines)


def drop_burst(text, lane=0):
    """The first burst with three bytes gone: rxactivehs, rxvalidhs and rxsynchs Low over it."""
    lines, col = _lines(text)
    rows, _ = _burst(lines, col, lane)
    a = col[f'dl{lane}_rxactivehs']
    i = rows[0]
    while i > 2 and lines[i - 1].split(',')[a] == '1':
        i -= 1
    while i < len(lines) and lines[i] and lines[i].split(',')[a] == '1':
        for x in ('rxactivehs', 'rxvalidhs', 'rxsynchs'):
            _set(lines, i, col[f'dl{lane}_{x}'], '0')
        i += 1
    return '\n'.join(lines)


def check_again(run):
    """check.txt of a run made again by csi2_dump.py with the arguments run_exp1.sh recheck gives it."""
    args = open(os.path.join(run, 'args.txt')).read()
    tb = open(os.path.join(run, 'tb.txt')).read()
    caps = captures(args)
    lanes = re.search(r'^TB START: NL (\d+)', tb, re.M)[1]
    lim = re.search(r'^trailer limit .*: (\S+)$', args, re.M)[1]
    sat = ','.join(str(SYNC_AT[c]) for c in caps)
    cmd = [sys.executable, CSI2_DUMP, 'bursts', '--truth', os.path.join(run, 'truth.txt'), '--lanes', lanes,
           f'--max-trailer={lim}', f'--sync-at={sat}', f'--max-lane-spread={LANE_SPREAD}',
           *(os.path.join(run, c) for c in caps)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    with open(os.path.join(run, 'check.txt'), 'w') as f:
        f.write(out.stdout + out.stderr)


EV_FAULTS = (   # (fault, entry of the folder, file, change of its text, check.txt made again, checks that must fail)
    ('none', None, None, None, False, []),
    ('rxsynchs High for three cycles', 'E1-1', 'ftel_ppi.csv', sync_wide, False, ['decode']),
    ('rxsynchs with the third payload byte', 'E1-1', 'ftel_ppi.csv', sync_late, False, ['decode']),
    ('lane 3 eight cycles later', 'E1-1', 'ftel_ppi.csv', lane_late, False, ['decode']),
    ('rxsynchs High for three cycles, checked again by csi2_dump.py', 'E1-1', 'ftel_ppi.csv', sync_wide, True,
     ['runs']),
    ('rxsynchs with the third payload byte, checked again by csi2_dump.py', 'E1-1', 'ftel_ppi.csv', sync_late, True,
     ['runs']),
    ('lane 3 eight cycles later, checked again by csi2_dump.py', 'E1-1', 'ftel_ppi.csv', lane_late, True, ['runs']),
    ('a payload bit of a capture', 'E1-1', 'ftel_ppi.csv', flip_capture, False, ['decode']),
    ('a burst missing from a capture', 'E1-1', 'xil_ppi.csv', drop_burst, False, ['decode']),
    ('a scenario failing in check.txt', 'E1-2a', 'check.txt', lambda s: s.replace('RESULT: PASS', 'RESULT: FAIL'),
     False, ['runs']),
    ('NEG-skew passing in check.txt', 'NEG-skew', 'check.txt', lambda s: s.replace('RESULT: FAIL', 'RESULT: PASS'),
     False, ['runs']),
    ('a run missing', 'E1-3a', None, None, False, ['runs']),
    ('a front-end difference', 'E1-1', 'tb.txt', lambda s: s.replace('differ at 0 of', 'differ at 1 of'), False,
     ['front']),
    ('a late term_en', 'E1-1', 'tb.txt', lambda s: s.replace('0 late, 0 missing', '1 late, 0 missing', 1), False,
     ['afe']),
    ('another eot_skip_bytes', 'E1-1', 'tb.txt', lambda s: s.replace('eot_skip_bytes 13', 'eot_skip_bytes 12'),
     False, ['config']),
    ('another sources hash of a build', 'build_1440_4l', 'src.sha', lambda s: '0000000000000000\n', False,
     ['sources']),
)


def evselftest(w):
    """evidence() with each fault of EV_FAULTS planted in turn: the entries of w (runs, builds, window) are linked
    into a temporary folder, the one changed is copied there (of a build only the file changed). True when every
    fault fails exactly its checks."""
    entries = sorted(os.listdir(w))
    ok_all = True
    for fault, entry, name, change, again, want in EV_FAULTS:
        with tempfile.TemporaryDirectory() as d:
            planted = change is None and entry is not None
            for e in entries:
                src = os.path.join(w, e)
                if e == entry and change is None:
                    continue                      # the run left out
                if e != entry:
                    os.symlink(src, os.path.join(d, e))
                    continue
                if os.path.exists(os.path.join(src, 'check.txt')):
                    shutil.copytree(src, os.path.join(d, e))
                else:
                    os.makedirs(os.path.join(d, e))
                    shutil.copy(os.path.join(src, name), os.path.join(d, e, name))
                path = os.path.join(d, e, name)
                text = open(path).read()
                new = change(text)
                planted = new != text
                with open(path, 'w') as f:
                    f.write(new)
                if again:
                    check_again(os.path.join(d, e))
            if entry is None:
                planted = True
            with contextlib.redirect_stdout(io.StringIO()):
                res = evidence(d)
        failing = sorted(k for k, ok in res.items() if not ok)
        ok = planted and failing == sorted(want)
        ok_all &= ok
        print(f"  {'ok  ' if ok else 'FAIL'} {fault}{'' if planted else ' (not planted)'}: failing checks"
              f" {failing}, expected {sorted(want)}")
    print(f"evselftest: {'PASS' if ok_all else 'FAIL'}")
    return ok_all


def main():
    a = sys.argv[1:]
    if a and a[0] == 'evselftest':
        return 0 if evselftest(a[1] if len(a) > 1 else os.path.join(FPGA, 'work', 'exp1')) else 1
    res = evidence(a[0] if a else os.path.join(FPGA, 'work', 'exp1'))
    return 0 if all(res.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
