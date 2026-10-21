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
#   run_syn.sh                      the corners of FTEL_LIB_CORNERS (.env), 1792 and 1500 Mb/s
#   run_syn.sh --rate 1792          one line rate in Mb/s (repeatable)
#   run_syn.sh --corner <corner>    one corner of the library (repeatable), named as in its .db files
#
# The standard-cell library comes from .env of the IP folder (see .env.example); syn/tech.tcl reads it.
# Constraints: sdc/m_ftel_dphy_rx_wrap.sdc (design intent) and syn/dc_syn.tcl (environment). The
# clock cells m_ftel_dphy_rx_cg and m_ftel_dphy_rx_clk_inv are replaced by syn/cells/ (rtl_rule K10).
# Run <corner>_<rate>Mbps writes syn/work/<run>/ (DC), syn/output/<run>/ (reports) and
# syn/netlist/<run>/ (netlist, ddc, sdc), all gitignored; syn/summarize.sh prints the key numbers.
# Pass: every run ends with "SYN DONE", no Error- message.
# ============================================================================
set -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IP="$(cd "$HERE/.." && pwd)"
[[ -f "$IP/.env" ]] || { echo "run_syn.sh: $IP/.env is missing: copy .env.example to .env and fill it in"; exit 2; }
set -a; . "$IP/.env"; set +a
for v in FTEL_LIB_DB_DIR FTEL_LIB_DB_PREFIX FTEL_LIB_CORNERS; do
  [[ -n "${!v}" ]] || { echo "run_syn.sh: $v is not set in $IP/.env (see .env.example)"; exit 2; }
done
TECH_FILE="$HERE/tech.tcl"
CELLS="$HERE/cells"
RATES=(); CORNERS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rate)   RATES+=("$2");   shift 2 ;;
    --corner) CORNERS+=("$2"); shift 2 ;;
    *) echo "usage: $0 [--rate <Mb/s>]... [--corner <corner>]..."; exit 2 ;;
  esac
done
[[ ${#RATES[@]} -eq 0 ]]   && RATES=(1792 1500)
[[ ${#CORNERS[@]} -eq 0 ]] && read -r -a CORNERS <<< "$FTEL_LIB_CORNERS"
export DC_SHELL_HOME="${DC_SHELL_HOME:-/opt/synopsys/syn/X-2025.06-SP5}"
export PATH="$DC_SHELL_HOME/bin:$PATH"
mkdir -p "$HERE/work"

# RTL in compile order, as sim/vcs_lint.sh reads it, with the clock cells of the library
FILES="$HERE/work/files.lst"
grep -v '^\s*//' "$IP/logical/filelist.f" | grep '\.sv\s*$' \
  | sed "s#\${FTEL_DPHY_RX_PATH}#$IP#; s#\$FTEL_DPHY_RX_PATH#$IP#" | tr -d ' ' \
  | sed "s#^$IP/logical/\(m_ftel_dphy_rx_cg\|m_ftel_dphy_rx_clk_inv\)\.sv#$CELLS/\1.sv#" > "$FILES"
[[ $(grep -c "^$CELLS/" "$FILES") -eq 2 ]] || { echo "clock cells not replaced in $FILES"; exit 1; }

rc=0
for rate in "${RATES[@]}"; do
  for corner in "${CORNERS[@]}"; do
    run="${corner}_${rate}Mbps"
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
