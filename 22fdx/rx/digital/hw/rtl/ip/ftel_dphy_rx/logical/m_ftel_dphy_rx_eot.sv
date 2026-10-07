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
// Module          : m_ftel_dphy_rx_eot
// Description     : EoT delay line and trailer removal of one data lane (HAS Block No. 4):
//                   PARA_EOT_DELAY_BYTES entries of a byte and its flags; on the EoT request
//                   the stored tail is scanned backwards and cut at the last payload byte.
// Parent          : m_ftel_dphy_rx_hs_datapath
// HAS             : draft v0.14, §4.6, Figure 4-9, ADR-006, Appendix B
// Clock domains   : byte
// REQ-IDs         : REQ-016, REQ-017, REQ-024, REQ-159, REQ-164, REQ-166, REQ-169, REQ-170,
//                   REQ-171, REQ-172, REQ-173, REQ-174, REQ-175, REQ-176, REQ-177, REQ-178,
//                   REQ-179, REQ-180, REQ-187, REQ-188, REQ-249, REQ-252, REQ-274, REQ-318,
//                   REQ-320
// OPEN            : ADR-006, ADR-007, S12
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
module m_ftel_dphy_rx_eot
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
  parameter int PARA_EOT_DELAY_BYTES = 32
) (
  // ---- clock / reset ----
  input  logic                          i_byte_clk,
  input  logic                          i_byte_rst_n,
  // ---- control ----
  input  logic                          i_eot_req,
  input  logic                          i_cancel,
  input  logic                          i_no_sync,
  // ---- data in: entry of this cycle (sync search) ----
  input  hs_entry_t                     i_entry,
  // ---- data out: oldest entry, the PPI outputs of the lane ----
  output hs_entry_t                     o_entry,
  // ---- status ----
  output logic                          o_eot_done,
  output logic                          o_eot_sync_err,
  // ---- configuration ----
  // CDC_QUASI_STATIC: eot_skip_bytes (HAS §4.1)
  input  logic [C_EOT_SKIP_BYTES_W-1:0] i_cfg_eot_skip_bytes
);

  localparam int C_D       = PARA_EOT_DELAY_BYTES;
  localparam int C_W       = C_DESER_RATIO;
  localparam int C_IDX_W   = $clog2(C_D);
  // A deskew detection ends up to two words after the cancelled lock: the flags of B1 are in
  // the three newest entries at most.
  localparam int C_CANCEL_ENTRIES = 3;

  logic [C_D-1:0][C_W-1:0] reg_data;
  logic [C_D-1:0]          reg_valid;
  logic [C_D-1:0]          reg_sync;
  logic [C_D-1:0]          reg_soterr;
  logic [C_D-1:0]          reg_sotsyncerr;
  logic [C_D-1:0]          reg_skewcal;
  logic [C_D-1:0]          reg_active;
  logic [C_IDX_W-1:0]      w_skip;
  logic [C_D-1:0]          w_in_burst;
  logic                    w_tv;
  logic [C_D-1:0]          w_cand;
  logic [C_D-1:0]          w_first;
  logic                    w_found;
  logic [C_IDX_W-1:0]      w_e;
  logic                    w_last_full;
  logic [C_IDX_W:0]        w_last_idx;
  logic [C_D-1:0]          w_cut;
  logic [C_D-1:0]          w_sse;
  logic [C_D-1:0]          w_flag_clr;
  logic [C_D-1:0]          w_active_clr;

  // A programmed skip beyond the line is clamped to its oldest entry (rtl_notes D-12).
  // REQ-173, REQ-318
  assign w_skip = (int'(i_cfg_eot_skip_bytes) >= C_D) ? C_IDX_W'(C_D - 1) : C_IDX_W'(i_cfg_eot_skip_bytes);

  // ------------------------------------------------------------------ backward scan
  // Only the byte values relative to the trailer are examined, never their meaning. The entries
  // of the burst are the active entries contiguous from the newest one. The newest remaining bit
  // (bit 7 of the entry after the skipped ones) is the trailer value; the newest entry that is
  // not uniformly equal to it holds the last payload bit, its highest differing bit.
  // REQ-024, REQ-172, REQ-174
  assign w_in_burst[0] = reg_active[0];
  assign w_tv          = reg_data[w_skip][C_W-1];

  for (genvar i = 0; i < C_D; i++) begin : g_scan
    if (i > 0) begin : g_chain
      // REQ-172
      assign w_in_burst[i] = w_in_burst[i-1] && reg_active[i];
    end
    // REQ-173, REQ-174
    assign w_cand[i] = (C_IDX_W'(i) >= w_skip) && w_in_burst[i] && (reg_data[i] != {C_W{w_tv}});
  end

  // Newest candidate: the lowest set bit of w_cand, as a one-hot vector, then its index.
  // OPEN ADR-006 REQ-274: the tail is buffered and cut at the last transition before THS-SKIP; the cut is exact above ~270 Mb/s only
  // REQ-174, REQ-175
  assign w_first = w_cand & (~w_cand + 1'b1);
  assign w_found = |w_cand;

  for (genvar b = 0; b < C_IDX_W; b++) begin : g_enc
    logic [C_D-1:0] w_bit_sel;
    for (genvar i = 0; i < C_D; i++) begin : g_bit
      // D-15
      assign w_bit_sel[i] = w_first[i] && (((i >> b) % 2) == 1);
    end
    // D-15
    assign w_e[b] = |w_bit_sel;
  end

  // The last payload bit is bit 7: that entry is the last byte; otherwise it is dropped too. The
  // last active entry after the cut is that entry, or the one before it when it is dropped.
  // REQ-176, REQ-178
  assign w_last_full = (reg_data[w_e][C_W-1] != w_tv);
  assign w_last_idx  = {1'b0, w_e} + (w_last_full ? '0 : (C_IDX_W+1)'(1));

  for (genvar i = 0; i < C_D; i++) begin : g_cut
    // REQ-175, REQ-176, REQ-177
    assign w_cut[i] = w_in_burst[i] && (!w_found || (C_IDX_W'(i) < w_e) || ((C_IDX_W'(i) == w_e) && !w_last_full));
    // OPEN ADR-007 REQ-159: a burst ended before a lock gets errsotsynchs_x on its last active entry
    // REQ-178
    assign w_sse[i] = i_no_sync && w_found && w_in_burst[i] && ((C_IDX_W+1)'(i) == w_last_idx);
  end

  // Flags cleared at the shift: the cut on the EoT request, and the three newest entries when a
  // deskew detection cancels a lock (sync, SoT error and valid only).
  // REQ-166, REQ-177
  assign w_active_clr = i_eot_req ? w_cut : '0;

  for (genvar i = 0; i < C_D; i++) begin : g_clr
    if (i < C_CANCEL_ENTRIES) begin : g_cancel
      // REQ-166
      assign w_flag_clr[i] = w_active_clr[i] || i_cancel;
    end else begin : g_keep
      // REQ-177
      assign w_flag_clr[i] = w_active_clr[i];
    end
  end

  // ------------------------------------------------------------------ delay line
  // Bytes are data registers without reset (rtl_rule K4); their flags are reset. The line shifts
  // every byte clock, so the tail drains only while rxbyteclkhs runs.
  // OPEN S12 REQ-188, REQ-320: the tail of the last burst needs PARA_EOT_DELAY_BYTES + 4 byte clocks after LP-11 (Λ = 2)
  // REQ-016, REQ-017, REQ-169, REQ-187
  always_ff @(posedge i_byte_clk) begin : p_line_data
    reg_data[0] <= i_entry.data;
    for (int i = 1; i < C_D; i++) begin
      reg_data[i] <= reg_data[i-1];
    end
  end

  // The cut clears valid and active, not the skew-calibration flag, so rxskewcalhs_x falls after
  // rxactivehs_x by about eot_skip_bytes byte clocks.
  // REQ-164, REQ-169, REQ-171, REQ-177, REQ-178
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_line_flags
    if (!i_byte_rst_n) begin
      reg_valid      <= '0;
      reg_sync       <= '0;
      reg_soterr     <= '0;
      reg_sotsyncerr <= '0;
      reg_skewcal    <= '0;
      reg_active     <= '0;
    end else begin
      reg_valid[0]      <= i_entry.valid;
      reg_sync[0]       <= i_entry.sync;
      reg_soterr[0]     <= i_entry.soterr;
      reg_sotsyncerr[0] <= i_entry.sotsyncerr;
      reg_skewcal[0]    <= i_entry.skewcal;
      reg_active[0]     <= i_entry.active;
      for (int i = 1; i < C_D; i++) begin
        reg_valid[i]      <= reg_valid[i-1] && !w_flag_clr[i-1];
        reg_sync[i]       <= reg_sync[i-1] && !w_flag_clr[i-1];
        reg_soterr[i]     <= reg_soterr[i-1] && !w_flag_clr[i-1];
        reg_sotsyncerr[i] <= (reg_sotsyncerr[i-1] && !w_active_clr[i-1]) || (i_eot_req && w_sse[i-1]);
        reg_skewcal[i]    <= reg_skewcal[i-1];
        reg_active[i]     <= reg_active[i-1] && !w_active_clr[i-1];
      end
    end
  end

  // Every PPI output of the lane comes from the oldest entry.
  // REQ-170, REQ-249, REQ-252
  assign o_entry = '{data:       reg_data[C_D-1],
                     valid:      reg_valid[C_D-1],
                     sync:       reg_sync[C_D-1],
                     soterr:     reg_soterr[C_D-1],
                     sotsyncerr: reg_sotsyncerr[C_D-1],
                     skewcal:    reg_skewcal[C_D-1],
                     active:     reg_active[C_D-1]};

  // EoT done leaves once the cut is decided, before the line drains; a partial last byte or a
  // tail without a transition is an EoT sync error (status only).
  // REQ-175, REQ-176, REQ-179, REQ-180
  assign o_eot_done     = i_eot_req;
  assign o_eot_sync_err = i_eot_req && (!w_found || !w_last_full);
endmodule
`default_nettype wire
