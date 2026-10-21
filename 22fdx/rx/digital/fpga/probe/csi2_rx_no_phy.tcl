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
# Description     : Probe: MIPI CSI-2 Rx Subsystem 6.0 with and without the PHY, on the XCVP1902
#                   part of the board.
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
# Probe: MIPI CSI-2 Rx Subsystem 6.0 with and without the PHY, on the XCVP1902 part of the board.
#  1. Block design cell with C_INC_PHY false and true: interfaces and pins.
#  2. Generated IP with C_INC_PHY false: how the CSI-2 Rx controller inside is wired
#     (core clock, byte clocks, enables) and its shutdown polarity.
# Usage (from fpga/probe/run_probe.sh): vivado -mode batch -source csi2_rx_no_phy.tcl -tclargs <work dir>
# Every result line starts with "PROBE".

set work [lindex $argv 0]
set part xcvp1902-vsva6865-2MP-e-S
set cfg [list CONFIG.CMN_NUM_LANES 4 CONFIG.C_DPHY_LANES 4 CONFIG.CMN_PXL_FORMAT RAW10 \
           CONFIG.DPY_LINE_RATE 1440 CONFIG.CMN_NUM_PIXELS 4]

# --- 1. interfaces and pins of the block design cell ---------------------------------------
create_project -in_memory -part $part
set_property target_language Verilog [current_project]
create_bd_design probe
foreach incphy {false true} {
  set c [create_bd_cell -type ip -vlnv xilinx.com:ip:mipi_csi2_rx_subsystem:6.0 csi_$incphy]
  set_property -dict [concat $cfg [list CONFIG.C_INC_PHY $incphy]] $c
  puts "PROBE C_INC_PHY=$incphy C_IS_VERSAL=[get_property CONFIG.C_IS_VERSAL $c]\
 DPY_LINE_RATE=[get_property CONFIG.DPY_LINE_RATE $c] lanes=[get_property CONFIG.CMN_NUM_LANES $c]"
  foreach ip [get_bd_intf_pins -of $c] {
    puts "PROBE   intf [get_property NAME $ip] [get_property MODE $ip] [get_property VLNV $ip]"
  }
  foreach p [get_bd_pins -of $c] {
    set w ""
    if {[get_property LEFT $p] ne ""} { set w "\[[get_property LEFT $p]:[get_property RIGHT $p]\]" }
    puts "PROBE   pin  [get_property NAME $p]$w [get_property DIR $p]"
  }
}
close_project

# --- 2. wiring of the controller inside the subsystem without PHY -------------------------
create_project gen [file join $work gen] -part $part -force
set_property target_language Verilog [current_project]
create_ip -name mipi_csi2_rx_subsystem -vendor xilinx.com -library ip -version 6.0 -module_name csi_no_phy
set_property -dict [concat $cfg [list CONFIG.C_INC_PHY false]] [get_ips csi_no_phy]
generate_target {instantiation_template synthesis} [get_ips csi_no_phy]
set gen_dir [file join $work gen gen.gen sources_1 ip csi_no_phy]
set bd_v [lindex [glob -nocomplain [file join $gen_dir bd_0 synth bd_*.v]] 0]
set rx_v [lindex [glob -nocomplain [file join $gen_dir bd_0 ip ip_0 bd_*_rx_0.v]] 0]
set fh [open $bd_v r]; set txt [read $fh]; close $fh
foreach port {core_clk dl0_rxbyteclkhs dl3_rxbyteclkhs cl_enable dl0_shutdown dl0_rxulpmesc m_axis_aclk s_axi_aclk} {
  if {[regexp "\\.$port\\((\[^)\]*)\\)" $txt -> net]} {
    puts "PROBE controller .$port <- $net"
  } else {
    puts "PROBE controller .$port not found"
  }
}
set fh [open $rx_v r]; set txt [read $fh]; close $fh
foreach par {CSI_INV_SHUTDOWN CSI_LANES C_HS_LINE_RATE C_FAMILY} {
  if {[regexp "\\.$par\\s*\\(\\s*(\[^)\]*?)\\s*\\)" $txt -> val]} { puts "PROBE controller $par = $val" }
}
set top_v [file join $gen_dir synth csi_no_phy.v]
set fh [open $top_v r]; set txt [read $fh]; close $fh
foreach {all w name} [regexp -all -inline {(?:input|output) wire (\[[^]]*\] )?(video_out_tdata|rxbyteclkhs_in|dphy_clk_200M)} $txt] {
  puts "PROBE top port $name $w"
}
puts "PROBE done"
