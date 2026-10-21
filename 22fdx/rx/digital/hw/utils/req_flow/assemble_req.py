#!/usr/bin/env python3
"""Assemble per-section requirement chunks into structured_spec.json (req_flow phase P1).

The extraction step (an LLM following .claude/commands/dphy_spec_parse.md) writes one JSON chunk
per spec section:  {"section": str, "requirements": [...], "findings": [...]}
Requirement and finding objects carry every schema field EXCEPT the ids. This script does the
deterministic part: orders everything by source line, assigns REQ-NNN / F-NNN, fills the
metadata (spec sha256 and revision are read from the spec itself, never typed by hand), and sets
the fields that follow from the spec by rule (derive_rules.py: open status, block and category of
table rows); the number of values it overrode is printed per field.

Ids are stable (since spec v0.11, so that RTL, SVA and test tags keep pointing at the same
requirement when the spec changes). With a previous artifact (--prev, by default the --out file
when it exists):
  1. an item that carries "prev_req_id" / "prev_finding_id" (a regenerated stale item, see the
     rebase worklist) keeps that id;
  2. an item whose source_quote and text are unchanged keeps its id;
  3. any other item gets the next free number. The id of an item that disappeared is retired and
     never reused: metadata.req_id_next / finding_id_next record the next free number.
The output stays ordered by source line, so ids are no longer in sequence. --renumber ignores the
previous artifact (a fresh extraction).

Usage:
  assemble_req.py --chunks <dir> --spec <spec.md> --ip <ip_name> --mode review|gate --out <json>
                  [--prev <json> | --renumber]
  assemble_req.py --selftest-ids --chunks <dir> --spec <spec.md> --ip <ip_name> --prev <json>
                  --workdir <scratch dir>
"""
import argparse
import copy
import glob
import hashlib
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive_rules    # noqa: E402
import spec_inventory  # noqa: E402


def spec_revision(text):
    m = re.search(r"\*\*DRAFT (v[0-9.]+)\*\*", text)
    if m:
        return f"{m.group(1)} (draft)"
    rows = re.findall(r"^\|\s*(v[0-9.]+[^|]*)\|\s*(\d{4}-\d{2}-\d{2})", text, re.M)
    return rows[-1][0].strip() if rows else "unknown"


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def ident(item):
    """Identity of a requirement or finding across revisions: its verbatim quote and its text."""
    return norm(item.get("source_quote")), norm(item.get("text"))


def id_num(x):
    return int(x.split("-")[1])


def assign_ids(items, prev_items, id_key, prefix, link_key, next_hint):
    """Give each (line, file, n, obj) of the sorted list an id; see the module docstring.
    Returns (ids, stats, next free number). Removes link_key from the objects."""
    prev_by_id = {p[id_key]: p for p in prev_items}
    unclaimed = {}
    for p in sorted(prev_items, key=lambda p: (p["source_line"], id_num(p[id_key]))):
        unclaimed.setdefault(ident(p), []).append(p[id_key])
    ids, claimed, linked, matched = [None] * len(items), set(), [], []
    for k, (_, f, n, obj) in enumerate(items):
        link = obj.pop(link_key, None)
        if link is None:
            continue
        if link not in prev_by_id:
            sys.exit(f"{f}: item {n}: {link_key} {link} is not in the previous artifact")
        if link in claimed:
            sys.exit(f"{f}: item {n}: {link_key} {link} is claimed twice")
        ids[k] = link
        claimed.add(link)
        linked.append(link)
        for lst in unclaimed.values():
            if link in lst:
                lst.remove(link)
    for k, (_, _, _, obj) in enumerate(items):
        if ids[k] is None:
            lst = unclaimed.get(ident(obj))
            if lst:
                ids[k] = lst.pop(0)
                claimed.add(ids[k])
                matched.append(ids[k])
    nxt = max([next_hint or 1] + [id_num(i) + 1 for i in prev_by_id])
    new = []
    for k in range(len(items)):
        if ids[k] is None:
            ids[k] = f"{prefix}-{nxt:03d}"
            nxt += 1
            new.append(ids[k])
    retired = sorted(set(prev_by_id) - claimed, key=id_num)
    return ids, {"linked": linked, "matched": matched, "new": new, "retired": retired}, nxt


