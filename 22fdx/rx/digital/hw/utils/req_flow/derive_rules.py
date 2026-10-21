#!/usr/bin/env python3
"""Deterministic requirement fields (req_flow; spec_review.md §5.4, option 1).

The A6 stability run of 2026-09-26 agreed on only 79.6 % of the anchors, and every disagreement
came from one of four rules the parse prompt left to judgment. These rules are computed here from
the spec instead, so two extractions of the same spec cannot differ on them:

  RC1/RC2  spec_status 'open' <=> the source line depends on an open item
           (spec_inventory.open_scope: OPEN word, Open Items row, OPEN heading or caption scope,
           citation of an open id, 'To be determined'). needs_human_decision <=> 'open'.
           A REQ the LLM marked 'open' on a line without that basis falls back to the tag of the
           line: ⚠️ -> assumed, [CSI] -> contract, ✅ -> verified, else design.
  RC3      block of a REQ sourced from a graded table row (spec_inventory.row_block)
  RC4      category of a REQ sourced from a graded table row (spec_inventory.CATEGORY_BY_KIND)

Flag consistency follows: an 'open' REQ needs review with ambiguity >= 0.35, and needs_review
implies ambiguity > 0.3. Other fields (text, clock_domain, release, ambiguity above the floor,
non-open spec_status of prose) stay with the extraction.

Used by assemble_req.py (applies the rules) and validate_req.py (checks that they hold).
"""
import copy

FALLBACK_TAGS = (("⚠️", "assumed"), ("[CSI]", "contract"), ("✅", "verified"))
OPEN_FLOOR = 0.35


def fallback_status(line_text):
    for tag, status in FALLBACK_TAGS:
        if tag in line_text:
            return status
    return "design"


def derive(req, inv, lines):
    """Return a copy of req with the deterministic fields set."""
    r = copy.deepcopy(req)
    ln = r["source_line"]
    opened = inv["open_derived"].get(str(ln))
    row = next((it for it in inv["items"] if it["line"] == ln and it.get("category")), None)
    if row:
        r["category"] = row["category"]
        r["block"] = row["block"]
    if opened is not None:
        r["spec_status"] = "open"
        r["open_item_ref"] = sorted(set(r["open_item_ref"]) | set(opened))
    elif r["spec_status"] == "open":
        r["spec_status"] = fallback_status(lines[ln - 1] if 0 < ln <= len(lines) else "")
    r["needs_human_decision"] = r["spec_status"] == "open"
    if r["needs_human_decision"]:
        r["needs_review"] = True
        r["ambiguity_score"] = max(r["ambiguity_score"], OPEN_FLOOR)
    if r["needs_review"] and r["ambiguity_score"] <= 0.3:
        r["ambiguity_score"] = OPEN_FLOOR
    return r


DERIVED_FIELDS = ("category", "block", "spec_status", "open_item_ref", "needs_human_decision",
                  "needs_review", "ambiguity_score")


def apply(doc, inv, lines):
    """Apply derive() to every requirement of doc in place; return {field: number of overrides}."""
    changed = {f: 0 for f in DERIVED_FIELDS}
    for i, r in enumerate(doc["requirements"]):
        d = derive(r, inv, lines)
        for f in DERIVED_FIELDS:
            changed[f] += d[f] != r[f]
        doc["requirements"][i] = d
    return changed


def differences(req, inv, lines):
    """Fields of req that differ from the derived value (used by the validator)."""
    d = derive(req, inv, lines)
    return [(f, req[f], d[f]) for f in DERIVED_FIELDS if d[f] != req[f]]
