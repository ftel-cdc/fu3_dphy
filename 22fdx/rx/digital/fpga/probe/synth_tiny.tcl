#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-12
# Description     : Probe: synthesize tiny_ibufds_dphy.v for the XCVP1902 part of the board.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-12   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# Probe: synthesize tiny_ibufds_dphy.v for the XCVP1902 part of the board. Shows whether the license
# server grants synthesis for xcvp1902 and that IBUFDS_DPHY with HSRX_O into fabric is accepted.
# Usage (from fpga/probe/run_probe.sh): vivado -mode batch -source synth_tiny.tcl -tclargs <work dir>
# Every result line starts with "PROBE"; the license lines are in the Vivado log.

set work [lindex $argv 0]
set here [file dirname [file normalize [info script]]]
read_verilog [file join $here tiny_ibufds_dphy.v]
synth_design -top tiny_ibufds_dphy -part xcvp1902-vsva6865-2MP-e-S
report_utilization -file [file join $work utilization.rpt]
# On Versal the BUFG of the source is mapped to a BUFGCE.
foreach cell {IBUFDS_DPHY BUFG BUFGCE FDRE} {
  puts "PROBE cells $cell = [llength [get_cells -hierarchical -filter "REF_NAME == $cell"]]"
}
puts "PROBE done"
