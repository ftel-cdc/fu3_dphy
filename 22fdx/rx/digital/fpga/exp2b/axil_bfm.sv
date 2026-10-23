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
// Description     : TN2b AXI4-Lite master, testbench only: register accesses of the CSI-2 subsystems.
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
// TN2b AXI4-Lite master (fpga/PLAN_TN2B.md §4.4), testbench only: the testbench programs and reads the CSI-2
// subsystems through it, in the order of AMD's drivers.
// - wr(addr, data): address and data are offered together, with all byte strobes; the write is done when both
//   were taken and the response came back. rd(addr, data) likewise with the read channels.
// - Signals change just after the rising edge of aclk and are sampled at the next one, as a synchronous master.
// - Every handshake waits at most timeout_cyc cycles of aclk. A timeout, or a response other than OKAY, is
//   printed and counted in errors, and the access ends; a timed-out read returns 32'hDEAD_BEEF.
// - poll(addr, mask, want, max_reads, ok): reads until (data & mask) == want, at most max_reads times, as the
//   wait loops of the drivers do; ok tells whether it got there. Only its first and last reads are printed.
// - Each access prints one line "TB AXIL <name> W|R 0x<addr> 0x<data>"; quiet = 1 stops them.
`timescale 1ns/1ps
module axil_bfm #(
  parameter string NAME = "axil",
  parameter int    AW   = 8
) (
  input  logic          aclk,
  input  logic          aresetn,
  output logic [AW-1:0] awaddr,
  output logic          awvalid,
  input  logic          awready,
  output logic [31:0]   wdata,
  output logic [3:0]    wstrb,
  output logic          wvalid,
  input  logic          wready,
  input  logic [1:0]    bresp,
  input  logic          bvalid,
  output logic          bready,
  output logic [AW-1:0] araddr,
  output logic          arvalid,
  input  logic          arready,
  input  logic [31:0]   rdata,
  input  logic [1:0]    rresp,
  input  logic          rvalid,
  output logic          rready
);
  // ---- knobs, set by the testbench ----
  int timeout_cyc = 10000;
  bit quiet       = 1'b0;

  // ---- results ----
  int n_writes = 0;
  int n_reads  = 0;
  int errors   = 0;

  initial begin
    awaddr  = '0;
    awvalid = 1'b0;
    wdata   = '0;
    wstrb   = '0;
    wvalid  = 1'b0;
    bready  = 1'b0;
    araddr  = '0;
    arvalid = 1'b0;
    rready  = 1'b0;
  end

  task automatic fail(input string what, input logic [AW-1:0] addr);
    errors++;
    $display("TB AXIL %s ERROR: %s at 0x%0h, %.3f ns", NAME, what, addr, $realtime);
  endtask

  task automatic wr(input logic [AW-1:0] addr, input logic [31:0] data);
    bit aw_done = 1'b0, w_done = 1'b0;
    int n = 0;
    @(posedge aclk);
    awaddr  <= addr;
    awvalid <= 1'b1;
    wdata   <= data;
    wstrb   <= 4'hF;
    wvalid  <= 1'b1;
    while (!(aw_done && w_done)) begin
      @(posedge aclk);
      if (awvalid && awready) begin aw_done = 1'b1; awvalid <= 1'b0; end
      if (wvalid && wready)   begin w_done  = 1'b1; wvalid  <= 1'b0; end
      if (++n > timeout_cyc) begin
        awvalid <= 1'b0;
        wvalid  <= 1'b0;
        fail("no address or data handshake", addr);
        return;
      end
    end
    bready <= 1'b1;
    n = 0;
    do begin
      @(posedge aclk);
      if (++n > timeout_cyc) begin
        bready <= 1'b0;
        fail("no write response", addr);
        return;
      end
    end while (!bvalid);
    bready <= 1'b0;
    if (bresp !== 2'b00) fail($sformatf("write response %b", bresp), addr);
    n_writes++;
    if (!quiet) $display("TB AXIL %s W 0x%02h 0x%08h", NAME, addr, data);
  endtask

  task automatic rd(input logic [AW-1:0] addr, output logic [31:0] data, input bit show = 1'b1);
    int n = 0;
    data = 32'hDEAD_BEEF;
    @(posedge aclk);
    araddr  <= addr;
    arvalid <= 1'b1;
    do begin
      @(posedge aclk);
      if (++n > timeout_cyc) begin
        arvalid <= 1'b0;
        fail("no read address handshake", addr);
        return;
      end
    end while (!arready);
    arvalid <= 1'b0;
    rready  <= 1'b1;
    n = 0;
    do begin
      @(posedge aclk);
      if (++n > timeout_cyc) begin
        rready <= 1'b0;
        fail("no read data", addr);
        return;
      end
    end while (!rvalid);
    data = rdata;
    rready <= 1'b0;
    if (rresp !== 2'b00) fail($sformatf("read response %b", rresp), addr);
    n_reads++;
    if (!quiet && show) $display("TB AXIL %s R 0x%02h 0x%08h", NAME, addr, data);
  endtask

  task automatic poll(input logic [AW-1:0] addr, input logic [31:0] mask, input logic [31:0] want,
                      input int max_reads, output bit ok);
    logic [31:0] d;
    int k;
    ok = 1'b0;
    for (k = 1; k <= max_reads; k++) begin
      rd(addr, d, k == 1);
      if ((d & mask) === (want & mask)) begin
        ok = 1'b1;
        break;
      end
    end
    if (!quiet)
      $display("TB AXIL %s POLL 0x%02h mask 0x%08h want 0x%08h: %s after %0d reads, last 0x%08h", NAME, addr, mask,
               want, ok ? string'("reached") : string'("NOT reached"), ok ? k : max_reads, d);
  endtask
endmodule
