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
// Module          : m_ftel_dphy_rx_tsync
// Description     : Toggle synchronizer: a one-cycle event inverts a flip-flop in the source
//                   clock; the level crosses through two flip-flops and a third
//                   flip-flop with an XOR turns each change into a one-cycle pulse.
// Parent          : m_ftel_dphy_rx_hs_datapath
// HAS             : draft v0.14, §4.1, Figure 4-1
// Clock domains   : source and destination clocks of the instance
// REQ-IDs         : REQ-060, REQ-061
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
module m_ftel_dphy_rx_tsync (
  input  logic i_src_clk,
  input  logic i_src_rst_n,
  input  logic i_dst_clk,
  input  logic i_dst_rst_n,
  input  logic i_pulse,
  output logic o_pulse
);

  logic reg_src_tgl;
  logic reg_dst_tgl;
  logic w_tgl_sync;

  // Two events must be at least three destination cycles apart (REQ-061): the user guarantees
  // it, each event occurs at most once per burst or per LP sequence.
  // REQ-060, REQ-061
  always_ff @(posedge i_src_clk or negedge i_src_rst_n) begin : p_src_tgl
    if (!i_src_rst_n) begin
      reg_src_tgl <= 1'b0;
    end else if (i_pulse) begin
      reg_src_tgl <= ~reg_src_tgl;
    end
  end

  // CDC_CROSSING: src -> dst: reg_src_tgl, toggle level (HAS §4.1, Figure 4-1)
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (2)
  ) u_sync_0 (
    .i_clk      (i_dst_clk),
    .i_rstn     (i_dst_rst_n),
    .i_data_in  (reg_src_tgl),
    .o_data_out (w_tgl_sync)
  );

  // REQ-060
  always_ff @(posedge i_dst_clk or negedge i_dst_rst_n) begin : p_dst_tgl
    if (!i_dst_rst_n) begin
      reg_dst_tgl <= 1'b0;
    end else begin
      reg_dst_tgl <= w_tgl_sync;
    end
  end

  // REQ-060
  assign o_pulse = w_tgl_sync ^ reg_dst_tgl;
endmodule
`default_nettype wire
