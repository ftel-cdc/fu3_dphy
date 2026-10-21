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
// Module          : m_ftel_dphy_rx_hs_deser
// Description     : HS deserializer of one physical data lane (HAS Block No. 1): a sampler,
//                   a shift register and a parallel register on each edge of the DDR clock;
//                   the two parallel registers hold one word, bit 0 received first.
// Parent          : m_ftel_dphy_rx_afe_adapter
// HAS             : draft v0.14, §4.3, Table 4-2, Figure 4-2, Appendix B
// Clock domains   : ddr, ddrn
// REQ-IDs         : REQ-328, REQ-332, REQ-334, REQ-339, REQ-340, REQ-341, REQ-342, REQ-349,
//                   REQ-350, REQ-351, REQ-352, REQ-363
// OPEN            : ADR-001
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
module m_ftel_dphy_rx_hs_deser #(
  parameter int PARA_DESER_RATIO = 8
) (
  // ---- clock ----
  input  logic                        i_ddr_clk,
  input  logic                        i_ddrn_clk,
  // ---- control: load phases (m_ftel_dphy_rx_byte_clk) ----
  input  logic                        i_load,
  input  logic                        i_load_fall,
  // ---- data out: word of the lane, held for four DDR clock periods ----
  output logic [PARA_DESER_RATIO-1:0] o_word,
  // ---- AFE: unsampled HS-RX output of the physical lane ----
  input  logic                        i_afe_hs_bit
);

  // Two edges per DDR clock period; bits taken by each edge in one word.
  localparam int C_EDGES = 2;
  localparam int C_HALF  = PARA_DESER_RATIO / C_EDGES;

  logic              reg_sample_rise;
  logic              reg_sample_fall;
  logic [C_HALF-1:0] reg_shift_rise;
  logic [C_HALF-1:0] reg_shift_fall;
  logic [C_HALF-1:0] reg_half_rise;
  logic [C_HALF-1:0] reg_half_fall;

  // Data flip-flops without reset (rtl_rule K4): the samplers, shift registers and parallel
  // registers hold data only, and the words before a burst are ignored (HAS §4.2, §4.6). Each
  // shift register takes the newest bit at its top, so bit 0 of a parallel register is the oldest.
  // The samplers are plain flip-flops; the window is met by placing them by hand.
  // OPEN ADR-001 REQ-349, REQ-363: samplers are standard flip-flops, hand-placed with their clock buffers next to the AFE (HAS §4.3 design note)
  // REQ-328, REQ-332, REQ-334, REQ-339, REQ-340, REQ-350, REQ-351, REQ-352
  always_ff @(posedge i_ddr_clk) begin : p_rise
    reg_sample_rise <= i_afe_hs_bit;
    reg_shift_rise  <= {reg_sample_rise, reg_shift_rise[C_HALF-1:1]};
    if (i_load) begin
      reg_half_rise <= reg_shift_rise;
    end
  end

  // The load phase of the falling edge comes from the falling-edge flip-flop of
  // m_ftel_dphy_rx_byte_clk, a full period before this register uses it.
  // SYNC_DDR (HAS §4.3)
  // REQ-334, REQ-339, REQ-340, REQ-342
  always_ff @(posedge i_ddrn_clk) begin : p_fall
    reg_sample_fall <= i_afe_hs_bit;
    reg_shift_fall  <= {reg_sample_fall, reg_shift_fall[C_HALF-1:1]};
    if (i_load_fall) begin
      reg_half_fall <= reg_shift_fall;
    end
  end

  // The rising-edge half holds the bits received one half period before those of the falling-edge
  // half, so the word interleaves them with bit 0 from the rising edge (rtl_notes D-17).
  for (genvar k = 0; k < C_HALF; k++) begin : g_word
    // REQ-340, REQ-341
    assign o_word[C_EDGES*k]     = reg_half_rise[k];
    assign o_word[C_EDGES*k + 1] = reg_half_fall[k];
  end
endmodule
`default_nettype wire
