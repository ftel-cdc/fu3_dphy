#!/usr/bin/env python3
"""Deterministic conflict check between autoflow phases (req_flow, /dphy_autoflow).

After each phase the orchestrator runs this script. Zero conflicts => the flow may continue;
any conflict => the flow STOPS and the conflict table must be resolved (fixed, or waived with a
rationale in req/waivers.yaml where the code allows it). No LLM is involved here.

Conflict codes implemented for phase P1 (spec parse):
  CF-SPEC    spec changed since the artifact was built           (not waivable)
  CF-SCHEMA  schema / flag-consistency / name / derived-field errors (auto-fix by regeneration, max 2)
  CF-QUOTE   a source_quote is not verbatim at its line           (not waivable)
  CF-COVER   inventory row or Q/C id without a REQ                (auto-fix by regeneration, max 2)
  CF-OPEN    OPEN-tagged source not flagged; in --mode gate also every REQ still needing a
             human decision                                        (stops for a human)
Phase P2 (configuration; Gate 2 is signed automatically by this script when there is no conflict):
  CF-SPEC    P1 has not passed on the current spec                 (not waivable)
  CF-DRIFT   structured_spec.json differs from the one P1 produced (not waivable)
  CF-CONFIG  config/<ip>.yaml breaks a constraint of validate_config.py (rule CFG-nn), or the
             generated package is missing (PKG-MISSING) or differs from the YAML (PKG-STALE)
             (stops for a human: a configuration value is a decision)
Phase P3a (RTL, /dphy_rtl_gen; writes req/rtm.json):
  CF-SPEC    P1 has not passed on the current spec                 (not waivable)
  CF-DRIFT   P2 inputs or the package changed since P2; RTL changed after the VCS or SpyGlass lint
             (not waivable)
  CF-LINT    check_rtl_rules form rules; VCS +lint=all (sim/vcs_lint/manifest.json); SpyGlass lint_rtl
             (lint/reports/lint.rpt): Fatal, Error or unwaived Warning
  CF-TAG     check_rtl_rules trace rules (T1, T2, T3, T6); a provisional REQ in scope without exactly
             one OPEN tag, or with an OPEN tag whose ids are not its open items
  CF-COVER   REQ of req/rtl_scope.json without a tag in the RTL body
  CF-OPEN    --mode gate: every provisional REQ in scope (review: count only)
Later stages add CF-INDEP, CF-SIM, CF-VAC, CF-CDC, CF-DOC.

Usage:
  flow_check.py --phase P1|P2|P3a --ip ftel_dphy_rx [--mode review|gate] [--no-state]
  flow_check.py --selftest-negative --ip ftel_dphy_rx --workdir <scratch dir>
Exit status: 0 = no conflict, 2 = conflicts (flow must stop), 1 = usage / selftest failure.
"""
import argparse
import copy
import datetime
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import validate_req  # noqa: E402
import check_rtl_rules  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, ".."))   # the IP folder (22fdx/rx/digital), which holds req_flow/
CODE_MAP = {"SPEC": "CF-SPEC", "SCHEMA": "CF-SCHEMA", "CONSIST": "CF-SCHEMA", "NAME": "CF-SCHEMA",
            "DERIVE": "CF-SCHEMA",
            "QUOTE": "CF-QUOTE", "COVER": "CF-COVER", "OPEN": "CF-OPEN", "GATE_OPEN": "CF-OPEN"}
NOT_WAIVABLE = {"CF-SPEC", "CF-QUOTE", "CF-INDEP", "CF-DRIFT"}
OWNER = {"CF-SPEC": "rerun P1", "CF-SCHEMA": "prompt / regeneration", "CF-QUOTE": "prompt / regeneration",
         "CF-COVER": "prompt / regeneration", "CF-OPEN": "spec owner / team", "CF-DRIFT": "rerun the stale phase",
         "CF-CONFIG": "configuration owner (decision)", "CF-LINT": "RTL (/dphy_rtl_gen)",
         "CF-TAG": "RTL (/dphy_rtl_gen)"}
FIX = {"CF-SPEC": "rerun /dphy_autoflow from P1 on the current spec",
       "CF-SCHEMA": "regenerate the affected REQs (max 2 rounds), else fix the parse prompt",
       "CF-QUOTE": "re-quote verbatim from the cited line; never edit the spec to match",
       "CF-COVER": "add REQs sourced from the uncovered row / citing the id",
       "CF-OPEN": "flag the REQ correctly, or resolve the open item with the owner",
       "CF-DRIFT": "rerun /dphy_autoflow from the earliest phase whose recorded hash differs",
       "CF-CONFIG": "fix config/<ip>.yaml (or waive with a decision reference), then validate_config.py --emit",
       "CF-LINT": "fix the RTL (max 3 rounds per module), rerun sim/vcs_lint.sh and the tool_flow lint",
       "CF-TAG": "fix the tags: header REQ-IDs, one OPEN tag per provisional REQ at its single implementation point"}
FIX["CF-COVER"] = FIX["CF-COVER"] + "; at P3a: tag the REQ where the RTL implements it"


def paths(ip, root=REPO):
    d = root   # the IP files sit directly in the IP folder; ip names the files
    return {"ip": ip, "ip_dir": d, "spec": os.path.join(d, "doc", "spec.md"),
            "structured": os.path.join(d, "req", "structured_spec.json"),
            "waivers": os.path.join(d, "req", "waivers.yaml"),
            "state": os.path.join(d, "req", "flow_state.json"),
            "conflicts": os.path.join(d, "req", "conflicts_P1.json"),
            "config": os.path.join(d, "config", f"{ip}.yaml"),
            "validator": os.path.join(d, "config", "validate_config.py"),
            "config_pkg": os.path.join(d, "logical", f"{ip}_config_pkg.sv")}


