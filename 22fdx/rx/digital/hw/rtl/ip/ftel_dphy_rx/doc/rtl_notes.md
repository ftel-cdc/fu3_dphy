# ftel_dphy_rx — RTL Design Notes (HAS ↔ RTL bridge and decisions)

> Companion to `spec.md` (the RTL follows HAS draft v0.14) and `rtl_rule.md` (v1.2). It records which HAS section each RTL block implements and why each RTL-level decision was
> made, so a reviewer can trace the RTL back to the HAS and a later change stays in one place. Same
> role as `ftel_intctl/doc/rtl_notes.md`.
> Markers: ✅ checked by a tool · ⚠️ assumption · 🔍 to confirm. Each decision states its confidence.

## 1. Status

- **Draft RTL, 2026-10-03.** Written against HAS v0.11 before HAS v1.0, by decision of 2026-10-03:
  every open item takes the default of the HAS and carries `// OPEN <id> REQ-xxx: <default>` at the
  single place that implements it. Such REQs are provisional and cannot be signed off.
- **HAS v0.12, same day.** It only states the AFE boundary explicitly, as announced by the AFE team:
  the AFE cuts the HS bit stream into 8-bit words at an arbitrary boundary, and Block No. 4 finds the
  byte boundary, which completes the deserialization. The RTL already worked this way. Only the
  `HAS` header field (v0.12) and the tag of the new REQ-324 at the barrel shifter of
  `m_ftel_dphy_rx_sync_search` changed.
- **HAS v0.13, 2026-10-06.** v0.13 corrects the AFE boundary to option A, as announced by the AFE
  team: the AFE has the HS-RX, the LP-RX and the switched termination only. Block No. 1 gains the
  samplers on both edges of the DDR clock `afe_cl_hs_clk`, the 1:8 deserializer, the byte clock
  (divider by 4 and clock gate) and the clock-activity detection; the AFE ports `afe_byteclk`,
  `afe_hs_word_x` and `afe_cl_clk_active` give way to `afe_cl_hs_clk` and `afe_hs_bit_x`.
- **RTL to HAS v0.14, 2026-10-07** (plan approved the same day). Designing the RTL of Block No. 1
  found errata, corrected in HAS v0.14 before the RTL was written:
  - one half-period path for the load phase of the falling-edge half, D-17;
  - the divider held in reset while the gate is closed, D-19;
  - both toggles in the DDR clock, D-20;
  - the two-stage HS path that sets Λ, D-18.

  The simulation of Block No. 1 (§8) found one more erratum: the loss of the clock is an upper bound
  of 60 ns, not a range of 50–60 ns (N-6).
  - New modules: `_byte_clk`, `_hs_deser` and `_clk_act`, plus copies of two fu2 clock cells,
    `_cg` and `_clk_inv` (D-23). `_afe_adapter` is rewritten for the HS part.
  - Small changes: `_cl_ctrl` (byte-clock enable, D-21), `_timing_init` (reset synchronizer of the
    DDR domain), the ports of the core and the wrapper, and the package (clock-activity window).
  - rtl_rule v1.2 allows exactly the clock structure of HAS §4.3, in `_byte_clk` only (K2, K12).
- **Checked:** VCS `+lint=all`, SpyGlass `lint_rtl` (one waiver, D-19), `check_rtl_rules.py`,
  `flow_check.py --phase P1|P2|P3a` (§7). **Simulated: Block No. 1 only**, with a directed TB at
  five line rates (§8). The rest of the IP is not simulated: lint-clean does not mean functionally
  correct. The unit testbenches (M3), the CDC/RDC runs (M4) and the timing constraints (M7, §6) are
  the next steps.
- **Release R1 only.** Block No. 5 (deskew calibration, R2, ADR-004) is absent: `PARA_DESKEW_EN` is
  locked to 0 and the delay taps are tied to 0. Block No. 8 (configuration and status, K3/ADR-005)
  is absent: see D-2.

## 2. Module hierarchy

