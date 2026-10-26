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
# Description     : TN2b (fpga/PLAN_TN2B.md): build, run and check the scenarios in XSIM.
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
# TN2b of fpga/PLAN_TN2B.md: synthetic RAW10 frames through AMD's CSI-2 TX Subsystem into AMD's CSI-2 RX Subsystem
# (R-X) and into ftel_dphy_rx followed by AMD's CSI-2 RX Subsystem without PHY (R-F), in XSIM. Outputs in
# fpga/work/exp2b (gitignored).
#   fpga/exp2b/run_exp2b.sh build <rate>                    # the three subsystems, project, compile, elaborate;
#                                                           # once per rate (4 lanes)
#   fpga/exp2b/run_exp2b.sh run <rate> <name> [+arg ...]    # one scenario
#   fpga/exp2b/run_exp2b.sh E2b-1|E2b-2|E2b-3               # scenarios at 1440 Mb/s
#   fpga/exp2b/run_exp2b.sh E2b-4 [a b c]                   # 260, 800, 1500 Mb/s
#   fpga/exp2b/run_exp2b.sh E2b-5|E2b-6|E2b-7|E2b-8         # active lanes, late receivers, ppm, stream off/on
#   fpga/exp2b/run_exp2b.sh E2b-9                           # a burst with a SoT sync error on lane 0 (with shim)
#   fpga/exp2b/run_exp2b.sh all                             # E2b-1 to E2b-9, then summary
#   fpga/exp2b/run_exp2b.sh model [<command> [arg ...]]     # the same with ftel_dphy_rx behind afe_model
#                                                           # (runs M_*; default all but E2b-8)
#   fpga/exp2b/run_exp2b.sh NEG-ecc|NEG-crc|NEG-front|neg   # negative tests (neg: all three)
#   fpga/exp2b/run_exp2b.sh shim [<command> [arg ...]]      # the same with rxactivehs into R-F through the gate
#                                                           # of fpga/rtl/ (runs SH_*; default all, model, neg)
#   fpga/exp2b/run_exp2b.sh finding                         # not re-timed: E2b-1, E2b-4, E2b-6, and the diagnosis
#                                                           # runs DBG-E2b-1-xfill, DBG-E2b-1-amd1..3
#   fpga/exp2b/run_exp2b.sh summary                         # verdict lines of every run so far
#   fpga/exp2b/run_exp2b.sh recheck                         # the checks of every run again, no simulation
#   fpga/exp2b/run_exp2b.sh evidence|evselftest             # tn2b_evidence.py over every run (plan §7)
# A build lives in fpga/work/exp2b/build_<rate> (build_<rate>_<debug> when EXP2B_DEBUG is not off); it is compiled
# and elaborated again when a source changed, and made again when exp2b.tcl or the set of exp2b/*.sv changed.
# A scenario writes fpga/work/exp2b/<name>/: the files of tb_exp2b.sv (frames.txt, tx_axis.csv, xil_axis.csv,
# ftel_axis.csv, xil_ppi.csv, ftel_ppi.csv, tx_ppi.csv), xsim.log, tb.txt (the TB and AFE lines), args.txt
# (arguments, hash of the sources of the build), check.txt (fpga/tools/csi2_dump.py, plan §2.3) and tbcheck.txt
# (tn2b_evidence.py tbcheck); a run passes when both pass. In check.txt a comparison passes only when both sides
# have as many lines or packets (csi2_dump.py compare does not judge the lengths). With +RX_LATE=1 the receivers
# are set up within frame 0: the frames of the TX are compared from its second start of frame, those of each
# receiver from its first start of frame after its set-up, and the packets of the TX are not compared with those
# of R-X. ftel_dphy_rx gets the run-time fields of its configuration model at the rate (exp1/cfg_for_rate.py)
# unless the arguments set them. rss.txt has the memory of the simulation every 10 s.
# EXP2B_DEBUG=typical keeps the signals for waveforms and +VCD=1; VIVADO overrides the Vivado binary.
# EXP2B_ARGS adds plusargs to every run and EXP2B_TAG puts a prefix before every run name; shim sets them to
# +PPI_ADAPTER=1 and SH_ (tb_exp2b.sv: rxactivehs into R-F from fpga/rtl/m_ftel_ppi_act_gate.sv, held Low until
# rxsynchs, fpga/PLAN_TN2B_GATE.md).
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
FPGA=$(dirname "$HERE")
REPO=$(dirname "$FPGA")
EXP1=$FPGA/exp1
W=$FPGA/work/exp2b
VIVADO=${VIVADO:-/opt/xilinx/2025.2/Vivado/bin/vivado}
XBIN=$(dirname "$VIVADO")
export PATH="$XBIN:$PATH"     # the XSIM scripts Vivado writes call xvlog, xelab and xsim by name
DEBUG=${EXP2B_DEBUG:-off}

