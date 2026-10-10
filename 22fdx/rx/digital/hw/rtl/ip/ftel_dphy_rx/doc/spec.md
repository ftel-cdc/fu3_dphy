# ftel_dphy_rx — MIPI D-PHY Receiver High-Level Architecture Specification

**DRAFT v0.15** — architecture level. Items that are not yet agreed are marked **OPEN** with the
default assumption used by this draft; they are tracked in chapter 9.

## Revision and History

| Version | Date | Author | Description of Change |
|---|---|---|---|
| v0.1 (draft) | 2026-09-25 | Ho Khanh Linh | First draft: block partitioning, PPI contract, lane/clock-lane behaviour, open decisions |
| v0.2 (draft) | 2026-09-25 | Ho Khanh Linh | §1 restructured: system context across the two chips (1.1), layer view (1.2), data versus control direction (1.3) |
| v0.3 (draft) | 2026-09-26 | Ho Khanh Linh | Renamed to the FX1 naming convention: IP `ftel_dphy_rx` (wrapper `m_ftel_dphy_rx_wrap`), synthesis parameters prefixed `PARA_`; no technical change |
| v0.4 (draft) | 2026-09-26 | Ho Khanh Linh | Clarifications from the requirement review: sync-search window and start, output gating while the byte clock is stopped, run-time deskew bypass field, LP-path polarity and lane map, FSM precedence and aborted requests, escape-watchdog scope, rate-dependent settle values; new open items K8 and ADR-004; S5 and K6 extended; `errsyncesc_x` tie-off linked to K2; C1 traced; marker 🌐 defined |
| v0.5 (draft) | 2026-09-29 | Ho Khanh Linh | Drawn figures replace the ASCII block sketch: D-PHY lane modules and where each of their functions is implemented (§2.1, Figures 2-1 to 2-3), top level (§2.2, Figure 2-4); synchronization of `afe_cl_clk_active` made explicit (§4.1, §4.3) |
| v0.6 (draft) | 2026-09-29 | Ho Khanh Linh | Block figures down to standard elements (Figures 4-1 to 4-13). Text made explicit where the drawing needed it: synchronizer cells and reset synchronizers (§4.1, §4.2), LP filter rule, lane-map direction and clock-lane polarity (§4.3), FSM outputs per state and LP-11 exceptions, CL_WAIT for aborted requests (§4.4, §4.5), escape decoding and trigger bit order (§4.5), sync-search and deskew-detection details, delay-line flags and EoT cut (§4.6), TINIT counters, `init_done` and watchdogs (§4.7), output gating (§4.9), status path (§4.10); status crossing added and "settle done" removed (§4.1); new run-time field `eot_skip_bytes`; ADR-006 reopened: the lane keeps waiting for EoT done (not waiting noted as the faster option), the cut below ~270 Mb/s and the order of `stopstate_x` and `rxactivehs_x` at the PPI stay open |
| v0.7 (draft) | 2026-09-29 | Ho Khanh Linh | HAS document format (Word version built from this document): the §1 sketches become Figures 1-1 to 1-3, every table gets a numbered caption, the signal-naming note moves into §1, Appendix C lists the acronyms; no technical change |
| v0.8 (draft) | 2026-09-30 | Ho Khanh Linh | Timing diagrams: PPI of a data lane and of the clock lane (§5.1, Figures 5-1 to 5-8), SoT and EoT at the AFE interface (§5.2, Figure 5-9). Gaps found while drawing them: CL_HS_TERM also waits for clock activity, so `cl_rxclkactivehs` means a running `rxbyteclkhs` (§4.4); the sync search stops at its limit and after a deskew detection, and the timing of `rxskewcalhs_x` at the PPI (§4.6); the EoT delay line needs a continuous clock (§1.4, §4.6); new open item ADR-007, start of the sync search at low rates and during THS-PREPARE (§4.6, chapter 7) |
| v0.9 (draft) | 2026-10-02 | Ho Khanh Linh | ADR-007 decided, option D: the sync search starts at DL_HS_RX, the end of THS-SETTLE, and Block No. 4 ignores the words received before it (§4.5, §4.6); `hs_settle_cyc` is placed from the AFE word latency Λ (§5.2, Appendix B). Decided with a bit-level model (chapter 7), which also corrects v0.8: a quiet AFE causes no leader loss at low rates, because the data path is delayed about as much as the HS entry signal; AFE words before THS-SETTLE,min were not ignored, so `hs_settle_cyc` had no effect on the search; the v0.8 formula of option C was wrong. Behaviour after a corrupted leader stated (§4.6); S5 no longer asks for the maximum THS-ZERO |
| v0.10 (draft) | 2026-10-02 | Ho Khanh Linh | Standalone document: references to other documents and files removed. The baseline standards are named in §1.5 without clause numbers, and the content taken from them is stated here (escape entry commands, Table 4-6); Appendix A states the requirements Q1 to Q9 of the standards and C1 to C16 of the CSI-2 Rx controller; chapter 7 describes the model behind ADR-007; S9, cited in §4.3, is added to the open items; no technical change |
| v0.11 (draft) | 2026-10-02 | Ho Khanh Linh | Ambiguities found by the review of v0.9 resolved. A rising `forcerxmode_x` restarts initialization and no longer holds the lane, so the controller can observe Stop state (§4.2, §4.5, §4.7). `rxbyteclkhs` is the DDR clock divided by 4, line rate / 8. Block No. 3 sends Block No. 4 one signal, the sync-search start: its fall is the EoT request and it sets the active flag, so the crossings cannot arrive out of order and an aborted HS entry gives no `rxactivehs_x` (§4.1, §4.5, §4.6). New state DL_HS_WAIT: after an EoT during which the line showed LP-00 the lane waits for LP-11 (§4.5). EoT without a transition, and `errsotsynchs_x` at the end of a burst that ends before a lock (§4.6). Disabling a lane clears its Block No. 4 (§4.2, §4.9). Lane-map reset value and rule for a map that is not a permutation (§4.3). LP detection and termination-enable latencies stated per parameter, AFE budget corrected (§4.3, §5.2, Appendix B); `clk_settle_cyc` 33; `PARA_EOT_DELAY_BYTES` 36 in R2. Clock after the last burst: new open item S12 and Appendix B row TCLK-POST (§4.6) |
| v0.12 (draft) | 2026-10-03 | Ho Khanh Linh | AFE boundary stated explicitly, as announced by the AFE team (ADR-001 option B): the AFE samples the HS bits and cuts them into 8-bit words at an arbitrary boundary; this IP finds the byte boundary from the SoT leader and completes the deserialization (§1, §1.1, §1.4, §2.1, §4.3, §4.6, §5.2, chapter 7, chapter 9, Appendix C). ADR-001 stays open for the interface details: one byte clock for all lanes, word timing and latency, clock-activity detection, termination timing, delay taps and LP glitch width. No technical change |
| v0.13 (draft) | 2026-10-06 | Ho Khanh Linh | AFE boundary corrected, as announced by the AFE team (ADR-001 option A): the AFE contains the HS-RX, the LP-RX and the switched termination only; v0.12 had read the announcement of 2026-10-03 as option B (sampler and 1:8 deserializer in the AFE). This IP now samples the HS bits on both edges of the DDR clock, deserializes them 1:8, generates `rxbyteclkhs` through a clock gate and detects the clock activity for TCLK-MISS (Block No. 1, §4.3). The AFE interface carries one unsampled bit stream per data lane and the DDR clock (§5.2); the word latency Λ is set by Block No. 1. New design notes: why the termination stays switched by this IP, and the sampler timing, whose sign-off corners are open (§4.3, ADR-001). Clocks and crossings (§4.1), start of `rxbyteclkhs` (§4.2), deskew delay line (§4.8, ADR-004), Appendix B row TSETUP[RX] / THOLD[RX], and §1, §2, §5, §8, chapter 9 and Appendix C updated |
| v0.14 (draft) | 2026-10-07 | Ho Khanh Linh | Errata found while designing the RTL of Block No. 1 (§4.3). A deserializer that samples on both edges has one path of half a DDR clock period: the falling-edge parallel register takes its load phase from the rising-edge strobe of the divider through one falling-edge flip-flop; v0.13 had stated that no path was shorter than one period. The margin of that path is added to the design note on the sampler timing: about 110 ps at 1500 Mb/s and none at 1792 Mb/s, at 1.35 V and 125 °C. The byte-clock divider and the load phase are held in reset while the clock gate is closed, so `rxbyteclkhs` is Low while the gate is closed and restarts with a complete pulse (§4.1, §4.2). Both clock-activity toggles run on the rising edge of the DDR clock, one changing on every edge and one on every fourth edge, independent of the divider (§4.1). The HS path registers each word in two stages, which set Λ = 2. The loss of the clock is stated as an upper bound: `cl_rxclkactivehs` falls at most 60 ns after the last clock edge; the range of 50–60 ns did not hold at the lowest rates, where the last edge is a falling edge half a period after the last toggle change, nor where a toggle aliases (§4.3, §4.4, §5.1, Appendix B). Interfaces unchanged |
| v0.15 (draft) | 2026-10-10 | Ho Khanh Linh | Timing figures moved from the 130 nm cells assumed until v0.14 to 22 nm cells, the node of the target: sampler aperture, clock buffers, the window left for the clock-to-data delay differences and the half-period path, now from a trial synthesis (§4.3 design note); the steps of a standard-cell delay line (§4.8); the basis of the timing score of ADR-001. The 1.2 V, 175 °C corner of the 130 nm cells no longer applies, and the half-period path at 1792 Mb/s is no longer an open risk. The samplers stay hand-placed. The cell library, its body bias and the sign-off corners are open items (chapter 9). No behaviour, interface or figure changes |

## Conventions

| Mark | Meaning |
|---|---|
| ✅ | Required by a baseline standard, [1] or [2] (§1.5), and checked against it |
| **[CSI]** | Requirement of the CSI-2 Rx controller, the user of the PPI (C1 to C16, Appendix A) |
| ⚠️ | Assumption or proposal of this draft, not yet agreed |
| 🌐 | Taken from a public secondary source (§1.5); not confirmed by the baseline standards |
| **OPEN Kx / Sx / ADR-nnn** | Open point; see chapter 7 (decisions) and chapter 9 (open items) |

## Table of Contents

