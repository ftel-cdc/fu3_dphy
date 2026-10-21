// TN1 line generator (fpga/PLAN_TN1_TN3.md §1): a D-PHY v1.1 transmitter at the pads, testbench only.
// - The clock lane enters HS once (LP-11 -> LP-01 -> LP-00 -> HS-0) and then runs continuously; its edges
//   sit in the middle of the data bits (bit k spans [t0 + k*ui, t0 + (k+1)*ui), clock edge k at its
//   centre, rising for even k).
// - A burst on the data lanes: LP-11 -> LP-01 (TLPX) -> LP-00 (THS-PREPARE) -> HS-0 (THS-ZERO) -> sync 0xB8
//   -> payload, LSB first -> trail (inverse of the last bit, THS-TRAIL) -> LP-11 (THS-EXIT before the
//   next burst). All lanes start together; a lane may carry fewer bytes and then ends earlier.
// - Pads are logic levels: an LP state drives Dp/Dn, HS drives Dp = bit, Dn = ~bit. Each lane changes
//   {Dp, Dn} in one assignment, delayed by its skew (transport delay), so a receiver never sees half a
//   change.
// - hs_truth/cl_hs_truth: 1 from HS-0 to the end of the trail, with the lane skew; the AFE model's
//   inferred line state is checked against it.
// - EoT stress (fpga/PLAN_TN1_FIX.md): trail_jitter adds 0..trail_jitter random bits to the trail of each
//   lane and burst, so LP-11 falls at every phase of the byte clock; the last t_eot_junk ns of the trail
//   are random bits, the transition junk that the receiver must skip (THS-SKIP).
// The testbench sets the knobs (ns, skews in ps) before start_clock() and opens the truth file. Truth line
// per lane and burst: B <burst> <lane> <bytes> <first sync bit at the pad, ps> <end of the last payload
// bit, ps> <payload hex>.
`timescale 1ns/1ps
module dphy_line_gen #(
  parameter int NL = 4
) (
  output logic          clk_p,
  output logic          clk_n,
  output logic [NL-1:0] d_p,
  output logic [NL-1:0] d_n,
  output logic [NL-1:0] hs_truth,
  output logic          cl_hs_truth
);
  localparam logic [7:0] SYNC = 8'hB8;

  typedef byte unsigned bq_t [$];

  // ---- knobs, set by the testbench ----
  real ui            = 0.694;
  real t_lpx         = 75.0;
  real t_hs_prepare  = 62.0;
  real t_hs_zero     = 150.0;
  real t_hs_trail    = 80.0;
  real t_hs_exit     = 150.0;
  real t_clk_prepare = 66.0;
  real t_clk_zero    = 300.0;
  real skew_ps [NL];
  real clk_skew_ps   = 0.0;
  real t_eot_junk    = 0.0;
  int  trail_jitter  = 0;
  int  truth_fd      = 0;

  // ---- undelayed lane states {p, n} ----
  logic [1:0]    cl_i    = 2'b11;
  logic [1:0]    dl_i [NL];
  logic          cl_hs_i = 1'b0;
  logic [NL-1:0] hs_i    = '0;
  real           t0      = 0.0;
  bit            clk_on  = 1'b0;
  int            n_bursts = 0;

  initial begin
    foreach (dl_i[l]) dl_i[l] = 2'b11;
    foreach (skew_ps[l]) skew_ps[l] = 0.0;
    {clk_p, clk_n} = 2'b11;
    d_p            = '1;
    d_n            = '1;
    hs_truth       = '0;
    cl_hs_truth    = 1'b0;
  end

  // Transport delays to the pads: every change arrives skew later, both lines of a lane at once.
  always @(cl_i) {clk_p, clk_n} <= #(clk_skew_ps / 1000.0) cl_i;
  always @(cl_hs_i) cl_hs_truth <= #(clk_skew_ps / 1000.0) cl_hs_i;
  for (genvar l = 0; l < NL; l++) begin : g_lane
    always @(dl_i[l]) {d_p[l], d_n[l]} <= #(skew_ps[l] / 1000.0) dl_i[l];
    always @(hs_i[l]) hs_truth[l] <= #(skew_ps[l] / 1000.0) hs_i[l];
  end

  // Clock lane: HS request, bridge, HS-0, then a free-running DDR clock on the bit grid.
  task automatic start_clock();
    cl_i = 2'b01;
    #(t_lpx);
    cl_i = 2'b00;
    #(t_clk_prepare);
    cl_i    = 2'b01;
    cl_hs_i = 1'b1;
    #(t_clk_zero);
    t0     = $realtime;
    clk_on = 1'b1;
    fork
      clock_run();
    join_none
  endtask

  task automatic clock_run();
    longint k = 0;
    forever begin
      #(t0 + (real'(k) + 0.5) * ui - $realtime);
      cl_i = (k % 2 == 0) ? 2'b10 : 2'b01;
      k++;
    end
  endtask

  // One burst: bytes[l] is the payload of lane l; a lane with no bytes stays in LP-11.
  task automatic burst(input int id, input bq_t bytes [NL]);
    real    now_t, t_hs0;
    longint k_hs0, k0;
    int     zero_bits, trail_bits, total;
    int     nbits [NL];
    int     tbits [NL];
    int     jbits [NL];
    logic   last  [NL];
    bit     act   [NL];
    string  s;
    if (!clk_on) $fatal(1, "dphy_line_gen: burst() before start_clock()");
    now_t = $realtime;
    k_hs0 = longint'($ceil((now_t + t_lpx + t_hs_prepare - t0) / ui));
    t_hs0 = t0 + real'(k_hs0) * ui;
    foreach (bytes[l]) act[l] = (bytes[l].size() > 0);
    #(t_hs0 - t_hs_prepare - t_lpx - now_t);
    foreach (dl_i[l]) if (act[l]) dl_i[l] = 2'b01;                 // LP-01, HS request
    #(t_lpx);
    foreach (dl_i[l]) if (act[l]) dl_i[l] = 2'b00;                 // LP-00, bridge
    #(t_hs0 - $realtime);
    foreach (dl_i[l]) if (act[l]) begin                             // HS-0
      dl_i[l] = 2'b01;
      hs_i[l] = 1'b1;
    end
    zero_bits  = int'($ceil(t_hs_zero / ui));
    trail_bits = int'($ceil(t_hs_trail / ui));
    k0         = k_hs0 + zero_bits;
    total      = 0;
    foreach (bytes[l]) begin
      nbits[l] = act[l] ? 8 * (1 + bytes[l].size()) : 0;
      tbits[l] = trail_bits + ((trail_jitter > 0) ? int'($urandom_range(trail_jitter)) : 0);
      jbits[l] = (t_eot_junk > 0.0) ? int'($ceil(t_eot_junk / ui)) : 0;
      if (jbits[l] > tbits[l] - 1) jbits[l] = tbits[l] - 1;          // at least one trail bit
      if (act[l] && nbits[l] + tbits[l] + 1 > total) total = nbits[l] + tbits[l] + 1;
    end
    for (int b = 0; b < total; b++) begin
      #(t0 + real'(k0 + b) * ui - $realtime);
      foreach (dl_i[l]) begin
        if (!act[l]) continue;
        if (b < nbits[l]) begin
          logic v;
          v       = (b < 8) ? SYNC[b] : bytes[l][(b - 8) / 8][(b - 8) % 8];
          dl_i[l] = {v, ~v};
          last[l] = v;
        end else if (b < nbits[l] + tbits[l] - jbits[l]) begin
          dl_i[l] = {~last[l], last[l]};                              // trail
        end else if (b < nbits[l] + tbits[l]) begin
          logic v;
          v       = 1'($urandom_range(1));                            // junk before LP-11
          dl_i[l] = {v, ~v};
        end else if (b == nbits[l] + tbits[l]) begin
          dl_i[l] = 2'b11;                                            // LP-11
          hs_i[l] = 1'b0;
        end
      end
    end
    if (truth_fd != 0)
      foreach (bytes[l]) begin
        if (!act[l]) continue;
        s = "";
        for (int i = 0; i < bytes[l].size(); i++) s = {s, $sformatf("%02x", bytes[l][i])};
        $fdisplay(truth_fd, "B %0d %0d %0d %0d %0d %s", id, l, bytes[l].size(),
                  longint'((t0 + real'(k0) * ui) * 1000.0 + skew_ps[l]),
                  longint'((t0 + real'(k0 + nbits[l]) * ui) * 1000.0 + skew_ps[l]), s);
      end
    n_bursts++;
    #(t_hs_exit);
  endtask
endmodule
