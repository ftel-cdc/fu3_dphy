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
# Description     : Checks of the TN2b runs (fpga/PLAN_TN2B.md §5, §7): the testbench-level verdict of a run, a
#                   decoder of its captures written apart from csi2_dump.py, and the evidence over all runs.
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
"""Checks of the TN2b runs (fpga/PLAN_TN2B.md) in fpga/work/exp2b.

  tn2b_evidence.py tbcheck <run>      testbench-level verdict of one run (run_exp2b.sh writes it to tbcheck.txt)
  tn2b_evidence.py decode <run>       the captures of one run decoded again, apart from csi2_dump.py, against the
                                      frames of the formula, item by item as check.txt
  tn2b_evidence.py selftest           the decoder on known values and on synthetic captures
  tn2b_evidence.py evidence [<dir>]   the evidence of PLAN_TN2B.md §7 over the runs in <dir> (default
                                      fpga/work/exp2b)
  tn2b_evidence.py evselftest [<dir>] evidence on the runs of <dir> with one planted fault at a time (links to
                                      the runs, the changed one copied into a temporary folder): exactly the checks
                                      named for that fault must fail, and none without a fault
  tn2b_evidence.py report [<dir>]     what PLAN_TN2B.md §5 reports without judging, per rate, from the SH_ runs:
                                      start of the TX, trailer bytes on the PPI of both receivers, bursts and gaps
                                      chosen by the TX controller, latency from the TX input to video_out, memory
                                      and length of the simulations

The runs (run_exp2b.sh): SH_* take rxactivehs into R-F through the gate of fpga/rtl/m_ftel_ppi_act_gate.sv
(+PPI_ADAPTER=1, tb_exp2b.sv, fpga/PLAN_TN2B_GATE.md) and are the scenarios of PLAN_TN2B.md §6 with E2b-9 of
PLAN_TN2B_GATE.md §4, their afe_model runs (SH_M_*) and the negative tests (SH_NEG-*); E2b-* without SH_ and DBG-*
are the runs of the finding: AMD's controller without PHY takes no packet of ftel_dphy_rx unless rxactivehs rises
with rxsynchs.

tbcheck prints one line per item, then the verdict line TBRESULT:
  done      the run ended with TB DONE OK
  axil      no AXI4-Lite access of the testbench timed out or got an error response
  tx        the TX reached core ready after its enable, took every beat of every frame, and its ISR (0x24) shows
            none of its error bits: underrun, wrong data type, line buffer full, ULPS, GSP FIFO full, lane
            configuration (bits 0-5)
  regs      both CSI-2 receivers: frame received (ISR bit 31) and none of the error bits of AMD's driver
            (protocol: frame sync and level of VC0-3, VCX frame; packet: ECC 1 and 2 bit, CRC, unknown data type;
            D-PHY: SoT, SoT sync; other: word count, lane configuration, line buffer full, YUV420, skew
            calibration); R-F has the packet count (CSR[31:16]) and the image information of VC0 (0x60, 0x64) of
            R-X, and that information gives the word count and the data type (RAW10) of the frames sent. Stop
            state and the short packet FIFO bits, and the lane information, are shown, not judged. A register digit
            printed as X or Z is unknown: unknown frame-received or error bits fail, as does an unknown bit of the
            packet count or of the image information; other unknown ISR bits are shown. With +RX_LATE=1,
            +STREAM_TOGGLE=1 and +PPI_SOTSYNCERR the item is shown, not judged (PLAN_TN2B.md §6; the registers of
            R-X after +PPI_SOTSYNCERR are judged by the evidence, check gate)
  axis      the TX took the frames given; video_out of R-X and of R-F gave as many frames and lines (with
            +RX_LATE=1 at least the frames after the first; with +PPI_SOTSYNCERR the lines of R-F are shown, not
            judged: check gate)
  front     the LP outputs of AMD's buffers (inside R-X) and of the buffers of ftel_dphy_rx were equal at every
            change after 2.5 ps (as in TN2a)
  afe       term_en of the data lanes and of the clock lane was never late or missing (afe_model). TN2b has no
            truth of the line state (no line generator, no pad decoder), so there is no line-state comparison
  corrupt   (+PPI_CORRUPT only) exactly one byte was flipped on the PPI into R-F
  adapter   (+PPI_ADAPTER=1 only) rxactivehs into R-F came from the gate of fpga/rtl/ (TB ADAPTER) and was equal
            to the model of the testbench at every byte clock: comparisons, and no difference
  sotsync   (+PPI_SOTSYNCERR only) exactly the burst named was given the SoT sync error: one event

decode prints one line per item, then the verdict line DECODERESULT:
  frames            frames.txt holds the frames of the formula (plan §2.1)
  tx-axis           the TX took exactly those frames (tx_axis.csv)
  pixels-xil, pixels-ftel
                    video_out of R-X, of R-F gave those frames line by line, every line with the word count and the
                    data type sent, from its first start of frame after the set-up of the receiver (TB RX CFG); with
                    +RX_LATE=1 from frame 1
  ppi-tx, ppi-xil, ppi-ftel
                    no packet of the PPI capture has an error: a short burst, a header with two or more bits wrong
                    (one is corrected, as a receiver does), a truncated payload or a CRC error; for R-X and R-F also
                    the timing at the PPI of the HAS (Table A-2): rxsynchs High in one sample of each lane burst, one
                    cycle before the first byte for AMD's D-PHY and in its cycle for ftel_dphy_rx (C6; one cycle
                    before where +PPI_AMD_TIMING=1|2 moved it), and each byte of a packet on all lanes within
                    LANE_SPREAD samples (C10)
  golden-ppi        the RAW10 lines after each frame start on the PPI of the TX and of R-X are the frames of the
                    formula
  packets-tx-xil, packets-xil-ftel
                    the two PPI captures carry the same packets (virtual channel, data type, word count, payload)
                    from the first frame start
  The items named as in check.txt must give its verdict (evidence, check decode).

evidence prints one line per check, then the verdict line EVIDENCE:
  checker   fpga/tools/csi2_dump.py selftest passes: planted faults are found, a clean capture passes
  decode    every run is decoded again (decode above): each item of its check.txt gets the same verdict, and frames,
            tx-axis and golden-ppi pass; the selftest of the decoder passes
  runs      every scenario of PLAN_TN2B.md §6 and E2b-9 was run through the gate (SH_), also behind afe_model
            (SH_M_, all but E2b-8 and E2b-9), the three negative tests (SH_NEG-*) and the runs of the finding
            (E2b-1, E2b-4a/b/c, E2b-6, DBG-*); every run ended with TB DONE OK; every SH_ scenario passed check.txt
            and tbcheck, SH_E2b-9 tbcheck (its check.txt fails on R-F by design: check gate)
  regs      in every SH_ scenario where they are judged, the registers of both receivers show frame received and
            no error bit, and R-F has the packet count and the image information of R-X; the runs where they are
            only shown (+RX_LATE, +STREAM_TOGGLE, +PPI_SOTSYNCERR) and the unknown bits of the ISRs are listed
  front     the two front ends were equal at every change in every run (NEG-front apart, see neg); ftel_dphy_rx
            behind IBUFDS_DPHY unless the scenario set +AFE=model
  afe       term_en was never late or missing (NEG-front apart, see neg)
  config    the run-time fields of ftel_dphy_rx printed by the testbench equal the configuration model at the rate
            (exp1/cfg_for_rate.py), or the values the scenario set; the parameters of the three subsystems printed by
            exp2b.tcl in each build used (EXP2B lines of build_<rate>/vivado.out) are those of PLAN_TN2B.md §4.2
            (BUILD_PARAMS)
  sources   every run was made from the current sources (RTL filelist, exp1/afe_model.sv, exp1/ppi_csv_mon.sv,
            rtl/m_ftel_ppi_act_gate.sv, exp2b/*.sv): the hash in its args.txt
  copy      the blocks of tb_exp2b.sv taken from exp1/tb_exp1.sv (front end of ftel_dphy_rx, front-end check,
            instance of the wrap) differ from it in exactly the lines of PLAN_TN2B.md §4.3 (COPY_ALLOWED),
            comments, blank lines and runs of white space aside
  neg       SH_NEG-ecc: the bit planted lands in a packet header and is corrected: check.txt passes, R-F alone
            reports ECC 1 bit, regs is the only failing item of tbcheck. SH_NEG-crc: the pixel the planted payload
            bit belongs to is the only wrong pixel of R-F, with that bit inverted; R-F alone reports CRC; check.txt
            fails exactly pixels-ftel, ppi-ftel and packets-xil-ftel, and regs is the only failing item of tbcheck.
            SH_NEG-front: the front-end check counts differences while R-X passes; ftel_dphy_rx and afe_model behind
            the changed buffers are reported, not judged
  finding   not re-timed, R-X passes and ftel_dphy_rx gives R-F the packets of R-X (packets-xil-ftel), yet R-F
            gives no line and counts no packet; at the start of every burst ftel_dphy_rx raises rxactivehs before
            rxsynchs and AMD's D-PHY raises both together; the diagnosis runs: R-F passes with the re-timings 1 and 3
            (rxactivehs from rxsynchs) and not with 2 (rxactivehs before rxsynchs) nor with the X of rxdatahs given 0;
            in every SH_ run rxactivehs into R-F rises with rxsynchs (NEG-front apart)
  gate      every SH_ run took rxactivehs into R-F from the gate, equal to the model of the testbench at every byte
            clock (tbcheck adapter). SH_E2b-9, a SoT sync error on lane 0 in packet 5 (PLAN_TN2B_GATE.md §4): only
            that burst was changed (tbcheck sotsync), and in ftel_ppi.csv that lane has one burst fewer than the
            others and errsotsynchs once, inside packet 5 of the other lanes, with its rxactivehs Low; R-X passes (its
            items of check.txt, frame received and no error bit); R-F gives every frame after the one with the error
            as the formula, word count and RAW10 in every line (it recovers), and the run ends with TB DONE OK. The
            frame with the error as R-F gives it, the ISR and the packet count of R-F are reported, not judged
Exit status 1 when the verdict is FAIL.
"""
import contextlib
import glob
import hashlib
import io
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FPGA = os.path.dirname(HERE)
EXP1 = os.path.join(FPGA, 'exp1')
IP = os.path.dirname(FPGA)   # the IP files sit in the folder that holds fpga/
sys.path.insert(0, os.path.join(FPGA, 'exp2'))
import tn2a_evidence as tn2a   # noqa: E402  (code_lines, block)

# ISR (0x24) of the CSI-2 receiver: the error groups of AMD's driver (csi_v1_8, xcsi_hw.h)
ISR_FR = 1 << 31
ISR_ERR = {'VC0-3 frame sync/level': 0xFF, 'unknown data type': 1 << 8, 'CRC': 1 << 9, 'ECC 1 bit': 1 << 10,
           'ECC 2 bit': 1 << 11, 'SoT sync': 1 << 12, 'SoT': 1 << 13, 'line buffer full': 1 << 18,
           'lane configuration': 1 << 21, 'word count': 1 << 22, 'YUV420 word count': 1 << 28,
           'skew calibration': 1 << 29, 'VCX frame': 1 << 30}
ISR_SHOWN = {'stop state': 1 << 17, 'short packet FIFO not empty': 1 << 19, 'short packet FIFO full': 1 << 20}
TX_ERR = 0x3F
DT_RAW10 = 0x2B

# the runs, as run_exp2b.sh names them
SCENARIOS = ('E2b-1', 'E2b-2a', 'E2b-2b', 'E2b-2c', 'E2b-3', 'E2b-4a', 'E2b-4b', 'E2b-4c', 'E2b-5a', 'E2b-5b',
             'E2b-6', 'E2b-7a', 'E2b-7b', 'E2b-8', 'E2b-9')
