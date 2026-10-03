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
// Module          : m_ftel_dphy_rx_esc_decoder
// Description     : Escape decoder of a data lane (HAS Block No. 3): Spaced-One-Hot bits
//                   into an 8-bit register, first bit in the MSB, and comparison of the
//                   entry command with the codes of Table 4-6.
// Parent          : m_ftel_dphy_rx_dl_ctrl
// HAS             : draft v0.11, §4.5, Table 4-6, Figure 4-7
// Clock domains   : core
// REQ-IDs         : REQ-117, REQ-125, REQ-135, REQ-136, REQ-137, REQ-138, REQ-139, REQ-140,
//                   REQ-141, REQ-142, REQ-143, REQ-144, REQ-145, REQ-254
// OPEN            : T1
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
module m_ftel_dphy_rx_esc_decoder
  import ftel_dphy_rx_pkg::*;
(
  // ---- clock / reset ----
  input  logic                      i_core_clk,
  input  logic                      i_core_rst_n,
  // ---- control: the lane FSM is in DL_ESC_GO or DL_ESC_CMD ----
  input  logic                      i_active,
  // ---- data in ----
  input  lp_state_t                 i_lp_state,
  // ---- data out: entry command, valid in the cycle of its eighth bit ----
  output logic                      o_cmd_valid,
  output logic                      o_cmd_ulps,
  output logic [C_NUM_TRIGGERS-1:0] o_cmd_trigger,
  output logic                      o_cmd_unknown
);

  localparam int C_CNT_W = $clog2(C_ESC_BITS);

  lp_state_t             reg_lp_prev;
  logic [C_ESC_BITS-1:0] reg_shift;
  logic [C_CNT_W-1:0]    reg_bit_cnt;
  logic                  w_bit_strobe;
  logic                  w_bit;
  logic [C_ESC_BITS-1:0] w_code;
  logic                  w_cmd_valid;
  logic                  w_cmd_ulps;
  logic [C_NUM_TRIGGERS-1:0] w_cmd_trigger;

  // A Mark followed by a Space is one bit: on each change to LP-00 the previous line state gives
  // it, Mark-0 (LP-01) a 0 and Mark-1 (LP-10) a 1. The first bit ends in the MSB (rtl_notes D-7).
  // REQ-135, REQ-136
  assign w_bit_strobe = i_active && (i_lp_state == LP_00) && ((reg_lp_prev == LP_01) || (reg_lp_prev == LP_10));
  assign w_bit        = (reg_lp_prev == LP_10);
  assign w_code       = {reg_shift[C_ESC_BITS-2:0], w_bit};
  assign w_cmd_valid  = w_bit_strobe && (reg_bit_cnt == C_CNT_W'(C_ESC_BITS - 1));

  // The bit counter and the register are cleared outside DL_ESC_GO and DL_ESC_CMD.
  // REQ-135, REQ-136
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_shift
    if (!i_core_rst_n) begin
      reg_lp_prev <= LP_11;
      reg_shift   <= '0;
      reg_bit_cnt <= '0;
    end else begin
      reg_lp_prev <= i_lp_state;
      if (!i_active) begin
        reg_shift   <= '0;
        reg_bit_cnt <= '0;
      end else if (w_bit_strobe) begin
        reg_shift   <= w_code;
        reg_bit_cnt <= reg_bit_cnt + 1'b1;
      end
    end
  end

  // After the eighth bit the command is ULPS, one of the four triggers or unknown; LPDT,
  // Undefined-1 and Undefined-2 are unknown while PARA_LPDT_EN = 0.
  // REQ-117, REQ-137, REQ-138, REQ-139, REQ-140, REQ-141, REQ-254
  assign w_cmd_ulps = w_cmd_valid && (w_code == C_ESC_ULPS);

  // OPEN T1 REQ-125, REQ-142, REQ-143, REQ-144, REQ-145: rxtriggeresc_x[3:0] in the order of Table 4-6
  assign w_cmd_trigger[0] = w_cmd_valid && (w_code == C_ESC_TRIG_RESET);
  assign w_cmd_trigger[1] = w_cmd_valid && (w_code == C_ESC_TRIG_UNKNOWN_3);
  assign w_cmd_trigger[2] = w_cmd_valid && (w_code == C_ESC_TRIG_UNKNOWN_4);
  assign w_cmd_trigger[3] = w_cmd_valid && (w_code == C_ESC_TRIG_UNKNOWN_5);

  // REQ-117, REQ-137, REQ-254
  assign o_cmd_valid   = w_cmd_valid;
  assign o_cmd_ulps    = w_cmd_ulps;
  assign o_cmd_trigger = w_cmd_trigger;
  assign o_cmd_unknown = w_cmd_valid && !w_cmd_ulps && !(|w_cmd_trigger);
endmodule
`default_nettype wire
