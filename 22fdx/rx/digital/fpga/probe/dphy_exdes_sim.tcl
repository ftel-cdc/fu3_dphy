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
# Description     : Probe (step F2): simulate the example design of AMD's MIPI D-PHY 4.3 receiver on
#                   Versal with XSIM.
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
# Probe (step F2): simulate the example design of the MIPI D-PHY 4.3 receiver on Versal with XSIM, to see
# how AMD's D-PHY drives the Advanced IO Wizard (bitslice reset, HS-RX disable, FIFO, byte clock), and
# with which latency and bit order the words reach the PPI (FP-2, FP-3, FP-4, FP-6 of FPGA_PROTO_PLAN.md).
# Heavy: run it by name (fpga/probe/run_probe.sh dphy_exdes_sim). Optional 2nd argument: simulated time
# limit in us (default 400).
# Writes <work>/f2.vcd with the signals listed in the "PROBE signal" lines; they are also logged in the
# waveform database of the example project, which the Vivado GUI can open.

set work [lindex $argv 0]
set limit_us [expr {[llength $argv] > 1 ? [lindex $argv 1] : 400}]
set part xcvp1902-vsva6865-2MP-e-S
create_project gen [file join $work gen] -part $part -force
set_property target_language Verilog [current_project]
create_ip -name mipi_dphy -vendor xilinx.com -library ip -version 4.3 -module_name dphy_rx4
set_property -dict [list CONFIG.C_DPHY_MODE SLAVE CONFIG.C_DPHY_LANES 4 CONFIG.C_HS_LINE_RATE 1440 \
                         CONFIG.SupportLevel 1] [get_ips dphy_rx4]
open_example_project -force -in_process -dir [file join $work exdes] [get_ips dphy_rx4]
puts "PROBE exdes project [get_property DIRECTORY [current_project]]"
puts "PROBE exdes sim top [get_property TOP [get_filesets sim_1]]"
puts "PROBE exdes ips [lsort [get_ips]]"

set_property -name xsim.simulate.runtime -value 0ns -objects [get_filesets sim_1]
set t0 [clock seconds]
launch_simulation -simset sim_1 -mode behavioral
puts "PROBE sim compiled in [expr {[clock seconds] - $t0}] s"

# Signals, by full path (the support files of the RX and of the TX partner are plain text):
#  - RX: wizard ports (reset, HS-RX disable, LP outputs, words, FIFO, PLL), pads, PPI and byte clock;
#  - TX partner: PPI requests and data, to tell when the transmitter started a burst.
set rx /dphy_rx4_tb/dphy_rx4_rx_exdes_i/dphy_rx4_rx_top_i/inst/inst/dphy_rx4_rx_support_i
set tx /dphy_rx4_tb/dphy_rx4_tx_exdes_i/tx_dphy_rx4_tx_top_i/inst/inst/tx_dphy_rx4_tx_support_i
set paths {}
foreach n {
  phy_reset_w pll_locked_w phy_rdy_out bit_slc_rst_w core_ref_clk_w fifo_wr_clk_w fifo_rd_clk_t fifo_empty_w
  rx_cl_disable_ibuf_w rx_dl0_disable_ibuf_w rx_dl1_disable_ibuf_w rx_dl2_disable_ibuf_w rx_dl3_disable_ibuf_w
  rx_cl_lp_dp_w rx_cl_lp_dn_w rx_dl0_lp_dp_w rx_dl0_lp_dn_w
  rx_cl_hs_dp_w rx_dl0_hs_dp_w rx_dl1_hs_dp_w rx_dl2_hs_dp_w rx_dl3_hs_dp_w
  clk_rxp data_rxp rxbyteclkhs
  cl_enable cl_stopstate cl_rxclkactivehs dl0_enable dl0_stopstate dl0_errsoths dl0_errsotsynchs
  dl0_rxdatahs dl0_rxvalidhs dl0_rxactivehs dl0_rxsynchs dl1_rxvalidhs dl2_rxvalidhs dl3_rxvalidhs
} { lappend paths $rx/$n }
foreach n {txbyteclkhs cl_txrequesths dl0_txrequesths dl0_txreadyhs dl0_txdatahs} { lappend paths $tx/$n }
set picked {}
foreach p $paths {
  if {[catch {get_objects $p} hit] || [llength $hit] == 0} {
    puts "PROBE signal NOT FOUND $p"
  } else {
    lappend picked $p
  }
}
puts "PROBE signals logged [llength $picked] of [llength $paths]"
open_vcd [file join $work f2.vcd]
log_vcd $picked
log_wave $picked

# Run in steps so that the log shows progress; stop when the testbench has called $finish.
set t1 [clock seconds]
set step_us 20
for {set done 0} {$done < $limit_us} {incr done $step_us} {
  set before [current_time]
  if {[catch {run $step_us us} err]} {
    puts "PROBE run stopped: [lindex [split $err \n] 0]"
    break
  }
  puts "PROBE progress [current_time] after [expr {[clock seconds] - $t1}] s"
  flush stdout
  if {[current_time] eq $before} break
}
close_vcd
puts "PROBE simulated to [current_time] in [expr {[clock seconds] - $t1}] s (limit $limit_us us)"
set log [file join [get_property DIRECTORY [current_project]] dphy_rx4_ex.sim sim_1 behav xsim simulate.log]
if {![catch {open $log r} f]} {
  foreach line [split [read $f] \n] {
    if {[regexp {MIPI_DPHY_TB : (ERROR|INFO): (Test .*)} $line -> kind msg]} { puts "PROBE tb $kind: $msg" }
  }
  close $f
}
close_sim
puts "PROBE vcd [file join $work f2.vcd]"
puts "PROBE done"
