#!/bin/bash
# Negative test of the front-end check of tb_exp1.sv (fpga/exp1/README.md §7.6). A copy of the 1440 Mb/s, 4-lane
# build gets a testbench whose buffers in front of ftel_dphy_rx see pull strength during HS (the option dropped in
# fpga/PLAN_TN1_FAIR.md §8), while AMD's buffers still see strong. E1-1 runs on that copy: the check must count
# differences, and tn1_evidence.py must report front FAIL. Outputs in fpga/work/exp1/neg (gitignored); the
# sources in the repo are not changed.
#   fpga/exp1/neg_front.sh        (~1 min)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
FPGA=$(dirname "$HERE")
W=$FPGA/work/exp1
N=$W/neg
XBIN=$(dirname "${VIVADO:-/opt/xilinx/2025.2/Vivado/bin/vivado}")
export PATH="$XBIN:$PATH"
OUT=$N/run/NEG-E1-1

"$HERE/run_exp1.sh" build 1440 4 || exit 1
rm -rf "$N"
mkdir -p "$OUT"
cp -r "$W/build_1440_4l/prj/exp1.sim/sim_1/behav/xsim" "$N/"
python3 - "$HERE/tb_exp1.sv" "$N/tb_exp1.sv" <<'EOF'
import sys
s = open(sys.argv[1]).read()
loop = "  for (genvar l = 0; l < NL; l++) begin : g_ibuf\n"
neg = """  wire [NL-1:0] neg_p, neg_n;   // negative test: pull strength during HS at the buffers of ftel_dphy_rx
  for (genvar l = 0; l < NL; l++) begin : g_neg
    assign (strong1, strong0) neg_p[l] = hs_truth[l] ? 1'bz : d_p[l];
    assign (pull1, pull0)     neg_p[l] = hs_truth[l] ? d_p[l] : 1'bz;
    assign (strong1, strong0) neg_n[l] = hs_truth[l] ? 1'bz : d_n[l];
    assign (pull1, pull0)     neg_n[l] = hs_truth[l] ? d_n[l] : 1'bz;
  end
"""
for old, new in ((loop, neg + loop), (".I            (d_p[l]),", ".I            (neg_p[l]),"),
                 (".IB           (d_n[l]),", ".IB           (neg_n[l]),")):
    assert s.count(old) == 1, old
    s = s.replace(old, new)
open(sys.argv[2], 'w').write(s)
EOF
if ! (cd "$N/xsim" && xvlog --relax -sv -L uvm -work xil_defaultlib -i "$(dirname "$FPGA")/hw/rtl/ip/ftel_dphy_rx/logical" \
        "$N/tb_exp1.sv" > "$N/compile.log" 2>&1 && bash elaborate.sh > "$N/elaborate.log" 2>&1); then
  echo "neg_front: build FAIL, see $N/compile.log and $N/elaborate.log"
  exit 1
fi
args=()
for a in $(python3 "$HERE/cfg_for_rate.py" 1440) +RATE=1440 "+OUTDIR=$OUT"; do
  args+=(-testplusarg "${a#+}")
done
echo "NEG-E1-1: 1440 Mb/s, 4 lane(s) " > "$OUT/args.txt"
(cd "$N/xsim" && xsim tb_exp1_behav -R -log "$OUT/xsim.log" "${args[@]}" > /dev/null 2>&1)
grep -E '^(TB |AFE )' "$OUT/xsim.log" > "$OUT/tb.txt"
echo "trailer limit (AMD, ftel_dphy_rx or ftel_dphy_rx alone): -,0" >> "$OUT/args.txt"
python3 "$FPGA/tools/csi2_dump.py" bursts --truth "$OUT/truth.txt" --lanes 4 --max-trailer=-,0 \
  "$OUT/xil_ppi.csv" "$OUT/ftel_ppi.csv" > "$OUT/check.txt" 2>&1
grep '^TB FRONT END CHECK' "$OUT/tb.txt"
ev=$(python3 "$HERE/tn1_evidence.py" "$N/run")   # exits 1 here by design
if grep '^FAIL  front' <<< "$ev"; then
  echo "NEGATIVE TEST PASS: the front-end check reports the different front end"
else
  echo "NEGATIVE TEST FAIL: the front-end check did not see the different front end"
  exit 1
fi
