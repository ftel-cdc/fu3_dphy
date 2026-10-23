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
# Description     : Probe (TN2b step S0): simulate the example design of AMD's MIPI CSI-2 TX Subsystem 2.2
#                   (TX-RX loopback) on the part of the board with XSIM, as AMD delivers it.
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
# Probe (TN2b step S0, fpga/PLAN_TN2B.md): the example design of the MIPI CSI-2 TX Subsystem 2.2 is a TX-RX
# loopback. An ATG in system-init mode programs both subsystems, a V-TPG sends one frame to the TX, the CSI-2 RX
# Subsystem receives it through the loopback, and a second ATG checks the ISR, data type and packet count of the
# RX. The probe generates it for the part of the board, simulates it unchanged and reports what TN2b takes from it:
#  1. the verdict of the example's own checker and the simulated time;
#  2. the IPs of the example and their parameters (exdes_ips.txt), the files of the ATG commands and their
#     content (the register sequence of AMD), and the block design (bd_*.txt by fpga/tools/bd_summary.py: how the
#     V-TPG stream reaches s_axis of the TX, tuser included);
#  3. the paths of the PPI inside the TX and of the LP outputs of the input buffers inside the RX, for tb_exp2b.sv.
# Heavy: run it by name (fpga/probe/run_probe.sh csi2_tx_exdes_sim). Optional 2nd argument: simulated time
# limit in us (default 6000).

set work [lindex $argv 0]
set limit_us [expr {[llength $argv] > 1 ? [lindex $argv 1] : 6000}]
set part xcvp1902-vsva6865-2MP-e-S
set tools [file join [file dirname [file dirname [file normalize [info script]]]] tools]

proc show_ip {ip names} {
  set out {}
  foreach n $names {
    if {![catch {get_property CONFIG.$n $ip} v] && $v ne ""} { lappend out "$n=$v" }
  }
  return [join $out " "]
}

# The command lists of an ATG in system-init/test mode: four .coe files of binary words, one entry each. The
# control word holds the command in bits [23:16] (2: read, compared with data under mask; 3: write) and the next
# entry in bits [15:8]. Runs of equal entries (the wait loops of the example) are printed once with their count.
proc coe_words {path} {
  set out {}
  set f [open $path r]
  foreach line [split [read $f] \n] {
    set w [string trim [string trim $line] ",;"]
    if {$w ne "" && [regexp {^[01]+$} $w]} { lappend out [expr "0b$w"] }
  }
  close $f
  return $out
}

proc atg_commands {dir suffix} {
  foreach k {addr ctrl data mask} {
    if {![file isfile [file join $dir $k$suffix.coe]]} return
    set $k [coe_words [file join $dir $k$suffix.coe]]
  }
  set prev ""
  set n 0
  for {set i 0} {$i < [llength $addr]} {incr i} {
    set c [lindex $ctrl $i]
    if {$c == 0xFFFFFFFF} break
    set cmd [expr {($c >> 16) & 0xFF}]
    set what [expr {$cmd == 3 ? "write" : ($cmd == 2 ? "read " : "cmd $cmd")}]
    set e [format "%s 0x%08x data 0x%08x mask 0x%08x" $what [lindex $addr $i] [lindex $data $i] [lindex $mask $i]]
    if {$e eq $prev} { incr n; continue }
    if {$n > 1} { puts "PROBE atg$suffix   ... the entry above $n times" }
    puts [format "PROBE atg%s %3d %s" $suffix $i $e]
    set prev $e
    set n 1
  }
  if {$n > 1} { puts "PROBE atg$suffix   ... the entry above $n times" }
}

proc bd_summary {tools bd out params nets} {
  if {[catch {exec python3 [file join $tools bd_summary.py] --params $params --nets-of $nets $bd > $out} err]} {
    puts "PROBE bd_summary failed on $bd: [lindex [split $err \n] 0]"
  } else {
    puts "PROBE bd_summary $out ([llength [split [read [set f [open $out r]]] \n]] lines)"
    close $f
  }
}

# --- 1. the IP and its example design --------------------------------------------------------------------
create_project gen [file join $work gen] -part $part -force
set_property target_language Verilog [current_project]
create_ip -name mipi_csi2_tx_subsystem -vendor xilinx.com -library ip -version 2.2 -module_name csitx
set_property CONFIG.C_EXDES_CONFIG 4Lane_YUV422_8bit_4Pixel_Mode [get_ips csitx]
puts "PROBE ip csitx: [show_ip [get_ips csitx] {C_EXDES_CONFIG C_CSI_LANES C_CSI_DATATYPE C_CSI_PIXEL_MODE C_HS_LINE_RATE C_INC_PHY SupportLevel C_IS_VERSAL}]"
if {[catch {open_example_project -force -in_process -dir [file join $work exdes] [get_ips csitx]} err]} {
  puts "PROBE exdes FAILED: [lindex [split $err \n] 0]"
  puts "PROBE done"
  return
}
set exdir [get_property DIRECTORY [current_project]]
puts "PROBE exdes project $exdir"
puts "PROBE exdes sim top [get_property TOP [get_filesets sim_1]]"
puts "PROBE exdes ips [lsort [get_ips]]"

