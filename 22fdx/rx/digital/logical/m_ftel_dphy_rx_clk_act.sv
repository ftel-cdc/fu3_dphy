//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-07
// Module          : m_ftel_dphy_rx_clk_act
// Description     : Clock-activity detection of Block No. 1 for TCLK-MISS: the two toggles
//                   of the DDR clock cross into core_clk, and the clock is active while one of
//                   them changed within the last C_CLK_ACT_WIN_CYC core_clk cycles.
// Parent          : m_ftel_dphy_rx_afe_adapter
// HAS             : draft v0.14, §4.1, §4.3, §4.4, Table 4-2, Appendix B
// Clock domains   : core
// REQ-IDs         : REQ-103, REQ-319, REQ-336, REQ-345, REQ-346, REQ-347
// OPEN            : none
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-07   0.1        Ho Khanh Linh Draft against HAS v0.14; open items at their defaults.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
`timescale 1ns/1ps
`default_nettype none
module m_ftel_dphy_rx_clk_act
  import ftel_dphy_rx_pkg::*;
(
  // ---- clock / reset ----
  input  logic                     i_core_clk,
  input  logic                     i_core_rst_n,
  // ---- data in: toggles of the DDR clock (m_ftel_dphy_rx_byte_clk) ----
  input  logic [C_ACT_TOGGLES-1:0] i_act_toggle,
  // ---- data out (Block No. 2) ----
  output logic                     o_clk_active
);

  // HAS Table 4-2: level, 2-flop synchronizers.
  localparam int C_SYNC_STAGES = 2;
  localparam int C_WIN_W       = $clog2(C_CLK_ACT_WIN_CYC);

  logic [C_ACT_TOGGLES-1:0] reg_toggle_prev;
  logic [C_WIN_W-1:0]       reg_act_cnt;
  logic [C_ACT_TOGGLES-1:0] w_toggle_sync;
  logic                     w_change;

  for (genvar t = 0; t < C_ACT_TOGGLES; t++) begin : g_toggle
    // CDC_CROSSING: ddr -> core: clock-activity toggle (HAS §4.1, Table 4-2)
    // REQ-336
    m_ftel_dphy_rx_sync #(
      .PARA_LEVELS (C_SYNC_STAGES)
    ) u_sync_0 (
      .i_clk      (i_core_clk),
      .i_rstn     (i_core_rst_n),
      .i_data_in  (i_act_toggle[t]),
      .o_data_out (w_toggle_sync[t])
    );
  end

  // A change of either synchronized toggle (rtl_notes D-20).
  // REQ-345, REQ-347
  assign w_change = |(w_toggle_sync ^ reg_toggle_prev);

  // The window counter restarts on every change and counts down to 0 otherwise, so the clock
  // stays active for C_CLK_ACT_WIN_CYC cycles after the last change is seen.
  // REQ-345, REQ-346
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_act_cnt
    if (!i_core_rst_n) begin
      reg_toggle_prev <= '0;
      reg_act_cnt     <= '0;
    end else begin
      reg_toggle_prev <= w_toggle_sync;
      if (w_change) begin
        reg_act_cnt <= C_WIN_W'(C_CLK_ACT_WIN_CYC - 1);
      end else if (reg_act_cnt != '0) begin
        reg_act_cnt <= reg_act_cnt - 1'b1;
      end
    end
  end

  // Not registered: a register would add one cycle and let cl_rxclkactivehs fall after TCLK-MISS
  // when a synchronizer resolves late (rtl_notes D-20). The loss is seen 45-50 ns after the last
  // toggle change, 5 ns more when the first synchronizer flip-flop resolves late.
  // REQ-103, REQ-319, REQ-345, REQ-346
  assign o_clk_active = w_change | (reg_act_cnt != '0);
endmodule
`default_nettype wire
