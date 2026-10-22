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
# Created Date    : 2026-10-22
# Description     : Checks of the TN2a runs (fpga/PLAN_TN2A.md §3.2, §6): the testbench-level verdict of a run,
#                   the pad decoder against the line generator, the evidence over all runs and the TX timing.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-22   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Checks of the TN2a runs (fpga/PLAN_TN2A.md) in fpga/work/exp2.

  tn2a_evidence.py tbcheck <run>      testbench-level verdict of one run (run_exp2.sh writes it to tbcheck.txt)
  tn2a_evidence.py padtruth <run>     truth.txt of the pad decoder against truth_gen.txt of the line generator
                                      (runs with +SRC=gen)
  tn2a_evidence.py selftest           tbcheck and padtruth on synthetic runs with planted faults
  tn2a_evidence.py evidence [<dir>]   the evidence of PLAN_TN2A.md §6 over the runs E2a-*, M_E2a-* and NEG-* in
                                      <dir> (default fpga/work/exp2)
  tn2a_evidence.py txtiming [<dir>]   the timing of the TX measured at the pads, per rate, and the limits of
                                      D-PHY v1.1
  tn2a_evidence.py evselftest [<dir>] evidence on the runs of <dir> with one planted fault at a time (links to
                                      the runs, the changed run copied into a temporary folder): exactly the
                                      checks named for that fault must fail, and none without a fault

