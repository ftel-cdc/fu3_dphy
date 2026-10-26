#!/bin/bash
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
# Description     : TN2a in XSIM: AMD's D-PHY TX into AMD's D-PHY RX and into ftel_dphy_rx; builds,
#                   scenarios and checks.
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
# TN2a of fpga/PLAN_TN2A.md: AMD's D-PHY TX (mipi_dphy 4.3 MASTER, driven at its PPI) into AMD's D-PHY RX and
# into ftel_dphy_rx (the ASIC RTL behind IBUFDS_DPHY, or behind afe_model with +AFE=model), in XSIM. Outputs in
# fpga/work/exp2 (gitignored).
#   fpga/exp2/run_exp2.sh build <rate> <lanes>                 # xtx and xrx IP, project, compile, elaborate;
#                                                              # once per rate and lane count
#   fpga/exp2/run_exp2.sh run <rate> <lanes> <name> [+arg ...] # one scenario
#   fpga/exp2/run_exp2.sh S0                                   # smoke test of the TX hookup (plan step 2), on a
#                                                              # build with debug typical, with tn2a.vcd
#   fpga/exp2/run_exp2.sh E2a-0                                # the pad decoder against the TN1 line generator
#   fpga/exp2/run_exp2.sh E2a-1|E2a-2|E2a-3                    # scenarios at 1440 Mb/s, 4 lanes
#   fpga/exp2/run_exp2.sh E2a-4 [a b c d e]                    # the other rates and lane counts
#   fpga/exp2/run_exp2.sh E2a-5 [rate ...]                     # EoT at every phase of core_clk; the rates can
#                                                              # be given, to run them in parallel
#   fpga/exp2/run_exp2.sh all                                  # E2a-0 to E2a-5, then summary
#   fpga/exp2/run_exp2.sh model [<command> [arg ...]]          # the same with ftel_dphy_rx behind afe_model
#                                                              # (runs M_*; default all)
#   fpga/exp2/run_exp2.sh NEG-tx|NEG-front|neg                 # negative tests of the byte check and of the
#                                                              # front-end check (neg: both)
#   fpga/exp2/run_exp2.sh summary                              # verdict lines of every scenario run so far
#   fpga/exp2/run_exp2.sh recheck                              # the checks of every run again, no simulation
#   fpga/exp2/run_exp2.sh txtiming                             # the TX timing at the pads per rate (tables)
#   fpga/exp2/run_exp2.sh evidence                             # the checks of the evidence over every run
# A build lives in fpga/work/exp2/build_<rate>_<lanes>l (build_<rate>_<lanes>l_<debug> when EXP2_DEBUG is not
# off); it is compiled and elaborated again when a source changed, and made again when exp2.tcl or the set of
# exp2/*.sv changed. A scenario writes fpga/work/exp2/<name>/: truth.txt (pad_truth), expected.txt, xil_ppi.csv,
# ftel_ppi.csv, xsim.log, tb.txt (the TB and AFE lines), args.txt (arguments, hash of the sources of the build,
# trailer limit), check.txt (fpga/tools/csi2_dump.py bursts) and tbcheck.txt (tn2a_evidence.py tbcheck); a run
# passes when both pass. ftel_dphy_rx gets the run-time fields of its configuration model at the rate
# (exp1/cfg_for_rate.py) unless the arguments set them. Trailer bytes: AMD's receiver keeps them (no limit);
# ftel_dphy_rx removes them: more than MAXTR in a burst is an error (default 0; the scenarios at 260 and
# 400 Mb/s take it from HAS v0.16 Table 4-7, tmax).
# EXP2_DEBUG=typical keeps the signals for waveforms and +VCD=1; VIVADO overrides the Vivado binary.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
FPGA=$(dirname "$HERE")
REPO=$(dirname "$FPGA")
EXP1=$FPGA/exp1
W=$FPGA/work/exp2
VIVADO=${VIVADO:-/opt/xilinx/2025.2/Vivado/bin/vivado}
XBIN=$(dirname "$VIVADO")
export PATH="$XBIN:$PATH"     # the XSIM scripts Vivado writes call xvlog, xelab and xsim by name
DEBUG=${EXP2_DEBUG:-off}

