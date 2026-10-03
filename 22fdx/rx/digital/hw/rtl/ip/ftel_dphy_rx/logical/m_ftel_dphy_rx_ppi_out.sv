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
// Module          : m_ftel_dphy_rx_ppi_out
// Description     : PPI Output Stage (HAS Block No. 7): maps the internal signals to the PPI
//                   names, forces the inactive value of every output of a disabled lane,
//                   generates rxclkesc_x and ties the LPDT outputs. Combinational only.
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.11, §4.9, Figure 4-12, §5.1, Table 5-1
// Clock domains   : none (gates core and byte outputs with the core-synchronized enables)
// REQ-IDs         : REQ-028, REQ-058, REQ-063, REQ-203, REQ-204, REQ-205, REQ-206, REQ-207,
//                   REQ-208, REQ-209, REQ-217, REQ-236, REQ-237, REQ-240, REQ-241, REQ-245
// OPEN            : K2
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
module m_ftel_dphy_rx_ppi_out
  import ftel_dphy_rx_pkg::*;
#(
  parameter int PARA_NUM_LANES   = 4,
  parameter int PARA_DESER_RATIO = 8
) (
  // ---- control: synchronized enables (Block No. 6) ----
  input  logic                                            i_cl_en,
  input  logic [PARA_NUM_LANES-1:0]                       i_dl_en,
  // ---- data in: clock lane (Block No. 2) ----
  input  logic                                            i_cl_stopstate,
  input  logic                                            i_cl_ulpsactivenot,
  input  logic                                            i_cl_ulpsclknot,
  input  logic                                            i_cl_rxclkactivehs,
  // ---- data in: data lanes, core_clk (Block No. 3) ----
  input  logic [PARA_NUM_LANES-1:0]                       i_stopstate,
  input  logic [PARA_NUM_LANES-1:0]                       i_ulpsactivenot,
  input  logic [PARA_NUM_LANES-1:0]                       i_rxulpsesc,
  input  logic [PARA_NUM_LANES-1:0][C_NUM_TRIGGERS-1:0]   i_rxtriggeresc,
  input  logic [PARA_NUM_LANES-1:0]                       i_erresc,
  input  logic [PARA_NUM_LANES-1:0]                       i_errcontrol,
  // ---- data in: data lanes, rxbyteclkhs (Block No. 4) ----
  input  logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] i_rxdatahs,
  input  logic [PARA_NUM_LANES-1:0]                       i_rxvalidhs,
  input  logic [PARA_NUM_LANES-1:0]                       i_rxactivehs,
  input  logic [PARA_NUM_LANES-1:0]                       i_rxsynchs,
  input  logic [PARA_NUM_LANES-1:0]                       i_rxskewcalhs,
  input  logic [PARA_NUM_LANES-1:0]                       i_errsoths,
  input  logic [PARA_NUM_LANES-1:0]                       i_errsotsynchs,
  // ---- data in: synchronized LP lines (Block No. 1), byte clock, init_done ----
  input  logic [PARA_NUM_LANES-1:0][1:0]                  i_lp_sync,
  input  logic                                            i_rxbyteclkhs,
  input  logic                                            i_init_done,
  // ---- data out: PPI (Table 5-1) ----
  output logic                                            o_init_done,
  output logic                                            o_cl_stopstate,
  output logic [PARA_NUM_LANES-1:0]                       o_stopstate,
  output logic                                            o_cl_ulpsactivenot,
  output logic [PARA_NUM_LANES-1:0]                       o_ulpsactivenot,
  output logic                                            o_rxbyteclkhs,
  output logic                                            o_cl_rxclkactivehs,
  output logic                                            o_cl_ulpsclknot,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] o_rxdatahs,
  output logic [PARA_NUM_LANES-1:0]                       o_rxvalidhs,
  output logic [PARA_NUM_LANES-1:0]                       o_rxactivehs,
  output logic [PARA_NUM_LANES-1:0]                       o_rxsynchs,
  output logic [PARA_NUM_LANES-1:0]                       o_rxskewcalhs,
  output logic [PARA_NUM_LANES-1:0]                       o_rxclkesc,
  output logic [PARA_NUM_LANES-1:0]                       o_rxlpdtesc,
  output logic [PARA_NUM_LANES-1:0]                       o_rxulpsesc,
  output logic [PARA_NUM_LANES-1:0][C_NUM_TRIGGERS-1:0]   o_rxtriggeresc,
  output logic [PARA_NUM_LANES-1:0][PARA_DESER_RATIO-1:0] o_rxdataesc,
  output logic [PARA_NUM_LANES-1:0]                       o_rxvalidesc,
  output logic [PARA_NUM_LANES-1:0]                       o_errsoths,
  output logic [PARA_NUM_LANES-1:0]                       o_errsotsynchs,
  output logic [PARA_NUM_LANES-1:0]                       o_erresc,
  output logic [PARA_NUM_LANES-1:0]                       o_errsyncesc,
  output logic [PARA_NUM_LANES-1:0]                       o_errcontrol
);

  // Clock lane: inactive value 0 ANDed with the enable, inactive value 1 ORed with its inverse.
  // REQ-063, REQ-204, REQ-208
  assign o_cl_stopstate     = i_cl_stopstate && i_cl_en;
  assign o_cl_rxclkactivehs = i_cl_rxclkactivehs && i_cl_en;
  assign o_cl_ulpsactivenot = i_cl_ulpsactivenot || !i_cl_en;
  assign o_cl_ulpsclknot    = i_cl_ulpsclknot || !i_cl_en;

  // rxbyteclkhs and init_done pass through, without logic on the clock path (rtl_rule K2).
  // REQ-028, REQ-203, REQ-209, REQ-217
  assign o_rxbyteclkhs = i_rxbyteclkhs;
  assign o_init_done   = i_init_done;

  for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_lane
    // LP outputs of the data lane (core_clk registers of Block No. 3).
    // REQ-063, REQ-204, REQ-208
    assign o_stopstate[x]     = i_stopstate[x] && i_dl_en[x];
    assign o_ulpsactivenot[x] = i_ulpsactivenot[x] || !i_dl_en[x];
    assign o_rxulpsesc[x]     = i_rxulpsesc[x] && i_dl_en[x];
    assign o_rxtriggeresc[x]  = i_rxtriggeresc[x] & {C_NUM_TRIGGERS{i_dl_en[x]}};
    assign o_erresc[x]        = i_erresc[x] && i_dl_en[x];
    assign o_errcontrol[x]    = i_errcontrol[x] && i_dl_en[x];

    // HS outputs of the rxbyteclkhs domain, gated combinationally with the enable synchronized
    // in core_clk, so their inactive values hold while the byte clock is stopped; a burst cut by
    // a disable is not delivered later because the disable also clears Block No. 4.
    // CDC_GATING (HAS §4.9)
    // REQ-028, REQ-058, REQ-205, REQ-206, REQ-208
    assign o_rxdatahs[x]     = i_rxdatahs[x] & {PARA_DESER_RATIO{i_dl_en[x]}};
    assign o_rxvalidhs[x]    = i_rxvalidhs[x] && i_dl_en[x];
    assign o_rxactivehs[x]   = i_rxactivehs[x] && i_dl_en[x];
    assign o_rxsynchs[x]     = i_rxsynchs[x] && i_dl_en[x];
    assign o_rxskewcalhs[x]  = i_rxskewcalhs[x] && i_dl_en[x];
    assign o_errsoths[x]     = i_errsoths[x] && i_dl_en[x];
    assign o_errsotsynchs[x] = i_errsotsynchs[x] && i_dl_en[x];

    // XOR of the synchronized LP lines, for PPI completeness; nothing inside is clocked by it.
    // REQ-207, REQ-236
    assign o_rxclkesc[x] = (i_lp_sync[x][1] ^ i_lp_sync[x][0]) && i_dl_en[x];

    // OPEN K2 REQ-209, REQ-237, REQ-240, REQ-241, REQ-245: LPDT outputs tied to 0
    assign o_rxlpdtesc[x]  = 1'b0;
    assign o_rxdataesc[x]  = '0;
    assign o_rxvalidesc[x] = 1'b0;
    assign o_errsyncesc[x] = 1'b0;
  end
endmodule
`default_nettype wire
