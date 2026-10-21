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
# Description     : Probe: implement tiny_ibufds_dphy.v (synth, opt, place, route) on the XCVP1902
#                   part of the board with the bank-705 pins of impl_tiny.xdc.
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
# Probe: implement tiny_ibufds_dphy.v (synth, opt, place, route) on the XCVP1902 part of the board with the
# bank-705 pins of impl_tiny.xdc. Shows whether the license server grants implementation for xcvp1902,
# how long it takes and how much memory Vivado needs for this device (FP-7).
# Heavy: run it by name when the machine is idle (fpga/probe/run_probe.sh impl_tiny).
# Usage (from run_probe.sh): vivado -mode batch -source impl_tiny.tcl -tclargs <work dir>
# Every result line starts with "PROBE". No device image is written.

set work [lindex $argv 0]
set here [file dirname [file normalize [info script]]]
set part xcvp1902-vsva6865-2MP-e-S
read_verilog [file join $here tiny_ibufds_dphy.v]
read_xdc [file join $here impl_tiny.xdc]

set last none
foreach {name cmd} {
  synth {synth_design -top tiny_ibufds_dphy -part $part}
  opt   {opt_design}
  place {place_design}
  route {route_design}
} {
  set t [clock seconds]
  if {[catch {uplevel #0 $cmd} err]} {
    puts "PROBE step $name FAIL: [lindex [split $err \n] 0]"
    break
  }
  puts "PROBE step $name ok [expr {[clock seconds] - $t}] s"
  set last $name
}
puts "PROBE last_step $last"

if {$last eq "route"} {
  report_drc -file [file join $work drc.rpt]
  report_timing_summary -file [file join $work timing.rpt]
  report_utilization -file [file join $work utilization.rpt]
  # Internal paths only: the probe sets no input delay on the lanes.
  puts "PROBE wns_ns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]"
}

# Licenses that Vivado checked out, from its own log (run_probe.sh starts Vivado in the work dir).
if {![catch {open vivado.log r} f]} {
  set seen {}
  foreach line [split [read $f] \n] {
    if {[regexp {Got license for feature '([^']+)' and/or device '([^']+)'} $line -> feat dev]} {
      if {[lsearch $seen "$feat/$dev"] < 0} {
        lappend seen "$feat/$dev"
        puts "PROBE license $feat device $dev"
      }
    }
  }
  close $f
}
# Peak resident memory of this Vivado process.
set f [open /proc/[pid]/status r]
regexp {VmHWM:\s+([0-9]+) kB} [read $f] -> hwm
close $f
puts "PROBE peak_rss_mb [expr {$hwm / 1024}]"
puts "PROBE done"