def conflicts_path(p, phase):
    return os.path.join(os.path.dirname(p["state"]), f"conflicts_{phase}.json")


def conflict(code, rule, where, evidence, n):
    return {"id": f"{code}-{n:03d}", "code": code, "rule": rule, "where": where, "evidence": evidence,
            "owner": OWNER[code], "fix": FIX[code]}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() if os.path.exists(path) else None


def load_waivers(path):
    if not os.path.exists(path):
        return []
    import yaml  # PyYAML; absence must fail loudly rather than silently ignore waivers
    data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    w = data.get("waivers") or []
    if not isinstance(w, list):
        raise SystemExit(f"{path}: 'waivers' must be a list")
    return w


def check_p1(p, mode, waivers=None):
    """Return (conflicts, waived, rejected_waivers, info)."""
    if not os.path.exists(p["structured"]):
        c = [{"id": "CF-SCHEMA-000", "code": "CF-SCHEMA", "rule": "MISSING", "where": p["structured"],
              "evidence": "structured_spec.json does not exist", "owner": OWNER["CF-SCHEMA"], "fix": "run P1"}]
        return c, [], [], {}
    doc = json.load(open(p["structured"], encoding="utf-8"))
    issues, warnings, _ = validate_req.check(doc, p["spec"], mode)
    conflicts = []
    for n, i in enumerate(issues, 1):
        code = CODE_MAP[i["code"]]
        conflicts.append({"id": f"{code}-{n:03d}", "code": code, "rule": i["code"], "where": i["where"],
                          "evidence": i["msg"], "owner": OWNER[code], "fix": FIX[code]})
    info = {"warnings": len(warnings)}
    if mode == "review" and isinstance(doc.get("requirements"), list):
        info["needs_human_decision"] = sum(bool(r.get("needs_human_decision")) for r in doc["requirements"])
    conflicts, waived, rejected = apply_waivers(conflicts, waivers if waivers is not None else load_waivers(p["waivers"]))
    return conflicts, waived, rejected, info


def apply_waivers(conflicts, waivers):
    """Remove the conflicts matched by a complete waiver of a waivable code; list the rejected waivers."""
    waived, rejected = [], []
    for w in waivers:
        missing = [k for k in ("code", "match", "reason", "ref", "by", "date") if not w.get(k)]
        if missing:
            rejected.append({**w, "rejected_because": f"missing fields {missing}"})
            continue
        if w["code"] in NOT_WAIVABLE:
            rejected.append({**w, "rejected_because": f"{w['code']} is an integrity conflict and cannot be waived"})
            continue
        hit = [c for c in conflicts if c["code"] == w["code"] and w["match"] in (c["where"] + " " + c["evidence"])]
        for c in hit:
            conflicts.remove(c)
            waived.append({**c, "waiver": w})
    return conflicts, waived, rejected


def load_state(p):
    return json.load(open(p["state"], encoding="utf-8")) if os.path.exists(p["state"]) else {"phases": {}}


def upstream_p1(p, n0=1):
    """CF-SPEC / CF-DRIFT when P1 did not pass on the current spec or its output was changed afterwards."""
    c, p1 = [], load_state(p)["phases"].get("P1")
    if not p1 or p1.get("status") != "pass":
        c.append(conflict("CF-SPEC", "P1-NOT-PASSED", "req/flow_state.json", "P1 has not passed; run P1 first", n0))
    elif p1["inputs"].get("spec") != sha(p["spec"]):
        c.append(conflict("CF-SPEC", "SPEC", "doc/spec.md",
                          f"spec sha256 {str(sha(p['spec']))[:12]} != P1 input {p1['inputs'].get('spec', '')[:12]}", n0))
    elif p1["outputs"].get("structured_spec") != sha(p["structured"]):
        c.append(conflict("CF-DRIFT", "STRUCTURED", "req/structured_spec.json",
                          "structured_spec.json differs from the P1 output recorded in flow_state.json", n0))
    return c


def load_validator(path):
    name = "validate_config_" + hashlib.sha256(path.encode()).hexdigest()[:8]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_p2(p, waivers=None):
    """Return (conflicts, waived, rejected_waivers, info) of the configuration phase."""
    conflicts = upstream_p1(p)
    info = {}
    if not os.path.exists(p["config"]) or not os.path.exists(p["validator"]):
        conflicts.append(conflict("CF-CONFIG", "MISSING", "config/",
                                  "config YAML or validate_config.py does not exist", len(conflicts) + 1))
    else:
        vc = load_validator(p["validator"])
        exp, errs, info = vc.expected_pkg(p["config"], p["spec"], p["structured"])
        rel = os.path.relpath(p["config"], p["ip_dir"])
        for e in errs:
            conflicts.append(conflict("CF-CONFIG", e["id"], rel, e["msg"], len(conflicts) + 1))
        if exp is not None:
            pkg = os.path.relpath(p["config_pkg"], p["ip_dir"])
            if not os.path.exists(p["config_pkg"]):
                conflicts.append(conflict("CF-CONFIG", "PKG-MISSING", pkg, "generated package does not exist",
                                          len(conflicts) + 1))
            elif open(p["config_pkg"], encoding="utf-8").read() != exp:
                conflicts.append(conflict("CF-CONFIG", "PKG-STALE", pkg,
                                          "package differs from the one generated by the YAML (hand edit or stale)",
                                          len(conflicts) + 1))
    conflicts, waived, rejected = apply_waivers(conflicts, waivers if waivers is not None else load_waivers(p["waivers"]))
    return conflicts, waived, rejected, {k: v for k, v in info.items() if k in ("eot_delay_need_bytes", "tclk_post_need_ui",
                                                                                 "afe_term_budget_ns")}


