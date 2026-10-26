//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-26
// Module          : m_ftel_ppi_act_gate
// Description     : FPGA prototype only. Per data lane, rxactivehs of ftel_dphy_rx towards AMD's
//                   CSI-2 RX Subsystem without PHY is held Low until rxsynchs, so that it rises with
//                   rxsynchs as AMD's D-PHY drives it. No delay; the other PPI signals do not pass here.
// Parent          : the RX design of the FPGA prototype (fpga/exp3/TN3_SPEC.md); tb_exp2b
// HAS             : none, not part of ftel_dphy_rx (fpga/PLAN_TN2B_GATE.md §2)
// Clock domains   : byte (rxbyteclkhs of ftel_dphy_rx)
// REQ-IDs         : none
// OPEN            : none
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-26   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
`timescale 1ns/1ps
`default_nettype none
// The inputs are "input var": with `default_nettype none, Vivado synthesis and XSIM without --relax reject an
// input port that has a data type and no net type ("input logic").
module m_ftel_ppi_act_gate #(
  parameter int PARA_NUM_LANES = 4
) (
  // ---- clock ----
  input  var logic                      i_byte_clk,
  // ---- reset ----
  input  var logic                      i_byte_rst_n,
  // ---- data in ----
  input  var logic [PARA_NUM_LANES-1:0] i_rxactivehs,
  input  var logic [PARA_NUM_LANES-1:0] i_rxsynchs,
  // ---- data out ----
  output logic     [PARA_NUM_LANES-1:0] o_rxactivehs
);

  (* ASYNC_REG = "TRUE" *) logic [1:0] reg_rst_sync;
  logic [PARA_NUM_LANES-1:0]           reg_seen;
  logic                                w_byte_rst_n;

  assign w_byte_rst_n = reg_rst_sync[1];

  // rxactivehs passes from the cycle of rxsynchs to the end of the burst. The flag clears in every cycle where
  // rxactivehs is Low, so a burst that follows a single Low cycle waits for its own rxsynchs. A burst without
  // rxsynchs (SoT sync error, deskew burst) stays Low here; errsotsynchs and the rest of the PPI go to the
  // subsystem directly, without delay.
  assign o_rxactivehs = i_rxactivehs & (i_rxsynchs | reg_seen);

  // The reset of ftel_dphy_rx, asserted at once and released at the second edge of the byte clock: the reset
  // synchronizer of an FPGA, its two flip-flops kept together by ASYNC_REG. While the byte clock is stopped the
  // release waits for it; ftel_dphy_rx drives no rxactivehs before its byte clock runs.
  // CDC_CROSSING: async -> byte: reset of the gate
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_rst_sync
    if (!i_byte_rst_n) begin
      reg_rst_sync <= '0;
    end else begin
      reg_rst_sync <= {reg_rst_sync[0], 1'b1};
    end
  end

  always_ff @(posedge i_byte_clk or negedge w_byte_rst_n) begin : p_seen
    if (!w_byte_rst_n) begin
      reg_seen <= '0;
    end else begin
      reg_seen <= o_rxactivehs;
    end
  end
endmodule
`default_nettype wire