sources() {
  sed -n 's#^${FTEL_DPHY_RX_PATH}#'"$REPO"'#p' "$REPO/logical/filelist.f"
  ls "$EXP1/afe_model.sv" "$EXP1/ppi_csv_mon.sv" "$FPGA/rtl/m_ftel_ppi_act_gate.sv" "$HERE"/*.sv
}

bdir() {   # bdir <rate>
  if [ "$DEBUG" = off ]; then echo "$W/build_$1"; else echo "$W/build_${1}_$DEBUG"; fi
}

build() {
  local rate=$1 d sim sha set
  d=$(bdir "$rate")
  sim=$d/prj/exp2b.sim/sim_1/behav/xsim
  set=$(ls "$HERE"/*.sv | xargs -n1 basename | tr '\n' ' ')
  mkdir -p "$d"
  if [ ! -f "$sim/elaborate.sh" ] || [ "$HERE/exp2b.tcl" -nt "$sim/elaborate.sh" ] \
     || [ "$(cat "$d/files.txt" 2>/dev/null)" != "$set" ]; then
    echo "build ${rate} Mb/s: Vivado project, the three subsystems (~40 s)"
    : > "$d/src.sha"                  # exp2b.tcl re-creates prj/ (create_project -force); compile again
    (cd "$d" && "$VIVADO" -mode batch -nojournal -log vivado.log -source "$HERE/exp2b.tcl" \
       -tclargs "$d" "$rate" "$DEBUG" > vivado.out 2>&1)
    if ! grep -q '^EXP2B done' "$d/vivado.out"; then
      echo "build FAIL: see $d/vivado.log"
      return 1
    fi
    echo "$set" > "$d/files.txt"
    grep -E '^EXP2B (x|path)' "$d/vivado.out"
  fi
  sha=$(sources | xargs sha256sum | sha256sum | cut -c1-16)
  if [ "$(cat "$d/src.sha" 2>/dev/null)" != "$sha" ]; then
    echo "build ${rate} Mb/s: compile and elaborate (~20 s)"
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

rss_log() {   # rss_log <run dir> <pid of the simulation>: memory of xsimk every 10 s until the simulation ends
  local out=$1 pid=$2 k s=0
  echo "# seconds, resident memory of xsimk in MB" > "$out/rss.txt"
  while kill -0 "$pid" 2>/dev/null; do
    sleep 10
    s=$((s + 10))
    k=$(pgrep -f -- "xsimk .*OUTDIR=$out( |\$)" | head -n 1)
    if [ -n "$k" ]; then echo "$s $(( $(ps -o rss= -p "$k" 2>/dev/null || echo 0) / 1024 ))" >> "$out/rss.txt"; fi
  done
  wait "$pid"
}

run() {
  local rate=$1 name=${EXP2B_TAG:-}${TN2B_PRE:-}$2 out sim t0 args=()
  shift 2
  set -- "$@" ${TN2B_ARGS:-} ${EXP2B_ARGS:-}
  build "$rate" || return 1
  out=$W/$name
  rm -rf "$out"
  mkdir -p "$out"
  # each run simulates in its own copy of the XSIM folder of the build: two runs in one folder share its run
  # settings (the second one ran with the plusargs of the first)
  sim=$out/sim
  cp -r "$(bdir "$rate")/prj/exp2b.sim/sim_1/behav/xsim" "$sim"
  # $value$plusargs takes the first match: the arguments of the scenario win over the model values
  for a in "$@" $(python3 "$EXP1/cfg_for_rate.py" "$rate") "+RATE=$rate" "+OUTDIR=$out"; do
    args+=(-testplusarg "${a#+}")
  done
  echo "$name: ${rate} Mb/s $*" > "$out/args.txt"
  echo "sources $(cat "$(bdir "$rate")/src.sha")" >> "$out/args.txt"
  t0=$(date +%s)
  (cd "$sim" && "$XBIN/xsim" tb_exp2b_behav -R -log "$out/xsim.log" "${args[@]}" > /dev/null 2>&1) &
  rss_log "$out" $!
  rm -rf "$sim"
  grep -E '^(TB |AFE )' "$out/xsim.log" > "$out/tb.txt"
  check "$out"
  echo "$name ($(( $(date +%s) - t0 )) s, xsimk up to $(awk '!/^#/ && $2 > m { m = $2 } END { print m + 0 }' \
    "$out/rss.txt") MB): $(grep -m1 '^RESULT' "$out/check.txt") | $(grep -m1 '^TBRESULT' "$out/tbcheck.txt")"
  grep '^ITEM .* FAIL' "$out/check.txt"
  grep '^TBCHECK .* FAIL ' "$out/tbcheck.txt"
  return 0
}

# The checks of one run (plan §2.3): csi2_dump.py on the captures, and the testbench-level verdict. Also used by
# recheck.
check() {   # check <run dir>
  local out=$1 c=$1/check.txt lanes tx xa=$1/xil_axis.csv fa=$1/ftel_axis.csv k t n=0 fails=()
  local D=(python3 "$FPGA/tools/csi2_dump.py")
  lanes=$(sed -n 's/.*+LANES_ACTIVE=\([0-9]*\).*/\1/p' "$out/args.txt" | head -1)
  lanes=${lanes:-4}
  tx=$out/tx_axis.csv
  if grep -q '+RX_LATE=1' "$out/args.txt"; then
    tx=$out/tx_axis_from1.csv       # from the second start of frame taken (sof and tready): the header lines, then
    awk -F, 'NR <= 2 { print; next } $7 == 1 && $8 == 1 { s++ } s >= 2 { print }' "$out/tx_axis.csv" > "$tx"
    # the receivers are enabled from reset (CCR = 1) and give part of frame 0: each from its first start of frame
    # after its set-up (TB RX CFG)
    for k in xil:R-X ftel:R-F; do
      t=$(sed -n "s/.*${k#*:} set up at \([0-9.]*\) us.*/\1/p" "$out/tb.txt")
      awk -F, -v t="${t:-0}" 'NR <= 2 { print; next } $4 >= t * 1e6 && $8 == 1 { s = 1 } s { print }' \
        "$out/${k%%:*}_axis.csv" > "$out/${k%%:*}_axis_late.csv"
    done
    xa=$out/xil_axis_late.csv
    fa=$out/ftel_axis_late.csv
  fi
  : > "$c"
  item() {   # item <name> <command ...>: the command must pass
    local name=$1
    shift
    n=$((n + 1))
    echo "== $name: $(basename "$2") $3 ${4##*/} ${5##*/}" >> "$c"
    if "$@" >> "$c" 2>&1; then echo "ITEM $name PASS" >> "$c"; else echo "ITEM $name FAIL" >> "$c"; fails+=("$name"); fi
  }
  cmp_item() {   # cmp_item <name> <compare arguments ...>: compare must pass with as many on both sides
    local name=$1 txt st a b
    shift
    n=$((n + 1))
    txt=$("${D[@]}" compare "$@" 2>&1)
    st=$?
    printf '== %s: compare %s %s %s\n%s\n' "$name" "$1" "${2##*/}" "${3##*/}" "$txt" >> "$c"
    a=$(sed -n 's/.*(A has \([0-9]*\), B has \([0-9]*\)).*/\1/p' <<< "$txt")
    b=$(sed -n 's/.*(A has \([0-9]*\), B has \([0-9]*\)).*/\2/p' <<< "$txt")
    if [ "$st" -eq 0 ] && [ -n "$a" ] && [ "$a" = "$b" ] && [ "$a" -gt 0 ]; then
      echo "ITEM $name PASS" >> "$c"
    else
      echo "ITEM $name FAIL (A $a, B $b)" >> "$c"
      fails+=("$name")
    fi
  }
  cmp_item pixels-xil axis "$tx" "$xa" --tready tready --tuser sof
  cmp_item pixels-ftel axis "$tx" "$fa" --tready tready --tuser sof
  # timing at the PPI of the receivers (HAS Table A-2): rxsynchs one cycle before the first byte for AMD's D-PHY, in
  # its cycle for ftel_dphy_rx (C6), except where +PPI_AMD_TIMING=1|2 moved it; the bytes of a burst at most 6 byte
  # clocks apart on the lanes (C10). The PPI inside the TX has no rxsynchs.
  local fsync=0
  grep -qE '\+PPI_AMD_TIMING=[12]' "$out/args.txt" && fsync=-1
  item ppi-tx "${D[@]}" ppi "$out/tx_ppi.csv" --lanes "$lanes"
  item ppi-xil "${D[@]}" ppi "$out/xil_ppi.csv" --lanes "$lanes" --sync-at=-1 --max-lane-spread=6
  item ppi-ftel "${D[@]}" ppi "$out/ftel_ppi.csv" --lanes "$lanes" --sync-at="$fsync" --max-lane-spread=6
  if [ "$tx" = "$out/tx_axis.csv" ]; then
    cmp_item packets-tx-xil ppi "$out/tx_ppi.csv" "$out/xil_ppi.csv" --lanes "$lanes"
  fi
  cmp_item packets-xil-ftel ppi "$out/xil_ppi.csv" "$out/ftel_ppi.csv" --lanes "$lanes"
  if [ ${#fails[@]} -eq 0 ]; then
    echo "RESULT: PASS ($n items)" >> "$c"
  else
    echo "RESULT: FAIL (${#fails[@]} of $n items: ${fails[*]})" >> "$c"
  fi
  python3 "$HERE/tn2b_evidence.py" tbcheck "$out" > "$out/tbcheck.txt" 2>&1
}

e2b_1() { run 1440 E2b-1; }
e2b_2() {
  run 1440 E2b-2a +PATTERN=prbs
  run 1440 E2b-2b +PATTERN=synclike
  run 1440 E2b-2c +WIDTH=3840 +HEIGHT=8
}
e2b_3() { run 1440 E2b-3 +FRAMES=8 +WIDTH=64 +HEIGHT=4; }
e2b_4() {
  local s
  for s in ${@:-a b c}; do
    case $s in
      a) run 260 E2b-4a +TIMEOUT_US=8000 ;;
      b) run 800 E2b-4b ;;
      c) run 1500 E2b-4c ;;
      *) echo "E2b-4: no scenario $s"; return 1 ;;
    esac
  done
}
e2b_5() {
  run 1440 E2b-5a +LANES_ACTIVE=2
  run 1440 E2b-5b +LANES_ACTIVE=1
}
e2b_6() { run 1440 E2b-6 +FRAMES=4 +RX_LATE=1; }
e2b_7() {
  run 1440 E2b-7a +FRAMES=8 +WIDTH=64 +HEIGHT=4 +CORE_HALF=2.501
  run 1440 E2b-7b +FRAMES=8 +WIDTH=64 +HEIGHT=4 +CORE_HALF=2.499
}
e2b_8() { run 1440 E2b-8 +FRAMES=4 +STREAM_TOGGLE=1; }
# A SoT sync error on lane 0 of packet 5 (line 4 of frame 0), as ftel_dphy_rx gives it (HAS C8): no rxsynchs and no
# rxvalidhs in that burst, errsotsynchs instead. The gate keeps rxactivehs of the burst Low; R-F must give the later
# frames (fpga/PLAN_TN2B_GATE.md §4). Meant with shim.
e2b_9() { run 1440 E2b-9 +FRAMES=3 +PPI_SOTSYNCERR=0,5; }

