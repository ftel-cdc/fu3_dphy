# ftel_dphy_rx — RTL Design Notes (HAS ↔ RTL bridge and decisions)

> Companion to `spec.md` (HAS draft v0.11) and `rtl_rule.md` (v1.1). It records which HAS section each
> RTL block implements and why each RTL-level decision was made, so a reviewer can trace the RTL back
> to the HAS and a later change stays in one place. Same role as `ftel_intctl/doc/rtl_notes.md`.
> Markers: ✅ checked by a tool · ⚠️ assumption · 🔍 to confirm. Each decision states its confidence.

## 1. Status

- **Draft RTL, 2026-10-03.** Written against HAS v0.11 before HAS v1.0, by decision of 2026-10-03:
  every open item takes the default of the HAS and carries `// OPEN <id> REQ-xxx: <default>` at the
  single place that implements it. Such REQs are provisional and cannot be signed off.
- **Checked:** compile and lint only (VCS `+lint=all`, SpyGlass `lint_rtl`, `check_rtl_rules.py`,
  `flow_check.py --phase P3a`). **Not simulated:** lint-clean does not mean functionally correct.
  The unit testbenches (M3) and the CDC/RDC runs (M4) are the next steps.
- **Release R1 only.** Block No. 5 (deskew calibration, R2, ADR-004) is absent: `PARA_DESKEW_EN` is
  locked to 0 and the delay taps are tied to 0. Block No. 8 (configuration and status, K3/ADR-005)
  is absent: see D-2.

## 2. Module hierarchy

```
m_ftel_dphy_rx_wrap                      wrapper: ports <dir>_dphy_rx_<name>, reset inverter (K6)
└─ m_ftel_dphy_rx  (u_dphy_rx_0)         core
   ├─ m_ftel_dphy_rx_timing_init         Block No. 6
   │  ├─ m_ftel_dphy_rx_rst_sync ×(2+N)  core, byte, Block No. 4 of each lane
   │  └─ m_ftel_dphy_rx_sync ×(1+2N)     cl_enable, dl_enable_x, forcerxmode_x
   ├─ m_ftel_dphy_rx_afe_adapter         Block No. 1
   │  ├─ m_ftel_dphy_rx_sync ×(2N+3)     LP lines, clock-lane LP lines, afe_cl_clk_active
   │  └─ m_ftel_dphy_rx_lp_filter ×(N+1)
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
| §4.3 Block No. 1 | `_afe_adapter`, `_lp_filter` | D-5, D-6 |
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

**D-16 Byte clock** (HIGH). `afe_byteclk` is forwarded by Block No. 1 and passes through Block No. 7 as
wires only (HAS §4.3, §4.9; rtl_rule K2); every byte-domain flip-flop uses that net.

## 5. Notes for the HAS (no RTL question pending)

No CF-GAP stop occurred: every behaviour visible at the PPI or the AFE is defined by HAS v0.11. While
writing the RTL these points were read literally; the HAS could state them to remove doubt:

| # | Point | RTL reading |
|---|---|---|
| N-1 | A burst without a lock whose line is stuck at one level: §4.6 clears every entry of the burst still in the delay line, and also asks for the SoT sync error flag on its last active entry | No active entry remains, so no `errsotsynchs_x` is raised for that burst; the EoT sync error status is raised |
| N-2 | Escape watchdog expiry and a line-state transition in the same cycle | The line-state transition wins (D-8) |
| N-3 | Line states not named in Tables 4-4 and 4-5 (e.g. LP-01 in DL_LP_RQST, LP-00 in DL_STOP) | The state is kept (D-8) |
| N-4 | `rxclkesc_x` is the XOR of the synchronized Dp and Dn, combinational | Cannot glitch in escape mode (one line changes at a time); a direct LP-01 ↔ LP-10 change could |
| N-5 | Status of aborted clock-lane requests | Both HS and ULPS aborts (D-14) |

## 6. Timing risks for Stage D (not measured)

- The EoT backward scan (D-12) is combinational over `PARA_EOT_DELAY_BYTES` entries in one byte clock
  (5.33 ns at 1500 Mb/s). Fallback: pipeline the scan by K cycles and deepen the line by K.
- The eight comparators, the lock priority and the barrel shifter of the sync search are one cycle.

## 7. Lint log

One line per correction round (rule 1 of `/dphy_rtl_gen`: at most 3 rounds per module).

| Module | Round | Finding | Fix |
|---|---|---|---|
| `m_ftel_dphy_rx_afe_adapter` | 1 | VCS Lint-[UI]/[ONGS]: clock-lane AFE enables not connected | `o_afe_cl_hs_en`, `o_afe_cl_term_en` assigned |
| `m_ftel_dphy_rx_timing_init` | — | checker N11 on the output resets and on `i_phy_core_rst` | checker corrected: N11 covers clock inputs and active-low reset inputs (rtl_rule 1.1); no RTL change |
| `m_ftel_dphy_rx_dl_ctrl` | 1 | checker T1: REQ-135 tagged but not in the header | header completed |
| whole IP (SpyGlass) | 1 | 29 W415a (multiple assignments in one always block), 3 W528 (timer fields distributed but unused) | encoders rewritten (D-15); Block No. 6 distributes only the fields Blocks No. 2–4 use |
| whole IP (`flow_check` P3a) | 1 | CF-COVER REQ-164, REQ-182 untagged | tags added in `_eot` and `_dl_ctrl` |

Final state: `check_rtl_rules` 0 violations on 17 files; VCS 0 Error / 0 Warning / 0 Lint for
`PARA_NUM_LANES` = 1, 2, 4; SpyGlass `lint_rtl` 0 Fatal / 0 Error / 0 Warning, no waiver.
VCS `+lint=all` does not report latches or unused nets (probe of 2026-10-03); SpyGlass covers them.
