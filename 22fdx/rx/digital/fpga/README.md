# fpga — FPGA prototype of ftel_dphy_rx

Prototype work for the D-PHY receiver `ftel_dphy_rx` (RTL in [`../logical`](../logical)) on an AMD Versal
VP1902 board (part `xcvp1902-vsva6865-2MP-e-S`) with a MIPI camera on FMC+, next to the MIPI CSI-2 Rx
Subsystem of AMD.

The prototype plan and the bring-up build of the board (step S0, made from the reference design of the
board) are kept by the team and are not in this repository. This folder holds what does not depend on
them: the simulation experiments, the specification of TN3 for the FPGA team, the Vivado probes of AMD's
IP and of the device, and the tools that check the captures.

> Status (2026-10-26): the work is split into three experiments ([`PLAN_TN1_TN3.md`](PLAN_TN1_TN3.md)).
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
>
> On 2026-10-26 a tester of the FPGA team found two gaps in the checkers: neither the width and place of `rxsynchs`
> nor the skew between lanes at the PPI was checked ([`PLAN_CHECK_C6_C10.md`](PLAN_CHECK_C6_C10.md)).
> - The checkers and the evidence scripts of TN1 and TN2 now check both: `rxsynchs` High for one sample at its place
>   from the first byte, and the bytes of a burst at most 6 byte clocks apart on the lanes. The faults the tester
>   planted are now among the planted faults of the self-tests.
> - TN1 was run again in this repository: the same results, with the outputs byte for byte those of the first run.
>   ftel_dphy_rx meets both checks in every run.
> - Three new runs skew lane 3 by 2.5, 5.5 and 7.5 byte times. Neither receiver aligns the lanes, so the skew reaches
>   the PPI. The first two pass; the third fails at the lane skew only.
>
> TN2a (`exp2/`, [`PLAN_TN2A.md`](PLAN_TN2A.md)) drives both receivers with AMD's own D-PHY TX (`mipi_dphy` 4.3
> MASTER, driven at its PPI) instead of the line generator.
> - Both receivers pass all 29 scenarios, at eight rates from 260 to 1500 Mb/s and with 1, 2 and 4 lanes. The same
>   scenarios with ftel_dphy_rx behind `afe_model` also pass (29/29). No fault was found in ftel_dphy_rx.
> - EoT at every phase of `core_clk` (both receivers 400 ppm slow, then fast, against the TX): 432/432 lane bursts at
>   each rate. From 400 Mb/s ftel_dphy_rx keeps no trailer byte.
> - The timing of the TX measured at the pads is within D-PHY v1.1 at every rate. Its TCLK-PREPARE (82–89 ns) and
>   its THS-PREPARE at 260 Mb/s (96–103 ns) go beyond the values TN1 tried.
> - Details are in [`exp2/README.md`](exp2/README.md); `exp2/tn2a_evidence.py evidence` re-checks all of it.
>
> TN2b (`exp2b/`, [`PLAN_TN2B.md`](PLAN_TN2B.md)) sends synthetic RAW10 frames through AMD's CSI-2 TX Subsystem into
> two complete receive paths: AMD's CSI-2 RX Subsystem with its D-PHY, and ftel_dphy_rx followed by the same RX
> Subsystem without PHY, the path of the prototype.
> - AMD's receive path gives every pixel in every run. AMD's controller without PHY takes none of the packets of
>   ftel_dphy_rx, although they are the same packets: ftel_dphy_rx raises `rxactivehs` some byte clocks before
>   `rxsynchs` (as its HAS allows), AMD's D-PHY raises both together, and AMD's controller needs `rxactivehs` not to
>   rise before `rxsynchs`. This is a mismatch of the PPI contract with AMD's controller, not a fault against the
>   HAS.
> - It is resolved in the FPGA only, with the RTL of ftel_dphy_rx unchanged ([`PLAN_TN2B_GATE.md`](PLAN_TN2B_GATE.md)).
>   [`rtl/m_ftel_ppi_act_gate.sv`](rtl/m_ftel_ppi_act_gate.sv) holds `rxactivehs` of each lane Low until `rxsynchs`:
>   6 flip-flops for 4 lanes, no added delay.
>   - Through it, all 27 runs pass for both receive paths: four rates from 260 to 1500 Mb/s, 2 and 1 active lanes
>     without a new build, ±400 ppm, receivers set up late, stream off and on, and behind `afe_model`. Their
>     captures are byte for byte those of the earlier runs, where the testbench held `rxactivehs` instead.
>   - The three negative tests fail where planted.
> - With a SoT sync error on one lane (E2b-9), AMD's controller recovers: the next frames are right pixel for pixel.
>   The frame with the error loses two lines; one of them still comes out wrong, with only a CRC flag in the ISR.
> - Details are in [`exp2b/README.md`](exp2b/README.md); `exp2b/tn2b_evidence.py evidence` re-checks all of it.