SOTSYNC = 'E2b-9'   # a SoT sync error on the PPI into R-F (fpga/PLAN_TN2B_GATE.md §4), judged in check gate
MODEL = tuple(s for s in SCENARIOS if s not in ('E2b-8', SOTSYNC))
NEGATIVE = ('NEG-ecc', 'NEG-crc', 'NEG-front')
SHIM = 'SH_'
FINDING = ('E2b-1', 'E2b-4a', 'E2b-4b', 'E2b-4c', 'E2b-6')
DIAG = {'DBG-E2b-1-xfill': False, 'DBG-E2b-1-amd1': True, 'DBG-E2b-1-amd2': False, 'DBG-E2b-1-amd3': True}  # R-F passes
LANE_SPREAD = 6   # C10 of the HAS: inter-lane byte divergence budget of the CSI-2 Rx controller, byte clocks

# (block, first line, last line) of the code tb_exp2b.sv takes from exp1/tb_exp1.sv, as tn2a_evidence.py
COPY_BLOCKS = tn2a.COPY_BLOCKS
# the lines of those blocks that differ on purpose (PLAN_TN2B.md §4.3): (line of tb_exp1.sv, line of tb_exp2b.sv)
COPY_ALLOWED = {
    'front-end check': (('`define TN1_XS g_x.u_xrx.inst.inst.xrx_rx_support_i',
                         '`define TN1_XS u_xrxss.inst.phy.inst.inst.`XRXSS_SUPPORT'),),
    'instance of the wrap': (('.i_dphy_rx_cl_enable (1\'b1),', '.i_dphy_rx_cl_enable (np_cl_enable),'),
                             ('.i_dphy_rx_dl_enable ({NL{1\'b1}}),', '.i_dphy_rx_dl_enable (np_dl_enable),'),
                             ('.o_dphy_rx_cl_ulpsclknot (),', '.o_dphy_rx_cl_ulpsclknot (f_cl_ulpsclknot),'),
                             ('.o_dphy_rx_rxulpsesc (),', '.o_dphy_rx_rxulpsesc (f_rxulpsesc),'),
                             ('.o_dphy_rx_erresc (),', '.o_dphy_rx_erresc (f_erresc),'),
                             ('.o_dphy_rx_errcontrol (),', '.o_dphy_rx_errcontrol (f_errcontrol),')),
}
# the parameters of PLAN_TN2B.md §4.2 in the EXP2B lines of exp2b.tcl; RATE is the line rate of the build
BUILD_PARAMS = {
    'xtxss': {'C_CSI_LANES': '4', 'C_DPHY_LANES': '4', 'C_CSI_DATATYPE': 'RAW10', 'C_CSI_PIXEL_MODE': '4',
              'C_CSI_MAX_BPC': '10', 'C_CSI_VID_INTERFACE': 'AXI4S', 'C_CSI_CRC_ENABLE': 'true',
              'C_CSI_EN_ACTIVELANES': 'true', 'C_HS_LINE_RATE': 'RATE', 'C_DPHY_MODE': 'MASTER', 'C_INC_PHY': 'true',
              'SupportLevel': '1'},
    'xrxss': {'C_INC_PHY': 'true', 'CMN_NUM_LANES': '4', 'C_DPHY_LANES': '4', 'CMN_PXL_FORMAT': 'RAW10',
              'CMN_NUM_PIXELS': '4', 'DPY_LINE_RATE': 'RATE', 'C_HS_LINE_RATE': 'RATE', 'CSI_BUF_DEPTH': '16384',
              'C_CSI_EN_CRC': 'true', 'C_CSI_EN_ACTIVELANES': 'true', 'C_CSI_FILTER_USERDATATYPE': 'true',
              'CMN_INC_VFB': 'true', 'VFB_TU_WIDTH': '96', 'SupportLevel': '1', 'C_EN_RXPPI_AS_MON': 'true'},
    'xrxss_np': {'C_INC_PHY': 'false', 'CMN_NUM_LANES': '4', 'C_DPHY_LANES': '4', 'CMN_PXL_FORMAT': 'RAW10',
                 'CMN_NUM_PIXELS': '4', 'DPY_LINE_RATE': 'RATE', 'C_HS_LINE_RATE': 'RATE', 'CSI_BUF_DEPTH': '16384',
                 'C_CSI_EN_CRC': 'true', 'C_CSI_EN_ACTIVELANES': 'true', 'C_CSI_FILTER_USERDATATYPE': 'true',
                 'CMN_INC_VFB': 'true', 'VFB_TU_WIDTH': '96'},
}
SETTLE_1440 = '141'   # C_HS_SETTLE_NS of both receivers at 1440 Mb/s, as in the board's build (§3)


def plus(args, name, default=None):
    """Value of +NAME=value in the arguments of a run (the scenario's own, first), as text."""
    m = re.search(rf'\+{name}=(\S+)', args)
    return m[1] if m else default


REG_LINE = r'^TB REG (\S+) 0x([0-9a-f]+) 0x([0-9a-fA-FxXzZ]+)$'


def regs(tb):
    """{(subsystem, offset): value} from the TB REG lines; a hex digit printed as X or Z reads as 0 (unknown())."""
    return {(m[1], int(m[2], 16)): int(re.sub('[xXzZ]', '0', m[3]), 16) for m in re.finditer(REG_LINE, tb, re.M)}


def unknown(tb):
    """{(subsystem, offset): mask of the bits of every hex digit printed as X or Z} from the TB REG lines."""
    out = {}
    for m in re.finditer(REG_LINE, tb, re.M):
        mask = 0
        for d in m[3]:
            mask = mask << 4 | (0xF if d in 'xXzZ' else 0)
        if mask:
            out[(m[1], int(m[2], 16))] = mask
    return out


def isr_text(v, xm=0):
    """An error bit that may be set because it is unknown gets a '?'."""
    bits = [n + ('?' if xm & m and not v & m else '') for n, m in ISR_ERR.items() if (v | xm) & m] + \
        [f'({n})' for n, m in ISR_SHOWN.items() if v & m]
    fr = ' frame received' if v & ISR_FR and not xm & ISR_FR else ''
    return f"0x{v:08x}{fr}{': ' + ', '.join(bits) if bits else ''}{f'; unknown bits 0x{xm:08x}' if xm else ''}"


def tbcheck(run):
    """[(item, ok, text)] of one run, from tb.txt and args.txt."""
    tb = open(os.path.join(run, 'tb.txt')).read()
    args = open(os.path.join(run, 'args.txt')).read()
    frames = int(plus(args, 'FRAMES', '2'))
    width = int(plus(args, 'WIDTH', '640'))
    height = int(plus(args, 'HEIGHT', '16'))
    late = plus(args, 'RX_LATE', '0') != '0'
    toggle = plus(args, 'STREAM_TOGGLE', '0') != '0'
    sotsync = plus(args, 'PPI_SOTSYNCERR') is not None
    items = []

    done = re.search(r'^TB DONE\s+OK: ', tb, re.M)
    items.append(('done', done is not None, 'TB DONE OK' if done else 'no TB DONE OK line'))

    m = re.search(r'^TB AXIL: errors TX (\d+), R-X (\d+), R-F (\d+)', tb, re.M)
    items.append(('axil', bool(m) and m.groups() == ('0', '0', '0'),
                  f'errors TX {m[1]}, R-X {m[2]}, R-F {m[3]}' if m else 'no TB AXIL line'))

    r = regs(tb)
    x = unknown(tb)
    m = re.search(r'^TB TX: .*\(core ready (reached|NOT reached)\).*, (\d+) frames, (\d+) lines sent', tb, re.M)
    tx_isr = r.get(('TX', 0x24))
    ok = bool(m) and m[1] == 'reached' and int(m[2]) == frames and int(m[3]) == frames * height \
        and tx_isr is not None and (tx_isr | x.get(('TX', 0x24), 0)) & TX_ERR == 0
    items.append(('tx', ok, (f'core ready {m[1]}, {m[2]}/{frames} frames, {m[3]}/{frames * height} lines'
                             f', ISR 0x{tx_isr if tx_isr is not None else 0:08x}') if m else 'no TB TX line'))

    wc = width * 10 // 8
    texts, ok = [], True
    for ss in ('R-X', 'R-F'):
        isr = r.get((ss, 0x24))
        if isr is None:
            ok = False
            texts.append(f'{ss}: no ISR')
            continue
        xm = x.get((ss, 0x24), 0)
        err = any((isr | xm) & m for m in ISR_ERR.values())
        ok &= bool(isr & ISR_FR) and not xm & ISR_FR and not err
        texts.append(f'{ss} ISR {isr_text(isr, xm)}')
    same = all(r.get(('R-F', a)) == r.get(('R-X', a)) and r.get(('R-X', a)) is not None for a in (0x60, 0x64))
    pkt = [r.get((ss, 0x10), 0) >> 16 for ss in ('R-X', 'R-F')]
    info = r.get(('R-X', 0x60), 0), r.get(('R-X', 0x64), 0)
    frame_ok = info[0] & 0xFFFF == wc and info[1] & 0x3F == DT_RAW10
    unk = [f'{ss} 0x{a:02x}' for ss in ('R-X', 'R-F') for a in (0x10, 0x60, 0x64) if x.get((ss, a))]
    ok &= same and pkt[0] == pkt[1] and frame_ok and not unk
    texts.append(f'packet count R-X {pkt[0]} R-F {pkt[1]}; image info VC0 R-X 0x{info[0]:08x} 0x{info[1]:08x}'
                 f" ({'equal' if same else 'NOT equal'} in R-F; word count {info[0] & 0xFFFF} of {wc},"
                 f' data type 0x{info[1] & 0x3F:02x})' + (f"; unknown bits in {', '.join(unk)}" if unk else ''))
    lanes = [f"{ss} " + ' '.join(f'{r.get((ss, a), 0):x}' for a in (0x3C, 0x40, 0x44, 0x48, 0x4C))
             for ss in ('R-X', 'R-F')]
    texts.append('clock/lane info ' + '; '.join(lanes))
    shown = late or toggle or sotsync
    items.append(('regs', ok or shown, ('shown, not judged: ' if shown else '') + '; '.join(texts)))

    ax = {k: (int(b), int(li), int(f)) for k, b, li, f in
          re.findall(r'^TB AXIS (\w+): beats (\d+), lines (\d+), frames (\d+)', tb, re.M)}
    if {'tx', 'xil', 'ftel'} <= set(ax):
        want_f = frames - 1 if late else frames
        ok = ax['tx'][1:] == (frames * height, frames)
        for k in ('xil', 'ftel'):
            if late:
                ok &= ax[k][1] >= want_f * height and ax[k][2] >= want_f
            elif not (sotsync and k == 'ftel'):
                ok &= ax[k][1:] == (frames * height, frames)
        items.append(('axis', ok, ', '.join(f'{k} {v[1]} lines {v[2]} frames' for k, v in ax.items())
                      + ('; ftel shown, not judged' if sotsync else '')))
    else:
        items.append(('axis', False, 'TB AXIS lines missing'))

    m = re.search(r'^TB FRONT END CHECK: .* differ at (\d+) of (\d+) changes', tb, re.M)
    s = re.search(r'^TB FRONT END CHECK START: comparisons (\d+), differences (\d+) up to 2\.5 ps', tb, re.M)
    text = f'{m[1]} differences in {m[2]} changes' if m else 'no TB FRONT END CHECK line'
    text += f' (not counted, up to 2.5 ps: {s[2]} of {s[1]} comparisons differ)' if s else '; no START line'
    items.append(('front', bool(m and s) and m[1] == '0' and int(m[2]) > 0, text))

    dl = re.search(r'^AFE data lanes: .*\(limit [\d.]+, (\d+) late, (\d+) missing\)', tb, re.M)
    cl = re.search(r'^AFE clock lane: .*\(limit [\d.]+, (\d+) late\)', tb, re.M)
    ok = bool(dl and cl) and dl[1] == dl[2] == cl[1] == '0'
    items.append(('afe', ok, f'term_en late {dl[1]}, missing {dl[2]}; clock lane late {cl[1]}'
                  if dl and cl else 'AFE lines missing'))

    if plus(args, 'PPI_CORRUPT'):
        m = re.search(r'^TB CORRUPT: (\d+) bytes flipped', tb, re.M)
        items.append(('corrupt', bool(m) and m[1] == '1', f'{m[1]} bytes flipped' if m else 'no TB CORRUPT line'))
    if plus(args, 'PPI_ADAPTER', '0') != '0':
        g = re.search(r'^TB ADAPTER: rxactivehs into xrxss_np from m_ftel_ppi_act_gate', tb, re.M)
        m = re.search(r'^TB ADAPTER CHECK: comparisons (\d+), differences (\d+)', tb, re.M)
        items.append(('adapter', bool(g and m) and int(m[1]) > 0 and m[2] == '0',
                      (f'the gate against the model of the testbench: {m[1]} comparisons, {m[2]} differences'
                       if m else 'no TB ADAPTER CHECK line') + ('' if g else '; no TB ADAPTER line')))
    if sotsync:
        m = re.search(r'^TB SOTSYNCERR: lane (\d+) packet (\d+): .*, (\d+) events', tb, re.M)
        ok = bool(m) and f'{m[1]},{m[2]}' == plus(args, 'PPI_SOTSYNCERR') and m[3] == '1'
        items.append(('sotsync', ok, f'lane {m[1]} packet {m[2]}: {m[3]} bursts given the SoT sync error' if m
                      else 'no TB SOTSYNCERR line'))
    return items