```
m_ftel_dphy_rx_wrap                      wrapper: ports <dir>_dphy_rx_<name>, reset inverter (K6)
└─ m_ftel_dphy_rx  (u_dphy_rx_0)         core
   ├─ m_ftel_dphy_rx_timing_init         Block No. 6
   │  ├─ m_ftel_dphy_rx_rst_sync ×(3+N)  core, DDR, byte, Block No. 4 of each lane
   │  └─ m_ftel_dphy_rx_sync ×(1+2N)     cl_enable, dl_enable_x, forcerxmode_x
   ├─ m_ftel_dphy_rx_afe_adapter         Block No. 1
   │  ├─ m_ftel_dphy_rx_sync ×(2N+2)     LP lines, clock-lane LP lines
   │  ├─ m_ftel_dphy_rx_lp_filter ×(N+1)
   │  ├─ m_ftel_dphy_rx_hs_deser ×N      samplers and 1:8 deserializer of each physical lane
   │  ├─ m_ftel_dphy_rx_byte_clk         clock structure (rtl_rule K2): DDR clock inverted, divider,
   │  │  │                                load phases, clock gate, clock-activity toggles
   │  │  ├─ m_ftel_dphy_rx_rst_sync      byte-clock enable core -> DDR (gate enable, divider reset)
   │  │  ├─ m_ftel_dphy_rx_clk_inv       u_dont_touch_clk_inv_0
   │  │  └─ m_ftel_dphy_rx_cg            u_dont_touch_cg_0, rxbyteclkhs
   │  └─ m_ftel_dphy_rx_clk_act          clock activity in core_clk
   │     └─ m_ftel_dphy_rx_sync ×2       toggles DDR -> core
   ├─ m_ftel_dphy_rx_cl_ctrl             Block No. 2
   ├─ g_lane[x] (x = 0..N-1)
   │  ├─ m_ftel_dphy_rx_dl_ctrl          Block No. 3
   │  │  └─ m_ftel_dphy_rx_esc_decoder
   │  └─ m_ftel_dphy_rx_hs_datapath      Block No. 4
   │     ├─ m_ftel_dphy_rx_sync          sync-search start core -> byte
   │     ├─ m_ftel_dphy_rx_sync_search
   │     ├─ m_ftel_dphy_rx_eot
   │     └─ m_ftel_dphy_rx_tsync         EoT done byte -> core
   └─ m_ftel_dphy_rx_ppi_out             Block No. 7
packages: ftel_dphy_rx_config_pkg (generated from config/ftel_dphy_rx.yaml), ftel_dphy_rx_pkg
```

## 3. HAS ↔ RTL

| HAS | RTL | Notes |
|---|---|---|
| §3 Table 3-1, 3-2 | `ftel_dphy_rx_config_pkg` (generated), `PARA_*` of the core and wrapper | `config/validate_config.py` checks the values against §4.3, §4.6 and Appendix B |
| §4.1 crossings, Figure 4-1 | `m_ftel_dphy_rx_sync`, `_tsync`, `_rst_sync`; tags `CDC_CROSSING`, `CDC_QUASI_STATIC`, `CDC_GATING` | Every instance of a cell carries its crossing |
| §4.2 reset | `_timing_init` (reset synchronizers), `_wrap` (inverter) | D-4 |
| §4.3 Block No. 1 | `_afe_adapter`, `_lp_filter`, `_hs_deser`, `_byte_clk`, `_clk_act`, `_cg`, `_clk_inv` | D-5, D-6, D-17 – D-25 |
| §4.4 Block No. 2 | `_cl_ctrl` | D-8, D-9 |
| §4.5 Block No. 3 | `_dl_ctrl`, `_esc_decoder` | D-7, D-8, D-9 |
| §4.6 Block No. 4 | `_hs_datapath`, `_sync_search`, `_eot` | D-12, D-13, D-15 |
| §4.7 Block No. 6 | `_timing_init` | D-10, D-11 |
| §4.9 Block No. 7 | `_ppi_out` | — |
| §4.10 Block No. 8 | absent | D-2 |
| §5.1, §5.2 | ports of `m_ftel_dphy_rx` (HAS names) and `m_ftel_dphy_rx_wrap` (`dphy_rx` token) | Per-lane signals are packed arrays: PPI ports by logical lane, AFE ports by physical lane |

The REQ-level trace is generated: `req/rtm.json` (`flow_check.py --phase P3a`) lists, for every REQ,
whether it is in the RTL scope (`req/rtl_scope.json`), the files that tag it and its OPEN tag.

## 4. RTL decisions