def load_chunks(chunks_dir):
    reqs, finds = [], []
    files = sorted(glob.glob(os.path.join(chunks_dir, "*.json")))
    if not files:
        sys.exit(f"no chunk files in {chunks_dir}")
    for f in files:
        try:
            ch = json.load(open(f, encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"{f}: invalid JSON: {e}")
        for key in ("requirements", "findings"):
            if not isinstance(ch.get(key, []), list):
                sys.exit(f"{f}: '{key}' must be a list")
        for n, r in enumerate(ch.get("requirements", [])):
            if "req_id" in r:
                sys.exit(f"{f}: requirement {n} carries req_id — ids are assigned by this script")
            reqs.append((r.get("source_line", 0), os.path.basename(f), n, r))
        for n, x in enumerate(ch.get("findings", [])):
            if "finding_id" in x:
                sys.exit(f"{f}: finding {n} carries finding_id — ids are assigned by this script")
            finds.append((x.get("source_line", 0), os.path.basename(f), n, x))
    reqs.sort(key=lambda t: (t[0], t[1], t[2]))
    finds.sort(key=lambda t: (t[0], t[1], t[2]))
    return reqs, finds, len(files)


def assemble(chunks_dir, spec, ip, mode, prev, repo):
    """Return (doc, id stats, derived-field overrides, chunk file count). prev: previous doc or None."""
    raw = open(spec, "rb").read()
    reqs, finds, nfiles = load_chunks(chunks_dir)
    pmd = (prev or {}).get("metadata", {})
    rid, rstat, rnext = assign_ids(reqs, (prev or {}).get("requirements", []), "req_id", "REQ",
                                   "prev_req_id", pmd.get("req_id_next"))
    fid, fstat, fnext = assign_ids(finds, (prev or {}).get("findings", []), "finding_id", "F",
                                   "prev_finding_id", pmd.get("finding_id_next"))
    if rnext > 1000 or fnext > 1000:
        sys.exit("more than 999 ids used: widen the id format first")
    doc = {
        "metadata": {
            "ip_name": ip,
            "spec_path": os.path.relpath(os.path.abspath(spec), repo),
            "spec_sha256": hashlib.sha256(raw).hexdigest(),
            "spec_revision": spec_revision(raw.decode("utf-8")),
            "mode": mode,
            "generated_by": "dphy_spec_parse (assembled by assemble_req.py)",
            "gate_1": {"status": "draft", "by": None, "at": None},
            "req_id_next": rnext,
            "finding_id_next": fnext,
        },
        "requirements": [{"req_id": i, **r} for i, (_, _, _, r) in zip(rid, reqs)],
        "findings": [{"finding_id": i, **x} for i, (_, _, _, x) in zip(fid, finds)],
    }
    inv = spec_inventory.build(spec)
    changed = derive_rules.apply(doc, inv, raw.decode("utf-8").splitlines())
    return doc, {"requirements": rstat, "findings": fstat}, changed, nfiles


def print_id_stats(stats):
    for kind, s in stats.items():
        print(f"ids ({kind}): {len(s['matched'])} kept (same quote and text), {len(s['linked'])} kept by link, "
              f"{len(s['new'])} new {s['new'][:12]}{' …' if len(s['new']) > 12 else ''}, "
              f"{len(s['retired'])} retired {s['retired'][:12]}{' …' if len(s['retired']) > 12 else ''}")


def selftest_ids(a, prev):
    """Id stability tests on scratch copies of the chunks; the real artifacts are not touched."""
    work = os.path.join(a.workdir, "assemble_selftest_ids")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    results = []

    def run(chunks, prev_doc):
        doc, stats, _, _ = assemble(chunks, a.spec, a.ip, "review", prev_doc, a.repo)
        return doc, stats

    def copy_chunks(name):
        d = os.path.join(work, name)
        shutil.copytree(a.chunks, d)
        return d

    by_key = lambda doc: {ident(r): r["req_id"] for r in doc["requirements"]}
    # 1. re-assembling the chunks of the previous artifact reproduces its ids and items
    d1, s1 = run(a.chunks, prev)
    same = (d1["requirements"] == prev["requirements"] and d1["findings"] == prev["findings"])
    results.append(("1 re-assemble reproduces every id and item", same,
                    f"new={s1['requirements']['new'][:3]} retired={s1['requirements']['retired'][:3]}"))
    nxt = d1["metadata"]["req_id_next"]
    # 2. a requirement inserted early keeps every other id; the new one gets the next number
    c2 = copy_chunks("c2")
    first = sorted(glob.glob(os.path.join(c2, "*.json")))[0]
    ch = json.load(open(first, encoding="utf-8"))
    ins = copy.deepcopy(ch["requirements"][0])
    ins["text"] = "SELFTEST inserted requirement " + ins["text"]
    ch["requirements"].insert(0, ins)
    json.dump(ch, open(first, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    d2, s2 = run(c2, d1)
    k1, k2 = by_key(d1), by_key(d2)
    kept = all(k2.get(k) == v for k, v in k1.items())
    results.append(("2 early insertion keeps all ids, new id = next", kept and s2["requirements"]["new"] == [f"REQ-{nxt:03d}"],
                    f"new={s2['requirements']['new']}"))
    # 3. delete the highest id, then add another item: the deleted id is retired, never reused
    top = max(d2["requirements"], key=lambda r: id_num(r["req_id"]))
    c3 = copy_chunks("c3")
    shutil.copy(first, os.path.join(c3, os.path.basename(first)))
    for f in sorted(glob.glob(os.path.join(c3, "*.json"))):
        ch = json.load(open(f, encoding="utf-8"))
        ch["requirements"] = [r for r in ch["requirements"] if ident(r) != ident(top)]
        json.dump(ch, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ch = json.load(open(os.path.join(c3, os.path.basename(first)), encoding="utf-8"))
    ins2 = copy.deepcopy(ins)
    ins2["text"] = "SELFTEST second inserted requirement"
    ch["requirements"].append(ins2)
    json.dump(ch, open(os.path.join(c3, os.path.basename(first)), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    d3, s3 = run(c3, d2)
    ids3 = {r["req_id"] for r in d3["requirements"]}
    ok3 = (top["req_id"] not in ids3 and s3["requirements"]["retired"] == [top["req_id"]]
           and s3["requirements"]["new"] == [f"REQ-{d2['metadata']['req_id_next']:03d}"])
    results.append(("3 deleted id retired, not reused", ok3,
                    f"retired={s3['requirements']['retired']} new={s3['requirements']['new']}"))
    # 4. a reworded item keeps its id only through prev_req_id
    c4 = copy_chunks("c4")
    victim = None
    for f in sorted(glob.glob(os.path.join(c4, "*.json"))):
        ch = json.load(open(f, encoding="utf-8"))
        if ch["requirements"] and victim is None:
            victim = ch["requirements"][-1]
            old_id = k1[ident(victim)]
            victim["text"] = victim["text"] + " (reworded)"
            victim["prev_req_id"] = old_id
            json.dump(ch, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _, s4 = run(c4, d1)
    ok4 = s4["requirements"]["linked"] == [old_id] and not s4["requirements"]["new"] and not s4["requirements"]["retired"]
    results.append(("4 reworded item keeps its id through prev_req_id", ok4, f"linked={s4['requirements']['linked']}"))
    print("ID SELFTEST")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}   ({detail})")
    allok = all(ok for _, ok, _ in results)
    print("RESULT:", f"{sum(ok for _, ok, _ in results)}/{len(results)}", "PASS" if allok else "FAIL")
    shutil.rmtree(work, ignore_errors=True)
    return 0 if allok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--ip", required=True)
    ap.add_argument("--mode", choices=["review", "gate"])
    ap.add_argument("--out")
    ap.add_argument("--prev", help="previous structured_spec.json whose ids are kept (default: --out when it exists)")
    ap.add_argument("--renumber", action="store_true", help="ignore any previous artifact (fresh extraction)")
    ap.add_argument("--selftest-ids", action="store_true")
    ap.add_argument("--workdir", help="scratch directory for --selftest-ids")
    ap.add_argument("--repo", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    a = ap.parse_args()

    prev_path = None if a.renumber else (a.prev or (a.out if a.out and os.path.exists(a.out) else None))
    prev = json.load(open(prev_path, encoding="utf-8")) if prev_path else None
    if a.selftest_ids:
        if not (prev and a.workdir):
            ap.error("--selftest-ids needs --prev (or an existing --out) and --workdir")
        sys.exit(selftest_ids(a, prev))
    if not (a.mode and a.out):
        ap.error("--mode and --out are required")
    doc, stats, changed, nfiles = assemble(a.chunks, a.spec, a.ip, a.mode, prev, a.repo)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"assembled {len(doc['requirements'])} requirements, {len(doc['findings'])} findings "
          f"from {nfiles} chunks -> {a.out}")
    print(f"id ledger: {'ids kept from ' + prev_path if prev_path else 'fresh numbering (no previous artifact)'}")
    print_id_stats(stats)
    print("derived-field overrides: " + ", ".join(f"{k} {v}" for k, v in changed.items()))


if __name__ == "__main__":
    main()
