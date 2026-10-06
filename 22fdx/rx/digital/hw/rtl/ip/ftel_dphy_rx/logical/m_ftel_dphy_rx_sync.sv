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
// Module          : m_ftel_dphy_rx_sync
// Description     : Level synchronizer: a chain of PARA_LEVELS flip-flops in the destination
//                   clock. Port-compatible with m_vlsi_synch, so that integration swaps
//                   the module name only (rtl_rule K10).
// Parent          : m_ftel_dphy_rx_afe_adapter, m_ftel_dphy_rx_timing_init, m_ftel_dphy_rx_tsync,
//                   m_ftel_dphy_rx_hs_datapath
// HAS             : draft v0.12, §4.1, Figure 4-1
// Clock domains   : destination clock of the instance
// REQ-IDs         : REQ-059
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
module m_ftel_dphy_rx_sync #(
  parameter int PARA_LEVELS = 2
) (
  input  logic i_clk,
  input  logic i_rstn,
  input  logic i_data_in,
  output logic o_data_out
);

  logic [PARA_LEVELS-1:0] reg_sync;

  // REQ-059
  always_ff @(posedge i_clk or negedge i_rstn) begin : p_sync
    if (!i_rstn) begin
      reg_sync <= '0;
    end else begin
      reg_sync <= {reg_sync[PARA_LEVELS-2:0], i_data_in};
    end
  end

  // REQ-059
  assign o_data_out = reg_sync[PARA_LEVELS-1];

`ifndef SYNTHESIS
  initial begin : p_check
    if (PARA_LEVELS < 2) $fatal(1, "m_ftel_dphy_rx_sync: PARA_LEVELS must be >= 2");
  end
`endif
endmodule
`default_nettype wire
