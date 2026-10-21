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
// $FTEL_DPHY_RX_PATH is set by tool_flow (run_ip_tool.py) and by sim/vcs_lint.sh.
// sim/vcs_lint.sh reads the compile order from this file.
+incdir+${FTEL_DPHY_RX_PATH}/logical
${FTEL_DPHY_RX_PATH}/logical/ftel_dphy_rx_config_pkg.sv
${FTEL_DPHY_RX_PATH}/logical/ftel_dphy_rx_pkg.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_sync.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_rst_sync.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_tsync.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_cg.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_clk_inv.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_lp_filter.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_clk_act.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_byte_clk.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_hs_deser.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_afe_adapter.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_timing_init.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_cl_ctrl.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_esc_decoder.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_dl_ctrl.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_sync_search.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_eot.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_hs_datapath.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_ppi_out.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx.sv
${FTEL_DPHY_RX_PATH}/logical/m_ftel_dphy_rx_wrap.sv