# Not re-timed, AMD's controller without PHY takes no packet of ftel_dphy_rx; the diagnosis runs give 0 to the X of
# rxdatahs, or re-time the PPI in the three ways of tb_exp2b.sv (+PPI_AMD_TIMING).
finding() {
  local m
  e2b_1
  e2b_4
  e2b_6
  run 1440 DBG-E2b-1-xfill +PPI_XFILL=1
  for m in 1 2 3; do run 1440 "DBG-E2b-1-amd$m" "+PPI_AMD_TIMING=$m"; done
}

recheck() {
  local c
  for c in "$W"/*/check.txt; do
    check "$(dirname "$c")"
  done
}

summary() {
  local c d
  for c in "$W"/*/check.txt; do
    d=$(dirname "$c")
    printf '%-14s %s | %s\n' "$(basename "$d")" "$(grep -m1 '^RESULT' "$c")" \
      "$(grep -m1 '^TBRESULT' "$d/tbcheck.txt" 2>/dev/null)"
  done
}

case "${1:-}" in
  build)   build "$2" ;;
  run)     shift; run "$@" ;;
  E2b-1)   e2b_1 ;;
  E2b-2)   e2b_2 ;;
  E2b-3)   e2b_3 ;;
  E2b-4)   shift; e2b_4 "$@" ;;
  E2b-5)   e2b_5 ;;
  E2b-6)   e2b_6 ;;
  E2b-7)   e2b_7 ;;
  E2b-8)   e2b_8 ;;
  E2b-9)   e2b_9 ;;
  all)     e2b_1; e2b_2; e2b_3; e2b_4; e2b_5; e2b_6; e2b_7; e2b_8; e2b_9; summary ;;
  model)   shift
           if [ $# -eq 0 ]; then
             for s in E2b-1 E2b-2 E2b-3 E2b-4 E2b-5 E2b-6 E2b-7; do TN2B_PRE=M_ TN2B_ARGS=+AFE=model "$0" "$s"; done
           else
             TN2B_PRE=M_ TN2B_ARGS=+AFE=model "$0" "$@"
           fi ;;
  # negative tests: one bit of the header (ECC corrects it, only the ECC register of R-F tells), one bit of the
  # payload (CRC error and one wrong pixel), pull strength at the buffers of ftel_dphy_rx during HS
  NEG-ecc)   run 1440 NEG-ecc +PPI_CORRUPT=0,1,0,0 ;;
  NEG-crc)   run 1440 NEG-crc +PPI_CORRUPT=1,1,2,3 ;;
  NEG-front) run 1440 NEG-front +NEG_FRONT=1 ;;
  neg)     "$0" NEG-ecc; "$0" NEG-crc; "$0" NEG-front ;;
  shim)    shift
           if [ $# -eq 0 ]; then
             for s in all model neg; do EXP2B_TAG=SH_ EXP2B_ARGS=+PPI_ADAPTER=1 "$0" "$s"; done
           else
             EXP2B_TAG=SH_ EXP2B_ARGS=+PPI_ADAPTER=1 "$0" "$@"
           fi ;;
  finding) finding ;;
  summary) summary ;;
  recheck) recheck; summary ;;
  evidence|evselftest) python3 "$HERE/tn2b_evidence.py" "$1" "$W" ;;
  *)       sed -n '23,58p' "$0"; exit 2 ;;
esac
