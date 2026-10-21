//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-12
// Description     : Probe design: a MIPI_DPHY clock lane and data lane on IBUFDS_DPHY, the HS clock on
//                   a BUFG and the HS data sampled on both edges by fabric flip-flops.
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-12   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
// Probe design: a MIPI_DPHY clock lane and data lane on IBUFDS_DPHY, the HS clock on a BUFG and
// the HS data sampled on both edges by fabric flip-flops. Only used by synth_tiny.tcl to check that
// the VP1902 part synthesizes (license) and that the primitive is accepted; not a design.
module tiny_ibufds_dphy (
  input  wire clk_p,
  input  wire clk_n,
  input  wire d_p,
  input  wire d_n,
  input  wire hs_dis,
  output wire q_r,
  output wire q_f,
  output wire lp_p,
  output wire lp_n
);
  wire clk_hs, clk_lpp, clk_lpn, d_hs, d_lpp, d_lpn, clk_g;
  reg  r_r, r_f, r_lp_p, r_lp_n;

  IBUFDS_DPHY #(.DIFF_TERM("TRUE"), .IOSTANDARD("MIPI_DPHY"), .SIM_DEVICE("VERSAL_PREMIUM")) u_clk (
    .I(clk_p), .IB(clk_n), .HSRX_DISABLE(hs_dis), .LPRX_DISABLE(1'b0),
    .HSRX_O(clk_hs), .LPRX_O_P(clk_lpp), .LPRX_O_N(clk_lpn));
  IBUFDS_DPHY #(.DIFF_TERM("TRUE"), .IOSTANDARD("MIPI_DPHY"), .SIM_DEVICE("VERSAL_PREMIUM")) u_d0 (
    .I(d_p), .IB(d_n), .HSRX_DISABLE(hs_dis), .LPRX_DISABLE(1'b0),
    .HSRX_O(d_hs), .LPRX_O_P(d_lpp), .LPRX_O_N(d_lpn));
  BUFG u_bufg (.I(clk_hs), .O(clk_g));

  always @(posedge clk_g) r_r <= d_hs;
  always @(negedge clk_g) r_f <= d_hs;
  always @(posedge clk_g) begin
    r_lp_p <= d_lpp ^ clk_lpp;
    r_lp_n <= d_lpn ^ clk_lpn;
  end

  assign q_r  = r_r;
  assign q_f  = r_f;
  assign lp_p = r_lp_p;
  assign lp_n = r_lp_n;
endmodule
