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
# Created Date    : 2026-11-06
# Description     : Environment of the ftel_dphy_rx folder (22fdx/rx/digital) for the flows that
#                   read it from outside: the synthesis and LEC flow of the SoC physical design,
#                   and tool_flow. Exports DPHY_RX_PATH = the folder of this script, on any machine
#                   and from any working directory. Source it in bash, after the set_env.sh of the
#                   SoC workspace:
#                     source <path of 22fdx/rx/digital>/set_env.sh
#                   LIB_PATH is the SoC library: logical/filelist.f reads -y $LIB_PATH/gate under
#                   the define FPT_SIGNOFF. It comes from the environment of the SoC workspace; this
#                   script checks it and never sets it. sim/, syn/ and fpga/ of this folder find
#                   the folder on their own and do not need this script.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-11-06   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------

# This file is sourced: it must not stop the shell of the user (no set -e, return instead of exit).
if [ -z "${BASH_VERSION:-}" ]; then
  echo "set_env.sh: needs bash; source it from a bash shell" >&2
  return 1 2>/dev/null || exit 1
fi
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "set_env.sh: source this file, do not run it:  source ${BASH_SOURCE[0]}" >&2
  exit 1
fi

# The folder of this script, whatever the working directory and wherever the repository is.
_dphy_rx_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" || return 1
_dphy_rx_rc=0
for _dphy_rx_f in logical/filelist.f logical/filelist_rtl.f logical/m_fpt_dphy_rx_wrap.sv \
                  sdc/constraint.sdc; do
  if [[ ! -e "$_dphy_rx_dir/$_dphy_rx_f" ]]; then
    echo "set_env.sh: $_dphy_rx_dir/$_dphy_rx_f not found, so this is not the ftel_dphy_rx folder" >&2
    _dphy_rx_rc=1
  fi
done
if [[ $_dphy_rx_rc -ne 0 ]]; then
  unset _dphy_rx_dir _dphy_rx_f _dphy_rx_rc
  return 1
fi
export DPHY_RX_PATH="$_dphy_rx_dir"

# LIB_PATH: checked only. The flows that read logical/filelist_rtl.f do not need it.
if [[ -z "${LIB_PATH:-}" ]]; then
  _dphy_rx_lib="not set"
  echo "set_env.sh: WARNING: LIB_PATH is not set. logical/filelist.f reads -y \$LIB_PATH/gate" \
       "under FPT_SIGNOFF; source the set_env.sh of the SoC workspace first." >&2
else
  _dphy_rx_lib="ok"
  for _dphy_rx_f in m_fpt_lib_cg m_fpt_lib_clk_inv; do
    if [[ ! -e "$LIB_PATH/gate/$_dphy_rx_f.sv" && ! -e "$LIB_PATH/gate/$_dphy_rx_f.v" ]]; then
      _dphy_rx_lib="incomplete"
      echo "set_env.sh: WARNING: $_dphy_rx_f not found in $LIB_PATH/gate; FPT_SIGNOFF needs it." >&2
    fi
  done
fi

echo "================ ENV PATH ================"
echo "DPHY_RX_PATH      = $DPHY_RX_PATH"
echo "LIB_PATH          = ${LIB_PATH:-} ($_dphy_rx_lib)"
echo "=========================================="
unset _dphy_rx_dir _dphy_rx_f _dphy_rx_rc _dphy_rx_lib
return 0
