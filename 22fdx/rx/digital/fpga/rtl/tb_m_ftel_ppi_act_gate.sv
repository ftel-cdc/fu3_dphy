//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-26
// Description     : Unit testbench of m_ftel_ppi_act_gate (fpga/PLAN_TN2B_GATE.md §3).
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-26   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
// Unit testbench of m_ftel_ppi_act_gate (fpga/PLAN_TN2B_GATE.md §3), NL lanes (+define+NL=<n>, default 4).
// Two checks, written apart from the RTL:
// - cycle by cycle, against a model with its own copy of the two-stage reset release;
// - at the end of each burst (run of rxactivehs in) without a reset in it, the property the block stands for:
//   rxactivehs out rises in the cycle of the first rxsynchs of the burst and stays High to its end; a burst
//   without rxsynchs gives none.
// Stimulus: a directed part on lane 0 (rxsynchs with the first byte and later, none, two bursts one cycle apart,
// reset after the sync, byte clock stopped in a burst), then random bursts on every lane (gaps of 1 to 20 cycles,
// rxsynchs from 0 to 25 cycles into the burst, wider than one cycle, or none), with resets and stops of the byte
// clock at random times. Every case of the coverage counts must be hit. Prints "TB RESULT: PASS" or FAIL.
//   +SEED=<n> (default 1)  +BURSTS=<n> random bursts per lane (default 3000)
`timescale 1ns/1ps
module tb_m_ftel_ppi_act_gate;
`ifndef NL
  `define NL 4
`endif
  localparam int NL = `NL;

  logic          clk = 1'b0, clk_en = 1'b1, rst_n = 1'b0;
  logic [NL-1:0] act = '0, sync = '0;
  wire  [NL-1:0] out;

  always #2.5 if (clk_en) clk = ~clk;   // byte clock; its edges stay on the 2.5 ns grid when it stops and runs again

  m_ftel_ppi_act_gate #(.PARA_NUM_LANES(NL)) dut (
    .i_byte_clk   (clk),
    .i_byte_rst_n (rst_n),
    .i_rxactivehs (act),
    .i_rxsynchs   (sync),
    .o_rxactivehs (out)
  );

  // ------------------------------------------------------------------ model, cycle by cycle
  logic [1:0]    m_rel = '0;           // release of the reset, two flip-flops
  logic [NL-1:0] m_seen = '0;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) m_rel <= '0;
    else        m_rel <= {m_rel[0], 1'b1};
  always @(posedge clk or negedge m_rel[1])
    if (!m_rel[1]) m_seen <= '0;
    else           m_seen <= act & (sync | m_seen);
  wire [NL-1:0] m_out = act & (sync | m_seen);

  int n_cmp = 0, n_diff = 0;
  initial begin : p_cmp
    #0.25;
    forever begin   // between the edges (x.0, x.5) and the input changes (edge + 0.1)
      n_cmp++;
      if (out !== m_out) begin
        n_diff++;
        if (n_diff <= 5) $display("TB DIFF at %.2f ns: out %b, model %b (act %b, sync %b)", $realtime, out, m_out,
                                  act, sync);
      end
      #0.5;
    end
  end

  // ------------------------------------------------------------------ property at the end of each burst
  int  cyc = 0;
  int  b_start [NL], b_sync [NL], b_rise [NL], b_idle [NL];
  bit  b_in [NL], b_drop [NL], b_rst [NL];
  int  n_bursts = 0, n_checked = 0, n_prop = 0;
  // coverage
  int  c_sync0 = 0, c_sync_later = 0, c_none = 0, c_gap1 = 0, c_wide = 0, c_rst_mid = 0, c_stop_mid = 0;
  int  b_width [NL];

  initial foreach (b_in[l]) begin
    b_in[l] = 0; b_idle[l] = 100; b_rst[l] = 0;
  end

  always @(posedge clk) begin : p_prop   // the values of the cycle that ends at this edge
    cyc++;
    for (int l = 0; l < NL; l++) begin
      if (act[l] && !b_in[l]) begin
        b_in[l] = 1; b_start[l] = cyc; b_sync[l] = -1; b_rise[l] = -1; b_drop[l] = 0; b_width[l] = 0;
        b_rst[l] = !m_rel[1];
        c_gap1 += b_idle[l] == 1;
      end
      if (b_in[l] && act[l]) begin
        if (!m_rel[1]) b_rst[l] = 1;
        if (sync[l]) begin
          if (b_sync[l] < 0) b_sync[l] = cyc;
          b_width[l]++;
        end
        if (out[l] && b_rise[l] < 0) b_rise[l] = cyc;
        if (!out[l] && b_rise[l] >= 0) b_drop[l] = 1;
      end
      if (!act[l] && b_in[l]) begin
        b_in[l] = 0;
        n_bursts++;
        if (!b_rst[l]) begin
          n_checked++;
          if (b_sync[l] < 0) c_none++;
          else if (b_sync[l] == b_start[l]) c_sync0++;
          else c_sync_later++;
          c_wide += b_width[l] > 1;
          if (b_rise[l] != b_sync[l] || b_drop[l]) begin
            n_prop++;
            if (n_prop <= 5) $display("TB PROPERTY: lane %0d burst from cycle %0d: first rxsynchs %0d, out from %0d%s",
                                      l, b_start[l], b_sync[l], b_rise[l], b_drop[l] ? ", Low again in the burst" : "");
          end
        end
      end
      b_idle[l] = act[l] ? 0 : b_idle[l] + 1;
    end
  end

  // ------------------------------------------------------------------ stimulus
  // The inputs change 0.1 ns after an edge of the byte clock, as from flip-flops of ftel_dphy_rx.
  task automatic cycle(int l, bit a, bit s);
    @(posedge clk);
    #0.1;
    act[l]  = a;
    sync[l] = s;
  endtask

  task automatic burst(int l, int gap, int len, int at, int width);   // at < 0: no rxsynchs
    repeat (gap) cycle(l, 0, 0);
    for (int k = 0; k < len; k++) cycle(l, 1, at >= 0 && k >= at && k < at + width);
  endtask

  task automatic reset_pulse(real width);
    c_rst_mid += act != '0;
    rst_n = 1'b0;
    #(width);
    rst_n = 1'b1;
  endtask

  task automatic stop_clock(real width);
    c_stop_mid += act != '0;
    clk_en = 1'b0;
    #(width);
    clk_en = 1'b1;
  endtask

  int seed = 1, n_rand = 3000;
  initial begin : p_main
    void'($value$plusargs("SEED=%d", seed));
    void'($value$plusargs("BURSTS=%d", n_rand));
    void'($urandom(seed));
    #20.3 rst_n = 1'b1;
    repeat (4) @(posedge clk);
    // directed, lane 0
    burst(0, 5, 10, 0, 1);       // rxsynchs with the first byte
    burst(0, 5, 20, 7, 1);       // rxsynchs 7 cycles in
    burst(0, 5, 12, -1, 1);      // no rxsynchs (SoT sync error)
    burst(0, 5, 9, 3, 1);
    burst(0, 1, 9, 4, 1);        // one Low cycle, then a burst whose rxsynchs comes later
    burst(0, 5, 8, 2, 3);        // rxsynchs three cycles wide
    fork
      burst(0, 5, 30, 2, 1);
      begin repeat (15) @(posedge clk); #0.3; reset_pulse(7.0); end     // reset after the rxsynchs
    join
    fork
      burst(0, 5, 30, 4, 1);
      begin repeat (12) @(posedge clk); #1.3; stop_clock(43.0); end     // byte clock stopped in the burst
    join
    // random, every lane; the processes are children of this one, so that wait fork waits for them
    for (int l = 0; l < NL; l++)
      fork
        automatic int ll = l;
        for (int b = 0; b < n_rand; b++) begin
          automatic int gap, len, at, width, kind;
          gap   = ($urandom_range(0, 9) == 0) ? 1 : $urandom_range(2, 20);
          len   = $urandom_range(1, 40);
          kind  = $urandom_range(0, 9);
          at    = kind == 0 ? -1 : (kind == 1 ? 0 : $urandom_range(0, 25));
          width = kind == 2 ? $urandom_range(2, 3) : 1;
          burst(ll, gap, len, at, width);
        end
      join_none
    fork
      repeat (40) begin
        #($urandom_range(500, 4000) + 0.3);
        if ($urandom_range(0, 1)) reset_pulse($urandom_range(3, 40));
        else                      stop_clock($urandom_range(5, 200));
      end
    join_none
    wait fork;
    repeat (30) cycle(0, 0, 0);
    begin   // automatic: computed here, not when the simulation starts
      automatic bit cov = c_sync0 > 0 && c_sync_later > 0 && c_none > 0 && c_gap1 > 0 && c_wide > 0 &&
                          c_rst_mid > 0 && c_stop_mid > 0;
      automatic bit ok  = n_diff == 0 && n_prop == 0 && n_cmp > 0 && n_checked > 0 && cov;
      $display("TB NL %0d: %0d comparisons with the model, %0d different; %0d bursts, %0d checked at their end, %0d against the property",
               NL, n_cmp, n_diff, n_bursts, n_checked, n_prop);
      $display("TB COVERAGE: rxsynchs with the first byte %0d, later %0d, none %0d; one Low cycle before %0d; wider than a cycle %0d; reset in a burst %0d; byte clock stopped in a burst %0d",
               c_sync0, c_sync_later, c_none, c_gap1, c_wide, c_rst_mid, c_stop_mid);
      $display("TB RESULT: %s", ok ? "PASS" : "FAIL");
    end
    $finish;
  end
endmodule
