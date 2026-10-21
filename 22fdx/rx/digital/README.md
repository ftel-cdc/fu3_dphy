# ftel_dphy_rx — Developer Guide

MIPI D-PHY receiver controller: receives one clock lane and up to four data lanes and
presents the received data on the PHY-Protocol Interface (PPI) toward a CSI-2 receiver.

This folder (`22fdx/rx/digital`) is the IP: its folders sit directly here, while the modules, the
packages and the configuration keep the IP name `ftel_dphy_rx` (`dphy_rx` in the FX1 tool_flow).
It came with its history from the team's working repository on 2026-10-21; the HAS .docx builds,
the planning notes and the reference specifications stayed there. Every command below runs from
this folder.

> Status (2026-10-19): architecture draft — [`doc/spec.md`](doc/spec.md) is HAS **draft v0.16**
> (open items in its chapter 9).
> - v0.13 moves the samplers, the 1:8 deserializer, the byte clock and the clock-activity detection
>   from the AFE into Block No. 1 (ADR-001 option A, as announced by the AFE team).
> - v0.14 corrects four statements found while designing and simulating the RTL of Block No. 1.
> - v0.15 moves the timing figures from 130 nm to 22 nm cells, the node of the target; no behaviour
>   or interface changes.
> - v0.16 corrects the EoT of Block No. 4 after the first simulation of the whole receiver (TN1 of
>   the FPGA plan, `fpga/exp1`): the fall of the sync-search start is held three byte clocks, the
>   `eot_skip_bytes` formula gains the data path latency, the guaranteed range of the trailer removal
>   is stated (Table 4-7), and `rxvalidhs_x` no longer pulses after `rxactivehs_x`.
>
> Question lists for the CSI team, the Tx side and the AFE team are in [`doc/sync/`](doc/sync/); the
> requirement tooling of the flow is described in [`req_flow/README.md`](req_flow/README.md).
>
> **Draft RTL** of release R1 in `logical/`, following HAS v0.16 (Block No. 4 and the configuration
> package; the other files keep v0.14 in their headers, as v0.15 and v0.16 change nothing there):
> - Open items stay at the defaults of the HAS, each tagged `// OPEN`.
> - Lint-clean: VCS, SpyGlass with one waiver, `check_rtl_rules.py`.
> - Simulated: Block No. 1 by a directed testbench (`sim/tb_afe_adapter`, five line rates), and the
>   whole receiver behind an AFE model against AMD's D-PHY RX in XSIM (`fpga/exp1`, TN1).
> - Timing constraints in `sdc/`. A trial synthesis on the library of the target (`syn/`) meets timing
>   at 1792 and 1500 Mb/s in the slow corners before layout.
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

| Document | Use |
|---|---|
| MIPI CSI-2 v1.3 | Source of truth for transmitter behaviour and Rx requirements (§7 Physical Layer) |
| MIPI D-PHY v1.1 | SoT/EoT sequences (§6.4), timing parameters (Table 14), PPI (Annex A) |
| Example Tx model (third party) | Illustrative stimulus only — not the real transmitter |

The MIPI specifications and the Tx model are not in this repository.

CSI-2 v1.3 requires D-PHY **v1.2**, which is not available here. Features that only exist
in v1.2 (data rates above 1.5 Gbps, the deskew calibration sequence) are defined in
`doc/spec.md` as explicit design decisions.

---

## Directory Structure

