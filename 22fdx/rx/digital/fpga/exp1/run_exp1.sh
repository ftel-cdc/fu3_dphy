#!/bin/bash
# TN1 of fpga/PLAN_TN1_TN3.md: dummy D-PHY data into AMD's D-PHY RX and into ftel_dphy_rx (the ASIC RTL behind
# an AFE model), in XSIM. Outputs in fpga/work/exp1 (gitignored).
#   fpga/exp1/run_exp1.sh build <rate> <lanes>                 # xrx IP, project, compile, elaborate (~5 min);
#                                                              # once per rate and lane count
#   fpga/exp1/run_exp1.sh run <rate> <lanes> <name> [+arg ...] # one scenario (~15 s), then the check
#   fpga/exp1/run_exp1.sh run <rate> stub <name> [+arg ...]    # ftel_dphy_rx alone, 4 lanes, with xrx_stub.sv
#                                                              # (any rate; AMD's IP needs 260..3200 Mb/s)
#   fpga/exp1/run_exp1.sh E1-1|E1-2|E1-3|E1-4|all              # the scenarios of the plan
#   fpga/exp1/run_exp1.sh summary                              # result line of every scenario run so far
# A build lives in fpga/work/exp1/build_<rate>_<lanes>l (build_stub for the stub); it is compiled and
# elaborated again when a source changed. A scenario writes fpga/work/exp1/<name>/: truth.txt, xil_ppi.csv, ftel_ppi.csv, xsim.log and
# check.txt (fpga/tools/csi2_dump.py bursts). ftel_dphy_rx gets the run-time fields of its configuration
# model at the rate (cfg_for_rate.py) unless the arguments set them.
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
  python3 "$FPGA/tools/csi2_dump.py" bursts --truth "$out/truth.txt" --lanes "$nl" "${csv[@]}" \
    > "$out/check.txt" 2>&1
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
e1_4() {
  run 80 stub E1-4a +LENS=1,2,3,4,5,8,16,64,256 +TIMEOUT_US=2500   # AMD's IP: 260 Mb/s minimum
  run 800 4 E1-4b
  run 1500 4 E1-4c
  run 1440 2 E1-4d
  run 1440 1 E1-4e
}

summary() {
  for c in "$W"/*/check.txt; do
    printf '%-8s %s\n' "$(basename "$(dirname "$c")")" "$(grep -m1 '^RESULT' "$c")"
  done
}

case "${1:-}" in
  build)   build "$2" "$3" ;;
  run)     shift; run "$@" ;;
  E1-1)    e1_1 ;;
  E1-2)    e1_2 ;;
  E1-3)    e1_3 ;;
  E1-4)    e1_4 ;;
  all)     e1_1; e1_2; e1_3; e1_4; summary ;;
  summary) summary ;;
  *)       sed -n '2,16p' "$0"; exit 2 ;;
esac