TRACE_RULES = {"T1", "T2", "T3", "T6"}


def p3a_paths(p):
    d = p["ip_dir"]
    return {"logical": os.path.join(d, "logical"), "rtl_rule": os.path.join(d, "doc", "rtl_rule.md"),
            "scope": os.path.join(d, "req", "rtl_scope.json"), "rtm": os.path.join(d, "req", "rtm.json"),
            "vcs_manifest": os.path.join(d, "sim", "vcs_lint", "manifest.json"),
            "sg_report": os.path.join(d, "lint", "reports", "lint.rpt"),
            "sg_checksum": os.path.join(d, "lint", "work", "*", "consolidated_reports", "*", "checksum.rpt")}


def scope_of(doc, scope):
    """req_id -> None when the REQ must be tagged, else the reason it is excluded."""
    rule, exc = scope["rule"], {e["req_id"]: e["reason"] for e in scope.get("exclusions", [])}
    out = {}
    for r in doc["requirements"]:
        if r["block"] not in rule["blocks"]:
            out[r["req_id"]] = f"block {r['block']} is not in this RTL"
        elif r["category"] in rule["exclude_categories"]:
            out[r["req_id"]] = f"category {r['category']}"
        elif r["release"] in rule.get("exclude_releases", []):
            out[r["req_id"]] = f"release {r['release']}"
        else:
            out[r["req_id"]] = exc.get(r["req_id"])
    return out


def rtl_tags(files, root):
    """REQ ids tagged in the body of each file, and the OPEN tags (file, line, ids, reqs)."""
    tags, opens = defaultdict(set), []
    for f in files:
        src = check_rtl_rules.Source(f, open(f, encoding="utf-8").read())
        first = next((n for n, l in enumerate(src.code_lines, 1) if l.strip()), 1)
        rel = os.path.relpath(f, root)
        for n, cs in src.comments.items():
            if n <= first:
                continue
            for c in cs:
                for r in check_rtl_rules.REQ_RE.findall(c):
                    tags[r].add(rel)
                m = check_rtl_rules.OPEN_TAG_RE.match(c) if c.startswith("OPEN") else None
                if m:
                    opens.append({"file": rel, "line": n, "ids": re.findall(check_rtl_rules.OPEN_ID, m.group(1)),
                                  "reqs": check_rtl_rules.REQ_RE.findall(m.group(2))})
    return tags, opens


def spyglass_messages(report):
    """Messages of a SpyGlass moresimple report: (severity, rule, file, line, text), each once."""
    seen, out = set(), []
    for line in open(report, encoding="utf-8", errors="replace"):
        m = re.match(r"^\[[0-9A-Fa-f]+\]\s+(\S+)\s+\S+\s+(Fatal|Error|Warning|Info)\s+(\S+)\s+(\d+)\s+\d+\s+(.*)$", line)
        if m and (m.group(1), m.group(3), m.group(4), m.group(5)) not in seen:
            seen.add((m.group(1), m.group(3), m.group(4), m.group(5)))
            out.append({"severity": m.group(2), "rule": m.group(1), "file": m.group(3), "line": int(m.group(4)),
                        "text": m.group(5).strip()})
    return out


