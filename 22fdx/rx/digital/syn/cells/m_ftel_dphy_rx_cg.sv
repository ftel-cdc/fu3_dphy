//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-10
// Module          : m_ftel_dphy_rx_cg
// Description     : Library mapping of the integrated clock gate for synthesis (rtl_rule K10):
//                   syn/run_syn.sh uses it in place of logical/m_ftel_dphy_rx_cg.sv. Same
//                   ports; one clock-gating cell of the library (latch_posedge_precontrol: the
//                   enable is latched while the clock is Low, scan enable on the test-enable
//                   pin). Cell and pin names: FTEL_LIB_CG_* of .env, defines from syn/tech.tcl.
// Parent          : m_ftel_dphy_rx_byte_clk
// HAS             : draft v0.14, §4.3
// Clock domains   : clock of the instance
// REQ-IDs         : REQ-343, REQ-344
// OPEN            : none
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-10   0.1        Ho Khanh Linh Synthesis mapping onto the clock-gating cell of the library.
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

  // REQ-343, REQ-344
  `FTEL_LIB_CG_CELL u_icg (
    .`FTEL_LIB_CG_PIN_CLK  (i_clk),
    .`FTEL_LIB_CG_PIN_EN   (i_en),
    .`FTEL_LIB_CG_PIN_TE   (i_scan_en),
    .`FTEL_LIB_CG_PIN_GCLK (o_clk)
  );
endmodule
`default_nettype wire