# --- 2. parameters, ATG commands, block designs --------------------------------------------------------
set rep [file join $work exdes_ips.txt]
file delete -force $rep
foreach ip [lsort [get_ips]] {
  report_property -file $rep -append $ip
  puts "PROBE ip $ip [get_property IPDEF $ip]"
}
puts "PROBE ip properties in $rep"
foreach ip [get_ips] {
  set def [get_property IPDEF $ip]
  if {[string match *mipi_csi2_tx_subsystem* $def]} {
    puts "PROBE tx $ip [show_ip $ip {C_CSI_LANES C_CSI_DATATYPE C_CSI_PIXEL_MODE C_CSI_MAX_BPC C_CSI_AXIS_TDATA_WIDTH C_CSI_LINE_BUFR_DEPTH C_CSI_CRC_ENABLE C_CSI_EN_ACTIVELANES C_EN_REG_BASED_FE_GEN C_HS_LINE_RATE C_INC_PHY SupportLevel DPHY_LPX_PERIOD C_DPHY_EN_REG_IF}]"
  } elseif {[string match *mipi_csi2_rx_subsystem* $def]} {
    puts "PROBE rx $ip [show_ip $ip {CMN_NUM_LANES CMN_PXL_FORMAT CMN_NUM_PIXELS DPY_LINE_RATE C_HS_LINE_RATE C_CSI_EN_CRC C_CSI_EN_ACTIVELANES VFB_TU_WIDTH CSI_BUF_DEPTH C_HS_SETTLE_NS C_INIT C_INC_PHY SupportLevel DPY_EN_REG_IF}]"
  } elseif {[string match *axi_traffic_gen* $def]} {
    foreach p [lsort [list_property $ip CONFIG.*]] {
      set v [get_property $p $ip]
      if {[regexp -nocase {MIF|SYSINIT|MODE|COE} $p]} {
        puts "PROBE atg $ip $p = $v"
        if {[file isfile $v]} {
          set f [open $v r]
          set n 0
          foreach line [split [read $f] \n] {
            if {[string trim $line] ne "" && [incr n] <= 400} { puts "PROBE atg $ip [file tail $v]: $line" }
          }
          close $f
        }
      }
    }
  }
}
foreach f [glob -nocomplain -directory $exdir -type f *.mif *.coe *.mem */*.mif */*.coe */*.mem] {
  puts "PROBE file $f"
}
# The ATG parameters name the .coe files relative to the IP; the example keeps them in imports/.
atg_commands [file join $exdir imports] ""
atg_commands [file join $exdir imports] "2"
set bds [glob -nocomplain [file join $exdir *.srcs sources_1 bd * *.bd]]
foreach bd $bds {
  bd_summary $tools $bd [file join $work "bd_[file rootname [file tail $bd]].txt"] ".*" "."
}
foreach bd [glob -nocomplain [file join $exdir *.gen sources_1 bd * ip * bd_0 *.bd]] {
  bd_summary $tools $bd [file join $work "sub_[file tail [file dirname [file dirname $bd]]].txt"] \
    "mipi_dphy|mipi_csi2|axis|smartconnect|axi_crossbar" "."
}

# --- 3. simulation, paths for tb_exp2b.sv ----------------------------------------------------------------
# The example ships its testbench in imports/ but may leave the top of sim_1 empty: then that testbench is set.
if {[get_property TOP [get_filesets sim_1]] eq ""} {
  foreach tb [glob -nocomplain [file join $exdir imports tb_*.v]] {
    if {[llength [get_files -quiet -of_objects [get_filesets sim_1] $tb]] == 0} {
      add_files -fileset sim_1 -norecurse $tb
    }
    set f [open $tb r]
    regexp -line {^\s*module\s+(\w+)} [read $f] -> top
    close $f
    set_property top $top [get_filesets sim_1]
    set_property top_lib xil_defaultlib [get_filesets sim_1]
    puts "PROBE exdes sim top was empty: set to $top of [file tail $tb], the testbench the example ships"
  }
}
set_property -name xsim.simulate.runtime -value 0ns -objects [get_filesets sim_1]
set t0 [clock seconds]
if {[catch {launch_simulation -simset sim_1 -mode behavioral} err]} {
  puts "PROBE sim FAILED to start: [lindex [split $err \n] 0]"
  puts "PROBE done"
  return
}
puts "PROBE sim compiled in [expr {[clock seconds] - $t0}] s"
foreach pat {*_rx_support_i *_tx_support_i} {
  if {[catch {get_scopes -r $pat} hit]} { set hit {} }
  foreach s [lrange $hit 0 9] { puts "PROBE scope $pat $s" }
}
foreach pat {*dl0_txdatahs *dl0_txrequesths *dl0_txreadyhs *cl_txrequesths *rx_dl0_lp_dp_w *rx_cl_lp_dp_w} {
  if {[catch {get_objects -r $pat} hit]} { set hit {} }
  foreach o [lrange $hit 0 9] { puts "PROBE object $pat $o" }
}

set t1 [clock seconds]
set step_us 100
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
puts "PROBE simulated to [current_time] in [expr {[clock seconds] - $t1}] s (limit $limit_us us)"
close_sim
foreach log [glob -nocomplain [file join $exdir *.sim sim_1 behav xsim simulate.log]] {
  set f [open $log r]
  set n 0
  foreach line [split [read $f] \n] {
    if {[regexp -nocase {pass|fail|error|test|frame|status|done} $line] && [incr n] <= 60} { puts "PROBE tb: $line" }
  }
  close $f
  puts "PROBE simulate.log $log"
}
puts "PROBE done"
