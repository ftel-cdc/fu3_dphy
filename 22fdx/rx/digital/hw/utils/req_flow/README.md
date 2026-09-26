# req_flow — requirement tooling for the adapted RTL flow

Deterministic scripts behind `/dphy_autoflow` and `/dphy_spec_parse` (`.claude/commands/`). They do
the parts of the flow that a machine can check exactly; the LLM only interprets the spec. Plan and
rationale: `hw/rtl/ip/ftel_dphy_rx/doc/RTL_FLOW_PLAN.md`.

Standard library only, except `flow_check.py`, which reads `req/waivers.yaml` with PyYAML.

| Script | Role |
|---|---|
| `spec_inventory.py` | Inventory of the spec: every row of the graded tables (recognised by header signature) with its rule-derived block and category, Q/C ids with ranges expanded, lines tagged `OPEN` / `⚠️`, and the lines that depend on an open item (`open_derived`). `--selftest` compares with the answer key `EXPECTED[<spec revision>]` |
| `jsonschema_lite.py` | Minimal draft-07 validator for the keywords the schemas use; unknown keywords are errors |
| `derive_rules.py` | Fields computed from the spec instead of judged by the LLM: `open` status and `needs_human_decision` (line depends on an open item), block and category of table rows. Added after the A6 stability run (79.6 % → 99.1 % on the same anchors) |
| `assemble_req.py` | Merges the per-section chunks written by the parse step, orders by source line, assigns `REQ-NNN` / `F-NNN`, fills metadata (spec sha256, revision), applies `derive_rules.py` and prints how many values it overrode |
| `rebase_req.py` | Carries chunks over to a new spec revision: items whose quote and text unit are unchanged get their new line number; the others and the changed / new spec text are listed in a worklist, so only those parts are re-extracted |
| `validate_req.py` | Grades `structured_spec.json`: schema, verbatim quotes at their line, coverage of every graded row and id, OPEN/⚠️ flag consistency, derived fields (`DERIVE`). `--report-md` prints the metric table |
| `compare_req.py` | Stability metric between two independent extractions (RTL_FLOW_PLAN A6), per anchor row; `--kinds` restricts the anchor kinds |
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

**Answer key.** `EXPECTED` in `spec_inventory.py` holds one set of counts per spec revision; the v0.2
set was registered before any extraction prompt existed. When a new revision changes the number of
rows on purpose, add its counts **before** editing the spec, commit them with the spec, and say so in
the commit message. Never update a count to make a run pass.

**Spec changed (CF-SPEC).** Re-sync incrementally instead of re-extracting everything:

```bash
W=hw/rtl/ip/ftel_dphy_rx/req/_work
git show HEAD:hw/rtl/ip/ftel_dphy_rx/doc/spec.md > $W/spec_old.md     # the revision the chunks were built on
mv $W/P1 $W/P1_<old revision>
python3 hw/utils/req_flow/rebase_req.py --chunks $W/P1_<old revision> --old-spec $W/spec_old.md \
        --new-spec hw/rtl/ip/ftel_dphy_rx/doc/spec.md --out $W/P1 --worklist $W/P1_rebase_worklist.json
# then /dphy_spec_parse regenerates only the worklist items into a delta chunk, and assembles as usual
```
