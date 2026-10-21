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
// Module          : m_ftel_dphy_rx_hs_datapath
// Description     : HS Receive Datapath of one data lane (HAS Block No. 4): crossing of the
//                   sync-search start into rxbyteclkhs and the hold of its fall, sync search,
//                   EoT delay line, EoT done back to core_clk, and the status events of the lane.
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.16, §4.1, §4.2, §4.6, Figures 4-8 and 4-9
// Clock domains   : byte (lane reset of Block No. 4), core (EoT done only)
// REQ-IDs         : REQ-020, REQ-024, REQ-052, REQ-053, REQ-058, REQ-061, REQ-064, REQ-067,
//                   REQ-150, REQ-172, REQ-179, REQ-181, REQ-231, REQ-232, REQ-233, REQ-234,
//                   REQ-235, REQ-242, REQ-243, REQ-367, REQ-368, REQ-379
// OPEN            : ADR-006
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
module m_ftel_dphy_rx_hs_datapath
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
  parameter int PARA_SYNC_SEARCH_BYTES = 16,
  parameter int PARA_EOT_DELAY_BYTES   = 32
) (
  // ---- clock / reset ----
  input  logic                          i_core_clk,
  input  logic                          i_core_rst_n,
  input  logic                          i_byte_clk,
  // reset of Block No. 4 of this lane, cleared while the lane is disabled (Block No. 6)
  input  logic                          i_byte_rst_n,
  // ---- control: sync-search start of Block No. 3 (core_clk) ----
  input  logic                          i_sync_search_start,
  // ---- data in: AFE word of the lane (Block No. 1) ----
  input  logic [C_DESER_RATIO-1:0]      i_hs_word,
  // ---- data out: PPI HS outputs of the lane, rxbyteclkhs (Block No. 7) ----
  // REQ-231, REQ-232, REQ-233, REQ-234, REQ-235, REQ-242, REQ-243
  output logic [C_DESER_RATIO-1:0]      o_rxdatahs,
  output logic                          o_rxvalidhs,
  output logic                          o_rxactivehs,
  output logic                          o_rxsynchs,
  output logic                          o_rxskewcalhs,
  output logic                          o_errsoths,
  output logic                          o_errsotsynchs,
  // ---- data out: EoT done to Block No. 3 (core_clk) ----
  output logic                          o_eot_done,
  // ---- status: source toggles of the events for Block No. 8 (rtl_notes D-2, D-14) ----
  output logic                          o_sts_errsoths_tgl,
  output logic                          o_sts_errsotsynchs_tgl,
  output logic                          o_sts_erreotsync_tgl,
  // ---- configuration ----
  // CDC_QUASI_STATIC: eot_skip_bytes (HAS §4.1)
  input  logic [C_EOT_SKIP_BYTES_W-1:0] i_cfg_eot_skip_bytes
);

  // Byte clocks for which the synchronized fall of the sync-search start is held (HAS §4.6).
  localparam int C_EOT_HOLD_BYTES = 3;

  logic                        reg_start_d;
  logic                        reg_sync_d;
  logic [C_EOT_HOLD_BYTES-1:0] reg_hold;
  logic                        reg_errsoths_tgl;
  logic                        reg_errsotsynchs_tgl;
  logic                        reg_erreotsync_tgl;
  logic                        w_start_sync;
  logic                        w_rise;
  logic                        w_hold;
  logic                        w_sync_fall;
  logic                        w_start;
  logic                        w_eot_req;
  hs_entry_t                   w_entry;
  hs_entry_t                   w_out;
  logic                        w_cancel;
  logic                        w_no_sync;
  logic                        w_eot_sync_err;

  // The sync-search start is the only signal from core_clk: its rise starts the search and its
  // fall, held below, is the EoT request, so start, active flag and request cannot arrive out of
  // order.
  // CDC_CROSSING: core -> byte: i_sync_search_start (HAS §4.1, Table 4-2)
  // REQ-052, REQ-181
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (2)
  ) u_sync_0 (
    .i_clk      (i_byte_clk),
    .i_rstn     (i_byte_rst_n),
    .i_data_in  (i_sync_search_start),
    .o_data_out (w_start_sync)
  );

  // Hold of the fall: the synchronized level reaches this block 2-3 byte clocks after the LP-11
  // detection, before the bytes of the same moment, which arrive 4-5 byte clocks after their last
  // bit at the line. The sync search, the active flag and the EoT request follow the held level, so
  // those bytes are stored before the cut.
  // OPEN ADR-006 REQ-379: the fall is held three byte clocks (C_EOT_HOLD_BYTES)
  // REQ-052, REQ-367
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_hold
    if (!i_byte_rst_n) begin
      reg_sync_d <= 1'b0;
      reg_hold   <= '0;
    end else begin
      reg_sync_d <= w_start_sync;
      reg_hold   <= {reg_hold[C_EOT_HOLD_BYTES-2:0], w_start_sync};
    end
  end

  // A rise during the hold (only below 260 Mb/s at the minimum THS-EXIT) ends the hold with one Low
  // cycle, which is the EoT request of the previous burst, so two bursts never merge; the new burst
  // starts one byte clock later.
  // REQ-367, REQ-368
  assign w_rise  = w_start_sync && !reg_sync_d;
  assign w_hold  = |reg_hold;
  assign w_start = (w_start_sync || w_hold) && !(w_rise && w_hold);

  // EoT done leaves at the synchronized fall, before the hold ends, so the hold does not delay the
  // return of the lane to Stop (ADR-006).
  // REQ-179
  assign w_sync_fall = reg_sync_d && !w_start_sync;

  // REQ-052, REQ-058, REQ-064, REQ-067, REQ-172
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_start_d
    if (!i_byte_rst_n) begin
      reg_start_d <= 1'b0;
    end else begin
      reg_start_d <= w_start;
    end
  end

  // REQ-052, REQ-172
  assign w_eot_req = reg_start_d && !w_start;

  // REQ-024, REQ-150
  m_ftel_dphy_rx_sync_search #(
    .PARA_SYNC_SEARCH_BYTES (PARA_SYNC_SEARCH_BYTES)
  ) u_sync_search_0 (
    .i_byte_clk   (i_byte_clk),
    .i_byte_rst_n (i_byte_rst_n),
    .i_start      (w_start),
    .i_word       (i_hs_word),
    .o_entry      (w_entry),
    .o_cancel     (w_cancel),
    .o_no_sync    (w_no_sync)
  );

  // REQ-024, REQ-150, REQ-172
  m_ftel_dphy_rx_eot #(
    .PARA_EOT_DELAY_BYTES (PARA_EOT_DELAY_BYTES)
  ) u_eot_0 (
    .i_byte_clk           (i_byte_clk),
    .i_byte_rst_n         (i_byte_rst_n),
    .i_eot_req            (w_eot_req),
    .i_cancel             (w_cancel),
    .i_no_sync            (w_no_sync),
    .i_entry              (w_entry),
    .o_entry              (w_out),
    .o_eot_sync_err       (w_eot_sync_err),
    .i_cfg_eot_skip_bytes (i_cfg_eot_skip_bytes)
  );

  // One EoT done per burst, so two events are far more than three core_clk cycles apart.
  // CDC_CROSSING: byte -> core: EoT done (HAS §4.1, Table 4-2)
  // REQ-053, REQ-061, REQ-179
  m_ftel_dphy_rx_tsync u_tsync_0 (
    .i_src_clk   (i_byte_clk),
    .i_src_rst_n (i_byte_rst_n),
    .i_dst_clk   (i_core_clk),
    .i_dst_rst_n (i_core_rst_n),
    .i_pulse     (w_sync_fall),
    .o_pulse     (o_eot_done)
  );

  // Status events counted when they reach the PPI; the EoT sync error when the cut is decided.
  // REQ-020
  always_ff @(posedge i_byte_clk or negedge i_byte_rst_n) begin : p_sts_tgl
    if (!i_byte_rst_n) begin
      reg_errsoths_tgl     <= 1'b0;
      reg_errsotsynchs_tgl <= 1'b0;
      reg_erreotsync_tgl   <= 1'b0;
    end else begin
      reg_errsoths_tgl     <= reg_errsoths_tgl ^ w_out.soterr;
      reg_errsotsynchs_tgl <= reg_errsotsynchs_tgl ^ w_out.sotsyncerr;
      reg_erreotsync_tgl   <= reg_erreotsync_tgl ^ w_eot_sync_err;
    end
  end

  // REQ-020, REQ-231, REQ-232, REQ-233, REQ-234, REQ-235, REQ-242, REQ-243
  assign o_rxdatahs             = w_out.data;
  assign o_rxvalidhs            = w_out.valid;
  assign o_rxactivehs           = w_out.active;
  assign o_rxsynchs             = w_out.sync;
  assign o_rxskewcalhs          = w_out.skewcal;
  assign o_errsoths             = w_out.soterr;
  assign o_errsotsynchs         = w_out.sotsyncerr;
  assign o_sts_errsoths_tgl     = reg_errsoths_tgl;
  assign o_sts_errsotsynchs_tgl = reg_errsotsynchs_tgl;
  assign o_sts_erreotsync_tgl   = reg_erreotsync_tgl;
endmodule
`default_nettype wire
