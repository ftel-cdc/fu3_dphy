# ftel_dphy_rx — Developer Guide

MIPI D-PHY receiver controller: receives one clock lane and up to four data lanes and
presents the received data on the PHY-Protocol Interface (PPI) toward a CSI-2 receiver.

> Status (2026-10-10): architecture draft — [`doc/spec.md`](doc/spec.md) is HAS **draft v0.15**
> (open items in its chapter 9).
> - v0.13 moves the samplers, the 1:8 deserializer, the byte clock and the clock-activity detection
>   from the AFE into Block No. 1 (ADR-001 option A, as announced by the AFE team).
> - v0.14 corrects four statements found while designing and simulating the RTL of Block No. 1.
> - v0.15 moves the timing figures from 130 nm to 22 nm cells, the node of the target; no behaviour
>   or interface changes.
>
> Research, change analysis and sync-up lists are in
> [`doc/DPHY_RX_RESEARCH_PLAN.md`](doc/DPHY_RX_RESEARCH_PLAN.md); the requirement-to-RTL flow is
> planned in [`doc/RTL_FLOW_PLAN.md`](doc/RTL_FLOW_PLAN.md).
>
> **Draft RTL** of release R1 in `logical/`, following HAS v0.14 (v0.15 changes no behaviour):
> - Open items stay at the defaults of the HAS, each tagged `// OPEN`.
> - Lint-clean: VCS, SpyGlass with one waiver, `check_rtl_rules.py`.
> - Only Block No. 1 is simulated, by a directed testbench (`sim/tb_afe_adapter`, five line rates).
> - Timing constraints in `sdc/`. A trial synthesis on [target library] (`syn/`) meets timing at 1792 and
>   1500 Mb/s in the slow corners before layout.
>
> Decisions and status in [`doc/rtl_notes.md`](doc/rtl_notes.md).

---

## Scope

In scope: the D-PHY receive path, lanes → PPI. CSI-2 v1.3 §7.1 sets the minimum
D-PHY requirements for a CSI-2 receiver:

- Data Lane Module: unidirectional slave, HS-RX, LP-RX and a CIL-SFEN function.
- Clock Lane Module: unidirectional slave, HS-RX, LP-RX and a CIL-SCNN function.
- Continuous clock behaviour on the Clock Lane is mandatory; non-continuous clock is optional.
- Forward escape ULPS on all Data Lanes is mandatory.
- A deskew mechanism in the Receive Data Lane Module, which may be bypassed.
- An N-lane receiver must work with an M-lane transmitter when M <= N (CSI-2 v1.3 §8.3).

Out of scope for now: the CSI-2 protocol layer (PPI → pixel stream).

## Reference documents

| Document | Location | Use |
|---|---|---|
| MIPI CSI-2 v1.3 | [`ref/spec/MIPI_CSI-2_Spec_V1.3.pdf`](../../../../ref/spec/MIPI_CSI-2_Spec_V1.3.pdf) | Source of truth for transmitter behaviour and Rx requirements (§7 Physical Layer) |
| MIPI D-PHY v1.1 | [`ref/spec/mipi_D-PHY_specification_v1-1.pdf`](../../../../ref/spec/mipi_D-PHY_specification_v1-1.pdf) | SoT/EoT sequences (§6.4), timing parameters (Table 14), PPI (Annex A) |
| Example Tx model | [`ref/mipi_tx_dphy_model/`](../../../../ref/mipi_tx_dphy_model/) | Illustrative stimulus only — not the real transmitter |

CSI-2 v1.3 requires D-PHY **v1.2**, which is not available here. Features that only exist
in v1.2 (data rates above 1.5 Gbps, the deskew calibration sequence) are defined in
`doc/spec.md` as explicit design decisions.

---

## Directory Structure

