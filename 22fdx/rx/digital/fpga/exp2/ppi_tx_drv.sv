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
// Description     : TN2a PPI driver of AMD's D-PHY TX (fpga/PLAN_TN2A.md §3.2), testbench only.
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
// TN2a PPI driver (fpga/PLAN_TN2A.md §3.2), testbench only: drives the PPI of AMD's D-PHY TX (mipi_dphy 4.3,
// MASTER) on its txbyteclkhs, as a CSI-2 controller would.
// - start_clock(): cl_txrequesths High for good, so the clock lane enters HS once and then runs continuously
//   (the IP has no parameter for a continuous clock; AMD's example does the same). It returns 2 us after
//   cl_txclkactivehs rises or, when that does not happen within 50 us, 2 us after cl_stopstate falls.
// - burst(id, bytes[NL]): the lanes with bytes raise txrequesths together, each with its first byte. A byte
//   is taken at a rising edge of txbyteclkhs where txreadyhs is High (the values before the edge, as the
//   IP's flops see them), and the next byte follows; a lane drops its request with the edge that takes its
//   last byte. Then the task waits until every lane is back in stopstate, and gap_ns more.
// - ready0 = 1: every lane follows txreadyhs of lane 0 (the IP option C_USE_LANE0_TXREADYHS, "use TX data
//   lane 0 txreadyhs for all other data lanes").
// - corrupt_*: that byte goes to the TX inverted, for the negative test of the byte check of pad_truth; the
//   bytes the testbench records as expected stay the original ones.
// - log_bursts > 0: one "TB TXLOG" line per change of the PPI handshake until log_bursts bursts are done.
`timescale 1ns/1ps
module ppi_tx_drv #(
  parameter int NL = 4
) (
  input  logic               byteclk,
  output logic               cl_txrequesths,
  input  logic               cl_txclkactivehs,
  input  logic               cl_stopstate,
  output logic [NL-1:0]      txrequesths,
  input  logic [NL-1:0]      txreadyhs,
  output logic [NL-1:0][7:0] txdatahs,
  input  logic [NL-1:0]      stopstate
);
  typedef byte unsigned bq_t [$];

  // ---- knobs, set by the testbench ----
  real gap_ns        = 150.0;
  bit  ready0        = 1'b0;
  int  corrupt_lane  = -1;
  int  corrupt_burst = -1;
  int  corrupt_byte  = -1;
  int  log_bursts    = 0;

  // ---- results ----
  int  n_bursts       = 0;
  int  n_no_hs        = 0;      // lanes with bytes whose stopstate never fell during their burst
  real t_cl_request   = -1.0;
  real t_cl_running   = -1.0;
  bit  cl_active_seen = 1'b0;

  initial begin
    cl_txrequesths = 1'b0;
    txrequesths    = '0;
    txdatahs       = '0;
  end

  function automatic byte unsigned tx_byte(int id, int l, int i, byte unsigned b);
    return (id == corrupt_burst && l == corrupt_lane && i == corrupt_byte) ? b ^ 8'hFF : b;
  endfunction

  task automatic start_clock();
    @(posedge byteclk);
    cl_txrequesths <= 1'b1;
    t_cl_request    = $realtime;
    fork : p_wait
      begin
        wait (cl_txclkactivehs === 1'b1);
        cl_active_seen = 1'b1;
      end
      #50000;
    join_any
    disable p_wait;
    if (!cl_active_seen) wait (cl_stopstate === 1'b0);
    t_cl_running = $realtime;
    #2000;
  endtask

  task automatic burst(input int id, input bq_t bytes [NL]);
    int idx [NL];
    bit left_stop [NL];
    bit busy;
    @(posedge byteclk);
    for (int l = 0; l < NL; l++) begin
      idx[l]       = 0;
      left_stop[l] = 1'b0;
      if (bytes[l].size() > 0) begin
        txdatahs[l]    <= tx_byte(id, l, 0, bytes[l][0]);
        txrequesths[l] <= 1'b1;
      end
    end
    do begin
      @(posedge byteclk);
      busy = 1'b0;
      for (int l = 0; l < NL; l++) begin
        if (idx[l] >= bytes[l].size()) continue;
        if (stopstate[l] === 1'b0) left_stop[l] = 1'b1;
        if (txrequesths[l] === 1'b1 && (ready0 ? txreadyhs[0] : txreadyhs[l]) === 1'b1) begin
          idx[l]++;
          if (idx[l] == bytes[l].size()) txrequesths[l] <= 1'b0;
          else                           txdatahs[l]    <= tx_byte(id, l, idx[l], bytes[l][idx[l]]);
        end
        if (idx[l] < bytes[l].size()) busy = 1'b1;
      end
    end while (busy);
    // back in stop state (txbyteclkhs of the TX runs continuously); each lane with bytes must have left it
    while ((&stopstate) !== 1'b1) begin
      @(posedge byteclk);
      for (int l = 0; l < NL; l++)
        if (bytes[l].size() > 0 && stopstate[l] === 1'b0) left_stop[l] = 1'b1;
    end
    for (int l = 0; l < NL; l++)
      if (bytes[l].size() > 0 && !left_stop[l]) n_no_hs++;
    n_bursts++;
    #(gap_ns);
  endtask

  always @(cl_txrequesths, cl_txclkactivehs, cl_stopstate, txrequesths, txreadyhs, stopstate)
    if (log_bursts > 0 && n_bursts < log_bursts)
      $display("TB TXLOG %.3f ns: clock lane request %b active %b stop %b; data lanes request %b ready %b stop %b",
               $realtime, cl_txrequesths, cl_txclkactivehs, cl_stopstate, txrequesths, txreadyhs, stopstate);
endmodule
