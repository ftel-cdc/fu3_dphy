#!/usr/bin/env python3
"""Mechanical grader of structured_spec.json against its spec.md (req_flow, criteria A5).

Checks (each issue carries a code consumed by flow_check.py):
  SPEC     metadata.spec_sha256 differs from the spec file on disk (stale baseline)
  SCHEMA   schema errors, duplicate / non-sequential ids, unknown enum-like references
  QUOTE    source_quote not found verbatim (whitespace-collapsed) at source_line..source_line+2
  COVER    a graded inventory row is the source of no REQ, or a Q/C id is cited by no REQ
  OPEN     a REQ sourced from a line that depends on an open item (spec_inventory.open_scope) is
           not flagged needs_human_decision / 'open'
  DERIVE   a field set by rule (derive_rules.py) differs from the rule: block / category of a table
           row, open_item_ref of an open line, 'open' or needs_human_decision without an open basis
  CONSIST  flag rules: ⚠️ line => ambiguity >= 0.35 + needs_review; needs_human_decision =>
           needs_review; (ambiguity > 0.3) == needs_review
  NAME     superseded names (m_fpt_) in REQ text
Warnings (never blocking): block vs section mismatch, R2 without a deskew cue.
In --mode gate every REQ still needing a human decision is reported as GATE_OPEN.

Usage:
  validate_req.py <structured_spec.json> --spec <spec.md> [--mode review|gate]
                  [--report-md] [--json-out <file>]
Exit status: 0 = no issues, 2 = issues found.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jsonschema_lite  # noqa: E402
import spec_inventory   # noqa: E402
import derive_rules     # noqa: E402

SCHEMA_PATH = os.path.join(HERE, "schemas", "structured_spec.schema.json")
DESKEW_CUE = re.compile(r"deskew|R2|No\.5|calibrat", re.I)
BLOCK_IN_SECTION = re.compile(r"Block No\.\s*([1-8])")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def check(doc, spec_path, mode):
    issues, warnings = [], []

    def add(code, where, msg):
        issues.append({"code": code, "where": where, "msg": msg})

    raw = open(spec_path, "rb").read()
    lines = raw.decode("utf-8").splitlines()
    inv = spec_inventory.build(spec_path)
    schema = json.load(open(SCHEMA_PATH, encoding="utf-8"))

    for e in jsonschema_lite.validate(doc, schema):
        add("SCHEMA", "schema", e)
    if any(i["code"] == "SCHEMA" for i in issues):
        return issues, warnings, inv          # structure unreliable: stop before semantic checks

    md = doc["metadata"]
    if md["spec_sha256"] != hashlib.sha256(raw).hexdigest():
        add("SPEC", "metadata.spec_sha256",
            f"artifact built on {md['spec_sha256'][:12]}…, spec on disk is {hashlib.sha256(raw).hexdigest()[:12]}…")

    reqs = doc["requirements"]
    ids = [r["req_id"] for r in reqs]
    if ids != [f"REQ-{i:03d}" for i in range(1, len(ids) + 1)]:
        add("SCHEMA", "requirements", "req_id sequence is not REQ-001..REQ-NNN in order")
    fids = [f["finding_id"] for f in doc["findings"]]
    if fids != [f"F-{i:03d}" for i in range(1, len(fids) + 1)]:
        add("SCHEMA", "findings", "finding_id sequence is not F-001..F-NNN in order")

    # lines depending on an open item: OPEN word, Open Items rows, OPEN heading/caption scope,
    # citation of an open id, 'To be determined' (spec_inventory.open_scope)
    open_lines = {int(k) for k in inv["open_derived"]}
    assume_lines = set(inv["assume_lines"])
    blocks = set(inv["blocks"]) | {"top", "wrap", "all"}
    param_names = {it["key"].split(":", 1)[1] for it in inv["items"] if it["kind"] in ("param", "runtime")}
    spec_text = "\n".join(lines)
    known_open_ids = set(re.findall(r"\b(K[0-9]+|S[0-9]+|T[0-9]+|ADR-[0-9]{3})\b", spec_text))

    def quote_ok(item, where):
        ln, q = item["source_line"], norm(item["source_quote"])
        if ln > len(lines):
            add("QUOTE", where, f"source_line {ln} beyond end of spec ({len(lines)} lines)")
            return
        window = norm(" ".join(lines[ln - 1: ln + 2]))
        if q in window:
            return
        where_else = [n + 1 for n, l in enumerate(lines) if q[:40] in norm(l)]
        hint = f"; text found at line(s) {where_else[:5]}" if where_else else "; text not found anywhere"
        add("QUOTE", where, f"quote not at line {ln}{hint}: {item['source_quote'][:70]!r}")

    for r in reqs:
        w = r["req_id"]
        quote_ok(r, w)
        ln = r["source_line"]
        if ln in open_lines:
            if not r["needs_human_decision"] or r["spec_status"] != "open":
                add("OPEN", w, f"line {ln} depends on an open item but needs_human_decision="
                               f"{r['needs_human_decision']}, spec_status={r['spec_status']!r}")
        for f, have, want in derive_rules.differences(r, inv, lines):
            if f in ("category", "block", "open_item_ref") or \
                    (f in ("spec_status", "needs_human_decision") and ln not in open_lines):
                add("DERIVE", w, f"{f} is {have!r}, the rule gives {want!r}")
        if ln in assume_lines:
            if r["ambiguity_score"] < 0.35 or not r["needs_review"] or r["spec_status"] not in ("assumed", "open"):
                add("CONSIST", w, f"line {ln} carries ⚠️ but ambiguity={r['ambiguity_score']}, "
                                  f"needs_review={r['needs_review']}, spec_status={r['spec_status']!r}")
        if r["needs_human_decision"] and not r["needs_review"]:
            add("CONSIST", w, "needs_human_decision without needs_review")
        if (r["ambiguity_score"] > 0.3) != r["needs_review"]:
            add("CONSIST", w, f"ambiguity {r['ambiguity_score']} inconsistent with needs_review={r['needs_review']}")
        if r["block"] not in blocks:
            add("SCHEMA", w, f"block {r['block']!r} not in the spec block table")
        for p in r["parameters_affected"]:
            if p not in param_names:
                add("SCHEMA", w, f"parameters_affected: {p!r} is not a parameter/runtime field of the spec")
        for o in r["open_item_ref"]:
            if o not in known_open_ids:
                add("SCHEMA", w, f"open_item_ref: {o!r} does not appear in the spec")
        if "m_fpt_" in r["text"]:
            add("NAME", w, "superseded name m_fpt_ in text")
        m = BLOCK_IN_SECTION.search(r["source_section"])
        if m and r["block"] not in (f"No.{m.group(1)}", "all", "top", "wrap"):
            warnings.append({"where": w, "msg": f"section says Block No.{m.group(1)}, REQ block is {r['block']}"})
        if r["release"] == "R2" and not DESKEW_CUE.search(r["text"] + r["source_quote"]):
            warnings.append({"where": w, "msg": "release R2 without a deskew/R2 cue in text"})
        if mode == "gate" and r["needs_human_decision"]:
            add("GATE_OPEN", w, "still needs a human decision (blocks Gate 1)")

    for f in doc["findings"]:
        quote_ok(f, f["finding_id"])

    # coverage: every graded row must be the source line of at least one REQ
    src_lines = collections.Counter(r["source_line"] for r in reqs)
    for it in inv["items"]:
        if it["kind"] in spec_inventory.GRADED_KINDS and src_lines[it["line"]] == 0:
            add("COVER", it["key"], f"row at line {it['line']} is the source of no REQ")
    cited = set()
    for r in reqs:
        for s in r["source_ids"]:
            cited |= spec_inventory.expand_ids(s)
    for x in inv["q_ids"] + inv["c_ids"]:
        if x not in cited:
            add("COVER", x, "id is cited by no REQ (source_ids)")
    return issues, warnings, inv


def metrics(doc, issues, warnings, inv):
    reqs = doc["requirements"]
    by = lambda k: collections.Counter(r[k] for r in reqs)
    src = collections.Counter(r["source_line"] for r in reqs)
    cov = {}
    for it in inv["items"]:
        if it["kind"] in spec_inventory.GRADED_KINDS:
            c = cov.setdefault(it["kind"], [0, 0])
            c[1] += 1
            c[0] += src[it["line"]] > 0
    nq = len(reqs) + len(doc["findings"])
    bad_q = len({i["where"] for i in issues if i["code"] == "QUOTE"})
    cited = set()
    for r in reqs:
        for s in r["source_ids"]:
            cited |= spec_inventory.expand_ids(s)
    for kind in ("q_ids", "c_ids"):
        cov[kind] = [sum(x in cited for x in inv[kind]), len(inv[kind])]
    return {
        "requirements": len(reqs),
        "findings": len(doc["findings"]),
        "by_category": dict(by("category")),
        "by_block": dict(by("block")),
        "by_spec_status": dict(by("spec_status")),
        "by_release": dict(by("release")),
        "needs_review": sum(r["needs_review"] for r in reqs),
        "needs_human_decision": sum(r["needs_human_decision"] for r in reqs),
        "quote_match": f"{nq - bad_q}/{nq}",
        "coverage": {k: f"{v[0]}/{v[1]}" for k, v in cov.items()},
        "issues_by_code": dict(collections.Counter(i["code"] for i in issues)),
        "warnings": len(warnings),
    }


def report_md(m, issues, warnings):
    out = ["| Metric | Value |", "|---|---|"]
    for k in ("requirements", "findings", "quote_match", "needs_review", "needs_human_decision", "warnings"):
        out.append(f"| {k} | {m[k]} |")
    for k in ("by_category", "by_block", "by_spec_status", "by_release", "coverage", "issues_by_code"):
        v = ", ".join(f"{a}: {b}" for a, b in sorted(m[k].items())) or "none"
        out.append(f"| {k} | {v} |")
    if issues:
        out += ["", "| Code | Where | Message |", "|---|---|---|"]
        out += [f"| {i['code']} | {i['where']} | {i['msg'].replace('|', '/')} |" for i in issues]
    if warnings:
        out += ["", "| Warning | Message |", "|---|---|"]
        out += [f"| {w['where']} | {w['msg']} |" for w in warnings]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("structured_spec")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--mode", choices=["review", "gate"], default="review")
    ap.add_argument("--report-md", action="store_true")
    ap.add_argument("--json-out")
    a = ap.parse_args()
    doc = json.load(open(a.structured_spec, encoding="utf-8"))
    issues, warnings, inv = check(doc, a.spec, a.mode)
    ok_struct = not any(i["code"] == "SCHEMA" and i["where"] == "schema" for i in issues)
    m = metrics(doc, issues, warnings, inv) if ok_struct else {"issues_by_code": dict(collections.Counter(i["code"] for i in issues))}
    if a.json_out:
        json.dump({"metrics": m, "issues": issues, "warnings": warnings}, open(a.json_out, "w"), indent=1)
    if a.report_md and ok_struct:
        print(report_md(m, issues, warnings))
    else:
        print(json.dumps(m, indent=1))
        for i in issues[:50]:
            print(f"{i['code']:<8} {i['where']:<14} {i['msg']}")
        if len(issues) > 50:
            print(f"... {len(issues) - 50} more issues")
    sys.exit(2 if issues else 0)


if __name__ == "__main__":
    main()
