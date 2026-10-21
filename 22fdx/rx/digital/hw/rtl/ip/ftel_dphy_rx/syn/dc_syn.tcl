# ============================================================================
# Design Compiler synthesis of ftel_dphy_rx, top m_ftel_dphy_rx_wrap with its default parameters
# (4 lanes). Started by syn/run_syn.sh in syn/work/<run>, which sets SYN_TECH_FILE, SYN_CORNER,
# SYN_RATE_MBPS, SYN_FILES, SYN_SDC, SYN_RPT_DIR and SYN_OUT_DIR.
# Design intent comes from sdc/m_ftel_dphy_rx_wrap.sdc. This script adds the synthesis
# environment: library, clock cells mapped onto it, margins before clock-tree synthesis (ideal
# clocks, no wire load), I/O drive and load.
# ============================================================================
source $::env(SYN_TECH_FILE)
set DB  $TECH(lib_dir)/$TECH(lib_prefix)$::env(SYN_CORNER).db
set RPT $::env(SYN_RPT_DIR)
set OUT $::env(SYN_OUT_DIR)
set TU  $TECH(time_per_ns)
file mkdir $RPT $OUT

set_app_var search_path    [list . $TECH(lib_dir)]
set_app_var target_library [list $DB]
set_app_var link_library   [list * $DB]
set_app_var enable_recovery_removal_arcs true
define_design_lib WORK -path ./WORK

# ---- RTL: logical/filelist.f with the clock cells of the technology (rtl_rule K10)
set fh [open $::env(SYN_FILES) r]
set files [split [string trim [read $fh]] "\n"]
close $fh
if {![analyze -format sverilog $files]} { echo "SYN: ANALYZE FAILED"; exit 1 }
if {![elaborate m_ftel_dphy_rx_wrap]}   { echo "SYN: ELABORATE FAILED"; exit 1 }
current_design m_ftel_dphy_rx_wrap
if {![link]} { echo "SYN: LINK FAILED"; exit 1 }
check_design -summary > $RPT/check_design_pre.rpt

# ---- constraints: design intent, then the environment before clock-tree synthesis
set DPHY_RX_LINE_RATE_MBPS   $::env(SYN_RATE_MBPS)
set DPHY_RX_TIME_UNIT_PER_NS $TU
source -echo $::env(SYN_SDC)
set_clock_uncertainty -setup [expr {0.030 * $TU}] [get_clocks {ddr_clk byte_clk}]
set_clock_uncertainty -hold  [expr {0.010 * $TU}] [get_clocks {ddr_clk byte_clk}]
set_clock_uncertainty -setup [expr {0.100 * $TU}] [get_clocks core_clk]
set_clock_uncertainty -hold  [expr {0.020 * $TU}] [get_clocks core_clk]
set_clock_transition [expr {0.030 * $TU}] [all_clocks]
set_driving_cell -lib_cell $TECH(drive_cell) \
    [remove_from_collection [all_inputs] [get_ports {i_dphy_rx_core_clk i_dphy_rx_afe_cl_hs_clk}]]
set_load [expr {2.0 * $TECH(cap_per_ff)}] [all_outputs]
# The clock cells of Block No. 1 are instances u_dont_touch_* (rtl_rule K12).
set_dont_touch [get_cells -hierarchical u_dont_touch_*]
check_timing > $RPT/check_timing.rpt

compile_ultra -no_autoungroup

# ---- reports
check_design -summary                     > $RPT/check_design_post.rpt
report_qor                                > $RPT/qor.rpt
report_area -hierarchy -nosplit           > $RPT/area_hier.rpt
report_reference -hierarchy -nosplit      > $RPT/reference.rpt
report_constraint -all_violators -nosplit > $RPT/violators.rpt
foreach g {core_clk ddr_clk byte_clk} {
  report_timing -group $g -max_paths 3 -nosplit -input_pins > $RPT/timing_$g.rpt
}
report_timing -delay_type min -max_paths 5 -nosplit       > $RPT/timing_hold.rpt
# Block No. 1 (rtl_notes §6). report_timing takes pins, not cells.
proc hpins {pattern} { return [get_pins -hierarchical -filter "full_name =~ $pattern"] }
set C $TECH(pin_clk)
set D $TECH(pin_d)
report_timing -from [get_ports i_dphy_rx_afe_hs_bit*] -max_paths 2 -nosplit -input_pins \
                                                          > $RPT/b1_samplers.rpt
report_timing -from [hpins *u_byte_clk_0/reg_load_reg/$C] -to [hpins *u_byte_clk_0/reg_load_fall_reg/$D] \
              -nosplit -input_pins                        > $RPT/b1_half_period.rpt
report_timing -from [hpins *reg_half_*/$C] -to [hpins *reg_hs_pre_reg*/$D] -nosplit \
                                                          > $RPT/b1_par2byte_setup.rpt
report_timing -from [hpins *reg_half_*/$C] -to [hpins *reg_hs_pre_reg*/$D] -delay_type min -nosplit \
                                                          > $RPT/b1_par2byte_hold.rpt
report_timing -to [hpins *u_dont_touch_cg_0/*/E] -nosplit -input_pins > $RPT/b1_icg_enable.rpt
report_timing -to [hpins *u_byte_clk_0/*_reg*/$TECH(pin_reset)] -nosplit -input_pins \
                                                          > $RPT/b1_div_recovery.rpt

# ---- outputs
write -format verilog -hierarchy -output $OUT/m_ftel_dphy_rx_wrap.v
write_file -format ddc -hierarchy -output $OUT/m_ftel_dphy_rx_wrap.ddc
write_sdc $OUT/m_ftel_dphy_rx_wrap.sdc
echo "SYN DONE"
exit 0
