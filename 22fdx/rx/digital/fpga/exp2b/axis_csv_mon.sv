//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-22
// Description     : TN2b AXI4-Stream video monitor, testbench only: one ILA-style CSV row per clock with tvalid.
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-22   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
// TN2b AXI4-Stream video monitor (fpga/PLAN_TN2B.md §4.4), testbench only: one CSV row per rising edge of aclk
// where tvalid is High while en is High, in the layout of ppi_csv_mon (a line of probe names, a "Radix - " line,
// then the samples), so that fpga/tools/csi2_dump.py axis reads it (--tuser sof). It samples the values just
// before the edge. Columns: sim_time_ps, tdata (the 4 pixels, 40 bits), tvalid, tready, sof (tuser[0]), tlast,
// tdest, and the fields of tuser:
// - RX = 0, the input of the TX Subsystem (axis_vid_gen): tu_dt = tuser[6:1], tu_wc = tuser[63:48];
// - RX = 1, video_out of a CSI-2 RX Subsystem with VFB_TU_WIDTH 96: tu_frame = tuser[31:16], tu_line =
//   tuser[47:32], tu_wc = tuser[63:48], tu_dt = tuser[69:64]. This layout is checked against the frames sent
//   (PLAN_TN2B.md, step S1). There is no packet-error column: for pixel data the frame buffer of the subsystem
//   (vfb_v1_0) gives tuser[15:1] as 0, the packet error of the controller only ends the line.
// Counts while en is High: beats (tvalid and tready), lines (beats with tlast) and frames (beats with sof).
`timescale 1ns/1ps
module axis_csv_mon #(
  parameter bit RX = 1'b1
) (
  input  logic        aclk,
  input  logic        en,
  input  logic [39:0] tdata,
  input  logic        tvalid,
  input  logic        tready,
  input  logic [95:0] tuser,
  input  logic        tlast,
  input  logic [9:0]  tdest
);
  int     fd = 0;
  longint n  = 0;
  int     n_beats = 0, n_lines = 0, n_frames = 0;

  logic [15:0] frame_no, line_no, wc;
  logic [5:0]  dt;
  assign frame_no = RX ? tuser[31:16] : '0;
  assign line_no  = RX ? tuser[47:32] : '0;
  assign wc       = tuser[63:48];
  assign dt       = RX ? tuser[69:64] : tuser[6:1];

  function automatic void open(input string path);
    fd = $fopen(path, "w");
    if (fd == 0) $fatal(1, "axis_csv_mon: cannot open %s", path);
    $fdisplay(fd, "Sample in Buffer,Sample in Window,TRIGGER,sim_time_ps,tdata[39:0],tvalid,tready,sof,tlast,tdest[9:0],%s",
              "tu_frame[15:0],tu_line[15:0],tu_wc[15:0],tu_dt[5:0]");
    $fdisplay(fd, "Radix - UNSIGNED,UNSIGNED,UNSIGNED,UNSIGNED,HEX,BIN,BIN,BIN,BIN,HEX,HEX,HEX,HEX,HEX");
  endfunction

  function automatic void close();
    if (fd != 0) $fclose(fd);
    fd = 0;
  endfunction

  always @(posedge aclk) if (en && tvalid === 1'b1) begin
    if (fd != 0) begin
      $fwrite(fd, "%0d,%0d,0,%0d,%010x,%b,%b,%b,%b,%03x", n, n, longint'($realtime * 1000.0), tdata, tvalid, tready,
              tuser[0], tlast, tdest);
      $fwrite(fd, ",%04x,%04x,%04x,%02x\n", frame_no, line_no, wc, dt);
      n++;
    end
    if (tready === 1'b1) begin
      n_beats++;
      if (tuser[0] === 1'b1) n_frames++;
      if (tlast === 1'b1) n_lines++;
    end
  end
endmodule