def print_tbcheck(items):
    for name, ok, text in items:
        print(f"TBCHECK {name:8s} {'ok  ' if ok else 'FAIL'} {text}")
    n_ok = sum(1 for _, ok, _ in items if ok)
    print(f"TBRESULT: {'PASS' if n_ok == len(items) else 'FAIL'} ({n_ok}/{len(items)} items)")
    return n_ok == len(items)


# ---------------------------------------------------------------------------------------------------
# decoder of the captures, written apart from fpga/tools/csi2_dump.py (plan §7, layer 3)

def pattern_line(pattern, f, y, width, height):
    """Pixels of line y of frame f (plan §2.1), as axis_vid_gen.sv makes them."""
    if pattern == 'prbs':
        s = ((1 + f * height + y) & 0x7FFF) or 1
        out = []
        for _ in range(width):
            p = 0
            for _ in range(10):
                nb = ((s >> 14) ^ (s >> 13)) & 1
                s = ((s << 1) | nb) & 0x7FFF
                p = (p << 1) | nb
            out.append(p)
        return out
    if pattern == 'synclike':
        cyc = (0x2E0, 0x2E0, 0x000, 0x000, 0x3FF, 0x3FF, 0x155, 0x2AA)
        return [cyc[x % 8] for x in range(width)]
    return [(x + 37 * y + 101 * f) % 1024 for x in range(width)]


def read_csv(path):
    """(names, rows) of a capture: the line of names, the radix line, then the samples (ppi_csv_mon layout)."""
    with open(path) as fh:
        lines = [line.rstrip('\n').split(',') for line in fh if line.strip()]
    return lines[0], lines[2:]