```
22fdx/rx/digital/
├── README.md             ← this file
├── ip_config.yaml        ← tool_flow design overrides (all commented = default convention)
├── .gitignore            ← tool outputs, flow work files, local HAS .docx builds, .env
├── .env.example          ← the local environment to copy to .env and fill in (see Environment Setup)
├── config/
│   ├── ftel_dphy_rx.yaml ← configuration: Table 3-1 parameters, Table 3-2 field widths and reset values
│   └── validate_config.py ← checks the YAML against the HAS formulas, emits logical/ftel_dphy_rx_config_pkg.sv
├── doc/
│   ├── spec.md           ← architecture specification (HAS), draft v0.16 (source of the docx); standalone:
│   │                       cites no other file or document, the MIPI standards by name only (§1.5)
│   ├── md2docx.py        ← spec.md → FTEL_IP_MIPI_D-PHY_RX_HAS_v<x.y>.docx in the FTEL HAS format
│   │                       (built locally, kept out of the repository by .gitignore)
│   ├── rtl_rule.md       ← RTL coding rule (naming, CDC, tags); [M] rules checked by check_rtl_rules.py
│   ├── rtl_notes.md      ← HAS ↔ RTL mapping, RTL decisions D-n, lint log
│   ├── sync/             ← question lists for the CSI team, the Tx side and the AFE team; figures/: the
│   │                       RX top and its GPIO pin options (gen_dphy_rx_top.py)
│   └── figures/          ← diagrams referenced by spec.md (drawio / WaveJSON sources + SVG; PNG local)
├── req/                  ← requirement artifacts of the flow (structured_spec.json, rtl_scope.json, rtm.json,
│                           conflicts_<phase>.json, flow_state.json, waivers.yaml, spec_review.md)
├── req_flow/             ← requirement tooling of the flow (spec inventory, REQ assembly, flow_check.py,
│                           check_rtl_rules.py), see its README
├── logical/              ← RTL (flat, 22 files: 2 packages, 20 modules) + filelist.f (compile order) /
│                           filelist_sim.f / filelist_netlist.f
├── sim/                  ← vcs_lint.sh (VCS +lint=all, 1/2/4 lanes); tb_afe_adapter/ (directed TB of
│                           Block No. 1, run.sh); later the unit testbenches, BFM, models
├── lint/                 ← lint_constraint.tcl, lint_waiver.tcl (SpyGlass lint_rtl)
├── cdc/                  ← cdc.sgdc, cdc_waiver.sgdc (SpyGlass cdc_verify)
├── rdc/                  ← rdc.sgdc, rdc_waiver.sgdc (SpyGlass rdc_verify_struct)
├── sdc/                  ← m_ftel_dphy_rx_wrap.sdc: clocks, exceptions, I/O budgets (design intent;
│                           also read by cdc/ and rdc/)
├── syn/                  ← synthesis (Design Compiler): run_syn.sh, dc_syn.tcl (environment, reports),
│                           summarize.sh, tech.tcl (the library, from .env), cells/ (clock cells on the
│                           library cells named in .env); work/, output/, netlist/ are generated (gitignored)
└── fpga/                 ← FPGA prototype on a Versal VP1902 board and the simulation experiments TN1 to TN3,
                            see its README
```

The lint/cdc/rdc/sdc/logical skeleton was created by the FX1 common flow
(`ip-dev/hw/utils/tool_flow`, `--tool init`, 2026-09-26). tool_flow takes the IP folder from
`FTEL_DPHY_RX_PATH` before it looks into its own `hw/rtl/ip/` layout, so it runs on this folder as it
is (`IP_DEV`: a checkout of the FX1 ip-dev repository):

```bash
export FTEL_DPHY_RX_PATH=$PWD
python3 -B $IP_DEV/hw/utils/tool_flow/bin/run_ip_tool.py --ip dphy_rx --tool <lint|cdc|rdc|vcs|vcs-run>
```

`lint` (SpyGlass `lint_rtl`, 2026-10-07: 0 Fatal / 0 Error / 0 Warning, one waiver for the clock
structure of Block No. 1, rtl_notes D-19) has been exercised; `cdc`, `rdc` and `vcs-run` come later.
VCS lint of the RTL and the directed simulation of Block No. 1:

```bash
sim/vcs_lint.sh                    # wrapper, PARA_NUM_LANES = 1, 2, 4
sim/vcs_lint.sh --module <name>    # one module with the files before it
sim/tb_afe_adapter/run.sh          # Block No. 1 at 80, 800, 1500, 1600, 1792 Mb/s
```

