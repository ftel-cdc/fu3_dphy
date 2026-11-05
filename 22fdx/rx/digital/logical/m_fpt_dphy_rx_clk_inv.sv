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
// Module          : m_fpt_dphy_rx_clk_inv
// Description     : Clock inverter: turns the falling edge of the DDR clock into the rising
//                   edge of the clock of the falling-edge flip-flops of Block No. 1. Port-
//                   compatible with m_fpt_lib_clk_inv; behavioural model (rtl_rule K10,
//                   rtl_notes D-23). With the define FPT_SIGNOFF (PD flow) it instantiates
//                   m_fpt_lib_clk_inv (rtl_notes D-30).
// Parent          : m_fpt_dphy_rx_byte_clk
// HAS             : draft v0.14, §4.3
// Clock domains   : none (clock path)
// REQ-IDs         : REQ-339
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
module m_fpt_dphy_rx_clk_inv (
  input  logic i_in,
  output logic o_out
);

`ifdef FPT_SIGNOFF
  // Sign-off view, read by the PD flow with the define FPT_SIGNOFF: the clock inverter of the SoC
  // library (rtl_notes D-30).
  // REQ-339
  m_fpt_lib_clk_inv u_lib_clk_inv_0 (
    .i_in  (i_in),
    .o_out (o_out)
  );
`else
  // Behavioural model of the clock inverter, for simulation and lint.
  // REQ-339
  assign o_out = ~i_in;
`endif
endmodule
`default_nettype wire
