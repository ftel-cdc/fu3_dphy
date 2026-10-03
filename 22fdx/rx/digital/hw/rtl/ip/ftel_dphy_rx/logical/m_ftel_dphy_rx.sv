//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-03
// Module          : m_ftel_dphy_rx
// Description     : Core of the D-PHY receiver controller: between the AFE and the PPI of the
//                   CSI-2 Rx controller, one clock lane and PARA_NUM_LANES data lanes. Blocks
//                   No. 1, 2, 3, 4, 6 and 7 of release R1; Block No. 5 (R2) and Block No. 8
//                   (configuration path, K3) are absent: the configuration fields are inputs
//                   and the status is exported (rtl_notes D-2).
// Parent          : m_ftel_dphy_rx_wrap
// HAS             : draft v0.11, §1.4, §2.2, §3, §5, Tables 2-2, 3-1, 5-1 and 5-2
// Clock domains   : core, byte
// REQ-IDs         : REQ-001, REQ-002, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009,
//                   REQ-011, REQ-013, REQ-014, REQ-030, REQ-031, REQ-032, REQ-033, REQ-034,
//                   REQ-035, REQ-036, REQ-038, REQ-057, REQ-218, REQ-219, REQ-220, REQ-221,
//                   REQ-222
// OPEN            : K1, K3
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-03   0.1        Ho Khanh Linh Draft against HAS v0.11; open items at their defaults.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
`timescale 1ns/1ps
`default_nettype none
module m_ftel_dphy_rx
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
  // REQ-013, REQ-030, REQ-031, REQ-032, REQ-033, REQ-034, REQ-035, REQ-036, REQ-038
  parameter int PARA_NUM_LANES         = C_NUM_LANES,
  parameter int PARA_DESER_RATIO       = C_DESER_RATIO,
  parameter int PARA_CORE_CLK_MHZ      = C_CORE_CLK_MHZ,
  parameter int PARA_DESKEW_EN         = C_DESKEW_EN,
  parameter int PARA_LPDT_EN           = C_LPDT_EN,
  parameter int PARA_LP_SYNC_STAGES    = C_LP_SYNC_STAGES,
  parameter int PARA_LP_FILTER_CYC     = C_LP_FILTER_CYC,
  parameter int PARA_EOT_DELAY_BYTES   = C_EOT_DELAY_BYTES,
  parameter int PARA_SYNC_SEARCH_BYTES = C_SYNC_SEARCH_BYTES,
  parameter int PARA_DLY_TAP_WIDTH     = C_DLY_TAP_WIDTH
) (
  // ---- clock / reset ----
  // REQ-007, REQ-222
  input  logic                                             i_core_clk,
  // REQ-005, REQ-221
  input  logic                                             i_phy_core_rst,
  // ---- control: PPI link control (Table 5-1) ----
  // REQ-005, REQ-218, REQ-219, REQ-220
  input  logic                                             i_cl_enable,
  input  logic [PARA_NUM_LANES-1:0]                        i_dl_enable,
  input  logic [PARA_NUM_LANES-1:0]                        i_forcerxmode,
  // ---- data out: PPI (Table 5-1), per-lane signals indexed by logical lane ----
  // REQ-002, REQ-004, REQ-014
  output logic                                             o_init_done,
  output logic                                             o_cl_stopstate,
  output logic [PARA_NUM_LANES-1:0]                        o_stopstate,
  output logic                                             o_cl_ulpsactivenot,
  output logic [PARA_NUM_LANES-1:0]                        o_ulpsactivenot,
  output logic                                             o_rxbyteclkhs,
  output logic                                             o_cl_rxclkactivehs,
  output logic                                             o_cl_ulpsclknot,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  o_rxdatahs,
  output logic [PARA_NUM_LANES-1:0]                        o_rxvalidhs,
  output logic [PARA_NUM_LANES-1:0]                        o_rxactivehs,
  output logic [PARA_NUM_LANES-1:0]                        o_rxsynchs,
  output logic [PARA_NUM_LANES-1:0]                        o_rxskewcalhs,
  output logic [PARA_NUM_LANES-1:0]                        o_rxclkesc,
  output logic [PARA_NUM_LANES-1:0]                        o_rxlpdtesc,
  output logic [PARA_NUM_LANES-1:0]                        o_rxulpsesc,
  output logic [PARA_NUM_LANES-1:0][C_NUM_TRIGGERS-1:0]    o_rxtriggeresc,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  o_rxdataesc,
  output logic [PARA_NUM_LANES-1:0]                        o_rxvalidesc,
  output logic [PARA_NUM_LANES-1:0]                        o_errsoths,
  output logic [PARA_NUM_LANES-1:0]                        o_errsotsynchs,
  output logic [PARA_NUM_LANES-1:0]                        o_erresc,
  output logic [PARA_NUM_LANES-1:0]                        o_errsyncesc,
  output logic [PARA_NUM_LANES-1:0]                        o_errcontrol,
  // ---- status: FSM states and event toggles for Block No. 8 (rtl_notes D-2) ----
  output cl_state_t                                        o_sts_cl_state,
  output dl_state_t [PARA_NUM_LANES-1:0]                   o_sts_dl_state,
  output logic                                             o_sts_cl_abort_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_sts_errsoths_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_sts_errsotsynchs_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_sts_erreotsync_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_sts_hs_rx_timeout_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_sts_erresc_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_sts_esc_timeout_tgl,
  // ---- AFE (Table 5-2), per-lane signals indexed by physical lane ----
  // REQ-006
  input  logic [PARA_NUM_LANES-1:0]                        i_afe_lp_dp,
  input  logic [PARA_NUM_LANES-1:0]                        i_afe_lp_dn,
  input  logic                                             i_afe_cl_lp_dp,
  input  logic                                             i_afe_cl_lp_dn,
  input  logic                                             i_afe_byteclk,
  input  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  i_afe_hs_word,
  input  logic                                             i_afe_cl_clk_active,
  output logic [PARA_NUM_LANES-1:0]                        o_afe_hs_en,
  output logic [PARA_NUM_LANES-1:0]                        o_afe_term_en,
  output logic                                             o_afe_cl_hs_en,
  output logic                                             o_afe_cl_term_en,
  output logic [PARA_NUM_LANES-1:0][PARA_DLY_TAP_WIDTH-1:0] o_afe_dly_tap,
  // ---- configuration ----
  // OPEN K3 REQ-008: the configuration fields are inputs of the core until the configuration path is defined
  // CDC_QUASI_STATIC: timing fields of Table 3-2 (HAS §4.1)
  // REQ-057
  input  cfg_timing_t                                      i_cfg_timing,
  // CDC_QUASI_STATIC: lane_map (HAS §4.1)
  input  logic [PARA_NUM_LANES-1:0][f_lane_sel_w(PARA_NUM_LANES)-1:0] i_cfg_lane_map,
  // CDC_QUASI_STATIC: lane_pol (HAS §4.1)
  input  logic [PARA_NUM_LANES-1:0]                        i_cfg_lane_pol
);

  logic                                            w_core_rst_n;
  logic                                            w_byte_clk;
  logic [PARA_NUM_LANES-1:0]                       w_hs_rst_n;
  logic                                            w_cl_en;
  logic [PARA_NUM_LANES-1:0]                       w_dl_en;
  logic [PARA_NUM_LANES-1:0]                       w_force_rise;
  logic                                            w_cl_init_done;
  logic [PARA_NUM_LANES-1:0]                       w_dl_init_done;
  logic                                            w_init_done;
  logic [PARA_NUM_LANES-1:0]                       w_hs_rx_timeout;
  logic [PARA_NUM_LANES-1:0]                       w_esc_timeout;
  logic [C_HS_SETTLE_CYC_W-1:0]                    w_cfg_hs_settle_cyc;
  logic [C_CLK_SETTLE_CYC_W-1:0]                   w_cfg_clk_settle_cyc;
  logic [C_EOT_SKIP_BYTES_W-1:0]                   w_cfg_eot_skip_bytes;
  lp_state_t [PARA_NUM_LANES-1:0]                  w_lp_state;
  logic [PARA_NUM_LANES-1:0][1:0]                  w_lp_sync;
  lp_state_t                                       w_cl_lp_state;
  logic                                            w_cl_clk_active;
  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] w_hs_word;
  logic                                            w_cl_stopstate;
  logic                                            w_cl_ulpsactivenot;
  logic                                            w_cl_ulpsclknot;
  logic                                            w_cl_rxclkactivehs;
  logic                                            w_cl_hs_en;
  logic                                            w_cl_term_en;
  cl_state_t                                       w_cl_state;
  logic                                            w_cl_abort_tgl;
  logic [PARA_NUM_LANES-1:0]                       w_stopstate;
  logic [PARA_NUM_LANES-1:0]                       w_ulpsactivenot;
  logic [PARA_NUM_LANES-1:0]                       w_rxulpsesc;
  logic [PARA_NUM_LANES-1:0][C_NUM_TRIGGERS-1:0]   w_rxtriggeresc;
  logic [PARA_NUM_LANES-1:0]                       w_erresc;
  logic [PARA_NUM_LANES-1:0]                       w_errcontrol;
  logic [PARA_NUM_LANES-1:0]                       w_sync_search_start;
  dl_state_t [PARA_NUM_LANES-1:0]                  w_dl_state;
  logic [PARA_NUM_LANES-1:0]                       w_erresc_tgl;
  logic [PARA_NUM_LANES-1:0]                       w_hs_en;
  logic [PARA_NUM_LANES-1:0]                       w_term_en;
  logic [PARA_NUM_LANES-1:0]                       w_eot_done;
  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] w_rxdatahs;
  logic [PARA_NUM_LANES-1:0]                       w_rxvalidhs;
  logic [PARA_NUM_LANES-1:0]                       w_rxactivehs;
  logic [PARA_NUM_LANES-1:0]                       w_rxsynchs;
  logic [PARA_NUM_LANES-1:0]                       w_rxskewcalhs;
  logic [PARA_NUM_LANES-1:0]                       w_errsoths;
  logic [PARA_NUM_LANES-1:0]                       w_errsotsynchs;

  // ------------------------------------------------------------------ Block No. 6
  // REQ-005, REQ-007, REQ-221
  m_ftel_dphy_rx_timing_init #(
    .PARA_NUM_LANES (PARA_NUM_LANES)
  ) u_timing_init_0 (
    .i_core_clk              (i_core_clk),
    .i_byte_clk              (w_byte_clk),
    .i_phy_core_rst          (i_phy_core_rst),
    .i_cl_enable             (i_cl_enable),
    .i_dl_enable             (i_dl_enable),
    .i_forcerxmode           (i_forcerxmode),
    .i_cl_lp_state           (w_cl_lp_state),
    .i_lp_state              (w_lp_state),
    .i_dl_state              (w_dl_state),
    .o_core_rst_n            (w_core_rst_n),
    .o_hs_rst_n              (w_hs_rst_n),
    .o_cl_en                 (w_cl_en),
    .o_dl_en                 (w_dl_en),
    .o_force_rise            (w_force_rise),
    .o_cl_init_done          (w_cl_init_done),
    .o_dl_init_done          (w_dl_init_done),
    .o_init_done             (w_init_done),
    .o_hs_rx_timeout         (w_hs_rx_timeout),
    .o_esc_timeout           (w_esc_timeout),
    .o_cfg_hs_settle_cyc     (w_cfg_hs_settle_cyc),
    .o_cfg_clk_settle_cyc    (w_cfg_clk_settle_cyc),
    .o_cfg_eot_skip_bytes    (w_cfg_eot_skip_bytes),
    .o_sts_hs_rx_timeout_tgl (o_sts_hs_rx_timeout_tgl),
    .o_sts_esc_timeout_tgl   (o_sts_esc_timeout_tgl),
    .i_cfg_timing            (i_cfg_timing)
  );

  // ------------------------------------------------------------------ Block No. 1
  // REQ-006, REQ-014
  m_ftel_dphy_rx_afe_adapter #(
    .PARA_NUM_LANES      (PARA_NUM_LANES),
    .PARA_DESER_RATIO    (PARA_DESER_RATIO),
    .PARA_LP_SYNC_STAGES (PARA_LP_SYNC_STAGES),
    .PARA_LP_FILTER_CYC  (PARA_LP_FILTER_CYC),
    .PARA_DLY_TAP_WIDTH  (PARA_DLY_TAP_WIDTH)
  ) u_afe_adapter_0 (
    .i_core_clk          (i_core_clk),
    .i_core_rst_n        (w_core_rst_n),
    .i_byte_clk          (w_byte_clk),
    .i_hs_en             (w_hs_en),
    .i_term_en           (w_term_en),
    .i_cl_hs_en          (w_cl_hs_en),
    .i_cl_term_en        (w_cl_term_en),
    .o_lp_state          (w_lp_state),
    .o_lp_sync           (w_lp_sync),
    .o_cl_lp_state       (w_cl_lp_state),
    .o_cl_clk_active     (w_cl_clk_active),
    .o_hs_word           (w_hs_word),
    .o_rxbyteclkhs       (w_byte_clk),
    .i_afe_lp_dp         (i_afe_lp_dp),
    .i_afe_lp_dn         (i_afe_lp_dn),
    .i_afe_cl_lp_dp      (i_afe_cl_lp_dp),
    .i_afe_cl_lp_dn      (i_afe_cl_lp_dn),
    .i_afe_byteclk       (i_afe_byteclk),
    .i_afe_hs_word       (i_afe_hs_word),
    .i_afe_cl_clk_active (i_afe_cl_clk_active),
    .o_afe_hs_en         (o_afe_hs_en),
    .o_afe_term_en       (o_afe_term_en),
    .o_afe_cl_hs_en      (o_afe_cl_hs_en),
    .o_afe_cl_term_en    (o_afe_cl_term_en),
    .o_afe_dly_tap       (o_afe_dly_tap),
    .i_cfg_lane_map      (i_cfg_lane_map),
    .i_cfg_lane_pol      (i_cfg_lane_pol)
  );

  // ------------------------------------------------------------------ Block No. 2
  // REQ-001
  m_ftel_dphy_rx_cl_ctrl u_cl_ctrl_0 (
    .i_core_clk           (i_core_clk),
    .i_core_rst_n         (w_core_rst_n),
    .i_en                 (w_cl_en),
    .i_init_done          (w_cl_init_done),
    .i_lp_state           (w_cl_lp_state),
    .i_clk_active         (w_cl_clk_active),
    .o_stopstate          (w_cl_stopstate),
    .o_ulpsactivenot      (w_cl_ulpsactivenot),
    .o_ulpsclknot         (w_cl_ulpsclknot),
    .o_rxclkactivehs      (w_cl_rxclkactivehs),
    .o_sts_state          (w_cl_state),
    .o_sts_abort_tgl      (w_cl_abort_tgl),
    .o_hs_en              (w_cl_hs_en),
    .o_term_en            (w_cl_term_en),
    .i_cfg_clk_settle_cyc (w_cfg_clk_settle_cyc)
  );

  // ------------------------------------------------------------------ Blocks No. 3 and 4, per data lane
  for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_lane
    // REQ-001, REQ-002, REQ-030
    m_ftel_dphy_rx_dl_ctrl u_dl_ctrl_0 (
      .i_core_clk          (i_core_clk),
      .i_core_rst_n        (w_core_rst_n),
      .i_en                (w_dl_en[x]),
      .i_force_rise        (w_force_rise[x]),
      .i_init_done         (w_dl_init_done[x]),
      .i_hs_rx_timeout     (w_hs_rx_timeout[x]),
      .i_esc_timeout       (w_esc_timeout[x]),
      .i_eot_done          (w_eot_done[x]),
      .i_lp_state          (w_lp_state[x]),
      .o_stopstate         (w_stopstate[x]),
      .o_ulpsactivenot     (w_ulpsactivenot[x]),
      .o_rxulpsesc         (w_rxulpsesc[x]),
      .o_rxtriggeresc      (w_rxtriggeresc[x]),
      .o_erresc            (w_erresc[x]),
      .o_errcontrol        (w_errcontrol[x]),
      .o_sync_search_start (w_sync_search_start[x]),
      .o_sts_state         (w_dl_state[x]),
      .o_sts_erresc_tgl    (w_erresc_tgl[x]),
      .o_hs_en             (w_hs_en[x]),
      .o_term_en           (w_term_en[x]),
      .i_cfg_hs_settle_cyc (w_cfg_hs_settle_cyc)
    );

    // REQ-001, REQ-002, REQ-030
    m_ftel_dphy_rx_hs_datapath #(
      .PARA_SYNC_SEARCH_BYTES (PARA_SYNC_SEARCH_BYTES),
      .PARA_EOT_DELAY_BYTES   (PARA_EOT_DELAY_BYTES)
    ) u_hs_datapath_0 (
      .i_core_clk             (i_core_clk),
      .i_core_rst_n           (w_core_rst_n),
      .i_byte_clk             (w_byte_clk),
      .i_byte_rst_n           (w_hs_rst_n[x]),
      .i_sync_search_start    (w_sync_search_start[x]),
      .i_hs_word              (w_hs_word[x]),
      .o_rxdatahs             (w_rxdatahs[x]),
      .o_rxvalidhs            (w_rxvalidhs[x]),
      .o_rxactivehs           (w_rxactivehs[x]),
      .o_rxsynchs             (w_rxsynchs[x]),
      .o_rxskewcalhs          (w_rxskewcalhs[x]),
      .o_errsoths             (w_errsoths[x]),
      .o_errsotsynchs         (w_errsotsynchs[x]),
      .o_eot_done             (w_eot_done[x]),
      .o_sts_errsoths_tgl     (o_sts_errsoths_tgl[x]),
      .o_sts_errsotsynchs_tgl (o_sts_errsotsynchs_tgl[x]),
      .o_sts_erreotsync_tgl   (o_sts_erreotsync_tgl[x]),
      .i_cfg_eot_skip_bytes   (w_cfg_eot_skip_bytes)
    );
  end

  // ------------------------------------------------------------------ Block No. 7
  // REQ-004, REQ-014
  m_ftel_dphy_rx_ppi_out #(
    .PARA_NUM_LANES   (PARA_NUM_LANES),
    .PARA_DESER_RATIO (PARA_DESER_RATIO)
  ) u_ppi_out_0 (
    .i_cl_en            (w_cl_en),
    .i_dl_en            (w_dl_en),
    .i_cl_stopstate     (w_cl_stopstate),
    .i_cl_ulpsactivenot (w_cl_ulpsactivenot),
    .i_cl_ulpsclknot    (w_cl_ulpsclknot),
    .i_cl_rxclkactivehs (w_cl_rxclkactivehs),
    .i_stopstate        (w_stopstate),
    .i_ulpsactivenot    (w_ulpsactivenot),
    .i_rxulpsesc        (w_rxulpsesc),
    .i_rxtriggeresc     (w_rxtriggeresc),
    .i_erresc           (w_erresc),
    .i_errcontrol       (w_errcontrol),
    .i_rxdatahs         (w_rxdatahs),
    .i_rxvalidhs        (w_rxvalidhs),
    .i_rxactivehs       (w_rxactivehs),
    .i_rxsynchs         (w_rxsynchs),
    .i_rxskewcalhs      (w_rxskewcalhs),
    .i_errsoths         (w_errsoths),
    .i_errsotsynchs     (w_errsotsynchs),
    .i_lp_sync          (w_lp_sync),
    .i_rxbyteclkhs      (w_byte_clk),
    .i_init_done        (w_init_done),
    .o_init_done        (o_init_done),
    .o_cl_stopstate     (o_cl_stopstate),
    .o_stopstate        (o_stopstate),
    .o_cl_ulpsactivenot (o_cl_ulpsactivenot),
    .o_ulpsactivenot    (o_ulpsactivenot),
    .o_rxbyteclkhs      (o_rxbyteclkhs),
    .o_cl_rxclkactivehs (o_cl_rxclkactivehs),
    .o_cl_ulpsclknot    (o_cl_ulpsclknot),
    .o_rxdatahs         (o_rxdatahs),
    .o_rxvalidhs        (o_rxvalidhs),
    .o_rxactivehs       (o_rxactivehs),
    .o_rxsynchs         (o_rxsynchs),
    .o_rxskewcalhs      (o_rxskewcalhs),
    .o_rxclkesc         (o_rxclkesc),
    .o_rxlpdtesc        (o_rxlpdtesc),
    .o_rxulpsesc        (o_rxulpsesc),
    .o_rxtriggeresc     (o_rxtriggeresc),
    .o_rxdataesc        (o_rxdataesc),
    .o_rxvalidesc       (o_rxvalidesc),
    .o_errsoths         (o_errsoths),
    .o_errsotsynchs     (o_errsotsynchs),
    .o_erresc           (o_erresc),
    .o_errsyncesc       (o_errsyncesc),
    .o_errcontrol       (o_errcontrol)
  );

  // ------------------------------------------------------------------ status
  // REQ-001
  assign o_sts_cl_state     = w_cl_state;
  assign o_sts_dl_state     = w_dl_state;
  assign o_sts_cl_abort_tgl = w_cl_abort_tgl;
  assign o_sts_erresc_tgl   = w_erresc_tgl;

`ifndef SYNTHESIS
  // Values locked in this release; config/validate_config.py enforces the same on the YAML.
  // OPEN K1 REQ-011: release R1, 80-1500 Mb/s, deskew bursts detected and flagged only
  // REQ-009, REQ-013, REQ-031, REQ-032, REQ-033, REQ-034
  initial begin : p_check
    if (!(PARA_NUM_LANES inside {1, 2, 4})) $fatal(1, "PARA_NUM_LANES must be 1, 2 or 4");
    if (PARA_DESER_RATIO != C_DESER_RATIO) $fatal(1, "PARA_DESER_RATIO is fixed at 8");
    if (PARA_CORE_CLK_MHZ != C_CORE_CLK_MHZ) $fatal(1, "PARA_CORE_CLK_MHZ is fixed at 200");
    if (PARA_DESKEW_EN != 0) $fatal(1, "PARA_DESKEW_EN = 1 needs Block No. 5 (R2), not in this RTL");
    if (PARA_LPDT_EN != 0) $fatal(1, "PARA_LPDT_EN = 1 needs LPDT reception, not in this RTL (K2)");
  end
`endif
endmodule
`default_nettype wire
