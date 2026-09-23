# m_fpt_dphy_rx — Developer Guide

MIPI D-PHY receiver controller: receives one clock lane and up to four data lanes and
presents the received data on the PHY-Protocol Interface (PPI) toward a CSI-2 receiver.

> Status (2026-09-23): directory structure only. The architecture specification
> (`doc/spec.md`) is the next deliverable; no RTL has been written yet.

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
| MIPI CSI-2 v1.3 | [`../../ref/spec/MIPI_CSI-2_Spec_V1.3.pdf`](../../ref/spec/MIPI_CSI-2_Spec_V1.3.pdf) | Source of truth for transmitter behaviour and Rx requirements (§7 Physical Layer) |
| MIPI D-PHY v1.1 | [`../../ref/spec/mipi_D-PHY_specification_v1-1.pdf`](../../ref/spec/mipi_D-PHY_specification_v1-1.pdf) | SoT/EoT sequences (§6.4), timing parameters (Table 14), PPI (Annex A) |
| Example Tx model | [`../../ref/mipi_tx_dphy_model/`](../../ref/mipi_tx_dphy_model/) | Illustrative stimulus only — not the real transmitter |

CSI-2 v1.3 requires D-PHY **v1.2**, which is not available here. Features that only exist
in v1.2 (data rates above 1.5 Gbps, the deskew calibration sequence) are defined in
`doc/spec.md` as explicit design decisions.

---

## Directory Structure

```
dphy_rx/
├── README.md          ← this file
├── doc/
│   ├── spec.md        ← architecture specification (HAS), next deliverable
│   └── figures/       ← diagrams referenced by spec.md (SVG + PNG)
├── logical/           ← RTL source (flat — all .sv at the same level) + filelist.f
├── sim/               ← testbenches tb_*.sv + Makefile (VCS)
├── lint/              ← SpyGlass lint
├── cdc/               ← SpyGlass CDC
├── rdc/               ← SpyGlass RDC
├── sdc/               ← timing constraints
└── syn/               ← synthesis (Design Compiler)
```

Empty directories are kept in git with a `.gitkeep` file.

---

## Coding Conventions

| Item | Convention |
|---|---|
| Language | SystemVerilog (`.sv`) |
| Module names | `m_fpt_dphy_rx` for the top, `m_fpt_dphy_rx_<block>` for sub-blocks |
| Files | One module per file; file name = module name |
| Ports | `i_` prefix for inputs, `o_` prefix for outputs |
| File header | FPT copyright + Evolution History block, identical in form to `ip/dbg` |
| Generated output | Never committed — see the repository `.gitignore` |

---

## Environment Setup

```bash
export RTL_HOME=/home/linhhk/Documents/DPHY/ip
export DPHY_RX_PATH=$RTL_HOME/dphy_rx
export VERDI_HOME=/opt/synopsys/verdi/X-2025.06
```

### Tools

| Tool | Version installed | Purpose |
|---|---|---|
| VCS | X-2025.06 | Simulation |
| Verdi | X-2025.06 | Waveform viewing |
| SpyGlass | X-2025.06-SP2 | Lint / CDC / RDC |
| Design Compiler | X-2025.06-SP5 | Synthesis |
