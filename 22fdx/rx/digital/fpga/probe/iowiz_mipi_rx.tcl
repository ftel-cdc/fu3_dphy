# Probe: an Advanced IO Wizard 1.1 with the MIPI_RX template, created on its own (outside the
# MIPI D-PHY IP), with the 44 parameter values the MIPI D-PHY 4.3 sets on its wizard sub-core
# (see dphy_rx_versal.tcl). Reports the ports of the generated wizard and the input buffer it
# instantiates for MIPI_DPHY.
# Usage (from fpga/probe/run_probe.sh): vivado -mode batch -source iowiz_mipi_rx.tcl -tclargs <work dir>
# Every result line starts with "PROBE".

set work [lindex $argv 0]
set part xcvp1902-vsva6865-2MP-e-S
# Values of the wizard sub-core of a D-PHY RX: 4 lanes, 1440 Mb/s (dphy_rx_versal.tcl, 2026-10-12)
set wiz_cfg {
  APPLICATION_TYPE SOURCE_SYNCHRONOUS  BITSLIP_VAL 0x002C  BUS0_IO_TYPE DIFF  BUS0_NUM_PINS 4
  BUS0_SIG_NAME data_rx  BUS0_SIG_TYPE Data  BUS0_STROBE_EN 1  BUS0_STROBE_IO_TYPE DIFF
  BUS0_STROBE_NAME clk_rx  BUS_DIR 1  CLK_FWD_PHASE 0  CLK_TO_DATA_ALIGN 3  DATA_SPEED 1500.00
  DIFF_IO_STD MIPI_DPHY  ENABLE_BITSLIP 0  ENABLE_BLI 1  ENABLE_PLLOUT1 0  ENABLE_RIU_INTERFACE 0
  ENABLE_XPLL_DESKEW 1  EXDES_INST 0  INPUT_CLK_FREQ 200.000  MIPI_DESKEW_EN 0  MIPI_RX_DATA_SPEED 1440
  MULTI_BANK_EN 0  PLL0_PLLOUTCLK1 200.000  PLL_ACROSS_BANKS 0  PLL_CLK_SOURCE BUFG_TO_PLL
  PLL_FIFO_WRITE_CLK_EN 1  PLL_IN_CORE 1  RIU_FROM_PLL 0  RX_APP_CLK_FREQ 100.000  RX_DELAY_CASCADE 0
  RX_DELAY_FORMAT TIME  RX_DELAY_TYPE 0  RX_DELAY_VALUE 0  RX_SERIALIZATION_FACTOR 8  TEMPLATE MIPI_RX
  TRI_SELECT 1  TX_APP_CLK_FREQ 100.000  TX_DELAY_FORMAT TIME  TX_DELAY_TYPE 0  TX_DELAY_VALUE 0
  TX_SERIALIZATION_FACTOR 8  WIZ_OVERRIDE 0
}

create_project gen [file join $work gen] -part $part -force
set_property target_language Verilog [current_project]
create_ip -name advanced_io_wizard -vendor xilinx.com -library ip -version 1.1 -module_name mipi_rx_xphy
set d {}
foreach {k v} $wiz_cfg { lappend d CONFIG.$k $v }
set_property -dict $d [get_ips mipi_rx_xphy]
foreach k {TEMPLATE DIFF_IO_STD MIPI_RX_DATA_SPEED BUS0_NUM_PINS BUS0_STROBE_EN RX_SERIALIZATION_FACTOR} {
  puts "PROBE wizard $k = [get_property CONFIG.$k [get_ips mipi_rx_xphy]]"
}
generate_target {instantiation_template synthesis} [get_ips mipi_rx_xphy]
set gen_dir [file join $work gen gen.gen sources_1 ip mipi_rx_xphy]
set fh [open [file join $gen_dir synth mipi_rx_xphy.sv] r]; set txt [read $fh]; close $fh
foreach {all dir w name} [regexp -all -inline {(input|output) wire (\[[^]]*\] )?(\w+);} $txt] {
  puts "PROBE port $dir $w$name"
}
set phy [lindex [glob -nocomplain [file join $gen_dir ip_0 hdl advanced_io_wizard_phy_*.sv]] 0]
set fh [open $phy r]; set txt [read $fh]; close $fh
if {[regexp {IBUFDS_DPHY\s*#\([^;]*?\.HSRX_O\((\w+)\[k\]\)} $txt -> hs]} {
  puts "PROBE phy IBUFDS_DPHY instantiated, HSRX_O drives $hs (XPHY data input)"
} else {
  puts "PROBE phy IBUFDS_DPHY not found"
}
puts "PROBE done"