```
ftel_dphy_rx/
├── README.md             ← this file
├── ip_config.yaml        ← tool_flow design overrides (all commented = default convention)
├── .gitignore            ← tool_flow output patterns
├── config/
│   ├── ftel_dphy_rx.yaml ← configuration: Table 3-1 parameters, Table 3-2 field widths and reset values
│   └── validate_config.py ← checks the YAML against the HAS formulas, emits logical/ftel_dphy_rx_config_pkg.sv
├── doc/
│   ├── spec.md           ← architecture specification (HAS), draft v0.15 (source of the docx); standalone:
│   │                       cites no other file or document, the MIPI standards by name only (§1.5)
│   ├── md2docx.py        ← spec.md → FTEL_IP_MIPI_D-PHY_RX_HAS_v<x.y>.docx in the FTEL HAS format
│   ├── FTEL_IP_MIPI_D-PHY_RX_HAS_v0.15.docx ← HAS as a Word document (built, do not edit by hand)
│   ├── DPHY_RX_RESEARCH_PLAN.md ← research, change analysis, sync-up lists, plan
│   ├── RTL_FLOW_PLAN.md  ← requirement-to-RTL flow (adapted [reference rule set] flow), stages and gates
│   ├── rtl_rule.md       ← RTL coding rule (naming, CDC, tags); [M] rules checked by check_rtl_rules.py
│   ├── rtl_notes.md      ← HAS ↔ RTL mapping, RTL decisions D-n, lint log
│   ├── analysis/         ← models behind design decisions (adr007: start of the sync search)
│   ├── sync/             ← question lists for the CSI team, the Tx side and the AFE team
│   └── figures/          ← diagrams referenced by spec.md (drawio / WaveJSON sources + SVG/PNG)
├── req/                  ← requirement artifacts of the flow (structured_spec.json, rtl_scope.json, rtm.json,
│                           conflicts_<phase>.json, flow_state.json)
├── logical/              ← RTL (flat, 22 files: 2 packages, 20 modules) + filelist.f (compile order) /
│                           filelist_sim.f / filelist_netlist.f
├── sim/                  ← vcs_lint.sh (VCS +lint=all, 1/2/4 lanes); tb_afe_adapter/ (directed TB of
│                           Block No. 1, run.sh); later the unit testbenches, BFM, models
├── lint/                 ← lint_constraint.tcl, lint_waiver.tcl (SpyGlass lint_rtl)
├── cdc/                  ← cdc.sgdc, cdc_waiver.sgdc (SpyGlass cdc_verify)
├── rdc/                  ← rdc.sgdc, rdc_waiver.sgdc (SpyGlass rdc_verify_struct)
├── sdc/                  ← m_ftel_dphy_rx_wrap.sdc: clocks, exceptions, I/O budgets (design intent;
│                           also read by cdc/ and rdc/)
└── syn/                  ← synthesis (Design Compiler): run_syn.sh, dc_syn.tcl (environment, reports),
                            summarize.sh, tech/<tech>.tcl (library), cells/<tech>/ (clock cells on library
                            cells); work/, output/, netlist/ are generated (gitignored)
```

The lint/cdc/rdc/sdc/logical skeleton was created by the FX1 common flow
(`ip-dev/hw/utils/tool_flow`, `--tool init`). Run it on this repository with `REPO_ROOT`:

```bash
REPO_ROOT=/home/linhhk/Documents/DPHY \
  python3 -B /home/linhhk/Documents/ip-dev/hw/utils/tool_flow/bin/run_ip_tool.py --ip dphy_rx --tool <init|lint|cdc|rdc|vcs|vcs-run>
```

`init` (2026-09-26) and `lint` (SpyGlass `lint_rtl`, 2026-10-07: 0 Fatal / 0 Error / 0 Warning, one
waiver for the clock structure of Block No. 1, rtl_notes D-19) have been exercised; `cdc`, `rdc` and
`vcs-run` come with M4 and M3. VCS lint of the RTL and the directed simulation of Block No. 1:

```bash
hw/rtl/ip/ftel_dphy_rx/sim/vcs_lint.sh                    # wrapper, PARA_NUM_LANES = 1, 2, 4
hw/rtl/ip/ftel_dphy_rx/sim/vcs_lint.sh --module <name>    # one module with the files before it
hw/rtl/ip/ftel_dphy_rx/sim/tb_afe_adapter/run.sh          # Block No. 1 at 80, 800, 1500, 1600, 1792 Mb/s
```