def check_p3a(p, mode, waivers=None):
    """Return (conflicts, waived, rejected_waivers, info, rtm) of the RTL phase."""
    q = p3a_paths(p)
    conflicts = upstream_p1(p)

    def add(code, rule, where, evidence):
        conflicts.append(conflict(code, rule, where, evidence, len(conflicts) + 1))

    p2 = load_state(p)["phases"].get("P2")
    cur2 = {"spec": sha(p["spec"]), "structured_spec": sha(p["structured"]), "config": sha(p["config"]),
            "validator": sha(p["validator"])}
    if not p2 or p2.get("status") != "pass":
        add("CF-DRIFT", "P2-NOT-PASSED", "req/flow_state.json", "P2 has not passed; run P2 first")
    else:
        for k, v in cur2.items():
            if p2["inputs"].get(k) != v:
                add("CF-DRIFT", "P2-INPUT", k, f"{k} changed since P2 passed; rerun from P2")
        if p2["outputs"].get("config_pkg") != sha(p["config_pkg"]):
            add("CF-DRIFT", "P2-OUTPUT", "logical/ftel_dphy_rx_config_pkg.sv", "configuration package changed since P2")
    if not os.path.exists(q["rtl_rule"]):
        add("CF-LINT", "RULE", "doc/rtl_rule.md", "rtl_rule.md does not exist")
    files = sorted(glob.glob(os.path.join(q["logical"], "*.sv")))
    if not files:
        add("CF-COVER", "NO-RTL", "logical/", "no RTL file")
    cur = {os.path.basename(f): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}

    # rule check: form rules -> CF-LINT, trace rules -> CF-TAG
    v, _ = check_rtl_rules.run(files, "ip", p["structured"], p["spec"])
    for x in v:
        add("CF-TAG" if x["rule"] in TRACE_RULES else "CF-LINT", x["rule"],
            f"{os.path.relpath(x['file'], p['ip_dir'])}:{x['line']}", x["msg"])

    # VCS lint
    if not os.path.exists(q["vcs_manifest"]):
        add("CF-LINT", "VCS-NOT-RUN", "sim/vcs_lint/manifest.json", "VCS lint has not been run (sim/vcs_lint.sh)")
    else:
        man = json.load(open(q["vcs_manifest"], encoding="utf-8"))
        for r in man.get("runs", []):
            if r["rc"] != 0 or r["errors"] or r["warnings"] or r["lint"]:
                add("CF-LINT", "VCS", r["log"], f"{r['name']}: rc={r['rc']} errors={r['errors']} "
                                                f"warnings={r['warnings']} lint={r['lint']}")
        linted = {os.path.basename(k): v for k, v in man.get("rtl", {}).items()}
        stale = sorted(f for f in cur if linted.get(f) != cur[f])
        if stale:
            add("CF-DRIFT", "VCS-STALE", "sim/vcs_lint/manifest.json", f"RTL changed after the VCS lint: {stale[:4]}")

    # SpyGlass lint
    if not os.path.exists(q["sg_report"]):
        add("CF-LINT", "SG-NOT-RUN", "lint/reports/lint.rpt", "SpyGlass lint_rtl has not been run (tool_flow --tool lint)")
    else:
        msgs = spyglass_messages(q["sg_report"])
        for m in msgs:
            if m["severity"] in ("Fatal", "Error", "Warning"):
                add("CF-LINT", f"SG-{m['rule']}", f"{os.path.basename(m['file'])}:{m['line']}",
                    f"{m['severity']}: {m['text'][:140]}")
        cks = glob.glob(q["sg_checksum"])
        md5 = {}
        for ck in cks:
            for line in open(ck, encoding="utf-8", errors="replace"):
                m = re.match(r"^([0-9a-f]{32})\s+\d+\s+(\S+)", line)
                if m:
                    md5[os.path.basename(m.group(2))] = m.group(1)
        now = {os.path.basename(f): hashlib.md5(open(f, "rb").read()).hexdigest() for f in files}
        # SpyGlass lists module files only; a package is checked against the report time
        rpt_time = max((os.path.getmtime(ck) for ck in cks), default=0)
        stale = sorted(f for f in now if (f in md5 and md5[f] != now[f]) or
                       (f not in md5 and os.path.getmtime(os.path.join(q["logical"], f)) > rpt_time))
        if not cks or stale:
            add("CF-DRIFT", "SG-STALE", "lint/reports/lint.rpt",
                f"RTL changed after the SpyGlass lint: {stale[:4] if cks else 'no checksum.rpt'}")

    # trace: coverage and OPEN tags
    doc = json.load(open(p["structured"], encoding="utf-8"))
    reqs = {r["req_id"]: r for r in doc["requirements"]}
    scope = json.load(open(q["scope"], encoding="utf-8")) if os.path.exists(q["scope"]) else None
    if scope is None:
        add("CF-COVER", "NO-SCOPE", "req/rtl_scope.json", "rtl_scope.json does not exist (register it before the RTL)")
        sc = {}
    else:
        sc = scope_of(doc, scope)
        for e in scope.get("exclusions", []):
            if e["req_id"] not in reqs:
                add("CF-TAG", "SCOPE", "req/rtl_scope.json", f"excluded {e['req_id']} is not in structured_spec.json")
    tags, opens = rtl_tags(files, p["ip_dir"])
    in_scope = [r for r, why in sc.items() if why is None]
    for r in in_scope:
        if r not in tags:
            add("CF-COVER", "RTL-TAG", r, f"{r} ({reqs[r]['block']}) has no tag in the RTL body")
    open_by_req = defaultdict(list)
    for o in opens:
        for r in o["reqs"]:
            open_by_req[r].append(o)
            if r in reqs and not reqs[r].get("needs_human_decision"):
                add("CF-TAG", "OPEN-NOT-NEEDED", f"{o['file']}:{o['line']}", f"OPEN tag on {r}, which needs no decision")
            elif r in reqs and not set(o["ids"]) & set(reqs[r].get("open_item_ref", [])):
                add("CF-TAG", "OPEN-ID", f"{o['file']}:{o['line']}",
                    f"OPEN {o['ids']} on {r}, whose open items are {reqs[r].get('open_item_ref')}")
    provisional = [r for r in in_scope if reqs[r].get("needs_human_decision")]
    for r in provisional:
        n = len(open_by_req.get(r, []))
        if n != 1:
            add("CF-TAG", "OPEN-COUNT", r, f"{r} needs a human decision and has {n} OPEN tags (exactly 1 required)")
        if mode == "gate":
            add("CF-OPEN", "GATE_OPEN", r, f"{r} is provisional (open items {reqs[r].get('open_item_ref')})")

    rtm = {"ip": p["ip"], "generated_by": "flow_check.py --phase P3a",
           "spec_sha256": sha(p["spec"]), "structured_spec_sha256": sha(p["structured"]),
           "rtl": {"logical/" + k: v for k, v in sorted(cur.items())},
           "requirements": [{"req_id": r, "block": reqs[r]["block"], "category": reqs[r]["category"],
                             "release": reqs[r]["release"], "in_rtl_scope": sc.get(r, "no scope") is None,
                             "excluded_reason": sc.get(r), "rtl_traced": r in tags,
                             "rtl_files": sorted(tags.get(r, [])),
                             "provisional": bool(reqs[r].get("needs_human_decision")),
                             "open_item_ref": reqs[r].get("open_item_ref", []),
                             "open_tags": [f"{o['file']}:{o['line']}" for o in open_by_req.get(r, [])]}
                            for r in sorted(reqs, key=lambda x: int(x.split("-")[1]))]}
    info = {"rtl_files": len(files), "in_scope": len(in_scope),
            "in_scope_traced": sum(r in tags for r in in_scope), "provisional_in_scope": len(provisional),
            "traced_total": len(tags), "open_tags": len(opens)}
    rtm["summary"] = info
    conflicts, waived, rejected = apply_waivers(conflicts, waivers if waivers is not None else load_waivers(p["waivers"]))
    return conflicts, waived, rejected, info, rtm


