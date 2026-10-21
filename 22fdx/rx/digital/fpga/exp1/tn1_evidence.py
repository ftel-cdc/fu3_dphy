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

  tn1_evidence.py [<dir>]      (default: fpga/work/exp1)

Checks, one result line each:
  checker   fpga/tools/csi2_dump.py selftest passes: planted faults are found, a clean capture passes.
  decode    every PPI capture is decoded again by code written apart from csi2_dump.py (bursts = runs of
            rxactivehs, bytes = rxdatahs where rxvalidhs) and compared with truth.txt, in order and in time
            (each burst reaches the PPI after it left the pad, as long after it as the median of the capture,
            within half the smallest gap between bursts); the bursts with an intact payload, the trailer span
            and the verdict must equal check.txt. The decoder is first tried on synthetic captures: a clean one
            must pass, and one where a lane loses a burst and repeats another with the same payload (count and
            payloads still match in order) must show the three bursts out of time.
  runs      every run ended with "TB DONE OK", and truth.txt has one line per burst and lane.
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
import csv
import glob
import hashlib
import os
import random
import re
import statistics
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
IP = os.path.dirname(FPGA)   # the IP files sit in the folder that holds fpga/
sys.path.insert(0, os.path.join(IP, 'config'))
import validate_config as vc  # noqa: E402

FIELDS = (('hs_settle_cyc', 'HS_SETTLE'), ('clk_settle_cyc', 'CLK_SETTLE'), ('eot_skip_bytes', 'EOT_SKIP'),
          ('tinit_cyc', 'TINIT'))


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


def decode(path, truth, lanes, limit):
    """Bursts of one capture against the truth: (bursts with an intact payload, all bursts, trailer span, errors).
    Errors: X on a control signal, rxvalidhs or a flag outside a burst, a burst open at the end, a missing or
    extra burst, a payload difference, rxsynchs not seen once, errsoths or errsotsynchs, a trailer over limit,
    a burst out of time."""
    rows = list(csv.reader(open(path)))
    col = {name: i for i, name in enumerate(rows[0])}
    tcol = col['sim_time_ps']
    n_ok = n_all = errs = 0
    trailers, delays, gaps = [], [], []
    for lane in range(lanes):
        d, v, a = (col[f'dl{lane}_rxdatahs[7:0]'], col[f'dl{lane}_rxvalidhs'], col[f'dl{lane}_rxactivehs'])
        fl = {k: col[f'dl{lane}_{k}'] for k in ('rxsynchs', 'errsoths', 'errsotsynchs')}
        bursts, cur, prev_sync = [], None, '0'
        for r in rows[2:]:
            if any(r[c] not in '01' for c in (a, v, *fl.values())):
                errs += 1
                continue
            if r[a] == '1':
                if cur is None:
                    cur = {'bytes': bytearray(), 'times': [], 'sync': 0, 'err': 0}
                if r[v] == '1':
                    cur['bytes'].append(int(r[d], 16))
                    cur['times'].append(int(r[tcol]))
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
            got = bursts[k]['bytes']
            last = min(len(got), len(pay)) - 1     # the last byte of the burst within the payload length
            if last >= 0:
                # its byte period on the line: the sync byte and the payload span t0..t1
                delays.append(bursts[k]['times'][last] - (t0 + (last + 2) * (t1 - t0) / (len(pay) + 1)))
            if bytes(got[:len(pay)]) == pay:
                n_ok += 1
                trailers.append(len(got) - len(pay))
                errs += limit is not None and len(got) - len(pay) > limit
            else:
                errs += 1
            errs += (bursts[k]['sync'] != 1) + (bursts[k]['err'] > 0)
    if delays:
        # pairing in time: after it left the pad, and within half the smallest gap of the median delay
        mid = statistics.median(delays)
        half_gap = min(gaps) / 2 if gaps else float('inf')
        errs += sum(1 for x in delays if x <= 0 or abs(x - mid) > half_gap)
    span = f'{min(trailers)}..{max(trailers)}' if trailers else '-'
    return n_ok, n_all, span, errs