Synthesis with Design Compiler on [target library]: one run per library corner and line rate. Each run
writes `syn/work/<run>/` (`dc.log`), `syn/output/<run>/` (reports) and `syn/netlist/<run>/`
(netlist, ddc, sdc). A run passes when it ends with `SYN DONE` and has no `Error` message.
Constraints and results are in `doc/rtl_notes.md` §6.

```bash
hw/rtl/ip/ftel_dphy_rx/syn/run_syn.sh                     # SSG 0.72 V at -40 and 125 °C, 1792 and 1500 Mb/s
hw/rtl/ip/ftel_dphy_rx/syn/run_syn.sh --rate 1792 --corner [corner]
hw/rtl/ip/ftel_dphy_rx/syn/summarize.sh                   # WNS/TNS, Block No. 1 paths, area per block
```

---

## Coding Conventions

FX1 conventions: the IP Wrapper Guideline
(`~/Documents/FX1_ips/Common_Info/IP_Wrapper_Guideline.pdf`, Tables 1-1 and 1-2) and the ip-dev
project settings (`ip-dev/hw/utils/tool_flow/config/project.yaml`). The complete rule set is
[`doc/rtl_rule.md`](doc/rtl_rule.md) (v1.2, 2026-10-07); the table below summarizes it.

| Item | Convention |
|---|---|
| Language | SystemVerilog (`.sv`), synthesizable subset; `always_ff` / `always_comb` only |
| IP folder | `hw/rtl/ip/ftel_dphy_rx` |
| Module names | Every module starts with `m_` (Guideline Table 1-1): wrapper `m_ftel_dphy_rx_wrap` (IP top for tool_flow), core `m_ftel_dphy_rx`, sub-blocks `m_ftel_dphy_rx_<block>`; packages `ftel_dphy_rx[_<name>]_pkg` |
| Parameters / defines | `PARA_<NAME>` / `DEF_<NAME>` |
| Flip-flops / instances | `reg_<name>` / `u_<name>_<n>` |
| Ports | `i_` / `o_` (no `io_` in this IP); wrapper ports `<dir>_dphy_rx_<type>_<name>` (Guideline Table 1-2, IP token `dphy_rx`) |
| Resets | Active-low `_n` at the wrapper; an active-high reset gets its inverter inside the wrapper |
| Clock-domain crossing | Only through the cells `m_ftel_dphy_rx_sync` (level, port-compatible with `m_vlsi_synch`), `m_ftel_dphy_rx_tsync` (toggle) and `m_ftel_dphy_rx_rst_sync` (reset, port-compatible with `m_fpt_lib_reset_sync_rising_edge_async_reset_n`), each instance tagged `// CDC_CROSSING` |
| Clock structure | Only in `m_ftel_dphy_rx_byte_clk` (Block No. 1, HAS §4.3): inverted DDR clock, divider by 4, clock gate, gate enable from a reset synchronizer, each tagged `// CLK_STRUCT`; the cells `m_ftel_dphy_rx_cg` and `m_ftel_dphy_rx_clk_inv` keep the ports of `m_fpt_lib_cg` and `m_fpt_lib_clk_inv`, instances `u_dont_touch_*` |
| Traceability | `// REQ-xxx` on every always block, assign group and instance; `// OPEN <id> REQ-xxx: <default>` at the single place of a provisional REQ (`req/rtl_scope.json`, `req/rtm.json`) |
| Files | One module per file; file name = module name |
| File header | FTEL copyright + Evolution History block, in the form used by `ftel_intctl` |
| Generated output | Never committed — see the repository `.gitignore` |

---

## Environment Setup

```bash
export REPO_ROOT=/home/linhhk/Documents/DPHY
export DPHY_RX_PATH=$REPO_ROOT/hw/rtl/ip/ftel_dphy_rx
export VERDI_HOME=/opt/synopsys/verdi/X-2025.06
```

### Tools

| Tool | Version installed | Purpose |
|---|---|---|
| VCS | X-2025.06 | Simulation |
| Verdi | X-2025.06 | Waveform viewing |
| SpyGlass | X-2025.06-SP2 | Lint / CDC / RDC |
| Design Compiler | X-2025.06-SP5 | Synthesis |
