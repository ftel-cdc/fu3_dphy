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
// Module          : m_ftel_dphy_rx_sync_search
// Description     : Sync search of one data lane (HAS Block No. 4): 2-word window, eight
//                   leader comparators with single-bit error tolerance, lock of the lowest
//                   offset, search counter, deskew-burst detection and barrel shifter. Each
//                   byte clock it produces one delay-line entry.
// Parent          : m_ftel_dphy_rx_hs_datapath
// HAS             : draft v0.12, §4.6, Figure 4-8, ADR-007
// Clock domains   : byte
// REQ-IDs         : REQ-033, REQ-150, REQ-151, REQ-152, REQ-153, REQ-154, REQ-155, REQ-156,
//                   REQ-157, REQ-158, REQ-160, REQ-161, REQ-162, REQ-163, REQ-165, REQ-166,
//                   REQ-167, REQ-168, REQ-181, REQ-184, REQ-185, REQ-247, REQ-248, REQ-251,
//                   REQ-273, REQ-277, REQ-324
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
module m_ftel_dphy_rx_sync_search
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
  parameter int PARA_SYNC_SEARCH_BYTES = 16
) (
  // ---- clock / reset ----
  input  logic                     i_byte_clk,
  input  logic                     i_byte_rst_n,
  // ---- control: synchronized sync-search start ----
  input  logic                     i_start,
  // ---- data in: AFE word of the lane, bit 0 received first ----
  input  logic [C_DESER_RATIO-1:0] i_word,
  // ---- data out: delay-line entry of this cycle and burst flags ----
  output hs_entry_t                o_entry,
  output logic                     o_cancel,
  output logic                     o_no_sync
);

  localparam int C_W       = C_DESER_RATIO;
  localparam int C_OFF_W   = $clog2(C_W);
  localparam int C_CNT_W   = $clog2(PARA_SYNC_SEARCH_BYTES + 1);
  localparam logic [C_W-1:0] C_ONES = '1;

  logic [C_W-1:0]      reg_w0;
  logic [C_W-1:0]      reg_w1;
  logic                reg_seen;
  logic [C_CNT_W-1:0]  reg_cnt;
  logic                reg_locked;
  logic [C_OFF_W-1:0]  reg_offset;
  logic                reg_sync_pend;
  logic                reg_soterr_pend;
  logic                reg_had_lock;
  logic                reg_limit;
  logic                reg_deskew;
  logic [C_OFF_W-1:0]  reg_first_one;
  logic                reg_ones;
  logic [2*C_W-1:0]    w_win;
  logic                w_first;
  logic                w_search_en;
  logic [C_W-1:0][C_W-1:0] w_diff;
  logic [C_W-1:0]      w_match;
  logic [C_W-1:0]      w_exact;
  logic [C_W-1:0]      w_cand;
  logic [C_W-1:0]      w_cand_first;
  logic                w_lock;
  logic [C_OFF_W-1:0]  w_lock_off;
  logic                w_lock_err;
  logic                w_limit_hit;
  logic [C_W-1:0]      w_one_first;
  logic [C_OFF_W-1:0]  w_first_one;
  logic                w_ones0;
  logic                w_detect;

  // ------------------------------------------------------------------ window
  // The window registers stay at zero while the start is Low, so the words received before it
  // (THS-PREPARE junk included) cannot match, start the search counter or start the deskew
  // detection (ADR-007, option D).
  // REQ-151, REQ-152, REQ-181, REQ-185, REQ-277
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_window
    if (!i_byte_rst_n) begin
      reg_w0 <= '0;
      reg_w1 <= '0;
    end else if (!i_start) begin
      reg_w0 <= '0;
      reg_w1 <= '0;
    end else begin
      reg_w0 <= i_word;
      reg_w1 <= reg_w0;
    end
  end

  // Two consecutive words, the older in the low half: bit index grows with arrival time.
  // REQ-153
  assign w_win = {reg_w0, reg_w1};

  // ------------------------------------------------------------------ comparators
  // The search starts at the first non-zero word after the start and lasts at most
  // PARA_SYNC_SEARCH_BYTES byte clocks; it stops after a lock, a deskew detection or the limit.
  // REQ-154, REQ-158
  assign w_first     = i_start && !reg_seen && (reg_w0 != '0);
  assign w_search_en = i_start && (reg_seen || w_first) && !reg_locked && !reg_limit && !reg_deskew &&
                       (!reg_seen || (reg_cnt < C_CNT_W'(PARA_SYNC_SEARCH_BYTES)));

  // Eight comparators, one per bit offset, each accepting at most one differing bit; a leader
  // with two or more errors may still match elsewhere, usually inside the payload.
  // REQ-153, REQ-160, REQ-161, REQ-184
  for (genvar k = 0; k < C_W; k++) begin : g_cmp
    // REQ-153, REQ-161
    assign w_diff[k]  = w_win[k +: C_W] ^ C_SYNC_LEADER;
    assign w_exact[k] = (w_diff[k] == '0);
    assign w_match[k] = (w_diff[k] & (w_diff[k] - C_W'(1))) == '0;
  end

  // The lowest matching offset is locked; a single-bit error raises errsoths_x with B1.
  // REQ-155, REQ-156, REQ-161
  assign w_cand       = w_match & {C_W{w_search_en}};
  assign w_cand_first = w_cand & (~w_cand + 1'b1);
  assign w_lock       = |w_cand;
  assign w_lock_err   = |(w_cand_first & ~w_exact);

  for (genvar b = 0; b < C_OFF_W; b++) begin : g_lock_enc
    logic [C_W-1:0] w_bit_sel;
    for (genvar k = 0; k < C_W; k++) begin : g_bit
      // D-15
      assign w_bit_sel[k] = w_cand_first[k] && (((k >> b) % 2) == 1);
    end
    // D-15
    assign w_lock_off[b] = |w_bit_sel;
  end

  // No lock within the limit: one errsotsynchs_x, no rxsynchs_x or rxvalidhs_x afterwards.
  // REQ-157, REQ-158, REQ-251
  assign w_limit_hit = i_start && reg_seen && (reg_cnt == C_CNT_W'(PARA_SYNC_SEARCH_BYTES)) &&
                       !reg_locked && !reg_limit && !reg_deskew;

  // ------------------------------------------------------------------ deskew detection
  // The first 1 after HS-0 is in the first non-zero word; the burst is a deskew burst when the
  // C_DESKEW_RUN bits from there, over three consecutive words, are all ones (rtl_notes D-13).
  // REQ-162, REQ-165, REQ-273
  assign w_one_first = reg_w0 & (~reg_w0 + 1'b1);

  for (genvar b = 0; b < C_OFF_W; b++) begin : g_one_enc
    logic [C_W-1:0] w_bit_sel;
    for (genvar k = 0; k < C_W; k++) begin : g_bit
      // D-15
      assign w_bit_sel[k] = w_one_first[k] && (((k >> b) % 2) == 1);
    end
    // D-15
    assign w_first_one[b] = |w_bit_sel;
  end

  // REQ-165
  assign w_ones0  = (reg_w0 == C_W'(C_ONES << w_first_one));
  assign w_detect = i_start && reg_seen && !reg_deskew && reg_ones &&
                    (((reg_cnt == C_CNT_W'(1)) && (reg_first_one == '0) && (reg_w0 == C_ONES)) ||
                     ((reg_cnt == C_CNT_W'(2)) && (reg_first_one != '0) &&
                      ((reg_w0 | C_W'(C_ONES << reg_first_one)) == C_ONES)));

  // ------------------------------------------------------------------ state
  // Everything is cleared while the start is Low; the flags hold until it falls, so the EoT
  // request still sees them (rtl_notes D-12).
  // REQ-154, REQ-155, REQ-156, REQ-157, REQ-158, REQ-163, REQ-165, REQ-166, REQ-167
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_state
    if (!i_byte_rst_n) begin
      reg_seen        <= 1'b0;
      reg_cnt         <= '0;
      reg_locked      <= 1'b0;
      reg_offset      <= '0;
      reg_sync_pend   <= 1'b0;
      reg_soterr_pend <= 1'b0;
      reg_had_lock    <= 1'b0;
      reg_limit       <= 1'b0;
      reg_deskew      <= 1'b0;
      reg_first_one   <= '0;
      reg_ones        <= 1'b0;
    end else if (!i_start) begin
      reg_seen        <= 1'b0;
      reg_cnt         <= '0;
      reg_locked      <= 1'b0;
      reg_offset      <= '0;
      reg_sync_pend   <= 1'b0;
      reg_soterr_pend <= 1'b0;
      reg_had_lock    <= 1'b0;
      reg_limit       <= 1'b0;
      reg_deskew      <= 1'b0;
      reg_first_one   <= '0;
      reg_ones        <= 1'b0;
    end else begin
      if (w_first) begin
        reg_seen      <= 1'b1;
        reg_cnt       <= C_CNT_W'(1);
        reg_first_one <= w_first_one;
        reg_ones      <= w_ones0;
      end else if (reg_seen) begin
        if (reg_cnt != C_CNT_W'(PARA_SYNC_SEARCH_BYTES)) reg_cnt <= reg_cnt + 1'b1;
        if (reg_cnt == C_CNT_W'(1)) reg_ones <= reg_ones && (reg_w0 == C_ONES);
      end
      // a deskew detection cancels the lock and keeps the comparators disabled
      if (w_detect) begin
        reg_deskew      <= 1'b1;
        reg_locked      <= 1'b0;
        reg_sync_pend   <= 1'b0;
        reg_soterr_pend <= 1'b0;
      end else if (w_lock) begin
        reg_locked      <= 1'b1;
        reg_offset      <= w_lock_off;
        reg_sync_pend   <= 1'b1;
        reg_soterr_pend <= w_lock_err;
        reg_had_lock    <= 1'b1;
      end else begin
        reg_sync_pend   <= 1'b0;
        reg_soterr_pend <= 1'b0;
      end
      if (w_limit_hit) reg_limit <= 1'b1;
    end
  end

  // ------------------------------------------------------------------ entry
  // Barrel shifter over the window at the locked offset, bit 0 received first. It aligns the AFE
  // words, cut at an arbitrary boundary, to the byte boundary found by the search: this completes
  // the deserialization. The entry after the lock is B1 with the sync flag; a deskew detection
  // clears the flags of this entry and asks the delay line to clear its three newest entries. The
  // active flag is the start itself, so an HS entry aborted before DL_HS_RX produces no active
  // entry.
  // REQ-155, REQ-156, REQ-162, REQ-163, REQ-166, REQ-167, REQ-168, REQ-247, REQ-248, REQ-324
  assign o_entry = '{data:       w_win[reg_offset +: C_W],
                     valid:      reg_locked && !w_detect,
                     sync:       reg_sync_pend && !w_detect,
                     soterr:     reg_soterr_pend && !w_detect,
                     sotsyncerr: w_limit_hit,
                     skewcal:    w_detect || reg_deskew,
                     active:     i_start};

  // REQ-033, REQ-150, REQ-166
  assign o_cancel  = w_detect;
  assign o_no_sync = !reg_had_lock && !reg_deskew && !reg_limit;
endmodule
`default_nettype wire
