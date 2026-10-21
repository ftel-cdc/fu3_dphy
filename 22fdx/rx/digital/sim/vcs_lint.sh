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
# Created Date    : 2026-10-03
# Description     : VCS lint of the ftel_dphy_rx RTL (doc/rtl_rule.md L1), in the form of
#                   ftel_intctl/sim/compile_rtl.sh.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-03   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# ============================================================================
# VCS lint of the ftel_dphy_rx RTL (doc/rtl_rule.md L1), in the form of ftel_intctl/sim/compile_rtl.sh.
#
#   vcs_lint.sh                    wrapper m_ftel_dphy_rx_wrap with PARA_NUM_LANES = 1, 2 and 4;
#                                  writes sim/vcs_lint/manifest.json (sha256 of the RTL linted, counts per run)
#   vcs_lint.sh --module <name>    one module or package: the files of logical/filelist.f up to its own
#                                  (compile order), top = <name>; writes sim/vcs_lint/module_<name>.json
#
# Compile order comes from logical/filelist.f. Pass criterion: exit 0 and no Error-, Warning- or Lint-
# message. Output stays in sim/vcs_lint/ (gitignored).
# ============================================================================
set -o pipefail

export VCS_HOME="${VCS_HOME:-/opt/synopsys/vcs/X-2025.06}"
export PATH="$VCS_HOME/bin:$PATH"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IP="$(cd "$HERE/.." && pwd)"
OUT="$HERE/vcs_lint"
export FTEL_DPHY_RX_PATH="$IP"
mkdir -p "$OUT"

# RTL files in compile order: the source lines of logical/filelist.f, ${FTEL_DPHY_RX_PATH} expanded
mapfile -t FILES < <(grep -v '^\s*//' "$IP/logical/filelist.f" | grep '\.sv\s*$' \
                     | sed "s#\${FTEL_DPHY_RX_PATH}#$IP#; s#\$FTEL_DPHY_RX_PATH#$IP#" | tr -d ' ')

# run <name> <top or -> [extra vcs options...]: compile into $OUT/<name>, log to $OUT/<name>.log
run() {
  local name="$1" top="$2"; shift 2
  local dir="$OUT/$name" log="$OUT/$name.log"
  rm -rf "$dir"; mkdir -p "$dir"
  local topopt=(); [ "$top" != "-" ] && topopt=(-top "$top")
  ( cd "$dir" && vcs -full64 -sverilog -q +lint=all,noVCDE "${topopt[@]}" "$@" "${SRC[@]}" \
      -Mdir="$dir/csrc" -o "$dir/simv" ) > "$log" 2>&1
  local rc=$?
  local e w l
  e=$(grep -c '^Error-\[' "$log"); w=$(grep -c '^Warning-\[' "$log"); l=$(grep -c '^Lint-\[' "$log")
  echo "$name rc=$rc errors=$e warnings=$w lint=$l"
  RESULTS+=("$name|$top|$*|$rc|$e|$w|$l|$log")
  [ "$rc" -eq 0 ] && [ "$e" -eq 0 ] && [ "$w" -eq 0 ] && [ "$l" -eq 0 ]
}

manifest() {  # manifest <json path>
  python3 - "$1" "$IP" "${RESULTS[@]}" <<'EOF'
import datetime, hashlib, json, os, sys
out, ip, rows = sys.argv[1], sys.argv[2], sys.argv[3:]
runs = []
for r in rows:
    name, top, opts, rc, e, w, l, log = r.split("|")
    runs.append({"name": name, "top": top, "options": opts, "rc": int(rc), "errors": int(e),
                 "warnings": int(w), "lint": int(l), "log": os.path.relpath(log, ip)})
rtl = {}
for f in sorted(os.listdir(os.path.join(ip, "logical"))):
    if f.endswith(".sv"):
        rtl["logical/" + f] = hashlib.sha256(open(os.path.join(ip, "logical", f), "rb").read()).hexdigest()
ver = os.popen("vcs -ID 2>/dev/null | grep -m1 -o 'Compiler version [^;]*'").read().strip()
json.dump({"tool": "vcs", "version": ver, "options": "+lint=all,noVCDE",
           "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "pass": all(x["rc"] == 0 and x["errors"] + x["warnings"] + x["lint"] == 0 for x in runs),
           "runs": runs, "rtl": rtl}, open(out, "w"), indent=1)
EOF
}

RESULTS=()
if [ "$1" = "--module" ]; then
  mod="$2"
  SRC=()
  for f in "${FILES[@]}"; do
    [ -f "$f" ] && SRC+=("$f")
    [ "$(basename "$f" .sv)" = "$mod" ] && break
  done
  [ "$(basename "${SRC[-1]}" .sv)" = "$mod" ] || { echo "module $mod not found in logical/filelist.f"; exit 2; }
  top="$mod"; case "$mod" in *_pkg) top="-";; esac
  run "module_$mod" "$top"; rc=$?
  manifest "$OUT/module_$mod.json"
  exit $rc
fi

SRC=("${FILES[@]}")
status=0
for n in 1 2 4; do
  run "wrap_lanes$n" m_ftel_dphy_rx_wrap "-pvalue+m_ftel_dphy_rx_wrap.PARA_NUM_LANES=$n" || status=1
done
manifest "$OUT/manifest.json"
echo "=== VCS lint: $([ $status -eq 0 ] && echo PASS || echo FAIL) (manifest: sim/vcs_lint/manifest.json) ==="
exit $status