**D-1 Field widths of the run-time timing fields** (confidence HIGH). `hs_settle_cyc` 8, `clk_settle_cyc`
8, `tinit_cyc` 16, `hs_rx_timeout_cyc` 20, `esc_timeout_cyc` 20, `eot_skip_bytes` 6 bits (YAML
`runtime.*.width`). Each holds its reset value and the Appendix B value at every rate of the release
(80 Mb/s needs `hs_settle_cyc` = 70); the timeouts reach 5.2 ms, four times the default, for K8.
`validate_config.py` (CFG-08, CFG-09, CFG-14) rejects a width that is too small.

**D-2 Block No. 8 absent** (HIGH). The configuration path is open (K3, ADR-005), so the core takes the
fields as inputs (`i_cfg_timing`, `i_cfg_lane_map`, `i_cfg_lane_pol`, quasi-static) and exports the
status: the FSM states and, per event, the source half of a toggle synchronizer (a level that inverts
on each event). Block No. 8 will add the configuration registers (reset values: config package and
`C_LANE_MAP_RST` / `C_LANE_POL_RST`), the destination halves and the counters, without touching the
blocks. The wrapper ports `i_dphy_rx_cfg_*` and `o_dphy_rx_sts_*` are placeholders.

**D-3 No configuration-clock reset synchronizer** (HIGH). HAS §4.2 gives each domain a reset
synchronizer; the configuration clock exists only with Block No. 8, so its synchronizer comes with it.

**D-4 Reset of Block No. 4 of a lane** (MEDIUM). The asynchronous input of its reset synchronizer is
the byte-domain reset AND a core register holding `dl_enable_x & cl_enable` (both synchronized). The
register keeps the clear free of glitches; the AND sits on the reset path, which an RDC run (M4) has
to accept as intended. Release: second byte-clock edge after the enable, as HAS §4.2 requires.

**D-5 LP filter** (HIGH). Run-length counter saturating at `PARA_LP_FILTER_CYC + 1`; the state changes
when the last `PARA_LP_FILTER_CYC + 1` samples agree, which gives the latency (S + F) cycles plus the
sampling delay of §4.3. Reset value LP-11, so the zeros of the synchronizers right after reset are
filtered out; the TINIT counter restarts on any other state anyway.

**D-6 Lane-map field** (MEDIUM). Width `f_lane_sel_w(N)` = max(1, log2 N), so every value selects an
existing physical lane for N = 2 and 4. With one lane the LP and HS paths read physical lane 0; the
field still enters the AFE-enable rule of §4.3, so a value other than 0 leaves the lane's AFE
disabled ("a physical lane that no logical lane selects has its enables off").

**D-7 Escape decoder** (HIGH). The decoder keeps its own previous-state register; the eighth bit and
the command are decoded in the cycle the Space starts, so the lane FSM moves on the same edge as for
any other line-state decision and the trigger or ULPS output follows the line like every LP output.

**D-8 FSM coding and precedence** (HIGH for the coding, MEDIUM for the precedence). State and outputs
are registered together, the outputs computed from the next state (glitch-free AFE controls, no
extra latency). Precedence in Block No. 3: disable or rising `forcerxmode_x` → DL_INIT; then the
explicit rows of Table 4-5, with LP-11 → DL_ERR rows before the general LP-11 → DL_STOP rule; then the
escape watchdog. A line state not named for a state keeps the state (e.g. LP-01 in DL_LP_RQST).

**D-9 Settle counters** (HIGH). The counter runs in the HS_TERM state and restarts outside it; the
state lasts exactly `hs_settle_cyc` (data lane) cycles, and at least `clk_settle_cyc` cycles until the
clock is active (clock lane), which is the timing of Appendix B.

**D-10 Initialization flag** (MEDIUM, K6). A lane is initialized when its LP-11 counter reaches
`tinit_cyc`; the flag stays set until the next lane reset (disable, rising `forcerxmode_x`,
`phy_core_rst`), so `init_done` does not drop during HS bursts.

**D-11 Watchdogs** (HIGH). Expiry when the count of cycles in the watched states equals the field
value; the expiry is a one-cycle pulse because the lane leaves the state on it, and it inverts the
status toggle.

