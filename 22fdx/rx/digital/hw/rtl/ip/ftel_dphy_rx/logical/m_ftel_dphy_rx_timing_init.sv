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
// Module          : m_ftel_dphy_rx_timing_init
// Description     : Timing & Init Control (HAS Block No. 6): reset synchronizers of the
//                   core, DDR and byte domains and of Block No. 4 of each lane, level
//                   synchronizers of the PPI enables, rising edge of forcerxmode_x, TINIT
//                   counters, init_done, HS RX and escape watchdogs, distribution of the
//                   timer values.
// Parent          : m_ftel_dphy_rx
// HAS             : draft v0.14, §4.1, §4.2, §4.7, Table 4-3, Figure 4-10
// Clock domains   : core, ddr and byte (reset synchronizers only)
// REQ-IDs         : REQ-022, REQ-023, REQ-056, REQ-058, REQ-059, REQ-062, REQ-063, REQ-064,
//                   REQ-065, REQ-066, REQ-067, REQ-068, REQ-189, REQ-190, REQ-191, REQ-192,
//                   REQ-193, REQ-194, REQ-195, REQ-196, REQ-197, REQ-198, REQ-221, REQ-223,
//                   REQ-321, REQ-338
// OPEN            : K6
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
module m_ftel_dphy_rx_timing_init
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;
#(
  parameter int PARA_NUM_LANES = 4
) (
  // ---- clock / reset ----
  input  logic                              i_core_clk,
  input  logic                              i_ddr_clk,
  input  logic                              i_byte_clk,
  // REQ-221
  input  logic                              i_phy_core_rst,
  // ---- control: PPI enables, levels from the registers of the CSI-2 controller ----
  input  logic                              i_cl_enable,
  input  logic [PARA_NUM_LANES-1:0]         i_dl_enable,
  input  logic [PARA_NUM_LANES-1:0]         i_forcerxmode,
  // ---- data in: line and FSM states ----
  input  lp_state_t                         i_cl_lp_state,
  input  lp_state_t [PARA_NUM_LANES-1:0]    i_lp_state,
  input  dl_state_t [PARA_NUM_LANES-1:0]    i_dl_state,
  // ---- data out: resets, enables, initialization, watchdogs, timer values ----
  output logic                              o_core_rst_n,
  output logic                              o_ddr_rst_n,
  output logic [PARA_NUM_LANES-1:0]         o_hs_rst_n,
  output logic                              o_cl_en,
  output logic [PARA_NUM_LANES-1:0]         o_dl_en,
  output logic [PARA_NUM_LANES-1:0]         o_force_rise,
  output logic                              o_cl_init_done,
  output logic [PARA_NUM_LANES-1:0]         o_dl_init_done,
  // REQ-223
  output logic                              o_init_done,
  output logic [PARA_NUM_LANES-1:0]         o_hs_rx_timeout,
  output logic [PARA_NUM_LANES-1:0]         o_esc_timeout,
  output logic [C_HS_SETTLE_CYC_W-1:0]      o_cfg_hs_settle_cyc,
  output logic [C_CLK_SETTLE_CYC_W-1:0]     o_cfg_clk_settle_cyc,
  output logic [C_EOT_SKIP_BYTES_W-1:0]     o_cfg_eot_skip_bytes,
  // ---- status: source toggles of the events for Block No. 8 (rtl_notes D-2) ----
  output logic [PARA_NUM_LANES-1:0]         o_sts_hs_rx_timeout_tgl,
  output logic [PARA_NUM_LANES-1:0]         o_sts_esc_timeout_tgl,
  // ---- configuration ----
  // CDC_QUASI_STATIC: timing fields of Table 3-2 (HAS §4.1)
  input  cfg_timing_t                       i_cfg_timing
);

  logic                                     reg_cl_tinit_done;
  logic [C_TINIT_CYC_W-1:0]                 reg_cl_tinit_cnt;
  logic [PARA_NUM_LANES-1:0]                reg_dl_tinit_done;
  logic [PARA_NUM_LANES-1:0][C_TINIT_CYC_W-1:0] reg_dl_tinit_cnt;
  logic [PARA_NUM_LANES-1:0]                reg_force_d;
  logic [PARA_NUM_LANES-1:0]                reg_hs_lane_en;
  logic                                     reg_init_done;
  logic [PARA_NUM_LANES-1:0][C_HS_RX_TIMEOUT_CYC_W-1:0] reg_hs_rx_cnt;
  logic [PARA_NUM_LANES-1:0][C_ESC_TIMEOUT_CYC_W-1:0]   reg_esc_cnt;
  logic [PARA_NUM_LANES-1:0]                reg_sts_hs_rx_timeout_tgl;
  logic [PARA_NUM_LANES-1:0]                reg_sts_esc_timeout_tgl;
  logic                                     w_arst_n;
  logic                                     w_core_rst_n;
  logic                                     w_byte_rst_n;
  logic                                     w_cl_en;
  logic [PARA_NUM_LANES-1:0]                w_dl_en;
  logic [PARA_NUM_LANES-1:0]                w_force;
  logic [PARA_NUM_LANES-1:0]                w_force_rise;
  logic [PARA_NUM_LANES-1:0]                w_hs_arst_n;
  logic                                     w_cl_tinit_hit;
  logic [PARA_NUM_LANES-1:0]                w_dl_tinit_hit;
  logic [PARA_NUM_LANES-1:0]                w_in_hs_rx;
  logic [PARA_NUM_LANES-1:0]                w_in_esc;
  logic [PARA_NUM_LANES-1:0]                w_hs_rx_expired;
  logic [PARA_NUM_LANES-1:0]                w_esc_expired;

  // ------------------------------------------------------------------ resets
  // OPEN K6 REQ-062: phy_core_rst active High and asynchronous; each domain releases it synchronously
  assign w_arst_n = ~i_phy_core_rst;

  // CDC_CROSSING: phy_core_rst -> core: reset release (HAS §4.2, Figure 4-1)
  // REQ-066
  m_ftel_dphy_rx_rst_sync u_rst_sync_0 (
    .i_clk           (i_core_clk),
    .i_async_reset_n (w_arst_n),
    .o_sync_reset_n  (w_core_rst_n)
  );

  // The byte domain leaves reset only once rxbyteclkhs runs.
  // CDC_CROSSING: phy_core_rst -> byte: reset release (HAS §4.2, Figure 4-1)
  // REQ-066, REQ-067
  m_ftel_dphy_rx_rst_sync u_rst_sync_1 (
    .i_clk           (i_byte_clk),
    .i_async_reset_n (w_arst_n),
    .o_sync_reset_n  (w_byte_rst_n)
  );

  // The DDR-clock domain (clock-activity toggles of Block No. 1) leaves reset on the second DDR
  // clock edge; the divider of Block No. 1 has its own reset, the byte-clock enable.
  // CDC_CROSSING: phy_core_rst -> ddr: reset release (HAS §4.2, Figure 4-1)
  // REQ-066, REQ-190, REQ-338
  m_ftel_dphy_rx_rst_sync u_rst_sync_2 (
    .i_clk           (i_ddr_clk),
    .i_async_reset_n (w_arst_n),
    .o_sync_reset_n  (o_ddr_rst_n)
  );

  // REQ-066
  assign o_core_rst_n = w_core_rst_n;

  // ------------------------------------------------------------------ enables
  // CDC_CROSSING: lite_aclk -> core: i_cl_enable (HAS §4.1, Table 4-2)
  // REQ-056, REQ-059, REQ-190
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (2)
  ) u_sync_0 (
    .i_clk      (i_core_clk),
    .i_rstn     (w_core_rst_n),
    .i_data_in  (i_cl_enable),
    .o_data_out (w_cl_en)
  );

  for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_lane
    // CDC_CROSSING: lite_aclk -> core: i_dl_enable (HAS §4.1, Table 4-2)
    // REQ-056, REQ-059, REQ-190
    m_ftel_dphy_rx_sync #(
      .PARA_LEVELS (2)
    ) u_sync_0 (
      .i_clk      (i_core_clk),
      .i_rstn     (w_core_rst_n),
      .i_data_in  (i_dl_enable[x]),
      .o_data_out (w_dl_en[x])
    );

    // CDC_CROSSING: lite_aclk -> core: i_forcerxmode (HAS §4.1, Table 4-2)
    // REQ-056, REQ-059, REQ-190
    m_ftel_dphy_rx_sync #(
      .PARA_LEVELS (2)
    ) u_sync_1 (
      .i_clk      (i_core_clk),
      .i_rstn     (w_core_rst_n),
      .i_data_in  (i_forcerxmode[x]),
      .o_data_out (w_force[x])
    );

    // Block No. 4 of the lane is cleared while the lane or the clock lane is disabled and
    // released on the second byte-clock edge after it is enabled. The clear is the registered
    // AND of the synchronized enables, so it cannot glitch (rtl_notes D-4).
    // REQ-058, REQ-064, REQ-068
    assign w_hs_arst_n[x] = w_byte_rst_n & reg_hs_lane_en[x];

    // CDC_CROSSING: core -> byte: lane enable, reset release of Block No. 4 (HAS §4.2, Table 4-2)
    // REQ-064, REQ-068
    m_ftel_dphy_rx_rst_sync u_rst_sync_0 (
      .i_clk           (i_byte_clk),
      .i_async_reset_n (w_hs_arst_n[x]),
      .o_sync_reset_n  (o_hs_rst_n[x])
    );
  end

  // A rising forcerxmode_x restarts the initialization of its lane.
  // OPEN K6 REQ-065: forcerxmode_x acts on its rising edge
  assign w_force_rise = w_force & ~reg_force_d;

  // REQ-058, REQ-064, REQ-065
  always_ff @(posedge i_core_clk or negedge w_core_rst_n) begin : p_enables
    if (!w_core_rst_n) begin
      reg_force_d    <= '0;
      reg_hs_lane_en <= '0;
    end else begin
      reg_force_d    <= w_force;
      reg_hs_lane_en <= w_dl_en & {PARA_NUM_LANES{w_cl_en}};
    end
  end

  // The synchronized enables go to the FSMs (INIT while Low) and to Block No. 7.
  // REQ-063, REQ-190, REQ-191
  assign o_cl_en      = w_cl_en;
  assign o_dl_en      = w_dl_en;
  assign o_force_rise = w_force_rise;

  // ------------------------------------------------------------------ TINIT
  // One counter per lane counts consecutive LP-11 cycles and restarts on any other state and on
  // a lane reset; the lane is initialized when it reaches tinit_cyc, and stays so until the
  // next lane reset (rtl_notes D-10).
  // REQ-192, REQ-194, REQ-321
  assign w_cl_tinit_hit = ({1'b0, reg_cl_tinit_cnt} + 1'b1) >= {1'b0, i_cfg_timing.tinit_cyc};

  // REQ-022, REQ-192, REQ-194
  always_ff @(posedge i_core_clk or negedge w_core_rst_n) begin : p_cl_tinit
    if (!w_core_rst_n) begin
      reg_cl_tinit_cnt  <= '0;
      reg_cl_tinit_done <= 1'b0;
    end else if (!w_cl_en) begin
      reg_cl_tinit_cnt  <= '0;
      reg_cl_tinit_done <= 1'b0;
    end else if (!reg_cl_tinit_done) begin
      if (i_cl_lp_state != LP_11) begin
        reg_cl_tinit_cnt <= '0;
      end else if (w_cl_tinit_hit) begin
        reg_cl_tinit_done <= 1'b1;
      end else begin
        reg_cl_tinit_cnt <= reg_cl_tinit_cnt + 1'b1;
      end
    end
  end

  for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_tinit
    // REQ-192, REQ-194, REQ-321
    assign w_dl_tinit_hit[x] = ({1'b0, reg_dl_tinit_cnt[x]} + 1'b1) >= {1'b0, i_cfg_timing.tinit_cyc};

    // REQ-022, REQ-065, REQ-192, REQ-194
    always_ff @(posedge i_core_clk or negedge w_core_rst_n) begin : p_dl_tinit
      if (!w_core_rst_n) begin
        reg_dl_tinit_cnt[x]  <= '0;
        reg_dl_tinit_done[x] <= 1'b0;
      end else if (!w_dl_en[x] || w_force_rise[x]) begin
        reg_dl_tinit_cnt[x]  <= '0;
        reg_dl_tinit_done[x] <= 1'b0;
      end else if (!reg_dl_tinit_done[x]) begin
        if (i_lp_state[x] != LP_11) begin
          reg_dl_tinit_cnt[x] <= '0;
        end else if (w_dl_tinit_hit[x]) begin
          reg_dl_tinit_done[x] <= 1'b1;
        end else begin
          reg_dl_tinit_cnt[x] <= reg_dl_tinit_cnt[x] + 1'b1;
        end
      end
    end
  end

  // REQ-192
  assign o_cl_init_done = reg_cl_tinit_done;
  assign o_dl_init_done = reg_dl_tinit_done;

  // OPEN K6 REQ-195: init_done is the registered AND of the clock lane and, per data lane, initialized or not enabled
  // REQ-022, REQ-193
  always_ff @(posedge i_core_clk or negedge w_core_rst_n) begin : p_init_done
    if (!w_core_rst_n) begin
      reg_init_done <= 1'b0;
    end else begin
      reg_init_done <= reg_cl_tinit_done & (&(reg_dl_tinit_done | ~w_dl_en));
    end
  end

  // REQ-193, REQ-223
  assign o_init_done = reg_init_done;

  // ------------------------------------------------------------------ watchdogs
  // One HS RX and one escape counter per data lane, counting core_clk cycles in the watched
  // states and restarting outside them; expiry when the count reaches the field value.
  for (genvar x = 0; x < PARA_NUM_LANES; x++) begin : g_wd
    // REQ-196, REQ-197
    assign w_in_hs_rx[x] = (i_dl_state[x] == DL_HS_RX);
    assign w_in_esc[x]   = (i_dl_state[x] == DL_LP_RQST)  || (i_dl_state[x] == DL_LP_YIELD) ||
                           (i_dl_state[x] == DL_ESC_RQST) || (i_dl_state[x] == DL_ESC_GO)   ||
                           (i_dl_state[x] == DL_ESC_CMD);
    assign w_hs_rx_expired[x] = w_in_hs_rx[x] && (reg_hs_rx_cnt[x] == i_cfg_timing.hs_rx_timeout_cyc);
    assign w_esc_expired[x]   = w_in_esc[x] && (reg_esc_cnt[x] == i_cfg_timing.esc_timeout_cyc);

    // REQ-196, REQ-197
    always_ff @(posedge i_core_clk or negedge w_core_rst_n) begin : p_watchdog
      if (!w_core_rst_n) begin
        reg_hs_rx_cnt[x] <= '0;
        reg_esc_cnt[x]   <= '0;
      end else begin
        if (!w_in_hs_rx[x]) begin
          reg_hs_rx_cnt[x] <= '0;
        end else if (!w_hs_rx_expired[x]) begin
          reg_hs_rx_cnt[x] <= reg_hs_rx_cnt[x] + 1'b1;
        end
        if (!w_in_esc[x]) begin
          reg_esc_cnt[x] <= '0;
        end else if (!w_esc_expired[x]) begin
          reg_esc_cnt[x] <= reg_esc_cnt[x] + 1'b1;
        end
      end
    end

    // Status events for Block No. 8: the source half of a toggle synchronizer (rtl_notes D-2).
    // REQ-198
    always_ff @(posedge i_core_clk or negedge w_core_rst_n) begin : p_sts_tgl
      if (!w_core_rst_n) begin
        reg_sts_hs_rx_timeout_tgl[x] <= 1'b0;
        reg_sts_esc_timeout_tgl[x]   <= 1'b0;
      end else begin
        reg_sts_hs_rx_timeout_tgl[x] <= reg_sts_hs_rx_timeout_tgl[x] ^ w_hs_rx_expired[x];
        reg_sts_esc_timeout_tgl[x]   <= reg_sts_esc_timeout_tgl[x] ^ w_esc_expired[x];
      end
    end
  end

  // REQ-196, REQ-198
  assign o_hs_rx_timeout         = w_hs_rx_expired;
  assign o_esc_timeout           = w_esc_expired;
  assign o_sts_hs_rx_timeout_tgl = reg_sts_hs_rx_timeout_tgl;
  assign o_sts_esc_timeout_tgl   = reg_sts_esc_timeout_tgl;

  // Timer values, quasi-static, distributed to the blocks that use them: Blocks No. 2, 3 and 4.
  // REQ-023, REQ-189
  assign o_cfg_hs_settle_cyc  = i_cfg_timing.hs_settle_cyc;
  assign o_cfg_clk_settle_cyc = i_cfg_timing.clk_settle_cyc;
  assign o_cfg_eot_skip_bytes = i_cfg_timing.eot_skip_bytes;
endmodule
`default_nettype wire
