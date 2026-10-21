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
# Description     : Probe: how the MIPI D-PHY 4.3 of AMD builds its receiver on Versal (the XCVP1902
#                   part of the board).
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
# Probe: how the MIPI D-PHY 4.3 of AMD builds its receiver on Versal (the XCVP1902 part of the board).
# Generates a D-PHY RX (4 lanes, 1440 Mb/s, shared logic in the core) and reports
#  - the Advanced IO Wizard sub-core it uses and the parameters the D-PHY sets on it,
#  - how the support logic makes rxbyteclkhs from the FIFO write clock of the wizard.
# Usage (from fpga/probe/run_probe.sh): vivado -mode batch -source dphy_rx_versal.tcl -tclargs <work dir>
# Every result line starts with "PROBE".

set work [lindex $argv 0]
set part xcvp1902-vsva6865-2MP-e-S
create_project gen [file join $work gen] -part $part -force
set_property target_language Verilog [current_project]
create_ip -name mipi_dphy -vendor xilinx.com -library ip -version 4.3 -module_name dphy_rx4
set_property -dict [list CONFIG.C_DPHY_MODE SLAVE CONFIG.C_DPHY_LANES 4 CONFIG.C_HS_LINE_RATE 1440 \
                         CONFIG.SupportLevel 1] [get_ips dphy_rx4]
foreach k {C_DPHY_MODE C_DPHY_LANES C_HS_LINE_RATE SupportLevel C_VERSAL C_HS_SETTLE_NS} {
  puts "PROBE dphy $k = [get_property CONFIG.$k [get_ips dphy_rx4]]"
}
generate_target {instantiation_template synthesis} [get_ips dphy_rx4]

# the wizard sub-core: its .xci records the values the D-PHY propagates to it
set gen_dir [file join $work gen gen.gen sources_1 ip dphy_rx4]
set xci [lindex [glob -nocomplain [file join $gen_dir ip_0 *io_wiz_rx.xci]] 0]
puts "PROBE wizard sub-core [file tail $xci]"
set fh [open $xci r]; set txt [read $fh]; close $fh
foreach k {TEMPLATE DIFF_IO_STD MIPI_RX_DATA_SPEED DATA_SPEED BUS0_DIR BUS0_NUM_PINS BUS0_STROBE_EN \
           BUS0_XPHY_ATTR RX_SERIALIZATION_FACTOR CLK_TO_DATA_ALIGN PLL_IN_CORE PLL_CLK_SOURCE INPUT_CLK_FREQ \
           PLL_FIFO_WRITE_CLK_EN BITSLIP_MODE} {
  if {[regexp "\"$k\": \\\[ \\\{ \"value\": \"(\[^\"\]*)\"" $txt -> val]} {
    puts "PROBE wizard $k = $val"
  } else {
    puts "PROBE wizard $k = ?"
  }
}
# byte clock of the D-PHY: FIFO write clock of the strobe nibble through a BUFG
set sup [lindex [glob -nocomplain [file join $gen_dir dphy_rx4 support dphy_rx4_support.v]] 0]
set fh [open $sup r]; set txt [read $fh]; close $fh
foreach pat {{assign div4_clk_t = fifo_wr_clk_w\[0\];} {BUFG rxbyteclkhs_buf} {assign  rxbyteclkhs               = div4_clk_w;}
             {\.fifo_rd_en\s+\(~fifo_empty_w} {\.bank0_pll_clkin\s+\(core_ref_clk_w} {assign  lp_rx_disable_w           = }} {
  puts "PROBE support [expr {[regexp -- $pat $txt] ? "has" : "lacks"}]: $pat"
}
puts "PROBE done"
