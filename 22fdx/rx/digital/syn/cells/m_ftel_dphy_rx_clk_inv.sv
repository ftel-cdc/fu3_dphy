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
// Module          : m_ftel_dphy_rx_clk_inv
// Description     : Library mapping of the clock inverter for synthesis (rtl_rule K10):
//                   syn/run_syn.sh uses it in place of logical/m_ftel_dphy_rx_clk_inv.sv. Same
//                   ports; one clock inverter cell of the library. Cell and pin names:
//                   FTEL_LIB_CKINV_* of .env, defines from syn/tech.tcl.
// Parent          : m_ftel_dphy_rx_byte_clk
// HAS             : draft v0.14, §4.3
// Clock domains   : none (clock path)
// REQ-IDs         : REQ-339
// OPEN            : none
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-10   0.1        Ho Khanh Linh Synthesis mapping onto the clock inverter of the library.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
`timescale 1ns/1ps
`default_nettype none
module m_ftel_dphy_rx_clk_inv (
  input  logic i_in,
  output logic o_out
);

  // REQ-339
  `FTEL_LIB_CKINV_CELL u_ckinv (
    .`FTEL_LIB_CKINV_PIN_IN  (i_in),
    .`FTEL_LIB_CKINV_PIN_OUT (o_out)
  );
endmodule
`default_nettype wire
