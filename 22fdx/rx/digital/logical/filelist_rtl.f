//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-09-26
// Description     : RTL of ftel_dphy_rx in compile order: packages, cells, blocks, core, wrapper.
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-09-26   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
// RTL of ftel_dphy_rx in compile order: packages, cells, blocks, core, wrapper.
// $DPHY_RX_PATH is the IP folder (22fdx/rx/digital), the <IP>_PATH of the PD flow; tool_flow
// (run_ip_tool.py) and sim/vcs_lint.sh set it. Paths are written $DPHY_RX_PATH, without braces:
// analyze -vcs of Design Compiler does not expand ${...} (rtl_notes D-30).
// tool_flow (ip_config.yaml), sim/, syn/run_syn.sh and the benches of fpga/ read the compile order
// from this file; logical/filelist.f, the filelist of the PD flow, includes it.
+incdir+$DPHY_RX_PATH/logical
$DPHY_RX_PATH/logical/ftel_dphy_rx_config_pkg.sv
$DPHY_RX_PATH/logical/ftel_dphy_rx_pkg.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_sync.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_rst_sync.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_cg.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_clk_inv.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_lp_filter.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_clk_act.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_byte_clk.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_hs_deser.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_afe_adapter.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_timing_init.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_cl_ctrl.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_esc_decoder.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_dl_ctrl.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_sync_search.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_eot.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_hs_datapath.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_ppi_out.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx.sv
$DPHY_RX_PATH/logical/m_fpt_dphy_rx_wrap.sv
