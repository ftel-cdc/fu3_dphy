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
# Created Date    : 2026-10-10
# Description     : Synthesis of ftel_dphy_rx with Design Compiler, one run per library corner and line
#                   rate.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-10   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# ============================================================================
# Synthesis of ftel_dphy_rx with Design Compiler, one run per library corner and line rate.
#
#   run_syn.sh                      [target library], both SSG 0.72 V corners, 1792 and 1500 Mb/s
#   run_syn.sh --rate 1792          one line rate in Mb/s (repeatable)
#   run_syn.sh --corner <corner>    one corner of the library (repeatable),
#                                   e.g. [corner]
#
# Constraints: sdc/m_ftel_dphy_rx_wrap.sdc (design intent) and syn/dc_syn.tcl (environment). The
# clock cells m_ftel_dphy_rx_cg and m_ftel_dphy_rx_clk_inv are replaced by syn/cells/<tech>/
# (rtl_rule K10). Run <tech>_<corner>_<rate>Mbps writes syn/work/<run>/ (DC),
# syn/output/<run>/ (reports) and syn/netlist/<run>/ (netlist, ddc, sdc), all gitignored;
# syn/summarize.sh prints the key numbers. Pass: every run ends with "SYN DONE", no Error- message.
# ============================================================================
set -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IP="$(cd "$HERE/.." && pwd)"
TECH=[tech]
TECH_FILE="$HERE/tech/$TECH.tcl"
CELLS="$HERE/cells/$TECH"
RATES=(); CORNERS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rate)   RATES+=("$2");   shift 2 ;;
    --corner) CORNERS+=("$2"); shift 2 ;;
    *) echo "usage: $0 [--rate <Mb/s>]... [--corner <corner>]..."; exit 2 ;;
  esac
done
[[ ${#RATES[@]} -eq 0 ]]   && RATES=(1792 1500)
[[ ${#CORNERS[@]} -eq 0 ]] && CORNERS=([corner] [corner])
export DC_SHELL_HOME="${DC_SHELL_HOME:-/opt/synopsys/syn/X-2025.06-SP5}"
export PATH="$DC_SHELL_HOME/bin:$PATH"
mkdir -p "$HERE/work"

# RTL in compile order, as sim/vcs_lint.sh reads it, with the clock cells of the technology
FILES="$HERE/work/files_$TECH.lst"
grep -v '^\s*//' "$IP/logical/filelist.f" | grep '\.sv\s*$' \
  | sed "s#\${FTEL_DPHY_RX_PATH}#$IP#; s#\$FTEL_DPHY_RX_PATH#$IP#" | tr -d ' ' \
  | sed "s#^$IP/logical/\(m_ftel_dphy_rx_cg\|m_ftel_dphy_rx_clk_inv\)\.sv#$CELLS/\1.sv#" > "$FILES"
[[ $(grep -c "^$CELLS/" "$FILES") -eq 2 ]] || { echo "clock cells not replaced in $FILES"; exit 1; }

rc=0
for rate in "${RATES[@]}"; do
  for corner in "${CORNERS[@]}"; do
    run="${TECH}_${corner}_${rate}Mbps"
    wd="$HERE/work/$run"
    mkdir -p "$wd"
    ( cd "$wd" && SYN_TECH_FILE="$TECH_FILE" SYN_CORNER="$corner" SYN_RATE_MBPS="$rate" \
        SYN_FILES="$FILES" SYN_SDC="$IP/sdc/m_ftel_dphy_rx_wrap.sdc" \
        SYN_RPT_DIR="$HERE/output/$run" SYN_OUT_DIR="$HERE/netlist/$run" \
        dc_shell -f "$HERE/dc_syn.tcl" -output_log_file dc.log > /dev/null 2>&1 )
    err=$(grep -c '^Error' "$wd/dc.log")
    fin=$(grep -c '^SYN DONE' "$wd/dc.log")
    echo "$run: $err errors, $([[ $fin -gt 0 ]] && echo done || echo FAILED)"
    [[ $err -eq 0 && $fin -gt 0 ]] || rc=1
  done
done
exit $rc
