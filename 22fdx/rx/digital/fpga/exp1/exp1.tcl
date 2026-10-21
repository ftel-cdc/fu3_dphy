# TN1 build (fpga/PLAN_TN1_TN3.md §1): a Vivado project with AMD's D-PHY RX (mipi_dphy 4.3, SLAVE, module
# xrx) for one line rate and lane count, the ftel_dphy_rx RTL (compile order of logical/filelist.f) and the
# TN1 testbench, then the XSIM scripts only. run_exp1.sh compiles and elaborates once per build and runs
# every scenario of that build from the same snapshot with its own plusargs.
# Usage: vivado -mode batch -source exp1.tcl -tclargs <build dir> <rate Mb/s> <lanes> [<debug level>]
# The debug level of xelab is off (fastest) unless given (typical keeps the signals for waveforms).
# XSIM needs --relax for the RTL (the project default, set here explicitly): its ports are "input logic"
# under `default_nettype none, which XSIM rejects without it (VRFC 10-1103) while VCS accepts it.

set work  [lindex $argv 0]
set rate  [lindex $argv 1]
set lanes [lindex $argv 2]
set dbg   [expr {[llength $argv] > 3 ? [lindex $argv 3] : "off"}]
set here  [file dirname [file normalize [info script]]]
set repo  [file dirname [file dirname $here]]
set ip    $repo                ;# the IP files sit in the folder that holds fpga/
set part  xcvp1902-vsva6865-2MP-e-S

create_project exp1 [file join $work prj] -part $part -force
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

# AMD's receiver: the init time at its minimum (99 us), everything else at the defaults of the rate
create_ip -name mipi_dphy -vendor xilinx.com -library ip -version 4.3 -module_name xrx
set_property -dict [list CONFIG.C_DPHY_MODE SLAVE CONFIG.C_DPHY_LANES $lanes CONFIG.C_HS_LINE_RATE $rate \
                         CONFIG.SupportLevel 1 CONFIG.C_INIT 99000] [get_ips xrx]
generate_target {simulation} [get_ips xrx]
set x [get_ips xrx]
puts "EXP1 xrx: [get_property CONFIG.C_HS_LINE_RATE $x] Mb/s, [get_property CONFIG.C_DPHY_LANES $x] lanes,\
  HS settle [get_property CONFIG.C_HS_SETTLE_NS $x] ns, init [get_property CONFIG.C_INIT $x] ns,\
  HS timeout [get_property CONFIG.C_HS_TIMEOUT $x], calibration [get_property CONFIG.C_CAL_MODE $x]"

# ftel_dphy_rx RTL in the order of filelist.f, then the testbench
set files {}
set f [open [file join $ip logical filelist.f] r]
foreach line [split [read $f] \n] {
  set line [string trim $line]
  if {$line eq "" || [string match "//*" $line] || [string match "+incdir*" $line]} continue
  lappend files [string map [list {${FTEL_DPHY_RX_PATH}} $ip] $line]
}
close $f
foreach t {dphy_line_gen.sv afe_model.sv ppi_csv_mon.sv tb_exp1.sv} {
  lappend files [file join $here $t]
}
add_files -fileset sim_1 -norecurse $files
set_property file_type SystemVerilog [get_files -of_objects [get_filesets sim_1] *.sv]
set s [get_filesets sim_1]
set_property top tb_exp1 $s
set_property top_lib xil_defaultlib $s
set_property generic "NL=$lanes" $s
set_property include_dirs [list [file join $ip logical]] $s
set_property -name xsim.compile.xvlog.relax -value true -objects $s
set_property -name xsim.elaborate.relax -value true -objects $s
set_property -name xsim.elaborate.debug_level -value $dbg -objects $s
update_compile_order -fileset sim_1
launch_simulation -scripts_only -simset sim_1 -mode behavioral
puts "EXP1 scripts [file join $work prj exp1.sim sim_1 behav xsim]"
puts "EXP1 done"
