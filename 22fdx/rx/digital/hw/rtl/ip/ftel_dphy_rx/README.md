# ftel_dphy_rx — Developer Guide

MIPI D-PHY receiver controller: receives one clock lane and up to four data lanes and
presents the received data on the PHY-Protocol Interface (PPI) toward a CSI-2 receiver.

> Status (2026-09-26): architecture draft — [`doc/spec.md`](doc/spec.md) is HAS **draft v0.4**
> (open items in its chapter 9). Research, change analysis and sync-up lists are in
> [`doc/DPHY_RX_RESEARCH_PLAN.md`](doc/DPHY_RX_RESEARCH_PLAN.md); the requirement-to-RTL flow is
> planned in [`doc/RTL_FLOW_PLAN.md`](doc/RTL_FLOW_PLAN.md). No RTL has been written yet.

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
├── doc/
│   ├── spec.md           ← architecture specification (HAS), draft v0.8 (source of the docx)
│   ├── md2docx.py        ← spec.md → FTEL_IP_MIPI_D-PHY_RX_HAS_v<x.y>.docx in the FTEL HAS format
│   ├── FTEL_IP_MIPI_D-PHY_RX_HAS_v0.8.docx ← HAS as a Word document (built, do not edit by hand)
│   ├── DPHY_RX_RESEARCH_PLAN.md ← research, change analysis, sync-up lists, plan
│   ├── RTL_FLOW_PLAN.md  ← requirement-to-RTL flow (adapted [reference rule set] flow), stages and gates
│   ├── sync/             ← question lists for the CSI team, the Tx side and the AFE team
│   └── figures/          ← diagrams referenced by spec.md (drawio / WaveJSON sources + SVG/PNG)
├── req/                  ← requirement artifacts of the flow (structured_spec.json, reviews, RTM)
├── logical/              ← RTL (flat) + filelist.f / filelist_sim.f / filelist_netlist.f
├── sim/                  ← testbenches, BFM, models
├── lint/                 ← lint_constraint.tcl, lint_waiver.tcl (SpyGlass lint_rtl)
├── cdc/                  ← cdc.sgdc, cdc_waiver.sgdc (SpyGlass cdc_verify)
├── rdc/                  ← rdc.sgdc, rdc_waiver.sgdc (SpyGlass rdc_verify_struct)
├── sdc/                  ← m_ftel_dphy_rx_wrap.sdc
└── syn/                  ← synthesis (Design Compiler)
```

The lint/cdc/rdc/sdc/logical skeleton was created by the FX1 common flow
(`ip-dev/hw/utils/tool_flow`, `--tool init`). Run it on this repository with `REPO_ROOT`:

```bash
REPO_ROOT=/home/linhhk/Documents/DPHY \
  python3 -B /home/linhhk/Documents/ip-dev/hw/utils/tool_flow/bin/run_ip_tool.py --ip dphy_rx --tool <init|lint|cdc|rdc|vcs|vcs-run>
```

Only `init` has been exercised so far (2026-09-26); the other tools are verified once RTL exists.

---

## Coding Conventions

FX1 conventions: the IP Wrapper Guideline
(`~/Documents/FX1_ips/Common_Info/IP_Wrapper_Guideline.pdf`, Tables 1-1 and 1-2) and the ip-dev
project settings (`ip-dev/hw/utils/tool_flow/config/project.yaml`). The complete rule set will be
written in `doc/rtl_rule.md` before any RTL (RTL_FLOW_PLAN Stage B).

| Item | Convention |
|---|---|
| Language | SystemVerilog (`.sv`), synthesizable subset; `always_ff` / `always_comb` only |
| IP folder | `hw/rtl/ip/ftel_dphy_rx` |
| Module names | Wrapper `m_ftel_dphy_rx_wrap` (IP top for tool_flow), core `ftel_dphy_rx`, sub-blocks `ftel_dphy_rx_<block>` |
| Parameters / defines | `PARA_<NAME>` / `DEF_<NAME>` |
| Flip-flops / instances | `reg_<name>` / `u_<name>_<n>` |
| Ports | `i_` / `o_` / `io_`; wrapper ports `<dir>_<ip>_<type>_<name>` (Guideline Table 1-2) |
| Resets | Active-low `_n` at the wrapper; an active-high reset gets its inverter inside the wrapper |
| Clock-domain crossing | Only through `ftel_dphy_rx_sync`, port-compatible with `m_vlsi_synch` (as `ftel_intctl`) |
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
