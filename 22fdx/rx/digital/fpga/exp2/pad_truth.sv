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
// Description     : TN2a decoder of the pads (fpga/PLAN_TN2A.md §3.2), testbench only: truth file, byte check
//                   of the line against the bytes given to it, and timing of the line.
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
// TN2a decoder of the pads (fpga/PLAN_TN2A.md §3.2), testbench only and independent of both receivers. It
// reads the pads of the line, finds each HS burst of each data lane, decodes its bytes at the edges of the
// clock lane, and writes the truth file that fpga/tools/csi2_dump.py bursts compares the PPI captures with.
// - Line state per lane, from the pads (the rule of afe_model, written apart): LP-11 -> LP-01 (HS request) ->
//   LP-00 (bridge) -> the next differential state is HS-0; HS lasts until LP-11. The pads are read 1 ps after
//   a change, so a pair that changes in two steps counts as one change. Every change of the state is compared
//   with in_hs of afe_model 2 ps after it (state_diffs).
// - Bits: while the clock lane is in HS, Dp of each data lane in HS is read at both edges of the clock pad
//   (D-PHY puts the clock edges in the middle of the data bits). After HS-0, the first 8 bits that read 0xB8
//   (LSB first) are the sync byte; HS-0 is all zeros, so nothing before the sync byte can match.
// - Payload: the testbench gives each lane its bursts in order (expect()); a burst takes the next expected
//   entry of its lane, and its N bytes follow the sync byte. Every decoded byte must equal the expected byte
//   (mismatches). A burst with no expected entry (unexpected), an expected entry with no burst by the end
//   (missing), a burst without sync byte (no_sync) and a burst that ends before its N bytes (short) are errors.
//   The bits after the payload until LP-11 are the trail.
// - Truth line per lane and burst, as the line generator writes it: B <burst> <lane> <bytes> <start of the
//   sync byte, ps> <end of the last payload bit, ps> <decoded payload hex>. A bit spans half the measured
//   edge interval on each side of the edge that reads it.
// - Timing of the line, min and max over all lanes and bursts: TLPX, THS-PREPARE, THS-ZERO (HS-0 to the
//   sync byte), PREPARE + ZERO, THS-TRAIL (end of the payload to LP-11, the TEOT of D-PHY) and THS-EXIT
//   (LP-11 to the next LP-01) of the data lanes; TLPX, TCLK-PREPARE, TCLK-ZERO (HS-0 to the first clock
//   edge), PREPARE + ZERO and TCLK-PRE (first clock edge to the first LP-01 of a data lane) of the clock
//   lane. report() prints one "TB TXTIMING" line per item with the D-PHY v1.1 limits at the nominal UI, and
//   OUTSIDE when a value is outside them (report only), then one "TB PADS" line with the counts.
`timescale 1ns/1ps
module pad_truth #(
  parameter int NL = 4
) (
  input  logic          clk_p,
  input  logic          clk_n,
  input  logic [NL-1:0] d_p,
  input  logic [NL-1:0] d_n,
  input  logic [NL-1:0] afe_in_hs,
  input  logic          afe_cl_in_hs,
  output logic [NL-1:0] in_hs,
  output logic          cl_in_hs
);
  typedef enum logic [1:0] {S_LP, S_RQST, S_BRIDGE, S_HS} st_t;
  typedef byte unsigned bq_t [$];
  localparam logic [7:0] SYNC = 8'hB8;

  real ui       = 0.694;   // nominal UI, set by the testbench (for the limits)
  int  truth_fd = 0;

  // ---- counts ----
  int n_bursts = 0, n_bytes = 0, mismatches = 0, unexpected = 0, no_sync = 0, short_bursts = 0;
  int state_diffs = 0, trail_min = -1, trail_max = -1;

  // ---- expected bursts per lane, in order: id, length, bytes ----
  int           exp_id  [NL][$];
  int           exp_len [NL][$];
  byte unsigned exp_dat [NL][$];

  function automatic void expect_burst(input int id, input bq_t bytes [NL]);
    for (int l = 0; l < NL; l++) begin
      if (bytes[l].size() == 0) continue;
      exp_id[l].push_back(id);
      exp_len[l].push_back(bytes[l].size());
      foreach (bytes[l][i]) exp_dat[l].push_back(bytes[l][i]);
    end
  endfunction

  // ---- timing: min, max, count, limits (lo, hi; a negative limit is none) ----
  typedef enum int {T_LPX, T_PREP, T_ZERO, T_PZ, T_TRAIL, T_EXIT,
                    T_CLPX, T_CPREP, T_CZERO, T_CPZ, T_CPRE, T_N} tm_t;
  string tm_name [T_N] = '{"data TLPX", "data THS-PREPARE", "data THS-ZERO", "data THS-PREPARE + THS-ZERO",
                           "data THS-TRAIL", "data THS-EXIT", "clock TLPX", "clock TCLK-PREPARE",
                           "clock TCLK-ZERO", "clock TCLK-PREPARE + TCLK-ZERO", "clock TCLK-PRE"};
  real tm_min [T_N];
  real tm_max [T_N];
  int  tm_cnt [T_N];

  initial foreach (tm_cnt[k]) tm_cnt[k] = 0;

  function automatic void tm_add(tm_t k, real v);
    if (tm_cnt[k] == 0 || v < tm_min[k]) tm_min[k] = v;
    if (tm_cnt[k] == 0 || v > tm_max[k]) tm_max[k] = v;
    tm_cnt[k]++;
  endfunction

  function automatic void tm_limits(tm_t k, output real lo, output real hi);
    lo = -1.0;
    hi = -1.0;
    case (k)
      T_LPX, T_CLPX: lo = 50.0;
      T_PREP:        begin lo = 40.0 + 4.0 * ui; hi = 85.0 + 6.0 * ui; end
      T_PZ:          lo = 145.0 + 10.0 * ui;
      T_TRAIL:       begin lo = (8.0 * ui > 60.0 + 4.0 * ui) ? 8.0 * ui : 60.0 + 4.0 * ui; hi = 105.0 + 12.0 * ui; end
      T_EXIT:        lo = 100.0;
      T_CPREP:       begin lo = 38.0; hi = 95.0; end
      T_CPZ:         lo = 300.0;
      T_CPRE:        lo = 8.0 * ui;
      default: ;
    endcase
  endfunction

  function automatic st_t step(st_t s, logic [1:0] prev, logic [1:0] pn);
    case (s)
      S_LP:     return (prev == 2'b11 && pn == 2'b01) ? S_RQST : S_LP;
      S_RQST:   return (pn == 2'b00) ? S_BRIDGE : ((pn == 2'b01) ? S_RQST : S_LP);
      S_BRIDGE: return (pn == 2'b00) ? S_BRIDGE : ((pn == 2'b11) ? S_LP : S_HS);
      default:  return (pn == 2'b11) ? S_LP : S_HS;
    endcase
  endfunction

  // ------------------------------------------------------------------ clock lane
  st_t        cl_st          = S_LP;
  logic [1:0] cl_pn_s        = 2'b11;
  real        cl_t_lp01      = -1.0;
  real        cl_t_lp00      = -1.0;
  real        cl_t_hs0       = -1.0;
  real        cl_t_edge1     = -1.0;   // first clock edge after HS-0
  bit         first_lp01_set = 1'b0;   // TCLK-PRE taken at the first LP-01 of a data lane

  always @(clk_p, clk_n) begin : p_cl_line
    logic [1:0] pn;
    st_t        nx;
    real        t;
    #0.001;
    pn = {clk_p, clk_n};
    if (pn !== cl_pn_s) begin
      t  = $realtime - 0.001;
      nx = step(cl_st, cl_pn_s, pn);
      if (nx == S_RQST && cl_st != S_RQST) cl_t_lp01 = t;
      if (nx == S_BRIDGE && cl_st != S_BRIDGE) begin
        cl_t_lp00 = t;
        if (cl_t_lp01 >= 0.0) tm_add(T_CLPX, cl_t_lp00 - cl_t_lp01);
      end
      if (nx == S_HS && cl_st != S_HS) begin
        cl_t_hs0 = t;
        tm_add(T_CPREP, cl_t_hs0 - cl_t_lp00);
      end
      if (cl_st == S_HS && nx == S_HS && cl_t_edge1 < 0.0 && pn == 2'b10) begin
        cl_t_edge1 = t;
        tm_add(T_CZERO, cl_t_edge1 - cl_t_hs0);
        tm_add(T_CPZ, cl_t_edge1 - cl_t_lp00);
      end
      cl_st   = nx;
      cl_pn_s = pn;
    end
  end

  assign cl_in_hs = (cl_st == S_HS);

  // ------------------------------------------------------------------ data lanes
  for (genvar l = 0; l < NL; l++) begin : g_dl
    st_t          st       = S_LP;
    logic [1:0]   pn_s     = 2'b11;
    real          t_lp01   = -1.0;
    real          t_lp00   = -1.0;
    real          t_hs0    = -1.0;
    real          t_lp11   = -1.0;
    // decoding of the current burst
    logic [7:0]   sh       = '0;
    int           nseen    = 0;
    real          tq [8];             // times of the last 8 bits read
    bit           synced   = 1'b0;
    bit           have_exp = 1'b0;
    int           cur_id   = -1;
    int           cur_len  = 0;
    bq_t          cur_exp;
    bq_t          got;
    logic [7:0]   cur_byte = '0;
    int           bitpos   = 0;
    real          ui_m     = 0.0;     // measured bit period of this burst
    real          t0       = 0.0;
    real          t1       = -1.0;
    int           trail_bits = 0;

    always @(d_p[l], d_n[l]) begin : p_line
      logic [1:0] pn;
      st_t        nx;
      real        t;
      #0.001;
      pn = {d_p[l], d_n[l]};
      if (pn !== pn_s) begin
        t  = $realtime - 0.001;
        nx = step(st, pn_s, pn);
        if (nx == S_RQST && st != S_RQST) begin
          if (t_lp11 >= 0.0) tm_add(T_EXIT, t - t_lp11);
          t_lp01 = t;
          if (!first_lp01_set && cl_t_edge1 >= 0.0) begin
            first_lp01_set = 1'b1;
            tm_add(T_CPRE, t - cl_t_edge1);
          end
        end
        if (nx == S_BRIDGE && st != S_BRIDGE) begin
          t_lp00 = t;
          tm_add(T_LPX, t_lp00 - t_lp01);
        end
        if (nx == S_HS && st != S_HS) begin
          t_hs0      = t;
          sh         = '0;
          nseen      = 0;
          synced     = 1'b0;
          have_exp   = 1'b0;
          got        = {};
          bitpos     = 0;
          t1         = -1.0;
          trail_bits = 0;
          tm_add(T_PREP, t_hs0 - t_lp00);
        end
        if (st == S_HS && nx == S_LP) begin
          t_lp11 = t;
          end_burst();
        end
        st   = nx;
        pn_s = pn;
      end
    end

    // One bit of an HS burst at each edge of the clock pad while the clock lane is in HS.
    always @(clk_p) if (cl_st == S_HS && st == S_HS) begin : p_bit
      logic b;
      real  te;
      b  = d_p[l];
      te = $realtime;
      if (!synced) begin
        for (int i = 0; i < 7; i++) tq[i] = tq[i + 1];
        tq[7] = te;
        sh    = {b, sh[7:1]};
        nseen++;
        if (nseen >= 8 && sh == SYNC) begin
          synced = 1'b1;
          ui_m   = (tq[7] - tq[0]) / 7.0;
          t0     = tq[0] - ui_m / 2.0;
          tm_add(T_ZERO, t0 - t_hs0);
          tm_add(T_PZ, t0 - t_lp00);
          if (exp_id[l].size() > 0) begin
            have_exp = 1'b1;
            cur_id   = exp_id[l].pop_front();
            cur_len  = exp_len[l].pop_front();
            cur_exp  = {};
            for (int i = 0; i < cur_len; i++) cur_exp.push_back(exp_dat[l].pop_front());
          end else begin
            unexpected++;
            $display("TB PADS UNEXPECTED: lane %0d, burst at %.3f ns with no expected entry", l, t_hs0);
          end
        end
      end else if (have_exp && got.size() < cur_len) begin
        cur_byte[bitpos] = b;
        bitpos++;
        if (bitpos == 8) begin
          got.push_back(cur_byte);
          bitpos = 0;
          if (got.size() == cur_len) t1 = te + ui_m / 2.0;
        end
      end else begin
        trail_bits++;
      end
    end

    function automatic void end_burst();
      string s;
      if (!synced) begin
        no_sync++;
        $display("TB PADS NO SYNC: lane %0d, HS burst %.3f .. %.3f ns", l, t_hs0, t_lp11);
        return;
      end
      if (!have_exp) return;
      n_bursts++;
      if (got.size() < cur_len) begin
        short_bursts++;
        $display("TB PADS SHORT: lane %0d burst %0d, %0d of %0d bytes before LP-11", l, cur_id, got.size(), cur_len);
        return;
      end
      for (int i = 0; i < cur_len; i++)
        if (got[i] !== cur_exp[i]) begin
          if (mismatches < 8)
            $display("TB PADS MISMATCH: lane %0d burst %0d byte %0d: %02x at the pads, %02x expected", l, cur_id, i,
                     got[i], cur_exp[i]);
          mismatches++;
        end
      n_bytes += cur_len;
      tm_add(T_TRAIL, t_lp11 - t1);
      if (trail_min < 0 || trail_bits < trail_min) trail_min = trail_bits;
      if (trail_bits > trail_max) trail_max = trail_bits;
      if (truth_fd != 0) begin
        s = "";
        foreach (got[i]) s = {s, $sformatf("%02x", got[i])};
        $fdisplay(truth_fd, "B %0d %0d %0d %0d %0d %s", cur_id, l, cur_len, longint'(t0 * 1000.0),
                  longint'(t1 * 1000.0), s);
      end
    endfunction

    assign in_hs[l] = (st == S_HS);

    always @(in_hs[l], afe_in_hs[l]) begin : p_state_chk
      #0.002;
      if (in_hs[l] !== afe_in_hs[l]) state_diffs++;
    end
  end

  always @(cl_in_hs, afe_cl_in_hs) begin : p_cl_state_chk
    #0.002;
    if (cl_in_hs !== afe_cl_in_hs) state_diffs++;
  end

  function automatic int missing();
    int m = 0;
    for (int l = 0; l < NL; l++) m += exp_id[l].size();
    return m;
  endfunction

  function automatic void report();
    real lo, hi;
    string lim;
    for (int k = 0; k < int'(T_N); k++) begin
      tm_limits(tm_t'(k), lo, hi);
      lim = (lo < 0.0 && hi < 0.0) ? "none" :
            ((hi < 0.0) ? $sformatf(">= %.3f", lo) : ((lo < 0.0) ? $sformatf("<= %.3f", hi) :
                                                     $sformatf("%.3f .. %.3f", lo, hi)));
      if (tm_cnt[k] == 0)
        $display("TB TXTIMING %s: not seen (limit %s)", tm_name[k], lim);
      else
        $display("TB TXTIMING %s: min %.3f max %.3f ns over %0d (limit %s)%s", tm_name[k], tm_min[k], tm_max[k],
                 tm_cnt[k], lim,   // string'(): ?: on two text literals pads the shorter one with spaces
                 ((lo >= 0.0 && tm_min[k] < lo) || (hi >= 0.0 && tm_max[k] > hi)) ? string'(" OUTSIDE") : string'(""));
    end
    $display("TB PADS: %0d bursts decoded, %0d payload bytes, mismatches %0d, unexpected %0d, missing %0d, without sync %0d, short %0d, line-state differences with afe_model %0d, trail bits %0d..%0d",
             n_bursts, n_bytes, mismatches, unexpected, missing(), no_sync, short_bursts, state_diffs, trail_min,
             trail_max);
  endfunction
endmodule
