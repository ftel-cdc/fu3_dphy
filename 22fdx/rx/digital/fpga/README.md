# fpga — FPGA prototype of ftel_dphy_rx

Prototype work for the D-PHY receiver `ftel_dphy_rx` (RTL in [`../logical`](../logical)) on an AMD Versal
VP1902 board (part `xcvp1902-vsva6865-2MP-e-S`) with a MIPI camera on FMC+, next to the MIPI CSI-2 Rx
Subsystem of AMD.

The prototype plan and the bring-up build of the board (step S0, made from the reference design of the
board) are kept by the team and are not in this repository. This folder holds what does not depend on
them: the simulation experiments, the specification of TN3 for the FPGA team, the Vivado probes of AMD's
IP and of the device, and the tools that check the captures.

> Status (2026-10-20): the work is split into three experiments ([`PLAN_TN1_TN3.md`](PLAN_TN1_TN3.md)).
> TN1 and TN2 run in Vivado simulation; TN3 (TX on a second FPGA board, test board, RX on the VP1902
> board) is specified for the FPGA team in [`exp3/TN3_SPEC.md`](exp3/TN3_SPEC.md) (part 1; the VEK280
> cannot be the TX, its FMC banks are fixed at 1.5 V). TN1 is in `exp1/`. Its first run found two faults
> in ftel_dphy_rx: payload bytes lost at the end of bursts (EoT cut), and one `rxvalidhs` outside
> `rxactivehs` per burst. Both are fixed with HAS v0.16 ([`PLAN_TN1_FIX.md`](PLAN_TN1_FIX.md)).
>
> Both receivers pass all 113 TN1 scenarios, E1-1 to E1-5 (`run_exp1.sh summary`).
> - From 260 Mb/s, ftel_dphy_rx loses no payload byte, and the trailer bytes it keeps stay within HAS
>   Table 4-7.
> - Table 4-7 comes from `run_exp1.sh window`, which reaches LP-11 at every phase of `core_clk`. The
>   first table had been measured without these phases; this measurement led to the refit of
>   `eot_skip_bytes`.
> - At 1440 Mb/s AMD's receiver keeps 16–17 trailer bytes in every burst. ftel_dphy_rx keeps none
>   without junk, and none in about 99 % of bursts with 40 ns of junk.
>
> TN1 compares the digital parts on equal terms ([`PLAN_TN1_FAIR.md`](PLAN_TN1_FAIR.md)).
> - ftel_dphy_rx sits behind `IBUFDS_DPHY`, the input buffer of AMD's receiver, driven with the same strength.
>   Each run checks that the LP outputs of both sets of buffers are equal at every change.
> - E1-5 runs both receivers at eight rates.
> - The same scenarios with ftel_dphy_rx behind `afe_model` (`run_exp1.sh model`) also pass, and their captures
>   equal those of the run before the change byte for byte.
> - Details are in [`exp1/README.md`](exp1/README.md); `exp1/tn1_evidence.py` re-checks all of it.

```
fpga/
├── PLAN_TN1_TN3.md      ← plan of the experiments TN1 (two receivers, one line), TN2 (TX -> RX), TN3 (two boards)
├── PLAN_TN1_FIX.md      ← plan of the fix of the two faults found by TN1 (EoT hold, eot_skip_bytes, HAS v0.16)
├── PLAN_TN1_FAIR.md     ← plan of the fair TN1: both receivers behind IBUFDS_DPHY, E1-5 for both
├── exp1/                ← TN1: D-PHY line generator, AFE model, PPI monitor, testbench, run_exp1.sh (XSIM),
│                          eot_window.py (table of the eot_skip_bytes window); README.md describes the tests;
│                          tn1_evidence.py re-checks the results independently of csi2_dump.py;
│                          neg_front.sh shows that its front-end check fails on a different front end
├── exp3/                ← TN3: TN3_SPEC.md, the experiment specification for the FPGA team
├── probe/               ← Vivado batch probes of AMD's D-PHY and CSI-2 IP and of the device (run_probe.sh)
├── tools/               ← csi2_dump.py: checks the CSI-2 traffic in ILA captures (PPI or AXI4-Stream) and
│                          the per-lane bursts of TN1 against the truth of the line generator;
│                          bd_summary.py: lists a block design (.bd JSON) without opening it in Vivado;
│                          f2_timing.py: timing of AMD's D-PHY RX from the VCD of probe dphy_exdes_sim
└── work/                ← outputs of the probes and tools (gitignored)
```

```bash
fpga/probe/run_probe.sh                    # light Vivado 2025.2 probes -> fpga/work/<probe>/probe.txt
fpga/probe/run_probe.sh impl_tiny          # heavy probes run only by name, when the machine is idle
python3 fpga/tools/bd_summary.py <file.bd> # cells, parameters, ports, address map, CSI-2 nets
python3 fpga/tools/csi2_dump.py selftest   # --tx-model also compares with the third-party Tx model in XSIM
                                           #     (ref/mipi_tx_dphy_model, not in this repository)
fpga/exp1/run_exp1.sh E1-1                 # TN1 at 1440 Mb/s: AMD's D-PHY RX and ftel_dphy_rx on one line
fpga/exp1/run_exp1.sh all                  # TN1 scenarios E1-1..E1-5 (one Vivado build per rate and lane count;
                                           #     E1-5: EoT stress of both receivers, HAS v0.16 Table 4-7; ~23 min)
fpga/exp1/run_exp1.sh model                # the same with ftel_dphy_rx behind afe_model, outputs in M_<name>
python3 fpga/exp1/tn1_evidence.py          # re-checks all TN1 outputs (decode, front end, sources, margin, ...)
fpga/exp1/run_exp1.sh window               # eot_skip_bytes from its model value - 1 to + 2, LP-11 at every phase
                                           #     (ftel_dphy_rx alone, ~7 min; table by exp1/eot_window.py)
fpga/exp1/run_exp1.sh report               # 80 Mb/s, outside the guaranteed range (AMD's IP needs 260..3200 Mb/s)
fpga/exp1/run_exp1.sh summary              # result line of every TN1 scenario run so far
fpga/exp1/run_exp1.sh recheck              # check every TN1 output again with the current csi2_dump.py (no sim)
fpga/probe/run_probe.sh tn3_pins           # pins and package delays behind exp3/TN3_SPEC.md §3-4
```

Tools: Vivado 2025.2 at `/opt/xilinx/2025.2` (a new login shell has it on PATH), part
`xcvp1902-vsva6865-2MP-e-S`.
