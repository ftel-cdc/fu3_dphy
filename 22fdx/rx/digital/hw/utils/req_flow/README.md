# req_flow — requirement tooling for the adapted RTL flow

Deterministic scripts behind `/dphy_autoflow` and `/dphy_spec_parse` (`.claude/commands/`). They do
the parts of the flow that a machine can check exactly; the LLM only interprets the spec. Plan and
rationale: `hw/rtl/ip/ftel_dphy_rx/doc/RTL_FLOW_PLAN.md`.

Standard library only, except `flow_check.py`, which reads `req/waivers.yaml` (and, through the IP's
`config/validate_config.py`, the configuration YAML) with PyYAML.

| Script | Role |
|---|---|
| `spec_inventory.py` | Inventory of the spec: every row of the graded tables (recognised by header signature) with its rule-derived block and category, Q/C ids with ranges expanded, lines tagged `OPEN` / `⚠️`, and the lines that depend on an open item (`open_derived`). `--selftest` compares with the answer key `EXPECTED[<spec revision>]` |
| `jsonschema_lite.py` | Minimal draft-07 validator for the keywords the schemas use; unknown keywords are errors |
| `derive_rules.py` | Fields computed from the spec instead of judged by the LLM: `open` status and `needs_human_decision` (line depends on an open item), block and category of table rows. Added after the A6 stability run (79.6 % → 99.1 % on the same anchors) |
| `assemble_req.py` | Merges the per-section chunks written by the parse step, orders by source line, assigns `REQ-NNN` / `F-NNN` (stable ids, below), fills metadata (spec sha256, revision, next free ids), applies `derive_rules.py` and prints how many values it overrode. `--selftest-ids` checks id stability on scratch copies |
| `rebase_req.py` | Carries chunks over to a new spec revision: items whose quote and text unit are unchanged get their new line number; the others and the changed / new spec text are listed in a worklist, so only those parts are re-extracted. With `--old-json` each stale item carries its old id (`prev_id`) |
| `validate_req.py` | Grades `structured_spec.json`: schema, verbatim quotes at their line, coverage of every graded row and id, OPEN/⚠️ flag consistency, derived fields (`DERIVE`). `--report-md` prints the metric table |
| `compare_req.py` | Stability metric between two independent extractions (RTL_FLOW_PLAN A6), per anchor row; `--kinds` restricts the anchor kinds |
| `flow_check.py` | Conflict check after each autoflow phase: P1 (spec parse), P2 (configuration: `config/validate_config.py`, package up to date, Gate 2 signed automatically at 0 conflicts), P3a (RTL: rules, VCS and SpyGlass lint results, coverage of `req/rtl_scope.json`, OPEN tags; writes `req/rtm.json`). Maps findings to conflict codes (`CF-*`), applies waivers, writes `req/conflicts_<phase>.json` and `req/flow_state.json`. Exit 2 stops the autoflow. `--selftest-negative` runs the pre-registered negative tests of the three phases on scratch copies |
| `check_rtl_rules.py` | Lexical checker of the [M] rules of `hw/rtl/ip/ftel_dphy_rx/doc/rtl_rule.md` (naming, file layout, header, constructs, CDC tags, REQ/OPEN tags). Profile `construct` keeps the language rules only, to check it on another IP (0 false positive on `ftel_intctl`). `--selftest-negative`: one seeded violation per rule |
| `schemas/structured_spec.schema.json` | Schema of `structured_spec.json` |

```bash
cd /home/linhhk/Documents/DPHY
python3 hw/utils/req_flow/spec_inventory.py hw/rtl/ip/ftel_dphy_rx/doc/spec.md --selftest
python3 hw/utils/req_flow/validate_req.py hw/rtl/ip/ftel_dphy_rx/req/structured_spec.json \
        --spec hw/rtl/ip/ftel_dphy_rx/doc/spec.md --report-md
python3 hw/utils/req_flow/flow_check.py --phase P1 --ip ftel_dphy_rx --mode review
python3 hw/utils/req_flow/flow_check.py --phase P2 --ip ftel_dphy_rx      # after validate_config.py --emit
python3 hw/utils/req_flow/flow_check.py --phase P3a --ip ftel_dphy_rx     # after sim/vcs_lint.sh and tool_flow lint
python3 hw/utils/req_flow/flow_check.py --selftest-negative --ip ftel_dphy_rx --workdir <scratch dir>
python3 hw/utils/req_flow/check_rtl_rules.py hw/rtl/ip/ftel_dphy_rx/logical/
python3 hw/utils/req_flow/check_rtl_rules.py --selftest-negative --workdir <scratch dir>
```

**Answer key.** `EXPECTED` in `spec_inventory.py` holds one set of counts per spec revision; the v0.2
set was registered before any extraction prompt existed. When a new revision changes the number of
rows on purpose, add its counts **before** editing the spec, commit them with the spec, and say so in
the commit message. Never update a count to make a run pass.

**Stable ids (since spec v0.11).** RTL, SVA and test tags cite `REQ-NNN`, so an id must keep
pointing at the same requirement when the spec changes. `assemble_req.py` keeps the id of an item
whose quote and text are unchanged, and of a regenerated item that carries `prev_req_id` /
`prev_finding_id`; any other item gets the next free number. The id of a requirement that
disappears is retired and never reused (`metadata.req_id_next`, `finding_id_next`). The items stay
ordered by source line, so the ids have gaps and are not in sequence. `--renumber` starts a fresh
numbering, which invalidates every tag: use it only before anything cites the ids.

**Spec changed (CF-SPEC).** Re-sync incrementally instead of re-extracting everything:

```bash
W=hw/rtl/ip/ftel_dphy_rx/req/_work
git show HEAD:hw/rtl/ip/ftel_dphy_rx/doc/spec.md > $W/spec_old.md     # the revision the chunks were built on
mv $W/P1 $W/P1_<old revision>
python3 hw/utils/req_flow/rebase_req.py --chunks $W/P1_<old revision> --old-spec $W/spec_old.md \
        --new-spec hw/rtl/ip/ftel_dphy_rx/doc/spec.md --out $W/P1 --worklist $W/P1_rebase_worklist.json \
        --old-json hw/rtl/ip/ftel_dphy_rx/req/structured_spec.json
# then /dphy_spec_parse regenerates only the worklist items into a delta chunk (a regenerated item that
# states the same requirement copies the stale item's prev_id as prev_req_id), and assembles as usual:
# assemble_req.py keeps the ids of the existing structured_spec.json
```

**RTL scope (P3a).** `req/rtl_scope.json` is registered before any RTL is written, like the answer
key: a rule (blocks, categories and releases that the RTL implements) plus the excluded REQs, each
with its reason. `flow_check.py` derives the REQ set from the rule on every run, so a new REQ of a
later spec revision must be tagged (CF-COVER). A REQ that needs a human decision carries exactly one
`// OPEN <id> REQ-xxx: <default>` tag, at the single place that implements its default (CF-TAG).
