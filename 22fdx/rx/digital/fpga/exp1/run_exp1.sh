#!/bin/bash
# TN1 of fpga/PLAN_TN1_TN3.md and fpga/PLAN_TN1_FIX.md: dummy D-PHY data into AMD's D-PHY RX and into ftel_dphy_rx (the ASIC RTL behind
# an AFE model), in XSIM. Outputs in fpga/work/exp1 (gitignored).
#   fpga/exp1/run_exp1.sh build <rate> <lanes>                 # xrx IP, project, compile, elaborate (~5 min);
#                                                              # once per rate and lane count
#   fpga/exp1/run_exp1.sh run <rate> <lanes> <name> [+arg ...] # one scenario (~15 s), then the check
#   fpga/exp1/run_exp1.sh run <rate> stub <name> [+arg ...]    # ftel_dphy_rx alone, 4 lanes, with xrx_stub.sv
#                                                              # (any rate; AMD's IP needs 260..3200 Mb/s)
#   fpga/exp1/run_exp1.sh E1-1|E1-2|E1-3|E1-4|E1-5|all         # the scenarios of the plans
#   fpga/exp1/run_exp1.sh window [<rate> ...]                  # eot_skip_bytes from its model value - 1 to + 2
#                                                              # (measurement, ~7 min, table by eot_window.py)
#   fpga/exp1/run_exp1.sh report                               # 80 Mb/s, outside the guaranteed range
#   fpga/exp1/run_exp1.sh summary                              # result line of every scenario run so far
# A build lives in fpga/work/exp1/build_<rate>_<lanes>l (build_stub for the stub); it is compiled and
# elaborated again when a source changed. A scenario writes fpga/work/exp1/<name>/: truth.txt, xil_ppi.csv, ftel_ppi.csv, xsim.log and
# check.txt (fpga/tools/csi2_dump.py bursts). ftel_dphy_rx gets the run-time fields of its configuration
# model at the rate (cfg_for_rate.py) unless the arguments set them. Trailer bytes: AMD's receiver keeps
# them (no limit); ftel_dphy_rx removes them: more than MAXTR in a burst is an error (default 0; the
# scenarios at the limits of HAS v0.16 Table 4-7 take it from that table, tmax).
# EXP1_DEBUG=typical keeps the signals for waveforms (new build); VIVADO overrides the Vivado binary.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
FPGA=$(dirname "$HERE")
REPO=$(dirname "$FPGA")
W=$FPGA/work/exp1
VIVADO=${VIVADO:-/opt/xilinx/2025.2/Vivado/bin/vivado}
XBIN=$(dirname "$VIVADO")
export PATH="$XBIN:$PATH"     # the XSIM scripts Vivado writes call xvlog, xelab and xsim by name
DEBUG=${EXP1_DEBUG:-off}

