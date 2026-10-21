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
// Module          : m_ftel_dphy_rx_cl_ctrl
// Description     : Clock Lane Control, CIL-SCNN (HAS Block No. 2): clock-lane FSM of
//                   Table 4-4 with its settle counter; outputs are registers.
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.14, §4.1, §4.4, Table 4-2, Table 4-4, Figure 4-4, Appendix B
// Clock domains   : core
// REQ-IDs         : REQ-015, REQ-063, REQ-083, REQ-084, REQ-085, REQ-086, REQ-087, REQ-088,
//                   REQ-089, REQ-090, REQ-091, REQ-092, REQ-093, REQ-094, REQ-095, REQ-096,
//                   REQ-097, REQ-098, REQ-099, REQ-100, REQ-101, REQ-102, REQ-224, REQ-226,
//                   REQ-229, REQ-230, REQ-253, REQ-255, REQ-315, REQ-317, REQ-323, REQ-337
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
module m_ftel_dphy_rx_cl_ctrl
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
(
  // ---- clock / reset ----
  input  logic                          i_core_clk,
  input  logic                          i_core_rst_n,
  // ---- control (Block No. 6) ----
  input  logic                          i_en,
  input  logic                          i_init_done,
  // ---- data in (Block No. 1) ----
  input  lp_state_t                     i_lp_state,
  input  logic                          i_clk_active,
  // ---- data out: PPI (Block No. 7) ----
  // REQ-224, REQ-226, REQ-229, REQ-230
  output logic                          o_stopstate,
  output logic                          o_ulpsactivenot,
  output logic                          o_ulpsclknot,
  output logic                          o_rxclkactivehs,
  // ---- status (Block No. 8, rtl_notes D-2) ----
  output cl_state_t                     o_sts_state,
  output logic                          o_sts_abort_tgl,
  // ---- AFE requests and byte-clock enable (Block No. 1) ----
  output logic                          o_hs_en,
  output logic                          o_term_en,
  // REQ-090, REQ-102, REQ-337
  output logic                          o_byteclk_en,
  // ---- configuration ----
  // CDC_QUASI_STATIC: clk_settle_cyc (HAS §4.1)
  input  logic [C_CLK_SETTLE_CYC_W-1:0] i_cfg_clk_settle_cyc
);

  cl_state_t                     reg_state;
  logic [C_CLK_SETTLE_CYC_W-1:0] reg_settle_cnt;
  logic                          reg_stopstate;
  logic                          reg_ulpsactivenot;
  logic                          reg_ulpsclknot;
  logic                          reg_rxclkactivehs;
  logic                          reg_hs_en;
  logic                          reg_term_en;
  logic                          reg_byteclk_en;
  logic                          reg_abort_tgl;
  cl_state_t                     w_state_nxt;
  logic                          w_settle_done;
  logic                          w_abort;

  // CL_HS_TERM lasts at least clk_settle_cyc cycles (rtl_notes D-9).
  // REQ-100, REQ-315
  assign w_settle_done = ({1'b0, reg_settle_cnt} + 1'b1) >= {1'b0, i_cfg_clk_settle_cyc};

  // Table 4-4. A disabled lane is held in CL_INIT; every other state goes to CL_STOP on LP-11.
  // REQ-015, REQ-063, REQ-084, REQ-085, REQ-086, REQ-087, REQ-088, REQ-089, REQ-090, REQ-091,
  // REQ-092, REQ-093, REQ-094, REQ-095, REQ-096, REQ-099, REQ-101, REQ-102, REQ-323
  always_comb begin : p_state_nxt
    w_state_nxt = reg_state;
    if (!i_en) begin
      w_state_nxt = CL_INIT;
    end else if (reg_state != CL_INIT && i_lp_state == LP_11) begin
      w_state_nxt = CL_STOP;
    end else begin
      unique case (reg_state)
        CL_INIT: begin
          if (i_init_done) w_state_nxt = CL_STOP;
        end
        CL_STOP: begin
          if (i_lp_state == LP_01)      w_state_nxt = CL_HS_RQST;
          else if (i_lp_state == LP_10) w_state_nxt = CL_ULPS_RQST;
        end
        CL_HS_RQST: begin
          if (i_lp_state == LP_00)      w_state_nxt = CL_HS_PRPR;
          else if (i_lp_state == LP_10) w_state_nxt = CL_WAIT;
        end
        CL_HS_PRPR: begin
          // the termination enable was issued on entry (output register)
          w_state_nxt = CL_HS_TERM;
        end
        CL_HS_TERM: begin
          if (w_settle_done && i_clk_active) w_state_nxt = CL_HS_CLK;
        end
        CL_HS_CLK: begin
          if (!i_clk_active) w_state_nxt = CL_HS_END;
        end
        CL_ULPS_RQST: begin
          if (i_lp_state == LP_00)      w_state_nxt = CL_ULPS;
          else if (i_lp_state == LP_01) w_state_nxt = CL_WAIT;
        end
        CL_ULPS: begin
          if (i_lp_state == LP_10) w_state_nxt = CL_ULPS_EXIT;
        end
        CL_HS_END, CL_ULPS_EXIT, CL_WAIT: begin
          w_state_nxt = reg_state;
        end
        default: begin
          w_state_nxt = CL_INIT;
        end
      endcase
    end
  end

  // An aborted HS or ULPS request (entry into CL_WAIT) is a status event, not a PPI error.
  // REQ-087, REQ-092
  assign w_abort = (w_state_nxt == CL_WAIT) && (reg_state != CL_WAIT);

  // State and outputs are registered together, the outputs from the next state, so the PPI
  // outputs, the AFE requests and the byte-clock enable change with the state and cannot glitch
  // (rtl_notes D-8). The byte-clock enable has its own register, equal to cl_rxclkactivehs: it
  // clears the reset synchronizer of the clock gate (rtl_notes D-21).
  // REQ-083, REQ-086, REQ-088, REQ-089, REQ-090, REQ-093, REQ-094, REQ-097, REQ-098, REQ-253,
  // REQ-317, REQ-337
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_state_reg
    if (!i_core_rst_n) begin
      reg_state         <= CL_INIT;
      reg_stopstate     <= 1'b0;
      reg_ulpsactivenot <= 1'b1;
      reg_ulpsclknot    <= 1'b1;
      reg_rxclkactivehs <= 1'b0;
      reg_hs_en         <= 1'b0;
      reg_term_en       <= 1'b0;
      reg_byteclk_en    <= 1'b0;
      reg_abort_tgl     <= 1'b0;
    end else begin
      reg_state         <= w_state_nxt;
      reg_stopstate     <= (w_state_nxt == CL_STOP);
      reg_ulpsactivenot <= (w_state_nxt != CL_ULPS);
      reg_ulpsclknot    <= (w_state_nxt != CL_ULPS) && (w_state_nxt != CL_ULPS_EXIT);
      reg_rxclkactivehs <= (w_state_nxt == CL_HS_CLK);
      reg_hs_en         <= (w_state_nxt == CL_HS_TERM) || (w_state_nxt == CL_HS_CLK);
      reg_term_en       <= (w_state_nxt == CL_HS_PRPR) || (w_state_nxt == CL_HS_TERM) ||
                           (w_state_nxt == CL_HS_CLK)  || (w_state_nxt == CL_HS_END);
      reg_byteclk_en    <= (w_state_nxt == CL_HS_CLK);
      reg_abort_tgl     <= reg_abort_tgl ^ w_abort;
    end
  end

  // The settle counter counts core_clk cycles in CL_HS_TERM and restarts outside it.
  // REQ-100
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_settle_cnt
    if (!i_core_rst_n) begin
      reg_settle_cnt <= '0;
    end else if (reg_state != CL_HS_TERM) begin
      reg_settle_cnt <= '0;
    end else if (!w_settle_done) begin
      reg_settle_cnt <= reg_settle_cnt + 1'b1;
    end
  end

  // REQ-224, REQ-226, REQ-229, REQ-230, REQ-255
  assign o_stopstate     = reg_stopstate;
  assign o_ulpsactivenot = reg_ulpsactivenot;
  assign o_ulpsclknot    = reg_ulpsclknot;
  assign o_rxclkactivehs = reg_rxclkactivehs;
  assign o_hs_en         = reg_hs_en;
  assign o_term_en       = reg_term_en;
  assign o_byteclk_en    = reg_byteclk_en;
  assign o_sts_state     = reg_state;
  assign o_sts_abort_tgl = reg_abort_tgl;
endmodule
`default_nettype wire
