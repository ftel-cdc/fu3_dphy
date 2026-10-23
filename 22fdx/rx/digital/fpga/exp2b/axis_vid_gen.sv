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
// Description     : TN2b frame generator, testbench only: synthetic RAW10 frames into the CSI-2 TX Subsystem.
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
// TN2b frame generator (fpga/PLAN_TN2B.md §2.1, §4.4), testbench only: drives s_axis of AMD's CSI-2 TX Subsystem
// with synthetic RAW10 frames in which every pixel follows from its position, and writes them to frames.txt.
// - Pixel p(f, y, x) of frame f, line y, column x (all from 0); tn2b_evidence.py computes the same values on its own:
//     counter   (x + 37*y + 101*f) mod 1024
//     prbs      10 consecutive output bits of the LFSR x^15 + x^14 + 1, first bit as MSB; the LFSR restarts at
//               the start of every line from 1 + f*H + y (15 bits, 1 if that is 0). One step: the new bit is
//               s[14] ^ s[13], s becomes {s[13:0], new bit}, the new bit is the output.
//     synclike  the cycle 0x2E0 0x2E0 0x000 0x000 0x3FF 0x3FF 0x155 0x2AA over x; packed as RAW10 the line
//               carries the bytes 0xB8 (the D-PHY sync byte), runs of 0x00 and 0xFF, 0x55 and 0xAA
// - 4 pixels per beat, pixel k of the beat in tdata[10k+9:10k] and the rest of tdata 0: the components sit in
//   consecutive slots of C_CSI_MAX_BPC (10) bits, as in AMD's example of the TX Subsystem. tkeep all ones,
//   tdest 0 (virtual channel 0).
// - tuser as AMD's example builds it: [0] start of frame on the first beat of a frame, [32:1] the data type
//   (RAW10, 0x2B), [63:48] the word count of the line (width * 10 / 8 bytes), the other bits 0. tlast on the last
//   beat of every line.
// - A beat moves at a rising edge of aclk where tvalid and tready are High. line_gap / frame_gap: cycles with
//   tvalid Low after each line / after each frame (0: the next beat follows at once).
// - frames.txt: "F <frame> <width> <height> <pattern>", then "L <frame> <line> <pixels>" per line, the pixels as
//   3 hex digits each; a frame is written before its first beat.
`timescale 1ns/1ps
module axis_vid_gen #(
  parameter int TDW = 120
) (
  input  logic             aclk,
  output logic [TDW-1:0]   tdata,
  output logic [TDW/8-1:0] tkeep,
  output logic [95:0]      tuser,
  output logic             tlast,
  output logic [1:0]       tdest,
  output logic             tvalid,
  input  logic             tready
);
  localparam int        PPC  = 4;
  localparam logic [5:0] DT_RAW10 = 6'h2B;

  // ---- knobs, set by the testbench ----
  int    width     = 640;
  int    height    = 16;
  string pattern   = "counter";
  int    line_gap  = 0;
  int    frame_gap = 0;
  int    frames_fd = 0;

  // ---- results ----
  int n_frames = 0;
  int n_lines  = 0;
  int n_beats  = 0;

  initial begin
    tdata  = '0;
    tkeep  = '1;
    tuser  = '0;
    tlast  = 1'b0;
    tdest  = '0;
    tvalid = 1'b0;
  end

  function automatic int synclike_px(int x);
    int cyc [8] = '{'h2E0, 'h2E0, 'h000, 'h000, 'h3FF, 'h3FF, 'h155, 'h2AA};
    return cyc[x % 8];
  endfunction

  function automatic void line_pixels(input int f, input int y, ref int px [$]);
    logic [14:0] s;
    logic        nb;
    px.delete();
    if (pattern == "prbs") begin
      s = 15'(1 + f * height + y);
      if (s == '0) s = 15'd1;
      for (int x = 0; x < width; x++) begin
        int p = 0;
        for (int b = 0; b < 10; b++) begin
          nb = s[14] ^ s[13];
          s  = {s[13:0], nb};
          p  = (p << 1) | nb;
        end
        px.push_back(p);
      end
    end else if (pattern == "synclike") begin
      for (int x = 0; x < width; x++) px.push_back(synclike_px(x));
    end else begin
      for (int x = 0; x < width; x++) px.push_back((x + 37 * y + 101 * f) % 1024);
    end
  endfunction

  task automatic put(input logic [TDW-1:0] d, input logic [95:0] u, input bit last);
    tdata  <= d;
    tuser  <= u;
    tlast  <= last;
    tvalid <= 1'b1;
    do @(posedge aclk); while (tready !== 1'b1);
    n_beats++;
  endtask

  task automatic idle(input int cycles);
    if (cycles <= 0) return;
    tvalid <= 1'b0;
    tlast  <= 1'b0;
    repeat (cycles) @(posedge aclk);
  endtask

  // After the last beat the testbench calls stop(), so that the beat is not taken again.
  task automatic stop();
    tvalid <= 1'b0;
    tlast  <= 1'b0;
    @(posedge aclk);
  endtask

  // Frame f, then frame_gap idle cycles. The caller starts it just after a rising edge of aclk, and calls stop()
  // when no frame follows at once.
  task automatic send_frame(input int f);
    int          px [$];
    logic [15:0] wc = 16'(width * 10 / 8);
    if (frames_fd != 0) begin
      $fdisplay(frames_fd, "F %0d %0d %0d %s", f, width, height, pattern);
      for (int y = 0; y < height; y++) begin
        string s = "";
        line_pixels(f, y, px);
        foreach (px[i]) s = {s, $sformatf("%03x", px[i])};
        $fdisplay(frames_fd, "L %0d %0d %s", f, y, s);
      end
      $fflush(frames_fd);
    end
    for (int y = 0; y < height; y++) begin
      line_pixels(f, y, px);
      for (int b = 0; b < width / PPC; b++) begin
        logic [TDW-1:0] d = '0;
        for (int k = 0; k < PPC; k++) d[10 * k +: 10] = 10'(px[PPC * b + k]);
        put(d, {32'd0, wc, 15'd0, 26'd0, DT_RAW10, (y == 0 && b == 0)}, b == width / PPC - 1);
      end
      n_lines++;
      if (y < height - 1) idle(line_gap);
    end
    n_frames++;
    idle(frame_gap);
  endtask
endmodule