**D-12 Block No. 4 pipeline** (MEDIUM). The window registers load the AFE word while the synchronized
start is High; each byte clock the sync search produces one delay-line entry from the window
(combinational), whose active flag is the synchronized start of that cycle. The EoT request is the
cycle in which the synchronized start is first Low: the backward scan runs on the line contents of
that cycle (combinational) and its result is applied as the line shifts. Margin: the entry of the last
payload byte is written Λ + 2 byte clocks after its last bit at the line (No. 1 register, window,
line), later than the depth estimate of §4.6 assumes, which covers the cycle that applies the cut.
An `eot_skip_bytes` beyond the line is clamped to its oldest entry.

**D-13 Deskew detection** (HIGH). The first non-zero word gives the position f of the first 1 and
whether bits f..7 are ones; the next word must be all ones; for f > 0 the low f bits of the third
word must be ones: 16 bits in total (`C_DESKEW_RUN`), detected 1 or 2 words after the possible lock on
`00011111`. The detection clears the flags of the entry being written and of the three newest entries.

**D-14 Status events** (MEDIUM). SoT and SoT sync errors are counted when their flags leave the delay
line (as the PPI sees them, after a possible deskew cancellation); the EoT sync error when the cut is
decided. "Aborted clock-lane requests" counts both aborted HS and aborted ULPS entries (any entry into
CL_WAIT).

**D-15 Priority encoders without loops** (HIGH). The lowest set bit is isolated as a one-hot vector
(`v & (~v + 1)`) and encoded by OR-reduction in generate blocks. Loops that assign a variable several
times in one always block (SpyGlass W415a) are not used, so the IP needs no lint waiver.

**D-16 Byte clock** (superseded on 2026-10-07 by D-19 and D-25). Until HAS v0.12 `afe_byteclk` was
forwarded by Block No. 1; since HAS v0.13 Block No. 1 generates `rxbyteclkhs` from the DDR clock.

**D-17 Deserializer structure** (HIGH for the structure, MEDIUM for the margin). Per physical lane,
each edge of the DDR clock has a sampler, a 4-bit shift register (newest bit at the top) and a 4-bit
parallel register (`_hs_deser`). The rising-edge parallel register loads at a strobe of the divider;
the falling-edge one takes that strobe through one flip-flop on the inverted DDR clock
(`reg_load_fall` in `_byte_clk`, shared by the lanes), half a period later. That arc is the only
path shorter than one DDR period (HAS v0.14 REQ-342, REQ-365). The word interleaves the halves,
bit 0 from the rising edge.
- Margin of the arc: half a period, plus the clock-inverter delay, minus clock-to-output and setup.
  From the 130 nm library at 1.35 V/125 °C, before wiring, this leaves about +110 ps at 1500 Mb/s
  and about 0 at 1792 Mb/s.
- Rejected alternative: retime the falling-edge sample to the rising edge right after the sampler.
  The inverter delay then counts against the arc: about +10 ps at 1500 Mb/s and −100 ps at 1792 Mb/s.

**D-18 Load phase, byte-clock phase and Λ** (HIGH). The divider counts 0..3 and the divided clock is
its top bit. The load strobe is High in the DDR period after the rising edge of the divided clock.
- Timing of one word: the rising-edge half loads 1 period after a byte-clock edge, the falling-edge
  half 0.5 period after that. The first `rxbyteclkhs` stage takes the word 3 periods after the
  rising-edge half loads, while both halves are stable. The HS path register takes it one byte clock
  later.
- Latency: from the end of the last bit at the line to the HS path register, 8.25 DDR periods =
  2.0625 byte clocks, plus fixed delays. That is the Λ = 2 of HAS §5.2, measured in §8.
- Why 3 periods and not 2: it keeps Λ near 2 at 80 Mb/s, where a byte clock is 100 ns and the
  window of `hs_settle_cyc` is narrowest. The price is the DDR → byte hold margin, about one DDR
  period minus the insertion delay of `rxbyteclkhs` (§6).

**D-19 Divider held in reset while the gate is closed** (HIGH; HAS v0.14 REQ-364). The reset synchronizer
of the byte-clock enable (core → DDR) drives both the enable of the clock gate and the asynchronous
reset of the divider and of the two load-phase flip-flops.
- What a free-running divider would allow:
  - When the DDR clock stops in the high half of the divided clock, the latch of the gate holds 1
    and `rxbyteclkhs` stays High.
  - A pulse at the HS-RX output at the next start could then glitch the divided clock while the gate
    passes it.
  - In zero-delay RTL, the enable and the divided clock can change on the same DDR edge (a race at
    the latch).
