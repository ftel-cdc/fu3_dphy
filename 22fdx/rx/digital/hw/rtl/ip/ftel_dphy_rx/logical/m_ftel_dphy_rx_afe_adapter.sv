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
// Module          : m_ftel_dphy_rx_afe_adapter
// Description     : AFE Adapter (HAS Block No. 1): LP path (synchronizers, polarity swap,
//                   glitch filter); HS deserializers, byte clock and clock-activity detection;
//                   HS path (two rxbyteclkhs stages, polarity inversion); lane mapping; AFE
//                   enables. The only block that changes when the AFE changes.
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.14, §4.1, §4.3, Table 4-2, Figure 4-2, §5.2, Table 5-2
// Clock domains   : core (LP path, clock activity, AFE enables), ddr and ddrn (deserializers,
//                   divider), byte (HS path)
// REQ-IDs         : REQ-026, REQ-047, REQ-048, REQ-050, REQ-059, REQ-069, REQ-070, REQ-072,
//                   REQ-074, REQ-075, REQ-077, REQ-079, REQ-080, REQ-081, REQ-102, REQ-183,
//                   REQ-228, REQ-257, REQ-258, REQ-262, REQ-263, REQ-264, REQ-266, REQ-270,
//                   REQ-271, REQ-322, REQ-328, REQ-329, REQ-333, REQ-335, REQ-339, REQ-341,
//                   REQ-343, REQ-345, REQ-348, REQ-355, REQ-356, REQ-357
// OPEN            : ADR-001, ADR-004, ADR-007, S9
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
module m_ftel_dphy_rx_afe_adapter
  import ftel_dphy_rx_pkg::*;