sources() {
  sed -n 's#^${FTEL_DPHY_RX_PATH}#'"$REPO"'#p' "$REPO/logical/filelist.f"
  ls "$EXP1/dphy_line_gen.sv" "$EXP1/afe_model.sv" "$EXP1/ppi_csv_mon.sv" "$HERE"/*.sv
}

bdir() {   # bdir <rate> <lanes>
  if [ "$DEBUG" = off ]; then echo "$W/build_${1}_${2}l"; else echo "$W/build_${1}_${2}l_$DEBUG"; fi
}

build() {
  local rate=$1 lanes=$2 d sim sha set
  d=$(bdir "$rate" "$lanes")
  sim=$d/prj/exp2.sim/sim_1/behav/xsim
  set=$(ls "$HERE"/*.sv | xargs -n1 basename | tr '\n' ' ')
  mkdir -p "$d"
  if [ ! -f "$sim/elaborate.sh" ] || [ "$HERE/exp2.tcl" -nt "$sim/elaborate.sh" ] \
     || [ "$(cat "$d/files.txt" 2>/dev/null)" != "$set" ]; then
    echo "build ${rate} Mb/s, ${lanes} lane(s): Vivado project, xtx and xrx IP (~3 min)"
    : > "$d/src.sha"                  # exp2.tcl re-creates prj/ (create_project -force); compile again
    (cd "$d" && "$VIVADO" -mode batch -nojournal -log vivado.log -source "$HERE/exp2.tcl" \
       -tclargs "$d" "$rate" "$lanes" "$DEBUG" > vivado.out 2>&1)
    if ! grep -q '^EXP2 done' "$d/vivado.out"; then
      echo "build FAIL: see $d/vivado.log"
      return 1
    fi
    echo "$set" > "$d/files.txt"
    grep '^EXP2 x' "$d/vivado.out"
  fi
  sha=$(sources | xargs sha256sum | sha256sum | cut -c1-16)
  if [ "$(cat "$d/src.sha" 2>/dev/null)" != "$sha" ]; then
    echo "build ${rate} Mb/s, ${lanes} lane(s): compile and elaborate (~4 min)"
    if ! (cd "$sim" && bash compile.sh > "$d/compile.log" 2>&1); then
      echo "compile FAIL: see $d/compile.log"
      grep -m 10 'ERROR' "$d/compile.log"
      return 1
    fi
    if ! (cd "$sim" && bash elaborate.sh > "$d/elaborate.log" 2>&1); then
      echo "elaborate FAIL: see $d/elaborate.log"
      grep -m 10 'ERROR' "$d/elaborate.log"
      return 1
    fi
    echo "$sha" > "$d/src.sha"
  fi
}

run() {
  local rate=$1 lanes=$2 name=${TN2_PRE:-}$3 out sim t0 args=()
  shift 3
  set -- "$@" ${TN2_ARGS:-}
  build "$rate" "$lanes" || return 1
  sim=$(bdir "$rate" "$lanes")/prj/exp2.sim/sim_1/behav/xsim
  out=$W/$name
  rm -rf "$out"
  mkdir -p "$out"
  # $value$plusargs takes the first match: the arguments of the scenario win over the model values
  for a in "$@" $(python3 "$EXP1/cfg_for_rate.py" "$rate") "+RATE=$rate" "+OUTDIR=$out"; do
    args+=(-testplusarg "${a#+}")
  done
  echo "$name: ${rate} Mb/s, ${lanes} lane(s) $*" > "$out/args.txt"
  echo "sources $(cat "$(bdir "$rate" "$lanes")/src.sha")" >> "$out/args.txt"
  t0=$(date +%s)
  (cd "$sim" && "$XBIN/xsim" tb_exp2a_behav -R -log "$out/xsim.log" "${args[@]}" > /dev/null 2>&1)
  grep -E '^(TB |AFE )' "$out/xsim.log" > "$out/tb.txt"
  check "$out" "$lanes"
  echo "$name ($(( $(date +%s) - t0 )) s): $(grep -m1 '^RESULT' "$out/check.txt") | $(grep -m1 '^TBRESULT' "$out/tbcheck.txt")"
  grep -E '^[AB] ' "$out/check.txt"
  grep '^TBCHECK .* FAIL ' "$out/tbcheck.txt"
  return 0
}

# The checks of one run: csi2_dump.py bursts of both captures against truth.txt (the trailer limit of ftel_dphy_rx
# from MAXTR), and the testbench-level verdict. Also used by recheck.
check() {   # check <run dir> <lanes>
  local out=$1 lanes=$2 lim sat=-1 csv=("$1/xil_ppi.csv")
  lim=$(sed -n 's/^trailer limit .*: //p' "$out/args.txt")
  if [ -z "$lim" ]; then
    lim="-,${MAXTR:-0}"
    [ -f "$out/ftel_ppi.csv" ] || lim="-"
    echo "trailer limit (AMD, ftel_dphy_rx): $lim" >> "$out/args.txt"
  fi
  if [ -f "$out/ftel_ppi.csv" ]; then
    csv+=("$out/ftel_ppi.csv")
    sat="-1,0"
  fi
  # timing at the PPI (HAS Table A-2): rxsynchs one cycle before the first byte for AMD's D-PHY, in its cycle for
  # ftel_dphy_rx (C6); the bytes of a burst at most 6 byte clocks apart on the lanes (C10)
  python3 "$FPGA/tools/csi2_dump.py" bursts --truth "$out/truth.txt" --lanes "$lanes" --max-trailer="$lim" \
    --sync-at="$sat" --max-lane-spread=6 "${csv[@]}" > "$out/check.txt" 2>&1
  python3 "$HERE/tn2a_evidence.py" tbcheck "$out" > "$out/tbcheck.txt" 2>&1
}

# Trailer bytes that HAS v0.16 Table 4-7 allows ftel_dphy_rx without junk before LP-11 (as tmax of
# exp1/run_exp1.sh): none from 600 Mb/s, otherwise its last column.
tmax() {   # tmax <rate Mb/s>
  case $1 in 260) echo 4 ;; 400) echo 6 ;; *) echo 0 ;; esac
}

# E2a-0: the TN1 line generator drives the pads (the TX stays in reset); truth.txt of the pad decoder must equal
# truth_gen.txt of the generator (tbcheck item padtruth): the lengths of E1-1, the corners of E1-3c, uneven lanes.
e2a_0() {
  run 1440 4 E2a-0a +SRC=gen
  run 1440 4 E2a-0b +SRC=gen +LENS=1,4,64,256 +TRAIL=min +EXIT=min +LPX=min
  run 1440 4 E2a-0c +SRC=gen +UNEVEN=1 +LENS=2,3,5,9,65,257
}
# E2a-1: the lengths of E1-1 (1 to 1024 bytes, counter); AMD's receiver must pass first (TX hookup and truth).
e2a_1() { run 1440 4 E2a-1; }
# E2a-2: the payloads of E1-2a/b/c; with +UNEVEN=1 the lanes from NL / 2 on end one byte early, lane 0 last (its
# txreadyhs paces every lane of the TX)
e2a_2() {
  run 1440 4 E2a-2a +PATTERN=prbs9 +LENS=1,2,3,8,64,256,1024 +REPEAT=2
  run 1440 4 E2a-2b +PATTERN=synclike +LENS=4,8,16,64,256,1024
  run 1440 4 E2a-2c +UNEVEN=1 +LENS=2,3,5,9,65,257
}
# E2a-3: the next burst requested at stopstate, so the shortest THS-EXIT of the TX
e2a_3() { run 1440 4 E2a-3 +GAP_NS=0 +LENS=1,4,64,256 +REPEAT=2; }
# E2a-4: the rates and lane counts of E1-4: 260 Mb/s (the lowest rate of the TX), 800, 1500; 2 lanes, 1 lane
e2a_4() {
  local s
  for s in ${@:-a b c d e}; do
    case $s in
      a) MAXTR=$(tmax 260) run 260 4 E2a-4a +TIMEOUT_US=3000 ;;
      b) run 800 4 E2a-4b ;;
      c) run 1500 4 E2a-4c ;;
      d) run 1440 2 E2a-4d ;;
      e) run 1440 1 E2a-4e ;;
      *) echo "E2a-4: no scenario $s"; return 1 ;;
    esac
  done
}
# E2a-5: EoT with the trail of the TX at every rate of HAS v0.16 Table 4-7, LP-11 at every phase of core_clk.
# The TX's clocking ignores the period of its core clock (S0), so the offset is on the receivers' side, as in
# E1-5: their core_clk 400 ppm slow, then 400 ppm fast. One build per rate.
e2a_5() {
  local r
  for r in ${@:-260 400 600 800 1000 1200 1440 1500}; do
    MAXTR=$(tmax "$r") run "$r" 4 "E2a-5_${r}_slow" +LENS=1,2,3,4,5,8,16,64,256 +REPEAT=6 +CORE_HALF=2.501
    MAXTR=$(tmax "$r") run "$r" 4 "E2a-5_${r}_fast" +LENS=1,2,3,4,5,8,16,64,256 +REPEAT=6 +CORE_HALF=2.499
  done
}

# The checks of every run so far again, with the current csi2_dump.py and tn2a_evidence.py: same truth, captures,
# lane count and trailer limit as recorded by run (tb.txt, args.txt). No simulation.
recheck() {
  local c out
  for c in "$W"/*/check.txt; do
    out=$(dirname "$c")
    check "$out" "$(sed -n 's/^TB START: NL \([0-9]*\),.*/\1/p' "$out/tb.txt")"
  done
}

