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
# Description     : TN2b (fpga/PLAN_TN2B.md): Vivado project and XSIM scripts of the TN2b testbench for one
#                   line rate.
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
# Creates in <work>/prj the three IPs of PLAN_TN2B.md §4.2 for one line rate, 4 lanes:
#   xtxss     MIPI CSI-2 TX Subsystem 2.2, with its D-PHY (MASTER);
#   xrxss     MIPI CSI-2 RX Subsystem 6.0 with its D-PHY (R-X), configured as the build of the board, plus the
#             PPI monitor port;
#   xrxss_np  the same without the PHY (R-F), fed by ftel_dphy_rx.
# Prints one "EXP2B <ip>:" line with the parameters of each IP, one "EXP2B port" line per port, the parameters of
# the D-PHY cores inside the subsystems (from their block designs, by fpga/tools/bd_summary.py into <work>), and
# the paths inside the subsystems that tb_exp2b.sv reaches ("EXP2B path"). Unless "ips" is given, it then adds the
# RTL of ftel_dphy_rx, the blocks of exp1/, the gate of the PPI of fpga/rtl/ (PLAN_TN2B_GATE.md) and exp2b/*.sv and
# writes the XSIM scripts.
# Usage: vivado -mode batch -source exp2b.tcl -tclargs <work> <rate> [debug level] [ips]

set work     [lindex $argv 0]
set rate     [lindex $argv 1]
set dbg      [expr {[llength $argv] > 2 ? [lindex $argv 2] : "off"}]
set only_ips [expr {[llength $argv] > 3 && [lindex $argv 3] eq "ips"}]
set lanes    4
set here     [file dirname [file normalize [info script]]]
set fpga     [file dirname $here]
set ip       [file dirname $fpga]          ;# the IP files sit in the folder that holds fpga/
set exp1     [file join $fpga exp1]
set part     xcvp1902-vsva6865-2MP-e-S

proc show_ip {name keys} {
  set out {}
  foreach k $keys {
    if {![catch {get_property CONFIG.$k [get_ips $name]} v] && $v ne ""} { lappend out "$k=$v" }
  }
  return [join $out " "]
}

create_project exp2b [file join $work prj] -part $part -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

create_ip -name mipi_csi2_tx_subsystem -vendor xilinx.com -library ip -version 2.2 -module_name xtxss
set_property -dict [list CONFIG.C_CSI_LANES $lanes CONFIG.C_CSI_PIXEL_MODE 4 CONFIG.C_HS_LINE_RATE $rate \
                         CONFIG.C_INC_PHY true CONFIG.SupportLevel 1] [get_ips xtxss]
# Set one by one: some of these may be derived from the others, and Vivado refuses to set a derived value.
foreach {k v} [list C_DPHY_LANES $lanes C_CSI_DATATYPE RAW10 C_CSI_MAX_BPC 10 C_CSI_EN_ACTIVELANES true \
                    C_CSI_CRC_ENABLE true] {
  if {[get_property CONFIG.$k [get_ips xtxss]] ne $v && [catch {set_property CONFIG.$k $v [get_ips xtxss]} err]} {
    puts "EXP2B xtxss: $k not set to $v: [lindex [split $err \n] 0]"
  }
}

set rxcfg [list CONFIG.CMN_NUM_LANES $lanes CONFIG.C_DPHY_LANES $lanes CONFIG.CMN_PXL_FORMAT RAW10 \
                CONFIG.CMN_NUM_PIXELS 4 CONFIG.DPY_LINE_RATE $rate CONFIG.C_HS_LINE_RATE $rate \
                CONFIG.CSI_BUF_DEPTH 16384 CONFIG.C_CSI_EN_ACTIVELANES true CONFIG.C_CSI_FILTER_USERDATATYPE true \
                CONFIG.VFB_TU_WIDTH 96]
create_ip -name mipi_csi2_rx_subsystem -vendor xilinx.com -library ip -version 6.0 -module_name xrxss
set_property -dict [concat $rxcfg [list CONFIG.C_INC_PHY true CONFIG.SupportLevel 1 CONFIG.C_EN_RXPPI_AS_MON true]] \
  [get_ips xrxss]
create_ip -name mipi_csi2_rx_subsystem -vendor xilinx.com -library ip -version 6.0 -module_name xrxss_np
set_property -dict [concat $rxcfg [list CONFIG.C_INC_PHY false]] [get_ips xrxss_np]

set t0 [clock seconds]
generate_target {instantiation_template simulation} [get_ips {xtxss xrxss xrxss_np}]
puts "EXP2B generated in [expr {[clock seconds] - $t0}] s"

