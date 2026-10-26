#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-26
# Description     : Out-of-context synthesis of m_ftel_ppi_act_gate for the XCVP1902 part of the board.
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-26   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
# Out-of-context synthesis of m_ftel_ppi_act_gate (fpga/PLAN_TN2B_GATE.md §3) for xcvp1902-vsva6865-2MP-e-S,
# 4 lanes, byte clock 224 MHz (1792 Mb/s, the design envelope of ftel_dphy_rx). The PPI inputs come from flip-flops
# and gates of ftel_dphy_rx and the output goes to flip-flops of the subsystem, so the ports get delays of a third of
# the period each against the byte clock; the reset is asynchronous, into the reset synchronizer of the block. Not
# the sign-off of a design: that is the whole RX design of TN3. Every result line starts with "RTL".
#   vivado -mode batch -source synth_rtl.tcl -tclargs <work dir>
set work  [lindex $argv 0]
set here  [file dirname [file normalize [info script]]]
file mkdir $work
read_verilog -sv [file join $here m_ftel_ppi_act_gate.sv]
synth_design -top m_ftel_ppi_act_gate -part xcvp1902-vsva6865-2MP-e-S -mode out_of_context \
  -generic PARA_NUM_LANES=4
set period 4.464
create_clock -name byte_clk -period $period [get_ports i_byte_clk]
set io [expr {$period / 3.0}]
set_input_delay  -clock byte_clk $io [get_ports {i_rxactivehs[*] i_rxsynchs[*]}]
set_output_delay -clock byte_clk $io [get_ports {o_rxactivehs[*]}]
set_false_path -from [get_ports i_byte_rst_n]
report_utilization -file [file join $work utilization.rpt]
report_timing_summary -file [file join $work timing.rpt]
report_methodology -file [file join $work methodology.rpt]
report_cdc -file [file join $work cdc.rpt]
set ff [llength [get_cells -hierarchical -filter {PRIMITIVE_TYPE =~ REGISTER.*}]]
set lut [llength [get_cells -hierarchical -filter {REF_NAME =~ LUT*}]]
set wns [get_property SLACK [get_timing_paths -max_paths 1 -setup]]
set whs [get_property SLACK [get_timing_paths -max_paths 1 -hold]]
set meth [get_methodology_violations]
set crit [llength [get_methodology_violations -filter {SEVERITY == {Critical Warning}}]]
set kinds [lsort -unique [lmap v $meth {lindex [split $v #] 0}]]
puts "RTL synth: $ff flip-flops, $lut LUTs, byte clock $period ns: WNS $wns ns, WHS $whs ns"
puts "RTL methodology: [llength $meth] violations, $crit critical warnings: $kinds"
puts "RTL reports in $work: utilization.rpt timing.rpt methodology.rpt cdc.rpt"