Synthesis with Design Compiler on the standard-cell library named in `.env`: one run per library
corner and line rate. Each run writes `syn/work/<run>/` (`dc.log`), `syn/output/<run>/` (reports)
and `syn/netlist/<run>/` (netlist, ddc, sdc). A run passes when it ends with `SYN DONE` and has no
`Error` message. Constraints and results are in `doc/rtl_notes.md` §6.

```bash
syn/run_syn.sh                                # the corners of FTEL_LIB_CORNERS, 1792 and 1500 Mb/s
syn/run_syn.sh --rate 1792 --corner <corner>  # one corner, named as in the .db files of the library
syn/summarize.sh                              # WNS/TNS, Block No. 1 paths, area per block
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
| IP folder | `22fdx/rx/digital` (this folder) |
| Module names | Every module starts with `m_` (Guideline Table 1-1): wrapper `m_ftel_dphy_rx_wrap` (IP top for tool_flow), core `m_ftel_dphy_rx`, sub-blocks `m_ftel_dphy_rx_<block>`; packages `ftel_dphy_rx[_<name>]_pkg` |
| Parameters / defines | `PARA_<NAME>` / `DEF_<NAME>` |
| Flip-flops / instances | `reg_<name>` / `u_<name>_<n>` |
| Ports | `i_` / `o_` (no `io_` in this IP); wrapper ports `<dir>_dphy_rx_<type>_<name>` (Guideline Table 1-2, IP token `dphy_rx`) |
| Resets | Active-low `_n` at the wrapper; an active-high reset gets its inverter inside the wrapper |
| Clock-domain crossing | Only through the cells `m_ftel_dphy_rx_sync` (level, port-compatible with `m_vlsi_synch`), `m_ftel_dphy_rx_tsync` (toggle) and `m_ftel_dphy_rx_rst_sync` (reset, port-compatible with `m_fpt_lib_reset_sync_rising_edge_async_reset_n`), each instance tagged `// CDC_CROSSING` |
| Clock structure | Only in `m_ftel_dphy_rx_byte_clk` (Block No. 1, HAS §4.3): inverted DDR clock, divider by 4, clock gate, gate enable from a reset synchronizer, each tagged `// CLK_STRUCT`; the cells `m_ftel_dphy_rx_cg` and `m_ftel_dphy_rx_clk_inv` keep the ports of `m_fpt_lib_cg` and `m_fpt_lib_clk_inv`, instances `u_dont_touch_*` |
| Traceability | `// REQ-xxx` on every always block, assign group and instance; `// OPEN <id> REQ-xxx: <default>` at the single place of a provisional REQ (`req/rtl_scope.json`, `req/rtm.json`) |
| Files | One module per file; file name = module name |
| File header | FTEL copyright + Evolution History block (`FTEL_signature.md` at the repository root), in the form used by `ftel_intctl` |
| Generated output | Never committed — see `.gitignore` of this folder |

---

## Environment Setup

What depends on the local installation and must not be published (the standard-cell library of the
target technology, the reference design of the FPGA board) is read from `.env` in this folder, which
is never committed. `.env.example` lists every variable with a placeholder and says what it must hold:

```bash
cp .env.example .env                                  # then replace each placeholder with the local value
export FTEL_DPHY_RX_PATH=<path of 22fdx/rx/digital>   # read by the filelists and by tool_flow
export VERDI_HOME=/opt/synopsys/verdi/X-2025.06
```

`syn/run_syn.sh` stops and names the missing variable when `.env` is incomplete.

### Tools

| Tool | Version installed | Purpose |
|---|---|---|
| VCS | X-2025.06 | Simulation |
| Verdi | X-2025.06 | Waveform viewing |
| SpyGlass | X-2025.06-SP2 | Lint / CDC / RDC |
| Design Compiler | X-2025.06-SP5 | Synthesis |
