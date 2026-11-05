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
// Module          : m_fpt_dphy_rx_cg
// Description     : Integrated clock gate: the enable is latched while the clock is Low, so
//                   the gated clock carries whole pulses only. Port-compatible with
//                   m_fpt_lib_cg; behavioural model (rtl_rule K10, rtl_notes D-23). With the
//                   define FPT_SIGNOFF (PD flow) it instantiates m_fpt_lib_cg (rtl_notes D-30).
// Parent          : m_fpt_dphy_rx_byte_clk
// HAS             : draft v0.14, §4.3
// Clock domains   : clock of the instance
// REQ-IDs         : REQ-343, REQ-344
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
module m_fpt_dphy_rx_cg (
  input  logic i_clk,
  input  logic i_en,
  input  logic i_scan_en,
  output logic o_clk
);

`ifdef FPT_SIGNOFF
  // Sign-off view, read by the PD flow with the define FPT_SIGNOFF: the clock-gating cell of the
  // SoC library, whose test enable is tied Low inside; i_scan_en, tied Low by the only instance,
  // is not used here (rtl_notes D-30).
  // REQ-343, REQ-344
  m_fpt_lib_cg u_lib_cg_0 (
    .i_clk (i_clk),
    .i_en  (i_en),
    .o_clk (o_clk)
  );
`else
  logic reg_en_lat;

  // The only latch of the IP (rtl_rule P6, P7). Behavioural model of the clock-gating cell, for
  // simulation and lint; the sign-off view above maps to the cell of the library.
  // REQ-343, REQ-344
  always_latch begin : p_en_lat
    if (!i_clk) begin
      reg_en_lat <= i_en | i_scan_en;
    end
  end

  // REQ-343, REQ-344
  assign o_clk = i_clk & reg_en_lat;
`endif
endmodule
`default_nettype wire
