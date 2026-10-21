#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-21
# Description     : Standard-cell library of syn/dc_syn.tcl, taken from the local environment (.env
#                   of the IP folder, see .env.example).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-21   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# ============================================================================
# Standard-cell library of syn/dc_syn.tcl. Nothing about the library is written in the repository:
# syn/run_syn.sh loads .env, and this file reads it from the environment. TECH(...) holds the timing
# models, the units, the cell that drives the inputs and the flip-flop pins named in the reports;
# TECH(defines) passes the clock-gating cell and the clock inverter, with their pins, to the analysis
# of syn/cells/*.sv as defines. A missing variable stops the run with its name.
# ============================================================================
set vars_tech {FTEL_LIB_DB_DIR FTEL_LIB_DB_PREFIX FTEL_LIB_TIME_PER_NS FTEL_LIB_CAP_PER_FF FTEL_LIB_DRIVE_CELL
               FTEL_LIB_FF_PIN_CLK FTEL_LIB_FF_PIN_D FTEL_LIB_FF_PIN_RESET}
set vars_cells {FTEL_LIB_CG_CELL FTEL_LIB_CG_PIN_CLK FTEL_LIB_CG_PIN_EN FTEL_LIB_CG_PIN_TE FTEL_LIB_CG_PIN_GCLK
                FTEL_LIB_CKINV_CELL FTEL_LIB_CKINV_PIN_IN FTEL_LIB_CKINV_PIN_OUT}
foreach v [concat $vars_tech $vars_cells] {
  if {![info exists ::env($v)] || $::env($v) eq ""} {
    echo "SYN: $v is not set (.env of the IP folder, see .env.example)"
    exit 1
  }
}
set TECH(lib_dir)     $::env(FTEL_LIB_DB_DIR)
set TECH(lib_prefix)  $::env(FTEL_LIB_DB_PREFIX)
set TECH(time_per_ns) $::env(FTEL_LIB_TIME_PER_NS)
set TECH(cap_per_ff)  $::env(FTEL_LIB_CAP_PER_FF)
set TECH(drive_cell)  $::env(FTEL_LIB_DRIVE_CELL)
set TECH(pin_clk)     $::env(FTEL_LIB_FF_PIN_CLK)
set TECH(pin_d)       $::env(FTEL_LIB_FF_PIN_D)
set TECH(pin_reset)   $::env(FTEL_LIB_FF_PIN_RESET)
set TECH(defines)     {}
foreach v $vars_cells { lappend TECH(defines) "$v=$::env($v)" }