def axis_frames(cap, after_us=0.0):
    """Frames of an AXI4-Stream capture (names, rows) of axis_csv_mon: [[(pixels, word count, data type) per line]
    per frame], from the beats with tvalid and tready, from the first start of frame at or after after_us; a frame
    starts at a beat with sof, a line ends at tlast. The lines before that start of frame are counted in the
    second value."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    frames, line, before = [], [], 0
    for r in rows:
        if r[col['tvalid']] != '1' or r[col['tready']] != '1':
            continue
        if r[col['sof']] == '1' and (frames or int(r[col['sim_time_ps']]) >= after_us * 1e6):
            frames.append([])
            line = []
        d = int(r[col['tdata']], 16)
        line += [(d >> (10 * k)) & 0x3FF for k in range(4)]
        if r[col['tlast']] == '1':
            if frames:
                frames[-1].append((line, int(r[col['tu_wc']], 16), int(r[col['tu_dt']], 16)))
            else:
                before += 1
            line = []
    return frames, before


def read_frames(path):
    """{frame: (width, height, pattern, [pixels per line])} of frames.txt."""
    out = {}
    for line in open(path):
        f = line.split()
        if f and f[0] == 'F':
            out[int(f[1])] = (int(f[2]), int(f[3]), f[4], [])
        elif f and f[0] == 'L':
            out[int(f[1])][3].append([int(f[3][i:i + 3], 16) for i in range(0, len(f[3]), 3)])
    return out


def ecc6(h):
    """ECC of the 24-bit packet header h (data identifier, word count), from the parity equations of CSI-2."""
    eq = ((0, 1, 2, 4, 5, 7, 10, 11, 13, 16, 20, 21, 22, 23), (0, 1, 3, 4, 6, 8, 10, 12, 14, 17, 20, 21, 22, 23),
          (0, 2, 3, 5, 6, 9, 11, 12, 15, 18, 20, 21, 22), (1, 2, 3, 7, 8, 9, 13, 14, 15, 19, 20, 21, 23),
          (4, 5, 6, 7, 8, 9, 16, 17, 18, 19, 20, 22, 23), (10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23))
    return sum((sum((h >> b) & 1 for b in bits) & 1) << p for p, bits in enumerate(eq))


ECC_COLUMN = {ecc6(1 << b): b for b in range(24)}   # syndrome of one wrong header bit -> that bit


def ecc_fix(h, ecc):
    """(status, header) of the 24-bit packet header h and its ECC byte: 'ok'; 'corrected' when one bit is wrong,
    of the header (then corrected) or of the ECC; 'bad' when more are."""
    s = ecc6(h) ^ (ecc & 0x3F)
    if s == 0:
        return 'ok', h
    if s in ECC_COLUMN:
        return 'corrected', h ^ (1 << ECC_COLUMN[s])
    if s & (s - 1) == 0:
        return 'corrected', h
    return 'bad', h


def crc16_bits(data):
    """CRC-16 of a long-packet payload (x^16 + x^12 + x^5 + 1, LSB first, start 0xFFFF), one bit at a time."""
    crc = 0xFFFF
    for byte in data:
        for k in range(8):
            fb = (crc ^ (byte >> k)) & 1
            crc >>= 1
            if fb:
                crc ^= 0x8408
    return crc


def ppi_packets(cap, lanes):
    """Packets of a PPI capture (names, rows) of ppi_csv_mon: per lane the bursts (runs of rxactivehs) and their
    bytes (samples with rxvalidhs); burst k of every lane makes packet k, byte j coming from lane j mod lanes.
    Each packet is {'dt', 'vc', 'wc', 'ecc' ('ok', 'corrected' or 'bad'), 'trailer'}, with 'payload' for a long
    packet and 'error' ('short burst', 'ECC', 'truncated', 'CRC') when it has one; a header with one wrong bit is
    corrected, as a receiver does. Lanes with different numbers of bursts give one packet with the error 'lanes'."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    bursts = []
    for lane in range(lanes):
        ca, cv, cd = (col[f'dl{lane}_{s}'] for s in ('rxactivehs', 'rxvalidhs', 'rxdatahs'))
        cur, act, out = [], False, []
        for r in rows:
            a = r[ca] == '1'
            if a and r[cv] == '1':
                cur.append(int(r[cd], 16))
            if act and not a:
                out.append(cur)
                cur = []
            act = a
        if act:
            out.append(cur)
        bursts.append(out)
    packets = []
    for k in range(min(len(b) for b in bursts)):
        part = [bursts[lane][k] for lane in range(lanes)]
        n = max(len(p) for p in part) * lanes
        data = [part[j % lanes][j // lanes] if j // lanes < len(part[j % lanes]) else None for j in range(n)]
        if len(data) < 4 or None in data[:4]:
            packets.append({'error': 'short burst'})
            continue
        ecc, h = ecc_fix(data[0] | data[1] << 8 | data[2] << 16, data[3])
        pk = {'dt': h & 0x3F, 'vc': (h >> 6) & 3, 'wc': h >> 8, 'ecc': ecc}
        size = 4 if pk['dt'] <= 0x0F else 4 + pk['wc'] + 2
        if ecc == 'bad':
            pk['error'] = 'ECC'
        elif size > 4:
            body = data[4:size]
            if len(body) < pk['wc'] + 2 or None in body:
                pk['error'] = 'truncated'
            else:
                pk['payload'] = bytes(body[:pk['wc']])
                if crc16_bits(pk['payload']) != body[pk['wc']] | body[pk['wc'] + 1] << 8:
                    pk['error'] = 'CRC'
        pk['trailer'] = sum(len(p) for p in part) - size
        packets.append(pk)
    if len({len(b) for b in bursts}) > 1:
        packets.append({'error': 'lanes'})
    return packets


def raw10_pixels(payload):
    """Pixels of a RAW10 payload: 4 pixels in 5 bytes, bits [9:2] in the first four, bits [1:0] in the fifth."""
    out = []
    for i in range(0, len(payload) - 4, 5):
        b = payload[i:i + 5]
        out += [(b[k] << 2) | ((b[4] >> (2 * k)) & 3) for k in range(4)]
    return out


def ppi_frames(packets):
    """[[pixels per line] per frame] of the RAW10 long packets without an error after each frame start, from the
    first one."""
    frames = []
    for pk in packets:
        if 'error' in pk:
            continue
        if pk['dt'] == 0x00:
            frames.append([])
        elif pk['dt'] == DT_RAW10 and frames:
            frames[-1].append(raw10_pixels(pk['payload']))
    return frames


def from_fs(packets):
    """(virtual channel, data type, word count, payload, error) of the packets from the first frame start."""
    i = next((k for k, p in enumerate(packets) if p.get('dt') == 0x00 and 'error' not in p), len(packets))
    return [(p.get('vc'), p.get('dt'), p.get('wc'), p.get('payload'), p.get('error')) for p in packets[i:]]


def burst_starts(cap, lanes):
    """[(rxsynchs - rxactivehs, first byte - rxsynchs)] in byte clocks for every burst of every lane of a PPI
    capture (names, rows): from the sample where rxactivehs rises to the first with rxsynchs, and from that one to
    the first with rxvalidhs (None when the burst has no rxsynchs or no byte)."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    out = []
    for lane in range(lanes):
        ca, cs, cv = (col[f'dl{lane}_{s}'] for s in ('rxactivehs', 'rxsynchs', 'rxvalidhs'))
        start = sync = byte = None
        for k, r in enumerate(rows + [None]):
            a = r is not None and r[ca] == '1'
            if start is not None and not a:
                out.append((None if sync is None else sync - start,
                            None if sync is None or byte is None else byte - sync))
                start = None
            if a and start is None:
                start, sync, byte = k, None, None
            if a and sync is None and r[cs] == '1':
                sync = k
            if a and byte is None and r[cv] == '1':
                byte = k
    return out


def ppi_timing(cap, lanes, sync_at, max_spread):
    """C6 and C10 of the HAS (Table A-2) in a PPI capture (names, rows), burst k of every lane making packet k as
    in ppi_packets: in each lane burst with a byte, rxsynchs High in one sample, sync_at samples from the first
    byte; in each packet, every byte on all lanes within max_spread samples. Returns (errors, sync offsets, widest
    spread of each packet)."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    per = []
    for lane in range(lanes):
        ca, cv, cs = (col[f'dl{lane}_{s}'] for s in ('rxactivehs', 'rxvalidhs', 'rxsynchs'))
        out, cur = [], None
        for k, r in enumerate(rows + [None]):
            a = r is not None and r[ca] == '1'
            if cur is not None and not a:
                out.append(cur)
                cur = None
            if a:
                cur = cur or ([], [])
                if r[cv] == '1':
                    cur[0].append(k)
                if r[cs] == '1':
                    cur[1].append(k)
        per.append(out)
    errs, offsets, widest = 0, [], []
    for byts, syncs in (b for lane_bursts in per for b in lane_bursts if b[0]):
        off = syncs[0] - byts[0] if len(syncs) == 1 else None
        if off is not None:
            offsets.append(off)
        errs += off != sync_at
    for k in range(min(len(b) for b in per)) if lanes > 1 else []:
        rws = [per[lane][k][0] for lane in range(lanes)]
        n = min(len(x) for x in rws)
        if n:
            widest.append(max(max(x[j] for x in rws) - min(x[j] for x in rws) for j in range(n)))
            errs += widest[-1] > max_spread
    return errs, offsets, widest


def lane_events(cap, lanes):
    """([[(first, last sample) of each run of rxactivehs] per lane], [(lane, sample, rxactivehs)] of the samples
    with errsotsynchs) of a PPI capture (names, rows)."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    runs, errs = [], []
    for lane in range(lanes):
        ca, ce = col[f'dl{lane}_rxactivehs'], col[f'dl{lane}_errsotsynchs']
        out, start = [], None
        for k, r in enumerate(rows):
            a = r[ca] == '1'
            if a and start is None:
                start = k
            elif not a and start is not None:
                out.append((start, k - 1))
                start = None
            if r[ce] == '1':
                errs.append((lane, k, a))
        if start is not None:
            out.append((start, len(rows) - 1))
        runs.append(out)
    return runs, errs


def span(values):
    """'a..b' (or 'a') of the values, 'none' when there are none or one is None."""
    if not values or None in values:
        return 'none' if not values else 'some missing'
    lo, hi = min(values), max(values)
    return f'{lo}' if lo == hi else f'{lo}..{hi}'


_RUNS = {}   # decode_run results by the real path of the run folder (evselftest links the runs)


def decode_run(run):
    """The decode of one run: {'items': [(item, ok, text)] (decode), 'ftel_diffs': [(frame, line, x, got, want)]
    of the pixels of R-F that differ in the lines it gave, 'ftel_odd': lines of R-F missing, extra or of another
    length, 'ftel_lines', 'ftel_frames': [[pixels per line] per frame] of R-F, 'ftel_shape': [word count and RAW10
    in every line] per frame of R-F, 'gold': the frames of the formula, 'corrected': {capture: headers corrected},
    'shape': [(data type, word count, error)] of the packets of R-X, 'starts': {'xil', 'ftel': burst_starts}, and
    with +PPI_SOTSYNCERR 'sotsync': lane_events of ftel_ppi.csv}."""
    key = os.path.realpath(run)
    if key in _RUNS:
        return _RUNS[key]
    args = open(os.path.join(run, 'args.txt')).read()
    tb = open(os.path.join(run, 'tb.txt')).read()
    frames = int(plus(args, 'FRAMES', '2'))
    width = int(plus(args, 'WIDTH', '640'))
    height = int(plus(args, 'HEIGHT', '16'))
    pattern = plus(args, 'PATTERN', 'counter')
    lanes = int(plus(args, 'LANES_ACTIVE', '4'))
    first = 1 if plus(args, 'RX_LATE', '0') != '0' else 0
    wc = width * 10 // 8
    gold = [[pattern_line(pattern, f, y, width, height) for y in range(height)] for f in range(frames)]
    m = re.search(r'^TB RX CFG: R-X set up at ([\d.]+) us .*, R-F set up at ([\d.]+) us', tb, re.M)
    setup = {'xil': float(m[1]), 'ftel': float(m[2])} if m else {'xil': 0.0, 'ftel': 0.0}
    items, res = [], {'corrected': {}}

    ft = read_frames(os.path.join(run, 'frames.txt'))
    ok = sorted(ft) == list(range(frames)) and all(ft[f][:2] == (width, height) and ft[f][3] == gold[f] for f in ft)
    items.append(('frames', ok, f'frames.txt: {len(ft)} frames {"equal to" if ok else "NOT equal to"} the formula'))
    got, before = axis_frames(read_csv(os.path.join(run, 'tx_axis.csv')))
    ok = [[px for px, *_ in fr] for fr in got] == gold
    items.append(('tx-axis', ok, f'tx_axis.csv: {len(got)} frames {"equal to" if ok else "NOT equal to"} the'
                                 f' formula, {before} lines before the first start of frame'))

    for k in ('xil', 'ftel'):
        got, before = axis_frames(read_csv(os.path.join(run, f'{k}_axis.csv')), setup[k])
        want = gold[first:]
        lines_got = [px for fr in got for px, *_ in fr]
        lines_want = [ln for fr in want for ln in fr]
        same = sum(1 for g, w in zip(want, got) if g == [px for px, *_ in w])
        shape = all(w == wc and d == DT_RAW10 for fr in got for _, w, d in fr)
        ok = len(got) == len(want) and same == len(want) and shape
        items.append((f'pixels-{k}', ok, f'{k}_axis.csv from the first start of frame after {setup[k]:.3f} us: '
                                         f'{len(got)} frames, {len(lines_got)} lines, {same} of {len(want)} frames'
                                         f' from frame {first} equal to the formula, word count {wc} and RAW10 in'
                                         f' {"every" if shape else "NOT every"} line; {before} lines before'))
        if k == 'ftel':
            diffs, odd = [], abs(len(lines_got) - len(lines_want))
            per = [len(fr) for fr in want]
            for n, (g, w) in enumerate(zip(lines_got, lines_want)):
                f, y = first, n
                while f - first < len(per) and y >= per[f - first]:
                    y -= per[f - first]
                    f += 1
                if len(g) != len(w):
                    odd += 1
                else:
                    diffs += [(f, y, x, a, b) for x, (a, b) in enumerate(zip(g, w)) if a != b]
            res.update(ftel_diffs=diffs, ftel_odd=odd, ftel_lines=len(lines_got),
                       ftel_frames=[[px for px, *_ in fr] for fr in got],
                       ftel_shape=[all(w == wc and d == DT_RAW10 for _, w, d in fr) for fr in got])

    pk = {}
    for k in ('tx', 'xil', 'ftel'):
        cap = read_csv(os.path.join(run, f'{k}_ppi.csv'))
        pk[k] = ppi_packets(cap, lanes)
        n_late, timing = 0, ''
        if k != 'tx':
            res.setdefault('starts', {})[k] = burst_starts(cap, lanes)
            # rxsynchs of AMD's D-PHY one cycle before the first byte; of ftel_dphy_rx in its cycle, unless the
            # testbench moved it (+PPI_AMD_TIMING=1|2)
            want = -1 if k == 'xil' or plus(args, 'PPI_AMD_TIMING', '0') in ('1', '2') else 0
            n_late, offsets, widest = ppi_timing(cap, lanes, want, LANE_SPREAD)
            timing = (f', rxsynchs {span(sorted(set(offsets)))} samples from the first byte (expected {want}), lane'
                      f' spread {span(widest)} (at most {LANE_SPREAD}), {n_late} timing errors')
            if k == 'ftel' and plus(args, 'PPI_SOTSYNCERR'):
                res['sotsync'] = lane_events(cap, lanes)
        bad = sorted({p['error'] for p in pk[k] if 'error' in p})
        n_bad = sum(1 for p in pk[k] if 'error' in p)
        res['corrected'][k] = sum(1 for p in pk[k] if p.get('ecc') == 'corrected')
        trail = [p['trailer'] for p in pk[k] if 'trailer' in p]
        items.append((f'ppi-{k}', not bad and not n_late, f'{k}_ppi.csv: {len(pk[k])} packets, {n_bad} with an error'
                                                          f'{" " + str(bad) if bad else ""}, {res["corrected"][k]}'
                                                          f' headers corrected, trailer bytes {span(trail)}{timing}'))
    golden = [(k, ppi_frames(pk[k])) for k in ('tx', 'xil')]
    items.append(('golden-ppi', all(g == gold for _, g in golden),
                  '; '.join(f'{k}_ppi.csv: {len(g)} frames {"equal to" if g == gold else "NOT equal to"} the formula'
                            for k, g in golden)))
    for a, b in (('tx', 'xil'), ('xil', 'ftel')):
        x, y = from_fs(pk[a]), from_fs(pk[b])
        n_same = sum(1 for p, q in zip(x, y) if p == q)
        items.append((f'packets-{a}-{b}', bool(x) and x == y, f'{a}_ppi.csv {len(x)} packets from the first frame'
                                                              f' start, {b}_ppi.csv {len(y)}, {n_same} equal in'
                                                              ' order'))
    res['shape'] = [(p.get('dt'), p.get('wc'), 'error' in p) for p in pk['xil']]
    res['gold'] = gold
    res['items'] = items
    _RUNS[key] = res
    return res


def synth_ppi(packets, lanes, early=3, flip=None):
    """A PPI capture (names, rows) carrying the packets (lists of bytes): byte k on lane k % lanes, each burst with
    rxactivehs early samples before rxsynchs, which comes with the first byte (as ftel_dphy_rx); flip=(packet,
    byte, bit) inverts one bit."""
    names = ['Sample in Buffer', 'Sample in Window', 'TRIGGER', 'sim_time_ps'] + \
        [f'dl{n}_{s}' for n in range(lanes) for s in ('rxdatahs[7:0]', 'rxvalidhs', 'rxactivehs', 'rxsynchs')]
    rows = []
    for p, data in enumerate(packets):
        data = list(data)
        if flip and flip[0] == p:
            data[flip[1]] ^= 1 << flip[2]
        per = [data[n::lanes] for n in range(lanes)]
        for k in range(early + max(len(b) for b in per) + 2):
            r = [str(len(rows))] * 2 + ['0', str(1000 * len(rows))]
            for b in per:
                j = k - early
                act = k < early + len(b)
                r += [f'{b[j]:02x}' if 0 <= j < len(b) else '00', '1' if 0 <= j < len(b) else '0',
                      '1' if act else '0', '1' if j == 0 else '0']
            rows.append(r)
    return names, rows


def long_packet(dt, payload):
    """The bytes of a long packet: header with its ECC, payload, CRC."""
    h = dt | len(payload) << 8
    crc = crc16_bits(payload)
    return [h & 0xFF, (h >> 8) & 0xFF, h >> 16, ecc6(h)] + list(payload) + [crc & 0xFF, crc >> 8]


def selftest():
    """The decoder on known values and synthetic captures. True when every case holds."""
    sys.path.insert(0, os.path.join(FPGA, 'tools'))
    import csi2_dump as cd   # written apart: its ECC and CRC are compared on random values
    rnd = random.Random(7)
    cases = []
    vectors = (('FF 00 00 02 B9 DC F3 72 BB D4 B8 5A C8 75 C2 7C 81 F8 05 DF FF 00 00 01', 0x00F0),
               ('FF 00 00 00 1E F0 1E C7 4F 82 78 C5 82 E0 8C 70 D2 3C 78 E9 FF 00 00 01', 0xE569))
    cases.append(('CRC examples of CSI-2 v1.3', all(crc16_bits(bytes.fromhex(v)) == c for v, c in vectors)))
    cases.append(('ECC example of CSI-2 v1.3 (DI 0x37, WC 0x01F0: 0x3F)', ecc6(0x37 | 0xF0 << 8 | 0x01 << 16) == 0x3F))
    hs = [rnd.getrandbits(24) for _ in range(200)]
    cases.append(('ECC equal to csi2_dump.py on 200 random headers', all(ecc6(h) == cd.ecc24(h) for h in hs)))
    data = [bytes(rnd.getrandbits(8) for _ in range(rnd.randint(1, 64))) for _ in range(50)]
    cases.append(('CRC equal to csi2_dump.py on 50 random payloads', all(crc16_bits(d) == cd.crc16(d) for d in data)))
    cases.append(('syndromes of one wrong header bit distinct, of odd weight above 1',
                  len(ECC_COLUMN) == 24 and all(bin(s).count('1') % 2 and s & (s - 1) for s in ECC_COLUMN)))
    one = all(ecc_fix(h ^ (1 << b), ecc6(h)) == ('corrected', h) for h in hs[:20] for b in range(24)) and \
        all(ecc_fix(h, ecc6(h) ^ (1 << b)) == ('corrected', h) for h in hs[:20] for b in range(6))
    cases.append(('one wrong bit of 30 corrected', one))
    two = all(ecc_fix(h ^ (1 << a) ^ (1 << b), ecc6(h))[0] == 'bad' for h in hs[:5] for a in range(24)
              for b in range(a + 1, 24))
    cases.append(('two wrong header bits found', two))

    px = [1, 2, 3, 1023, 512, 0, 7, 600]
    payload = bytes(b for i in range(0, 8, 4) for b in [p >> 2 for p in px[i:i + 4]] +
                    [sum((p & 3) << (2 * k) for k, p in enumerate(px[i:i + 4]))])
    fs, fe = [0x00, 0x00, 0x00, ecc6(0)], [0x01, 0x00, 0x00, ecc6(1)]
    stream = [fs, long_packet(DT_RAW10, payload), fe]
    pk = ppi_packets(synth_ppi(stream, 2), 2)
    cases.append(('synthetic capture: FS, one RAW10 line, FE decoded to its pixels',
                  [p.get('dt') for p in pk] == [0, DT_RAW10, 1] and not any('error' in p for p in pk)
                  and ppi_frames(pk) == [[px]]))
    cases.append(('rxactivehs 3 samples before rxsynchs, first byte with it',
                  set(burst_starts(synth_ppi(stream, 2), 2)) == {(3, 0)}))
    pk = ppi_packets(synth_ppi(stream, 2, flip=(1, 7, 4)), 2)
    cases.append(('a payload bit found by the CRC', pk[1].get('error') == 'CRC' and ppi_frames(pk) == [[]]))
    pk = ppi_packets(synth_ppi(stream, 2, flip=(1, 0, 0)), 2)
    cases.append(('a header bit corrected', pk[1]['ecc'] == 'corrected' and ppi_frames(pk) == [[px]]))
    bad = list(stream[1])
    bad[1] ^= 0x03
    pk = ppi_packets(synth_ppi([fs, bad, fe], 2), 2)
    cases.append(('two header bits found', pk[1].get('error') == 'ECC'))
    pk = ppi_packets(synth_ppi([fs, stream[1][:-3], fe], 2), 2)
    cases.append(('a truncated payload found', pk[1].get('error') == 'truncated'))

    names = ['Sample in Buffer', 'Sample in Window', 'TRIGGER', 'sim_time_ps', 'tdata[39:0]', 'tvalid', 'tready',
             'sof', 'tlast', 'tdest[9:0]', 'tu_frame[15:0]', 'tu_line[15:0]', 'tu_wc[15:0]', 'tu_dt[5:0]']
    beats = [(1000, 1, 1, 1, 9), (2000000, 1, 0, 1, 1), (2001000, 0, 0, 0, 7), (2002000, 0, 1, 1, 0),
             (2003000, 0, 1, 0, 5)]   # (time, sof, tlast, tready, pixel base): beats without tready are not taken
    rows = [['0', '0', '0', str(t), f'{sum((b + k) << (10 * k) for k in range(4)):010x}', '1', str(rd), str(s),
             str(tl), '2b0', '0000', '0000', '0005', '2b'] for t, s, tl, rd, b in beats]
    fr, before = axis_frames((names, rows), 1.5)
    cases.append(('AXI4-Stream: from the first start of frame after 1.5 us, beats without tready left out',
                  before == 1 and fr == [[([1, 2, 3, 4, 0, 1, 2, 3], 5, DT_RAW10)]]))
    for name, ok in cases:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    ok = all(ok for _, ok in cases)
    print(f"selftest: {'PASS' if ok else 'FAIL'}")
    return ok


# ---------------------------------------------------------------------------------------------------
# evidence over all runs

def sources_hash():
    """The hash run_exp2b.sh keeps in build_*/src.sha and in args.txt: sha256sum of the RTL filelist sources,
    exp1/afe_model.sv, exp1/ppi_csv_mon.sv, rtl/m_ftel_ppi_act_gate.sv and exp2b/*.sv, in the order of ls."""
    files = [IP + line.rstrip('\n')[len('${FTEL_DPHY_RX_PATH}'):]
             for line in open(os.path.join(IP, 'logical', 'filelist.f')) if line.startswith('${FTEL_DPHY_RX_PATH}')]
    files += sorted([os.path.join(EXP1, f) for f in ('afe_model.sv', 'ppi_csv_mon.sv')]
                    + [os.path.join(FPGA, 'rtl', 'm_ftel_ppi_act_gate.sv')] + glob.glob(os.path.join(HERE, '*.sv')))
    text = ''.join(f'{hashlib.sha256(open(f, "rb").read()).hexdigest()}  {f}\n' for f in files)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def copy_blocks(tb2=None):
    """[(block, code lines in tb_exp1.sv, differing line pairs or None, as allowed)] of the blocks tb_exp2b.sv (or
    the file tb2) takes from exp1/tb_exp1.sv, lines without comments, blank lines and runs of white space."""
    a = [' '.join(x.split()) for x in tn2a.code_lines(os.path.join(EXP1, 'tb_exp1.sv'))]
    b = [' '.join(x.split()) for x in tn2a.code_lines(tb2 or os.path.join(HERE, 'tb_exp2b.sv'))]
    out = []
    for name, start, end in COPY_BLOCKS:
        x, y = tn2a.block(a, start, end), tn2a.block(b, start, end)
        diff = [(p, q) for p, q in zip(x, y) if p != q] if x and len(x) == len(y) else None
        allowed = sorted(COPY_ALLOWED.get(name, ()))
        out.append((name, len(x), diff, diff is not None and sorted(diff) == allowed))
    return out


def build_params(w, rate):
    """The differences of the EXP2B lines of build_<rate>/vivado.out from BUILD_PARAMS (and SETTLE_1440), as text;
    None when the file is missing."""
    path = os.path.join(w, f'build_{rate}', 'vivado.out')
    if not os.path.exists(path):
        return None
    got = {m[1]: dict(kv.split('=', 1) for kv in m[2].split())
           for m in re.finditer(r'^EXP2B (xtxss|xrxss|xrxss_np): (.*)$', open(path).read(), re.M)}
    out = []
    for ip, want in BUILD_PARAMS.items():
        want = {k: str(rate) if v == 'RATE' else v for k, v in want.items()}
        if rate == 1440 and ip != 'xtxss':
            want['C_HS_SETTLE_NS'] = SETTLE_1440
        out += [f'{ip} {k}={got.get(ip, {}).get(k)} (expected {v})' for k, v in want.items()
                if got.get(ip, {}).get(k) != v]
    return out


def planted(args, lanes, shape):
    """Where the bit of +PPI_CORRUPT=<lane>,<packet>,<byte>,<bit> lands, from the packets of R-X (shape: [(data
    type, word count, error)]): packet p is burst p of the lane, byte j of the lane is byte j * lanes + lane of the
    packet (tb_exp2b.sv). ('header', p, k) for header byte k, ('pixel', p, frame, line, x, mask) for a byte of a
    RAW10 payload, ('crc', p, k) for a CRC byte; None when it lands on no packet."""
    c = re.search(r'\+PPI_CORRUPT=(\d+),(\d+),(\d+),(\d+)', args)
    if not c:
        return None
    lane, p, j, bit = (int(x) for x in c.groups())
    if p >= len(shape) or shape[p][2]:
        return None
    dt, wc, _ = shape[p]
    k = j * lanes + lane
    if k < 4:
        return ('header', p, k)
    if dt != DT_RAW10:
        return None
    if k - 4 >= wc:
        return ('crc', p, k - 4 - wc)
    frame = sum(1 for s in shape[:p] if s[0] == 0x00) - 1
    line = 0
    for s in reversed(shape[:p]):
        if s[0] == 0x00:
            break
        line += s[0] == DT_RAW10
    g, r = divmod(k - 4, 5)
    if r < 4:
        return ('pixel', p, frame, line, 4 * g + r, 1 << (bit + 2))
    return ('pixel', p, frame, line, 4 * g + bit // 2, 1 << (bit % 2))


def neg_checks(info):
    """{test: (ok, text)} of the three negative tests (check neg), from info[run] = (tbcheck items, check.txt
    items, decode_run, args, tb)."""
    out = {}
    for kind in ('ecc', 'crc', 'front'):
        name = f'{SHIM}NEG-{kind}'
        if name not in info or info[name][2] is None:
            out[name] = (False, 'not run or not decoded')
            continue
        items, cits, dec, args, tb = info[name]
        fails_tb = sorted(n for n, (ok, _) in items.items() if not ok)
        fails_ck = sorted(n for n, v in cits.items() if v == 'FAIL')
        r, x = regs(tb), unknown(tb)
        rx, rf = r.get(('R-X', 0x24), 0), r.get(('R-F', 0x24), 0)
        rx_clean = not any((rx | x.get(('R-X', 0x24), 0)) & m for m in ISR_ERR.values())
        if kind == 'front':
            m = re.search(r'^TB FRONT END CHECK: .* differ at (\d+) of (\d+) changes', tb, re.M)
            rx_items = [n for n in ('pixels-xil', 'ppi-tx', 'ppi-xil', 'packets-tx-xil') if cits.get(n) != 'PASS']
            ok = bool(m) and int(m[1]) > 0 and not items['front'][0] and not rx_items
            out[name] = (ok, f'{m[1] if m else "?"} differences in {m[2] if m else "?"} changes, R-X'
                             f' {"passes" if not rx_items else "fails " + str(rx_items)}; reported only, behind the'
                             f' changed buffers: ftel_dphy_rx {", ".join(n + " " + v for n, v in cits.items() if "ftel" in n)},'
                             f' afe_model {items["afe"][1]}')
            continue
        lanes = int(plus(args, 'LANES_ACTIVE', '4'))
        where = planted(args, lanes, dec['shape'])
        corrupt = items.get('corrupt', (False, 'no corrupt item'))
        if kind == 'ecc':
            ok = (bool(where) and where[0] == 'header' and not fails_ck and fails_tb == ['regs'] and corrupt[0]
                  and bool(rf & ISR_ERR['ECC 1 bit']) and rx_clean and dec['corrected']['ftel'] == 1
                  and dec['corrected']['xil'] == 0)
            out[name] = (ok, f'planted in {f"header byte {where[2]} of packet {where[1]}" if where else "?"} '
                             f'({corrupt[1]}): {dec["corrected"]["ftel"]} header corrected on the PPI of R-F, check.txt'
                             f' {"passes" if not fails_ck else "fails " + str(fails_ck)}, R-F ISR {isr_text(rf)},'
                             f' R-X ISR {isr_text(rx)}, tbcheck failing {fails_tb}')
        else:
            diffs = dec['ftel_diffs']
            hit = bool(where) and where[0] == 'pixel' and len(diffs) == 1 and dec['ftel_odd'] == 0 \
                and diffs[0][:3] == where[2:5] and diffs[0][3] == diffs[0][4] ^ where[5]
            ok = (hit and fails_ck == ['packets-xil-ftel', 'pixels-ftel', 'ppi-ftel'] and fails_tb == ['regs']
                  and corrupt[0] and bool(rf & ISR_ERR['CRC']) and rx_clean)
            exp = (f'frame {where[2]} line {where[3]} pixel {where[4]} xor 0x{where[5]:03x}'
                   if where and where[0] == 'pixel' else str(where))
            seen = '; '.join(f'frame {f} line {y} pixel {px}: 0x{a:03x} for 0x{b:03x}' for f, y, px, a, b in diffs[:3])
            out[name] = (ok, f'planted ({corrupt[1]}) in {exp}; wrong pixels of R-F: {len(diffs)} ({seen}), lines'
                             f' missing or of another length {dec["ftel_odd"]}; check.txt failing {fails_ck}, R-F ISR'
                             f' {isr_text(rf)}, R-X ISR {isr_text(rx)}, tbcheck failing {fails_tb}')
    return out


def finding_checks(info, names):
    """(ok, text, details) of the finding (check finding), from info as neg_checks."""
    details, ok = [], True
    plain = [n for n in names if re.match(r'(M_)?E2b-', n)]
    diag = [n for n in names if n in DIAG]
    shim = [n for n in names if n.startswith(SHIM) and n != f'{SHIM}NEG-front']
    missing = [n for n in (*FINDING, *DIAG) if n not in names]
    if missing:
        ok = False
        details.append(f'missing {missing}')
    per_rate = {}
    for name in plain + diag + shim:
        items, cits, dec, args, tb = info[name]
        if dec is None:
            ok = False
            details.append(f'{name}: not decoded')
            continue
        st = dec['starts']
        r = regs(tb)
        rf_pkt = r.get(('R-F', 0x10), 0) >> 16
        rf_fr = bool(r.get(('R-F', 0x24), 0) & ISR_FR)
        early = [s for s, _ in st['ftel']]
        together_f = bool(early) and all(s == 0 for s in early)
        before_f = bool(early) and all(s is not None and s > 0 for s in early)
        together_x = bool(st['xil']) and all(s == 0 for s, _ in st['xil'])
        passes = all(v == 'PASS' for v in cits.values()) and all(v for v, _ in items.values())
        nothing = dec['ftel_lines'] == 0 and rf_pkt == 0 and not rf_fr
        if name in plain:
            judged = plus(args, 'RX_LATE', '0') == '0' and plus(args, 'STREAM_TOGGLE', '0') == '0'
            fails_ck = sorted(n for n, v in cits.items() if v == 'FAIL')
            fails_tb = sorted(n for n, (v, _) in items.items() if not v)
            good = (fails_ck == ['pixels-ftel'] and fails_tb == (['axis', 'regs'] if judged else ['axis'])
                    and nothing and before_f and together_x and not plus(args, 'PPI_AMD_TIMING'))
            rate = int(re.search(r'^\S+: (\d+) Mb/s', args, re.M)[1])
            p = per_rate.setdefault(rate, [[], [], [], [], 0])
            p[0] += early
            p[1] += [b for _, b in st['ftel']]
            p[2] += [s for s, _ in st['xil']]
            p[3] += [b for _, b in st['xil']]
            p[4] += 1
            if not good:
                details.append(f'{name}: check.txt failing {fails_ck}, tbcheck failing {fails_tb}, R-F lines'
                               f' {dec["ftel_lines"]}, packet count {rf_pkt}, rxsynchs - rxactivehs ftel'
                               f' {span(early)} AMD {span([s for s, _ in st["xil"]])}')
        elif name in diag:
            good = (passes and together_f) if DIAG[name] else (nothing and before_f)
            details.append(f'{name}: R-F {"passes" if passes else "gives " + str(dec["ftel_lines"]) + " lines"},'
                           f' rxsynchs - rxactivehs into R-F {span(early)} byte clocks, first byte after rxsynchs'
                           f' {span([b for _, b in st["ftel"]])}{"" if good else " (NOT as expected)"}')
        else:
            good = together_f
            if not good:
                details.append(f'{name}: rxsynchs - rxactivehs into R-F {span(early)} byte clocks')
        ok &= good
    rates = '; '.join(f'{r} Mb/s ({p[4]} runs): ftel_dphy_rx {span(p[0])} byte clocks, first byte {span(p[1])}'
                      f' after rxsynchs, AMD\'s D-PHY {span(p[2])}, first byte {span(p[3])} after'
                      for r, p in sorted(per_rate.items()))
    text = (f'not re-timed ({len(plain)} runs): R-X passes, R-F gets the packets of R-X and gives no line, counts no'
            f' packet; rxsynchs - rxactivehs at the start of every burst: {rates or "no run"}; diagnosis'
            f' {len(diag)} runs; through the gate ({len(shim)} runs): rxactivehs into R-F with rxsynchs in every'
            ' burst')
    return ok and bool(plain), text, details


def gate_checks(info, names):
    """(ok, text, details) of the gate (check gate), from info as neg_checks."""
    details, ok, n_cmp = [], True, 0
    shim = [n for n in names if n.startswith(SHIM)]
    for name in shim:
        items, tb = info[name][0], info[name][4]
        m = re.search(r'^TB ADAPTER CHECK: comparisons (\d+), differences (\d+)', tb, re.M)
        if 'adapter' in items and items['adapter'][0]:
            n_cmp += int(m[1])
        else:
            ok = False
            details.append(f'{name}: {items["adapter"][1] if "adapter" in items else "no gate (+PPI_ADAPTER=1)"}')
    text = f'rxactivehs into R-F from the gate in {len(shim)} SH_ runs, {n_cmp} byte clocks equal to the model'
    name = SHIM + SOTSYNC
    if name not in info or info[name][2] is None:
        return False, f'{text}; {name} not run or not decoded', details
    items, cits, dec, args, tb = info[name]
    sel = re.fullmatch(r'(\d+),(\d+)', plus(args, 'PPI_SOTSYNCERR', ''))
    if not sel or plus(args, 'PPI_ADAPTER', '0') == '0':
        return False, f'{text}; {name} without +PPI_SOTSYNCERR=<lane>,<packet> or the gate', details
    lane, pkt = int(sel[1]), int(sel[2])
    lanes = int(plus(args, 'LANES_ACTIVE', '4'))
    for it in ('done', 'sotsync'):
        if not items[it][0]:
            ok = False
            details.append(f'{name}: {it} {items[it][1]}')
    # where the error is: frame and line of packet pkt, from the packets of R-X (as planted() for +PPI_CORRUPT)
    shape = dec['shape']
    f_err = sum(1 for s in shape[:pkt + 1] if s[0] == 0x00) - 1
    y_err = 0
    for s in shape[:pkt]:
        if s[0] == 0x00:
            y_err = 0
        elif s[0] == DT_RAW10:
            y_err += 1
    where = (f'packet {pkt} ({"line " + str(y_err) + " of frame " + str(f_err) if pkt < len(shape) and
                                shape[pkt][0] == DT_RAW10 else "not a line"})')
    # the PPI into R-F: the lane one burst fewer than the others, errsotsynchs once, inside packet pkt of the other
    # lanes (LANE_SPREAD samples before its start at most), with rxactivehs of the lane Low
    runs, errs = dec.get('sotsync', ([], []))
    n_b = [len(b) for b in runs]
    others = [x for x in range(lanes) if x != lane]
    inside = len(errs) == 1 and all(pkt < n_b[x] and runs[x][pkt][0] - LANE_SPREAD <= errs[0][1] <= runs[x][pkt][1]
                                    for x in others)
    ppi_ok = (len(n_b) == lanes and lane < lanes and all(n_b[x] == n_b[lane] + 1 for x in others) and inside
              and errs[0][0] == lane and not errs[0][2])
    if not ppi_ok:
        ok = False
        details.append(f'{name}: ftel_ppi.csv bursts per lane {n_b}, errsotsynchs (lane, sample, rxactivehs)'
                       f' {errs[:4]}')
    # R-X: its items of check.txt and its registers
    rx_fail = [n for n in ('pixels-xil', 'ppi-tx', 'ppi-xil', 'packets-tx-xil') if cits.get(n) != 'PASS']
    r, x = regs(tb), unknown(tb)
    rx, rxm = r.get(('R-X', 0x24), 0), x.get(('R-X', 0x24), 0)
    rx_ok = not rx_fail and bool(rx & ISR_FR) and not rxm & ISR_FR and not any((rx | rxm) & m for m in ISR_ERR.values())
    if not rx_ok:
        ok = False
        details.append(f'{name}: R-X check.txt failing {rx_fail}, ISR {isr_text(rx, rxm)}')
    # R-F: the frames after the one with the error as the formula, each line with the word count and RAW10
    got, gold, sh = dec['ftel_frames'], dec['gold'], dec['ftel_shape']
    after = gold[f_err + 1:]
    k0 = len(got) - len(after)
    rec = bool(after) and k0 >= 0 and got[k0:] == after and all(sh[k0:])
    if not rec:
        ok = False
        same = k0 >= 0 and got[k0:] == after
        details.append(f'{name}: R-F gives {len(got)} frames, the last {len(after)}'
                       f' {"equal to" if same else "NOT equal to"} frames {f_err + 1} to {len(gold) - 1} of the formula'
                       + ('' if all(sh[max(k0, 0):]) else ', word count or data type wrong'))
    before = '; '.join(f'{len(fr)} lines, {sum(1 for ln in fr if ln in gold[f_err])} of them lines of frame {f_err},'
                       f' its lines {[y for y, ln in enumerate(gold[f_err]) if ln not in fr]} missing'
                       for fr in got[:max(k0, 0)]) or 'none'
    rf, rfm = r.get(('R-F', 0x24), 0), x.get(('R-F', 0x24), 0)
    pk = [r.get((ss, 0x10), 0) >> 16 for ss in ('R-X', 'R-F')]
    text += (f'; {name}: SoT sync error on lane {lane} in {where}: ftel_ppi.csv bursts per lane {n_b}, errsotsynchs at'
             f' sample {errs[0][1] if errs else "?"} with rxactivehs {"Low" if errs and not errs[0][2] else "High"}'
             f' ({"as planted" if ppi_ok else "NOT as planted"}); R-X {"passes" if rx_ok else "fails"}; R-F gives'
             f' frames {f_err + 1} to {len(gold) - 1} as the formula: {"yes, it recovers" if rec else "NO"}, TB DONE'
             f' {"OK" if items["done"][0] else "missing"}; reported: before them R-F gives {before}; R-F ISR'
             f' {isr_text(rf, rfm)}; packet count R-X {pk[0]}, R-F {pk[1]}')
    return ok, text, details


_SELF = {}   # results that do not change while evselftest plants faults: the two selftests


def evidence(w, tb2=None):
    """The checks of the evidence over the runs in w ({check: passed}); tb2 replaces tb_exp2b.sv in the check
    copy."""
    if EXP1 not in sys.path:
        sys.path.insert(0, EXP1)
    import tn1_evidence as tn1   # the configuration model and the fields of TB FTEL CFG
    with open(tn1.vc.YAML_DEFAULT, 'rb') as f:
        model = tn1.vc.Model(tn1.vc.yaml.safe_load(f.read()))
    names = sorted(os.path.basename(os.path.dirname(c)) for c in glob.glob(os.path.join(w, '*', 'check.txt')))
    judged = [n for n in names if n.startswith(SHIM) and not n[len(SHIM):].startswith('NEG-')]
    known = [n for n in names if n.startswith(SHIM) or re.match(r'(M_)?E2b-', n) or n in DIAG]
    other = [n for n in names if n not in known]
    results = {}

    def report(name, ok, text, details=()):
        results[name] = ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:8s} {text}")
        for d in list(details)[:12]:
            print(f'          {d}')

    if 'checker' not in _SELF:
        st = subprocess.run([sys.executable, os.path.join(FPGA, 'tools', 'csi2_dump.py'), 'selftest'],
                            capture_output=True, text=True)
        _SELF['checker'] = st.returncode == 0 and 'selftest: PASS' in st.stdout
        with contextlib.redirect_stdout(io.StringIO()):
            _SELF['decoder'] = selftest()
    report('checker', _SELF['checker'], 'csi2_dump.py selftest (planted faults found, clean capture passes)')

    cur = sources_hash()
    bad = {k: [] for k in ('decode', 'runs', 'regs', 'front', 'afe', 'config', 'sources')}
    info, shown, unk, builds = {}, [], {}, {}
    n_item = n_same = n_fe = n_changes = n_model = 0
    start_diff = []
    for name in known:
        run = os.path.join(w, name)
        args, tb, check = (open(os.path.join(run, f)).read() if os.path.exists(os.path.join(run, f)) else ''
                           for f in ('args.txt', 'tb.txt', 'check.txt'))
        items = {n: (ok, text) for n, ok, text in tbcheck(run)}
        cits = dict(re.findall(r'^ITEM (\S+) (PASS|FAIL)', check, re.M))
        try:
            dec = decode_run(run)
        except (OSError, ValueError, KeyError, IndexError) as e:
            dec = None
            bad['decode'].append(f'{name}: not decoded ({e!r})')
        info[name] = (items, cits, dec, args, tb)

        if dec:
            d = {n: (ok, text) for n, ok, text in dec['items']}
            for it, verdict in cits.items():
                n_item += 1
                if it not in d:
                    bad['decode'].append(f'{name}: no decode item {it}')
                elif d[it][0] != (verdict == 'PASS'):
                    bad['decode'].append(f'{name}/{it}: decode {"PASS" if d[it][0] else "FAIL"}, check.txt {verdict}:'
                                         f' {d[it][1]}')
                else:
                    n_same += 1
            for it in ('frames', 'tx-axis', 'golden-ppi'):
                if not d[it][0]:
                    bad['decode'].append(f'{name}/{it}: {d[it][1]}')

        if not items['done'][0]:
            bad['runs'].append(f'{name}: {items["done"][1]}')
        if name in judged:
            failing = [n for n, (ok, _) in items.items() if not ok]
            result = re.search(r'^RESULT: .*', check, re.M)
            # SH_E2b-9: check.txt fails on R-F by design; check gate judges the run
            if failing or not result or not (result[0].startswith('RESULT: PASS') or name == SHIM + SOTSYNC):
                bad['runs'].append(f'{name}: {result[0] if result else "no RESULT"}; tbcheck failing {failing}')
            if items['regs'][1].startswith('shown, not judged'):
                r = regs(tb)
                shown.append(f'{name}: R-X ISR {isr_text(r.get(("R-X", 0x24), 0))}, R-F ISR'
                             f' {isr_text(r.get(("R-F", 0x24), 0))}')
            elif not items['regs'][0]:
                bad['regs'].append(f'{name}: {items["regs"][1]}')
        for (ss, a), mask in unknown(tb).items():
            unk.setdefault(f'{ss} 0x{a:02x} 0x{mask:08x}', []).append(name)

        if not name.endswith('NEG-front'):
            fe = re.search(r'^TB FRONT END: ftel_dphy_rx behind\s+(\S+)', tb, re.M)
            want_fe = 'afe_model' if '+AFE=model' in args else 'IBUFDS_DPHY'
            n_model += want_fe == 'afe_model'
            if not fe or fe[1] != want_fe:
                bad['front'].append(f'{name}: behind {fe[1] if fe else "?"}, expected {want_fe}')
            chk = re.search(r'^TB FRONT END CHECK: .* differ at (\d+) of (\d+) changes', tb, re.M)
            start = re.search(r'^TB FRONT END CHECK START: comparisons (\d+), differences (\d+)', tb, re.M)
            if items['front'][0]:
                n_fe += 1
                n_changes += int(chk[2])
                if int(start[2]):
                    start_diff.append(f'{name} {start[2]}/{start[1]}')
            else:
                bad['front'].append(f'{name}: {items["front"][1]}')
            if not items['afe'][0]:
                bad['afe'].append(f'{name}: {items["afe"][1]}')

        m = re.search(r'^\S+: (\d+) Mb/s', args, re.M)
        rate = int(m[1]) if m else 0
        cfg = re.search(r'^TB FTEL CFG: hs_settle_cyc (\d+), clk_settle_cyc (\d+), eot_skip_bytes (\d+), '
                        r'tinit_cyc (\d+)', tb, re.M)
        want = {'hs_settle_cyc': model.hs_settle(float(rate)), 'clk_settle_cyc': model.clk_settle(),
                'eot_skip_bytes': model.eot_skip(float(rate)), 'tinit_cyc': None}
        for i, (field, pn) in enumerate(tn1.FIELDS):
            exp = int(plus(args, pn)) if plus(args, pn) else want[field]
            if not cfg or (exp is not None and int(cfg[i + 1]) != exp):
                bad['config'].append(f'{name} {field} {cfg[i + 1] if cfg else "?"} (expected {exp})')
        if rate not in builds:
            builds[rate] = build_params(w, rate)
            if builds[rate] is None:
                bad['config'].append(f'build_{rate}/vivado.out missing')
            else:
                bad['config'] += [f'build_{rate}: {x}' for x in builds[rate]]

        src = re.search(r'^sources (\S+)$', args, re.M)
        if not src or src[1] != cur:
            bad['sources'].append(f'{name}: {src[1] if src else "no sources line"}')

    want_runs = [*(SHIM + s for s in SCENARIOS), *(SHIM + 'M_' + s for s in MODEL), *(SHIM + n for n in NEGATIVE),
                 *FINDING, *DIAG]
    missing = [n for n in want_runs if n not in names]
    report('decode', n_item > 0 and not bad['decode'] and _SELF['decoder'],
           f'{n_same}/{n_item} items of check.txt in {len(known)} runs with the same verdict decoded again; frames,'
           f' tx-axis and golden-ppi pass in every run; decoder selftest {"PASS" if _SELF["decoder"] else "FAIL"}',
           bad['decode'])
    report('runs', not missing and not bad['runs'],
           f'{len(known)} runs: {len(SCENARIOS)} scenarios through the gate, {len(MODEL)} behind afe_model,'
           f' {len(NEGATIVE)} negative tests, {len(FINDING) + len(DIAG)} of the finding'
           f' {"all there" if not missing else "missing " + str(missing)}; TB DONE OK in every run; every SH_'
           f' scenario PASS in check.txt and tbcheck ({SHIM + SOTSYNC}: tbcheck, its check.txt in check gate)'
           + (f'; not judged: {other}' if other else ''), bad['runs'])
    unk_text = '; '.join(f'{k} in {len(v)} runs' for k, v in sorted(unk.items())) or 'none'
    report('regs', bool(judged) and not bad['regs'],
           f'{len(judged) - len(shown)} SH_ scenarios: frame received and no error bit in both receivers, R-F with'
           f' the packet count and image information of R-X; shown only: {len(shown)}; unknown (X) register bits:'
           f' {unk_text}', bad['regs'] + shown + [f'{k}: all but {sorted(set(known) - set(v))}'
                                                  if len(v) > len(known) / 2 else f'{k}: {v}'
                                                  for k, v in sorted(unk.items())])
    report('front', n_fe > 0 and not bad['front'],
           f'{n_fe} runs with equal LP outputs of the two front ends at every change after 2.5 ps ({n_changes}'
           f' changes); up to 2.5 ps, not counted, differences in {start_diff if start_diff else "no run"};'
           f' ftel_dphy_rx behind afe_model in the {n_model} runs with +AFE=model (NEG-front: see neg)',
           bad['front'])
    n_afe = len([n for n in known if not n.endswith('NEG-front')])
    report('afe', not bad['afe'], f'{n_afe - len(bad["afe"])}/{n_afe} runs without late or missing term_en'
           ' (NEG-front: see neg)', bad['afe'])
    report('config', not bad['config'],
           f'{len(known)} runs with the configuration of the model or of the scenario; builds'
           f' {sorted(builds)} with the parameters of PLAN_TN2B.md §4.2', bad['config'])
    report('sources', bool(known) and not bad['sources'],
           f'{len(known) - len(bad["sources"])}/{len(known)} runs made from the current sources (hash {cur})',
           bad['sources'])
    blocks = copy_blocks(tb2)
    report('copy', all(ok for *_, ok in blocks),
           '; '.join(f'{b} {n} code lines, {"?" if d is None else len(d)} different'
                     f' {"as allowed" if ok else "NOT as allowed"}' for b, n, d, ok in blocks)
           + ' (tb_exp2b.sv against exp1/tb_exp1.sv)',
           [f'{b}: {p} -> {q}' for b, _, d, ok in blocks if not ok and d for p, q in d])
    neg = neg_checks(info)
    report('neg', all(ok for ok, _ in neg.values()), '; '.join(f'{n}: {"as planted" if ok else "NOT as planted"}'
                                                                for n, (ok, _) in neg.items()),
           [f'{n}: {t}' for n, (_, t) in neg.items()])
    f_ok, f_text, f_details = finding_checks(info, known)
    report('finding', f_ok, f_text, f_details)
    g_ok, g_text, g_details = gate_checks(info, known)
    report('gate', g_ok, g_text, g_details)
    ok = all(results.values())
    print(f"EVIDENCE: {'PASS' if ok else 'FAIL'} ({sum(results.values())}/{len(results)} checks)")
    return results


def flip_pixel(text, frame=0):
    """The AXI4-Stream capture with the lowest bit of the first pixel of a frame inverted: at the start of frame
    number frame (0: the first) among the beats with sof, tvalid and tready."""
    lines = text.split('\n')
    head = lines[0].split(',')
    d, s, v, r = (head.index(n) for n in ('tdata[39:0]', 'sof', 'tvalid', 'tready'))
    for i in range(2, len(lines)):
        f = lines[i].split(',')
        if len(f) > max(d, s, v, r) and f[s] == f[v] == f[r] == '1':
            if frame == 0:
                f[d] = f'{int(f[d], 16) ^ 1:010x}'
                lines[i] = ','.join(f)
                break
            frame -= 1
    return '\n'.join(lines)


def drop_line(text):
    """The AXI4-Stream capture without the beats of the second line after the first start of frame."""
    lines = text.split('\n')
    head = lines[0].split(',')
    s, t = head.index('sof'), head.index('tlast')
    out, state = lines[:2], 0   # 0: before the first start of frame, 1: line 0, 2: line 1 (left out), 3: after
    for line in lines[2:]:
        f = line.split(',')
        if len(f) > t:
            if state == 0 and f[s] == '1':
                state = 1
            keep = state != 2
            if f[t] == '1' and state in (1, 2):
                state += 1
            if not keep:
                continue
        out.append(line)
    return '\n'.join(out)


def flip_ppi(text):
    """The PPI capture with the lowest bit of the second byte of lane 0 in its second burst inverted (a payload
    byte of the first long packet)."""
    lines = text.split('\n')
    head = lines[0].split(',')
    d, v, a = head.index('dl0_rxdatahs[7:0]'), head.index('dl0_rxvalidhs'), head.index('dl0_rxactivehs')
    burst, byte, act = -1, 0, False
    for i in range(2, len(lines)):
        f = lines[i].split(',')
        if len(f) <= a:
            continue
        if f[a] == '1' and not act:
            burst, byte = burst + 1, 0
        act = f[a] == '1'
        if act and f[v] == '1':
            if burst == 1 and byte == 1:
                f[d] = f'{int(f[d], 16) ^ 1:02x}'
                lines[i] = ','.join(f)
                break
            byte += 1
    return '\n'.join(lines)


def raise_active(text):
    """The PPI capture with rxactivehs of lane 0 High from its errsotsynchs to the end of the burst of lane 1: the
    burst with the SoT sync error let through, as without the gate."""
    lines = text.split('\n')
    head = lines[0].split(',')
    a0, e0, a1 = head.index('dl0_rxactivehs'), head.index('dl0_errsotsynchs'), head.index('dl1_rxactivehs')
    on = False
    for i in range(2, len(lines)):
        f = lines[i].split(',')
        if len(f) <= max(a0, e0, a1):
            continue
        on = (on or f[e0] == '1') and f[a1] == '1'
        if on:
            f[a0] = '1'
            lines[i] = ','.join(f)
    return '\n'.join(lines)


WRAP_LINE = '.i_dphy_rx_core_clk              (core_clk),'   # a line of the copied instance of the wrap
EV_FAULTS = (   # (fault, entry of the folder (None: tb_exp2b.sv), file, change of its text, checks that must fail)
    ('none', None, None, None, []),
    ('a pixel of video_out', 'SH_E2b-1', 'ftel_axis.csv', flip_pixel, ['decode']),
    ('a line missing from video_out', 'SH_E2b-1', 'xil_axis.csv', drop_line, ['decode']),
    ('a payload bit on the PPI', 'SH_E2b-1', 'ftel_ppi.csv', flip_ppi, ['decode']),
    # the faults a tester of the FPGA team planted in copies of captures (2026-10-26); rxsynchs two bytes late also
    # opens a gap from rxactivehs, which the check of the finding sees in the re-timed runs
    ('rxsynchs High for three cycles', 'SH_E2b-1', 'ftel_ppi.csv', lambda s: tn2a.tn1_module().sync_wide(s),
     ['decode']),
    ('rxsynchs with the third payload byte', 'SH_E2b-1', 'ftel_ppi.csv', lambda s: tn2a.tn1_module().sync_late(s),
     ['decode', 'finding']),
    ('lane 3 eight cycles later', 'SH_E2b-1', 'ftel_ppi.csv', lambda s: tn2a.tn1_module().lane_late(s),
     ['decode']),
    ('an error bit in a register', 'SH_E2b-1', 'tb.txt',
     lambda s: re.sub(r'^TB REG R-F 0x24 0x\S+$', 'TB REG R-F 0x24 0x80020200', s, flags=re.M), ['regs', 'runs']),
    ('a front-end difference', 'SH_E2b-1', 'tb.txt', lambda s: s.replace('differ at 0 of', 'differ at 1 of'),
     ['front', 'runs']),
    ('a late term_en', 'SH_E2b-1', 'tb.txt', lambda s: s.replace('0 late, 0 missing', '1 late, 0 missing', 1),
     ['afe', 'runs']),
    ('another eot_skip_bytes', 'SH_E2b-1', 'tb.txt', lambda s: s.replace('eot_skip_bytes 13', 'eot_skip_bytes 12'),
     ['config']),
    ('another parameter of a build', 'build_1440', 'vivado.out',
     lambda s: s.replace('VFB_TU_WIDTH=96', 'VFB_TU_WIDTH=64', 1), ['config']),
    ('another sources hash', 'SH_E2b-1', 'args.txt',
     lambda s: re.sub(r'^sources \S+$', 'sources 0000000000000000', s, flags=re.M), ['sources']),
    ('a run missing', 'SH_E2b-3', None, None, ['runs']),
    ('another bit planted in NEG-crc', 'SH_NEG-crc', 'args.txt',
     lambda s: s.replace('+PPI_CORRUPT=1,1,2,3', '+PPI_CORRUPT=1,1,2,4'), ['neg']),
    ('R-F counts packets without the re-timing', 'E2b-1', 'tb.txt',
     lambda s: re.sub(r'^TB REG R-F 0x10 0x\S+$', 'TB REG R-F 0x10 0x00200000', s, flags=re.M), ['finding']),
    ('a changed line of the copied code', None, 'tb_exp2b.sv',
     lambda s: s.replace(WRAP_LINE, WRAP_LINE.replace('(core_clk)', '(tx_core_clk)')), ['copy']),
    # the gate (fpga/PLAN_TN2B_GATE.md §4)
    ('a difference of the gate from its model', 'SH_E2b-1', 'tb.txt',
     lambda s: re.sub(r'^(TB ADAPTER CHECK: comparisons \d+), differences 0$', r'\1, differences 1', s, flags=re.M),
     ['gate', 'runs']),
    ('a pixel of R-F after the SoT sync error', SHIM + SOTSYNC, 'ftel_axis.csv', lambda s: flip_pixel(s, 1),
     ['gate']),
    ('rxactivehs in the burst with the SoT sync error', SHIM + SOTSYNC, 'ftel_ppi.csv', raise_active,
     ['finding', 'gate']),
)


def evselftest(w):
    """evidence() with each fault of EV_FAULTS planted in turn: the entries of w (runs and builds) are linked into
    a temporary folder, the one changed is copied there (of a build only the file changed). True when every fault
    fails exactly its checks."""
    entries = sorted(os.listdir(w))
    ok_all = True
    for fault, entry, name, change, want in EV_FAULTS:
        with tempfile.TemporaryDirectory() as d:
            done, tb2 = change is None, None
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
                done = new != text
                with open(path, 'w') as f:
                    f.write(new)
            if entry is None and change is not None:
                tb2 = os.path.join(d, name)
                text = open(os.path.join(HERE, name)).read()
                new = change(text)
                done = new != text
                with open(tb2, 'w') as f:
                    f.write(new)
            with contextlib.redirect_stdout(io.StringIO()):
                res = evidence(d, tb2)
        failing = sorted(k for k, ok in res.items() if not ok)
        ok = done and failing == sorted(want)
        ok_all &= ok
        print(f"  {'ok  ' if ok else 'FAIL'} {fault}{'' if done else ' (not planted)'}: failing checks"
              f" {failing}, expected {sorted(want)}")
    print(f"evselftest: {'PASS' if ok_all else 'FAIL'}")
    return ok_all


def axis_times(cap):
    """(times of the beats with sof, times of the beats with tlast) in ns of an AXI4-Stream capture (names, rows),
    beats with tvalid and tready."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    sof, eol = [], []
    for r in rows:
        if r[col['tvalid']] == '1' and r[col['tready']] == '1':
            t = int(r[col['sim_time_ps']]) / 1000.0
            if r[col['sof']] == '1':
                sof.append(t)
            if r[col['tlast']] == '1':
                eol.append(t)
    return sof, eol


def tx_bursts(cap):
    """[(start, end)] in ns of the bursts (runs of txrequesths) of lane 0 of the TX capture (names, rows)."""
    names, rows = cap
    col = {n.split('[')[0]: i for i, n in enumerate(names)}
    ca, ct = col['dl0_rxactivehs'], col['sim_time_ps']
    out, start = [], None
    for r in rows:
        a = r[ca] == '1'
        if a and start is None:
            start = int(r[ct]) / 1000.0
        elif not a and start is not None:
            out.append((start, int(r[ct]) / 1000.0))
            start = None
    return out


def rng(values, fmt='{:.0f}'):
    """'a..b' (or 'a') of numbers, '-' when there are none."""
    if not values:
        return '-'
    lo, hi = fmt.format(min(values)), fmt.format(max(values))
    return lo if lo == hi else f'{lo}..{hi}'


REPORT_TX = ('init_done', 'enabled', 'first beat', 'HS clock requested', 'HS at R-X', 'HS at R-F')


def report(w):
    """Markdown tables per rate over the SH_ runs of w with the frames of E2b-1 (2 frames of 640x16, 4 lanes, not
    +RX_LATE, +STREAM_TOGGLE, +PPI_SOTSYNCERR, negative tests): start of the TX (TB TX, us), trailer bytes of a
    packet on the PPI of each receiver (all lanes), bursts of the TX controller (txrequesths of lane 0) for a line
    and for a short packet and the gaps between bursts, latency from the TX input to video_out (first start of
    frame, every end of line; ns); then memory and length of every run (rss.txt, sampled every 10 s). Returns 0."""
    per, rows = {}, []
    for c in sorted(glob.glob(os.path.join(w, '*', 'check.txt'))):
        run = os.path.dirname(c)
        name = os.path.basename(run)
        args = open(os.path.join(run, 'args.txt')).read()
        rss = [line.split() for line in open(os.path.join(run, 'rss.txt')) if line[:1].isdigit()] \
            if os.path.exists(os.path.join(run, 'rss.txt')) else []
        rows.append((name, max((int(m) for _, m in rss), default=0), max((int(s) for s, _ in rss), default=0)))
        if not name.startswith(SHIM) or any(plus(args, k) for k in ('RX_LATE', 'STREAM_TOGGLE', 'LANES_ACTIVE',
                                                                     'PPI_CORRUPT', 'PPI_SOTSYNCERR', 'NEG_FRONT',
                                                                     'FRAMES', 'WIDTH', 'HEIGHT')):
            continue
        tb = open(os.path.join(run, 'tb.txt')).read()
        p = per.setdefault(int(re.search(r'^\S+: (\d+) Mb/s', args, re.M)[1]), {'runs': []})
        p['runs'].append(name)
        m = re.search(r'^TB TX: init_done ([\d.]+) us, enabled ([\d.]+) us .*first beat ([\d.]+) us, HS clock requested'
                      r' ([\d.]+) us, seen by R-X ([\d.]+) us, by R-F ([\d.]+) us', tb, re.M)
        for k, v in zip(REPORT_TX, m.groups() if m else ()):
            p.setdefault(k, []).append(float(v))
        dec = decode_run(run)
        for k, _, text in dec['items']:
            if k in ('ppi-xil', 'ppi-ftel'):
                t = re.search(r'trailer bytes (\d+)(?:\.\.(\d+))?', text)
                p.setdefault(f'trailer bytes of a packet, {k[4:]}', []).extend(int(x) for x in t.groups() if x)
        cap = read_csv(os.path.join(run, 'tx_ppi.csv'))
        bursts = tx_bursts(cap)
        for pk, (s, e) in zip(ppi_packets(cap, 4), bursts):
            p.setdefault('TX burst of a line (ns)' if pk.get('dt') == DT_RAW10 else 'TX burst of a short packet (ns)',
                         []).append(e - s)
        p.setdefault('TX gap between bursts (ns)', []).extend(bursts[i + 1][0] - bursts[i][1]
                                                              for i in range(len(bursts) - 1))
        tx_sof, tx_eol = axis_times(read_csv(os.path.join(run, 'tx_axis.csv')))
        for k in ('xil', 'ftel'):
            sof, eol = axis_times(read_csv(os.path.join(run, f'{k}_axis.csv')))
            if sof and tx_sof:
                p.setdefault(f'latency, first start of frame, {k} (ns)', []).append(sof[0] - tx_sof[0])
            p.setdefault(f'latency, end of line, {k} (ns)', []).extend(r - t for r, t in zip(eol, tx_eol))
    rates = sorted(per)
    keys = []
    for r in rates:
        keys += [k for k in per[r] if k not in keys and k != 'runs']
    print('Per rate, SH_ runs with the frames of E2b-1 (min..max):\n')
    print('| | ' + ' | '.join(f'{r} Mb/s' for r in rates) + ' |')
    print('|---|' + '---|' * len(rates))
    print('| runs | ' + ' | '.join(', '.join(per[r]['runs']) for r in rates) + ' |')
    for k in keys:
        fmt = '{:.3f}' if k in REPORT_TX else '{:.0f}'
        print(f'| {k}{" (us)" if k in REPORT_TX else ""} | ' + ' | '.join(rng(per[r].get(k, []), fmt) for r in rates)
              + ' |')
    print('\n| Run | xsimk max (MB) | length (s, from rss.txt) |\n|---|---|---|')
    for name, mb, s in rows:
        print(f'| {name} | {mb} | {s} |')
    return 0


def main():
    a = sys.argv[1:]
    w = a[1] if len(a) == 2 else os.path.join(FPGA, 'work', 'exp2b')
    if a[:1] == ['report'] and len(a) <= 2:
        return report(w)
    if len(a) == 2 and a[0] == 'tbcheck':
        return 0 if print_tbcheck(tbcheck(a[1])) else 1
    if len(a) == 2 and a[0] == 'decode':
        res = decode_run(a[1])['items']
        for name, ok, text in res:
            print(f"DECODE {name:16s} {'ok  ' if ok else 'FAIL'} {text}")
        print(f"DECODERESULT: {'PASS' if all(ok for _, ok, _ in res) else 'FAIL'}")
        return 0 if all(ok for _, ok, _ in res) else 1
    if a == ['selftest']:
        return 0 if selftest() else 1
    if a[:1] == ['evidence'] and len(a) <= 2:
        return 0 if all(evidence(w).values()) else 1
    if a[:1] == ['evselftest'] and len(a) <= 2:
        return 0 if evselftest(w) else 1
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
