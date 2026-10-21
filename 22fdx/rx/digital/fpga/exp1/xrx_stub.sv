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
// Description     : Stand-in for AMD's D-PHY RX in the TN1 testbench, used by "run_exp1.sh stub" to
//                   run ftel_dphy_rx alone.
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
// Stand-in for AMD's D-PHY RX of the TN1 testbench (module xrx, ports of mipi_dphy 4.3 SLAVE with 4 lanes),
// used by "run_exp1.sh stub": it runs ftel_dphy_rx alone, below 260 Mb/s where AMD's IP cannot be built
// (C_HS_LINE_RATE 260..3200 on xcvp1902) and for quick sweeps (compile about 10 s, a run a few seconds).
// init_done rises after 1 us; every PPI output stays 0, so its CSV carries no burst.
`timescale 1ns/1ps
module xrx (
  input  logic       core_clk,
  input  logic       core_rst,
  output logic       rxbyteclkhs,
  output logic       clkoutphy_out,
  output logic       pll_lock_out,
  output logic       system_rst_out,
  output logic       init_done,
  output logic       cl_stopstate,
  input  logic       cl_enable,
  output logic       cl_ulpsactivenot,
  output logic       cl_rxclkactivehs,
  output logic       cl_rxulpsclknot,
  output logic       dl0_stopstate,     dl1_stopstate,     dl2_stopstate,     dl3_stopstate,
  input  logic       dl0_enable,        dl1_enable,        dl2_enable,        dl3_enable,
  output logic       dl0_ulpsactivenot, dl1_ulpsactivenot, dl2_ulpsactivenot, dl3_ulpsactivenot,
  output logic [7:0] dl0_rxdatahs,      dl1_rxdatahs,      dl2_rxdatahs,      dl3_rxdatahs,
  output logic       dl0_rxvalidhs,     dl1_rxvalidhs,     dl2_rxvalidhs,     dl3_rxvalidhs,
  output logic       dl0_rxactivehs,    dl1_rxactivehs,    dl2_rxactivehs,    dl3_rxactivehs,
  output logic       dl0_rxsynchs,      dl1_rxsynchs,      dl2_rxsynchs,      dl3_rxsynchs,
  input  logic       dl0_forcerxmode,   dl1_forcerxmode,   dl2_forcerxmode,   dl3_forcerxmode,
  output logic       dl0_rxclkesc,      dl1_rxclkesc,      dl2_rxclkesc,      dl3_rxclkesc,
  output logic       dl0_rxlpdtesc,     dl1_rxlpdtesc,     dl2_rxlpdtesc,     dl3_rxlpdtesc,
  output logic       dl0_rxulpsesc,     dl1_rxulpsesc,     dl2_rxulpsesc,     dl3_rxulpsesc,
  output logic [3:0] dl0_rxtriggeresc,  dl1_rxtriggeresc,  dl2_rxtriggeresc,  dl3_rxtriggeresc,
  output logic [7:0] dl0_rxdataesc,     dl1_rxdataesc,     dl2_rxdataesc,     dl3_rxdataesc,
  output logic       dl0_rxvalidesc,    dl1_rxvalidesc,    dl2_rxvalidesc,    dl3_rxvalidesc,
  output logic       dl0_errsoths,      dl1_errsoths,      dl2_errsoths,      dl3_errsoths,
  output logic       dl0_errsotsynchs,  dl1_errsotsynchs,  dl2_errsotsynchs,  dl3_errsotsynchs,
  output logic       dl0_erresc,        dl1_erresc,        dl2_erresc,        dl3_erresc,
  output logic       dl0_errsyncesc,    dl1_errsyncesc,    dl2_errsyncesc,    dl3_errsyncesc,
  output logic       dl0_errcontrol,    dl1_errcontrol,    dl2_errcontrol,    dl3_errcontrol,
  input  logic       clk_rxp,
  input  logic       clk_rxn,
  input  logic [3:0] data_rxp,
  input  logic [3:0] data_rxn
);
  initial begin
    rxbyteclkhs = 1'b0;
    init_done   = 1'b0;
    #1000 init_done = 1'b1;
  end
  always #2.778 rxbyteclkhs = ~rxbyteclkhs;

  assign {clkoutphy_out, pll_lock_out, system_rst_out, cl_stopstate, cl_ulpsactivenot, cl_rxclkactivehs,
          cl_rxulpsclknot} = '0;
  assign {dl0_stopstate, dl0_ulpsactivenot, dl0_rxdatahs, dl0_rxvalidhs, dl0_rxactivehs, dl0_rxsynchs,
          dl0_rxclkesc, dl0_rxlpdtesc, dl0_rxulpsesc, dl0_rxtriggeresc, dl0_rxdataesc, dl0_rxvalidesc,
          dl0_errsoths, dl0_errsotsynchs, dl0_erresc, dl0_errsyncesc, dl0_errcontrol} = '0;
  assign {dl1_stopstate, dl1_ulpsactivenot, dl1_rxdatahs, dl1_rxvalidhs, dl1_rxactivehs, dl1_rxsynchs,
          dl1_rxclkesc, dl1_rxlpdtesc, dl1_rxulpsesc, dl1_rxtriggeresc, dl1_rxdataesc, dl1_rxvalidesc,
          dl1_errsoths, dl1_errsotsynchs, dl1_erresc, dl1_errsyncesc, dl1_errcontrol} = '0;
  assign {dl2_stopstate, dl2_ulpsactivenot, dl2_rxdatahs, dl2_rxvalidhs, dl2_rxactivehs, dl2_rxsynchs,
          dl2_rxclkesc, dl2_rxlpdtesc, dl2_rxulpsesc, dl2_rxtriggeresc, dl2_rxdataesc, dl2_rxvalidesc,
          dl2_errsoths, dl2_errsotsynchs, dl2_erresc, dl2_errsyncesc, dl2_errcontrol} = '0;
  assign {dl3_stopstate, dl3_ulpsactivenot, dl3_rxdatahs, dl3_rxvalidhs, dl3_rxactivehs, dl3_rxsynchs,
          dl3_rxclkesc, dl3_rxlpdtesc, dl3_rxulpsesc, dl3_rxtriggeresc, dl3_rxdataesc, dl3_rxvalidesc,
          dl3_errsoths, dl3_errsotsynchs, dl3_erresc, dl3_errsyncesc, dl3_errcontrol} = '0;
endmodule
