#!/usr/bin/env python3
#-------------------------------------------------------------------------------
# Copyright (c) 2026 FPT Telecom. All rights reserved.
#
# This source code and the associated design are the proprietary
# and confidential information of FPT Telecom.
# Any unauthorized use, reproduction, or disclosure is strictly prohibited.
#-------------------------------------------------------------------------------
# Author          : Ho Khanh Linh
# Email           : linhhk26@fpt.com
# Created Date    : 2026-10-19
# Description     : Run-time fields of ftel_dphy_rx at one line rate, as plusargs of the TN1 testbench
#                   (tb_exp1.sv).
#
# Evolution History:
# ------------------------------------------------------------------------------
# Date         Version    Author        Description
# 2026-10-19   0.1        Ho Khanh Linh Initial creation.
#
# This section is not intended for routine updates or minor design changes.
# A new version is strictly reserved for major architectural shifts
# that require software modifications across different chip generations.
#-------------------------------------------------------------------------------
"""Run-time fields of ftel_dphy_rx at one line rate, as plusargs of the TN1 testbench (tb_exp1.sv).

  cfg_for_rate.py <rate Mb/s>   ->   +HS_SETTLE=<cyc> +CLK_SETTLE=<cyc> +EOT_SKIP=<bytes>

The values come from the timing model of the configuration validator
(config/validate_config.py, class Model) and its YAML; nothing is recomputed here.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'config')
sys.path.insert(0, CONFIG)
import validate_config as vc  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rate = float(sys.argv[1])
    with open(vc.YAML_DEFAULT, 'rb') as f:
        cfg = vc.yaml.safe_load(f.read())
    m = vc.Model(cfg)
    print(f"+HS_SETTLE={m.hs_settle(rate)} +CLK_SETTLE={m.clk_settle()} +EOT_SKIP={m.eot_skip(rate)}")


if __name__ == '__main__':
    main()
