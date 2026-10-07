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
// Module          : m_ftel_dphy_rx_cg
// Description     : Integrated clock gate: the enable is latched while the clock is Low, so
//                   the gated clock carries whole pulses only. Port-compatible with
//                   m_fpt_lib_cg; behavioural model (rtl_rule K10, rtl_notes D-23).
// Parent          : m_ftel_dphy_rx_byte_clk
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
module m_ftel_dphy_rx_cg (
  input  logic i_clk,
  input  logic i_en,
  input  logic i_scan_en,
  output logic o_clk
);

  logic reg_en_lat;

  // The only latch of the IP (rtl_rule P6, P7). At integration the module is replaced by
  // m_fpt_lib_cg, which maps to an integrated clock-gating cell of the target library.
  // REQ-343, REQ-344
  always_latch begin : p_en_lat
    if (!i_clk) begin
      reg_en_lat <= i_en | i_scan_en;
    end
  end

  // REQ-343, REQ-344
  assign o_clk = i_clk & reg_en_lat;
endmodule
`default_nettype wire
