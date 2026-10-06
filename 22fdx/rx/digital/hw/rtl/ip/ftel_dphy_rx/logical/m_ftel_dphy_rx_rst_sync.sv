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
// Module          : m_ftel_dphy_rx_rst_sync
// Description     : Reset synchronizer: asynchronous assertion, release on the second clock
//                   edge. Port-compatible with m_fpt_lib_reset_sync_rising_edge_async_reset_n
//                   (rtl_rule K10).
// Parent          : m_ftel_dphy_rx_timing_init
// HAS             : draft v0.12, §4.2, Figure 4-1
// Clock domains   : clock of the instance
// REQ-IDs         : REQ-066
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
module m_ftel_dphy_rx_rst_sync (
  input  logic i_clk,
  input  logic i_async_reset_n,
  output logic o_sync_reset_n
);

  localparam int C_STAGES = 2;

  logic [C_STAGES-1:0] reg_sync;

  // The asynchronous reset clears both flip-flops; the second one is the reset of the domain.
  // REQ-066
  always_ff @(posedge i_clk or negedge i_async_reset_n) begin : p_sync
    if (!i_async_reset_n) begin
      reg_sync <= '0;
    end else begin
      reg_sync <= {reg_sync[C_STAGES-2:0], 1'b1};
    end
  end

  // REQ-066
  assign o_sync_reset_n = reg_sync[C_STAGES-1];
endmodule
`default_nettype wire