- [1. Overview](#1-overview)
- [2. Block Diagram](#2-block-diagram)
- [3. Parameters](#3-parameters)
- [4. Functions](#4-functions)
- [5. Interfaces](#5-interfaces)
- [6. Registers](#6-registers)
- [7. Design Decisions](#7-design-decisions)
- [8. Verification Requirement](#8-verification-requirement)
- [9. Open Items](#9-open-items)
- [Appendix A. Requirement Traceability](#appendix-a-requirement-traceability)
- [Appendix B. Receiver Timing Parameters](#appendix-b-receiver-timing-parameters)
- [Appendix C. Acronyms](#appendix-c-acronyms)

---

## 1. Overview

`ftel_dphy_rx` is the digital controller of a MIPI D-PHY receiver. On the physical signal path it
sits **after** the analog front-end (AFE: HS-RX, LP-RX and termination) and **before** the CSI-2 Rx
controller, to which it presents the received lanes on the PHY-Protocol Interface (PPI). The CSI-2
Rx controller calls it the "D-PHY macro".

**Who deserializes.** This IP deserializes the HS data, as announced by the AFE team:
- The AFE contains the line receivers and the termination only. Its HS-RX outputs are one bit
  stream per data lane, not sampled, and the DDR clock of the clock lane.
- This IP samples the bits on both edges of the DDR clock, cuts them into 8-bit words and generates
  the byte clock (Block No. 1, §4.3). It then finds the byte boundary from the SoT leader, aligns the
  words into bytes (Block No. 4, §4.6) and presents the bytes on the PPI.
- Line-state decoding, the HS-RX and termination enables, SoT and EoT handling and escape mode are
  in this IP too. The AFE cannot enable its termination on its own: only the sequence of line states
  tells an HS request from an escape entry (§4.3).

Signal names ending in `_x` exist once per data lane. Unless stated otherwise, signals are active High.

### 1.1 System context — physical signal path

![Figure 1-1 — system context: physical signal path from the sensor to the ISP](figures/ftel_dphy_rx_system.svg)

**Table 1-1 — Elements on the physical signal path**

| Element | Location | Function | Owner |
|---|---|---|---|
| CSI-2 Tx protocol | Sensor chip | Builds packets (header, ECC, payload, CRC) and distributes bytes over the lanes | Sensor vendor / Tx side |
| D-PHY Tx | Sensor chip | Serializes bytes, drives the HS and LP line levels, performs SoT/EoT, drives the clock lane | Sensor vendor / Tx side |
| Lanes | PCB | One differential clock lane and 1, 2 or 4 differential data lanes | Board |
| AFE | Receiving chip, at the pins | Receives the analog line levels — HS: \|VOD\| 140–270 mV around a ~200 mV common mode; LP: 1.1–1.3 V single-ended (D-PHY [1] ✅) — plus the termination, switched on request; outputs the HS bits unsampled, one wire per data lane, and the DDR clock of the clock lane | Analog team |
| `ftel_dphy_rx` | Receiving chip | Sampling and 1:8 deserialization of the HS bits, byte clock, line-state FSMs, SoT sync and byte alignment, EoT, escape/ULPS, errors; outputs aligned bytes on the PPI | This IP |
| CSI-2 Rx controller | Receiving chip | Lane merging, header ECC, payload CRC, frame handling, pixel unpacking | CSI team |

The order AFE → D-PHY Rx → CSI-2 Rx is fixed by what each stage needs as input:
- Only analog circuits can receive the line levels, so the AFE must be at the pins.
- The D-PHY Rx turns line states and the HS bit streams into aligned bytes.
- The CSI-2 Rx controller needs bytes to parse packet headers and check ECC/CRC.

Basis:
- CSI-2 [2] ✅ draws the same chain: pins Cp/Cn, Dxp/Dxn → D-PHY (CIL-SCNN / CIL-SFEN) → PPI → lane merger → protocol.
- The CSI-2 Rx controller does not connect to the image sensor: the sensor drives the D-PHY lanes,
  and this IP presents the recovered byte streams to the controller over the PPI **[CSI]**.

### 1.2 Layer view — why "CSI-2 Tx talks to CSI-2 Rx"

![Figure 1-2 — layer view: CSI-2 Tx and CSI-2 Rx are logical peers](figures/ftel_dphy_rx_layers.svg)

- **Logical peers.** The CSI-2 transmitter and receiver are peers: both follow the packet format of
  CSI-2 v1.3 (header, ECC, CRC). This is why they are often described as "connected".
- **Physical path.** There is no direct wire between them. A packet goes down the Tx stack
  (protocol → PPI → D-PHY Tx), crosses the lanes, and goes up the Rx stack (AFE → D-PHY Rx → PPI →
  protocol).
- **Basis.** In CSI-2 [2] ✅ the lane management layer of the protocol interfaces with the D-PHY, and
  D-PHY [1] ✅ defines the PPI as the logical PHY-Protocol interface of each lane towards the
  protocol.

### 1.3 Data direction versus control direction

The CSI-2 Rx controller **controls** this IP, while this IP **delivers data** to the controller.
Because the controller's registers drive the D-PHY enables and reset, a register-level view can
make the controller look as if it were "in front of" the D-PHY. The data path runs the other way.

![Figure 1-3 — data direction versus control direction](figures/ftel_dphy_rx_directions.svg)

**Table 1-2 — Data, control, clock and configuration paths**

| Path | Direction | Signals | Reference |
|---|---|---|---|
| Received data and lane status | AFE → `ftel_dphy_rx` → CSI-2 Rx controller | `rxbyteclkhs`, `rxdatahs_x`, `rxvalidhs_x`, `rxactivehs_x`, `rxsynchs_x`, `rxskewcalhs_x`, Stop / ULPS / trigger / error indications, `init_done` | Inputs of the CSI-2 Rx controller **[CSI]** |
| Link control | CSI-2 Rx controller → `ftel_dphy_rx` | `cl_enable`, `dl_enable_x`, `forcerxmode_x`, `phy_core_rst` | Outputs of the controller, driven from its registers **[CSI]** |
| AFE control | `ftel_dphy_rx` → AFE | HS-RX enable, termination enable, delay taps | §5.2 |
| Reference clock | System → `ftel_dphy_rx` | `core_clk` (200 MHz) | System clock **[CSI]** |
| Timer configuration | Configuration bus → `ftel_dphy_rx` | Timer values, lane map, polarity | §4.10, OPEN K3 |

### 1.4 Baselines, release plan and features

**Baselines.**
- MIPI CSI-2 v1.3 [2] ✅ sets the minimum D-PHY feature set of a CSI-2 receiver.
- D-PHY behaviour follows D-PHY v1.1 [1] ✅. The only D-PHY v1.2 feature needed is the deskew
  calibration, required above 1.5 Gb/s **[CSI]** C4. The v1.2 specification is not available to this
  project; the deskew items are therefore design decisions (ADR-004).

**Table 1-3 — Release plan (proposed, OPEN K1)**

| Release | Line rate per lane | Deskew | Target use |
|---|---|---|---|
| R1 | 80–1500 Mb/s | Deskew burst **detected** and flagged on `rxskewcalhs_x`; no calibration | OS04C10 (750 Mb/s), 4K single exposure |
| R2 | 80–1792 Mb/s | Calibration active (Block No. 5) | 4K staggered HDR RAW12 **[CSI]** C4 |

**Features.**
- One clock lane and 1, 2 or 4 data lanes (`PARA_NUM_LANES` = 4) **[CSI]** C2.
- PPI with an 8-bit data path per lane on one shared `rxbyteclkhs` = line rate / 8, the HS DDR clock
  divided by 4 **[CSI]** C3.
- Clock lane: HS entry and exit, continuous-clock operation (mandatory, CSI-2 [2] ✅), and
  clock-lane ULPS (D-PHY [1] ✅). The clock-lane FSM also handles LP entry between bursts, but the
  EoT delay line needs `rxbyteclkhs` after each burst for longer than a non-continuous clock runs
  (§4.6 design note), so this IP needs a continuous clock ⚠️, as the system uses **[CSI]** C5. When
  the clock lane leaves HS after the last burst, the tail of that burst also needs the clock for
  longer than the minimum TCLK-POST (OPEN S12).
- Data lanes: sampling and 1:8 deserialization of the HS bits, SoT/EoT (D-PHY [1] ✅), sync
  detection with single-bit error tolerance, trailer removal, escape mode with **ULPS and Triggers**
  (D-PHY [1] ✅). Low-Power Data Transmission (LPDT) is not in R1 (OPEN K2).
- Error indications: SoT error, SoT sync error, escape entry error, false control error (D-PHY
  [1] ✅); EoT sync error as status. An HS RX timeout guarantees that `rxactivehs_x` falls while the
  byte clock runs, because the CSI-2 controller has no timeout of its own **[CSI]** C11.
- Initialization: TINIT detection and `init_done`, reset request `phy_core_rst`, per-lane enables,
  `forcerxmode_x` **[CSI]** C14, C16.
- Programmable receiver timing (THS-SETTLE, TCLK-SETTLE, TINIT, timeouts), counted in `core_clk`
  (200 MHz) **[CSI]** C15.

**Out of scope.** The CSI-2 protocol layer (packet header, ECC, CRC, pixel unpacking) is in the
CSI-2 Rx controller; this IP never parses byte content. The AFE, which holds the line receivers and
the termination only, is outside this IP; its interface is defined in §5.2 (details OPEN ADR-001).
Reverse direction, turnaround and 8b9b coding are not supported (unidirectional slave per CSI-2 [2] ✅).

### 1.5 References

This document states every rule and value it uses; the references give their origin. [1] and [2]
are the baseline standards that this IP follows; [3] is a public secondary source, used where the
baseline standards are not available to this project.

- [1] MIPI Alliance, Specification for D-PHY, version 1.1.
- [2] MIPI Alliance, Specification for Camera Serial Interface 2 (CSI-2), version 1.3.
- [3] Lattice Semiconductor, CSI-2/DSI D-PHY Rx IP User Guide, FPGA-IPUG-02081-2.1, January 2024,
  section 2.4.1: a receiver detects the D-PHY skew-calibration burst by its all-ones sync pattern;
  the detection is required above 1.5 Gb/s and ends when the lines return to LP-11.

---

## 2. Block Diagram

### 2.1 Lane modules (D-PHY reference)

D-PHY [1] ✅ describes every lane as a Universal Lane Module: a Lane Control and Interface Logic
(CIL) block between the PPI and the line-side functions HS-TX, HS-RX, LP-TX, LP-RX and LP-CD. A PHY
implements a stripped-down module per lane type, named after its functions (the letters are spelled
out for CIL-SFEN below). The slave side of a unidirectional data lane contains HS-RX, LP-RX and a
CIL-SFXN; the slave side of a clock lane contains HS-RX, LP-RX and a CIL-SCNN. CSI-2 [2] ✅ uses
CIL-SFEN for the data lanes.

- **CIL-SFEN.** Slave side, Forward-only high-speed, Escape mode with Events only (triggers and
  ULPS), No reverse escape. With LPDT (OPEN K2) the data lanes become CIL-SFAN.
- **AFE share.** Only the line-side receivers, HS-RX and LP-RX, and the switched termination are in
  the AFE, as announced by the AFE team. The data sampler and HS-Deserialize are in this IP: Block
  No. 1 samples each data lane on both edges of the clock-lane DDR clock, cuts the bits into 8-bit
  words at an arbitrary boundary and divides the DDR clock by 4 into `rxbyteclkhs`, line rate / 8;
  Block No. 4 finds the byte boundary (Table 2-1).
- **Clock lane.** It has no escape decoder: its ULPS entry is a line-state sequence handled by the
  clock-lane FSM (D-PHY [1] ✅).
- **Wires.** One clock lane and N data lanes use 2 × (N + 1) interconnect wires (D-PHY [1] ✅).

![Figure 2-1 — data lane module: Universal Lane Module reduced to CIL-SFEN](figures/ftel_dphy_rx_ulm_data.svg)

![Figure 2-2 — clock lane module: Universal Lane Module reduced to CIL-SCNN](figures/ftel_dphy_rx_ulm_clock.svg)

![Figure 2-3 — lane configuration: one clock lane and N forward-only data lanes](figures/ftel_dphy_rx_lanes.svg)

Where each function of the Universal Lane Module of D-PHY [1] is implemented:

**Table 2-1 — Universal Lane Module functions and where they are implemented**

| ULM function | Data lane (CIL-SFEN) | Clock lane (CIL-SCNN) |
|---|---|---|
| HS-RX with termination, LP-RX | AFE | AFE |
| HS-TX, LP-TX, LP-CD | Not used: unidirectional slave, no turnaround | Not used |
| TX Ctrl Logic, Esc Encoder, HS-Serialize, Sequences | Not used: transmit side | Not used |
| Data Sampler | No.1: samplers on both edges of the DDR clock | Not used: the HS-RX output is the DDR clock, which No.1 divides by 4 into `rxbyteclkhs` |
| HS-Deserialize | No.1: 1:8 at an arbitrary boundary. No.4: finds the byte boundary from the SoT leader (sync search) and aligns the bytes | Not used |
| Ctrl Decoder | No.1: synchronization, glitch filter, LP state. No.3: line-state sequences | No.1, also clock-activity detection. No.2: line-state sequences |
| Esc Decoder | No.3: ULPS and trigger commands | Not used |
| State Machine | No.3; timers and initialization in No.6 | No.2; timers and initialization in No.6 |
| Error detect | No.3: `errcontrol_x`, `erresc_x`. No.4: `errsoths_x`, `errsotsynchs_x`, EoT sync error | No.2: aborted HS request, status only (No.8) |
| Data IF logic | No.4: EoT trailer removal. No.7: PPI data outputs | Not used |
| Ctrl IF logic | No.6: `dl_enable_x`, `forcerxmode_x`. No.7: PPI outputs | No.6: `cl_enable`. No.7: PPI outputs |
| Not in the v1.1 module | No.5: deskew (D-PHY v1.2, R2). No.8: configuration and status | No.8: configuration and status |

### 2.2 Top level

![Figure 2-4 — ftel_dphy_rx top-level block diagram](figures/ftel_dphy_rx_top.svg)

Each data lane slice is the CIL-SFEN of Figure 2-1; the clock lane slice is the CIL-SCNN of
Figure 2-2. Output groups in the figure, by the Source column of §5.1:
- HS outputs: the `rxbyteclkhs` outputs from No.4.
- LP / escape outputs: the outputs from No.3, `rxclkesc_x` and the LPDT outputs tied to 0 (K2).
- Clock-lane outputs: the outputs from No.2.

**Table 2-2 — Blocks of the top level**

| Block | Name | Instances | Clock domain | Release |
|---|---|---|---|---|
| No.1 | AFE Adapter | per lane + clock lane | `core_clk` (LP path, clock activity), DDR clock (samplers, deserializer, byte-clock divider), `rxbyteclkhs` (HS path) | R1 |
| No.2 | Clock Lane Control (CIL-SCNN) | 1 | `core_clk` | R1 |
| No.3 | Data Lane Control (CIL-SFEN) | per data lane | `core_clk` | R1 |
| No.4 | HS Receive Datapath | per data lane | `rxbyteclkhs` | R1 |
| No.5 | Deskew Controller | per data lane | `rxbyteclkhs` | R2 |
| No.6 | Timing & Init Control | 1 | `core_clk` | R1 |
| No.7 | PPI Output Stage | 1 | `rxbyteclkhs` (HS signals), asynchronous (LP signals) | R1 |
| No.8 | Configuration & Status | 1 | configuration clock (OPEN K3) | R1 |

---

## 3. Parameters

Synthesis-time parameters. Values that depend on an open item show the default used by this draft.

**Table 3-1 — Synthesis parameters**

| # | Parameter | Value / formula | Type | Description |
|---|---|---|---|---|
| 1 | `PARA_NUM_LANES` | 4 | Configurable | Data lane slices instantiated: 1, 2 or 4 **[CSI]** C2. Lanes are enabled at run time by `dl_enable_x` |
| 2 | `PARA_DESER_RATIO` | 8 | Fixed | Ratio of the deserializer of Block No. 1 and width of `rxdatahs_x` **[CSI]** C3. Kept as a parameter so a 1:16 deserializer can be supported later |
| 3 | `PARA_CORE_CLK_MHZ` | 200 | Fixed | Reference clock of all timers **[CSI]** C15; resolution 5 ns |
| 4 | `PARA_DESKEW_EN` | 0 (R1), 1 (R2) | Configurable | Instantiates Block No. 5. When 0, deskew bursts are still detected (Block No. 4) |
| 5 | `PARA_LPDT_EN` | 0 | Configurable | Instantiates LPDT reception. When 0, LPDT PPI outputs are tied inactive (OPEN K2) |
| 6 | `PARA_LP_SYNC_STAGES` | 2 | Fixed | Synchronizer depth of the LP-RX inputs into `core_clk` |
| 7 | `PARA_LP_FILTER_CYC` | 2 ⚠️ | Configurable | Glitch filter on LP states, in `core_clk` cycles. Bounded by the termination-enable budget (Appendix B) and by the maximum LP glitch width passed by the AFE (OPEN ADR-001) |
| 8 | `PARA_EOT_DELAY_BYTES` | 32 (R1), 36 (R2) ⚠️ | Configurable | Depth of the EoT delay line (Block No. 4). Shall hold TEOT,max plus the LP-11 detection latency and the crossing at the highest line rate: about 30 bytes at 1500 Mb/s, 35 at 1792 Mb/s (§4.6) ⚠️. S5 confirms the Tx timing. The depth also sets the clock the Tx must supply after the last burst (S12) |
| 9 | `PARA_SYNC_SEARCH_BYTES` | 16 ⚠️ | Configurable | Byte clocks searched for the sync sequence before `errsotsynchs_x` is raised, counted from the first non-zero word after the sync-search start ⚠️ (§4.6); a burst that ends earlier without a lock raises it at its end |
| 10 | `PARA_DLY_TAP_WIDTH` | To be determined | Configurable | Width of the delay-tap control of a delay line in front of the samplers (R2, ADR-004; the AFE has none) |

Run-time programmable timing values (reset defaults; the configuration path is OPEN K3):

**Table 3-2 — Run-time timing fields**

| Field | Default | Basis |
|---|---|---|
| `hs_settle_cyc` | 19 ⚠️ | Length of DL_HS_TERM, which ends with the start of the sync search (§4.6): places that start after THS-SETTLE,min and before the first 1 of a leader sent at the minimum THS-PREPARE + THS-ZERO, for the word latency Λ of Block No. 1 (Appendix B, ADR-007); 19 at 1500 Mb/s with Λ = 2 ⚠️. Rate dependent: software programs the value of Appendix B for the line rate before enabling the lanes ⚠️ |
| `clk_settle_cyc` | 33 ⚠️ | Length of CL_HS_TERM in cycles: the centre of TCLK-SETTLE (95–300 ns → 197.5 ns) minus the entry into CL_HS_TERM, 30–35 ns after the start of LP-00 (Appendix B) |
| `tinit_cyc` | 20 000 | TINIT,SLAVE ≥ 100 µs (D-PHY [1] ✅) |
| `hs_rx_timeout_cyc` | 2^18 (1.31 ms) ⚠️ | Longer than the longest burst: 5802-byte line at 80 Mb/s on one lane ≈ 580 µs; the longest burst per lane is OPEN K8 |
| `esc_timeout_cyc` | 2^18 ⚠️ | Escape-mode watchdog (D-PHY [1] ✅, informative); scope and expiry in §4.7 |
| `eot_skip_bytes` | 16 ⚠️ | Newest delay-line entries discarded before the last-transition search (§4.6): (LP-11 detection latency ≈ 20 ns + crossing ≈ 2.5 byte clocks + centre of the cut window (40 + 60 + 4·UI) / 2 ns) / byte period; at 1500 Mb/s (20 + 13.3 + 51.3) / 5.33 ≈ 16. Rate dependent, programmed with `hs_settle_cyc` ⚠️ |

---

## 4. Functions

### 4.1 Clock

**Table 4-1 — Clocks**

| Clock | Source | Frequency | Used by | Notes |
|---|---|---|---|---|
| `core_clk` | System, free-running **[CSI]** | 200 MHz | Blocks No. 1 (LP path, clock activity), 2, 3, 6 | All LP-state, escape and timer logic. Escape reception is by oversampling (ADR-002) |
| DDR clock `afe_cl_hs_clk` | AFE: HS-RX output of the clock lane | Line rate / 2; 750 MHz at 1500 Mb/s, 896 MHz at 1792 Mb/s | Block No. 1: samplers (both edges), deserializer, byte-clock divider, clock-activity toggles | Runs only while the clock lane is in HS; its pulses during TCLK-SETTLE are ignored (§4.3) |
| `rxbyteclkhs` | Block No. 1: DDR clock / 4 through a clock gate | Line rate / 8; 187.5 MHz at 1500 Mb/s, 224 MHz at 1792 Mb/s | Blocks No. 1 (HS path), 4, 5, 7 | Runs only while the clock lane is in CL_HS_CLK (§4.3). Forwarded to the PPI as `rxbyteclkhs` **[CSI]** C3 |
| configuration clock | System | To be determined | Block No. 8 | Depends on ADR-005 (OPEN K3) |

Clock-domain crossings:

**Table 4-2 — Clock-domain crossings**

| From → To | Signals | Method |
|---|---|---|
| AFE LP-RX (asynchronous) → `core_clk` | `afe_lp_dp_x`, `afe_lp_dn_x`, `afe_cl_lp_dp`, `afe_cl_lp_dn` | `PARA_LP_SYNC_STAGES` flip-flops + `PARA_LP_FILTER_CYC` glitch filter |
| AFE HS-RX → DDR clock | `afe_hs_bit_x` | Source-synchronous: sampled on both edges of the DDR clock, which the transmitter sends centred in the bits (D-PHY [1] ✅); hand-placed samplers within the setup and hold window (§4.3) ⚠️ |
| DDR clock → `rxbyteclkhs` | Words of the deserializer of Block No. 1 | Synchronous: `rxbyteclkhs` is generated from the DDR clock, and each word is held for four DDR clock periods; timed by STA, no synchronizer ⚠️ |
| DDR clock → `core_clk` | Clock-activity toggles of Block No. 1 | Level, 2-flop synchronizers; the clock is active while one toggle has changed within the last 8 `core_clk` cycles (§4.3) ⚠️ |
| `core_clk` → DDR clock | Byte-clock enable (Block No. 2, High in CL_HS_CLK) | Reset synchronizer in the DDR clock: cleared at once when the enable falls, set on the second DDR clock edge after it rises; it enables the clock gate of `rxbyteclkhs` and releases the byte-clock divider (§4.3) ⚠️ |
| `core_clk` → `rxbyteclkhs` | Sync-search start (Block No. 3 → No. 4) | Level, 2-flop synchronizer. Block No. 4 starts the sync search on its rise and takes its fall as the EoT request, so the start, the active flag and the EoT request cannot arrive out of order ⚠️ |
| `rxbyteclkhs` → `core_clk` | EoT done (Block No. 4 → No. 3) | Toggle synchronizer |
| `core_clk`, `rxbyteclkhs` → configuration clock | Status events of Blocks No. 2, 3 and 4; lane FSM states | Events: toggle synchronizers into the flags and counters of Block No. 8 ⚠️. FSM states: 2-flop synchronizers; a read during a state change may be incoherent (debug use) ⚠️ |
| Enables (`lite_aclk`) → `core_clk` | `cl_enable`, `dl_enable_x`, `forcerxmode_x` | Level, 2-flop synchronizers; `lite_aclk` is the register clock of the CSI-2 Rx controller, and the PPI defines the enables as level sensitive **[CSI]** C14 |
| Configuration clock → `core_clk` / `rxbyteclkhs` | Timer values, lane map, polarity | Quasi-static: software changes them only while the affected lanes are disabled |
| `core_clk` → PPI outputs and Block No. 4 of the `rxbyteclkhs` domain | Synchronized lane enables | Combinational gating at the output stage (§4.9), and an asynchronous clear of Block No. 4 of the lane, released through a reset synchronizer in `rxbyteclkhs` (§4.2) ⚠️. An enable may change at any time |

The crossings use three cells (Figure 4-1):
- **Level synchronizer.** A chain of flip-flops in the destination clock: `PARA_LP_SYNC_STAGES` for the
  LP-RX inputs, 2 elsewhere.
- **Toggle synchronizer.** A one-cycle event inverts a flip-flop in the source clock. The level crosses
  through two flip-flops, and a third flip-flop with an XOR gate turns each change into a one-cycle
  pulse in the destination clock. Two events of one kind must be at least three destination cycles
  apart; each event listed above occurs at most once per burst or per LP sequence ⚠️.
- **Reset synchronizer.** §4.2. One more, in the DDR clock, sets the enable of the clock gate of
  `rxbyteclkhs` and releases the byte-clock divider (§4.3).

![Figure 4-1 — synchronizer cells: level, toggle and reset](figures/ftel_dphy_rx_sync_cells.svg)

### 4.2 Reset

**Table 4-3 — Reset controls**

| Control | Type | Scope | Behaviour |
|---|---|---|---|
| `phy_core_rst` | Input, asynchronous assert, synchronous release per domain | Whole IP | Asserted ≥ 40 `core_clk` cycles by the CSI-2 controller **[CSI]** C14. On release every lane restarts initialization (§4.7). Polarity and synchronicity OPEN K6; draft assumes active High, asynchronous |
| `cl_enable`, `dl_enable_x` | Input, level | One lane | Low: the lane is shut down — AFE enables off, lane FSM held in reset, PPI outputs of the lane at their inactive values (Enable of the PPI, D-PHY [1] ✅). Block No. 4 of a data lane is cleared while its `dl_enable_x` or `cl_enable` is Low, so a burst cut by a disable is not delivered later ⚠️ |
| `forcerxmode_x` | Input, level | One data lane | Rising edge: the lane FSM returns to DL_INIT immediately and re-initializes; it reaches DL_STOP after LP-11 held for `tinit_cyc`, also while `forcerxmode_x` stays High, so the controller can observe Stop state for TINIT before it releases the signal (D-PHY [1] ✅: the lane waits for a Stop state) ⚠️. Asserted only while the lane is in Stop state **[CSI]**; exact semantics OPEN K6 |

Each clock domain has a reset synchronizer in Block No. 6 (Figure 4-1): `phy_core_rst` clears its two
flip-flops asynchronously. The second flip-flop is the active-low reset of the domain, released on the
second clock edge after `phy_core_rst` falls. The `rxbyteclkhs` domain therefore leaves reset only when
the byte clock runs. The clock lane is in HS before any data lane leaves Stop (TCLK-PRE, D-PHY
[1] ✅), so Block No. 4 is out of reset before its first burst ⚠️: at 80 Mb/s `rxbyteclkhs` starts at
most about 190 ns after the first clock edge (clock-activity detection and clock gate, §4.3) and
Block No. 4 is released two byte clocks later, before a data lane that starts its HS request at the
minimum TCLK-PRE can enter DL_HS_RX. The DDR-clock domain (clock-activity toggles of Block No. 1)
likewise leaves reset on the second DDR clock edge. The byte-clock divider and the load phase of the
deserializer are held in reset while the clock gate of `rxbyteclkhs` is closed (§4.3); the samplers,
shift registers and parallel registers of the deserializer hold data only and have no reset ⚠️.
Block No. 4 of each data lane has one more reset synchronizer in `rxbyteclkhs`, cleared also while
the synchronized `dl_enable_x` or `cl_enable` is Low; it is released on the second byte-clock edge
after the lane is enabled ⚠️.

### 4.3 AFE Adapter (Block No. 1)

**Overview.** Isolates the rest of the IP from the AFE, and holds what the AFE does not do: the
samplers, the 1:8 deserializer, the byte clock and the clock-activity detection (§1). It is the
only block that changes when the AFE changes.

**Function** (Figure 4-2).
- LP path: synchronizes each LP-RX output into `core_clk` (`PARA_LP_SYNC_STAGES` flip-flops), swaps
  Dp and Dn when the polarity bit of the physical lane is set, filters the 2-bit line state and
  presents one of LP-11, LP-10, LP-01, LP-00 per lane. The filter accepts a new state once it has
  been sampled `PARA_LP_FILTER_CYC` + 1 times in a row (Figure 4-3): at the LP-RX output a state
  shorter than `PARA_LP_FILTER_CYC` cycles is always ignored, and one of `PARA_LP_FILTER_CYC` + 1
  cycles or longer is always accepted ⚠️. The LP state follows a change at the LP-RX output after
  (`PARA_LP_SYNC_STAGES` + `PARA_LP_FILTER_CYC`) cycles plus a sampling delay of 0 to 1 cycle: the LP
  detection latency, 20–25 ns with the defaults, one cycle more when the first synchronizer flip-flop
  resolves late ⚠️.
- HS deserializer, one per physical data lane, clocked by the DDR clock `afe_cl_hs_clk` ⚠️:
  - Samplers: a flip-flop on the rising edge and one on the falling edge of the DDR clock sample
    `afe_hs_bit_x`. The transmitter places each clock edge in the middle of a bit (D-PHY [1] ✅), so
    the two flip-flops take alternate bits. They are hand-placed with their clock buffers (design
    note below).
  - Each sampler shifts into a 4-bit shift register on its own clock edge. Once every four DDR clock
    periods, at a phase set by the byte-clock divider, a parallel register per edge takes the four
    bits. The two parallel registers together hold 8 consecutive bits, interleaved in the order
    received, bit 0 received first: the word of the lane.
  - The word boundary is where the divider happens to be, not where the bytes of the burst begin;
    Block No. 4 finds the byte boundary (§4.6). The words of all lanes are cut at the same time.
  - Each sampler, shift register and parallel register works on one edge of the DDR clock. The load
    phase of the parallel registers is a strobe of the divider on the rising edge; the falling-edge
    parallel register takes it through one flip-flop on the falling edge, half a DDR clock period
    later. The path into that flip-flop is the only one of the deserializer shorter than one DDR
    clock period (design note on the sampler timing) ⚠️. The parallel registers hold each word for
    four DDR clock periods, so its transfer into `rxbyteclkhs` has several DDR clock periods ⚠️.
- Byte clock: a divider by 4 of the DDR clock gives line rate / 8. A clock gate passes it as
  `rxbyteclkhs` only while the clock lane is in CL_HS_CLK (Block No. 2). The gate enable is cleared
  at once when the clock lane leaves CL_HS_CLK and set two DDR clock edges after it enters it (reset
  synchronizer, §4.1), so `rxbyteclkhs` starts within about one byte clock after `cl_rxclkactivehs`
  rises ⚠️. While the gate enable is cleared, the divider and the load phase are held in reset:
  `rxbyteclkhs` is Low while the gate is closed, even when the DDR clock stopped in the high half of
  the divided clock, and its first pulse after the gate opens is complete ⚠️. Pulses at the HS-RX
  output while the clock lane starts or leaves HS never reach `rxbyteclkhs`; D-PHY [1] ✅ lets the
  receiver ignore the clock-lane transitions during TCLK-SETTLE.
- Clock activity, for Block No. 2: two toggle flip-flops on the rising edge of the DDR clock, one
  that changes on every edge (line rate / 4) and one that changes on every fourth edge (line
  rate / 16). They run whenever the DDR clock runs, independent of the clock gate and the divider.
  Each crosses into `core_clk` through a 2-flop synchronizer. The clock is active while one of them
  has changed within the last 8 `core_clk` cycles (40 ns), and inactive otherwise ⚠️.
  - The loss of the clock is seen 45–55 ns after the last toggle change that `core_clk` sees: the
    last rising edge of the DDR clock, or up to three DDR clock periods earlier where the toggle of
    every edge aliases. `cl_rxclkactivehs` falls one `core_clk` cycle later, at most 60 ns after the
    last clock edge, so within TCLK-MISS (60 ns) at every rate ⚠️.
  - Two toggles are needed because `core_clk` (200 MHz) sees a toggle whose frequency is near a
    multiple of 200 MHz as almost constant: line rate / 4 is 200 MHz at 800 Mb/s and 400 MHz at
    1600 Mb/s, where line rate / 16 is 50 and 100 MHz. At 80 Mb/s the toggle of every edge changes
    every 25 ns ⚠️.
- HS path: registers the word of each lane on `rxbyteclkhs` in two stages, which set the word
  latency Λ = 2 (§5.2), and inverts all its bits when the polarity bit of the physical lane is set
  (P/N polarity inversion). Alignment is done in Block No. 4.
- Lane mapping: one configuration field per logical lane selects its physical lane, for the LP
  path and the HS path alike. At reset each logical lane selects the physical lane of the same number
  and every polarity bit is 0 ⚠️. Software programs a permutation. The AFE enables of a physical lane
  are the OR of the requests of the logical lanes that select it, so a physical lane that no logical
  lane selects has its enables off; its delay taps come from the lowest-numbered logical lane that
  selects it ⚠️. The clock lane is neither inverted nor remapped ⚠️ (S9).
- Drives the AFE controls requested by Blocks No. 2, 3 and 5: HS-RX enable, termination enable,
  delay taps (R2). The FSM outputs `hs_en_x`, `term_en_x`, `cl_hs_en` and `cl_term_en` are internal
  requests, driven by registers; this block passes them to the AFE ports `afe_*` of §5.2 through the
  lane mapping without a further register, so the enable timing of Appendix B is unchanged ⚠️.

![Figure 4-2 — Block No. 1, AFE Adapter: LP path, HS deserializer, byte clock and clock activity](figures/ftel_dphy_rx_afe_adapter.svg)

![Figure 4-3 — LP glitch filter of Block No. 1](figures/ftel_dphy_rx_lp_filter.svg)

**Design note ⚠️.** TD-TERM-EN (≤ 35 ns + 4·UI) and TCLK-TERM-EN (≤ 38 ns) are measured from the
LP-00 crossing at the line. The termination enable is issued without an extra timer, by the register
of the FSM state entered on LP-00: 25–30 ns after the LP-RX output changes with the defaults (the LP
detection latency plus one cycle). The AFE then has 5–10 ns + 4·UI on a data lane and 8–13 ns on the
clock lane for its LP-RX delay and the termination switch, 5 ns less when the first synchronizer
flip-flop resolves late. If the AFE cannot meet this budget, `PARA_LP_FILTER_CYC` is reduced
(Appendix B) ⚠️. The AFE cannot switch the termination on its own: an HS request is the sequence
LP-11, LP-01, LP-00, while an escape entry, LP-11, LP-10, LP-00, LP-01, LP-00, also passes from
LP-01 to LP-00, and ULPS holds LP-00 (D-PHY [1] ✅). Only the line-state sequence of the lane FSM
tells them apart; a termination switched on LP-00 alone would load the lines during escape mode.

**Design note ⚠️ (sampler timing, OPEN ADR-001).** D-PHY [1] ✅ gives the receiver a setup and hold
window of 0.3·UI when its maximum rate is 1 Gb/s and of 0.4·UI above: 300 ps at 1 Gb/s, 267 ps at
1500 Mb/s, 223 ps at 1792 Mb/s (Appendix B). The window has to hold the aperture of the sampling
flip-flop (setup plus hold) and every difference between the clock and data delays from the AFE
inputs to the samplers: the HS-RX of the AFE, the wiring and the clock buffers of this IP.
- With the 22 nm standard cells assumed for this IP (core supply 0.8 V), the aperture of a D
  flip-flop is about 20 ps in the fast corner (0.88 V, −40 °C) and 35 ps in the slow corner (0.72 V,
  125 °C); one clock buffer takes about 15–20 ps in the fast corner and 25–30 ps in the slow one ⚠️.
- A clock tree of three buffer levels built by the usual flow varies by about 30 ps over the
  corners, and its whole delay, 45–90 ps, falls on one side of the window unless the data inputs are
  delayed to match. The samplers, the buffers of the DDR clock that drive them and the data inputs to
  them are therefore placed by hand next to the AFE, with the clock and data paths built from the
  same cells so that their delays track; the rest of the IP uses the usual flow ⚠️.
- In the slow corner this leaves about ±115 ps at 1500 Mb/s, ±95 ps at 1792 Mb/s and ±130 ps at
  1 Gb/s for the clock-to-data delay differences of the AFE and of this IP together, the duty-cycle
  error of the DDR clock included.
- The load phase of the falling-edge parallel register is the one path of half a DDR clock period
  (deserializer above). Half a period, plus the delay of the clock inverter of the falling edge, has
  to hold the clock-to-output delay of one flip-flop and the setup time of the next. A trial
  synthesis in the slow corner, before wiring and with ideal clocks, leaves about 470 ps at
  1500 Mb/s and 360 ps at 1792 Mb/s. Its two flip-flops are placed next to each other, with the
  samplers ⚠️.
- OPEN with physical design: the cell library and its body bias, the sign-off corners and the hand
  placement. OPEN with the AFE team: the clock-to-data delay difference and the duty cycle of the
  DDR clock at the AFE outputs, and the maximum line rate of the HS-RX.

### 4.4 Clock Lane Control (Block No. 2)

**Overview.** Implements CIL-SCNN: clock-lane HS entry/exit and clock-lane ULPS (D-PHY [1] ✅).

**Table 4-4 — Clock lane FSM**

| State | Line state | Exit condition → next state | Outputs |
|---|---|---|---|
| CL_INIT | any | LP-11 held for `tinit_cyc` → CL_STOP | — |
| CL_STOP | LP-11 | LP-01 → CL_HS_RQST; LP-10 → CL_ULPS_RQST | `cl_stopstate` = 1 |
| CL_HS_RQST | LP-01 | LP-00 → CL_HS_PRPR; LP-11 → CL_STOP; LP-10 → CL_WAIT (aborted request: status flag, no PPI error) ⚠️ | — |
| CL_HS_PRPR | LP-00 | termination enable issued → CL_HS_TERM | `cl_term_en` = 1 |
| CL_HS_TERM | LP-00 → HS | `clk_settle_cyc` elapsed and clock active → CL_HS_CLK ⚠️ | `cl_hs_en` = 1 |
| CL_HS_CLK | HS clock | clock activity lost (TCLK-MISS) → CL_HS_END | `cl_rxclkactivehs` = 1, byte-clock enable = 1 |
| CL_HS_END | HS-0 / trail | LP-11 → CL_STOP | HS-RX disabled |
| CL_ULPS_RQST | LP-10 | LP-00 → CL_ULPS; LP-11 → CL_STOP; LP-01 → CL_WAIT (aborted entry, D-PHY [1] ✅) | — |
| CL_ULPS | LP-00 | LP-10 (Mark-1) → CL_ULPS_EXIT | `cl_ulpsclknot` = 0, `cl_ulpsactivenot` = 0 |
| CL_ULPS_EXIT | LP-10 | LP-11 → CL_STOP | `cl_ulpsclknot` = 0, `cl_ulpsactivenot` = 1 **[CSI]** |
| CL_WAIT | any | LP-11 → CL_STOP | — |

Figure 4-4 shows the FSM and its settle counter.
- Every state except CL_INIT goes to CL_STOP on LP-11 ⚠️.
- Outputs not listed keep their inactive value (§5.1), except that `cl_term_en` stays 1 from
  CL_HS_PRPR to CL_HS_END and `cl_hs_en` stays 1 in CL_HS_TERM and CL_HS_CLK ⚠️. The outputs are
  registers, so the AFE controls are glitch-free.
- CL_INIT ends when Block No. 6 reports that the lane has seen LP-11 for `tinit_cyc` (§4.7).
- The settle counter counts `core_clk` cycles in CL_HS_TERM and restarts outside it. CL_HS_TERM lasts
  at least `clk_settle_cyc` cycles and ends once the clock is active ⚠️ (Figure 5-7): TCLK-ZERO,
  HS-0 without clock transitions, can outlast TCLK-SETTLE, and the CSI-2 Rx controller takes
  `cl_rxclkactivehs` as the only indication that `rxbyteclkhs` is running **[CSI]**; `rxbyteclkhs`
  starts within about one byte clock after it rises (§4.3) ⚠️.
- "Clock active" and "clock activity lost" come from the clock-activity detection of Block No. 1
  (§4.3). The byte-clock enable opens the clock gate of `rxbyteclkhs` (§4.3).

![Figure 4-4 — Block No. 2, clock lane FSM and settle counter](figures/ftel_dphy_rx_cl_fsm.svg)

**Design note ⚠️ (TCLK-MISS, ≤ 60 ns).** At 80 Mb/s the byte clock period is 100 ns, so the loss of
the clock cannot be detected within 60 ns from `rxbyteclkhs` alone. Block No. 1 therefore also
watches toggles of the DDR clock, and `cl_rxclkactivehs` falls at most 60 ns after the last clock
edge at every rate (§4.3).

### 4.5 Data Lane Control (Block No. 3)

**Overview.** Implements CIL-SFEN: the Control-mode FSM of a unidirectional slave data lane, HS
entry, EoT hand-over and escape mode (D-PHY [1] ✅).

**Table 4-5 — Data lane FSM**

| State | Line state | Exit condition → next state | Outputs / actions |
|---|---|---|---|
| DL_INIT | any | LP-11 held for `tinit_cyc` → DL_STOP | — |
| DL_STOP | LP-11 | LP-01 → DL_HS_RQST; LP-10 → DL_LP_RQST | `stopstate_x` = 1 |
| DL_HS_RQST | LP-01 | LP-00 → DL_HS_PRPR; other → DL_ERR | — |
| DL_HS_PRPR | LP-00 | termination enable issued → DL_HS_TERM | `term_en_x` = 1 |
| DL_HS_TERM | LP-00 → HS | `hs_settle_cyc` elapsed → DL_HS_RX | `hs_en_x` = 1 |
| DL_HS_RX | HS | LP-11 → DL_HS_EOT; `hs_rx_timeout_cyc` elapsed → DL_HS_EOT (timeout status) | Block No. 4 active, sync-search start |
| DL_HS_EOT | LP-11 | Block No. 4 reports EoT done → DL_STOP; EoT done after the line has shown LP-00 in this state → DL_HS_WAIT ⚠️ | — (EoT requested by the fall of the sync-search start) |
| DL_HS_WAIT | any | LP-11 → DL_STOP | — |
| DL_LP_RQST | LP-10 | LP-00 → DL_LP_YIELD; LP-11 → DL_ERR | — |
| DL_LP_YIELD | LP-00 | LP-01 → DL_ESC_RQST; LP-10 → turnaround request, not supported → DL_ERR | — |
| DL_ESC_RQST | LP-01 | LP-00 → DL_ESC_GO; other → DL_ERR | — |
| DL_ESC_GO | LP-00 | first Mark → DL_ESC_CMD | — |
| DL_ESC_CMD | Spaced-One-Hot | 8 bits decoded (Table 4-6 ✅): ULPS `00011110` → DL_ULPS; Trigger → DL_ESC_WAIT; LPDT `11100001` → DL_ESC_WAIT (R1) with `erresc_x`; unknown → DL_ESC_WAIT with `erresc_x` | Command decoder |
| DL_ULPS | LP-00 | LP-10 (Mark-1) → DL_ULPS_EXIT | `rxulpsesc_x` = 1, `ulpsactivenot_x` = 0 |
| DL_ULPS_EXIT | LP-10 | LP-11 → DL_STOP | `rxulpsesc_x` = 1, `ulpsactivenot_x` = 1 **[CSI]** |
| DL_ESC_WAIT | any | LP-11 → DL_STOP | Trigger bit held on `rxtriggeresc_x` until Stop (D-PHY [1] ✅) |
| DL_ERR | any | LP-11 → DL_STOP | `errcontrol_x` held until the next line-state change **[CSI]** C13 |

Any state returns to DL_STOP on LP-11 (D-PHY [1] ✅: "any RX state"), except DL_INIT, DL_HS_RX
(LP-11 ends the burst: DL_HS_EOT) and DL_HS_EOT (waits for EoT done) ⚠️.
DL_HS_WAIT keeps the lane out of DL_STOP while the line is not in LP-11: after an HS RX timeout the
line is still in HS, and at low rates the transmitter may have started its next sequence before EoT
done arrives; joining that sequence in the middle could take the LP-01 of an escape entry for an HS
request and enable the termination ⚠️. Where a row names LP-11 or
"other" as a path to DL_ERR (DL_HS_RQST, DL_LP_RQST, DL_ESC_RQST), that row takes precedence: the
lane passes through DL_ERR, raising `errcontrol_x`, and then returns to DL_STOP ⚠️. The four trigger
entry commands of Table 4-6 map in table order: Reset-Trigger to `rxtriggeresc_x[0]`, Unknown-3 to
`[1]`, Unknown-4 to `[2]`, Unknown-5 to `[3]` ⚠️ (T1).

**Structure** (Figure 4-5). The lane FSM (Figure 4-6), a settle counter, the escape decoder
(Figure 4-7), a line-state change detector and the output registers.
- `term_en_x` = 1 in DL_HS_PRPR, DL_HS_TERM and DL_HS_RX; `hs_en_x` = 1 in DL_HS_TERM and DL_HS_RX.
  The only signal to Block No. 4 is the sync-search start, High in DL_HS_RX (ADR-007); its fall, on
  any exit from DL_HS_RX, is the EoT request ⚠️.
  The outputs are registers, so the AFE controls are glitch-free.
- The settle counter counts `core_clk` cycles in DL_HS_TERM and restarts outside it; DL_HS_TERM lasts
  `hs_settle_cyc` cycles ⚠️. Its end is the end of THS-SETTLE for the sync search (§4.6,
  Appendix B).
- DL_INIT ends when Block No. 6 reports that the lane has seen LP-11 for `tinit_cyc`. `dl_enable_x`
  Low holds the lane in DL_INIT, and a rising `forcerxmode_x` returns it there (§4.2). The HS RX
  timeout and the escape watchdog come from Block No. 6 (§4.7).
- `errcontrol_x` (set on entry into DL_ERR) and `erresc_x` (set by the escape decoder) stay High until
  the next line-state change (D-PHY [1] ✅); `rxtriggeresc_x` and `rxulpsesc_x` stay High until
  DL_STOP.

**Escape decoder** (Figure 4-7). A Mark-0 (LP-01) or a Mark-1 (LP-10) followed by a Space (LP-00) is
a 0 or a 1 bit (D-PHY [1] ✅): on each change to LP-00 in DL_ESC_GO or DL_ESC_CMD, the previous line
state gives the bit. Bits shift into an 8-bit register, the first bit ending in the most significant
position, and a bit counter, cleared outside these two states, marks the eighth bit. The register is
then compared with the entry codes of Table 4-6: ULPS and the four triggers; any other value, LPDT
included while `PARA_LPDT_EN` = 0, is unknown ⚠️.

**Table 4-6 — Escape entry commands, first bit received first (D-PHY [1] ✅)**

| Command | Type | Entry code | Handling |
|---|---|---|---|
| Low-Power Data Transmission | mode | `11100001` | Unknown while `PARA_LPDT_EN` = 0: `erresc_x` |
| Ultra-Low Power State | mode | `00011110` | DL_ULPS |
| Undefined-1 | mode | `10011111` | Unknown: `erresc_x` |
| Undefined-2 | mode | `11011110` | Unknown: `erresc_x` |
| Reset-Trigger | trigger | `01100010` | `rxtriggeresc_x[0]` ⚠️ (T1) |
| Unknown-3 | trigger | `01011101` | `rxtriggeresc_x[1]` ⚠️ (T1) |
| Unknown-4 | trigger | `00100001` | `rxtriggeresc_x[2]` ⚠️ (T1) |
| Unknown-5 | trigger | `10100000` | `rxtriggeresc_x[3]` ⚠️ (T1) |

![Figure 4-5 — Block No. 3, Data Lane Control](figures/ftel_dphy_rx_dl_ctrl.svg)

![Figure 4-6 — data lane FSM of Block No. 3](figures/ftel_dphy_rx_dl_fsm.svg)

![Figure 4-7 — escape decoder of Block No. 3](figures/ftel_dphy_rx_esc_decoder.svg)

**Design note ⚠️ (return to Stop after EoT).** DL_HS_EOT waits for EoT done from Block No. 4, a
round trip through two crossings: 3–4 byte clocks plus about 3 `core_clk` cycles, i.e. 300–400 ns
at 80 Mb/s and about 35 ns at 1500 Mb/s. A Tx that drives THS-EXIT and TLPX at their minimums
(100 ns + 50 ns, D-PHY [1] ✅) can present its next HS request before the lane is back in DL_STOP
below roughly 240 Mb/s, and the lane then misses that burst.
- Decided (ADR-006): the lane keeps this wait. Below roughly 240 Mb/s the next burst is received
  only when THS-EXIT + TLPX exceeds the round trip, about 32·UI + 15 ns (415 ns at 80 Mb/s) ⚠️; the
  Tx side is asked in S5. Otherwise the lane waits in DL_HS_WAIT for the LP-11 that ends that burst.
- Order at the PPI, OPEN ADR-006: the CSI-2 Rx controller expects `stopstate_x` to rise at or after
  the last byte **[CSI]**. EoT done leaves Block No. 4 once the cut is decided, before the delay
  line drains (§4.6), so `stopstate_x` can rise up to `PARA_EOT_DELAY_BYTES` byte clocks (3.2 µs at
  80 Mb/s) before the last byte reaches the PPI ⚠️ (Figure 5-1); the CSI team is asked. The controller
  routes `stopstate_x` to IRQ_STATUS bit 11 and LANE_STATUS only, and its Burst FSM opens and
  closes a burst on `rxactivehs_x` **[CSI]**. Sending EoT done only after the drain would meet that
  expectation, but the lane would then miss bursts at the minimum THS-EXIT + TLPX below roughly
  1.2 Gb/s with the default depth ⚠️.
- Faster option, kept for later: DL_HS_EOT does not wait; Block No. 4 completes the EoT on its own
  and EoT done only feeds the status. The lane is then back in DL_STOP a few `core_clk` cycles after
  LP-11, so bursts at the minimum THS-EXIT + TLPX are received at every rate, and `stopstate_x`
  rises one round trip earlier. It needs Block No. 4 to accept the next sync-search start while the
  previous EoT is still pending ⚠️.

### 4.6 HS Receive Datapath (Block No. 4)

**Overview.** Per data lane, in `rxbyteclkhs`. Turns the words of Block No. 1, cut at an arbitrary
boundary, into aligned PPI bytes: finding the byte boundary here completes the deserialization
that Block No. 1 starts (§1).

**Function** (Figures 4-8 and 4-9).
- **Sync search.** Starts with the sync-search start from Block No. 3, raised in DL_HS_RX at the end
  of THS-SETTLE (ADR-007). The words received before it are ignored: the window registers stay at
  zero while the start is Low, so these words cannot match, start the search counter or start the
  deskew detection. D-PHY [1] ✅: the HS receiver shall ignore any Data Lane transitions before
  THS-SETTLE,min.
  - The search compares a 2-word window (two consecutive words, every byte clock) with the
    leader `…00011101` (first bit received first), accepting any single-bit error (D-PHY [1] ✅).
  - It lasts at most `PARA_SYNC_SEARCH_BYTES` byte clocks, counted from the first non-zero word after
    the start ⚠️: D-PHY [1] ✅ gives only a minimum for THS-PREPARE + THS-ZERO, so a compliant Tx
    may drive HS-0 for longer than any fixed window.
  - Exact match: the byte offset is locked; `rxsynchs_x` pulses in the **same cycle** as the first
    payload byte **[CSI]** C6.
  - Single-bit error: as above, plus a one-cycle `errsoths_x` (D-PHY [1] ✅).
  - No match within `PARA_SYNC_SEARCH_BYTES`: one-cycle `errsotsynchs_x`; no `rxsynchs_x` and no
    `rxvalidhs_x` for the rest of the burst, while `rxactivehs_x` stays asserted until EoT
    **[CSI]** C8 (Figure 5-2). The search counter stops at `PARA_SYNC_SEARCH_BYTES`, and the
    comparators stay disabled until the sync-search start falls ⚠️.
  - No match before the EoT (OPEN ADR-007): with the limit not reached and no deskew burst detected,
    for example a short packet on four lanes after a corrupted leader, `errsotsynchs_x` pulses once, in
    the last cycle of `rxactivehs_x` (EoT, below) ⚠️. The CSI-2 Rx controller is asked to confirm.
  - A leader with two or more bit errors usually matches at a wrong offset before that limit, most
    often inside the payload (about 99 % of such bursts with the default limit, model of chapter 7).
    The burst is then delivered misaligned and the CSI-2 layer rejects it (ECC, CRC);
    `errsotsynchs_x` is raised only when no offset matches ⚠️. The CSI-2 Rx controller expects it for
    every corrupted leader (OPEN ADR-007).
  - Eight comparators, one per bit offset of the window, each accept at most one differing bit, and
    the lowest matching offset is locked. The leader differs from each of its earlier shifts in at
    least three bits, so a single-bit error cannot move the lock to a wrong offset ⚠️.
- **Deskew-burst detection (R1 and R2).** A run of ≥ 16 ones after HS-0 (v1.2 skew-calibration sync,
  a run of ones [3] 🌐) asserts `rxskewcalhs_x` until after the lane has returned to Stop state; no
  `rxvalidhs_x` or `rxsynchs_x` is produced **[CSI]** C9. In R2 the burst is forwarded to Block No. 5.
  - The skew-calibration flag is set on every delay-line entry written from the detection until the
    sync-search start falls. At the PPI `rxskewcalhs_x` therefore falls after `rxactivehs_x`, by about
    `eot_skip_bytes` byte clocks, and after `stopstate_x` rises (Figure 5-3) ⚠️; the CSI-2 Rx
    controller expects `rxskewcalhs_x` to stay asserted after `rxactivehs_x` has fallen **[CSI]**.
  - The first 1 after HS-0 is located in the first non-zero word after the sync-search start; the
    burst is a deskew burst when the 16 bits from that position, taken from three consecutive words,
    are all ones ⚠️.
  - The deskew sync also matches the leader with one bit in error (`00011111`). The detection,
    which ends up to two words after that match, cancels the lock by clearing the sync, SoT-error
    and valid flags already written into the delay line, which are in its three newest entries ⚠️.
    It also clears the lock register and keeps the comparators disabled until the sync-search start
    falls, so no later entry is marked valid ⚠️.
- **Byte alignment.** A barrel shifter (an 8-to-1 multiplexer of 8-bit slices, selected by the
  locked offset) over two consecutive words produces `rxdatahs_x` with bit 0 received first.
  `rxvalidhs_x` is asserted for every aligned byte.
- **Delay line and outputs.** Each entry of the `PARA_EOT_DELAY_BYTES` delay line holds a byte and its
  flags: valid, sync, SoT error, SoT sync error, skew calibration and active. Every PPI output of the
  lane is taken from the oldest entry, so the outputs follow the line by `PARA_EOT_DELAY_BYTES` byte
  clocks (3.2 µs at 80 Mb/s) and consecutive bursts leave in order ⚠️. `rxactivehs_x` is the active
  flag at the output: it is set for every entry written while the synchronized sync-search start is
  High, so an HS entry aborted in DL_HS_TERM (LP-11 before THS-SETTLE ends) gives no `rxactivehs_x` ⚠️.
- **EoT and trailer removal** (Figure 4-9). On the EoT request (the fall of the sync-search start:
  LP-11, the HS RX timeout or `forcerxmode_x` in Block No. 3) the stored tail is scanned backwards
  (D-PHY [1] ✅):
  - the `eot_skip_bytes` newest entries are discarded: the THS-SKIP interval and the detection
    latency (Appendix B) ⚠️;
  - the newest remaining bit gives the trailer value; the newest entry that is not uniformly equal to
    it holds the last payload bit, which is its highest bit that differs;
  - if no entry of the burst differs from the trailer value (a line stuck at one level, which ends
    with the HS RX timeout), every entry of the burst still in the delay line loses its valid and
    active flags and the EoT sync error status is raised ⚠️;
  - if that bit is bit 7 the entry is the last byte; otherwise the last payload bit is not on a byte
    boundary, the entry is dropped as well and the EoT sync error status is raised (D-PHY [1] ✅;
    the PPI has no signal for it) ⚠️;
  - entries after the last byte lose their valid and active flags, so `rxactivehs_x` falls after the
    last byte. A burst without a lock, without a deskew detection and without `errsotsynchs_x` at the
    search limit gets the SoT sync error flag on its last active entry ⚠️. EoT done goes to Block No. 3
    once the cut is decided, before the delay line drains ⚠️.
- **Timeout.** The HS RX timeout of Block No. 3 forces the same EoT sequence, so `rxactivehs_x`
  always falls while the byte clock runs **[CSI]** C11; the lane then waits in DL_HS_WAIT until the
  line returns to LP-11 (§4.5).

![Figure 4-8 — Block No. 4, HS Receive Datapath: sync search, deskew detection and byte alignment](figures/ftel_dphy_rx_hs_datapath.svg)

![Figure 4-9 — EoT delay line and trailer removal of Block No. 4](figures/ftel_dphy_rx_eot.svg)

**Design note ⚠️ (start of the sync search, ADR-007).** The sync-search start and the words reach the
search with about the same delay. The start is raised on entry into DL_HS_RX in `core_clk` and
crosses into `rxbyteclkhs` in 2–3 byte clocks (§4.1). A word reaches the Block No. 1 register Λ byte
clocks after its last bit at the line (§5.2). The first word searched therefore began at the line
between Λ and Λ − 1 byte clocks before the entry into DL_HS_RX, at every line rate.
- `hs_settle_cyc` places that entry so that the search starts after THS-SETTLE,min (85 ns + 6·UI) and
  before the first 1 of a leader sent at the minimum THS-PREPARE + THS-ZERO (145 ns + 13·UI). The
  window for the entry is 60 ns − 1·UI wide, 47.5 ns at 80 Mb/s (Appendix B).
- Λ is set by the deserializer of Block No. 1 (§4.3; OPEN ADR-007 until its RTL confirms the
  value). With Λ one byte clock off, the Appendix B values
  still work from about 300 Mb/s; below that rate `hs_settle_cyc` has to be reprogrammed
  (model of chapter 7).
- At the lowest rates the search can start inside the three leading zeros of the leader. A bit error
  there is then not reported on `errsoths_x` (about 15 in 1000 single-bit errors at 80 Mb/s, none
  from 100 Mb/s); the burst is received normally.
- The HS-RX output during THS-PREPARE, and so the words, may be junk, including all ones (ADR-001). Because they are ignored,
  they cannot make the deskew detection take a normal burst for a deskew burst.

**Design note ⚠️ (EoT cut at low rates, OPEN ADR-006).** The cut must fall inside the trailer: after
the last payload bit, and at least THS-SKIP,min = 40 ns before LP-11. With a minimum trailer
(THS-TRAIL ≥ 60 ns + 4·UI, D-PHY [1] ✅) this window is 20 ns + 4·UI wide. The EoT request reaches
this block with an uncertainty of one byte clock plus one `core_clk` cycle (8·UI + 5 ns), so a fixed
`eot_skip_bytes` places the cut correctly only above roughly 270 Mb/s.
- Below that rate, a late cut delivers trailer bytes after the packet footer, and an early cut loses
  payload bytes (`err_wc` in the CSI-2 Rx controller). The controller finds the end of a packet from
  its Word Count; whether it ignores bytes after the footer is not known ⚠️.
- Options: bias `eot_skip_bytes` late at low rates; time-stamp the LP-11 detection against byte-clock
  edges seen in `core_clk`; or deliver the trailer and let the CSI-2 controller drop it, since D-PHY
  [1] ✅ allows EoT processing by the protocol.

**Design note ⚠️ (delay line depth).** The tail to hold is TEOT,max (105 ns + 12·UI, D-PHY [1] ✅)
plus the LP-11 detection latency and the crossing into `rxbyteclkhs`: about 30 bytes at 1500 Mb/s and
35 at 1792 Mb/s. The default `PARA_EOT_DELAY_BYTES` of 32 therefore covers R1 only.

**Design note ⚠️ (clock after the last burst, OPEN S12).** The delay line drains only while
`rxbyteclkhs` runs, and the transmitter stops the clock TCLK-POST after the last burst: after every
burst with a non-continuous clock, and with a continuous clock before the clock lane enters ULPS or
when the stream stops. At the minimum TCLK-POST (60 ns + 52·UI, D-PHY [1] ✅) the byte clock runs
about 18 byte clocks after LP-11 at 1500 Mb/s and 7 at 80 Mb/s, while Bn reaches the PPI up to about
`PARA_EOT_DELAY_BYTES` + Λ + 1 byte clocks after LP-11 at the lowest rates (Λ: §5.2) and
`rxactivehs_x` falls one byte clock later ⚠️.
- Between bursts the last bytes of a burst would wait for the next one, so this IP needs a continuous
  clock, which the CSI-2 Rx controller also requires **[CSI]** C5.
- After the last burst, at the minimum TCLK-POST, the tail of that burst, for example a Frame End
  packet, stays in the delay line with `rxactivehs_x` High until the clock runs again. D-PHY [1] ✅
  provides for this: when a receiver needs more clock cycles than TCLK-POST,min to finish reception,
  the transmitter supplies them. This IP needs the clock for `PARA_EOT_DELAY_BYTES` + Λ + 2 byte
  clocks after the last data lane enters LP-11: 288·UI in R1 and 320·UI in R2 with Λ = 2 ⚠️
  (OPEN S12, Tx side). The CSI-2 Rx controller, whose lane management also runs on `rxbyteclkhs`, is
  asked how many byte clocks it needs after the last byte; that number adds to this one.

### 4.7 Timing & Init Control (Block No. 6)

- Holds the programmable timer values and distributes them to Blocks No. 2 and 3.
- Hosts the reset synchronizers of the four clock domains (`core_clk`, the DDR clock, `rxbyteclkhs`,
  the configuration clock) and of Block No. 4 of each data lane (§4.2), and the level synchronizers
  of `cl_enable`, `dl_enable_x` and `forcerxmode_x` (§4.1). The synchronized enables go to Block No. 7.
  A lane whose enable is Low is held in its INIT state; a data lane returns to DL_INIT when its
  synchronized `forcerxmode_x` rises ⚠️.
- Initialization (D-PHY [1] ✅): after `phy_core_rst` release, enable, or a rising `forcerxmode_x`,
  a lane ignores all line states until it has observed LP-11 for `tinit_cyc`. `init_done` rises when the
  clock lane and every enabled data lane have completed initialization **[CSI]** C14, C16.
  - One counter per lane counts consecutive LP-11 cycles and restarts on any other state or on a
    lane reset; the lane is initialized when the counter reaches `tinit_cyc` ⚠️.
  - `init_done` is the registered AND of the clock lane and, for each data lane, "initialized or not
    enabled" ⚠️ (exact semantics OPEN K6).
- Hosts the HS RX and escape watchdogs (D-PHY [1] ✅): one counter each per data lane, counting
  `core_clk` cycles in the watched states and restarting outside them; expiry when the counter
  reaches `hs_rx_timeout_cyc` or `esc_timeout_cyc` ⚠️. The HS RX timeout watches DL_HS_RX.
- Escape watchdog ⚠️: runs only in DL_LP_RQST, DL_LP_YIELD, DL_ESC_RQST, DL_ESC_GO and DL_ESC_CMD,
  not in DL_ULPS, DL_ULPS_EXIT or DL_ESC_WAIT (ULPS may last indefinitely and the Mark-1 exit
  lasts TWAKEUP ≥ 1 ms). On expiry the lane goes to DL_ESC_WAIT, which waits for LP-11 without a
  PPI error, and the escape-timeout sticky flag of Block No. 8 is set.

![Figure 4-10 — Block No. 6, Timing & Init Control](figures/ftel_dphy_rx_timing_init.svg)

### 4.8 Deskew Controller (Block No. 5, R2)

- Receives deskew bursts identified by Block No. 4, drives the delay taps of a delay line in front
  of the samplers of its lane, and selects the tap in the centre of the passing window.
- The algorithm, the tap resolution and the use of periodic calibration are decided in R2
  (ADR-004). The AFE has no delay line (ADR-001). One built from standard cells would have steps of
  one buffer, about 15–30 ps depending on the corner, against a UI of 558 ps at 1792 Mb/s, so its
  range and resolution drift by a factor of about 2 ⚠️.
- RxErrorCalHS is not required **[CSI]** C9.
- With `PARA_DESKEW_EN` = 0 the block is absent and the taps are held at their reset value.
- Figure 4-11 shows the boundary of the block; its content stays OPEN until ADR-004.

![Figure 4-11 — Block No. 5, Deskew Controller: boundary (content OPEN ADR-004)](figures/ftel_dphy_rx_deskew.svg)

### 4.9 PPI Output Stage (Block No. 7)

- Maps internal signals to the PPI names of §5.1, so a change of the PPI contract stays inside this
  block.
- Forces the inactive value of every output of a lane whose enable is Low (D-PHY [1] ✅).
  The outputs of the `rxbyteclkhs` domain are gated combinationally with the synchronized enable,
  so their inactive values hold while the byte clock is stopped ⚠️ (crossing listed in §4.1). The
  enable may change at any time: a burst cut by a disable is not delivered when the lane is enabled
  again, because the disable also clears Block No. 4 of the lane (§4.2) ⚠️.
- Generates `rxclkesc_x` as the XOR of the synchronized LP lines for PPI completeness; no logic
  inside this IP is clocked by it (ADR-002).
- Gating (Figure 4-12): an output whose inactive value is 0 is ANDed with the synchronized enable of
  its lane; `ulpsactivenot_x`, `cl_ulpsactivenot` and `cl_ulpsclknot` (inactive value 1) are ORed
  with its inverse ⚠️. The LPDT outputs are tied to 0 (K2); `rxbyteclkhs` and `init_done` pass through.

![Figure 4-12 — Block No. 7, PPI Output Stage](figures/ftel_dphy_rx_ppi_out.svg)

### 4.10 Configuration & Status (Block No. 8)

Configuration fields: the timer values of §3, lane polarity inversion and lane mapping, and a
run-time deskew bypass `deskew_bypass` (R2, present only when `PARA_DESKEW_EN` = 1; holds the taps
at their reset value) ⚠️.

Status: the lane FSM states, and a sticky flag with a counter for each of: SoT errors (`errsoths_x`),
SoT sync errors (`errsotsynchs_x`), EoT sync errors, HS RX timeouts, escape errors, escape timeouts
and aborted clock-lane requests ⚠️.

The bus and register map are OPEN (K3, ADR-005); chapter 6.

Figure 4-13 shows the block, with the bus interface drawn at its boundary.
- The configuration fields are registers of the configuration clock, used quasi-statically by the
  other blocks (§4.1).
- Each status event arrives through a toggle synchronizer (§4.1), sets its sticky flag and increments
  its counter; software clears both ⚠️ (access method with the register map, chapter 6).
- The lane FSM states arrive through 2-flop synchronizers (§4.1).

![Figure 4-13 — Block No. 8, Configuration & Status (bus OPEN K3)](figures/ftel_dphy_rx_cfg_status.svg)

---

## 5. Interfaces

### 5.1 PPI (to the CSI-2 Rx controller)

Direction is seen from this IP. Signal list and semantics follow the CSI-2 Rx controller **[CSI]**.

**Table 5-1 — PPI signals**

| Signal | Dir | Width | Domain | Source | Inactive value | R1 |
|---|---|---|---|---|---|---|
| `cl_enable` | In | 1 | level | — | — | Yes |
| `dl_enable_x` | In | 1 | level | — | — | Yes |
| `forcerxmode_x` | In | 1 | level | — | — | Yes |
| `phy_core_rst` | In | 1 | async | — | — | Yes |
| `core_clk` | In | 1 | — | system | — | Yes |
| `init_done` | Out | 1 | `core_clk` | No.6 | 0 | Yes |
| `cl_stopstate` | Out | 1 | async | No.2 | 0 | Yes |
| `stopstate_x` | Out | 1 | async | No.3 | 0 | Yes |
| `cl_ulpsactivenot` | Out | 1 | async | No.2 | 1 | Yes |
| `ulpsactivenot_x` | Out | 1 | async | No.3 | 1 | Yes |
| `rxbyteclkhs` | Out | 1 | clock | No.1 | — | Yes |
| `cl_rxclkactivehs` | Out | 1 | async | No.2 | 0 | Yes |
| `cl_ulpsclknot` | Out | 1 | async | No.2 | 1 | Yes |
| `rxdatahs_x` | Out | 8 | `rxbyteclkhs` | No.4 | 0 | Yes |
| `rxvalidhs_x` | Out | 1 | `rxbyteclkhs` | No.4 | 0 | Yes |
| `rxactivehs_x` | Out | 1 | `rxbyteclkhs` | No.4 | 0 | Yes |
| `rxsynchs_x` | Out | 1 | `rxbyteclkhs` | No.4 | 0 | Yes |
| `rxskewcalhs_x` | Out | 1 | `rxbyteclkhs` | No.4 | 0 | Yes (detection) |
| `rxclkesc_x` | Out | 1 | clock | No.7 | 0 | Yes |
| `rxlpdtesc_x` | Out | 1 | `core_clk` | — | 0 | Tied 0 (K2) |
| `rxulpsesc_x` | Out | 1 | async | No.3 | 0 | Yes |
| `rxtriggeresc_x` | Out | 4 | async | No.3 | 0 | Yes |
| `rxdataesc_x` | Out | 8 | `core_clk` | — | 0 | Tied 0 (K2) |
| `rxvalidesc_x` | Out | 1 | `core_clk` | — | 0 | Tied 0 (K2) |
| `errsoths_x` | Out | 1 | `rxbyteclkhs` | No.4 | 0 | Yes |
| `errsotsynchs_x` | Out | 1 | `rxbyteclkhs` | No.4 | 0 | Yes |
| `erresc_x` | Out | 1 | async | No.3 | 0 | Yes |
| `errsyncesc_x` | Out | 1 | async | — | 0 | Tied 0 (no LPDT, K2) |
| `errcontrol_x` | Out | 1 | async | No.3 | 0 | Yes |

**Timing at the PPI.** Figures 5-1 to 5-8 show one data lane and the clock lane. They are not to
scale; a double slash is a time break, and a hatched area is undefined or marks a pulse that only
some bursts have.
- HS outputs. Every HS output of a lane is taken from the oldest entry of the EoT delay line (§4.6),
  so the HS outputs follow the line by `PARA_EOT_DELAY_BYTES` byte clocks.
  - `rxactivehs_x` rises at or before `rxsynchs_x`.
  - `rxsynchs_x`, and `errsoths_x` after a leader with a single-bit error, pulse in the cycle of the
    first payload byte B1 **[CSI]** C6. The lane management of the CSI-2 Rx controller writes a byte
    when `rxvalidhs_x` is High and the sync is seen in that cycle or was seen before, so it would also
    accept the pulse one cycle before B1 **[CSI]**.
  - `rxvalidhs_x` is High for every byte from B1 to Bn and falls with `rxactivehs_x` after Bn.
  - `stopstate_x` falls when LP-01 is seen, before `rxactivehs_x` rises, and rises before Bn reaches
    the PPI (OPEN ADR-006, §4.5).
  - SoT sync error (Figure 5-2): one `errsotsynchs_x` pulse `PARA_SYNC_SEARCH_BYTES` byte clocks after
    the first non-zero word that follows the sync-search start, then no `rxsynchs_x` or `rxvalidhs_x`
    until the end of the burst **[CSI]** C8. A burst that ends earlier without a lock has its pulse in
    the last cycle of `rxactivehs_x` ⚠️ (§4.6).
  - Deskew burst (Figure 5-3): `rxskewcalhs_x` from the detection until about `eot_skip_bytes` byte
    clocks after `rxactivehs_x` falls; no `rxvalidhs_x` or `rxsynchs_x` **[CSI]** C9.
- LP outputs. `stopstate_x`, the escape outputs and the clock-lane outputs are registers in
  `core_clk`. They follow the line state one cycle after the LP detection latency, 25–30 ns with the
  defaults (§4.3, Appendix B).
  - Escape mode (Figures 5-4 and 5-5): the trigger bit, or `rxulpsesc_x` with `ulpsactivenot_x`
    Low, is set when the eighth bit of the entry command is decoded. Mark-1 raises `ulpsactivenot_x`
    **[CSI]**. `rxtriggeresc_x` and `rxulpsesc_x` fall with the return to Stop **[CSI]** C12.
  - Errors (Figure 5-6): `errcontrol_x` and `erresc_x` are held until the next line-state change
    **[CSI]** C13.
  - Clock lane (Figure 5-7): `cl_rxclkactivehs` rises once the clock is active after TCLK-SETTLE, and
    `rxbyteclkhs` starts within about one byte clock after it. `cl_rxclkactivehs` falls at most
    60 ns after the last clock edge, within TCLK-MISS (§4.3, §4.4) ⚠️.
- Initialization (Figure 5-8): after `phy_core_rst` and the enables, each lane leaves its INIT state
  after `tinit_cyc` cycles of LP-11, and `init_done` follows (§4.7; exact semantics OPEN K6)
  **[CSI]** C14, C16.

![Figure 5-1 — HS receive at the PPI](figures/ftel_dphy_rx_wave_hs_rx.svg)

![Figure 5-2 — HS receive with a SoT sync error at the PPI](figures/ftel_dphy_rx_wave_sot_sync_err.svg)

![Figure 5-3 — deskew burst at the PPI](figures/ftel_dphy_rx_wave_deskew.svg)

![Figure 5-4 — escape mode, Reset-Trigger, at the PPI](figures/ftel_dphy_rx_wave_trigger.svg)

![Figure 5-5 — data-lane ULPS entry and exit at the PPI](figures/ftel_dphy_rx_wave_ulps.svg)

![Figure 5-6 — false control and unsupported escape command at the PPI](figures/ftel_dphy_rx_wave_lp_err.svg)

![Figure 5-7 — clock lane: HS clock start and stop, clock-lane ULPS](figures/ftel_dphy_rx_wave_clock_lane.svg)

![Figure 5-8 — initialization of the lanes](figures/ftel_dphy_rx_wave_init.svg)

### 5.2 AFE interface (signal details OPEN ADR-001)

The AFE contains the line receivers and the termination only, as announced by the AFE team. It
delivers the HS bits of each data lane **unsampled**, one wire per lane, and the DDR clock of the
clock lane. This IP samples and deserializes the bits, generates the byte clock (§4.3) and finds the
byte boundary (§4.6).

**Table 5-2 — AFE interface signals**

| Signal | Dir | Width | Domain | Description |
|---|---|---|---|---|
| `afe_lp_dp_x`, `afe_lp_dn_x` | In | 1 each | async | LP-RX outputs of data lane x |
| `afe_cl_lp_dp`, `afe_cl_lp_dn` | In | 1 each | async | LP-RX outputs of the clock lane |
| `afe_cl_hs_clk` | In | 1 | clock | HS-RX output of the clock lane: the DDR clock, line rate / 2, at CMOS levels; Low while the clock-lane HS-RX is disabled ⚠️. Its pulses while the HS-RX starts or stops are ignored (§4.3) |
| `afe_hs_bit_x` | In | 1 | `afe_cl_hs_clk`, both edges | HS-RX output of data lane x: the received bit stream at CMOS levels, not sampled; the transmitter centres each DDR clock edge in a bit (D-PHY [1] ✅). Clock-to-data delay difference and duty cycle within the budget of §4.3 ⚠️ |
| `afe_hs_en_x`, `afe_cl_hs_en` | Out | 1 each | `core_clk` | HS-RX enable |
| `afe_term_en_x`, `afe_cl_term_en` | Out | 1 each | `core_clk` | HS termination enable. An AFE with one enable for the HS-RX and the termination of a lane uses this one ⚠️ |
| `afe_dly_tap_x` | Out | `PARA_DLY_TAP_WIDTH` | `rxbyteclkhs` | Delay-line setting (R2), only with a delay line in the AFE (ADR-004) |

**Timing at the AFE interface** (Figure 5-9, not to scale; D-PHY [1] ✅).
- SoT. `afe_term_en_x` rises in DL_HS_PRPR, 25–30 ns after the start of LP-00 at the LP-RX output,
  within TD-TERM-EN (35 ns + 4·UI) when the AFE adds at most 5–10 ns + 4·UI (§4.3). `afe_hs_en_x`
  follows in DL_HS_TERM, 30–35 ns after it, and DL_HS_RX starts `hs_settle_cyc` cycles later with
  the sync-search start (Appendix B).
- Word latency Λ: byte clocks from the last bit of a word at the line to that word in the HS path
  register of Block No. 1, the HS-RX delay of the AFE included. Λ = 2, set by the deserializer of
  Block No. 1 (§4.3) ⚠️ (OPEN ADR-007 until its RTL confirms the value); `hs_settle_cyc` depends on
  it.
- The sync-search start reaches Block No. 4 2–3 byte clocks later (§4.1). The first word searched
  began at the line between Λ and Λ − 1 byte clocks before the entry into DL_HS_RX, so the words
  received during THS-PREPARE are ignored (§4.6).
- EoT. LP-11 moves the lane to DL_HS_EOT, which clears both AFE enables and lowers the sync-search
  start, the EoT request; EoT done returns the lane to DL_STOP (§4.5, §4.6). The PPI outputs of the
  burst follow `PARA_EOT_DELAY_BYTES` byte clocks later (Figure 5-1).

![Figure 5-9 — data lane at the AFE interface: SoT and EoT](figures/ftel_dphy_rx_wave_afe_sot_eot.svg)

### 5.3 Configuration and status interface

OPEN K3 / ADR-005. Draft assumption: a dedicated APB subordinate in Block No. 8.

---

## 6. Registers

Deferred until ADR-005 is agreed and the register map of the CSI-2 Rx controller (OPEN K5) is
available. The fields to be exposed are listed in §3 and §4.10.

---

## 7. Design Decisions

Scores 1–5; weight in brackets.

### ADR-001 — AFE boundary and interface (boundary A, announced by the AFE team)

**Table 7-1 — ADR-001: AFE boundary options**

| Criterion (weight) | **A: AFE gives serial HS bits + DDR clock** | B: AFE gives unaligned 1:8 words + byte clock | C: hard PHY up to PPI (vendor macro) |
|---|---|---|---|
| Timing feasibility at 1.5–1.8 Gb/s (5) | 1 | 5 | 5 |
| Portability across AFE / process (3) | 3 | 4 | 1 |
| Deskew support in R2 (3) | 2 | 4 | 5 |
| Verification effort (2) | 4 | 4 | 3 |
| Protocol logic owned in RTL (3) | 5 | 5 | 1 |
| **Total** | **43** | 72 | 52 |

Boundary: option A, announced by the AFE team on 2026-10-06. The AFE contains the HS-RX, the LP-RX
and the termination switch only, and has no line-state logic. It delivers each data lane as one
unsampled bit stream and the clock lane as the DDR clock. Draft v0.12 had read an earlier
announcement, of 2026-10-03, as option B; the AFE provides neither the sampler nor the deserializer
that B needs.

A is chosen although its score is the lowest: B needs a sampler and a deserializer in the AFE, and C
replaces this IP by a vendor macro, a project decision outside this document. A moves into this IP
the samplers, the 1:8 deserializer, the byte clock and the clock-activity detection for TCLK-MISS
(§4.3); the word latency Λ is now set by this IP (§5.2).

Basis of the timing score of A: when the maximum rate is above 1 Gb/s, the receiver setup and hold
window is 0.4 UI, ±133 ps at 1.5 Gb/s (D-PHY [1] ✅). The window must hold the sampler aperture and
the difference between the clock and data delays inside the chip, which a synthesized clock tree
does not keep centred across process corners. The samplers are therefore a hand-placed structure of
this IP next to the AFE. The score was given with 130 nm cells, with which the structure fits the
window at 1.35 V and 125 °C but not at 1.2 V and 175 °C. With the 22 nm cells assumed since v0.15 it
fits in the slow corner with about ±95 ps left at 1792 Mb/s (§4.3 design note): the timing risk of A
is lower, and the choice is unchanged.

Still OPEN with the AFE team: the maximum line rate of the HS-RX; the clock-to-data delay difference
and the duty cycle of the DDR clock at the AFE outputs, which share the sampler window with this IP;
the HS-RX outputs while disabled and while starting; one enable or two per lane for the HS-RX and the
termination; termination timing; the maximum LP glitch width; a delay line for deskew (R2). OPEN with
physical design: the cell library and its body bias, the sign-off corners, and the hand placement of
the samplers and of the half-period path of the deserializer (§4.3 design note).

### ADR-002 — LP and escape reception (decided in this draft: A)

**Table 7-2 — ADR-002: LP and escape reception options**

| Criterion (weight) | **A: oversample LP lines in `core_clk`** | B: clock escape logic with XOR(Dp, Dn) |
|---|---|---|
| Robustness to glitches on LP lines (4) | 4 | 2 |
| STA / DFT friendliness (4) | 5 | 1 |
| Latency (2) | 3 | 5 |
| Matches the CSI-2 Rx controller (escape data in `core_clk`) (2) | 5 | 2 |
| Area (1) | 3 | 5 |
| **Total** | **55** | 31 |

Basis: every LP state lasts at least TLPX = 50 ns (D-PHY [1] ✅), i.e. ≥ 10 samples at 200 MHz.

### ADR-003 — Release staging

R1 without deskew calibration, R2 with it (Table 1-3). OPEN K1.

### ADR-004 — Deskew algorithm (R2)

Deferred: depends on a delay line in front of the samplers, which the AFE does not have (ADR-001,
§4.8), and on the Tx deskew behaviour (S4). Constraint
fixed now: the R1 datapath already detects deskew bursts, so R2 only adds Block No. 5.

### ADR-005 — Configuration path (proposed: B, OPEN K3)

**Table 7-3 — ADR-005: configuration path options**

| Criterion (weight) | A: fields added to the CSI-2 controller CSR | **B: own APB subordinate** | C: synthesis parameters only |
|---|---|---|---|
| Programmability for rate changes (5) | 5 | 5 | 1 |
| Integration effort with the CSI team (3) | 2 | 4 | 5 |
| Independence and reuse of the PHY (3) | 2 | 5 | 3 |
| Area (1) | 5 | 3 | 5 |
| **Total** | 42 | **55** | 34 |

### ADR-006 — Trailer removal (decided: delay line + last transition, wait for EoT done; OPEN: cut below ~270 Mb/s, order at the PPI)

The PHY does not know packet lengths (it never parses content), so the only method that follows
D-PHY [1] ✅ is to buffer the tail of the burst and cut it at the last transition before the
THS-SKIP interval. Discarding a fixed number of bytes fails when the Tx trail length changes.

Reopened by the block-level design (design notes of §4.5 and §4.6). Decided: DL_HS_EOT keeps waiting
for EoT done; §4.5 states the resulting rate limit and keeps not waiting as the faster option.
Still open: the precision of the cut below ~270 Mb/s and the order of `stopstate_x` and
`rxactivehs_x` at the PPI (CSI team).

### ADR-007 — Start of the sync search (decided: D)

Opened by the timing diagrams of v0.8 (Figure 5-9) and decided in v0.9 with a bit-level model of the
line, the AFE, the crossing and each option (model below). D-PHY [1] ✅ requires the HS receiver to
ignore Data Lane transitions before THS-SETTLE,min and to respond to them after THS-SETTLE,max;
until THS-SETTLE,min the HS-RX output, and so the words of Block No. 1, may be junk (ADR-001).
- A (v0.8): the search starts on entry into DL_HS_TERM, after an all-zero word.
- B: 8 zero bits followed by the leader, compared over three words; the search counter restarts on
  every all-zero word.
- C: a run-time field `hs_skip_bytes` skips the first words after the entry into DL_HS_TERM.
- **D: the search starts with the sync-search start (DL_HS_RX), and the words before it are ignored
  (§4.6).**
- E: the AFE forces its HS-RX output to zero until DL_HS_RX (a new AFE behaviour).

**Table 7-4 — ADR-007: sync-search start options**

| Criterion (weight) | A | B | C | **D** | E |
|---|---|---|---|---|---|
| Ignores the words before THS-SETTLE,min and finds every leader, 80–2500 Mb/s (5) | 1 | 2 | 4 | 5 | 5 |
| Fallback without RTL change when an assumption fails (5) | 1 | 1 | 3 | 5 | 3 |
| No new obligation on another team (4) | 2 | 4 | 2 | 5 | 1 |
| No further rate-dependent field; every field does what its name says (3) | 3 | 3 | 1 | 5 | 5 |
| RTL complexity, area, timing (2) | 4 | 2 | 3 | 4 | 4 |
| Verification effort (2) | 3 | 2 | 3 | 4 | 3 |
| Behaviour after a corrupted leader (1) | 3 | 2 | 3 | 3 | 3 |
| **Total** | 44 | 50 | 61 | **104** | 76 |

Model behind the evidence below, Table 7-5 and the `hs_settle_cyc` values of Appendix B:
- Line: time 0 is the start of LP-00. The Tx sends HS-0 until THS-PREPARE + THS-ZERO (the minimum
  145 ns + 10·UI, a few UI more, or 2 µs), then the leader `00011101` with 0, 1 or 2 bit errors and a
  payload.
- AFE: until THS-SETTLE,min the HS receiver output is zero, random or all ones (three junk models,
  bounds rather than measurements). Words start at a random byte phase, and a word reaches the
  Block No. 1 register Λ byte clocks after its last bit, with Λ from 1 to 3.
- Control path: DL_HS_TERM is entered 30–40 ns after the start of LP-00 and DL_HS_RX
  `hs_settle_cyc` × 5 ns later. Each level crosses into `rxbyteclkhs` through two flip-flops, the
  first of which may resolve one cycle late.
- Search: as in §4.6, started as each option defines.
- Runs: 15 to 400 bursts per condition from 80 to 2500 Mb/s, so "no failure" is evidence, not proof.
  For D, correctness also follows from the closed-form window of Appendix B, which the model
  confirms: the passing range of `hs_settle_cyc` contains the Appendix B value at every rate and
  latency.
- Not modelled: jitter, lane skew and the EoT.

Evidence, as failures per 1000 bursts in the worst case over Λ = 1 to 3:
- With words of zero before HS-0, every option receives every leader, at 80 Mb/s too.
- With random or all-ones words up to THS-SETTLE,min:
  - A fails 1000 at every rate when HS-0 is long, and from 1 Gb/s also at the minimum HS-0.
  - B locks wrongly on 17–50 up to 1500 Mb/s, 208 at 1792 Mb/s and 1000 at 2500 Mb/s.
  - C with the v0.8 formula fails 741–1000.
  - D and E have no failure.
- C works only with values outside its v0.8 formula, and at 80–100 Mb/s with a single value,
  because it moves in steps of one byte clock. D moves in steps of 5 ns and has 10–15 passing values
  at every rate.
- D is not worse than another option on any criterion, so the order does not depend on the weights.

Corrections to v0.8: a quiet AFE causes no leader loss at low rates (v0.8 compared the arrival of the
entry into DL_HS_TERM with the line without the delay of the data path), and the words before
THS-SETTLE,min were not ignored, so `hs_settle_cyc` had no effect on the search.

**Table 7-5 — ADR-007: events and fallbacks**

| Event | A | B | C | **D** | E |
|---|---|---|---|---|---|
| AFE junk up to THS-SETTLE,min, all ones included | fails | fails | new value | works | works if the AFE does it |
| Word latency Λ differs from the value assumed | works | works | new value | works from ~300 Mb/s, new value below | works |
| Junk 20–40 ns beyond THS-SETTLE,min (non-compliant AFE) | fails | fails | new value | new value | new value |
| Line rate anywhere in 80 Mb/s to 2.5 Gb/s (K1) | fails with junk | fails from 1792 Mb/s with junk | works; one or two values below 200 Mb/s | works | works |
| THS-ZERO at the minimum or much longer (S5) | fails with junk | works | works | works | works |
| No software path for PHY timing (K3) | works | works | one more field to default | works | works |
| Sync errors at bring-up | no knob | no knob | knob in byte-clock steps | `hs_settle_cyc`, 5 ns steps | depends on the AFE |

"New value": a programmed value changes, the RTL does not. Fallbacks of D, in this order:
- reprogram `hs_settle_cyc`;
- if an AFE leaves junk after THS-SETTLE,min at low rates, add the 16-bit pattern of B behind the
  start (no failure in the model; not in the RTL);
- if the AFE team provides E, D stays correct with it;
- with a vendor hard PHY (ADR-001 C), Block No. 4 is bypassed.

Still open (OPEN ADR-007): the value of Λ, now set by Block No. 1 and confirmed with its RTL; whether
the CSI-2 controller needs
`errsotsynchs_x` after a corrupted leader that matches inside the payload, and whether it accepts the
`errsotsynchs_x` at the end of a burst that ends before a lock (§4.6, CSI team).

---

## 8. Verification Requirement

- **Stimulus.** A specification-compliant Tx BFM is required. An example Tx model may be reused
  only after its deviations are corrected: the trail must be the flipped last bit, THS-EXIT must be
  ≥ 100 ns, and the clock must be in quadrature with the data.
- **AFE model.** A behavioural AFE model converts the line-level stimulus to the §5.2 interface: one
  bit stream per data lane and the DDR clock, with programmable clock-to-data and lane-to-lane
  delays, duty-cycle error, and pulses at the HS-RX outputs while they start or stop.
- **Scenarios.**
  - 1/2/4 lanes, including bursts whose length is not a multiple of the lane count.
  - Rate sweep 80–1500 Mb/s (R1).
  - Samplers and deserializer (Block No. 1): every byte phase of the divider; clock-to-data delays
    across the setup and hold window on both edges, with duty-cycle error; pulses of the DDR clock
    during TCLK-SETTLE and at the HS exit of the clock lane, with no short pulse on `rxbyteclkhs`;
    clock-activity detection at 80, 800 and 1600 Mb/s, where a single toggle would alias, with
    `cl_rxclkactivehs` falling within TCLK-MISS.
  - Timing corners of THS-SETTLE, TCLK-SETTLE and the trail length; at 80 Mb/s the minimum
    THS-PREPARE + THS-ZERO, and an HS-0 much longer than the minimum (§4.6).
  - Start of the sync search (ADR-007): an HS-RX output during THS-PREPARE that is zero, random or
    all ones up to THS-SETTLE,min; word latency Λ from 1 to 3; the minimum and a long THS-PREPARE +
    THS-ZERO; every byte-clock phase. A sweep of `hs_settle_cyc` at each rate shall pass over a range
    that contains the Appendix B value (reference: the model of chapter 7).
  - SoT with a single-bit error (`errsoths_x`); with a corrupted leader that matches no offset:
    exactly one `errsotsynchs_x` and no later `rxsynchs_x` (Figure 5-2); with a corrupted leader that
    matches inside the payload: `rxsynchs_x` at that offset and no `errsotsynchs_x`; in a burst that
    ends before the search limit without a lock: one `errsotsynchs_x` in the last cycle of
    `rxactivehs_x`. An HS entry aborted in DL_HS_TERM: no PPI output.
  - Deskew burst: no `rxvalidhs_x` after the cancelled lock, and `rxskewcalhs_x` after
    `rxactivehs_x` falls (Figure 5-3); a normal burst after an all-ones HS-RX output during
    THS-PREPARE is not taken for a deskew burst.
  - Clock lane: TCLK-ZERO longer than TCLK-SETTLE + TCLK-MISS (Figure 5-7); the clock lane leaving HS
    after the last burst with TCLK-POST at its minimum (tail delayed until the clock runs again) and at
    the S12 value (tail delivered).
  - EoT on and off a byte boundary; a stored tail without a transition (stuck line, HS RX timeout).
  - Clock-lane and data-lane ULPS entry/exit; the four triggers; unknown escape command
    (`erresc_x`); false control (`errcontrol_x`).
  - HS RX timeout with the line still in HS (`stopstate_x` only after LP-11) and escape watchdog
    expiry; at 80 Mb/s an EoT done that arrives after the next HS request or escape entry has begun.
  - P/N-swapped and remapped lanes, in both HS and LP; the reset map; a map that is not a permutation.
  - Enables, also changed during a burst; `forcerxmode_x` held High until Stop has lasted TINIT, as the
    CSI-2 Rx controller does; `phy_core_rst`, TINIT and `init_done`.
  - Deskew burst detection (R1) and calibration (R2).
- **PPI monitor.** Checks the relations of Figures 5-1 to 5-8 on every burst and LP sequence.
- **Integration.** Co-simulation with the CSI-2 Rx controller RTL, checking the expectations of its
  lane management: inter-lane divergence ≤ 6 byte cycles (C10) and no stuck `rxactivehs_x` (C11).
- **Coverage.** Every FSM state and transition of Blocks No. 2 and 3, every PPI error output, every
  lane count.
- **Static timing.** The sampler window of §4.3 at the sign-off corners, with the samplers placed
  (OPEN ADR-001).

---

## 9. Open Items

**Table 9-1 — Open items**

| ID | Item | Default in this draft | Owner / with |
|---|---|---|---|
| K1 | Target line rate (1500 or 1792 Mb/s) and the release of 4K staggered HDR | R1 ≤ 1500 Mb/s | CSI team |
| K2 | LPDT ports: tie-off and clock domain | Tied 0 | CSI team |
| K3 / ADR-005 | Configuration path of the timers | Own APB subordinate | CSI team |
| K4 | Inter-lane byte divergence budget at the PPI | ≤ 6 byte cycles | CSI team |
| K5 | Register map of the CSI-2 Rx controller (PHY_CONFIG, PHY_STATUS, LANE_STATUS) | — | CSI team |
| K6 | `phy_core_rst` polarity and synchronicity; whether it is a reset-type port under the wrapper convention of the SoC (active-low `_n` at the wrapper); exact `init_done` and `forcerxmode_x` semantics | Active High, asynchronous; wrapper port active-low with the inverter inside `m_ftel_dphy_rx_wrap`; `forcerxmode_x` restarts initialization on its rising edge (§4.2) | CSI team |
| K8 | Longest HS burst per lane over all sensor modes and lane/rate combinations (sizes `hs_rx_timeout_cyc`) | 5802-byte line at 80 Mb/s on one lane | CSI team |
| ADR-001 | AFE interface details: maximum line rate of the HS-RX, clock-to-data delay difference and duty cycle of the DDR clock at the AFE outputs, HS-RX outputs while disabled or starting, one or two enables per lane, termination timing, maximum LP glitch width, delay line (R2); the cell library and its body bias, the sign-off corners, and the hand placement of the samplers and of the half-period path of the deserializer | Boundary: option A, announced by the AFE team (the AFE has the line receivers and the termination only; this IP samples, deserializes and aligns); details as assumed in §4.3 and §5.2 | AFE team; physical design |
| ADR-004 | Deskew algorithm, tap resolution and periodic calibration (R2) | Centre of the passing window; initial calibration only; needs a delay line, which the AFE does not have (§4.8) | This IP, after ADR-001 and S4 |
| S4 | Tx deskew behaviour (initial / periodic, exact pattern) | D-PHY v1.2 pattern [3] 🌐 | Tx side |
| S5 | Tx timing table, in particular the maximum THS-TRAIL (sizes `PARA_EOT_DELAY_BYTES`) | Specification minimums | Tx side |
| S9 | Lane order and P/N polarity on the board and package | Straight, no inversion; the data lanes can be remapped and inverted (§4.3), the clock lane cannot | Tx side |
| S12 | HS clock after the last burst, before the clock lane leaves HS (TCLK-POST) | Specification minimum: the tail of the last burst waits in the delay line until the clock runs again; this IP needs `PARA_EOT_DELAY_BYTES` + Λ + 2 byte clocks, 288·UI in R1 (§4.6) | Tx side; CSI team (its own need) |
| T1 | Mapping of the four trigger commands to `rxtriggeresc_x[3:0]` | Order of Table 4-6 (D-PHY [1]) | Specification check |
| ADR-006 | EoT: cut precision below ~270 Mb/s; order of `stopstate_x` and `rxactivehs_x` at the PPI; gap between bursts below ~240 Mb/s | Lane waits for EoT done (decided); `stopstate_x` may rise before the last byte, earlier than the CSI-2 Rx controller expects (to confirm); limits in §4.5 and §4.6 | This IP, CSI team, Tx side |
| ADR-007 | Sync search, start decided (DL_HS_RX, option D): word latency Λ of Block No. 1, which places `hs_settle_cyc`; behaviour after a corrupted leader at the PPI, including a burst that ends before a lock | Λ = 2; `PARA_SYNC_SEARCH_BYTES` = 16; `errsotsynchs_x` at the end of a burst without a lock (§4.6) | This IP (Λ, with the RTL of Block No. 1); CSI team (corrupted leader) |

---

## Appendix A. Requirement Traceability

Q1 to Q9 are the receiver requirements of the baseline standards (§1.5). C1 to C16 are the
requirements of the CSI-2 Rx controller, the user of the PPI (**[CSI]**). Each one is stated here and
traced to the sections that implement it.

**Table A-1 — Requirements of the baseline standards**

| ID | Requirement | Covered in |
|---|---|---|
| Q1 | A CSI-2 receiver uses D-PHY v1.2 (or C-PHY v1.0) [2] | §1 (v1.1 behaviour + deskew, ADR-003/004) |
| Q2 | Unidirectional slave: data lanes with HS-RX, LP-RX and CIL-SFEN, a clock lane with HS-RX, LP-RX and CIL-SCNN [2] | §4.4, §4.5 |
| Q3 | Continuous clock mandatory, non-continuous clock optional [2] | §4.4 |
| Q4 | Forward escape ULPS on every data lane [2] | §4.5 |
| Q5 | Deskew as in D-PHY v1.2, which can be bypassed at low rates or with an older transmitter [2] | §4.6, §4.8, `PARA_DESKEW_EN` |
| Q6 | An N-lane receiver works with an M-lane transmitter, M ≤ N [2] | `dl_enable_x`, §4.2 |
| Q7 | EoT, LP state and SoT between packets [2] | §4.5, §4.6 |
| Q8 | D-PHY errors reported to the protocol: SoT error, SoT sync error and false control; Stop state of each lane during initialization [2] | §4.5, §4.6, §5.1 |
| Q9 | Forward escape with ULPS and triggers on every lane; other escape functions optional; an unknown command raises the escape error [1] | §4.5 |

**Table A-2 — Requirements of the CSI-2 Rx controller**

| ID | Requirement | Covered in |
|---|---|---|
| C1 | Baseline CSI-2 v1.3 and D-PHY v1.2 | §1.4 Baselines |
| C2 | One clock lane and 1, 2 or 4 data lanes; 3 and 8 lanes are not supported | §3 (#1, #2), §5.1 |
| C3 | PPI of 8 bits per lane, bit 0 received first, on one shared `rxbyteclkhs` of line rate / 8 | §3 (#1, #2), §5.1 |
| C4 | Design envelope 1792 Mb/s per lane (`rxbyteclkhs` 224 MHz); deskew calibration required above 1.5 Gb/s | §1 release plan |
| C5 | Continuous clock only; `cl_rxclkactivehs` serves diagnosis | §1, §4.4 |
| C6 | `rxsynchs_x` is a one-cycle pulse in the cycle of the first payload byte | §4.6 |
| C7 | `rxvalidhs_x` may have gaps inside a burst | §4.6 |
| C8 | After `errsotsynchs_x`: no `rxsynchs_x`, `rxvalidhs_x` Low for the rest of the burst, `rxactivehs_x` held until EoT; `errsoths_x` is a one-cycle pulse and the burst stays usable | §4.6 |
| C9 | `rxskewcalhs_x` set when the all-ones sync is seen and held until the lane returns to Stop; no `rxvalidhs_x` or `rxsynchs_x` in a deskew burst; no calibration error output | §4.6 |
| C10 | Inter-lane byte divergence at the PPI of at most 6 `rxbyteclkhs` cycles | §8 integration check, K4 |
| C11 | The controller has no timeout for a stuck `rxactivehs_x`, so `rxactivehs_x` must always fall | §4.5 (timeout), §4.6 |
| C12 | ULPS and trigger indications, asynchronous, held until the return to Stop; LPDT ports declared but unused | §4.5, §5.1 |
| C13 | LP errors (`erresc_x`, `errsyncesc_x`, `errcontrol_x`), asynchronous, held until the next line-state change | §4.5, §5.1 |
| C14 | `cl_enable`, `dl_enable_x` and `forcerxmode_x` are levels from the registers of the controller (`lite_aclk`); `phy_core_rst` lasts at least 40 `core_clk` cycles; `init_done` returns in `core_clk` | §4.1, §4.2, §4.7 |
| C15 | `core_clk` of 200 MHz, free-running, from the system | §4.1, §4.2, §4.7 |
| C16 | Bring-up uses Stop state only: reset the D-PHY, enable the lanes, wait for Stop on every lane (the Tx holds LP-11 for TINIT ≥ 100 µs) | §4.1, §4.2, §4.7 |

## Appendix B. Receiver Timing Parameters

Specification values from D-PHY [1] ✅. `core_clk` period = 5 ns. Times are counted from the start of
LP-00 at the LP-RX output; the LP-RX delay of the AFE adds to them. The LP detection latency is
(`PARA_LP_SYNC_STAGES` + `PARA_LP_FILTER_CYC`) × 5 ns plus a sampling delay of 0–5 ns, 20–25 ns with
the defaults (§4.3); each FSM state adds 5 ns, so a lane enters its HS_PRPR state 25–30 ns and its
HS_TERM state 30–35 ns after the start of LP-00.

**Table B-1 — Receiver timing parameters**

| Parameter | Specification | Implementation |
|---|---|---|
| THS-SETTLE | 85 ns + 6·UI … 145 ns + 10·UI, from the start of THS-PREPARE | Ends the interval the sync search ignores (§4.6). DL_HS_RX is entered at t = 35 ns + 5 ns × `hs_settle_cyc` after the start of LP-00 (35 ns = (`PARA_LP_SYNC_STAGES` + `PARA_LP_FILTER_CYC` + 3) × 5 ns, the latest entry into DL_HS_TERM); t shall lie in [85 ns + 6·UI + Λ·8·UI, 145 ns + 13·UI + (Λ − 1)·8·UI], Λ = word latency (§5.2). `hs_settle_cyc` = round((115 ns + 9.5·UI + (Λ − 0.5)·8·UI − 35 ns) / 5 ns), the centre. With Λ = 2 ⚠️: 80 Mb/s 70, 750 Mb/s 22, 1500 Mb/s 19, 1792 Mb/s 18 |
| TCLK-SETTLE | 95 … 300 ns | `clk_settle_cyc` = (197.5 − 32.5) / 5 = 33: CL_HS_TERM is entered 30–35 ns after the start of LP-00 and lasts 33 cycles, so it ends 195–200 ns after it, at the centre of TCLK-SETTLE |
| TD-TERM-EN | ≤ 35 ns + 4·UI | `afe_term_en_x` 25–30 ns after the start of LP-00; the AFE has the remaining 5–10 ns + 4·UI for its LP-RX delay and the termination switch (§4.3) ⚠️ |
| TCLK-TERM-EN | ≤ 38 ns | `afe_cl_term_en` 25–30 ns after the start of LP-00; the AFE has the remaining 8–13 ns (§4.3) ⚠️ |
| THS-SKIP | 40 … 55 ns + 4·UI | Bits discarded before the last-transition search (Block No. 4): `eot_skip_bytes` places the cut between 40 ns and THS-TRAIL,min before LP-11, exactly only above ~270 Mb/s (§4.6) ⚠️ |
| TCLK-MISS | ≤ 60 ns | Clock-activity detection of Block No. 1: `cl_rxclkactivehs` falls at most 60 ns after the last DDR clock edge (§4.3) ⚠️ |
| TSETUP[RX], THOLD[RX] | Each ≥ 0.15·UI when the maximum rate is 1 Gb/s, ≥ 0.2·UI above: a setup and hold window of 0.3·UI (300 ps at 1 Gb/s) or 0.4·UI (267 ps at 1500 Mb/s) | Samplers of Block No. 1 on both edges of the DDR clock, hand-placed: the window holds their aperture and the clock-to-data delay differences of the AFE and of this IP (§4.3, OPEN ADR-001) ⚠️ |
| TCLK-POST | ≥ 60 ns + 52·UI, transmitter | This IP needs the HS clock for `PARA_EOT_DELAY_BYTES` + Λ + 2 byte clocks after the last data lane enters LP-11: 288·UI in R1, 320·UI in R2 with Λ = 2 (§4.6, OPEN S12) ⚠️ |
| TINIT (slave) | ≥ 100 µs | `tinit_cyc` = 20 000 |
| TLPX | ≥ 50 ns | Basis of the LP oversampling (ADR-002) |
| TWAKEUP | ≥ 1 ms | Tx-side; the Rx leaves ULPS on Mark-1 then Stop, no timer needed |

## Appendix C. Acronyms

| Acronym | Description |
|---|---|
| ADR | Architecture decision record (chapter 7) |
| AFE | Analog front-end: HS-RX, LP-RX and the switched termination, outside this IP |
| APB | AMBA Advanced Peripheral Bus |
| BFM | Bus functional model (verification stimulus) |
| CIL | Lane Control and Interface Logic of a D-PHY lane module |
| CIL-SCNN | Clock lane module of the slave side (D-PHY [1]) |
| CIL-SFEN | Data lane module of the slave side: forward-only high-speed, escape mode with events only, no reverse escape |
| CRC | Cyclic redundancy check of a CSI-2 packet |
| CSI-2 | MIPI Camera Serial Interface 2 |
| [CSI] | Requirement of the CSI-2 Rx controller, the user of the PPI (Appendix A) |
| CSR | Control and status register |
| D-PHY | MIPI D-PHY physical layer |
| DDR | Double data rate (the HS clock); DDR memory in Figure 1-1 |
| DFT | Design for test |
| ECC | Error-correcting code of a CSI-2 packet header |
| EoT | End of transmission (of an HS burst) |
| FSM | Finite state machine |
| FX1 | The receiving SoC that integrates this IP |
| HAS | High-level architecture specification |
| HDR | High dynamic range |
| HS | High-speed mode of a lane |
| HS-RX, HS-TX | High-speed receiver, transmitter |
| IP | Intellectual property block |
| ISP | Image signal processor |
| LP | Low-power mode of a lane |
| LP-RX, LP-TX, LP-CD | Low-power receiver, transmitter, contention detector |
| LP-xy | Low-power line state, Dp = x and Dn = y (for example LP-11 = Stop) |
| LPDT | Low-power data transmission |
| MIPI | MIPI Alliance, owner of the CSI-2 and D-PHY specifications |
| OPEN | Open point, tracked in chapter 9: Kx with the CSI team, Sx with the Tx side, ADR-nnn a design decision |
| PCB | Printed circuit board |
| PHY | Physical layer |
| PPI | PHY-Protocol Interface between the D-PHY and the CSI-2 Rx controller |
| R1, R2 | Releases of this IP (§1.4) |
| RTL | Register-transfer level |
| SoC | System on chip |
| SoT | Start of transmission (of an HS burst) |
| STA | Static timing analysis |
| TBC | To be confirmed: an assumption or proposal of this draft, not yet agreed (marked with a warning sign in the Markdown source) |
| THS-x, TCLK-x, TLPX, TINIT, TEOT, TWAKEUP | D-PHY timing parameters (Appendix B, D-PHY [1]) |
| UI | Unit interval: one bit time on a lane |
| ULM | Universal Lane Module of D-PHY |
| ULPS | Ultra-low power state |
| VOD | Differential voltage of the HS signal |
