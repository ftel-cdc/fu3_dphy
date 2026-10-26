#!/usr/bin/env bash
#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-26
# Description     : Checks of the FPGA-only RTL of fpga/rtl/ (m_ftel_ppi_act_gate, fpga/PLAN_TN2B_GATE.md §3).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-26   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# Checks of m_ftel_ppi_act_gate (fpga/PLAN_TN2B_GATE.md §3). Outputs in fpga/work/rtl (gitignored).
#   fpga/rtl/run_rtl.sh lint     # VCS +lint=all,noVCDE with 1, 2 and 4 lanes (doc/rtl_rule.md L1): 0 Error,
#                                # Warning, Lint
#   fpga/rtl/run_rtl.sh rules    # req_flow/check_rtl_rules.py, profile construct (the block is not part of the IP)
#   fpga/rtl/run_rtl.sh sim      # unit testbench with VCS, 1, 2 and 4 lanes: TB RESULT: PASS
#   fpga/rtl/run_rtl.sh synth    # Vivado out of context on the part of the board (synth_rtl.tcl, ~2 min)
#   fpga/rtl/run_rtl.sh all      # the four, in that order
set -uo pipefail
export VCS_HOME="${VCS_HOME:-/opt/synopsys/vcs/X-2025.06}"
export PATH="$VCS_HOME/bin:$PATH"
HERE=$(cd "$(dirname "$0")" && pwd)
FPGA=$(dirname "$HERE")
IP=$(dirname "$FPGA")
W=$FPGA/work/rtl
VIVADO=${VIVADO:-/opt/xilinx/2025.2/Vivado/bin/vivado}
SRC=("$HERE/m_ftel_ppi_act_gate.sv")
TOP=m_ftel_ppi_act_gate
mkdir -p "$W"

lint() {
  local n d log rc e w l status=0
  for n in 1 2 4; do
    d=$W/lint_$n
    log=$W/lint_$n.log
    rm -rf "$d"
    mkdir -p "$d"
    (cd "$d" && vcs -full64 -sverilog -q +lint=all,noVCDE -top "$TOP" "-pvalue+$TOP.PARA_NUM_LANES=$n" "${SRC[@]}" \
       -Mdir="$d/csrc" -o "$d/simv") > "$log" 2>&1
    rc=$?
    e=$(grep -c '^Error-\[' "$log"); w=$(grep -c '^Warning-\[' "$log"); l=$(grep -c '^Lint-\[' "$log")
    echo "lint $n lane(s): rc=$rc errors=$e warnings=$w lint=$l"
    [ "$rc" -eq 0 ] && [ "$e" -eq 0 ] && [ "$w" -eq 0 ] && [ "$l" -eq 0 ] || status=1
  done
  return $status
}

rules() {
  python3 "$IP/req_flow/check_rtl_rules.py" "$HERE/$TOP.sv" --profile construct
}

sim() {
  local n d status=0
  for n in 1 2 4; do
    d=$W/sim_$n
    rm -rf "$d"
    mkdir -p "$d"
    if ! (cd "$d" && vcs -full64 -sverilog -q -timescale=1ns/1ps "+define+NL=$n" "${SRC[@]}" \
            "$HERE/tb_$TOP.sv" -top "tb_$TOP" -Mdir="$d/csrc" -o "$d/simv") > "$d/compile.log" 2>&1; then
      echo "sim $n lane(s): compile FAILED (see $d/compile.log)"
      status=1
      continue
    fi
    (cd "$d" && ./simv) > "$d/sim.log" 2>&1
    grep -E '^TB (NL|COVERAGE|DIFF|PROPERTY)' "$d/sim.log"
    grep -q '^TB RESULT: PASS' "$d/sim.log" && echo "sim $n lane(s): PASS" || { echo "sim $n lane(s): FAIL"; status=1; }
  done
  return $status
}

synth() {
  local d=$W/synth
  mkdir -p "$d"
  echo "synth: Vivado out of context (~2 min)"
  (cd "$d" && "$VIVADO" -mode batch -nojournal -log "$d/vivado.log" -source "$HERE/synth_rtl.tcl" \
     -tclargs "$d") > "$d/vivado.out" 2>&1
  grep '^RTL ' "$d/vivado.out"
  grep -q '^RTL synth' "$d/vivado.out"
}

case "${1:-}" in
  lint)  lint ;;
  rules) rules ;;
  sim)   sim ;;
  synth) synth ;;
  all)   s=0; lint || s=1; rules || s=1; sim || s=1; synth || s=1; exit $s ;;
  *)     sed -n '23,29p' "$0"; exit 2 ;;
esac
