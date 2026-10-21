#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-19
# Description     : Probe: pin facts behind fpga/exp3/TN3_SPEC.md §3–4 (TN3: D-PHY TX on a second FPGA
#                   board -> test board -> RX on the VP1902 board).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-19   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# Probe: pin facts behind fpga/exp3/TN3_SPEC.md §3–4 (TN3: D-PHY TX on a second FPGA board -> test board
# -> RX on the VP1902 board).
# - VEK280 (xcve2802-vsvh1760-2MP-e-S): the VCCO that the MIPI_DPHY standard needs, and the bank of every
#   FMCP1 LA/CLK pin of the VEK280 board file (part0_pins.xml). With the fixed 1.5 V of banks 705/706
#   (UG1612), this shows why the VEK280 cannot be the TX.
# - VP1902 (xcvp1902-vsva6865-2MP-e-S): bank, nibble, site and package delay of the 10 camera pins on
#   FMC+ "01", the RX side of TN3.
# The package delays are the MIN_DELAY/MAX_DELAY properties of the package pins (Vivado device data);
# UG863 asks to include them in every MIPI skew budget. A port placed on one pin and written with write_csv
# shows the unit Vivado gives them.
# Heavy (loads the VP1902 device): run it by name when the machine is idle (fpga/probe/run_probe.sh tn3_pins).
# Usage (from run_probe.sh): vivado -mode batch -source tn3_pins.tcl -tclargs <work dir>
# Every result line starts with "PROBE".

set work [lindex $argv 0]

proc pin_line {tag name ball} {
  set p [get_package_pins -quiet $ball]
  if {$p eq ""} {
    puts "PROBE $tag $name $ball no_such_pin"
    return
  }
  puts "PROBE $tag $name $ball bank=[get_property BANK $p] nibble=[get_property PKGPIN_NIBBLE_INDEX $p]\
    site=[get_property PIN_FUNC $p] delay=[get_property MIN_DELAY $p]..[get_property MAX_DELAY $p]"
}

# VEK280
link_design -part xcve2802-vsvh1760-2MP-e-S
set std [get_io_standards MIPI_DPHY]
puts "PROBE vek280 MIPI_DPHY vcco_in=[get_property VCCO_IN $std] vcco_out=[get_property VCCO_OUT $std]"
set xml [file join [file dirname $env(XILINX_VIVADO)] data xhub boards XilinxBoardStore boards Xilinx \
  vek280 production 1.2 part0_pins.xml]
set f [open $xml r]
set banks {}
foreach line [split [read $f] \n] {
  if {[regexp {name="(fmcp1_(la|clk)[^"]*)"[^>]*loc="([A-Z0-9]+)"} $line -> name - ball]} {
    pin_line vek280 $name $ball
    dict incr banks [get_property BANK [get_package_pins $ball]]
  }
}
close $f
puts "PROBE vek280 fmcp1_la_clk_pins_per_bank $banks"

# Unit of MIN_DELAY/MAX_DELAY, from the write_csv header and the row of one placed port
create_port -direction OUT unit_check
set_property PACKAGE_PIN AR30 [get_ports unit_check]
if {[catch {write_csv -force [file join $work unit_check.csv]} err]} {
  puts "PROBE unit_check write_csv FAIL: [lindex [split $err \n] 0]"
} else {
  set f [open [file join $work unit_check.csv] r]
  foreach line [split [read $f] \n] {
    if {[regexp -nocase {trace|delay|dly} $line] || [string match *unit_check* $line]} {
      puts "PROBE unit_check $line"
    }
  }
  close $f
}
close_design

# VP1902, FMC+ "01" camera pins (netlist of the board)
link_design -part xcvp1902-vsva6865-2MP-e-S
foreach {name ball} {
  clk_p CV60 clk_n CV59 d0_p CY61 d0_n DA61 d1_p CT61 d1_n CU61
  d2_p DC60 d2_n DC59 d3_p DA60 d3_n DA59
} {
  pin_line vp1902 $name $ball
}

set f [open /proc/[pid]/status r]
regexp {VmHWM:\s+([0-9]+) kB} [read $f] -> hwm
close $f
puts "PROBE peak_rss_mb [expr {$hwm / 1024}]"
puts "PROBE done"