puts "EXP2B xtxss: [show_ip xtxss {C_CSI_LANES C_DPHY_LANES C_CSI_DATATYPE C_CSI_PIXEL_MODE C_CSI_MAX_BPC C_CSI_AXIS_TDATA_WIDTH C_CSI_LINE_BUFR_DEPTH C_CSI_VID_INTERFACE C_CSI_CRC_ENABLE C_CSI_EN_ACTIVELANES C_EN_REG_BASED_FE_GEN C_HS_LINE_RATE C_DPHY_MODE C_INC_PHY SupportLevel DPHY_LPX_PERIOD DPHY_ESC_CLK_PERIOD C_DPHY_EN_REG_IF C_CSI_XMIT_INITIAL_DESKEW C_IS_VERSAL}]"
foreach n {xrxss xrxss_np} {
  puts "EXP2B $n: [show_ip $n {C_INC_PHY CMN_NUM_LANES C_DPHY_LANES CMN_PXL_FORMAT CMN_NUM_PIXELS DPY_LINE_RATE C_HS_LINE_RATE CSI_BUF_DEPTH C_CSI_EN_CRC C_CSI_EN_ACTIVELANES C_CSI_FILTER_USERDATATYPE CMN_INC_VFB VFB_TU_WIDTH CMN_VC C_HS_SETTLE_NS C_INIT C_HS_TIMEOUT SupportLevel C_EN_RXPPI_AS_MON DPY_EN_REG_IF C_IS_VERSAL}]"
}

set gen [file join $work prj exp2b.gen sources_1 ip]
foreach n {xtxss xrxss xrxss_np} {
  set veo [file join $gen $n $n.veo]
  if {[catch {open $veo r} f]} { puts "EXP2B port $n: no instantiation template"; continue }
  foreach line [split [read $f] \n] {
    if {[regexp {//\s*(input|output|inout)\s+wire\s*(\[[^]]*\])?\s*(\S+)} $line -> dir w name]} {
      puts "EXP2B port $n $dir $name [string map {{ } {}} $w]"
    }
  }
  close $f
  foreach bd [glob -nocomplain [file join $gen $n bd_0 *.bd]] {
    set out [file join $work "bd_$n.txt"]
    if {[catch {exec python3 [file join $fpga tools bd_summary.py] --params "mipi_dphy|mipi_csi2|axis|smartconnect" \
                  --nets-of "." $bd > $out} err]} {
      puts "EXP2B bd $n: bd_summary.py failed: [lindex [split $err \n] 0]"
    } else {
      puts "EXP2B bd $n: $out"
    }
  }
}
# What tb_exp2b.sv reaches by path. The front-end check reads the LP outputs of the input buffers in the support
# module of the D-PHY inside xrxss (xrxss > inst > phy > inst > inst > <bd>_phy_0_rx_support_i); its instance
# name carries the name Vivado gives the block design, so it goes to the testbench as XRXSS_SUPPORT.
# tx_ppi.csv reads the PPI between the controller and the D-PHY inside xtxss: the ports of the D-PHY instance
# mipi_dphy_0 of its block design (dlx_txdatahs, dlx_txrequesths, dlx_txreadyhs, init_done).
set support ""
foreach v [glob -nocomplain [file join $gen xrxss bd_0 ip * *_phy_0_c1.v]] {
  set f [open $v r]
  regexp {(\w+_rx_support_i)\s*\(} [read $f] -> support
  close $f
}
puts "EXP2B path xrxss: u_xrxss.inst.phy.inst.inst.[expr {$support eq "" ? "NOT FOUND" : $support}]"
set txphy "NOT FOUND"
foreach v [glob -nocomplain [file join $gen xtxss bd_0 sim *.v]] {
  set f [open $v r]
  if {[regexp {\n\s*(\w+_mipi_dphy_0_0)\s+mipi_dphy_0\s*\n?\s*\(} [read $f] -> mod]} { set txphy "mipi_dphy_0 ($mod)" }
  close $f
}
puts "EXP2B path xtxss: u_xtxss.inst.$txphy, ports dlx_txdatahs, dlx_txrequesths, dlx_txreadyhs, init_done"
if {$only_ips} {
  puts "EXP2B done (ips)"
  return
}

set files {}
set f [open [file join $ip logical filelist.f] r]
foreach line [split [read $f] \n] {
  set line [string trim $line]
  if {$line eq "" || [string match "//*" $line] || [string match "+incdir*" $line]} continue
  lappend files [string map [list {${FTEL_DPHY_RX_PATH}} $ip] $line]
}
close $f
foreach n {afe_model.sv ppi_csv_mon.sv} {
  lappend files [file join $exp1 $n]
}
lappend files [file join $fpga rtl m_ftel_ppi_act_gate.sv]
foreach n [lsort [glob [file join $here *.sv]]] {
  lappend files $n
}
add_files -fileset sim_1 -norecurse $files
set_property file_type SystemVerilog [get_files -of_objects [get_filesets sim_1] *.sv]
set s [get_filesets sim_1]
set_property top tb_exp2b $s
set_property top_lib xil_defaultlib $s
set_property generic "NL=$lanes" $s
set_property verilog_define [list "XRXSS_SUPPORT=$support"] $s
set_property include_dirs [list [file join $ip logical]] $s
set_property -name xsim.compile.xvlog.relax -value true -objects $s
set_property -name xsim.elaborate.relax -value true -objects $s
set_property -name xsim.elaborate.debug_level -value $dbg -objects $s
update_compile_order -fileset sim_1
launch_simulation -scripts_only -simset sim_1 -mode behavioral
puts "EXP2B scripts [file join $work prj exp2b.sim sim_1 behav xsim]"
puts "EXP2B done"
