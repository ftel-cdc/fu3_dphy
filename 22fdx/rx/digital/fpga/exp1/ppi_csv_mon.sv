//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-19
// Description     : TN1/TN2 PPI monitor, testbench only: one CSV row per byte clock, in the layout of
//                   Vivado's write_hw_ila_data.
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-19   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
// TN1/TN2 PPI monitor (fpga/PLAN_TN1_TN3.md §1), testbench only: one CSV row per rising edge of the byte
// clock while en is High, in the layout of Vivado's write_hw_ila_data (a line of probe names, a "Radix - "
// line, then the samples), so that fpga/tools/csi2_dump.py reads simulation and ILA captures alike.
// Like an ILA, it samples the values just before the clock edge. sim_time_ps is the time of the edge.
`timescale 1ns/1ps
module ppi_csv_mon #(
  parameter int NL = 4
) (
  input  logic                clk,
  input  logic                en,
  input  logic [NL-1:0][7:0]  data,
  input  logic [NL-1:0]       valid,
  input  logic [NL-1:0]       active,
  input  logic [NL-1:0]       sync,
  input  logic [NL-1:0]       errsot,
  input  logic [NL-1:0]       errsotsync,
  input  logic [NL-1:0]       stop,
  input  logic                cl_stop
);
  int     fd = 0;
  longint n  = 0;

  function automatic void open(input string path);
    string names, radix;
    fd = $fopen(path, "w");
    if (fd == 0) $fatal(1, "ppi_csv_mon: cannot open %s", path);
    names = "Sample in Buffer,Sample in Window,TRIGGER,sim_time_ps";
    radix = "Radix - UNSIGNED,UNSIGNED,UNSIGNED,UNSIGNED";
    for (int l = 0; l < NL; l++) begin
      names = {names, $sformatf(",dl%0d_rxdatahs[7:0],dl%0d_rxvalidhs,dl%0d_rxactivehs,dl%0d_rxsynchs", l, l, l, l),
               $sformatf(",dl%0d_errsoths,dl%0d_errsotsynchs,dl%0d_stopstate", l, l, l)};
      radix = {radix, ",HEX,BIN,BIN,BIN,BIN,BIN,BIN"};
    end
    $fdisplay(fd, "%s,cl_stopstate", names);
    $fdisplay(fd, "%s,BIN", radix);
  endfunction

  function automatic void close();
    if (fd != 0) $fclose(fd);
    fd = 0;
  endfunction

  always @(posedge clk) if (en && fd != 0) begin
    $fwrite(fd, "%0d,%0d,0,%0d", n, n, longint'($realtime * 1000.0));
    for (int l = 0; l < NL; l++)
      $fwrite(fd, ",%02x,%b,%b,%b,%b,%b,%b", data[l], valid[l], active[l], sync[l], errsot[l], errsotsync[l], stop[l]);
    $fwrite(fd, ",%b\n", cl_stop);
    n++;
  end
endmodule