- With the reset: `rxbyteclkhs` is Low while the gate is closed, and the first pulse after it opens
  is whole. It starts 3–4 DDR periods after `cl_rxclkactivehs`, 5 when the synchronizer resolves
  late.
- SpyGlass reports the reset used as data (STARC05-1.3.1.3). The waiver names this decision
  (`lint/lint_waiver.tcl`, rtl_rule K2 (4)).

**D-20 Clock-activity toggles** (HIGH). A free-running 3-bit counter in the DDR clock, reset by the DDR
reset synchronizer of Block No. 6, gives both toggles:
- bit 0 changes on every rising edge (line rate / 4);
- bit 2 changes on every fourth rising edge (line rate / 16).

They do not use the divider, which is held in reset before CL_HS_CLK, while the detection must see
the clock in CL_HS_TERM. `_clk_act` synchronizes each toggle (2 flip-flops) and restarts a 3-bit
window counter on every change; the clock is active while a change is seen or the counter is not 0
(`C_CLK_ACT_WIN_CYC` = 8). `o_clk_active` is not registered: one more cycle would let
`cl_rxclkactivehs` fall after TCLK-MISS when a synchronizer resolves late.

**D-21 Byte-clock enable of Block No. 2** (HIGH). A register of its own, set from the next state like
`cl_rxclkactivehs` (High in CL_HS_CLK). The PPI output and the asynchronous clear of the gate-enable
synchronizer near the AFE do not share a net.

**D-22 Scan enable of the clock gate tied Low** (MEDIUM). The IP has no scan plan yet; at integration the
DFT flow connects the scan enable of the `m_fpt_lib_cg` cell.

**D-23 Clock cells** (HIGH). `m_ftel_dphy_rx_cg` and `m_ftel_dphy_rx_clk_inv` keep the ports of
`m_fpt_lib_cg` and `m_fpt_lib_clk_inv` of the fu2 lib and their behavioural model. At integration only
the module name changes, as for the synchronizer cells. The instances are named `u_dont_touch_*`, the
fu2 convention that keeps synthesis from optimizing them (rtl_rule K10, K12).
- Do not use `m_fpt_lib_dff_falling_edge_async_reset_n` for the falling-edge flip-flops: in its
  GF130 branch it maps to `DFFRQ`, a rising-edge flip-flop.

**D-24 Polarity inversion after the HS path register** (MEDIUM). As in Figure 4-2, the word is inverted
after the second `rxbyteclkhs` stage and before the lane-map multiplexer. Up to v0.12 the RTL inverted
it before its single register. Same function; the XOR now sits in front of Block No. 4 (§6).

**D-25 rxbyteclkhs returns through the core** (HIGH). `_byte_clk` generates `rxbyteclkhs` inside
`_afe_adapter`, whose output goes to the core net `w_byte_clk`. That net comes back as the input
`i_byte_clk` of the HS path registers (rtl_rule N11: a block clocks its flip-flops from inputs) and
goes to Blocks No. 4, 6 and 7.

## 5. Notes for the HAS (no RTL question pending)

No CF-GAP stop occurred: every behaviour visible at the PPI or the AFE is defined by the HAS (v0.11; Block No. 1
by v0.14). While
writing the RTL these points were read literally; the HAS could state them to remove doubt:

| # | Point | RTL reading |
|---|---|---|
| N-1 | A burst without a lock whose line is stuck at one level: §4.6 clears every entry of the burst still in the delay line, and also asks for the SoT sync error flag on its last active entry | No active entry remains, so no `errsotsynchs_x` is raised for that burst; the EoT sync error status is raised |
| N-2 | Escape watchdog expiry and a line-state transition in the same cycle | The line-state transition wins (D-8) |
| N-3 | Line states not named in Tables 4-4 and 4-5 (e.g. LP-01 in DL_LP_RQST, LP-00 in DL_STOP) | The state is kept (D-8) |
| N-4 | `rxclkesc_x` is the XOR of the synchronized Dp and Dn, combinational | Cannot glitch in escape mode (one line changes at a time); a direct LP-01 ↔ LP-10 change could |
| N-5 | Status of aborted clock-lane requests | Both HS and ULPS aborts (D-14) |
| N-6 | Loss of the clock, HAS v0.13: `cl_rxclkactivehs` falls 50–60 ns after the last clock edge | The toggles change on rising edges only. The trail ends on a falling edge, and near 800 and 1600 Mb/s the edge toggle aliases. Simulation (§8): 38.5–42.2 ns after the last edge at 80 Mb/s, at most 54.7 ns at every rate. HAS v0.14 states the upper bound, at most 60 ns, which is TCLK-MISS |

