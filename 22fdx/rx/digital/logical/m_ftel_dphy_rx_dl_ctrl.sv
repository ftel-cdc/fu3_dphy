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
// Module          : m_ftel_dphy_rx_dl_ctrl
// Description     : Data Lane Control, CIL-SFEN (HAS Block No. 3): data-lane FSM of
//                   Table 4-5, settle counter, escape decoder, line-state change detector
//                   and output registers; drives the sync-search start of Block No. 4 and
//                   takes its HS busy for stopstate_x (PARA_STOP_DRAIN_EN).
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.17, §4.1, §4.5, Tables 4-2 and 4-5, Figures 4-5 and 4-6, Appendix B
// Clock domains   : core
// REQ-IDs         : REQ-018, REQ-021, REQ-025, REQ-063, REQ-083, REQ-104, REQ-105, REQ-106,
//                   REQ-107, REQ-108, REQ-109, REQ-110, REQ-111, REQ-112, REQ-113, REQ-114,
//                   REQ-115, REQ-116, REQ-117, REQ-118, REQ-119, REQ-120, REQ-121, REQ-122,
//                   REQ-123, REQ-124, REQ-126, REQ-127, REQ-128, REQ-129, REQ-130, REQ-131,
//                   REQ-132, REQ-133, REQ-134, REQ-135, REQ-147, REQ-148, REQ-180, REQ-182,
//                   REQ-198, REQ-225, REQ-227, REQ-238, REQ-239, REQ-244, REQ-246, REQ-250,
//                   REQ-253, REQ-254, REQ-265, REQ-314, REQ-316, REQ-323, REQ-382, REQ-383,
//                   REQ-384, REQ-385, REQ-386, REQ-390, REQ-391
// OPEN            : ADR-001, ADR-006, ADR-007, S12
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
module m_ftel_dphy_rx_dl_ctrl
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
  parameter int PARA_STOP_DRAIN_EN = 0
) (
  // ---- clock / reset ----
  input  logic                         i_core_clk,
  input  logic                         i_core_rst_n,
  // ---- control (Blocks No. 6 and 4) ----
  input  logic                         i_en,
  input  logic                         i_force_rise,
  input  logic                         i_init_done,
  input  logic                         i_hs_rx_timeout,
  input  logic                         i_esc_timeout,
  // HS busy of Block No. 4 (rxbyteclkhs level)
  input  logic                         i_hs_busy,
  // ---- data in (Block No. 1) ----
  input  lp_state_t                    i_lp_state,
  // ---- data out: PPI (Block No. 7) ----
  // REQ-225, REQ-227, REQ-238, REQ-239, REQ-244, REQ-246
  output logic                         o_stopstate,
  output logic                         o_ulpsactivenot,
  output logic                         o_rxulpsesc,
  output logic [C_NUM_TRIGGERS-1:0]    o_rxtriggeresc,
  output logic                         o_erresc,
  output logic                         o_errcontrol,
  // ---- data out: Block No. 4 ----
  output logic                         o_sync_search_start,
  // ---- status (Block No. 8, rtl_notes D-2) ----
  output dl_state_t                    o_sts_state,
  output logic                         o_sts_erresc_tgl,
  // ---- AFE requests (Block No. 1) ----
  output logic                         o_hs_en,
  output logic                         o_term_en,
  // ---- configuration ----
  // CDC_QUASI_STATIC: hs_settle_cyc (HAS §4.1)
  input  logic [C_HS_SETTLE_CYC_W-1:0] i_cfg_hs_settle_cyc
);

  dl_state_t                    reg_state;
  logic [C_HS_SETTLE_CYC_W-1:0] reg_settle_cnt;
  lp_state_t                    reg_lp_prev;
  logic                         reg_stopstate;
  logic                         reg_ulpsactivenot;
  logic                         reg_rxulpsesc;
  logic [C_NUM_TRIGGERS-1:0]    reg_rxtriggeresc;
  logic                         reg_erresc;
  logic                         reg_errcontrol;
  logic                         reg_sync_search_start;
  logic                         reg_hs_en;
  logic                         reg_term_en;
  logic                         reg_erresc_tgl;
  dl_state_t                    w_state_nxt;
  logic                         w_settle_done;
  logic                         w_lp_change;
  logic                         w_esc_active;
  logic                         w_mark;
  logic                         w_cmd_valid;
  logic                         w_cmd_ulps;
  logic [C_NUM_TRIGGERS-1:0]    w_cmd_trigger;
  logic                         w_cmd_unknown;
  logic                         w_err_entry;
  logic                         w_hs_busy;
  logic                         w_stop_hold;

  // ------------------------------------------------------------------ escape decoder
  // REQ-126
  assign w_esc_active = (reg_state == DL_ESC_GO) || (reg_state == DL_ESC_CMD);

  // REQ-117, REQ-126, REQ-135
  m_ftel_dphy_rx_esc_decoder u_esc_decoder_0 (
    .i_core_clk    (i_core_clk),
    .i_core_rst_n  (i_core_rst_n),
    .i_active      (w_esc_active),
    .i_lp_state    (i_lp_state),
    .o_cmd_valid   (w_cmd_valid),
    .o_cmd_ulps    (w_cmd_ulps),
    .o_cmd_trigger (w_cmd_trigger),
    .o_cmd_unknown (w_cmd_unknown)
  );

  // ------------------------------------------------------------------ helpers
  // DL_HS_TERM lasts hs_settle_cyc cycles; its end is the end of THS-SETTLE and places the entry
  // into DL_HS_RX, the start of the sync search (rtl_notes D-9).
  // REQ-130, REQ-182, REQ-314
  assign w_settle_done = ({1'b0, reg_settle_cnt} + 1'b1) >= {1'b0, i_cfg_hs_settle_cyc};

  // Line-state change detector; a Mark is LP-01 or LP-10.
  // REQ-126, REQ-133
  assign w_lp_change = (i_lp_state != reg_lp_prev);
  assign w_mark      = (i_lp_state == LP_01) || (i_lp_state == LP_10);

  // ------------------------------------------------------------------ HS busy of Block No. 4
  // A burst of the lane is still in Block No. 4 (held start or delay-line entries). With PARA_STOP_DRAIN_EN,
  // stopstate_x waits for its end, so it rises after the last HS output of the burst at the PPI.
  // CDC_CROSSING: byte -> core: i_hs_busy (HAS §4.1, Table 4-2)
  // REQ-382
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (2)
  ) u_sync_0 (
    .i_clk      (i_core_clk),
    .i_rstn     (i_core_rst_n),
    .i_data_in  (i_hs_busy),
    .o_data_out (w_hs_busy)
  );

  // Only the stopstate_x register uses HS busy; the lane FSM does not, so both values of the parameter
  // receive the same bursts. A stopped rxbyteclkhs keeps HS busy, and so stopstate_x, until the drain.
  // OPEN ADR-006 REQ-147, REQ-391: PARA_STOP_DRAIN_EN = 0, stopstate_x is the Stop state of the lane
  // OPEN S12 REQ-386: with PARA_STOP_DRAIN_EN = 1, stopstate_x waits for the byte clock to drain the lane
  // REQ-383, REQ-385
  assign w_stop_hold = (PARA_STOP_DRAIN_EN != 0) && w_hs_busy;

  // ------------------------------------------------------------------ FSM, Table 4-5
  // dl_enable_x Low holds the lane in DL_INIT and a rising forcerxmode_x returns it there. LP-11
  // returns any state to DL_STOP except DL_INIT and DL_HS_RX (-> DL_HS_EOT, then DL_STOP); the rows
  // that name LP-11 or "other" as a path to DL_ERR take precedence (rtl_notes D-8).
  // REQ-018, REQ-021, REQ-025, REQ-063, REQ-104, REQ-105, REQ-106, REQ-107, REQ-108, REQ-109,
  // REQ-110, REQ-112, REQ-113, REQ-114, REQ-115, REQ-116, REQ-117, REQ-118, REQ-119, REQ-120,
  // REQ-121, REQ-122, REQ-123, REQ-124, REQ-131, REQ-132, REQ-180, REQ-198, REQ-250, REQ-323
  always_comb begin : p_state_nxt
    w_state_nxt = reg_state;
    if (!i_en || i_force_rise) begin
      w_state_nxt = DL_INIT;
    end else begin
      unique case (reg_state)
        DL_INIT: begin
          if (i_init_done) w_state_nxt = DL_STOP;
        end
        DL_STOP: begin
          if (i_lp_state == LP_01)      w_state_nxt = DL_HS_RQST;
          else if (i_lp_state == LP_10) w_state_nxt = DL_LP_RQST;
        end
        DL_HS_RQST: begin
          if (i_lp_state == LP_00)      w_state_nxt = DL_HS_PRPR;
          else if (i_lp_state != LP_01) w_state_nxt = DL_ERR;
        end
        DL_HS_PRPR: begin
          // the termination enable was issued on entry (output register)
          if (i_lp_state == LP_11) w_state_nxt = DL_STOP;
          else                     w_state_nxt = DL_HS_TERM;
        end
        DL_HS_TERM: begin
          if (i_lp_state == LP_11) w_state_nxt = DL_STOP;
          else if (w_settle_done)  w_state_nxt = DL_HS_RX;
        end
        DL_HS_RX: begin
          if (i_lp_state == LP_11 || i_hs_rx_timeout) w_state_nxt = DL_HS_EOT;
        end
        DL_HS_EOT: begin
          // One cycle: Block No. 4 completes the EoT on its own (REQ-111, REQ-384).
          // OPEN ADR-006 REQ-390: the return to Stop waits for no signal of the byte clock domain
          // LP-00 is the line still in HS after the HS RX timeout (REQ-111, REQ-123)
          w_state_nxt = (i_lp_state == LP_00) ? DL_HS_WAIT : DL_STOP;
        end
        DL_LP_RQST: begin
          if (i_lp_state == LP_00)      w_state_nxt = DL_LP_YIELD;
          else if (i_lp_state == LP_11) w_state_nxt = DL_ERR;
          else if (i_esc_timeout)       w_state_nxt = DL_ESC_WAIT;
        end
        DL_LP_YIELD: begin
          if (i_lp_state == LP_01)      w_state_nxt = DL_ESC_RQST;
          else if (i_lp_state == LP_10) w_state_nxt = DL_ERR;   // turnaround is not supported
          else if (i_lp_state == LP_11) w_state_nxt = DL_STOP;
          else if (i_esc_timeout)       w_state_nxt = DL_ESC_WAIT;
        end
        DL_ESC_RQST: begin
          if (i_lp_state == LP_00)      w_state_nxt = DL_ESC_GO;
          else if (i_lp_state != LP_01) w_state_nxt = DL_ERR;
          else if (i_esc_timeout)       w_state_nxt = DL_ESC_WAIT;
        end
        DL_ESC_GO: begin
          if (i_lp_state == LP_11) w_state_nxt = DL_STOP;
          else if (w_mark)         w_state_nxt = DL_ESC_CMD;
          else if (i_esc_timeout)  w_state_nxt = DL_ESC_WAIT;
        end
        DL_ESC_CMD: begin
          if (i_lp_state == LP_11) w_state_nxt = DL_STOP;
          else if (w_cmd_valid)    w_state_nxt = w_cmd_ulps ? DL_ULPS : DL_ESC_WAIT;
          else if (i_esc_timeout)  w_state_nxt = DL_ESC_WAIT;
        end
        DL_ULPS: begin
          if (i_lp_state == LP_11)      w_state_nxt = DL_STOP;
          else if (i_lp_state == LP_10) w_state_nxt = DL_ULPS_EXIT;
        end
        DL_HS_WAIT, DL_ULPS_EXIT, DL_ESC_WAIT, DL_ERR: begin
          if (i_lp_state == LP_11) w_state_nxt = DL_STOP;
        end
        default: begin
          w_state_nxt = DL_INIT;
        end
      endcase
    end
  end

  // errcontrol_x is set on entry into DL_ERR.
  // REQ-121, REQ-133
  assign w_err_entry = (w_state_nxt == DL_ERR) && (reg_state != DL_ERR);

  // State and outputs are registered together, the outputs from the next state (rtl_notes D-8).
  // The sync-search start is High in DL_HS_RX; its fall on any exit is the EoT request.
  // OPEN ADR-007 REQ-128: the sync-search start, High in DL_HS_RX, is the only signal to Block No. 4
  // OPEN ADR-001 REQ-265: afe_term_en_x rises with the register of DL_HS_PRPR, one cycle after the LP state
  // REQ-083, REQ-106, REQ-108, REQ-109, REQ-110, REQ-111, REQ-118, REQ-119, REQ-120, REQ-127,
  // REQ-129, REQ-133, REQ-134, REQ-148, REQ-253, REQ-254, REQ-316
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_state_reg
    if (!i_core_rst_n) begin
      reg_state             <= DL_INIT;
      reg_lp_prev           <= LP_11;
      reg_stopstate         <= 1'b0;
      reg_ulpsactivenot     <= 1'b1;
      reg_rxulpsesc         <= 1'b0;
      reg_rxtriggeresc      <= '0;
      reg_erresc            <= 1'b0;
      reg_errcontrol        <= 1'b0;
      reg_sync_search_start <= 1'b0;
      reg_hs_en             <= 1'b0;
      reg_term_en           <= 1'b0;
      reg_erresc_tgl        <= 1'b0;
    end else begin
      reg_state             <= w_state_nxt;
      reg_lp_prev           <= i_lp_state;
      reg_stopstate         <= (w_state_nxt == DL_STOP) && !w_stop_hold;
      reg_ulpsactivenot     <= (w_state_nxt != DL_ULPS);
      reg_rxulpsesc         <= (w_state_nxt == DL_ULPS) || (w_state_nxt == DL_ULPS_EXIT);
      reg_sync_search_start <= (w_state_nxt == DL_HS_RX);
      reg_hs_en             <= (w_state_nxt == DL_HS_TERM) || (w_state_nxt == DL_HS_RX);
      reg_term_en           <= (w_state_nxt == DL_HS_PRPR) || (w_state_nxt == DL_HS_TERM) ||
                               (w_state_nxt == DL_HS_RX);
      // trigger bit held until the lane is back in Stop (or reset)
      if ((w_state_nxt == DL_STOP) || (w_state_nxt == DL_INIT)) begin
        reg_rxtriggeresc <= '0;
      end else if ((reg_state == DL_ESC_CMD) && (w_state_nxt == DL_ESC_WAIT)) begin
        reg_rxtriggeresc <= reg_rxtriggeresc | w_cmd_trigger;
      end
      // errors held until the next line-state change (cleared while the lane is held in reset)
      if (w_state_nxt == DL_INIT) begin
        reg_errcontrol <= 1'b0;
      end else if (w_err_entry) begin
        reg_errcontrol <= 1'b1;
      end else if (w_lp_change) begin
        reg_errcontrol <= 1'b0;
      end
      if (w_state_nxt == DL_INIT) begin
        reg_erresc <= 1'b0;
      end else if ((reg_state == DL_ESC_CMD) && (w_state_nxt == DL_ESC_WAIT) && w_cmd_unknown) begin
        reg_erresc <= 1'b1;
      end else if (w_lp_change) begin
        reg_erresc <= 1'b0;
      end
      reg_erresc_tgl <= reg_erresc_tgl ^ ((reg_state == DL_ESC_CMD) && (w_state_nxt == DL_ESC_WAIT) && w_cmd_unknown);
    end
  end

  // The settle counter counts core_clk cycles in DL_HS_TERM and restarts outside it.
  // REQ-130
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_counters
    if (!i_core_rst_n) begin
      reg_settle_cnt <= '0;
    end else begin
      if (reg_state != DL_HS_TERM) begin
        reg_settle_cnt <= '0;
      end else if (!w_settle_done) begin
        reg_settle_cnt <= reg_settle_cnt + 1'b1;
      end
    end
  end

  // REQ-127, REQ-128, REQ-225, REQ-227, REQ-238, REQ-239, REQ-244, REQ-246
  assign o_stopstate         = reg_stopstate;
  assign o_ulpsactivenot     = reg_ulpsactivenot;
  assign o_rxulpsesc         = reg_rxulpsesc;
  assign o_rxtriggeresc      = reg_rxtriggeresc;
  assign o_erresc            = reg_erresc;
  assign o_errcontrol        = reg_errcontrol;
  assign o_sync_search_start = reg_sync_search_start;
  assign o_hs_en             = reg_hs_en;
  assign o_term_en           = reg_term_en;
  assign o_sts_state         = reg_state;
  assign o_sts_erresc_tgl    = reg_erresc_tgl;
endmodule
`default_nettype wire