def decode_selftest():
    """decode() on synthetic captures from the selftest generator of csi2_dump.py, written in the layout of
    ppi_csv_mon.sv: eight bursts with the same payload on one lane; clean, it must find no error; with burst 5
    lost and burst 7 once more, the three bursts from 5 on are out of time. True when both hold."""
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
            cols = cd.synth_bursts({0: [(k, same, *t) for k, t in enumerate(times)]}, 1, rnd, faults, slot)
            names = [n.split('/')[-1] for n in cols]
            with open(path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(names)
                w.writerow(['Radix - UNSIGNED'] + ['HEX' if 'data' in n else 'BIN' for n in names[1:]])
                for vals in zip(*cols.values()):
                    w.writerow([f'{v:02x}' if 'data' in n else str(v) for n, v in zip(names, vals)])
            errs.append(decode(path, {0: [(same, *t) for t in times]}, 1, None)[3])
    return errs == [0, 3]


def sources_hash():
    """The hash run_exp1.sh keeps in build_*/src.sha: sha256sum of the RTL filelist sources and exp1/*.sv."""
    files = [IP + line.strip()[len('${FTEL_DPHY_RX_PATH}'):] for line in open(os.path.join(IP, 'logical', 'filelist.f'))
             if line.startswith('${FTEL_DPHY_RX_PATH}')]
    files += sorted(glob.glob(os.path.join(HERE, '*.sv')))
    text = ''.join(f'{hashlib.sha256(open(f, "rb").read()).hexdigest()}  {f}\n' for f in files)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def main():
    w = sys.argv[1] if len(sys.argv) > 1 else os.path.join(FPGA, 'work', 'exp1')
    with open(vc.YAML_DEFAULT, 'rb') as f:
        model = vc.Model(vc.yaml.safe_load(f.read()))
    runs = sorted(os.path.dirname(c) for c in glob.glob(os.path.join(w, '*', 'check.txt')))
    results = []

    def report(name, ok, text):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name:8s} {text}")

    st = subprocess.run([sys.executable, os.path.join(FPGA, 'tools', 'csi2_dump.py'), 'selftest'],
                        capture_output=True, text=True)
    report('checker', st.returncode == 0 and 'selftest: PASS' in st.stdout,
           'csi2_dump.py selftest (planted faults found, clean capture passes)')

    n_cap = same = 0
    bad = []
    n_done = n_truth = 0
    n_pair = n_same_fe = n_changes = 0
    fe_bad, fe_model = [], []
    afe_bad = []
    cfg_bad = []
    for run in runs:
        name = os.path.basename(run)
        args = open(os.path.join(run, 'args.txt')).read()
        tb = open(os.path.join(run, 'tb.txt')).read()
        check = open(os.path.join(run, 'check.txt')).read()
        truth = read_truth(os.path.join(run, 'truth.txt'))
        lanes = int(re.search(r'^TB START: NL (\d+)', tb, re.M)[1])
        stub = ' stub lane(s)' in args
        caps = ['ftel_ppi.csv'] if stub else ['xil_ppi.csv', 'ftel_ppi.csv']
        lim = re.search(r'^trailer limit .*: (\S+)$', args, re.M)   # runs before the limit existed have none
        limits = lim[1].split(',') if lim else ['-']
        limits = [None if x == '-' else int(x) for x in (limits if len(limits) == len(caps) else limits[-1:] * len(caps))]
        lines = re.findall(r'^[AB] \S+: \d+ lane\(s\), (\d+)/(\d+) bursts carry the payload sent, trailer bytes ([-0-9.]+)'
                           r'.*errors (\d+)$', check, re.M)
        for cap, lim, ref in zip(caps, limits, lines):
            n_ok, n_all, span, errs = decode(os.path.join(run, cap), truth, lanes, lim)
            n_cap += 1
            if (n_ok, n_all, span, errs == 0) == (int(ref[0]), int(ref[1]), ref[2], ref[3] == '0'):
                same += 1
            else:
                bad.append(f'{name}/{cap}: {n_ok}/{n_all} trailer {span} errors {errs}; check.txt {ref[0]}/{ref[1]}'
                           f' trailer {ref[2]} errors {ref[3]}')
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
    own = decode_selftest()
    report('decode', n_cap > 0 and same == n_cap and own,
           f'{same}/{n_cap} captures of {len(runs)} runs decoded again with the same result as check.txt;'
           f' decoder selftest {"PASS" if own else "FAIL"} (a clean synthetic capture passes, a lost and a'
           f' repeated burst with the same payload are found by their time)')
    for b in bad:
        print(f'          {b}')
    report('runs', n_done == n_truth == len(runs), f'{n_done}/{len(runs)} runs ended with TB DONE OK, {n_truth} with'
           ' one truth line per burst and lane')
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
    print(f"EVIDENCE: {'PASS' if all(results) else 'FAIL'} ({sum(results)}/{len(results)} checks)")
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