#(
  parameter int PARA_NUM_LANES      = 4,
  parameter int PARA_DESER_RATIO    = 8,
  parameter int PARA_LP_SYNC_STAGES = 2,
  parameter int PARA_LP_FILTER_CYC  = 2,
  parameter int PARA_DLY_TAP_WIDTH  = 1
) (
  // ---- clock / reset ----
  input  logic                                             i_core_clk,
  input  logic                                             i_core_rst_n,
  // DDR clock afe_cl_hs_clk of the AFE, and its reset from Block No. 6.
  // REQ-026, REQ-333
  input  logic                                             i_ddr_clk,
  input  logic                                             i_ddr_rst_n,
  // rxbyteclkhs, generated here (o_rxbyteclkhs) and returned by the core (rtl_notes D-25).
  input  logic                                             i_byte_clk,
  // ---- control: requests of Blocks No. 2 and 3, per logical lane ----
  // REQ-080, REQ-081
  input  logic [PARA_NUM_LANES-1:0]                        i_hs_en,
  input  logic [PARA_NUM_LANES-1:0]                        i_term_en,
  input  logic                                             i_cl_hs_en,
  input  logic                                             i_cl_term_en,
  // Byte-clock enable of Block No. 2, High in CL_HS_CLK.
  // REQ-102
  input  logic                                             i_byteclk_en,
  // ---- data out: line states and words of the logical lanes ----
  output lp_state_t [PARA_NUM_LANES-1:0]                   o_lp_state,
  output logic [PARA_NUM_LANES-1:0][1:0]                   o_lp_sync,
  output lp_state_t                                        o_cl_lp_state,
  output logic                                             o_cl_clk_active,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0]  o_hs_word,
  // REQ-048, REQ-228
  output logic                                             o_rxbyteclkhs,
  // ---- AFE (Table 5-2) ----
  // OPEN ADR-001 REQ-257, REQ-258, REQ-262, REQ-263, REQ-355, REQ-356, REQ-357: AFE interface of option A: LP-RX outputs, unsampled HS bits, the DDR clock (i_ddr_clk) and the enables (Table 5-2)
  input  logic [PARA_NUM_LANES-1:0]                        i_afe_lp_dp,
  input  logic [PARA_NUM_LANES-1:0]                        i_afe_lp_dn,
  input  logic                                             i_afe_cl_lp_dp,
  input  logic                                             i_afe_cl_lp_dn,
  input  logic [PARA_NUM_LANES-1:0]                        i_afe_hs_bit,
  output logic [PARA_NUM_LANES-1:0]                        o_afe_hs_en,
  output logic [PARA_NUM_LANES-1:0]                        o_afe_term_en,
  output logic                                             o_afe_cl_hs_en,
  output logic                                             o_afe_cl_term_en,
  output logic [PARA_NUM_LANES-1:0][PARA_DLY_TAP_WIDTH-1:0] o_afe_dly_tap,
  // ---- configuration ----
  // CDC_QUASI_STATIC: lane_map (HAS §4.1)
  input  logic [PARA_NUM_LANES-1:0][f_lane_sel_w(PARA_NUM_LANES)-1:0] i_cfg_lane_map,
  // CDC_QUASI_STATIC: lane_pol (HAS §4.1)
  input  logic [PARA_NUM_LANES-1:0]                        i_cfg_lane_pol
);

  localparam int C_SEL_W = f_lane_sel_w(PARA_NUM_LANES);

  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] reg_hs_pre;
  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] reg_hs_word;
  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] w_deser_word;
  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] w_hs_word;
  logic                                            w_ddrn_clk;
  logic                                            w_load;
  logic                                            w_load_fall;
  logic [C_ACT_TOGGLES-1:0]                        w_act_toggle;
  logic [PARA_NUM_LANES-1:0]                       w_dp_sync;
  logic [PARA_NUM_LANES-1:0]                       w_dn_sync;
  logic [PARA_NUM_LANES-1:0][1:0]                  w_phy_lp_sync;
  lp_state_t [PARA_NUM_LANES-1:0]                  w_phy_lp_state;
  logic [PARA_NUM_LANES-1:0][C_SEL_W-1:0]          w_sel;
  logic [PARA_NUM_LANES-1:0][C_SEL_W-1:0]          w_mux_sel;
  logic [PARA_NUM_LANES-1:0][PARA_NUM_LANES-1:0]   w_sel_hit;
  logic [PARA_NUM_LANES-1:0]                       w_afe_hs_en;
  logic [PARA_NUM_LANES-1:0]                       w_afe_term_en;
  logic                                            w_cl_dp_sync;
  logic                                            w_cl_dn_sync;

  // ------------------------------------------------------------------ physical lanes
  for (genvar p = 0; p < PARA_NUM_LANES; p++) begin : g_phy
    // LP lines are oversampled in core_clk: every LP state lasts at least TLPX = 50 ns, i.e.
    // 10 samples (ADR-002).
    // CDC_CROSSING: afe -> core: i_afe_lp_dp (HAS §4.1, Table 4-2)
    // REQ-050, REQ-059, REQ-270, REQ-271, REQ-322
    m_ftel_dphy_rx_sync #(
      .PARA_LEVELS (PARA_LP_SYNC_STAGES)
    ) u_sync_0 (
      .i_clk      (i_core_clk),
      .i_rstn     (i_core_rst_n),
      .i_data_in  (i_afe_lp_dp[p]),
      .o_data_out (w_dp_sync[p])
    );

    // CDC_CROSSING: afe -> core: i_afe_lp_dn (HAS §4.1, Table 4-2)
    // REQ-050, REQ-059
    m_ftel_dphy_rx_sync #(
      .PARA_LEVELS (PARA_LP_SYNC_STAGES)
    ) u_sync_1 (
      .i_clk      (i_core_clk),
      .i_rstn     (i_core_rst_n),
      .i_data_in  (i_afe_lp_dn[p]),
      .o_data_out (w_dn_sync[p])
    );

    // Dp and Dn are swapped when the polarity bit of the physical lane is set.
    // REQ-070
    assign w_phy_lp_sync[p] = i_cfg_lane_pol[p] ? {w_dn_sync[p], w_dp_sync[p]} : {w_dp_sync[p], w_dn_sync[p]};

    // REQ-050, REQ-070, REQ-072
    m_ftel_dphy_rx_lp_filter #(
      .PARA_LP_FILTER_CYC (PARA_LP_FILTER_CYC)
    ) u_lp_filter_0 (
      .i_core_clk   (i_core_clk),
      .i_core_rst_n (i_core_rst_n),
      .i_lp         (lp_state_t'(w_phy_lp_sync[p])),
      .o_lp         (w_phy_lp_state[p])
    );

    // Samplers and 1:8 deserializer of the physical lane, on both edges of the DDR clock. The
    // words of all lanes are cut at the same load phase.
    // REQ-328, REQ-339, REQ-341
    m_ftel_dphy_rx_hs_deser #(
      .PARA_DESER_RATIO (PARA_DESER_RATIO)
    ) u_hs_deser_0 (
      .i_ddr_clk    (i_ddr_clk),
      .i_ddrn_clk   (w_ddrn_clk),
      .i_load       (w_load),
      .i_load_fall  (w_load_fall),
      .o_word       (w_deser_word[p]),
      .i_afe_hs_bit (i_afe_hs_bit[p])
    );

    // HS path: two rxbyteclkhs stages, data registers without reset (rtl_rule K4). The first takes
    // the word three DDR periods after the rising-edge half is loaded, while both halves are
    // stable; the second is the HS path register (rtl_notes D-18).
    // OPEN ADR-007 REQ-183, REQ-266: word latency Λ = 2 byte clocks, set by two rxbyteclkhs stages after the parallel registers
    // SYNC_DDR (HAS §4.3)
    // REQ-026, REQ-074, REQ-335
    always_ff @(posedge i_byte_clk) begin : p_hs_word
      reg_hs_pre[p]  <= w_deser_word[p];
      reg_hs_word[p] <= reg_hs_pre[p];
    end

    // All bits inverted when the polarity bit of the physical lane is set, after the HS path
    // register (Figure 4-2, rtl_notes D-24).
    // REQ-074
    assign w_hs_word[p] = reg_hs_word[p] ^ {PARA_DESER_RATIO{i_cfg_lane_pol[p]}};
  end

  // ------------------------------------------------------------------ lane mapping
  // One field per logical lane selects its physical lane, for the LP path and the HS path
  // alike. With one lane the paths read physical lane 0; the field still takes part in the
  // AFE-enable rule, so a value other than 0 leaves the lane disabled (rtl_notes D-6).
  for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_log
    // REQ-075
    assign w_sel[x] = i_cfg_lane_map[x];

    if (PARA_NUM_LANES > 1) begin : g_map
      // REQ-075
      assign w_mux_sel[x] = w_sel[x];
    end else begin : g_nomap
      // D-6
      assign w_mux_sel[x] = '0;
    end

    // REQ-069, REQ-070, REQ-074, REQ-075
    assign o_lp_state[x] = w_phy_lp_state[w_mux_sel[x]];
    assign o_lp_sync[x]  = w_phy_lp_sync[w_mux_sel[x]];
    assign o_hs_word[x]  = w_hs_word[w_mux_sel[x]];
  end

  // The AFE enables of a physical lane are the OR of the requests of the logical lanes that
  // select it, without a further register: the requests are FSM registers already. The AFE
  // switches the termination only on these requests, which follow the line-state sequence.
  // REQ-077, REQ-080, REQ-081, REQ-329, REQ-348
  for (genvar p = 0; p < PARA_NUM_LANES; p++) begin : g_afe_en
    for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_req
      // REQ-077
      assign w_sel_hit[p][x] = (w_sel[x] == C_SEL_W'(p));
    end
    // REQ-077, REQ-080, REQ-081
    assign w_afe_hs_en[p]   = |(i_hs_en & w_sel_hit[p]);
    assign w_afe_term_en[p] = |(i_term_en & w_sel_hit[p]);
  end

  // REQ-077, REQ-080, REQ-081
  assign o_afe_hs_en   = w_afe_hs_en;
  assign o_afe_term_en = w_afe_term_en;

  // Deskew taps stay at their reset value while PARA_DESKEW_EN = 0 (Block No. 5 absent).
  // OPEN ADR-004 REQ-264: taps tied to 0
  assign o_afe_dly_tap = '0;

  // ------------------------------------------------------------------ clock lane
  // OPEN S9 REQ-079: the clock lane is neither inverted nor remapped
  // CDC_CROSSING: afe -> core: i_afe_cl_lp_dp (HAS §4.1, Table 4-2)
  // REQ-050, REQ-059
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (PARA_LP_SYNC_STAGES)
  ) u_sync_0 (
    .i_clk      (i_core_clk),
    .i_rstn     (i_core_rst_n),
    .i_data_in  (i_afe_cl_lp_dp),
    .o_data_out (w_cl_dp_sync)
  );

  // CDC_CROSSING: afe -> core: i_afe_cl_lp_dn (HAS §4.1, Table 4-2)
  // REQ-050, REQ-059
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (PARA_LP_SYNC_STAGES)
  ) u_sync_1 (
    .i_clk      (i_core_clk),
    .i_rstn     (i_core_rst_n),
    .i_data_in  (i_afe_cl_lp_dn),
    .o_data_out (w_cl_dn_sync)
  );

  // REQ-050, REQ-070
  m_ftel_dphy_rx_lp_filter #(
    .PARA_LP_FILTER_CYC (PARA_LP_FILTER_CYC)
  ) u_lp_filter_0 (
    .i_core_clk   (i_core_clk),
    .i_core_rst_n (i_core_rst_n),
    .i_lp         (lp_state_t'({w_cl_dp_sync, w_cl_dn_sync})),
    .o_lp         (o_cl_lp_state)
  );

  // Clock-lane AFE enables: the FSM registers of Block No. 2, passed without a further register.
  // REQ-080, REQ-081
  assign o_afe_cl_hs_en   = i_cl_hs_en;
  assign o_afe_cl_term_en = i_cl_term_en;

  // ------------------------------------------------------------------ byte clock
  // Inverted DDR clock, divider by 4 with the load phases, clock gate of rxbyteclkhs and the
  // clock-activity toggles: the clock structure of rtl_rule K2.
  // REQ-026, REQ-048, REQ-228, REQ-343
  m_ftel_dphy_rx_byte_clk #(
    .PARA_DESER_RATIO (PARA_DESER_RATIO)
  ) u_byte_clk_0 (
    .i_ddr_clk    (i_ddr_clk),
    .i_ddr_rst_n  (i_ddr_rst_n),
    .i_byteclk_en (i_byteclk_en),
    .o_byte_clk   (o_rxbyteclkhs),
    .o_ddrn_clk   (w_ddrn_clk),
    .o_load       (w_load),
    .o_load_fall  (w_load_fall),
    .o_act_toggle (w_act_toggle)
  );

  // Clock activity for Block No. 2 (TCLK-MISS), in core_clk.
  // REQ-047, REQ-102, REQ-345
  m_ftel_dphy_rx_clk_act u_clk_act_0 (
    .i_core_clk   (i_core_clk),
    .i_core_rst_n (i_core_rst_n),
    .i_act_toggle (w_act_toggle),
    .o_clk_active (o_cl_clk_active)
  );
endmodule
`default_nettype wire
