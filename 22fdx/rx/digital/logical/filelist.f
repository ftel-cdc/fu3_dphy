//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : Ho Khanh Linh
// Email           : linhhk26@fpt.com
// Created Date    : 2026-11-04
// Description     : Filelist of the PD flow for synthesis and LEC (define FPT_SIGNOFF): the
//                   compile order of filelist_rtl.f and the library of the SoC.
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-11-04   0.1        Ho Khanh Linh Initial creation.
//
// This section is not intended for routine updates or minor design changes.
// A new version is strictly reserved for major architectural shifts
// that require software modifications across different chip generations.
//------------------------------------------------------------------------------
// Filelist of the PD flow (naming rules of the PD team): synthesis and LEC read this file with the
// define FPT_SIGNOFF, under which the two clock cells instantiate m_fpt_lib_cg and m_fpt_lib_clk_inv
// of the SoC library, found in $LIB_PATH/gate (rtl_notes D-30). The compile order is in
// filelist_rtl.f, which every other flow reads, so that they need no $LIB_PATH.
+libext+.v+.sv
-y $LIB_PATH/gate
-f $DPHY_RX_PATH/logical/filelist_rtl.f