```
fpga/
├── PLAN_TN1_TN3.md      ← plan of the experiments TN1 (two receivers, one line), TN2 (TX -> RX), TN3 (two boards)
├── PLAN_TN1_FIX.md      ← plan of the fix of the two faults found by TN1 (EoT hold, eot_skip_bytes, HAS v0.16)
├── PLAN_TN1_FAIR.md     ← plan of the fair TN1: both receivers behind IBUFDS_DPHY, E1-5 for both
├── PLAN_TN2A.md         ← plan of TN2a: AMD's D-PHY TX into both receivers, its findings and results
├── PLAN_TN2B.md         ← plan of TN2b: CSI-2 frames from AMD's TX Subsystem into both receive paths, its findings
├── PLAN_CHECK_C6_C10.md ← plan and results of the checks of rxsynchs and lane skew at the PPI (gaps found by a
│                          tester of the FPGA team), TN1 run again with them
├── PLAN_TN2B_GATE.md    ← plan and results of the rxactivehs gate between ftel_dphy_rx and AMD's controller
│                          (option A), TN2b run again through it, E2b-9 (SoT sync error on one lane)
├── exp1/                ← TN1: D-PHY line generator, AFE model, PPI monitor, testbench, run_exp1.sh (XSIM),
│                          eot_window.py (table of the eot_skip_bytes window); README.md describes the tests;
│                          TN1_DESCRIPTION.md and TN1_REPORT.md: description and report for the FPGA team;
│                          tn1_evidence.py re-checks the results independently of csi2_dump.py;
│                          neg_front.sh shows that its front-end check fails on a different front end
├── exp2/                ← TN2a: PPI driver of AMD's D-PHY TX, pad decoder (truth and TX timing), testbench,
│                          run_exp2.sh (XSIM); README.md describes the tests; tn2a_evidence.py checks each run
│                          and re-checks all of them (decode, pads, front end, sources, copy from TN1);
│                          TN2_DESCRIPTION.md and TN2_REPORT.md: description and report of TN2a and TN2b for the
│                          FPGA team
├── exp2b/               ← TN2b: frame generator, AXI4-Stream monitor, AXI4-Lite master, testbench, run_exp2b.sh
│                          (XSIM); README.md describes the tests and the finding; tn2b_evidence.py checks each run
│                          and re-checks all of them (decode, registers, front end, sources, copy, negative tests)
├── exp3/                ← TN3: TN3_SPEC.md, the experiment specification for the FPGA team
├── probe/               ← Vivado batch probes of AMD's D-PHY and CSI-2 IP and of the device (run_probe.sh)
├── rtl/                 ← FPGA-only RTL: m_ftel_ppi_act_gate.sv (holds rxactivehs of each lane Low until rxsynchs,
│                          for AMD's controller), its unit testbench, run_rtl.sh (lint, rules, sim, synth) and
│                          synth_rtl.tcl (out-of-context synthesis for the part of the board)
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
python3 fpga/exp1/tn1_evidence.py          # re-checks all TN1 outputs: checker, decode, runs, front end, AFE,
                                           #     configuration, sources, margin
python3 fpga/exp1/tn1_evidence.py evselftest   # the same with one planted fault at a time: each must fail its check
fpga/exp1/run_exp1.sh skew                 # lane 3 skewed by 2.5, 5.5 and 7.5 byte times (the last must fail)
fpga/exp1/run_exp1.sh window               # eot_skip_bytes from its model value - 1 to + 2, LP-11 at every phase
                                           #     (ftel_dphy_rx alone, ~7 min; table by exp1/eot_window.py)
fpga/exp1/run_exp1.sh report               # 80 Mb/s, outside the guaranteed range (AMD's IP needs 260..3200 Mb/s)
fpga/exp1/run_exp1.sh summary              # result line of every TN1 scenario run so far
fpga/exp1/run_exp1.sh recheck              # check every TN1 output again with the current csi2_dump.py (no sim)
fpga/exp2/run_exp2.sh E2a-1                # TN2a at 1440 Mb/s: AMD's D-PHY TX into AMD's D-PHY RX and ftel_dphy_rx
fpga/exp2/run_exp2.sh all                  # TN2a scenarios E2a-0..E2a-5 (one Vivado build per rate and lane count)
fpga/exp2/run_exp2.sh model                # the same with ftel_dphy_rx behind afe_model, outputs in M_<name>
fpga/exp2/run_exp2.sh neg                  # negative tests: a byte sent inverted, pull strength at the buffers
fpga/exp2/run_exp2.sh evidence             # re-checks all TN2a outputs: checker, decode, runs, TX bytes at the
                                           #     pads, pad truth, front end, AFE, configuration, sources, copy
fpga/exp2/run_exp2.sh txtiming             # timing of AMD's D-PHY TX at the pads per rate, against D-PHY v1.1
fpga/exp2b/run_exp2b.sh E2b-1              # TN2b at 1440 Mb/s: AMD's CSI-2 TX Subsystem into both receive paths
fpga/exp2b/run_exp2b.sh shim               # all TN2b scenarios with rxactivehs into AMD's controller through
                                           #     fpga/rtl/m_ftel_ppi_act_gate.sv (SH_*, E2b-9 included)
fpga/exp2b/run_exp2b.sh finding            # the runs of the finding: not re-timed, and the diagnosis runs
fpga/exp2b/run_exp2b.sh evidence           # re-checks all TN2b outputs: checker, decode, runs, registers, front
                                           #     end, AFE, configuration, sources, copy, negative tests, finding, gate
fpga/rtl/run_rtl.sh all                    # the gate: VCS lint, rule check, unit testbench (VCS), Vivado OOC synthesis
fpga/probe/run_probe.sh tn3_pins           # pins and package delays behind exp3/TN3_SPEC.md §3-4
```

Tools: Vivado 2025.2 at `/opt/xilinx/2025.2` (a new login shell has it on PATH), part
`xcvp1902-vsva6865-2MP-e-S`.
