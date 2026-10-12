# Pins of tiny_ibufds_dphy for impl_tiny.tcl: the camera clock lane and data lane 0 of bank 705
# (FPGA_PROTO_PLAN.md §4), the other ports on spare pins of nibbles 4-7 of the same 1.2 V bank.
# Only for the implementation probe; no device image is written from it.
set_property -dict {PACKAGE_PIN CV60 IOSTANDARD MIPI_DPHY} [get_ports clk_p]
set_property -dict {PACKAGE_PIN CV59 IOSTANDARD MIPI_DPHY} [get_ports clk_n]
set_property -dict {PACKAGE_PIN CY61 IOSTANDARD MIPI_DPHY} [get_ports d_p]
set_property -dict {PACKAGE_PIN DA61 IOSTANDARD MIPI_DPHY} [get_ports d_n]
set_property -dict {PACKAGE_PIN CJ60 IOSTANDARD LVCMOS12} [get_ports hs_dis]
set_property -dict {PACKAGE_PIN CK60 IOSTANDARD LVCMOS12} [get_ports q_r]
set_property -dict {PACKAGE_PIN CD60 IOSTANDARD LVCMOS12} [get_ports q_f]
set_property -dict {PACKAGE_PIN CD59 IOSTANDARD LVCMOS12} [get_ports lp_p]
set_property -dict {PACKAGE_PIN CF61 IOSTANDARD LVCMOS12} [get_ports lp_n]
# DDR clock of 1440 Mb/s (720 MHz), so that place and route are timing driven
create_clock -name clk_hs -period 1.389 [get_ports clk_p]