def run_phase(ip, mode, write_state=True, phase="P1"):
    p = paths(ip)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    if phase == "P1":
        conflicts, waived, rejected, info = check_p1(p, mode)
        result = {"phase": "P1", "mode": mode, "at": now, "spec_sha256": sha(p["spec"]),
                  "structured_spec_sha256": sha(p["structured"]), "conflicts": conflicts,
                  "waived": waived, "rejected_waivers": rejected, "info": info}
        inputs, outputs = {"spec": result["spec_sha256"]}, {"structured_spec": result["structured_spec_sha256"]}
    elif phase == "P2":
        conflicts, waived, rejected, info = check_p2(p)
        inputs = {"spec": sha(p["spec"]), "structured_spec": sha(p["structured"]), "config": sha(p["config"]),
                  "validator": sha(p["validator"])}
        outputs = {"config_pkg": sha(p["config_pkg"])}
        result = {"phase": phase, "mode": mode, "at": now, "inputs": inputs, "outputs": outputs,
                  "conflicts": conflicts, "waived": waived, "rejected_waivers": rejected, "info": info}
    else:
        conflicts, waived, rejected, info, rtm = check_p3a(p, mode)
        q = p3a_paths(p)
        rtl = hashlib.sha256("".join(f"{k}{v}" for k, v in sorted(rtm["rtl"].items())).encode()).hexdigest()
        inputs = {"spec": sha(p["spec"]), "structured_spec": sha(p["structured"]), "config_pkg": sha(p["config_pkg"]),
                  "rtl_rule": sha(q["rtl_rule"]), "rtl_scope": sha(q["scope"]), "vcs_manifest": sha(q["vcs_manifest"]),
                  "spyglass_report": sha(q["sg_report"])}
        if write_state:
            json.dump(rtm, open(q["rtm"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        outputs = {"rtl": rtl, "rtm": sha(q["rtm"]) if write_state else None}
        result = {"phase": phase, "mode": mode, "at": now, "inputs": inputs, "outputs": outputs,
                  "conflicts": conflicts, "waived": waived, "rejected_waivers": rejected, "info": info}
    if write_state:
        json.dump(result, open(conflicts_path(p, phase), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        state = load_state(p)
        state.setdefault("ip", ip)
        entry = {"status": "pass" if not conflicts else "blocked", "mode": mode, "at": now,
                 "inputs": inputs, "outputs": outputs, "conflicts": len(conflicts), "waived": len(waived)}
        if phase == "P2":
            entry["gate_2"] = ({"status": "auto-signed", "by": "flow_check.py (0 conflicts)", "at": now}
                               if not conflicts else {"status": "blocked"})
        state["phases"][phase] = entry
        json.dump(state, open(p["state"], "w", encoding="utf-8"), indent=1)
    print(f"{phase} ({mode}): {len(conflicts)} conflict(s), {len(waived)} waived, {len(rejected)} waiver(s) rejected, info={info}")
    if conflicts:
        print(f"{'ID':<14} {'Code':<10} {'Where':<16} Evidence")
        for c in conflicts[:60]:
            print(f"{c['id']:<14} {c['code']:<10} {c['where']:<16} {c['evidence'][:110]}")
        if len(conflicts) > 60:
            print(f"... {len(conflicts) - 60} more (see {conflicts_path(p, phase) if write_state else 'output'})")
    for r in rejected:
        print(f"WAIVER REJECTED: {r['rejected_because']}: {r}")
    return 0 if not conflicts else 2


def selftest_negative(ip, workdir):
    """Pre-registered negative tests (RTL_FLOW_PLAN A8) on scratch copies; real artifacts untouched."""
    src = paths(ip)
    if not os.path.exists(src["structured"]):
        print("selftest needs an existing structured_spec.json (run P1 first)")
        return 1
    work = os.path.join(workdir, "flow_check_selftest")
    shutil.rmtree(work, ignore_errors=True)
    root = os.path.join(work, "repo")
    p = paths(ip, root)
    os.makedirs(os.path.dirname(p["spec"]))
    os.makedirs(os.path.dirname(p["structured"]))
    shutil.copy(src["spec"], p["spec"])
    base_doc = json.load(open(src["structured"], encoding="utf-8"))

    def write(doc):
        json.dump(doc, open(p["structured"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def codes(mode, waivers=None):
        c, w, rj, _ = check_p1(p, mode, waivers or [])
        return c, rj

    results = []
    write(base_doc)
    c, _ = codes("review")
    results.append(("baseline review run is clean", not c, f"{len(c)} conflicts"))
    if c:
        for x in c[:10]:
            print("   baseline:", x["code"], x["where"], x["evidence"][:90])

    # 1. spec changed by one byte -> CF-SPEC
    with open(p["spec"], "a", encoding="utf-8") as f:
        f.write("\n")
    c, _ = codes("review")
    results.append(("1 spec edit -> CF-SPEC", any(x["code"] == "CF-SPEC" for x in c), [x["code"] for x in c][:3]))
    shutil.copy(src["spec"], p["spec"])

    # 2. one source_quote altered -> CF-QUOTE
    d2 = copy.deepcopy(base_doc)
    d2["requirements"][0]["source_quote"] += " [tampered]"
    write(d2)
    c, _ = codes("review")
    ok2 = any(x["code"] == "CF-QUOTE" and x["where"] == d2["requirements"][0]["req_id"] for x in c)
    results.append(("2 tampered quote -> CF-QUOTE", ok2, [x["code"] for x in c][:3]))

    # 5. waiver for that CF-QUOTE -> rejected, conflict stays
    w = [{"code": "CF-QUOTE", "match": d2["requirements"][0]["req_id"], "reason": "test", "ref": "none",
          "by": "selftest", "date": "2026-09-26"}]
    c, rj = codes("review", w)
    ok5 = bool(rj) and any(x["code"] == "CF-QUOTE" for x in c)
    results.append(("5 waiver on CF-QUOTE -> rejected", ok5, f"rejected={len(rj)}"))

    # 3. drop every REQ sourced from one PPI row -> CF-COVER
    import spec_inventory
    inv = spec_inventory.build(p["spec"])
    ppi = next(it for it in inv["items"] if it["kind"] == "ppi")
    d3 = copy.deepcopy(base_doc)
    d3["requirements"] = [r for r in d3["requirements"] if r["source_line"] != ppi["line"]]
    write(d3)  # ids are stable: the dropped ids leave gaps, they are not renumbered
    c, _ = codes("review")
    ok3 = any(x["code"] == "CF-COVER" and x["where"] == ppi["key"] for x in c)
    results.append((f"3 drop REQs of {ppi['key']} -> CF-COVER", ok3, [x["where"] for x in c if x["code"] == "CF-COVER"][:3]))

    # 4. clear needs_human_decision of a REQ sourced from an OPEN line, gate mode -> CF-OPEN (rule OPEN)
    d4 = copy.deepcopy(base_doc)
    tgt = next((r for r in d4["requirements"] if r["source_line"] in set(inv["open_lines"])), None)
    if tgt is None:
        results.append(("4 OPEN flag cleared -> CF-OPEN", False, "no REQ sourced from an OPEN line"))
    else:
        tgt["needs_human_decision"] = False
        write(d4)
        c, _ = codes("gate")
        ok4 = any(x["code"] == "CF-OPEN" and x["rule"] == "OPEN" and x["where"] == tgt["req_id"] for x in c)
        results.append((f"4 OPEN flag cleared on {tgt['req_id']} (gate) -> CF-OPEN", ok4,
                        [x["rule"] for x in c if x["where"] == tgt["req_id"]]))

    # 6. block of a REQ sourced from a data-lane FSM row changed -> CF-SCHEMA (rule DERIVE)
    fsm = next(it for it in inv["items"] if it["kind"] == "fsm_dl")
    d6 = copy.deepcopy(base_doc)
    tgt6 = next((r for r in d6["requirements"] if r["source_line"] == fsm["line"]), None)
    if tgt6 is None:
        results.append(("6 derived block changed -> CF-SCHEMA/DERIVE", False, f"no REQ on {fsm['key']}"))
    else:
        tgt6["block"] = "No.8" if tgt6["block"] != "No.8" else "No.1"
        write(d6)
        c, _ = codes("review")
        ok6 = any(x["code"] == "CF-SCHEMA" and x["rule"] == "DERIVE" and x["where"] == tgt6["req_id"] for x in c)
        results.append((f"6 block of {tgt6['req_id']} ({fsm['key']}) changed -> CF-SCHEMA/DERIVE", ok6,
                        [x["rule"] for x in c if x["where"] == tgt6["req_id"]]))

    # 7. two requirements share one id (ids are stable, not sequential) -> CF-SCHEMA
    d7 = copy.deepcopy(base_doc)
    d7["requirements"][1]["req_id"] = d7["requirements"][0]["req_id"]
    write(d7)
    c, _ = codes("review")
    ok7 = any(x["code"] == "CF-SCHEMA" and x["where"] == "req_id" and "duplicate" in x["evidence"] for x in c)
    results.append(("7 duplicate req_id -> CF-SCHEMA", ok7, [x["evidence"][:40] for x in c if x["code"] == "CF-SCHEMA"][:2]))

    results += selftest_p2(src, p)
    results += selftest_p3a(src, p)

    print("NEGATIVE SELFTEST")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}   ({detail})")
    allok = all(ok for _, ok, _ in results)
    print("RESULT:", f"{sum(ok for _, ok, _ in results)}/{len(results)}", "PASS" if allok else "FAIL")
    shutil.rmtree(work, ignore_errors=True)
    return 0 if allok else 1


def selftest_p2(src, p):
    """Pre-registered negative tests of phase P2 on the scratch copy (real artifacts untouched)."""
    results = []
    for k in ("structured", "state", "config", "validator", "config_pkg"):
        if not os.path.exists(src[k]):
            return [(f"P2 selftest needs {os.path.relpath(src[k], REPO)}", False, "missing")]
        os.makedirs(os.path.dirname(p[k]), exist_ok=True)
        shutil.copy(src[k], p[k])
    shutil.copy(src["spec"], p["spec"])

    def run2(waivers=None):
        c, w, rj, _ = check_p2(p, waivers or [])
        return c, w, rj

    def restore(*keys):
        for k in keys:
            shutil.copy(src[k], p[k])

    c, _, _ = run2()
    results.append(("P2 baseline run is clean", not c, [x["rule"] for x in c][:4]))

    text = open(src["config"], encoding="utf-8").read()
    open(p["config"], "w", encoding="utf-8").write(text.replace("NUM_LANES:         4", "NUM_LANES:         3"))
    c, _, _ = run2()
    results.append(("P2-1 NUM_LANES 3 -> CF-CONFIG/CFG-02", any(x["code"] == "CF-CONFIG" and x["rule"] == "CFG-02" for x in c),
                    [x["rule"] for x in c][:3]))
    w = [{"code": "CF-CONFIG", "match": "CFG-02", "reason": "test", "ref": "K1", "by": "selftest", "date": "2026-10-03"}]
    c, wv, _ = run2(w)
    results.append(("P2-2 complete waiver of that CF-CONFIG -> waived", not c and len(wv) == 1, f"left={len(c)} waived={len(wv)}"))
    restore("config")

    pkg = open(src["config_pkg"], encoding="utf-8").read()
    open(p["config_pkg"], "w", encoding="utf-8").write(pkg.replace("C_NUM_LANES = 4", "C_NUM_LANES = 2"))
    c, _, _ = run2()
    results.append(("P2-3 hand-edited package -> CF-CONFIG/PKG-STALE", any(x["rule"] == "PKG-STALE" for x in c),
                    [x["rule"] for x in c][:3]))
    os.remove(p["config_pkg"])
    c, _, _ = run2()
    results.append(("P2-4 missing package -> CF-CONFIG/PKG-MISSING", any(x["rule"] == "PKG-MISSING" for x in c),
                    [x["rule"] for x in c][:3]))
    restore("config_pkg")

    with open(p["spec"], "a", encoding="utf-8") as f:
        f.write("\n")
    c, _, _ = run2()
    results.append(("P2-5 spec edited after P1 -> CF-SPEC", any(x["code"] == "CF-SPEC" for x in c), [x["code"] for x in c][:3]))
    shutil.copy(src["spec"], p["spec"])

    with open(p["structured"], "a", encoding="utf-8") as f:
        f.write("\n")
    c, _, _ = run2()
    results.append(("P2-6 structured_spec edited after P1 -> CF-DRIFT", any(x["code"] == "CF-DRIFT" for x in c),
                    [x["code"] for x in c][:3]))
    w = [{"code": "CF-DRIFT", "match": "structured", "reason": "test", "ref": "none", "by": "selftest", "date": "2026-10-03"}]
    c, wv, rj = run2(w)
    results.append(("P2-7 waiver of CF-DRIFT -> rejected", bool(rj) and any(x["code"] == "CF-DRIFT" for x in c),
                    f"rejected={len(rj)}"))
    restore("structured")
    return results


def selftest_p3a(src, p):
    """Pre-registered negative tests of phase P3a on the scratch copy (real artifacts untouched)."""
    sq, q = p3a_paths(src), p3a_paths(p)
    results = []
    if not os.path.exists(sq["vcs_manifest"]) or not os.path.exists(sq["sg_report"]):
        return [("P3a selftest needs the VCS and SpyGlass lint results", False, "missing")]
    for k in ("spec", "structured", "state", "config", "validator", "config_pkg"):
        os.makedirs(os.path.dirname(p[k]), exist_ok=True)
        shutil.copy2(src[k], p[k])
    for k in ("rtl_rule", "scope", "vcs_manifest", "sg_report"):
        os.makedirs(os.path.dirname(q[k]), exist_ok=True)
        shutil.copy2(sq[k], q[k])
    for ck in glob.glob(sq["sg_checksum"]):
        dst = os.path.join(p["ip_dir"], os.path.relpath(ck, src["ip_dir"]))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(ck, dst)
    rtl = sorted(glob.glob(os.path.join(sq["logical"], "*.sv")))

    def restore_rtl():
        for f in rtl:
            shutil.copy2(f, os.path.join(q["logical"], os.path.basename(f)))

    def edit(name, old, new):
        f = os.path.join(q["logical"], name)
        t = open(f, encoding="utf-8").read()
        if old not in t:
            return False
        open(f, "w", encoding="utf-8").write(t.replace(old, new))
        return True

    def run3(mode="review"):
        c, _, _, info, _ = check_p3a(p, mode, [])
        return c, info

    restore_rtl()
    c, info = run3()
    results.append(("P3a baseline run is clean", not c, [f"{x['code']}/{x['rule']}" for x in c][:4]))

    applied = all(edit(os.path.basename(f), "REQ-323", "REQ-001") for f in rtl
                  if "REQ-323" in open(f, encoding="utf-8").read())
    c, _ = run3()
    results.append(("P3a-1 every tag of REQ-323 removed -> CF-COVER",
                    applied and any(x["code"] == "CF-COVER" and x["where"] == "REQ-323" for x in c),
                    [x["code"] for x in c if x["code"] == "CF-COVER"][:2]))
    restore_rtl()

    ok = edit("m_ftel_dphy_rx_timing_init.sv", "// OPEN K6 REQ-195:", "// REQ-195:")
    c, _ = run3()
    results.append(("P3a-2 OPEN tag of a provisional REQ removed -> CF-TAG/OPEN-COUNT",
                    ok and any(x["rule"] == "OPEN-COUNT" and x["where"] == "REQ-195" for x in c),
                    [x["rule"] for x in c if x["code"] == "CF-TAG"][:3]))
    restore_rtl()

    ok = edit("m_ftel_dphy_rx_timing_init.sv", "  // OPEN K6 REQ-195:", "  // OPEN K6 REQ-195: duplicate\n  // OPEN K6 REQ-195:")
    c, _ = run3()
    results.append(("P3a-3 OPEN tag duplicated -> CF-TAG/OPEN-COUNT",
                    ok and any(x["rule"] == "OPEN-COUNT" and "has 2 OPEN" in x["evidence"] for x in c),
                    [x["evidence"][:50] for x in c if x["rule"] == "OPEN-COUNT"][:1]))
    restore_rtl()

    ok = edit("m_ftel_dphy_rx_timing_init.sv", "// OPEN K6 REQ-195:", "// OPEN K8 REQ-195:")
    c, _ = run3()
    results.append(("P3a-4 OPEN tag with an id the REQ does not have -> CF-TAG/OPEN-ID",
                    ok and any(x["rule"] == "OPEN-ID" for x in c), [x["rule"] for x in c if x["code"] == "CF-TAG"][:3]))
    restore_rtl()

    ok = edit("m_ftel_dphy_rx_cl_ctrl.sv", "`timescale 1ns/1ps", "// edited after the lint\n`timescale 1ns/1ps")
    c, _ = run3()
    rules = {x["rule"] for x in c}
    results.append(("P3a-5 RTL edited after the lint -> CF-DRIFT (VCS and SpyGlass)",
                    ok and {"VCS-STALE", "SG-STALE"} <= rules, sorted(rules)[:4]))
    restore_rtl()

    man = json.load(open(sq["vcs_manifest"], encoding="utf-8"))
    man["runs"][0]["lint"] = 1
    json.dump(man, open(q["vcs_manifest"], "w", encoding="utf-8"))
    c, _ = run3()
    results.append(("P3a-6 VCS lint message -> CF-LINT/VCS", any(x["rule"] == "VCS" for x in c), [x["rule"] for x in c][:3]))
    shutil.copy2(sq["vcs_manifest"], q["vcs_manifest"])

    with open(q["sg_report"], "a", encoding="utf-8") as f:
        f.write("[2A]     W415a    W415a    Warning    /x/m_ftel_dphy_rx_eot.sv    97    5     Signal w_x is being assigned multiple times\n")
    c, _ = run3()
    results.append(("P3a-7 SpyGlass warning -> CF-LINT/SG", any(x["rule"] == "SG-W415a" for x in c), [x["rule"] for x in c][:3]))
    shutil.copy2(sq["sg_report"], q["sg_report"])

    ok = edit("m_ftel_dphy_rx_cl_ctrl.sv", "always_comb begin : p_state_nxt", "always @* begin : p_state_nxt")
    c, _ = run3()
    results.append(("P3a-8 rule violation (always @*) -> CF-LINT", ok and any(x["code"] == "CF-LINT" and x["rule"] in ("P6", "R2")
                                                                             for x in c), sorted({x["rule"] for x in c})[:4]))
    restore_rtl()

    ok = edit("m_ftel_dphy_rx_ppi_out.sv", "  // REQ-207, REQ-236\n", "  // REQ-207, REQ-236, REQ-999\n")
    c, _ = run3()
    results.append(("P3a-9 tag of a REQ that does not exist -> CF-TAG/T6", ok and any(x["rule"] == "T6" for x in c),
                    [x["rule"] for x in c if x["code"] == "CF-TAG"][:3]))
    restore_rtl()

    with open(p["config_pkg"], "a", encoding="utf-8") as f:
        f.write("\n")
    c, _ = run3()
    results.append(("P3a-10 configuration package edited after P2 -> CF-DRIFT/P2-OUTPUT",
                    any(x["rule"] == "P2-OUTPUT" for x in c), [x["rule"] for x in c][:3]))
    shutil.copy2(src["config_pkg"], p["config_pkg"])

    c, info = run3("gate")
    n_open = sum(x["code"] == "CF-OPEN" for x in c)
    results.append(("P3a-11 gate mode -> CF-OPEN for every provisional REQ in scope",
                    n_open == info["provisional_in_scope"] and n_open > 0, f"CF-OPEN {n_open}"))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=["P1", "P2", "P3a"])
    ap.add_argument("--ip", required=True)
    ap.add_argument("--mode", choices=["review", "gate"], default="review")
    ap.add_argument("--no-state", action="store_true", help="do not write conflicts/flow_state files")
    ap.add_argument("--selftest-negative", action="store_true")
    ap.add_argument("--workdir", help="scratch directory for --selftest-negative")
    a = ap.parse_args()
    if a.selftest_negative:
        if not a.workdir:
            ap.error("--selftest-negative needs --workdir")
        sys.exit(selftest_negative(a.ip, a.workdir))
    if not a.phase:
        ap.error("--phase is required")
    sys.exit(run_phase(a.ip, a.mode, not a.no_state, a.phase))


if __name__ == "__main__":
    main()