## 6. Timing risks for Stage D (not measured)

- The EoT backward scan (D-12) is combinational over `PARA_EOT_DELAY_BYTES` entries in one byte clock
  (5.33 ns at 1500 Mb/s). Fallback: pipeline the scan by K cycles and deepen the line by K.
- The eight comparators, the lock priority and the barrel shifter of the sync search are one cycle.
  The polarity XOR and the lane-map multiplexer now sit in front of them (D-24).
- **Block No. 1, constraints the SDC needs at M7** (`sdc/m_ftel_dphy_rx_wrap.sdc` is still a stub):
  - Clocks:
    - `afe_cl_hs_clk`: period 2 UI at the top rate of the release.
    - The inverted DDR clock, through the clock inverter.
    - The divided clock: a generated clock, divide by 4, on the top bit of `reg_div_cnt`.
    - `rxbyteclkhs` behind the clock gate. The gating check of the latch-based gate is inferred.
    - `core_clk` asynchronous to the DDR family (`ddr`, `ddrn`, byte).
  - Samplers: source-synchronous input delays on `afe_hs_bit_x`, on both edges of `afe_cl_hs_clk`
    (hand placement, HAS §4.3, OPEN ADR-001).
  - Load phase, `reg_load` → `reg_load_fall`: half a period, the only short path. About +110 ps at
    1500 Mb/s and 0 at 1792 Mb/s at 1.35 V/125 °C before wiring. The two flip-flops sit with the
    samplers (D-17, REQ-365).
  - Parallel registers → first `rxbyteclkhs` stage: the halves change once per word, 3 DDR periods
    (2.5 for the falling half) before the byte-clock edge that takes them. This needs a multicycle
    path (setup 3, hold 2, in the DDR clock); otherwise STA assumes a change on every DDR edge.
  - Hold of that transfer, rising half: about one DDR period plus the clock-to-output delay, minus
    the insertion delay of `rxbyteclkhs` relative to the DDR clock (divider flip-flop, gate, byte
    clock tree). At 1792 Mb/s a byte clock tree slower than about 1.5 ns needs hold buffers on
    these 8 bits per lane; setup has more than 3 DDR periods.
  - Reset recovery: the gate-enable reset is released on a rising DDR edge. The divider recovers in
    one period, `reg_load_fall` in half a period (rtl_rule K3, K11).
  - Crossings: the reset synchronizers (`byteclk_en`, DDR reset) and the toggle synchronizers have
    asynchronous inputs, so their first stage is a false path, as for every synchronizer of
    Table 4-2.

## 7. Lint log

One line per correction round (rule 1 of `/dphy_rtl_gen`: at most 3 rounds per module).

| Module | Round | Finding | Fix |
|---|---|---|---|
| `m_ftel_dphy_rx_afe_adapter` | 1 | VCS Lint-[UI]/[ONGS]: clock-lane AFE enables not connected | `o_afe_cl_hs_en`, `o_afe_cl_term_en` assigned |
| `m_ftel_dphy_rx_timing_init` | — | checker N11 on the output resets and on `i_phy_core_rst` | checker corrected: N11 covers clock inputs and active-low reset inputs (rtl_rule 1.1); no RTL change |
| `m_ftel_dphy_rx_dl_ctrl` | 1 | checker T1: REQ-135 tagged but not in the header | header completed |
| whole IP (SpyGlass) | 1 | 29 W415a (multiple assignments in one always block), 3 W528 (timer fields distributed but unused) | encoders rewritten (D-15); Block No. 6 distributes only the fields Blocks No. 2–4 use |
| whole IP (`flow_check` P3a) | 1 | CF-COVER REQ-164, REQ-182 untagged | tags added in `_eot` and `_dl_ctrl` |
| whole IP (HAS v0.12) | 1 | P2 CF-CONFIG: config package header behind the spec; P3a CF-COVER REQ-324 (this IP completes the deserialization) untagged | package regenerated; tag added at the barrel shifter of `_sync_search` |