summary() {
  local c d
  for c in "$W"/*/check.txt; do
    d=$(dirname "$c")
    printf '%-22s %s | %s\n' "$(basename "$d")" "$(grep -m1 '^RESULT' "$c")" \
      "$(grep -m1 '^TBRESULT' "$d/tbcheck.txt" 2>/dev/null)"
  done
}

# Plan step 2 (S0): the TX hookup, on a build with debug typical, so that tn2a.vcd holds the pads and both PPIs.
# Once with the TX's core clock equal to core_clk, once 100 ppm slow (the default of the bench).
s0() {
  DEBUG=typical
  run 1440 4 S0_exact +LENS=1,2,3 +TXLOG=3 +VCD=1 +TX_CORE_HALF=2.5
  run 1440 4 S0_ppm +LENS=1,2,3 +TXLOG=3 +VCD=1
}

case "${1:-}" in
  build)   build "$2" "$3" ;;
  run)     shift; run "$@" ;;
  S0)      s0 ;;
  E2a-0)   e2a_0 ;;
  E2a-1)   e2a_1 ;;
  E2a-2)   e2a_2 ;;
  E2a-3)   e2a_3 ;;
  E2a-4)   shift; e2a_4 "$@" ;;
  E2a-5)   shift; e2a_5 "$@" ;;
  all)     e2a_0; e2a_1; e2a_2; e2a_3; e2a_4; e2a_5; summary ;;
  model)   shift; TN2_PRE=M_ TN2_ARGS=+AFE=model "$0" "${@:-all}" ;;
  # negative tests: one byte goes to the TX inverted (the byte check must report exactly that one, so the run
  # fails while both receivers agree with the pads); pull strength at the buffers of ftel_dphy_rx during HS
  NEG-tx)    run 1440 4 NEG-tx +TX_CORRUPT=1,3,0 ;;
  NEG-front) run 1440 4 NEG-front +NEG_FRONT=1 ;;
  neg)     "$0" NEG-tx; "$0" NEG-front ;;
  summary) summary ;;
  recheck) recheck; summary ;;
  txtiming) python3 "$HERE/tn2a_evidence.py" txtiming "$W" ;;
  evidence) python3 "$HERE/tn2a_evidence.py" evidence "$W" ;;
  *)       sed -n '24,55p' "$0"; exit 2 ;;
esac
