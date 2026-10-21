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
# Created Date    : 2026-10-07
# Description     : Directed simulation of Block No. 1 with tb_afe_adapter.sv at 80, 800, 1500, 1600
#                   and 1792 Mb/s.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-07   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# ============================================================================
# Directed simulation of Block No. 1 (RTL plan of 2026-10-07, B7): compiles the RTL of
# logical/filelist.f with tb_afe_adapter.sv and runs it at 80, 800, 1500, 1600 and 1792 Mb/s.
# Pass: every run prints "TB RESULT: PASS". Output stays in out/ (gitignored).
# ============================================================================
set -o pipefail
export VCS_HOME="${VCS_HOME:-/opt/synopsys/vcs/X-2025.06}"
export PATH="$VCS_HOME/bin:$PATH"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IP="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/out"
rm -rf "$OUT"; mkdir -p "$OUT"
# RTL files in compile order, as sim/vcs_lint.sh reads them
mapfile -t FILES < <(grep -v '^\s*//' "$IP/logical/filelist.f" | grep '\.sv\s*$' \
                     | sed "s#\${FTEL_DPHY_RX_PATH}#$IP#; s#\$FTEL_DPHY_RX_PATH#$IP#" | tr -d ' ')
( cd "$OUT" && vcs -full64 -sverilog -q -timescale=1ns/1ps +incdir+"$IP/logical" "${FILES[@]}" \
    "$HERE/tb_afe_adapter.sv" -top tb_afe_adapter -Mdir="$OUT/csrc" -o "$OUT/simv" ) > "$OUT/compile.log" 2>&1 \
  || { echo "compile FAILED (see $OUT/compile.log)"; exit 1; }
rc=0
for r in 80 800 1500 1600 1792; do
  ( cd "$OUT" && ./simv +RATE=$r ) > "$OUT/sim_$r.log" 2>&1
  res=$(grep -m1 '^TB RESULT' "$OUT/sim_$r.log" || echo "TB RESULT: none (see $OUT/sim_$r.log)")
  echo "$r Mb/s: $res"
  grep -q '^TB RESULT: PASS' "$OUT/sim_$r.log" || rc=1
done
exit $rc