sources() {
  sed -n 's#^${FTEL_DPHY_RX_PATH}#'"$REPO"'/hw/rtl/ip/ftel_dphy_rx#p' "$REPO/hw/rtl/ip/ftel_dphy_rx/logical/filelist.f"
  ls "$HERE"/*.sv
}

build() {
  local rate=$1 lanes=$2 d sim sha
  d=$W/build_${rate}_${lanes}l
  sim=$d/prj/exp1.sim/sim_1/behav/xsim
  mkdir -p "$d"
  if [ ! -f "$sim/elaborate.sh" ] || [ "$HERE/exp1.tcl" -nt "$sim/elaborate.sh" ]; then
    echo "build ${rate} Mb/s, ${lanes} lane(s): Vivado project and xrx IP (~2 min)"
    : > "$d/src.sha"                  # exp1.tcl re-creates prj/ (create_project -force); compile again
    (cd "$d" && "$VIVADO" -mode batch -nojournal -log vivado.log -source "$HERE/exp1.tcl" \
       -tclargs "$d" "$rate" "$lanes" "$DEBUG" > vivado.out 2>&1)
    if ! grep -q '^EXP1 done' "$d/vivado.out"; then
      echo "build FAIL: see $d/vivado.log"
      return 1
    fi
    grep '^EXP1 xrx' "$d/vivado.out"
  fi
  sha=$(sources | xargs sha256sum | sha256sum | cut -c1-16)
  if [ "$(cat "$d/src.sha" 2>/dev/null)" != "$sha" ]; then
    echo "build ${rate} Mb/s, ${lanes} lane(s): compile and elaborate (~3 min)"
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

stub_build() {
  local d=$W/build_stub sha
  mkdir -p "$d"
  sha=$(sources | xargs sha256sum | sha256sum | cut -c1-16)
  if [ "$(cat "$d/src.sha" 2>/dev/null)" != "$sha" ]; then
    echo "build stub: compile and elaborate ftel_dphy_rx with xrx_stub.sv (~10 s)"
    if ! (cd "$d" && xvlog -sv --relax -i "$REPO/hw/rtl/ip/ftel_dphy_rx/logical" $(sources) > compile.log 2>&1 \
          && xelab --relax -debug off tb_exp1 -generic_top NL=4 -s tb_exp1_stub > elaborate.log 2>&1); then
      echo "build stub FAIL: see $d/compile.log and $d/elaborate.log"
      return 1
    fi
    echo "$sha" > "$d/src.sha"
  fi
}

run() {
  local rate=$1 lanes=$2 name=$3 out sim snap=tb_exp1_behav nl=$2 t0 args=() csv=()
  shift 3
  if [ "$lanes" = stub ]; then
    stub_build || return 1
    sim=$W/build_stub
    snap=tb_exp1_stub
    nl=4
  else
    build "$rate" "$lanes" || return 1
    sim=$W/build_${rate}_${lanes}l/prj/exp1.sim/sim_1/behav/xsim
    csv=("$W/$name/xil_ppi.csv")
  fi
  out=$W/$name
  rm -rf "$out"
  mkdir -p "$out"
  # $value$plusargs takes the first match: the arguments of the scenario win over the model values
  for a in "$@" $(python3 "$HERE/cfg_for_rate.py" "$rate") "+RATE=$rate" "+OUTDIR=$out"; do
    args+=(-testplusarg "${a#+}")
  done
  echo "$name: ${rate} Mb/s, ${lanes} lane(s) $*" > "$out/args.txt"
  t0=$(date +%s)
  (cd "$sim" && "$XBIN/xsim" "$snap" -R -log "$out/xsim.log" "${args[@]}" > /dev/null 2>&1)
  grep -E '^(TB |AFE )' "$out/xsim.log" > "$out/tb.txt"
  [ -f "$out/ftel_ppi.csv" ] && csv+=("$out/ftel_ppi.csv")
  local lim="${MAXTR:-0}"
  [ "${#csv[@]}" -eq 2 ] && lim="-,$lim"
  echo "trailer limit (AMD, ftel_dphy_rx or ftel_dphy_rx alone): $lim" >> "$out/args.txt"
  python3 "$FPGA/tools/csi2_dump.py" bursts --truth "$out/truth.txt" --lanes "$nl" --max-trailer="$lim" \
    "${csv[@]}" > "$out/check.txt" 2>&1
  local rc=$?
  echo "$name ($(( $(date +%s) - t0 )) s): $(grep -m1 '^TB DONE' "$out/tb.txt" | cut -c1-60)..."
  grep -E '^(RESULT|[AB] )' "$out/check.txt"
  return $rc
}

e1_1() { run 1440 4 E1-1; }
e1_2() {
  run 1440 4 E1-2a +PATTERN=prbs9 +LENS=1,2,3,8,64,256,1024 +REPEAT=2
  run 1440 4 E1-2b +PATTERN=synclike +LENS=4,8,16,64,256,1024
  run 1440 4 E1-2c +UNEVEN=1 +LENS=2,3,5,9,65,257
}
e1_3() {
  local l=+LENS=1,4,64,256
  run 1440 4 E1-3a $l +PREP=min +ZERO=min
  run 1440 4 E1-3b $l +PREP=max +ZERO=min
  run 1440 4 E1-3c $l +TRAIL=min +EXIT=min +LPX=min
  run 1440 4 E1-3d $l +CLK_SKEW=139
  run 1440 4 E1-3e $l +SKEW0=139 +SKEW1=139 +SKEW2=139 +SKEW3=139
  run 1440 4 E1-3f $l +SKEW1=46 +SKEW2=93 +SKEW3=139
  run 1440 4 E1-3g $l +AFE_NOISE=1
}
# Trailer bytes that HAS v0.16 Table 4-7 allows ftel_dphy_rx with the eot_skip_bytes of Table 3-2: none without
# junk from 600 Mb/s, otherwise its last column, floor((TEOT,max + 29 ns) / byte period) - eot_skip_bytes.
tmax() {   # tmax <rate Mb/s> <junk ns>
  if [ "$2" -eq 0 ] && [ "$1" -ge 600 ]; then
    echo 0
    return
  fi
  case $1 in 260) echo 4 ;; 400) echo 6 ;; 600) echo 7 ;; 800) echo 8 ;; 1000) echo 9 ;; 1200) echo 10 ;;
             1440|1500) echo 12 ;; *) echo 0 ;; esac
}

e1_4() {
  # 260 Mb/s: the lowest rate of AMD's IP on xcvp1902, the low end of the guarantee (fpga/PLAN_TN1_FIX.md)
  MAXTR=$(tmax 260 0) run 260 4 E1-4a +TIMEOUT_US=1500
  MAXTR=$(tmax 260 0) run 260 4 E1-4a_min +TRAIL=min +EXIT=min +LPX=min +TIMEOUT_US=1500
  run 800 4 E1-4b
  run 1500 4 E1-4c
  run 1440 2 E1-4d
  run 1440 1 E1-4e
}
# EoT stress of ftel_dphy_rx alone (the trailer cut is its own): every rate of HAS v0.16 Table 4-7 x trail x
# jitter x junk, LP-11 at every phase of core_clk (400 ppm slow), trailer bytes limited by that table.
e1_5() {
  local r t j n
  for r in 260 400 600 800 1000 1200 1440 1500; do
    for t in min def max; do
      for j in 0 1; do
        for n in 0 40; do
          MAXTR=$(tmax "$r" "$n") \
            run "$r" stub "E1-5_${r}_${t}_j${j}_n${n}" +LENS=1,2,3,4,5,8,16,64,256 +REPEAT=2 \
              $([ "$t" != def ] && echo "+TRAIL=$t") +TRAIL_JITTER=$j +EOT_JUNK=$n +SEED=$(( r + j + n )) \
              +CORE_HALF=2.501 +TIMEOUT_US=2500
        done
      done
    done
  done
}
# Window of eot_skip_bytes (fpga/PLAN_TN1_FIX.md §5): ftel_dphy_rx alone from the value of its configuration
# model - 1 to + 2, where the payload of the shortest trail is lost; trail min and max, junk 0 and 40 ns; LP-11 at every phase of the byte clock
# (trail jitter) and of core_clk (400 ppm slow). A measurement, not a verdict: every burst with trailer bytes
# counts as an error (MAXTR 0) and payload loss shows in the bursts count. Outputs in fpga/work/exp1/window/,
# outside summary.
window() {
  local r t n d s
  for r in ${@:-260 400 600 800 1000 1200 1440 1500}; do
    s=$(python3 "$HERE/cfg_for_rate.py" "$r" | sed -n 's/.*+EOT_SKIP=\([0-9]*\).*/\1/p')
    for t in min max; do
      for n in 0 40; do
        for d in -1 0 1 2; do
          [ $(( s + d )) -lt 0 ] && continue
          run "$r" stub "window/W_${r}_${t}_n${n}_s$(( s + d ))" +EOT_SKIP=$(( s + d )) +TRAIL=$t +TRAIL_JITTER=1 \
            +EOT_JUNK=$n +CORE_HALF=2.501 +SEED=$(( r + n + s + d )) +LENS=1,2,3,4,5,8,16 +REPEAT=40 +TIMEOUT_US=8000
        done
      done
    done
  done
  python3 "$HERE/eot_window.py" "$W/window"
}
# Outside the guaranteed range: reported, not part of the verdict. THS-EXIT keeps S5 of the HAS.
report() {
  MAXTR=1 run 80 stub R-80 +LENS=1,2,3,4,5,8,16,64,256 +THS_EXIT=400 +TIMEOUT_US=2500
}

summary() {
  for c in "$W"/*/check.txt; do
    printf '%-20s %s\n' "$(basename "$(dirname "$c")")" "$(grep -m1 '^RESULT' "$c")"
  done
}

case "${1:-}" in
  build)   build "$2" "$3" ;;
  run)     shift; run "$@" ;;
  E1-1)    e1_1 ;;
  E1-2)    e1_2 ;;
  E1-3)    e1_3 ;;
  E1-4)    e1_4 ;;
  E1-5)    e1_5 ;;
  all)     e1_1; e1_2; e1_3; e1_4; e1_5; summary ;;
  window)  shift; window "$@" ;;
  report)  report ;;
  summary) summary ;;
  *)       sed -n '2,20p' "$0"; exit 2 ;;
esac
