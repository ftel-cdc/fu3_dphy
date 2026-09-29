# ftel_dphy_rx figures

Figures of the HAS (`../spec.md`). Each figure has a drawio source (`.drawio`) and an SVG render
(`.svg`). Both are committed, and `spec.md` embeds the SVG. PNG renders are local build products
(`.gitignore`), used for review and later for the docx build.

## Rules

The ten conventions of `reference_diagram_conventions`, the figure rules of `ftel_intctl`, and
four additions for this IP. `check_figures.py` enforces the rules marked (checked).

1. Main flow left to right: AFE side on the left, PPI side on the right, shared blocks at the bottom.
2. Every arrow carries a signal name, group name or bus width.
3. Signal classes by line style, explained in a legend: HS data bus (thick), control and status
   (thin), clock and reset (grey dashed), configuration (green dotted), not used (light grey dashed).
4. Repeated structure in a dashed frame with its count (for example "replicated PARA_NUM_LANES times").
5. Grid-aligned, fontSize >= 18 on every label (checked), strokeWidth 2, block titles in bold.
6. Port and parameter names identical to spec.md (checked).
7. Few crossings, orthogonal routing, arc jumps where lines cross.
8. A legend whenever more than one class is used.
9. Connected edges; ASCII-only XML (checked; U+00A0 written by the drawio editor is accepted).
10. Only FTEL_DRAWIO_LIB_V1 components (checked), no text blocks with RTL equations.
11. **Hierarchy.** Every block drawn at one level has its own figure at the next level, until the
    leaves are standard elements (register, counter, comparator, mux, gate, FSM, synchronizer).
    A block whose content is still OPEN is drawn at its boundary only, with the ID of the open item.
    The figure title names the figure it details.
12. **Text first.** Every function drawn in a figure is described in spec.md; a gap found while
    drawing is fixed in the text (marked ⚠️) in the same change.
13. **Clock domains** by fill colour: `core_clk` blue, `rxbyteclkhs` orange, configuration clock
    green, analog (AFE) grey, mixed or asynchronous white. In leaf-level figures only the clocked
    elements (registers, counters, FSM states, synchronizers) carry the fill; gates, multiplexers and
    comparators are white.
14. **No emoji in figures.** Open items are written as text, for example "(OPEN K3)" or "(R2)".

## Figure tree

| Figure | File | Shows | Details |
|---|---|---|---|
| 1-1 | `ftel_dphy_rx_system` | System context: physical signal path from the sensor to the ISP | CSI-2 v1.3 Annex B Figure 146 |
| 1-2 | `ftel_dphy_rx_layers` | Layer view: CSI-2 Tx and Rx are logical peers, the data crosses the D-PHY | Figure 1-1 |
| 1-3 | `ftel_dphy_rx_directions` | Data direction versus control direction | Figure 1-1 |
| 2-1 | `ftel_dphy_rx_ulm_data` | Data lane module: Universal Lane Module reduced to CIL-SFEN | D-PHY v1.1 Figure 4 |
| 2-2 | `ftel_dphy_rx_ulm_clock` | Clock lane module: Universal Lane Module reduced to CIL-SCNN | D-PHY v1.1 Figure 4 |
| 2-3 | `ftel_dphy_rx_lanes` | Lane configuration: 1 clock lane + N data lanes | D-PHY v1.1 Figure 8 |
| 2-4 | `ftel_dphy_rx_top` | Top level: blocks No.1 to No.8 | Figures 2-1, 2-2 |
| 4-1 | `ftel_dphy_rx_sync_cells` | Level, toggle and reset synchronizers | all blocks |
| 4-2 | `ftel_dphy_rx_afe_adapter` | Block No.1: LP path, HS path, lane map, AFE controls | Figure 2-4 |
| 4-3 | `ftel_dphy_rx_lp_filter` | LP glitch filter | Figure 4-2 |
| 4-4 | `ftel_dphy_rx_cl_fsm` | Block No.2: clock lane FSM and settle counter | Figure 2-4 |
| 4-5 | `ftel_dphy_rx_dl_ctrl` | Block No.3: structure and output registers | Figure 2-4 |
| 4-6 | `ftel_dphy_rx_dl_fsm` | Data lane FSM | Figure 4-5 |
| 4-7 | `ftel_dphy_rx_esc_decoder` | Escape decoder | Figure 4-5 |
| 4-8 | `ftel_dphy_rx_hs_datapath` | Block No.4: sync search, deskew detection, byte alignment | Figure 2-4 |
| 4-9 | `ftel_dphy_rx_eot` | EoT delay line and trailer removal | Figure 4-8 |
| 4-10 | `ftel_dphy_rx_timing_init` | Block No.6: resets, enables, TINIT, watchdogs, `init_done` | Figure 2-4 |
| 4-11 | `ftel_dphy_rx_deskew` | Block No.5: boundary only (content OPEN ADR-004) | Figure 2-4 |
| 4-12 | `ftel_dphy_rx_ppi_out` | Block No.7: output gating, `rxclkesc_x`, tie-offs | Figure 2-4 |
| 4-13 | `ftel_dphy_rx_cfg_status` | Block No.8: configuration and status (bus OPEN K3) | Figure 2-4 |

## Rendering

```sh
python3 render_drawio.py ftel_dphy_rx_*.drawio   # writes <name>.svg and <name>.png beside each source
python3 render_drawio.py --selftest              # FTEL library glyph sheet, must match selftest/*.png
python3 check_figures.py                         # rules above; --selftest-negative tests the checker
```

- The renderer is drawio 31.5.3, pinned by `drawio_lock.json` (sha256 of `viewer-static.min.js` and
  `stencils.min.js`). The files are taken from `$FTEL_DPHY_RX_DRAWIO_DIR`, from `.drawio_cache/`
  (filled by `render_drawio.py --fetch`, needs network) or from the VSCode extension
  `hediet.vscode-drawio`, and only when their sha256 matches the lock.
- A render is offline: Chrome gets a dead proxy, and any stencil that fails to load stops the render.
- Each render displays the SVG through `<img>` and compares it with the PNG, so an SVG whose labels
  do not show outside the drawio viewer cannot be committed silently.
- To edit a figure: open the `.drawio` in VSCode (Draw.io Integration) or app.diagrams.net, save,
  run `render_drawio.py` on it, then `check_figures.py`.
- `selftest/build_glyph_sheet.py` rebuilds the glyph sheet from the FTEL library
  (`~/Documents/FX1_ips/Common_Info/FTEL_DRAWIO_LIB_V1.drawio`, or `$FTEL_DRAWIO_LIB`).
- `render_wave.py` renders WaveJSON timing diagrams with `wavedrom-cli@3.2.0`; not used yet (batch 3).
