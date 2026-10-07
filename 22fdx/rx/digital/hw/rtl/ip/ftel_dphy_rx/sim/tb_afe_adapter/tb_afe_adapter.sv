//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-10-07
// Module          : tb_afe_adapter
// Description     : Directed self-checking testbench of Block No. 1 through the core
//                   m_ftel_dphy_rx (HAS v0.14 §4.3): samplers and 1:8 deserializer, word
//                   latency, byte clock and its gate, clock activity. Not the unit TB of M3.
//                   One line rate per run: +RATE=<Mb/s>. See run.sh.
//
// Checks per clock-lane burst (4 bursts of 64..67 DDR periods, so the divider stops at every
// phase; pulses at the HS-RX output during TCLK-SETTLE and after the trail):
//   W1  every word of the HS path is 8 consecutive bits of the lane, bit 0 received first, and
//       consecutive words follow each other (offset + 8)
//   W2  the words of all lanes are cut at the same time; polarity inversion of lanes 1 and 3
//   L1  word latency from the end of the last bit at the line to the HS path register
//       (Λ, HAS §5.2): 8.25 DDR periods = 2.0625 byte clocks in zero-delay RTL
//   B1  rxbyteclkhs rises only while cl_rxclkactivehs is High (CL_HS_CLK), never on a pulse at
//       the HS-RX output while the clock lane starts or leaves HS (REQ-344)
//   B2  every period 4 DDR periods, every high phase whole: 2 DDR periods (the last one may be
//       longer when the clock stops in the high half); Low once the gate is closed (REQ-364)
//   B3  first rxbyteclkhs edge 3..4 DDR periods after cl_rxclkactivehs rises (REQ-343)
//   A1  no loss of clock activity while the DDR clock runs (both toggles, REQ-347)
//   A2  loss seen 45-50 ns after the last toggle change core_clk sees (the last rising DDR edge,
//       or up to 3 DDR periods before it when the edge toggle aliases), cl_rxclkactivehs 5 ns
//       later (zero-delay RTL: no late synchronizer), within TCLK-MISS = 60 ns (REQ-346, REQ-319)
//------------------------------------------------------------------------------
`timescale 1ns/1ps
module tb_afe_adapter;
  import ftel_dphy_rx_pkg::*;
  import ftel_dphy_rx_config_pkg::*;

  localparam int  N         = 4;
  localparam int  W         = 8;
  localparam real CORE_HALF = 2.5;
  localparam real TOL       = 0.002;     // ns: time comparisons in a ps-resolution simulation

  // ------------------------------------------------------------------ stimulus
  logic                 core_clk     = 1'b0;
  logic                 phy_core_rst = 1'b1;
  logic                 ddr_clk      = 1'b0;
  logic [N-1:0]         hs_bit       = '0;
  logic                 cl_dp        = 1'b1;
  logic                 cl_dn        = 1'b1;
  cfg_timing_t          cfg;
  logic [N-1:0][1:0]    lane_map     = {2'd3, 2'd2, 2'd1, 2'd0};
  logic [N-1:0]         lane_pol     = 4'b1010;

  logic                 rxbyteclkhs;
  logic                 cl_rxclkactivehs;

  real    rate_mbps, ui, tddr, tbyte;
  int     errors = 0;

  always #(CORE_HALF) core_clk = ~core_clk;

  initial begin
    cfg                   = '0;
    cfg.hs_settle_cyc     = C_HS_SETTLE_CYC_RST;
    cfg.clk_settle_cyc    = C_CLK_SETTLE_CYC_RST;
    cfg.tinit_cyc         = 100;
    cfg.hs_rx_timeout_cyc = C_HS_RX_TIMEOUT_CYC_RST;
    cfg.esc_timeout_cyc   = C_ESC_TIMEOUT_CYC_RST;
    cfg.eot_skip_bytes    = C_EOT_SKIP_BYTES_RST;
  end

  m_ftel_dphy_rx #(
    .PARA_NUM_LANES (N)
  ) u_dut (
    .i_core_clk              (core_clk),
    .i_phy_core_rst          (phy_core_rst),
    .i_cl_enable             (1'b1),
    .i_dl_enable             ({N{1'b1}}),
    .i_forcerxmode           ({N{1'b0}}),
    .o_init_done             (),
    .o_cl_stopstate          (),
    .o_stopstate             (),
    .o_cl_ulpsactivenot      (),
    .o_ulpsactivenot         (),
    .o_rxbyteclkhs           (rxbyteclkhs),
    .o_cl_rxclkactivehs      (cl_rxclkactivehs),
    .o_cl_ulpsclknot         (),
    .o_rxdatahs              (),
    .o_rxvalidhs             (),
    .o_rxactivehs            (),
    .o_rxsynchs              (),
    .o_rxskewcalhs           (),
    .o_rxclkesc              (),
    .o_rxlpdtesc             (),
    .o_rxulpsesc             (),
    .o_rxtriggeresc          (),
    .o_rxdataesc             (),
    .o_rxvalidesc            (),
    .o_errsoths              (),
    .o_errsotsynchs          (),
    .o_erresc                (),
    .o_errsyncesc            (),
    .o_errcontrol            (),
    .o_sts_cl_state          (),
    .o_sts_dl_state          (),
    .o_sts_cl_abort_tgl      (),
    .o_sts_errsoths_tgl      (),
    .o_sts_errsotsynchs_tgl  (),
    .o_sts_erreotsync_tgl    (),
    .o_sts_hs_rx_timeout_tgl (),
    .o_sts_erresc_tgl        (),
    .o_sts_esc_timeout_tgl   (),
    .i_afe_lp_dp             ({N{1'b1}}),
    .i_afe_lp_dn             ({N{1'b1}}),
    .i_afe_cl_lp_dp          (cl_dp),
    .i_afe_cl_lp_dn          (cl_dn),
    .i_afe_cl_hs_clk         (ddr_clk),
    .i_afe_hs_bit            (hs_bit),
    .o_afe_hs_en             (),
    .o_afe_term_en           (),
    .o_afe_cl_hs_en          (),
    .o_afe_cl_term_en        (),
    .o_afe_dly_tap           (),
    .i_cfg_timing            (cfg),
    .i_cfg_lane_map          (lane_map),
    .i_cfg_lane_pol          (lane_pol)
  );

  // ------------------------------------------------------------------ bit streams
  // PRBS31 on lanes 0 and 2; lane 1 repeats lane 0 and lane 3 inverts lane 2, so with the
  // polarity bits 4'b1010 word 1 = ~word 0 and word 3 = word 2.
  logic [30:0] lfsr0 = 31'h1234_5678;
  logic [30:0] lfsr2 = 31'h0ACE_1357;

  function automatic logic prbs(ref logic [30:0] s);
    logic b;
    b = s[30] ^ s[27];
    s = {s[29:0], b};
    return b;
  endfunction

  logic bits [N][$];     // bits of the current burst, per lane, in the order sent
  real  edge_t [$];      // DDR clock edge at the centre of each bit

  task automatic run_clock(input int nperiods);
    logic b0, b2;
    for (int k = 0; k < 2 * nperiods; k++) begin
      b0 = prbs(lfsr0);
      b2 = prbs(lfsr2);
      hs_bit = {~b2, b2, b0, b0};
      bits[0].push_back(b0);
      bits[1].push_back(b0);
      bits[2].push_back(b2);
      bits[3].push_back(~b2);
      #(ui / 2);
      ddr_clk = ~ddr_clk;             // edge k in the centre of bit k: rising for even k
      edge_t.push_back($realtime);
      #(ui / 2);
    end
  endtask

  // Pulses at the HS-RX output of the clock lane while it starts or leaves HS.
  task automatic garbage(input int n);
    repeat (n) begin
      #(7.3);
      ddr_clk = 1'b1;
      #(0.35);
      ddr_clk = 1'b0;
    end
  endtask

  // ------------------------------------------------------------------ monitors
  real bclk_rise [$];
  real bclk_fall [$];
  real act_rise_t, act_fall_t, ca_fall_t;
  real ca_falls [$];
  real word_t [$];
  logic [N-1:0][W-1:0] word_v [$];

  always @(posedge rxbyteclkhs) bclk_rise.push_back($realtime);
  always @(negedge rxbyteclkhs) bclk_fall.push_back($realtime);
  always @(posedge cl_rxclkactivehs) act_rise_t = $realtime;
  always @(negedge cl_rxclkactivehs) act_fall_t = $realtime;
  always @(negedge u_dut.u_afe_adapter_0.o_cl_clk_active) ca_falls.push_back($realtime);

  // HS path register, read just after the byte-clock edge that loads it.
  always @(posedge rxbyteclkhs) begin
    real t;
    t = $realtime;
    #0.001;
    word_t.push_back(t);
    word_v.push_back(u_dut.u_afe_adapter_0.o_hs_word);
  end

  function automatic void err(input string msg);
    errors++;
    $display("ERROR %0t: %s", $time, msg);
  endfunction

  // ------------------------------------------------------------------ one clock-lane burst
  task automatic burst(input int nperiods);
    real t_lp00, t_first, t_last_rise, t_last, t_start;
    int  r0, f0, w0, nrise, matched, m_prev;
    real lam, lam_min, lam_max;

    bclk_rise.delete();
    bclk_fall.delete();
    ca_falls.delete();
    word_t.delete();
    word_v.delete();
    act_rise_t = -1.0;
    act_fall_t = -1.0;
    t_start    = $realtime;

    // LP-11 -> LP-01 (TLPX) -> LP-00: TCLK-PREPARE + TCLK-ZERO, with pulses at the HS-RX output
    {cl_dp, cl_dn} = 2'b01;
    #60;
    {cl_dp, cl_dn} = 2'b00;
    t_lp00 = $realtime;
    #20;
    garbage(3);
    #(t_lp00 + 320.0 - $realtime);

    // HS clock with data on the data lanes
    for (int l = 0; l < N; l++) bits[l].delete();
    edge_t.delete();
    run_clock(nperiods);
    t_first     = edge_t[0];
    t_last      = edge_t[edge_t.size() - 1];
    t_last_rise = edge_t[edge_t.size() - 2];

    // trail (HS-0), pulses at the HS-RX output once the loss is detected, then LP-11
    #(70.0 + t_last - $realtime);
    garbage(2);
    #(t_last + 120.0 - $realtime);
    {cl_dp, cl_dn} = 2'b11;
    #300;

    // ---- B1, B3: rxbyteclkhs only in CL_HS_CLK, start 3..4 DDR periods after it
    if (act_rise_t < 0.0 || act_fall_t < act_rise_t) begin
      err($sformatf("cl_rxclkactivehs did not pulse (rise %.3f, fall %.3f)", act_rise_t, act_fall_t));
      return;
    end
    nrise = bclk_rise.size();
    if (nrise < 8) err($sformatf("only %0d rxbyteclkhs edges", nrise));
    foreach (bclk_rise[i])
      if (bclk_rise[i] < act_rise_t || bclk_rise[i] > act_fall_t)
        err($sformatf("B1: rxbyteclkhs rises at %.3f outside CL_HS_CLK [%.3f, %.3f]",
                      bclk_rise[i], act_rise_t, act_fall_t));
    if (nrise > 0) begin
      real d;
      d = bclk_rise[0] - act_rise_t;
      if (d < 3.0 * tddr - TOL || d > 4.0 * tddr + TOL)
        err($sformatf("B3: first rxbyteclkhs edge %.3f ns = %.2f DDR periods after cl_rxclkactivehs",
                      d, d / tddr));
      $display("  B3 start: %.3f ns = %.2f DDR periods = %.3f byte clocks after cl_rxclkactivehs",
               d, d / tddr, d / tbyte);
    end

    // ---- B2: whole pulses, period 4 DDR periods, Low once the gate is closed
    for (int i = 0; i + 1 < nrise; i++)
      if ((bclk_rise[i + 1] - bclk_rise[i]) < tbyte - TOL || (bclk_rise[i + 1] - bclk_rise[i]) > tbyte + TOL)
        err($sformatf("B2: rxbyteclkhs period %.3f at %.3f", bclk_rise[i + 1] - bclk_rise[i], bclk_rise[i]));
    if (bclk_fall.size() != nrise)
      err($sformatf("B2: %0d rises, %0d falls", nrise, bclk_fall.size()));
    else
      for (int i = 0; i < nrise; i++) begin
        real hi;
        hi = bclk_fall[i] - bclk_rise[i];
        if (hi < tbyte / 2.0 - TOL || (i < nrise - 1 && hi > tbyte / 2.0 + TOL))
          err($sformatf("B2: high phase %.3f ns at %.3f", hi, bclk_rise[i]));
      end
    if (rxbyteclkhs !== 1'b0) err("B2: rxbyteclkhs not Low after the gate closed");
    if (nrise > 0)
      $display("  B2 stop: last high phase %.3f ns (%s half of the divided clock when the clock stopped)",
               bclk_fall[nrise - 1] - bclk_rise[nrise - 1],
               (bclk_fall[nrise - 1] - bclk_rise[nrise - 1] > tbyte / 2.0 + TOL) ? "high" : "low");

    // ---- A1, A2: clock activity
    foreach (ca_falls[i])
      if (ca_falls[i] > t_first + 60.0 && ca_falls[i] < t_last)
        err($sformatf("A1: clock activity lost at %.3f while the clock runs", ca_falls[i]));
    ca_fall_t = -1.0;
    foreach (ca_falls[i])
      if (ca_falls[i] >= t_last && ca_fall_t < 0.0) ca_fall_t = ca_falls[i];
    if (ca_fall_t < 0.0) err("A2: clock activity never lost");
    else begin
      real a, b;
      a = ca_fall_t - t_last_rise;
      b = act_fall_t - t_last_rise;
      // 45-50 ns after the last toggle change core_clk sees; when the edge toggle aliases, that
      // change can be the last one of the slow toggle, up to 3 DDR periods before the last edge.
      if (a < 45.0 - 3.0 * tddr - TOL || a > 50.0 + TOL)
        err($sformatf("A2: loss seen %.3f ns after the last rising edge", a));
      if (b < 50.0 - 3.0 * tddr - TOL || b > 55.0 + TOL || act_fall_t - t_last > 60.0)
        err($sformatf("A2: cl_rxclkactivehs falls %.3f ns after the last rising edge", b));
      $display("  A2 loss: seen %.3f ns, cl_rxclkactivehs %.3f ns after the last rising edge (%.3f ns after the last edge)",
               a, b, act_fall_t - t_last);
    end

    // ---- W1, W2, L1: words of the HS path register
    matched = 0;
    m_prev  = -1;
    lam_min = 1.0e9;
    lam_max = -1.0e9;
    foreach (word_t[j]) begin
      int m;
      m = -1;
      for (int c = 0; c + W <= bits[0].size(); c += 2) begin
        logic ok;
        real l0;
        ok = 1'b1;
        for (int i = 0; i < W; i++) if (word_v[j][0][i] !== bits[0][c + i]) ok = 1'b0;
        if (!ok) continue;
        l0 = (word_t[j] - (edge_t[c + W - 1] + ui / 2.0)) / tbyte;
        if (l0 > 1.9 && l0 < 2.25) begin     // one even offset only: offsets differ by 0.25
          m = c;
          break;
        end
      end
      if (m < 0) begin
        if (m_prev >= 0) err($sformatf("W1: word %0d at %.3f matches no 8 consecutive bits after the last match", j, word_t[j]));
        continue;
      end
      if (m_prev >= 0 && m != m_prev + W)
        err($sformatf("W1: word at %.3f starts at bit %0d, previous at %0d", word_t[j], m, m_prev));
      m_prev = m;
      matched++;
      lam = (word_t[j] - (edge_t[m + W - 1] + ui / 2.0)) / tbyte;
      if (lam < lam_min) lam_min = lam;
      if (lam > lam_max) lam_max = lam;
      if (lam < 2.0625 - 0.001 || lam > 2.0625 + 0.001)
        err($sformatf("L1: word latency %.4f byte clocks at %.3f", lam, word_t[j]));
      if (word_v[j][1] !== ~word_v[j][0]) err($sformatf("W2: lane 1 word %h is not ~%h", word_v[j][1], word_v[j][0]));
      for (int i = 0; i < W; i++)
        if (word_v[j][2][i] !== bits[2][m + i]) begin
          err($sformatf("W2: lane 2 word at %.3f not cut at bit %0d", word_t[j], m));
          break;
        end
      if (word_v[j][3] !== word_v[j][2]) err($sformatf("W2: lane 3 word %h differs from lane 2 %h", word_v[j][3], word_v[j][2]));
    end
    // The first two words after the gate opens are older ones: the load phase starts with the
    // divider, after the first byte-clock edge.
    if (matched < nrise - 2 || nrise < (2 * nperiods) / W - 6)
      err($sformatf("W1: %0d words matched of %0d rxbyteclkhs edges", matched, nrise));
    $display("  W/L: %0d words checked, Λ %.4f .. %.4f byte clocks (%.2f DDR periods)",
             matched, lam_min, lam_max, lam_min * 4.0);
    $display("burst %0d periods: %0d rxbyteclkhs edges, errors so far %0d", nperiods, nrise, errors);
  endtask

  // ------------------------------------------------------------------ sequence
  initial begin
    if (!$value$plusargs("RATE=%f", rate_mbps)) rate_mbps = 800.0;
    // Half a UI rounded to the 1 ps resolution, so the clock the TB makes and the periods the
    // checks expect are the same.
    ui    = 2.0 * (real'($rtoi(1000.0 / rate_mbps * 500.0 + 0.5)) / 1000.0);
    tddr  = 2.0 * ui;
    tbyte = 4.0 * tddr;
    $display("tb_afe_adapter: %.0f Mb/s (%.2f Mb/s after rounding), UI %.4f ns, DDR period %.4f ns, byte clock %.4f ns",
             rate_mbps, 1000.0 / ui, ui, tddr, tbyte);
    #300.3;
    phy_core_rst = 1'b0;
    #2000;
    for (int b = 0; b < 4; b++) burst(64 + b);
    $display("TB RESULT: %s (%0d errors) at %.0f Mb/s", errors == 0 ? "PASS" : "FAIL", errors, rate_mbps);
    $finish;
  end
endmodule