tbcheck prints one line per item, then the verdict line TBRESULT:
  done      the run ended with TB DONE OK
  pads      the pad decoder found every lane burst given to the line (expected.txt) and no other one, each with
            its sync byte and all its bytes, the bytes equal to the bytes given (mismatches 0), and its line
            state equal to afe_model's at every change
  front     the LP outputs of AMD's buffers and of the buffers of ftel_dphy_rx were equal at every change after
            2.5 ps; the comparisons up to 2.5 ps (the pads of AMD's TX leave X at 1 ps) are printed by the
            testbench and shown here, not counted
  afe       afe_model saw no line-state error, and term_en was never late or missing
  tx        (source: AMD's TX) the TX finished every burst, and every lane burst left the stop state
  padtruth  (source: the line generator) truth.txt equals truth_gen.txt: the same lane bursts and bytes, the
            start of the sync byte (t0) and the end of the payload (t1) within 1 ps

evidence prints one line per check, then the verdict line EVIDENCE:
  checker   fpga/tools/csi2_dump.py selftest passes: planted faults are found, a clean capture passes
  decode    every PPI capture is decoded again by the decoder of exp1/tn1_evidence.py (written apart from
            csi2_dump.py) against truth.txt, with the same result as check.txt; that decoder's selftest passes
  runs      every scenario of PLAN_TN2A.md §5 was run, also behind afe_model (M_*), and both negative tests;
            every run ended with TB DONE OK with one truth line per burst and lane; every scenario passed
            check.txt and tbcheck.txt
  tx        in every run from AMD's TX the bytes at the pads equal the bytes given to the TX; in NEG-tx the byte
            sent inverted is the only mismatch, the only failing item of tbcheck, and both receivers still agree
            with the pads
  padtruth  in every run from the line generator truth.txt equals truth_gen.txt; the selftest of this script
            passes
  front     the two front ends were equal at every change in every run but NEG-front, where the check counts
            differences while AMD's receiver still passes; ftel_dphy_rx behind IBUFDS_DPHY unless the scenario
            set +AFE=model. In NEG-front ftel_dphy_rx and afe_model work behind the changed buffers, whose LP
            outputs keep 00 after LP-11 (the model does not look again when only the strength changes): their
            results there are reported, not judged (exp2/README.md §7.6)
  afe       afe_model saw no line-state error, and term_en was never late or missing (NEG-front apart)
  config    the run-time fields of ftel_dphy_rx printed by the testbench equal the configuration model at the
            rate (exp1/cfg_for_rate.py), or the values the scenario set
  sources   every run was made from the current sources (RTL filelist, the three blocks of exp1/, exp2/*.sv):
            the hash in its args.txt
  copy      the blocks of tb_exp2a.sv copied from exp1/tb_exp1.sv (front end of ftel_dphy_rx, front-end check,
            instance of the wrap) are still equal to it, comments and blank lines aside
Exit status 1 when the verdict is FAIL (txtiming: when a value is outside the limits).
"""
import contextlib
import glob
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
EXP1 = os.path.join(FPGA, 'exp1')
IP = os.path.dirname(FPGA)   # the IP files sit in the folder that holds fpga/
TOL_PS = 1   # rounding of the times to the ps

# the scenarios of PLAN_TN2A.md §5, as run_exp2.sh names them
RATES = (260, 400, 600, 800, 1000, 1200, 1440, 1500)
SCENARIOS = (['E2a-0a', 'E2a-0b', 'E2a-0c', 'E2a-1', 'E2a-2a', 'E2a-2b', 'E2a-2c', 'E2a-3']
             + [f'E2a-4{s}' for s in 'abcde'] + [f'E2a-5_{r}_{d}' for r in RATES for d in ('slow', 'fast')])
NEGATIVE = ('NEG-tx', 'NEG-front')
# (block, first line, last line) of the code tb_exp2a.sv takes from tb_exp1.sv
COPY_BLOCKS = (('front end of ftel_dphy_rx', 'logic [NL-1:0] b_lp_dp', 'assign r_cl_hs_clk'),
               ('front-end check', 'int fe_diffs = 0', '`endif'),
               ('instance of the wrap', 'm_ftel_dphy_rx_wrap #(.PARA_NUM_LANES(NL)) u_ftel', ');'))
# the TB TXTIMING lines of pad_truth.sv, in its order
TIMING = ('data TLPX', 'data THS-PREPARE', 'data THS-ZERO', 'data THS-PREPARE + THS-ZERO', 'data THS-TRAIL',
          'data THS-EXIT', 'clock TLPX', 'clock TCLK-PREPARE', 'clock TCLK-ZERO', 'clock TCLK-PREPARE + TCLK-ZERO',
          'clock TCLK-PRE')


def read_b(path):
    """{(burst, lane): (bytes, t0, t1, payload hex)} from the B lines of a truth file."""
    out = {}
    for line in open(path):
        f = line.split()
        if len(f) >= 6 and f[0] == 'B':
            out[(int(f[1]), int(f[2]))] = (int(f[3]), int(f[4]), int(f[5]), f[6] if len(f) > 6 else '')
    return out


def padtruth(run):
    """(lane bursts equal, lane bursts of the generator, differences) of truth.txt against truth_gen.txt."""
    got = read_b(os.path.join(run, 'truth.txt'))
    gen = read_b(os.path.join(run, 'truth_gen.txt'))
    diffs, same = [], 0
    for k in sorted(set(got) | set(gen)):
        where = f'burst {k[0]} lane {k[1]}'
        if k not in got:
            diffs.append(f'{where}: sent by the generator, not decoded at the pads')
        elif k not in gen:
            diffs.append(f'{where}: decoded at the pads, not sent by the generator')
        else:
            (n, t0, t1, pay), (gn, gt0, gt1, gpay) = got[k], gen[k]
            if (n, pay) != (gn, gpay):
                diffs.append(f'{where}: {n} bytes {pay[:16]}, the generator sent {gn} bytes {gpay[:16]}')
            elif abs(t0 - gt0) > TOL_PS or abs(t1 - gt1) > TOL_PS:
                diffs.append(f'{where}: t0 {t0} t1 {t1} ps, the generator {gt0} {gt1} ps')
            else:
                same += 1
    return same, len(gen), diffs


def tbcheck(run):
    """[(item, ok, text)] of one run, from tb.txt, args.txt, expected.txt and, with +SRC=gen, the truth files."""
    tb = open(os.path.join(run, 'tb.txt')).read()
    args = open(os.path.join(run, 'args.txt')).read()
    n_exp = sum(1 for line in open(os.path.join(run, 'expected.txt')) if line.startswith('E '))
    gen = '+SRC=gen' in args
    items = []

    done = re.search(r'^TB DONE\s+OK: .*?, (\d+) bursts,', tb, re.M)
    items.append(('done', done is not None, done[0][:60] if done else 'no TB DONE OK line'))

    m = re.search(r'^TB PADS: (\d+) bursts decoded, (\d+) payload bytes, mismatches (\d+), unexpected (\d+), '
                  r'missing (\d+), without sync (\d+), short (\d+), line-state differences with afe_model (\d+)',
                  tb, re.M)
    if m:
        dec, nbytes, mis, unexp, miss, nosync, short, sdiff = (int(x) for x in m.groups())
        ok = dec == n_exp and mis == unexp == miss == nosync == short == sdiff == 0
        items.append(('pads', ok, f'{dec}/{n_exp} lane bursts decoded, {nbytes} bytes, mismatches {mis}, unexpected'
                                  f' {unexp}, missing {miss}, without sync {nosync}, short {short}, line-state'
                                  f' differences {sdiff}'))
    else:
        items.append(('pads', False, 'no TB PADS line'))

    m = re.search(r'^TB FRONT END CHECK: .* differ at (\d+) of (\d+) changes', tb, re.M)
    s = re.search(r'^TB FRONT END CHECK START: comparisons (\d+), differences (\d+) up to 2\.5 ps', tb, re.M)
    text = f'{m[1]} differences in {m[2]} changes' if m else 'no TB FRONT END CHECK line'
    text += f' (not counted, up to 2.5 ps: {s[2]} of {s[1]} comparisons differ)' if s else '; no START line'
    items.append(('front', bool(m and s) and m[1] == '0' and int(m[2]) > 0, text))

    dl = re.search(r'^AFE data lanes: .*\(limit [\d.]+, (\d+) late, (\d+) missing\)', tb, re.M)
    cl = re.search(r'^AFE clock lane: .*\(limit [\d.]+, (\d+) late\)', tb, re.M)
    st = re.search(r'AFE line-state errors (\d+)', tb)
    ok = bool(dl and cl and st) and dl[1] == dl[2] == cl[1] == st[1] == '0'
    items.append(('afe', ok, f'term_en late {dl[1]}, missing {dl[2]}; clock lane late {cl[1]}; line-state errors'
                             f' {st[1]}' if dl and cl and st else 'AFE lines missing'))

    if gen:
        same, total, diffs = padtruth(run)
        items.append(('padtruth', total > 0 and not diffs,
                      f'{same}/{total} lane bursts equal to the generator' + (f'; {diffs[:3]}' if diffs else '')))
    else:
        m = re.search(r'^TB TX: .*, (\d+) bursts done, (\d+) lane bursts without HS', tb, re.M)
        ok = bool(m and done) and int(m[1]) == int(done[1]) and m[2] == '0'
        items.append(('tx', ok, f'{m[1]} bursts done of {done[1] if done else "?"}, {m[2]} lane bursts without HS'
                                if m else 'no TB TX line'))
    return items


def print_tbcheck(items):
    for name, ok, text in items:
        print(f"TBCHECK {name:8s} {'ok  ' if ok else 'FAIL'} {text}")
    n_ok = sum(1 for _, ok, _ in items if ok)
    print(f"TBRESULT: {'PASS' if n_ok == len(items) else 'FAIL'} ({n_ok}/{len(items)} items)")
    return n_ok == len(items)


# ---------------------------------------------------------------------------------------------------
# self test

START = ('TB FRONT END CHECK START: comparisons 1, differences 1 up to 2.5 ps, not counted (the pads can leave X at'
         ' 1 ps)\n')
CLEAN_TB = """TB START: NL 2, rate 1440.92 Mb/s (UI 0.694 ns), lengths '{1,2} x 1, pattern counter, ftel 1, source x
""" + START + """AFE data lanes: 4 HS entries, term_en after LP-00 max 29.998 ns (limit 37.776, 0 late, 0 missing), hs_en max 34.998 ns, term_en during HS request 0, term_en off after LP-11 max 29.810 ns
AFE clock lane: term_en after LP-00 29.998 ns (limit 38.000, 0 late), hs_en 34.998 ns
TB PADS: 4 bursts decoded, 6 payload bytes, mismatches 0, unexpected 0, missing 0, without sync 0, short 0, line-state differences with afe_model 0, trail bits 120..121
TB FRONT END CHECK: LP outputs of AMD's buffers and of the buffers of ftel_dphy_rx differ at 0 of 100 changes
TB TX: init_done 383.253 us, clock lane requested 384.255 us, running 384.733 us (cl_txclkactivehs), 2 bursts done, 0 lane bursts without HS
TB DONE      OK: NL 2, rate 1440.92 Mb/s (UI 0.694 ns), 2 bursts, AMD init_done 100.113 us, ftel init_done 100.123 us, AFE line-state errors 0
"""
CLEAN_EXP = "E 0 0 1 00\nE 0 1 1 40\nE 1 0 2 1011\nE 1 1 2 5051\n"
CLEAN_TRUTH = ("B 0 0 1 1000 7944 00\nB 0 1 1 1000 7944 40\n"
               "B 1 0 2 20000 31110 1011\nB 1 1 2 20000 31110 5051\n")


def write_run(d, tb, args, exp, truth, truth_gen=None):
    os.makedirs(d, exist_ok=True)
    for name, text in (('tb.txt', tb), ('args.txt', args), ('expected.txt', exp), ('truth.txt', truth),
                       ('truth_gen.txt', truth_gen)):
        if text is not None:
            with open(os.path.join(d, name), 'w') as f:
                f.write(text)


def selftest():
    """tbcheck and padtruth on synthetic runs: the clean ones pass (a difference up to 2.5 ps is not counted),
    each planted fault is found, and a 1 ps difference of the times stays within the rounding. True when all
    hold."""
    gen_args = 'S: 1440 Mb/s, 2 lane(s) +SRC=gen\n'
    tx_args = 'S: 1440 Mb/s, 2 lane(s)\n'
    cases = [   # (name, tb, args, truth, truth_gen, failing items)
        ('clean tx', CLEAN_TB, tx_args, CLEAN_TRUTH, None, []),
        ('clean gen', CLEAN_TB, gen_args, CLEAN_TRUTH, CLEAN_TRUTH, []),
        ('mismatch', CLEAN_TB.replace('mismatches 0', 'mismatches 1'), tx_args, CLEAN_TRUTH, None, ['pads']),
        ('decoded fewer', CLEAN_TB.replace('4 bursts decoded', '3 bursts decoded'), tx_args, CLEAN_TRUTH, None,
         ['pads']),
        ('front', CLEAN_TB.replace('differ at 0 of', 'differ at 3 of'), tx_args, CLEAN_TRUTH, None, ['front']),
        ('no START line', CLEAN_TB.replace(START, ''), tx_args, CLEAN_TRUTH, None, ['front']),
        ('term_en late', CLEAN_TB.replace('0 late, 0 missing', '1 late, 0 missing'), tx_args, CLEAN_TRUTH, None,
         ['afe']),
        # without TB DONE OK the burst count of the TX cannot be confirmed either
        ('no TB DONE', CLEAN_TB.replace('TB DONE      OK', 'TB DONE TIMEOUT'), tx_args, CLEAN_TRUTH, None,
         ['done', 'tx']),
        ('lane without HS', CLEAN_TB.replace('0 lane bursts', '1 lane bursts'), tx_args, CLEAN_TRUTH, None, ['tx']),
        ('byte', CLEAN_TB, gen_args, CLEAN_TRUTH.replace('5051', '5052'), CLEAN_TRUTH, ['padtruth']),
        ('t0 + 2 ps', CLEAN_TB, gen_args, CLEAN_TRUTH.replace('B 1 0 2 20000', 'B 1 0 2 20002'), CLEAN_TRUTH,
         ['padtruth']),
        ('t1 + 1 ps', CLEAN_TB, gen_args, CLEAN_TRUTH.replace('31110 1011', '31111 1011'), CLEAN_TRUTH, []),
        ('lost line', CLEAN_TB, gen_args, CLEAN_TRUTH.replace('B 0 1 1 1000 7944 40\n', ''), CLEAN_TRUTH,
         ['padtruth']),
    ]
    ok_all = True
    with tempfile.TemporaryDirectory() as work:
        for k, (name, tb, args, truth, truth_gen, fails) in enumerate(cases):
            d = os.path.join(work, f'r{k}')
            write_run(d, tb, args, CLEAN_EXP, truth, truth_gen)
            items = tbcheck(d)
            bad = [n for n, ok, _ in items if not ok]
            ok = bad == fails
            ok_all &= ok
            print(f"  {'ok  ' if ok else 'FAIL'} {name}: failing items {bad}, expected {fails}")
    print(f"selftest: {'PASS' if ok_all else 'FAIL'}")
    return ok_all


# ---------------------------------------------------------------------------------------------------
# evidence over all runs

def sources_hash():
    """The hash run_exp2.sh keeps in build_*/src.sha and in args.txt: sha256sum of the RTL filelist sources, the
    three blocks of exp1/ and exp2/*.sv, in the order of ls."""
    files = [IP + line.rstrip('\n')[len('${FTEL_DPHY_RX_PATH}'):]
             for line in open(os.path.join(IP, 'logical', 'filelist.f')) if line.startswith('${FTEL_DPHY_RX_PATH}')]
    files += sorted([os.path.join(EXP1, f) for f in ('dphy_line_gen.sv', 'afe_model.sv', 'ppi_csv_mon.sv')]
                    + glob.glob(os.path.join(HERE, '*.sv')))
    text = ''.join(f'{hashlib.sha256(open(f, "rb").read()).hexdigest()}  {f}\n' for f in files)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def code_lines(path):
    """The lines of a source without // comments and blank lines."""
    out = []
    for line in open(path):
        line = re.sub(r'//.*', '', line).rstrip()
        if line.strip():
            out.append(line)
    return out


def block(lines, start, end):
    """The lines from the first one that starts with start to the next one that starts with end ([] if none)."""
    for i, line in enumerate(lines):
        if line.strip().startswith(start):
            for j in range(i, len(lines)):
                if lines[j].strip().startswith(end):
                    return lines[i:j + 1]
    return []


def copy_blocks(tb2=None):
    """[(block, code lines in tb_exp1.sv, equal)] of the blocks tb_exp2a.sv (or the file tb2) takes from
    tb_exp1.sv."""
    a = code_lines(os.path.join(EXP1, 'tb_exp1.sv'))
    b = code_lines(tb2 or os.path.join(HERE, 'tb_exp2a.sv'))
    out = []
    for name, start, end in COPY_BLOCKS:
        x, y = block(a, start, end), block(b, start, end)
        out.append((name, len(x), bool(x) and x == y))
    return out


def neg_tx(run, args, tb, check, items):
    """(ok, text) of NEG-tx: the byte of +TX_CORRUPT is the only mismatch at the pads, sent inverted, every other
    count of TB PADS is clean, pads is the only failing item of tbcheck, and both receivers agree with the pads."""
    c = re.search(r'\+TX_CORRUPT=(\d+),(\d+),(\d+)', args)
    mm = re.findall(r'^TB PADS MISMATCH: lane (\d+) burst (\d+) byte (\d+): (\w+) at the pads, (\w+) expected$',
                    tb, re.M)
    p = re.search(r'^TB PADS: (\d+) bursts decoded, \d+ payload bytes, mismatches (\d+), unexpected (\d+), missing'
                  r' (\d+), without sync (\d+), short (\d+), line-state differences with afe_model (\d+)', tb, re.M)
    n_exp = sum(1 for line in open(os.path.join(run, 'expected.txt')) if line.startswith('E '))
    fails = [n for n, (ok, _) in items.items() if not ok]
    rx_ok = re.search(r'^RESULT: PASS', check, re.M) is not None
    ok = (bool(c and p and len(mm) == 1) and mm[0][:3] == c.groups() and int(mm[0][3], 16) == int(mm[0][4], 16) ^ 0xff
          and int(p[1]) == n_exp and p.groups()[1:] == ('1', '0', '0', '0', '0', '0') and fails == ['pads'] and rx_ok)
    where = (f'{mm[0][3]} at the pads for {mm[0][4]} at lane {mm[0][0]} burst {mm[0][1]} byte {mm[0][2]}'
             if len(mm) == 1 else f'{len(mm)} mismatch lines')
    planted = ','.join(c.groups()) if c else '?'
    return ok, (f'{where} (planted {planted}), tbcheck failing {fails}, both receivers'
                f' {"agree with the pads" if rx_ok else "do not pass"}')


def evidence(w, tb2=None):
    """The checks of the evidence over the runs E2a-*, M_E2a-* and NEG-* in w ({check: passed}); tb2 replaces
    tb_exp2a.sv in the check copy."""
    if EXP1 not in sys.path:
        sys.path.insert(0, EXP1)
    import tn1_evidence as tn1   # its decoder, written apart from csi2_dump.py; it loads the configuration model
    with open(tn1.vc.YAML_DEFAULT, 'rb') as f:
        model = tn1.vc.Model(tn1.vc.yaml.safe_load(f.read()))
    names = sorted(os.path.basename(os.path.dirname(c)) for c in glob.glob(os.path.join(w, '*', 'check.txt')))
    runs = [n for n in names if re.match(r'(M_)?E2a-|NEG-', n)]
    results = {}

    def report(name, ok, text, details=()):
        results[name] = ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:8s} {text}")
        for d in list(details)[:10]:
            print(f'          {d}')

    st = subprocess.run([sys.executable, os.path.join(FPGA, 'tools', 'csi2_dump.py'), 'selftest'],
                        capture_output=True, text=True)
    report('checker', st.returncode == 0 and 'selftest: PASS' in st.stdout,
           'csi2_dump.py selftest (planted faults found, clean capture passes)')

    cur = sources_hash()
    bad = {k: [] for k in ('decode', 'runs', 'tx', 'padtruth', 'front', 'afe', 'config', 'sources')}
    neg = {}
    n_cap = n_same = n_tx = n_gen = n_fe = n_changes = n_model = 0
    start_diff = []
    for name in runs:
        run = os.path.join(w, name)
        args, tb, check = (open(os.path.join(run, f)).read() if os.path.exists(os.path.join(run, f)) else ''
                           for f in ('args.txt', 'tb.txt', 'check.txt'))
        nl = re.search(r'^TB START: NL (\d+)', tb, re.M)
        if not nl or not os.path.exists(os.path.join(run, 'truth.txt')):
            bad['runs'].append(f'{name}: no TB START line or no truth.txt')
            continue
        lanes = int(nl[1])
        truth = tn1.read_truth(os.path.join(run, 'truth.txt'))
        items = {n: (ok, text) for n, ok, text in tbcheck(run)}

        lim = re.search(r'^trailer limit .*: (\S+)$', args, re.M)
        limits = [None if x == '-' else int(x) for x in lim[1].split(',')] if lim else []
        refs = re.findall(r'^[AB] \S+: \d+ lane\(s\), (\d+)/(\d+) bursts carry the payload sent, trailer bytes'
                          r' ([-0-9.]+).*errors (\d+)$', check, re.M)
        if len(refs) != 2 or len(limits) != 2:
            bad['decode'].append(f'{name}: {len(refs)} capture lines in check.txt, trailer limits {limits}')
        for cap, limit, ref in zip(('xil_ppi.csv', 'ftel_ppi.csv'), limits, refs):
            n_ok, n_all, span, errs = tn1.decode(os.path.join(run, cap), truth, lanes, limit)
            n_cap += 1
            if (n_ok, n_all, span, errs == 0) == (int(ref[0]), int(ref[1]), ref[2], ref[3] == '0'):
                n_same += 1
            else:
                bad['decode'].append(f'{name}/{cap}: {n_ok}/{n_all} trailer {span} errors {errs}; check.txt'
                                     f' {ref[0]}/{ref[1]} trailer {ref[2]} errors {ref[3]}')

        done = re.search(r'^TB DONE\s+OK: NL (\d+), .*?, (\d+) bursts,', tb, re.M)
        n_lines = sum(len(v) for v in truth.values())
        if not done or int(done[1]) * int(done[2]) != n_lines:
            bad['runs'].append(f'{name}: {done[0][:40] if done else "no TB DONE OK"}, {n_lines} truth lines')
        failing = [n for n, (ok, _) in items.items() if not ok]
        result = re.search(r'^RESULT: .*', check, re.M)
        if not name.startswith('NEG-') and (failing or not result or not result[0].startswith('RESULT: PASS')):
            bad['runs'].append(f'{name}: {result[0] if result else "no RESULT"}; tbcheck failing {failing}')

        if '+SRC=gen' in args:
            n_gen += 1
            same, total, diffs = padtruth(run)
            if not total or diffs:
                bad['padtruth'].append(f'{name}: {same}/{total} lane bursts equal; {diffs[:2]}')
        else:
            n_tx += 1
            if name == 'NEG-tx':
                neg['tx'] = neg_tx(run, args, tb, check, items)
                if not neg['tx'][0]:
                    bad['tx'].append(f'{name}: {neg["tx"][1]}')
            elif not (items['pads'][0] and items['tx'][0]):
                bad['tx'].append(f'{name}: {items["pads"][1]}; {items["tx"][1]}')

        fe = re.search(r'^TB FRONT END: ftel_dphy_rx behind\s+(\S+)', tb, re.M)
        want_fe = 'afe_model' if '+AFE=model' in args else 'IBUFDS_DPHY'
        n_model += want_fe == 'afe_model'
        if not fe or fe[1] != want_fe:
            bad['front'].append(f'{name}: behind {fe[1] if fe else "?"}, expected {want_fe}')
        chk = re.search(r'^TB FRONT END CHECK: .* differ at (\d+) of (\d+) changes', tb, re.M)
        start = re.search(r'^TB FRONT END CHECK START: comparisons (\d+), differences (\d+)', tb, re.M)
        if name == 'NEG-front':
            amd_ok = re.search(r'^A xil_ppi\.csv: .*errors 0$', check, re.M) is not None
            ftel = re.search(r'^B ftel_ppi\.csv: .*?(\d+/\d+) bursts carry .*errors (\d+)$', check, re.M)
            ok = bool(chk) and int(chk[1]) > 0 and not items['front'][0] and amd_ok
            neg['front'] = (ok, f'{chk[1] if chk else "?"} differences in {chk[2] if chk else "?"} changes, AMD\'s'
                                f' receiver {"passes" if amd_ok else "fails"}; reported only, behind the changed'
                                f' buffers: ftel_dphy_rx {ftel[1] + " bursts, errors " + ftel[2] if ftel else "?"},'
                                f' {items["afe"][1]}')
            if not ok:
                bad['front'].append(f'{name}: {neg["front"][1]}')
        elif items['front'][0]:
            n_fe += 1
            n_changes += int(chk[2])
            if int(start[2]):
                start_diff.append(f'{name} {start[2]}/{start[1]}')
        else:
            bad['front'].append(f'{name}: {items["front"][1]}')

        if not items['afe'][0] and name != 'NEG-front':
            bad['afe'].append(f'{name}: {items["afe"][1]}')

        rate = float(re.search(r'^\S+: (\d+) Mb/s', args, re.M)[1])
        cfg = re.search(r'^TB FTEL CFG: hs_settle_cyc (\d+), clk_settle_cyc (\d+), eot_skip_bytes (\d+), '
                        r'tinit_cyc (\d+)', tb, re.M)
        want = {'hs_settle_cyc': model.hs_settle(rate), 'clk_settle_cyc': model.clk_settle(),
                'eot_skip_bytes': model.eot_skip(rate), 'tinit_cyc': None}
        for i, (field, plus) in enumerate(tn1.FIELDS):
            m = re.search(rf'\+{plus}=(\d+)', args)
            exp = int(m[1]) if m else want[field]
            if not cfg or (exp is not None and int(cfg[i + 1]) != exp):
                bad['config'].append(f'{name} {field} {cfg[i + 1] if cfg else "?"} (expected {exp})')

        src = re.search(r'^sources (\S+)$', args, re.M)
        if not src or src[1] != cur:
            bad['sources'].append(f'{name}: {src[1] if src else "no sources line"}')

    want_runs = [*SCENARIOS, *('M_' + s for s in SCENARIOS), *NEGATIVE]
    missing = [n for n in want_runs if n not in runs]
    own = tn1.decode_selftest()
    report('decode', n_cap > 0 and not bad['decode'] and own,
           f'{n_same}/{n_cap} captures of {len(runs)} runs decoded again by exp1/tn1_evidence.py with the same'
           f' result as check.txt; its decoder selftest {"PASS" if own else "FAIL"}', bad['decode'])
    report('runs', not missing and not bad['runs'],
           f'{len(runs)} runs: {len(SCENARIOS)} scenarios, their M_ runs and {len(NEGATIVE)} negative tests'
           f' {"all there" if not missing else "missing " + str(missing)}; TB DONE OK with one truth line per'
           ' burst and lane; every scenario PASS in check.txt and tbcheck.txt', bad['runs'])
    report('tx', n_tx > 0 and not bad['tx'] and neg.get('tx', (False,))[0],
           f'{n_tx} runs from AMD\'s TX: the bytes at the pads equal to the bytes given; NEG-tx:'
           f' {neg["tx"][1] if "tx" in neg else "not run"}', bad['tx'])
    with contextlib.redirect_stdout(io.StringIO()):
        st_ok = selftest()
    report('padtruth', n_gen > 0 and not bad['padtruth'] and st_ok,
           f'{n_gen} runs from the line generator: truth.txt equal to truth_gen.txt (bytes; t0, t1 within'
           f' {TOL_PS} ps); selftest of tbcheck and padtruth {"PASS" if st_ok else "FAIL"}', bad['padtruth'])
    report('front', n_fe > 0 and not bad['front'] and neg.get('front', (False,))[0],
           f'{n_fe} runs with equal LP outputs of the two front ends at every change after 2.5 ps ({n_changes}'
           f' changes); up to 2.5 ps, not counted, differences in {start_diff if start_diff else "no run"};'
           f' ftel_dphy_rx behind afe_model in the {n_model} runs with +AFE=model; NEG-front:'
           f' {neg["front"][1] if "front" in neg else "not run"}', bad['front'])
    n_afe = len(runs) - ('NEG-front' in runs)
    report('afe', not bad['afe'], f'{n_afe - len(bad["afe"])}/{n_afe} runs without AFE line-state error or late or'
           ' missing term_en (NEG-front apart, see front)', bad['afe'])
    report('config', not bad['config'], f'{len(runs)} runs with the configuration of the model or of the scenario',
           bad['config'])
    report('sources', bool(runs) and not bad['sources'],
           f'{len(runs) - len(bad["sources"])}/{len(runs)} runs made from the current sources (hash {cur})',
           bad['sources'])
    blocks = copy_blocks(tb2)
    report('copy', all(eq for _, _, eq in blocks),
           '; '.join(f'{b} {n} code lines {"equal" if eq else "DIFFERENT"}' for b, n, eq in blocks)
           + ' (tb_exp2a.sv against exp1/tb_exp1.sv)')
    ok = all(results.values())
    print(f"EVIDENCE: {'PASS' if ok else 'FAIL'} ({sum(results.values())}/{len(results)} checks)")
    return results


def flip_capture(text):
    """The capture with the lowest bit of the first payload byte of lane 0 inverted."""
    lines = text.split('\n')
    head = lines[0].split(',')
    d, v = head.index('dl0_rxdatahs[7:0]'), head.index('dl0_rxvalidhs')
    for i in range(2, len(lines)):
        f = lines[i].split(',')
        if len(f) > v and f[v] == '1':
            f[d] = f'{int(f[d], 16) ^ 1:02x}'
            lines[i] = ','.join(f)
            break
    return '\n'.join(lines)


def flip_truth(text):
    """The truth with the lowest bit of the first byte of its first lane burst inverted."""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        f = line.split()
        if len(f) > 6 and f[0] == 'B':
            f[6] = f'{int(f[6][:2], 16) ^ 1:02x}' + f[6][2:]
            lines[i] = ' '.join(f)
            break
    return '\n'.join(lines)


WRAP_LINE = '.i_dphy_rx_core_clk              (core_clk),'   # a line of the copied instance of the wrap
EV_FAULTS = (   # (fault, run (None: tb_exp2a.sv), file, change of its text, checks that must fail)
    ('none', None, None, None, []),
    ('a payload bit of a capture', 'E2a-1', 'ftel_ppi.csv', flip_capture, ['decode']),
    ('another byte planted in NEG-tx', 'NEG-tx', 'args.txt',
     lambda s: s.replace('+TX_CORRUPT=1,3,0', '+TX_CORRUPT=1,3,1'), ['tx']),
    ('a byte of the generator truth', 'E2a-0a', 'truth_gen.txt', flip_truth, ['padtruth', 'runs']),
    ('a front-end difference', 'E2a-1', 'tb.txt', lambda s: s.replace('differ at 0 of', 'differ at 1 of'),
     ['front', 'runs']),
    ('a late term_en', 'E2a-1', 'tb.txt', lambda s: s.replace('0 late, 0 missing', '1 late, 0 missing', 1),
     ['afe', 'runs']),
    ('another eot_skip_bytes', 'E2a-1', 'tb.txt', lambda s: s.replace('eot_skip_bytes 13', 'eot_skip_bytes 12'),
     ['config']),
    ('another sources hash', 'E2a-1', 'args.txt',
     lambda s: re.sub(r'^sources \S+$', 'sources 0000000000000000', s, flags=re.M), ['sources']),
    ('a run missing', 'E2a-3', None, None, ['runs']),
    ('a changed line of the copied code', None, 'tb_exp2a.sv',
     lambda s: s.replace(WRAP_LINE, WRAP_LINE.replace('(core_clk)', '(tx_core_clk)')), ['copy']),
)


def evselftest(w):
    """evidence() with each fault of EV_FAULTS planted in turn: the runs of w are linked into a temporary folder,
    the run changed is copied there. True when every fault fails exactly its checks."""
    runs = sorted(os.path.basename(os.path.dirname(c)) for c in glob.glob(os.path.join(w, '*', 'check.txt'))
                  if re.match(r'(M_)?E2a-|NEG-', os.path.basename(os.path.dirname(c))))
    ok_all = True
    for fault, run, name, change, want in EV_FAULTS:
        with tempfile.TemporaryDirectory() as d:
            planted, tb2 = change is None, None
            for r in runs:
                if r == run and change is None:
                    continue                      # the run left out
                if r == run:
                    shutil.copytree(os.path.join(w, r), os.path.join(d, r))
                    path = os.path.join(d, r, name)
                    text = open(path).read()
                    new = change(text)
                    planted = new != text
                    with open(path, 'w') as f:
                        f.write(new)
                else:
                    os.symlink(os.path.join(w, r), os.path.join(d, r))
            if run is None and change is not None:
                tb2 = os.path.join(d, name)
                text = open(os.path.join(HERE, name)).read()
                new = change(text)
                planted = new != text
                with open(tb2, 'w') as f:
                    f.write(new)
            with contextlib.redirect_stdout(io.StringIO()):
                res = evidence(d, tb2)
        failing = sorted(k for k, ok in res.items() if not ok)
        ok = planted and failing == sorted(want)
        ok_all &= ok
        print(f"  {'ok  ' if ok else 'FAIL'} {fault}{'' if planted else ' (not planted)'}: failing checks"
              f" {failing}, expected {sorted(want)}")
    print(f"evselftest: {'PASS' if ok_all else 'FAIL'}")
    return ok_all


def txtiming(w):
    """Markdown tables over the runs from AMD's TX (E2a-* and M_E2a-*, not +SRC=gen): the timing measured at the
    pads per rate (min..max of the TB TXTIMING lines, ns) and the limits of D-PHY v1.1 at each rate. Returns the
    number of values outside the limits."""
    per, used = {}, {}   # rate -> parameter -> [min, max, count, limit, outside]; rate -> runs
    for c in sorted(glob.glob(os.path.join(w, '*', 'check.txt'))):
        run = os.path.dirname(c)
        name = os.path.basename(run)
        args = open(os.path.join(run, 'args.txt')).read()
        if not re.match(r'(M_)?E2a-', name) or '+SRC=gen' in args:
            continue
        rate = int(re.search(r'^\S+: (\d+) Mb/s', args, re.M)[1])
        used.setdefault(rate, []).append(name)
        tb = open(os.path.join(run, 'tb.txt')).read()
        for m in re.finditer(r'^TB TXTIMING (.+?): min ([\d.]+) max ([\d.]+) ns over (\d+) \(limit (.*?)\)'
                             r'( OUTSIDE)?\s*$', tb, re.M):
            p = per.setdefault(rate, {}).setdefault(m[1], [float('inf'), float('-inf'), 0, m[5], 0])
            p[0], p[1] = min(p[0], float(m[2])), max(p[1], float(m[3]))
            p[2] += int(m[4])
            p[4] += m[6] is not None
    rates = sorted(per)
    outside = 0

    def cell(rate, name, limit):
        p = per[rate].get(name)
        if not p:
            return '-'
        if limit:
            return p[3]
        v = f'{p[0]:.1f}' if f'{p[0]:.1f}' == f'{p[1]:.1f}' else f'{p[0]:.1f}..{p[1]:.1f}'
        return v + (' OUTSIDE' if p[4] else '')

    for title, limit in (('TX timing at the pads (ns): min..max over the runs from the TX at each rate', False),
                         ('Limits of D-PHY v1.1 at each rate (ns)', True)):
        print(f'{title}\n')
        print('| Parameter | ' + ' | '.join(str(r) for r in rates) + ' |')
        print('|---|' + '---|' * len(rates))
        for name in TIMING:
            print(f'| {name} | ' + ' | '.join(cell(r, name, limit) for r in rates) + ' |')
        print()
    for r in rates:
        outside += sum(p[4] for p in per[r].values())
        print(f'{r} Mb/s: {len(used[r])} runs ({", ".join(used[r])})')
    print('THS-EXIT depends on +GAP_NS, the wait after stopstate before the next request (E2a-3: none).')
    print(f'TXTIMING: {outside} values outside the limits')
    return outside


def main():
    a = sys.argv[1:]
    w = a[1] if len(a) == 2 else os.path.join(FPGA, 'work', 'exp2')
    if len(a) == 2 and a[0] == 'tbcheck':
        return 0 if print_tbcheck(tbcheck(a[1])) else 1
    if len(a) == 2 and a[0] == 'padtruth':
        same, total, diffs = padtruth(a[1])
        print(f"PADTRUTH: {'PASS' if total and not diffs else 'FAIL'} ({same}/{total} lane bursts equal)")
        for x in diffs[:10]:
            print(f'  {x}')
        return 0 if total and not diffs else 1
    if a == ['selftest']:
        return 0 if selftest() else 1
    if a[:1] == ['evidence'] and len(a) <= 2:
        return 0 if all(evidence(w).values()) else 1
    if a[:1] == ['evselftest'] and len(a) <= 2:
        return 0 if evselftest(w) else 1
    if a[:1] == ['txtiming'] and len(a) <= 2:
        return 0 if txtiming(w) == 0 else 1
    sys.exit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
