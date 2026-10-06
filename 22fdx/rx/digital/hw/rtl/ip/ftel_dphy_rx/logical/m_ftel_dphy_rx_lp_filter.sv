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
// Module          : m_ftel_dphy_rx_lp_filter
// Description     : LP glitch filter of one lane (Block No. 1): a new line state is
//                   accepted once it has been sampled PARA_LP_FILTER_CYC + 1 times in a
//                   row; the output is a register.
// Parent          : m_ftel_dphy_rx_afe_adapter
// HAS             : draft v0.12, §4.3, Figure 4-3, Appendix B
// Clock domains   : core
// REQ-IDs         : REQ-071, REQ-072, REQ-313
// OPEN            : none
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
module m_ftel_dphy_rx_lp_filter
  import ftel_dphy_rx_pkg::*;
#(
  parameter int PARA_LP_FILTER_CYC = 2
) (
  // ---- clock / reset ----
  input  logic      i_core_clk,
  input  logic      i_core_rst_n,
  // ---- data in ----
  input  lp_state_t i_lp,
  // ---- data out ----
  output lp_state_t o_lp
);

  // Run length counts samples up to PARA_LP_FILTER_CYC + 1 and saturates there.
  localparam int C_RUN_MAX = PARA_LP_FILTER_CYC + 1;
  localparam int C_RUN_W   = $clog2(C_RUN_MAX + 1);

  lp_state_t            reg_cand;
  logic [C_RUN_W-1:0]   reg_run;
  lp_state_t            reg_lp;
  logic [C_RUN_W-1:0]   w_run_nxt;

  // Length of the run of identical samples, including the current one.
  // REQ-071
  always_comb begin : p_run_nxt
    w_run_nxt = C_RUN_W'(1);
    if (i_lp == reg_cand && reg_run != C_RUN_W'(C_RUN_MAX)) begin
      w_run_nxt = reg_run + C_RUN_W'(1);
    end else if (i_lp == reg_cand) begin
      w_run_nxt = reg_run;
    end
  end

  // The state changes when the last PARA_LP_FILTER_CYC + 1 samples agree, so the output
  // follows the LP-RX output after (PARA_LP_SYNC_STAGES + PARA_LP_FILTER_CYC) cycles plus the
  // sampling delay of the first synchronizer flip-flop. Reset value LP-11 (rtl_notes D-5).
  // REQ-071, REQ-072, REQ-313
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_filter
    if (!i_core_rst_n) begin
      reg_cand <= LP_11;
      reg_run  <= '0;
      reg_lp   <= LP_11;
    end else begin
      reg_cand <= i_lp;
      reg_run  <= w_run_nxt;
      if (w_run_nxt == C_RUN_W'(C_RUN_MAX)) begin
        reg_lp <= i_lp;
      end
    end
  end

  // REQ-071
  assign o_lp = reg_lp;
endmodule
`default_nettype wire
