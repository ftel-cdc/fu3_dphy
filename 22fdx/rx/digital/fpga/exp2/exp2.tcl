#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-22
# Description     : TN2a build: Vivado project with AMD's D-PHY TX (mipi_dphy 4.3 MASTER, module xtx), AMD's
#                   D-PHY RX (SLAVE, module xrx) and the ftel_dphy_rx RTL for one line rate and lane count.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-22   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# TN2a build (fpga/PLAN_TN2A.md §3.2): a Vivado project with AMD's D-PHY TX (mipi_dphy 4.3, MASTER, module xtx)
# and RX (SLAVE, module xrx, as in TN1) for one line rate and lane count, the ftel_dphy_rx RTL (compile order of
# logical/filelist.f), the TN1 blocks that the bench reuses (exp1/dphy_line_gen.sv, afe_model.sv,
# ppi_csv_mon.sv) and the TN2a sources (exp2/*.sv), then the XSIM scripts only. run_exp2.sh compiles and
# elaborates once per build and runs every scenario of that build from the same snapshot with its own plusargs.
# Usage: vivado -mode batch -source exp2.tcl -tclargs <build dir> <rate Mb/s> <lanes> [<debug level>]
# The debug level of xelab is off (fastest) unless given (typical keeps the signals for waveforms and $dumpvars).
# XSIM needs --relax for the RTL, as in TN1 (exp1.tcl).

set work  [lindex $argv 0]
set rate  [lindex $argv 1]
set lanes [lindex $argv 2]
set dbg   [expr {[llength $argv] > 3 ? [lindex $argv 3] : "off"}]
set here  [file dirname [file normalize [info script]]]
set fpga  [file dirname $here]
set ip    [file dirname $fpga]          ;# the IP files sit in the folder that holds fpga/
set exp1  [file join $fpga exp1]
set part  xcvp1902-vsva6865-2MP-e-S

create_project exp2 [file join $work prj] -part $part -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

# AMD's receiver, as in TN1: the init time at its minimum (99 us), everything else at the defaults of the rate
create_ip -name mipi_dphy -vendor xilinx.com -library ip -version 4.3 -module_name xrx
set_property -dict [list CONFIG.C_DPHY_MODE SLAVE CONFIG.C_DPHY_LANES $lanes CONFIG.C_HS_LINE_RATE $rate \
                         CONFIG.SupportLevel 1 CONFIG.C_INIT 99000] [get_ips xrx]

# AMD's transmitter. The mode goes first, because its update procedure sets C_INIT to the MASTER default (1 ms);
# then the init time at its minimum (99 us). Everything else, the HS timing included, stays at the defaults of
# the rate: the IP computes that timing itself and has no parameter for it.
create_ip -name mipi_dphy -vendor xilinx.com -library ip -version 4.3 -module_name xtx
set_property CONFIG.C_DPHY_MODE MASTER [get_ips xtx]
set_property -dict [list CONFIG.C_DPHY_LANES $lanes CONFIG.C_HS_LINE_RATE $rate CONFIG.SupportLevel 1 \
                         CONFIG.C_INIT 99000] [get_ips xtx]
generate_target {simulation} [get_ips {xrx xtx}]

set x [get_ips xrx]
puts "EXP2 xrx: [get_property CONFIG.C_HS_LINE_RATE $x] Mb/s, [get_property CONFIG.C_DPHY_LANES $x] lanes,\
  mode [get_property CONFIG.C_DPHY_MODE $x], HS settle [get_property CONFIG.C_HS_SETTLE_NS $x] ns,\
  init [get_property CONFIG.C_INIT $x] ns, HS timeout [get_property CONFIG.C_HS_TIMEOUT $x],\
  calibration [get_property CONFIG.C_CAL_MODE $x]"
set t [get_ips xtx]
set speed [expr {[catch {get_property SPEED [get_parts $part]} s] ? "unknown" : $s}]
puts "EXP2 xtx: [get_property CONFIG.C_HS_LINE_RATE $t] Mb/s, [get_property CONFIG.C_DPHY_LANES $t] lanes,\
  mode [get_property CONFIG.C_DPHY_MODE $t], LPX [get_property CONFIG.C_LPX_PERIOD $t] ns,\
  init [get_property CONFIG.C_INIT $t] ns, HS timeout [get_property CONFIG.C_HS_TIMEOUT $t],\
  lane-0 txreadyhs for all lanes [get_property CONFIG.C_USE_LANE0_TXREADYHS $t],\
  example simulation [get_property CONFIG.C_EXAMPLE_SIMULATION $t], speed grade $speed"

# ftel_dphy_rx RTL in the order of filelist.f, the TN1 blocks, then the TN2a sources
set files {}
set f [open [file join $ip logical filelist.f] r]
foreach line [split [read $f] \n] {
  set line [string trim $line]
  if {$line eq "" || [string match "//*" $line] || [string match "+incdir*" $line]} continue
  lappend files [string map [list {${FTEL_DPHY_RX_PATH}} $ip] $line]
}
close $f
foreach n {dphy_line_gen.sv afe_model.sv ppi_csv_mon.sv} {
  lappend files [file join $exp1 $n]
}
foreach n [lsort [glob [file join $here *.sv]]] {
  lappend files $n
}
add_files -fileset sim_1 -norecurse $files
set_property file_type SystemVerilog [get_files -of_objects [get_filesets sim_1] *.sv]
set s [get_filesets sim_1]
set_property top tb_exp2a $s
set_property top_lib xil_defaultlib $s
set_property generic "NL=$lanes" $s
set_property include_dirs [list [file join $ip logical]] $s
set_property -name xsim.compile.xvlog.relax -value true -objects $s
set_property -name xsim.elaborate.relax -value true -objects $s
set_property -name xsim.elaborate.debug_level -value $dbg -objects $s
update_compile_order -fileset sim_1
launch_simulation -scripts_only -simset sim_1 -mode behavioral
puts "EXP2 scripts [file join $work prj exp2.sim sim_1 behav xsim]"
puts "EXP2 done"
