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
// Module          : ftel_dphy_rx_pkg
// Description     : Types and constants shared by the blocks of ftel_dphy_rx: LP line
//                   state, the clock-lane and data-lane FSM states, escape entry codes,
//                   SoT leader, run-time timing fields and the delay-line entry.
// Parent          : none
// HAS             : draft v0.11, §4.3, §4.4, §4.5, §4.6, Table 4-6
// Clock domains   : none
// REQ-IDs         : REQ-023, REQ-057, REQ-076, REQ-084, REQ-104, REQ-137, REQ-139, REQ-142,
//                   REQ-143, REQ-144, REQ-145, REQ-153, REQ-165, REQ-169
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
package ftel_dphy_rx_pkg;

  import ftel_dphy_rx_config_pkg::*;

  // Line state of one lane as {Dp, Dn}: LP-01 is Dp = 0, Dn = 1 (Mark-0); LP-10 is Mark-1.
  // REQ-084, REQ-104
  typedef enum logic [1:0] {
    LP_00 = 2'b00,
    LP_01 = 2'b01,
    LP_10 = 2'b10,
    LP_11 = 2'b11
  } lp_state_t;

  // Clock-lane FSM, Table 4-4.
  // REQ-084
  typedef enum logic [3:0] {
    CL_INIT,
    CL_STOP,
    CL_HS_RQST,
    CL_HS_PRPR,
    CL_HS_TERM,
    CL_HS_CLK,
    CL_HS_END,
    CL_ULPS_RQST,
    CL_ULPS,
    CL_ULPS_EXIT,
    CL_WAIT
  } cl_state_t;

  // Data-lane FSM, Table 4-5.
  // REQ-104
  typedef enum logic [4:0] {
    DL_INIT,
    DL_STOP,
    DL_HS_RQST,
    DL_HS_PRPR,
    DL_HS_TERM,
    DL_HS_RX,
    DL_HS_EOT,
    DL_HS_WAIT,
    DL_LP_RQST,
    DL_LP_YIELD,
    DL_ESC_RQST,
    DL_ESC_GO,
    DL_ESC_CMD,
    DL_ULPS,
    DL_ULPS_EXIT,
    DL_ESC_WAIT,
    DL_ERR
  } dl_state_t;

  // Escape entry commands of Table 4-6 with the first received bit in the MSB, as the escape
  // decoder shifts them; every other value (LPDT included while PARA_LPDT_EN = 0) is unknown.
  // REQ-137, REQ-139
  localparam int               C_ESC_BITS           = 8;
  localparam logic [C_ESC_BITS-1:0] C_ESC_ULPS      = 8'b00011110;
  // REQ-142, REQ-143, REQ-144, REQ-145
  localparam int               C_NUM_TRIGGERS       = 4;
  localparam logic [C_ESC_BITS-1:0] C_ESC_TRIG_RESET     = 8'b01100010;
  localparam logic [C_ESC_BITS-1:0] C_ESC_TRIG_UNKNOWN_3 = 8'b01011101;
  localparam logic [C_ESC_BITS-1:0] C_ESC_TRIG_UNKNOWN_4 = 8'b00100001;
  localparam logic [C_ESC_BITS-1:0] C_ESC_TRIG_UNKNOWN_5 = 8'b10100000;

  // SoT leader ...00011101 (first bit received first) with the first received bit in bit 0,
  // the order of the AFE words and of rxdatahs_x.
  // REQ-153
  localparam logic [C_DESER_RATIO-1:0] C_SYNC_LEADER = 8'b1011_1000;
  // A deskew burst starts with a run of at least this many ones after HS-0.
  // REQ-165
  localparam int C_DESKEW_RUN = 16;

  // Reset value of the lane map (logical lane x selects physical lane x) and of the polarity
  // bits, for the configuration registers of Block No. 8 (absent until K3, rtl_notes D-2).
  // Sized for the largest lane count; a smaller IP uses the low entries.
  // REQ-076
  localparam int C_MAX_LANES = 4;
  localparam logic [C_MAX_LANES-1:0][1:0] C_LANE_MAP_RST = {2'd3, 2'd2, 2'd1, 2'd0};
  localparam logic [C_MAX_LANES-1:0]      C_LANE_POL_RST = '0;

  // Width of a lane-map field for a given lane count (rtl_notes D-6).
  function automatic int f_lane_sel_w(input int num_lanes);
    return (num_lanes > 1) ? $clog2(num_lanes) : 1;
  endfunction

  // Run-time timing fields of Table 3-2, quasi-static for every block that uses them.
  // REQ-023, REQ-057
  typedef struct packed {
    logic [C_HS_SETTLE_CYC_W-1:0]     hs_settle_cyc;
    logic [C_CLK_SETTLE_CYC_W-1:0]    clk_settle_cyc;
    logic [C_TINIT_CYC_W-1:0]         tinit_cyc;
    logic [C_HS_RX_TIMEOUT_CYC_W-1:0] hs_rx_timeout_cyc;
    logic [C_ESC_TIMEOUT_CYC_W-1:0]   esc_timeout_cyc;
    logic [C_EOT_SKIP_BYTES_W-1:0]    eot_skip_bytes;
  } cfg_timing_t;

  // One entry of the EoT delay line of Block No. 4: a byte and its flags.
  // REQ-169
  typedef struct packed {
    logic [C_DESER_RATIO-1:0] data;
    logic                     valid;
    logic                     sync;
    logic                     soterr;
    logic                     sotsyncerr;
    logic                     skewcal;
    logic                     active;
  } hs_entry_t;

endpackage
`default_nettype wire
