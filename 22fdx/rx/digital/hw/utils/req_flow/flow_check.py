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
Later stages add CF-CONFIG, CF-INDEP, CF-LINT, CF-DRIFT, CF-SIM, CF-VAC, CF-CDC, CF-DOC.

Usage:
  flow_check.py --phase P1 --ip ftel_dphy_rx [--mode review|gate] [--no-state]
  flow_check.py --selftest-negative --ip ftel_dphy_rx --workdir <scratch dir>
Exit status: 0 = no conflict, 2 = conflicts (flow must stop), 1 = usage / selftest failure.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import validate_req  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CODE_MAP = {"SPEC": "CF-SPEC", "SCHEMA": "CF-SCHEMA", "CONSIST": "CF-SCHEMA", "NAME": "CF-SCHEMA",
            "DERIVE": "CF-SCHEMA",
            "QUOTE": "CF-QUOTE", "COVER": "CF-COVER", "OPEN": "CF-OPEN", "GATE_OPEN": "CF-OPEN"}
NOT_WAIVABLE = {"CF-SPEC", "CF-QUOTE", "CF-INDEP"}
OWNER = {"CF-SPEC": "rerun P1", "CF-SCHEMA": "prompt / regeneration", "CF-QUOTE": "prompt / regeneration",
         "CF-COVER": "prompt / regeneration", "CF-OPEN": "spec owner / team"}
FIX = {"CF-SPEC": "rerun /dphy_autoflow from P1 on the current spec",
       "CF-SCHEMA": "regenerate the affected REQs (max 2 rounds), else fix the parse prompt",
       "CF-QUOTE": "re-quote verbatim from the cited line; never edit the spec to match",
       "CF-COVER": "add REQs sourced from the uncovered row / citing the id",
       "CF-OPEN": "flag the REQ correctly, or resolve the open item with the owner"}


def paths(ip, root=REPO):
    d = os.path.join(root, "hw", "rtl", "ip", ip)
    return {"ip_dir": d, "spec": os.path.join(d, "doc", "spec.md"),
            "structured": os.path.join(d, "req", "structured_spec.json"),
            "waivers": os.path.join(d, "req", "waivers.yaml"),
            "state": os.path.join(d, "req", "flow_state.json"),
            "conflicts": os.path.join(d, "req", "conflicts_P1.json")}


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
    waived, rejected = [], []
    for w in (waivers if waivers is not None else load_waivers(p["waivers"])):
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
    return conflicts, waived, rejected, info


def run_phase(ip, mode, write_state=True):
    p = paths(ip)
    conflicts, waived, rejected, info = check_p1(p, mode)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    result = {"phase": "P1", "mode": mode, "at": now, "spec_sha256": sha(p["spec"]),
              "structured_spec_sha256": sha(p["structured"]), "conflicts": conflicts,
              "waived": waived, "rejected_waivers": rejected, "info": info}
    if write_state:
        json.dump(result, open(p["conflicts"], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        state = json.load(open(p["state"], encoding="utf-8")) if os.path.exists(p["state"]) else {"ip": ip, "phases": {}}
        state["phases"]["P1"] = {"status": "pass" if not conflicts else "blocked", "mode": mode, "at": now,
                                 "inputs": {"spec": result["spec_sha256"]},
                                 "outputs": {"structured_spec": result["structured_spec_sha256"]},
                                 "conflicts": len(conflicts), "waived": len(waived)}
        json.dump(state, open(p["state"], "w", encoding="utf-8"), indent=1)
    print(f"P1 ({mode}): {len(conflicts)} conflict(s), {len(waived)} waived, {len(rejected)} waiver(s) rejected, info={info}")
    if conflicts:
        print(f"{'ID':<14} {'Code':<10} {'Where':<16} Evidence")
        for c in conflicts[:60]:
            print(f"{c['id']:<14} {c['code']:<10} {c['where']:<16} {c['evidence'][:110]}")
        if len(conflicts) > 60:
            print(f"... {len(conflicts) - 60} more (see {p['conflicts'] if write_state else 'output'})")
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
    for i, r in enumerate(d3["requirements"], 1):
        r["req_id"] = f"REQ-{i:03d}"
    write(d3)
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

    print("NEGATIVE SELFTEST")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}   ({detail})")
    allok = all(ok for _, ok, _ in results)
    print("RESULT:", f"{sum(ok for _, ok, _ in results)}/{len(results)}", "PASS" if allok else "FAIL")
    shutil.rmtree(work, ignore_errors=True)
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", choices=["P1"])
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
    sys.exit(run_phase(a.ip, a.mode, not a.no_state))


if __name__ == "__main__":
    main()
