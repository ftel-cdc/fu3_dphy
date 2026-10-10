# ============================================================================
# Timing constraints of m_ftel_dphy_rx_wrap (ftel_dphy_rx): clocks, clock relationships, timing
# exceptions and I/O budgets, i.e. design intent only. Library-dependent settings (driving cells,
# loads, margins before clock-tree synthesis) are in syn/dc_syn.tcl.
#
# Sources: HAS v0.14 Table 4-1 (clocks), Table 4-2 (crossings), §4.3 (Block No. 1), Table 5-1
# (PPI), Table 5-2 (AFE); doc/rtl_notes.md §6 (constraints of Block No. 1).
# Object names follow the netlist of Design Compiler (registers <signal>_reg). Also read by the
# CDC and RDC flows through sdc_data in cdc/cdc.sgdc and rdc/rdc.sgdc.
#
# Parameters, set before sourcing this file to override the default:
#   DPHY_RX_LINE_RATE_MBPS    top line rate per lane. Default 1792, the envelope of HAS-CSI; R1
#                             of the HAS is 1500 (OPEN K1).
#   DPHY_RX_TIME_UNIT_PER_NS  time units of the library per ns. Default 1000, a library in ps.
#   DPHY_RX_HS_SKEW_NS        clock-data skew at the samplers, AFE and routing together. Default
#                             0 until the AFE team answers A8 (OPEN ADR-001).
# ============================================================================
if {![info exists DPHY_RX_LINE_RATE_MBPS]}   { set DPHY_RX_LINE_RATE_MBPS 1792 }
if {![info exists DPHY_RX_TIME_UNIT_PER_NS]} { set DPHY_RX_TIME_UNIT_PER_NS 1000.0 }
if {![info exists DPHY_RX_HS_SKEW_NS]}       { set DPHY_RX_HS_SKEW_NS 0.0 }

set TU     $DPHY_RX_TIME_UNIT_PER_NS
set T_CORE [expr {5.0 * $TU}]
set T_DDR  [expr {2000.0 / $DPHY_RX_LINE_RATE_MBPS * $TU}]
set T_BYTE [expr {4.0 * $T_DDR}]
set BC     u_dphy_rx_0/u_afe_adapter_0/u_byte_clk_0

# ---- clocks (Table 4-1)
create_clock -name core_clk -period $T_CORE [get_ports i_dphy_rx_core_clk]
# DDR clock, 2 UI. The falling-edge flip-flops run on its inverse, which needs no clock of its own:
# the clock propagates through the clock inverter u_dont_touch_clk_inv_0 with its sense inverted.
create_clock -name ddr_clk -period $T_DDR [get_ports i_dphy_rx_afe_cl_hs_clk]
# Byte clock: the top bit of the divider by 4, defined where it enters the clock gate
# u_dont_touch_cg_0, so that it does not propagate into the counter logic of the divider.
# rxbyteclkhs is this clock behind the gate, whose enable check the library cell provides.
create_generated_clock -name byte_clk -source [get_ports i_dphy_rx_afe_cl_hs_clk] -divide_by 4 \
    [get_pins $BC/u_dont_touch_cg_0/i_clk]
# Every crossing between core_clk and the DDR clock family goes through a synchronizer
# (Table 4-2), so the first synchronizer stage is not timed.
set_clock_groups -asynchronous -group [get_clocks core_clk] -group [get_clocks {ddr_clk byte_clk}]

# ---- samplers (§4.3, Table 5-2): the transmitter centres each DDR clock edge in a bit, so a bit
#      changes a quarter of a DDR clock period after an edge, within the skew budget
set Q_MAX [expr {$T_DDR / 4.0 + $DPHY_RX_HS_SKEW_NS * $TU}]
set Q_MIN [expr {$T_DDR / 4.0 - $DPHY_RX_HS_SKEW_NS * $TU}]
set HS    [get_ports i_dphy_rx_afe_hs_bit*]
set_input_delay -clock ddr_clk -max $Q_MAX $HS
set_input_delay -clock ddr_clk -min $Q_MIN $HS
set_input_delay -clock ddr_clk -clock_fall -max $Q_MAX $HS -add_delay
set_input_delay -clock ddr_clk -clock_fall -min $Q_MIN $HS -add_delay

# ---- parallel registers -> first byte-clock stage (rtl_notes §6). Each half is loaded once per
#      word, 3 DDR clock periods (2.5 for the falling half) before the byte-clock edge that takes
#      it, and loaded again 1 period (1.5) after that edge: setup 3 and hold 3, in periods of the
#      DDR clock. A hold of 2 would check a launch at the capture edge, which the load phase
#      never makes.
set PAR [get_cells -hierarchical reg_half_*]
set PRE [get_cells -hierarchical reg_hs_pre_reg*]
set_multicycle_path 3 -setup -start -from $PAR -to $PRE
set_multicycle_path 3 -hold  -start -from $PAR -to $PRE

# ---- inputs (Tables 5-1, 5-2): the reset, the PPI control and the LP-RX outputs are asynchronous
#      and enter through synchronizers; the configuration is static while it is used (Table 4-2)
set_false_path -from [get_ports {i_dphy_rx_phy_core_rst_n i_dphy_rx_cl_enable i_dphy_rx_dl_enable* \
                                 i_dphy_rx_forcerxmode* i_dphy_rx_afe_lp_d* i_dphy_rx_afe_cl_lp_d* \
                                 i_dphy_rx_cfg_*}]

# ---- outputs launched by rxbyteclkhs (Tables 5-1, 5-2): 30 % of the byte clock is left to the
#      receiver, a budget to agree with the CSI team at integration (OPEN)
set BYTE_OUT [get_ports {o_dphy_rx_rxdatahs* o_dphy_rx_rxvalidhs* o_dphy_rx_rxactivehs* \
                         o_dphy_rx_rxsynchs* o_dphy_rx_rxskewcalhs* o_dphy_rx_errsoths* \
                         o_dphy_rx_errsotsynchs* o_dphy_rx_afe_dly_tap*}]
set_output_delay -clock byte_clk [expr {0.3 * $T_BYTE}] $BYTE_OUT

# ---- outputs launched by core_clk: 40 % of core_clk is left to the receiver (budget, OPEN)
set CORE_OUT [get_ports {o_dphy_rx_init_done o_dphy_rx_rxlpdtesc* o_dphy_rx_rxdataesc* \
                         o_dphy_rx_rxvalidesc* o_dphy_rx_afe_hs_en* o_dphy_rx_afe_term_en* \
                         o_dphy_rx_afe_cl_hs_en o_dphy_rx_afe_cl_term_en}]
set_output_delay -clock core_clk [expr {0.4 * $T_CORE}] $CORE_OUT

# ---- asynchronous outputs, synchronized by the receiver (Table 5-1), and the status of the
#      Block No. 8 placeholder (OPEN K3, ADR-005). rxbyteclkhs and rxclkesc_x are clocks for the
#      receiver and have no output delay.
set_false_path -to [get_ports {o_dphy_rx_cl_stopstate o_dphy_rx_stopstate* o_dphy_rx_cl_ulpsactivenot \
                               o_dphy_rx_ulpsactivenot* o_dphy_rx_cl_rxclkactivehs o_dphy_rx_cl_ulpsclknot \
                               o_dphy_rx_rxulpsesc* o_dphy_rx_rxtriggeresc* o_dphy_rx_erresc* \
                               o_dphy_rx_errsyncesc* o_dphy_rx_errcontrol* o_dphy_rx_sts_*}]
