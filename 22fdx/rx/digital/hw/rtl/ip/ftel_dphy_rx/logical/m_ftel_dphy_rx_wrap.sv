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
// Module          : m_ftel_dphy_rx_wrap
// Description     : IP wrapper of ftel_dphy_rx under the FX1 IP Wrapper Guideline: ports
//                   <dir>_dphy_rx_<name>, active-low reset with its inverter inside. No logic
//                   other than the inverter. The configuration and status ports stand in for
//                   Block No. 8 until the configuration path is defined (K3).
// Parent          : SoC
// HAS             : draft v0.12, §1.3, §4.2, §5, Table 9-1 (K3, K6)
// Clock domains   : core, byte
// REQ-IDs         : REQ-001, REQ-004, REQ-005, REQ-006, REQ-007, REQ-221, REQ-302
// OPEN            : K3, K6
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
module m_ftel_dphy_rx_wrap
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
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
  // REQ-007
  input  logic                                             i_dphy_rx_core_clk,
  // REQ-221, REQ-302
  input  logic                                             i_dphy_rx_phy_core_rst_n,
  // ---- PPI: link control ----
  // REQ-005
  input  logic                                             i_dphy_rx_cl_enable,
  input  logic [PARA_NUM_LANES-1:0]                        i_dphy_rx_dl_enable,
  input  logic [PARA_NUM_LANES-1:0]                        i_dphy_rx_forcerxmode,
  // ---- PPI: outputs ----
  // REQ-004
  output logic                                             o_dphy_rx_init_done,
  output logic                                             o_dphy_rx_cl_stopstate,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_stopstate,
  output logic                                             o_dphy_rx_cl_ulpsactivenot,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_ulpsactivenot,
  output logic                                             o_dphy_rx_rxbyteclkhs,
  output logic                                             o_dphy_rx_cl_rxclkactivehs,
  output logic                                             o_dphy_rx_cl_ulpsclknot,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  o_dphy_rx_rxdatahs,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxvalidhs,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxactivehs,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxsynchs,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxskewcalhs,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxclkesc,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxlpdtesc,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxulpsesc,
  output logic [PARA_NUM_LANES-1:0][C_NUM_TRIGGERS-1:0]    o_dphy_rx_rxtriggeresc,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  o_dphy_rx_rxdataesc,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_rxvalidesc,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_errsoths,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_errsotsynchs,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_erresc,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_errsyncesc,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_errcontrol,
  // ---- status, placeholder of Block No. 8 (K3) ----
  output logic [$bits(cl_state_t)-1:0]                     o_dphy_rx_sts_cl_state,
  output logic [PARA_NUM_LANES-1:0][$bits(dl_state_t)-1:0] o_dphy_rx_sts_dl_state,
  output logic                                             o_dphy_rx_sts_cl_abort_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_sts_errsoths_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_sts_errsotsynchs_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_sts_erreotsync_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_sts_hs_rx_timeout_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_sts_erresc_tgl,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_sts_esc_timeout_tgl,
  // ---- AFE ----
  // REQ-006
  input  logic [PARA_NUM_LANES-1:0]                        i_dphy_rx_afe_lp_dp,
  input  logic [PARA_NUM_LANES-1:0]                        i_dphy_rx_afe_lp_dn,
  input  logic                                             i_dphy_rx_afe_cl_lp_dp,
  input  logic                                             i_dphy_rx_afe_cl_lp_dn,
  input  logic                                             i_dphy_rx_afe_byteclk,
  input  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  i_dphy_rx_afe_hs_word,
  input  logic                                             i_dphy_rx_afe_cl_clk_active,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_afe_hs_en,
  output logic [PARA_NUM_LANES-1:0]                        o_dphy_rx_afe_term_en,
  output logic                                             o_dphy_rx_afe_cl_hs_en,
  output logic                                             o_dphy_rx_afe_cl_term_en,
  output logic [PARA_NUM_LANES-1:0][PARA_DLY_TAP_WIDTH-1:0] o_dphy_rx_afe_dly_tap,
  // ---- configuration, placeholder of Block No. 8 (K3) ----
  // CDC_QUASI_STATIC: timing fields of Table 3-2, lane map and polarity (HAS §4.1)
  input  logic [C_HS_SETTLE_CYC_W-1:0]                     i_dphy_rx_cfg_hs_settle_cyc,
  input  logic [C_CLK_SETTLE_CYC_W-1:0]                    i_dphy_rx_cfg_clk_settle_cyc,
  input  logic [C_TINIT_CYC_W-1:0]                         i_dphy_rx_cfg_tinit_cyc,
  input  logic [C_HS_RX_TIMEOUT_CYC_W-1:0]                 i_dphy_rx_cfg_hs_rx_timeout_cyc,
  input  logic [C_ESC_TIMEOUT_CYC_W-1:0]                   i_dphy_rx_cfg_esc_timeout_cyc,
  input  logic [C_EOT_SKIP_BYTES_W-1:0]                    i_dphy_rx_cfg_eot_skip_bytes,
  input  logic [PARA_NUM_LANES-1:0][f_lane_sel_w(PARA_NUM_LANES)-1:0] i_dphy_rx_cfg_lane_map,
  input  logic [PARA_NUM_LANES-1:0]                        i_dphy_rx_cfg_lane_pol
);

  logic                           w_phy_core_rst;
  cfg_timing_t                    w_cfg_timing;
  cl_state_t                      w_sts_cl_state;
  dl_state_t [PARA_NUM_LANES-1:0] w_sts_dl_state;

  // The wrapper reset is active Low (Wrapper Guideline); phy_core_rst of the core is active High.
  // OPEN K6 REQ-302: active-low wrapper port, inverter inside m_ftel_dphy_rx_wrap
  assign w_phy_core_rst = ~i_dphy_rx_phy_core_rst_n;

  // Wiring only: the configuration fields into the core structure, the states out as vectors.
  // REQ-001
  assign w_cfg_timing.hs_settle_cyc     = i_dphy_rx_cfg_hs_settle_cyc;
  assign w_cfg_timing.clk_settle_cyc    = i_dphy_rx_cfg_clk_settle_cyc;
  assign w_cfg_timing.tinit_cyc         = i_dphy_rx_cfg_tinit_cyc;
  assign w_cfg_timing.hs_rx_timeout_cyc = i_dphy_rx_cfg_hs_rx_timeout_cyc;
  assign w_cfg_timing.esc_timeout_cyc   = i_dphy_rx_cfg_esc_timeout_cyc;
  assign w_cfg_timing.eot_skip_bytes    = i_dphy_rx_cfg_eot_skip_bytes;
  assign o_dphy_rx_sts_cl_state         = w_sts_cl_state;
  assign o_dphy_rx_sts_dl_state         = w_sts_dl_state;

  // REQ-001, REQ-004, REQ-005, REQ-006, REQ-007
  m_ftel_dphy_rx #(
    .PARA_NUM_LANES         (PARA_NUM_LANES),
    .PARA_DESER_RATIO       (PARA_DESER_RATIO),
    .PARA_CORE_CLK_MHZ      (PARA_CORE_CLK_MHZ),
    .PARA_DESKEW_EN         (PARA_DESKEW_EN),
    .PARA_LPDT_EN           (PARA_LPDT_EN),
    .PARA_LP_SYNC_STAGES    (PARA_LP_SYNC_STAGES),
    .PARA_LP_FILTER_CYC     (PARA_LP_FILTER_CYC),
    .PARA_EOT_DELAY_BYTES   (PARA_EOT_DELAY_BYTES),
    .PARA_SYNC_SEARCH_BYTES (PARA_SYNC_SEARCH_BYTES),
    .PARA_DLY_TAP_WIDTH     (PARA_DLY_TAP_WIDTH)
  ) u_dphy_rx_0 (
    .i_core_clk              (i_dphy_rx_core_clk),
    .i_phy_core_rst          (w_phy_core_rst),
    .i_cl_enable             (i_dphy_rx_cl_enable),
    .i_dl_enable             (i_dphy_rx_dl_enable),
    .i_forcerxmode           (i_dphy_rx_forcerxmode),
    .o_init_done             (o_dphy_rx_init_done),
    .o_cl_stopstate          (o_dphy_rx_cl_stopstate),
    .o_stopstate             (o_dphy_rx_stopstate),
    .o_cl_ulpsactivenot      (o_dphy_rx_cl_ulpsactivenot),
    .o_ulpsactivenot         (o_dphy_rx_ulpsactivenot),
    .o_rxbyteclkhs           (o_dphy_rx_rxbyteclkhs),
    .o_cl_rxclkactivehs      (o_dphy_rx_cl_rxclkactivehs),
    .o_cl_ulpsclknot         (o_dphy_rx_cl_ulpsclknot),
    .o_rxdatahs              (o_dphy_rx_rxdatahs),
    .o_rxvalidhs             (o_dphy_rx_rxvalidhs),
    .o_rxactivehs            (o_dphy_rx_rxactivehs),
    .o_rxsynchs              (o_dphy_rx_rxsynchs),
    .o_rxskewcalhs           (o_dphy_rx_rxskewcalhs),
    .o_rxclkesc              (o_dphy_rx_rxclkesc),
    .o_rxlpdtesc             (o_dphy_rx_rxlpdtesc),
    .o_rxulpsesc             (o_dphy_rx_rxulpsesc),
    .o_rxtriggeresc          (o_dphy_rx_rxtriggeresc),
    .o_rxdataesc             (o_dphy_rx_rxdataesc),
    .o_rxvalidesc            (o_dphy_rx_rxvalidesc),
    .o_errsoths              (o_dphy_rx_errsoths),
    .o_errsotsynchs          (o_dphy_rx_errsotsynchs),
    .o_erresc                (o_dphy_rx_erresc),
    .o_errsyncesc            (o_dphy_rx_errsyncesc),
    .o_errcontrol            (o_dphy_rx_errcontrol),
    .o_sts_cl_state          (w_sts_cl_state),
    .o_sts_dl_state          (w_sts_dl_state),
    .o_sts_cl_abort_tgl      (o_dphy_rx_sts_cl_abort_tgl),
    .o_sts_errsoths_tgl      (o_dphy_rx_sts_errsoths_tgl),
    .o_sts_errsotsynchs_tgl  (o_dphy_rx_sts_errsotsynchs_tgl),
    .o_sts_erreotsync_tgl    (o_dphy_rx_sts_erreotsync_tgl),
    .o_sts_hs_rx_timeout_tgl (o_dphy_rx_sts_hs_rx_timeout_tgl),
    .o_sts_erresc_tgl        (o_dphy_rx_sts_erresc_tgl),
    .o_sts_esc_timeout_tgl   (o_dphy_rx_sts_esc_timeout_tgl),
    .i_afe_lp_dp             (i_dphy_rx_afe_lp_dp),
    .i_afe_lp_dn             (i_dphy_rx_afe_lp_dn),
    .i_afe_cl_lp_dp          (i_dphy_rx_afe_cl_lp_dp),
    .i_afe_cl_lp_dn          (i_dphy_rx_afe_cl_lp_dn),
    .i_afe_byteclk           (i_dphy_rx_afe_byteclk),
    .i_afe_hs_word           (i_dphy_rx_afe_hs_word),
    .i_afe_cl_clk_active     (i_dphy_rx_afe_cl_clk_active),
    .o_afe_hs_en             (o_dphy_rx_afe_hs_en),
    .o_afe_term_en           (o_dphy_rx_afe_term_en),
    .o_afe_cl_hs_en          (o_dphy_rx_afe_cl_hs_en),
    .o_afe_cl_term_en        (o_dphy_rx_afe_cl_term_en),
    .o_afe_dly_tap           (o_dphy_rx_afe_dly_tap),
    .i_cfg_timing            (w_cfg_timing),
    .i_cfg_lane_map          (i_dphy_rx_cfg_lane_map),
    .i_cfg_lane_pol          (i_dphy_rx_cfg_lane_pol)
  );
endmodule
`default_nettype wire
