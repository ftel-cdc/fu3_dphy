# req_flow — requirement tooling for the adapted RTL flow

Deterministic scripts behind `/dphy_autoflow` and `/dphy_spec_parse` (`.claude/commands/`). They do
the parts of the flow that a machine can check exactly; the LLM only interprets the spec. Plan and
rationale: `hw/rtl/ip/ftel_dphy_rx/doc/RTL_FLOW_PLAN.md`.

Standard library only, except `flow_check.py`, which reads `req/waivers.yaml` with PyYAML.

| Script | Role |
|---|---|
| `spec_inventory.py` | Inventory of the spec: every row of the graded tables (recognised by header signature), Q/C ids with ranges expanded, lines tagged `OPEN` / `⚠️`. `--selftest` compares with the pre-registered answer key `EXPECTED` |
| `jsonschema_lite.py` | Minimal draft-07 validator for the keywords the schemas use; unknown keywords are errors |
| `assemble_req.py` | Merges the per-section chunks written by the parse step, orders by source line, assigns `REQ-NNN` / `F-NNN`, fills metadata (spec sha256, revision) |
| `validate_req.py` | Grades `structured_spec.json`: schema, verbatim quotes at their line, coverage of every graded row and id, OPEN/⚠️ flag consistency. `--report-md` prints the metric table |
| `flow_check.py` | Maps the grader's issues to conflict codes (`CF-*`), applies waivers, writes `req/conflicts_<phase>.json` and `req/flow_state.json`. Exit 2 stops the autoflow. `--selftest-negative` runs the pre-registered negative tests on scratch copies |
| `schemas/structured_spec.schema.json` | Schema of `structured_spec.json` |

```bash
cd /home/linhhk/Documents/DPHY
python3 hw/utils/req_flow/spec_inventory.py hw/rtl/ip/ftel_dphy_rx/doc/spec.md --selftest
python3 hw/utils/req_flow/validate_req.py hw/rtl/ip/ftel_dphy_rx/req/structured_spec.json \
        --spec hw/rtl/ip/ftel_dphy_rx/doc/spec.md --report-md
python3 hw/utils/req_flow/flow_check.py --phase P1 --ip ftel_dphy_rx --mode review
python3 hw/utils/req_flow/flow_check.py --selftest-negative --ip ftel_dphy_rx --workdir <scratch dir>
```

**Answer key.** `EXPECTED` in `spec_inventory.py` was registered on spec v0.2 before any extraction
prompt existed. When the spec changes the number of rows on purpose, update `EXPECTED` in the same
commit as the spec and say so in the commit message. Never update it to make a run pass.
