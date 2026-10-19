// TN1/TN2 AFE model (fpga/PLAN_TN1_TN3.md §1), testbench only: D-PHY pads (logic levels) -> the AFE
// outputs of ftel_dphy_rx (HAS Table 5-2, ADR-001 option A: LP-RX outputs, unsampled HS bit, DDR clock).
// - Line state per lane, inferred from the pads as the AFE sees them: LP-11 -> LP-01 (HS request) -> LP-00
//   (bridge) -> the next differential state is HS-0; HS lasts until LP-11. An escape entry starts with
//   LP-10, so a LP-01 that does not follow LP-11 stays an LP state.
// - In HS the LP receivers read LP-00, because the HS swing stays below VIL, as on silicon. (The XSIM
//   model of AMD's IBUFDS_DPHY lets its LP outputs follow the HS levels instead, FPGA_PROTO_PLAN.md
//   Appendix A.)
// - HS-RX output = Dp while the lane is in HS and the RTL enables the HS receiver (hs_en), else 0. With
//   noise = 1: random bits while hs_en is High during LP-00, when the comparator sees no differential
//   signal.
// - The pads are read 1 ps after a change, so a Dp/Dn pair that changes in two steps (TN2: two output
//   buffers of the TX model) counts as one change.
// - Report-only check of the enables, from the start of LP-00 (TD-TERM-EN <= 35 ns + 4 UI on a data lane,
//   TCLK-TERM-EN <= 38 ns on the clock lane), of termination left on during an HS request, and of the
//   delay to switch it off after LP-11. report() prints one "AFE" line.
`timescale 1ns/1ps
module afe_model #(
  parameter int NL = 4
) (
  input  logic          clk_p,
  input  logic          clk_n,
  input  logic [NL-1:0] d_p,
  input  logic [NL-1:0] d_n,
  input  logic [NL-1:0] hs_en,
  input  logic [NL-1:0] term_en,
  input  logic          cl_hs_en,
  input  logic          cl_term_en,
  output logic [NL-1:0] lp_dp,
  output logic [NL-1:0] lp_dn,
  output logic [NL-1:0] hs_bit,
  output logic          cl_lp_dp,
  output logic          cl_lp_dn,
  output logic          cl_hs_clk,
  output logic [NL-1:0] in_hs,
  output logic          cl_in_hs
);
  typedef enum logic [1:0] {S_LP, S_RQST, S_BRIDGE, S_HS} st_t;

  real ui    = 0.694;      // set by the testbench
  bit  noise = 1'b0;

  // enable check: delays in ns, worst case over all lanes and bursts
  real dl_term_max = 0.0, dl_hs_max = 0.0, dl_off_max = 0.0;
  int  dl_entries = 0, dl_term_late = 0, dl_term_missing = 0, dl_term_in_rqst = 0;
  real cl_term_dly = -1.0, cl_hs_dly = -1.0;
  int  cl_term_late = 0;

  function automatic st_t step(st_t s, logic [1:0] prev, logic [1:0] pn);
    case (s)
      S_LP:     return (prev == 2'b11 && pn == 2'b01) ? S_RQST : S_LP;
      S_RQST:   return (pn == 2'b00) ? S_BRIDGE : ((pn == 2'b01) ? S_RQST : S_LP);
      S_BRIDGE: return (pn == 2'b00) ? S_BRIDGE : ((pn == 2'b11) ? S_LP : S_HS);
      default:  return (pn == 2'b11) ? S_LP : S_HS;
    endcase
  endfunction

  // ------------------------------------------------------------------ data lanes
  for (genvar l = 0; l < NL; l++) begin : g_dl
    st_t        st        = S_LP;
    logic [1:0] pn_s      = 2'b11;
    logic       nb        = 1'b0;
    real        t_bridge  = 0.0;
    real        t_lp11    = 0.0;
    bit         wait_term = 1'b0;
    bit         wait_hs   = 1'b0;
    bit         wait_off  = 1'b0;

    always @(d_p[l], d_n[l]) begin : p_line
      logic [1:0] pn;
      st_t        nx;
      #0.001;
      pn = {d_p[l], d_n[l]};
      if (pn !== pn_s) begin
        nx = step(st, pn_s, pn);
        if (nx == S_RQST && st != S_RQST && term_en[l]) dl_term_in_rqst++;
        if (nx == S_BRIDGE && st != S_BRIDGE) begin
          t_bridge  = $realtime;
          wait_term = 1'b1;
          wait_hs   = 1'b1;
          dl_entries++;
        end
        if (st == S_HS && nx == S_LP) begin
          t_lp11 = $realtime;
          if (wait_term) begin
            dl_term_missing++;
            wait_term = 1'b0;
          end
          wait_off = 1'b1;
        end
        st   = nx;
        pn_s = pn;
      end
    end

    always begin : p_noise
      wait (noise && hs_en[l] && st == S_BRIDGE);
      #(ui * 0.37);
      nb = 1'($urandom_range(0, 1));
    end

    always @(posedge term_en[l]) if (wait_term) begin : p_term
      real d;
      d         = $realtime - t_bridge;
      wait_term = 1'b0;
      if (d > dl_term_max) dl_term_max = d;
      if (d > 35.0 + 4.0 * ui) dl_term_late++;
    end

    always @(posedge hs_en[l]) if (wait_hs) begin : p_hs
      real d;
      d       = $realtime - t_bridge;
      wait_hs = 1'b0;
      if (d > dl_hs_max) dl_hs_max = d;
    end

    always @(negedge term_en[l]) if (wait_off) begin : p_off
      real d;
      d        = $realtime - t_lp11;
      wait_off = 1'b0;
      if (d > dl_off_max) dl_off_max = d;
    end

    assign in_hs[l]  = (st == S_HS);
    assign lp_dp[l]  = (st == S_HS) ? 1'b0 : pn_s[1];
    assign lp_dn[l]  = (st == S_HS) ? 1'b0 : pn_s[0];
    assign hs_bit[l] = (st == S_HS && hs_en[l]) ? pn_s[1] :
                       ((noise && hs_en[l] && st == S_BRIDGE) ? nb : 1'b0);
  end

  // ------------------------------------------------------------------ clock lane
  st_t        cl_st       = S_LP;
  logic [1:0] cl_pn_s     = 2'b11;
  real        cl_t_bridge = 0.0;
  bit         cl_wait     = 1'b0;

  always @(clk_p, clk_n) begin : p_cl_line
    logic [1:0] pn;
    st_t        nx;
    #0.001;
    pn = {clk_p, clk_n};
    if (pn !== cl_pn_s) begin
      nx = step(cl_st, cl_pn_s, pn);
      if (nx == S_BRIDGE && cl_st != S_BRIDGE) begin
        cl_t_bridge = $realtime;
        cl_wait     = 1'b1;
      end
      cl_st   = nx;
      cl_pn_s = pn;
    end
  end

  always @(posedge cl_term_en) if (cl_wait && cl_term_dly < 0.0) begin
    cl_term_dly = $realtime - cl_t_bridge;
    if (cl_term_dly > 38.0) cl_term_late++;
  end

  always @(posedge cl_hs_en) if (cl_wait && cl_hs_dly < 0.0) cl_hs_dly = $realtime - cl_t_bridge;

  assign cl_in_hs  = (cl_st == S_HS);
  assign cl_lp_dp  = (cl_st == S_HS) ? 1'b0 : cl_pn_s[1];
  assign cl_lp_dn  = (cl_st == S_HS) ? 1'b0 : cl_pn_s[0];
  assign cl_hs_clk = (cl_st == S_HS && cl_hs_en) ? cl_pn_s[1] : 1'b0;

  function automatic void report();
    $display("AFE data lanes: %0d HS entries, term_en after LP-00 max %.3f ns (limit %.3f, %0d late, %0d missing), hs_en max %.3f ns, term_en during HS request %0d, term_en off after LP-11 max %.3f ns",
             dl_entries, dl_term_max, 35.0 + 4.0 * ui, dl_term_late, dl_term_missing, dl_hs_max,
             dl_term_in_rqst, dl_off_max);
    $display("AFE clock lane: term_en after LP-00 %.3f ns (limit 38.000, %0d late), hs_en %.3f ns",
             cl_term_dly, cl_term_late, cl_hs_dly);
  endfunction
endmodule