| `m_ftel_dphy_rx_*` (HAS v0.14, rtl_rule 1.2) | 1 | VCS per module (`_cg`, `_clk_inv`, `_clk_act`, `_byte_clk`, `_hs_deser`, `_afe_adapter`, `_timing_init`, `_cl_ctrl`): 0 / 0 / 0 at the first round | — |
| whole IP (SpyGlass, HAS v0.14) | 1 | STARC05-1.3.1.3 (AsyncResetOtherUse): the gate-enable reset synchronizer output is also the enable of the clock gate | intended structure of rtl_rule K2 (4), waived with D-19 in `lint/lint_waiver.tcl` (first attempt: `-comment {...}` is an SGDC syntax error, the comment must be a quoted string) |
| whole IP (`flow_check` P3a, HAS v0.14) | 1 | CF-COVER REQ-083 (termination enable from the FSM register, no extra timer) untagged | tags added at the state registers of `_dl_ctrl` and `_cl_ctrl` |

Final state (HAS v0.14, rtl_rule 1.2): `check_rtl_rules` 0 violations on 22 files; VCS 0 Error /
0 Warning / 0 Lint for `PARA_NUM_LANES` = 1, 2, 4; SpyGlass `lint_rtl` 0 Fatal / 0 Error / 0 Warning,
one waiver (D-19).
VCS `+lint=all` does not report latches or unused nets (probe of 2026-10-03); SpyGlass covers them.

## 8. Simulation of Block No. 1 (directed, 2026-10-07)

`sim/tb_afe_adapter/run.sh`: `tb_afe_adapter.sv` drives the core `m_ftel_dphy_rx` with four lanes.
The clock-lane FSM, the reset synchronizers and the byte-clock enable are the real ones.
- Per line rate: four clock-lane bursts of 64–67 DDR periods, so the divider stops at every phase.
- Data: PRBS31 on lanes 0 and 2; lane 1 repeats lane 0 and lane 3 inverts lane 2, with polarity bits
  `1010`.
- Pulses at the HS-RX output during TCLK-SETTLE and after the trail.
- Zero-delay RTL. The checks are listed in the TB header; they cover REQ-340, REQ-341, REQ-343,
  REQ-344, REQ-346, REQ-347, REQ-364 and the Λ of REQ-266.

| Rate (Mb/s) | Words checked | Λ (byte clocks) | `rxbyteclkhs` start after `cl_rxclkactivehs` (DDR periods) | Loss seen after the last rising edge (ns) | `cl_rxclkactivehs` falls after the last edge (ns) | Result |
|---|---|---|---|---|---|---|
| 80 | 55 | 2.0625 | 3.41–3.56 | 46.0–49.7 | 38.5–42.2 | PASS |
| 800 | 51 | 2.0625 | 3.12–3.87 | 41.0–49.1 | 44.7–52.8 | PASS |
| 1500 | 46 | 2.0625 | 3.03–3.96 | 45.2–49.1 | 49.5–53.5 | PASS |
| 1600 | 45 | 2.0625 | 3.07–3.51 | 46.1–49.6 | 50.4–54.0 | PASS |
| 1792 | 44 | 2.0625 | 3.34–3.92 | 46.0–49.4 | 50.4–53.8 | PASS |

Every word is 8 consecutive bits, bit 0 received first, and words follow each other. All lanes are
cut at the same time, and the polarity inversion works.

`rxbyteclkhs` behaves as specified:
- It rises only in CL_HS_CLK, never on a pulse at the HS-RX output.
- Every pulse is whole: period 4 DDR periods, high phase 2.
- It is Low after the gate closes, whether the clock stopped in the high or the low half.

The loss of the clock is never seen while the clock runs, including at 800 and 1600 Mb/s where the
edge toggle aliases. At 800 Mb/s it is seen up to about 3 DDR periods early, from the slow toggle.

One TB artefact was corrected before the final runs: the half UI is rounded to the 1 ps simulation
resolution, and the expected periods are derived from it.
