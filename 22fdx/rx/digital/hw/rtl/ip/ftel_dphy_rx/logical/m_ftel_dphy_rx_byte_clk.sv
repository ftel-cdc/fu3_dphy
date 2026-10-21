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
// Module          : m_ftel_dphy_rx_byte_clk
// Description     : Clock structure of Block No. 1, the only place of the IP with logic on
//                   a clock path (rtl_rule K2): inverted DDR clock, divider by 4 with the
//                   load phases of the deserializer, clock gate of rxbyteclkhs and its enable,
//                   and the clock-activity toggles of the DDR clock.
// Parent          : m_ftel_dphy_rx_afe_adapter
// HAS             : draft v0.14, §4.1, §4.2, §4.3, Table 4-2, Figure 4-2
// Clock domains   : ddr, ddrn (load phase of the falling edge), core -> ddr (gate enable)
// REQ-IDs         : REQ-048, REQ-228, REQ-337, REQ-338, REQ-339, REQ-340, REQ-341, REQ-342,
//                   REQ-343, REQ-344, REQ-345, REQ-347, REQ-364, REQ-365
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
module m_ftel_dphy_rx_byte_clk
  import ftel_dphy_rx_pkg::*;
#(
  parameter int PARA_DESER_RATIO = 8
) (
  // ---- clock / reset ----
  input  logic                     i_ddr_clk,
  input  logic                     i_ddr_rst_n,
  // ---- control: byte-clock enable of Block No. 2, High in CL_HS_CLK ----
  input  logic                     i_byteclk_en,
  // ---- data out: clocks and load phases of the deserializers ----
  output logic                     o_byte_clk,
  output logic                     o_ddrn_clk,
  output logic                     o_load,
  output logic                     o_load_fall,
  // ---- status: clock-activity toggles (m_ftel_dphy_rx_clk_act) ----
  output logic [C_ACT_TOGGLES-1:0] o_act_toggle
);

  // Two bits per DDR clock period: a word lasts C_DIV_PERIODS periods.
  localparam int C_DIV_PERIODS = PARA_DESER_RATIO / 2;
  localparam int C_DIV_W       = $clog2(C_DIV_PERIODS);
  // Count reached at the rising edge of the divided clock (rtl_notes D-18).
  localparam logic [C_DIV_W-1:0] C_DIV_RISE = C_DIV_W'(C_DIV_PERIODS / 2);
  // Bit 0 of the toggle counter changes on every rising edge, its top bit on every
  // C_DIV_PERIODS-th one.
  localparam int C_TOGGLE_W    = C_DIV_W + 1;

  logic [C_DIV_W-1:0]    reg_div_cnt;
  logic                  reg_load;
  logic                  reg_load_fall;
  logic [C_TOGGLE_W-1:0] reg_toggle_cnt;
  logic [C_DIV_W-1:0]    w_div_cnt_nxt;
  logic                  w_ddrn_clk;
  logic                  w_div_clk;
  logic                  w_ddr_div_rst_n;

  // ------------------------------------------------------------------ gate enable
  // Set two DDR clock edges after the byte-clock enable rises, cleared at once when it falls. It
  // enables the clock gate and holds the divider and the load phase in reset while it is Low, so
  // rxbyteclkhs is Low while the gate is closed and starts with a whole pulse (rtl_notes D-19).
  // CDC_CROSSING: core -> ddr: byteclk_en (HAS §4.1, Table 4-2)
  // CLK_STRUCT (HAS §4.3)
  // REQ-337, REQ-343, REQ-364
  m_ftel_dphy_rx_rst_sync u_rst_sync_0 (
    .i_clk           (i_ddr_clk),
    .i_async_reset_n (i_byteclk_en),
    .o_sync_reset_n  (w_ddr_div_rst_n)
  );

  // ------------------------------------------------------------------ inverted DDR clock
  // The falling-edge flip-flops of the deserializer run on its rising edge (rtl_rule P12).
  // CLK_STRUCT (HAS §4.3)
  // REQ-339, REQ-342
  m_ftel_dphy_rx_clk_inv u_dont_touch_clk_inv_0 (
    .i_in  (i_ddr_clk),
    .o_out (w_ddrn_clk)
  );

  // ------------------------------------------------------------------ divider and load phase
  // REQ-343
  assign w_div_cnt_nxt = reg_div_cnt + 1'b1;

  // The load strobe is High in the DDR period after the rising edge of the divided clock: the
  // rising-edge parallel registers load one period after a byte-clock edge, three periods before
  // the next one, which takes their word (rtl_notes D-18).
  // REQ-340, REQ-341, REQ-343, REQ-364
  always_ff @(posedge i_ddr_clk or negedge w_ddr_div_rst_n) begin : p_div
    if (!w_ddr_div_rst_n) begin
      reg_div_cnt <= '0;
      reg_load    <= 1'b0;
    end else begin
      reg_div_cnt <= w_div_cnt_nxt;
      reg_load    <= (w_div_cnt_nxt == C_DIV_RISE);
    end
  end

  // The falling-edge parallel registers take the load phase half a DDR clock period later: the
  // only half-period path of the deserializer, placed with the samplers (HAS §4.3 design note,
  // rtl_notes D-17). Its reset is released on a rising edge, half a period before this edge.
  // SYNC_DDR (HAS §4.3)
  // REQ-342, REQ-364, REQ-365
  always_ff @(posedge w_ddrn_clk or negedge w_ddr_div_rst_n) begin : p_load_fall
    if (!w_ddr_div_rst_n) begin
      reg_load_fall <= 1'b0;
    end else begin
      reg_load_fall <= reg_load;
    end
  end

  // ------------------------------------------------------------------ byte clock
  // The top bit of the divider is the divided clock, line rate / 8.
  // CLK_STRUCT (HAS §4.3)
  // REQ-048, REQ-343
  assign w_div_clk = reg_div_cnt[C_DIV_W-1];

  // The gate passes the divided clock as rxbyteclkhs while its enable is set. Scan enable tied
  // Low (rtl_notes D-22).
  // CLK_STRUCT (HAS §4.3)
  // REQ-048, REQ-228, REQ-343, REQ-344
  m_ftel_dphy_rx_cg u_dont_touch_cg_0 (
    .i_clk     (w_div_clk),
    .i_en      (w_ddr_div_rst_n),
    .i_scan_en (1'b0),
    .o_clk     (o_byte_clk)
  );

  // ------------------------------------------------------------------ clock activity
  // Free-running counter of the DDR clock, independent of the gate and the divider: the
  // detection must see the clock before CL_HS_CLK (rtl_notes D-20).
  // REQ-338, REQ-345, REQ-347
  always_ff @(posedge i_ddr_clk or negedge i_ddr_rst_n) begin : p_toggle
    if (!i_ddr_rst_n) begin
      reg_toggle_cnt <= '0;
    end else begin
      reg_toggle_cnt <= reg_toggle_cnt + 1'b1;
    end
  end

  // Toggles of line rate / 4 and line rate / 16.
  // REQ-345, REQ-347
  assign o_act_toggle = {reg_toggle_cnt[C_TOGGLE_W-1], reg_toggle_cnt[0]};

  // REQ-339, REQ-340, REQ-342
  assign o_ddrn_clk  = w_ddrn_clk;
  assign o_load      = reg_load;
  assign o_load_fall = reg_load_fall;
endmodule
`default_nettype wire
