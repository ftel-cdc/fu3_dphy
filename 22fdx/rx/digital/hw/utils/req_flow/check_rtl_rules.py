#!/usr/bin/env python3
"""Machine check of the [M] rules of hw/rtl/ip/ftel_dphy_rx/doc/rtl_rule.md.

The checker reads SystemVerilog the way the rule set asks for it to be written: one module or package
per file, ANSI ports, always_ff / always_comb / assign, named instance connections. It is a lexical
checker, not a parser: it strips comments, tracks brackets and statement boundaries, and reports each
place where the text breaks a rule. What text cannot decide (latches, multiple drivers, a crossing
without a cell, widths) is left to VCS lint, SpyGlass lint and SpyGlass CDC (rtl_rule.md §7).

Profiles:
  ip         every [M] rule, with the naming of ftel_dphy_rx (default)
  construct  only the language-construct rules (R1 form, R7, P1-P4, P6, P10-P12, F6): used to run
             the checker on RTL of another IP (ftel_intctl) and count its false positives

Usage:
  check_rtl_rules.py <file or dir>... [--profile ip|construct] [--structured <json>] [--spec <md>]
                     [--json <out>]
  check_rtl_rules.py --selftest-negative --workdir <scratch dir>
Exit status: 0 = no violation, 1 = violations, 2 = usage error or selftest failure.
"""
import argparse
import bisect
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IP_DIR = os.path.join(REPO, "hw", "rtl", "ip", "ftel_dphy_rx")
RULE_DOC = os.path.join(IP_DIR, "doc", "rtl_rule.md")

RULES = {
    "N1": "module name m_ftel_dphy_rx[_<block>]",
    "N2": "parameter PARA_<NAME>",
    "N3": "define DEF_<NAME>",
    "N4": "flip-flop reg_<name>: assigned in always_ff only",
    "N5": "port i_<name> / o_<name>",
    "N6": "instance u_<name>_<n>",
    "N7": "case: signals lower case, constants and enum members upper case",
    "N9": "localparam C_<NAME>",
    "N10": "net w_<name>; internal signals are reg_ or w_",
    "N11": "clock / reset of a block i_<core|byte|cfg>_clk / _rst_n",
    "N12": "package ftel_dphy_rx[_<name>]_pkg, type <name>_t",
    "N13": "label g_ (generate), p_ (always), a_ (assertion)",
    "F1": "one module or package per file, file name = unit name",
    "F2": "header, `timescale 1ns/1ps, `default_nettype none, unit, `default_nettype wire",
    "F3": "header fields",
    "F6": "named connections and named parameter overrides only",
    "R1": "always_ff @(posedge <clk> [or negedge <rst>])",
    "R2": "combinational logic in always_comb or assign only",
    "R7": "no reg / wire / integer; no int or bit signal",
    "R8": "always_ff / always_comb labelled",
    "P1": "no #delay",
    "P2": "no initial outside `ifndef SYNTHESIS",
    "P3": "no casex / casez",
    "P4": "no defparam",
    "P5": "`default_nettype none",
    "P6": "no always @, always_latch or plain always",
    "P10": "no system task outside `ifndef SYNTHESIS",
    "P11": "no inout",
    "P12": "negedge only for the asynchronous reset of an always_ff",
    "K5": "CDC_CROSSING tag on each synchronizer cell instance",
    "K6": "CDC_QUASI_STATIC tag on each configuration input",
    "K7": "CDC_GATING only in m_ftel_dphy_rx_ppi_out",
    "K10": "ports of the shared cells",
    "T1": "header REQ-IDs = REQs tagged in the body; HAS field",
    "T2": "trace tag on each always block, assign group and instance",
    "T3": "OPEN tag format, id in Table 9-1",
    "T6": "REQ-ID exists in structured_spec.json",
}
CONSTRUCT = {"R1", "R2", "R7", "P1", "P2", "P3", "P4", "P6", "P10", "P11", "P12", "F6"}

MODULE_RE = re.compile(r"^m_ftel_dphy_rx(_[a-z0-9]+)*$")
PACKAGE_RE = re.compile(r"^ftel_dphy_rx(_[a-z0-9]+)*_pkg$")
PARAM_RE = re.compile(r"^PARA_[A-Z0-9_]+$")
DEFINE_RE = re.compile(r"^DEF_[A-Z0-9_]+$")
LOCALPARAM_RE = re.compile(r"^C_[A-Z0-9_]+$")
PORT_RE = re.compile(r"^[io]_[a-z0-9_]+$")
SIGNAL_RE = re.compile(r"^(reg|w)_[a-z0-9_]+$")
INST_RE = re.compile(r"^u_[a-z0-9_]+_[0-9]+$")
TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*_t$")
UPPER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
LOWER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
BLOCK_CLK_RE = re.compile(r"^i_(core|byte|cfg)_clk$")
BLOCK_RST_RE = re.compile(r"^i_(core|byte|cfg)_rst_n$")
LOCAL_RST_RE = re.compile(r"^w_(core|byte|cfg)_rst_n$")

CORE, WRAP = "m_ftel_dphy_rx", "m_ftel_dphy_rx_wrap"
CELL_PORTS = {  # K10
    "m_ftel_dphy_rx_sync": {"i_clk", "i_rstn", "i_data_in", "o_data_out"},
    "m_ftel_dphy_rx_rst_sync": {"i_clk", "i_async_reset_n", "o_sync_reset_n"},
    "m_ftel_dphy_rx_tsync": {"i_src_clk", "i_src_rst_n", "i_dst_clk", "i_dst_rst_n", "i_pulse", "o_pulse"},
}
GATING_MODULE = "m_ftel_dphy_rx_ppi_out"
N11_EXEMPT = {CORE, WRAP, *CELL_PORTS}
HEADER_FIELDS = ("Author", "Email", "Created Date", "Module", "Description", "Parent", "HAS",
                 "Clock domains", "REQ-IDs", "OPEN")
F3_REQUIRED = ("Module", "Description", "HAS", "Clock domains", "REQ-IDs", "OPEN")
SYS_FUNCS_OK = {"clog2", "bits", "signed", "unsigned", "high", "low", "left", "right", "size",
                "countones", "onehot", "onehot0"}
OPEN_ID = r"(?:K\d+|S\d+|T\d+|ADR-\d{3})"
OPEN_TAG_RE = re.compile(rf"^OPEN\s+({OPEN_ID}(?:\s*[,/]\s*{OPEN_ID})*)\s+(REQ-\d{{3}}(?:\s*,\s*REQ-\d{{3}})*)\s*:\s*\S")
CDC_TAG_RE = re.compile(r"CDC_CROSSING:\s*\S+\s*->\s*\S+:\s*\S.*\(HAS §[0-9.]+(?:,\s*(?:Table|Figure) [0-9-]+)?\)")
QUASI_TAG_RE = re.compile(r"CDC_QUASI_STATIC:\s*\S.*\(HAS §[0-9.]+\)")
TRACE_RE = re.compile(r"\b(REQ-\d{3}|D-\d+)\b|CDC_CROSSING:|CDC_GATING|CDC_QUASI_STATIC:")
REQ_RE = re.compile(r"\bREQ-\d{3}\b")

KEYWORDS = {
    "module", "endmodule", "package", "endpackage", "input", "output", "inout", "logic", "bit", "int",
    "integer", "reg", "wire", "byte", "shortint", "longint", "signed", "unsigned", "parameter",
    "localparam", "typedef", "enum", "struct", "packed", "union", "assign", "always", "always_ff",
    "always_comb", "always_latch", "initial", "final", "begin", "end", "if", "else", "case", "casex",
    "casez", "endcase", "default", "for", "while", "repeat", "forever", "generate", "endgenerate",
    "genvar", "function", "endfunction", "task", "endtask", "return", "import", "export", "posedge",
    "negedge", "or", "and", "not", "assert", "assume", "cover", "property", "endproperty", "sequence",
    "endsequence", "disable", "iff", "unique", "unique0", "priority", "inside", "var", "automatic",
    "static", "const", "void", "defparam", "string", "real", "type",
}
DIRECTIVES_LINE = {"`timescale", "`default_nettype", "`ifdef", "`ifndef", "`else", "`elsif", "`endif",
                   "`define", "`undef", "`include", "`resetall"}

TOKEN_RE = re.compile(r"""
   (?P<ws>\s+)
  |(?P<dir>`[A-Za-z_]\w*)
  |(?P<num>\d*'[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ_?]+|\d[\d_]*(?:\.\d+)?|'[01xXzZ])
  |(?P<id>\$?[A-Za-z_][A-Za-z0-9_$]*)
  |(?P<op>\|->|\|=>|===|!==|<<<=|>>>=|<<=|>>=|<<<|>>>|==|!=|<=|>=|<<|>>|&&|\|\||::|\+\+|--|\+=|-=|\*=|/=|&=|\|=|\^=|->|\#\#|[-+*/%&|^~!<>=?:;,.\#@(){}\[\]'"])
""", re.X)


class Tok:
    __slots__ = ("kind", "text", "line")

    def __init__(self, kind, text, line):
        self.kind, self.text, self.line = kind, text, line


class Source:
    """One file: code with comments blanked, comments per line, tokens, preprocessor regions."""

    def __init__(self, path, text):
        self.path, self.text = path, text
        self.code, self.comments, self.raw_comments = split_code_comments(text)
        self.code_lines = self.code.split("\n")
        self.nosynth = nosynth_lines(self.code_lines)
        self.toks = tokenize(self.code)

    def comment_block_above(self, line):
        """Comments on `line` plus the contiguous comment-only lines directly above it."""
        out = list(self.comments.get(line, []))
        k = line - 1
        while k >= 1 and self.comments.get(k) and not self.code_lines[k - 1].strip():
            out = self.comments[k] + out
            k -= 1
        return out


def split_code_comments(text):
    """Code with comments and string bodies blanked (same length, newlines kept); comments by line."""
    code, comments, raw = [], defaultdict(list), defaultdict(list)
    i, n, line = 0, len(text), 1
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            comments[line].append(text[i + 2:j].strip())
            raw[line].append(text[i + 2:j])
            code.append(" " * (j - i))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            seg = text[i:j]
            for k, part in enumerate(seg[2:-2].split("\n")):
                comments[line + k].append(part.strip())
                raw[line + k].append(part)
            code.append("".join(ch if ch == "\n" else " " for ch in seg))
            line += seg.count("\n")
            i = j
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] not in '"\n':
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            code.append('"' + " " * max(0, j - i - 2) + ('"' if j - i >= 2 else ""))
            i = j
        else:
            if text[i] == "\n":
                line += 1
            code.append(text[i])
            i += 1
    return "".join(code), comments, raw


def nosynth_lines(code_lines):
    """Lines excluded from synthesis: inside `ifndef SYNTHESIS (before its `else) or `ifdef SYNTHESIS `else."""
    out, stack = set(), []
    for n, l in enumerate(code_lines, 1):
        m = re.match(r"\s*`(ifdef|ifndef|elsif|else|endif)\b\s*(\w*)", l)
        if m:
            kind, macro = m.groups()
            if kind in ("ifdef", "ifndef"):
                stack.append([kind, macro, False])
            elif kind in ("else", "elsif") and stack:
                stack[-1][2] = True
            elif kind == "endif" and stack:
                stack.pop()
            continue
        if any((k == "ifndef" and mac == "SYNTHESIS" and not e) or (k == "ifdef" and mac == "SYNTHESIS" and e)
               for k, mac, e in stack):
            out.add(n)
    return out


def tokenize(code):
    starts = [0] + [m.end() for m in re.finditer("\n", code)]
    toks, pos, skip_line = [], 0, None
    for m in TOKEN_RE.finditer(code):
        if m.start() != pos:  # unknown character: keep it as an operator token
            pass
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        line = bisect.bisect_right(starts, m.start())
        if skip_line == line:
            continue
        if kind == "dir":
            if m.group() in DIRECTIVES_LINE:
                skip_line = line  # directive and its arguments are not design text
                continue
            kind = "id"  # macro use: an expression atom
        toks.append(Tok(kind, m.group(), line))
    return toks


def match_close(toks, i, open_t="(", close_t=")"):
    d = 0
    for k in range(i, len(toks)):
        if toks[k].text == open_t:
            d += 1
        elif toks[k].text == close_t:
            d -= 1
            if d == 0:
                return k
    return len(toks) - 1


def match_end(toks, i):
    """toks[i] is 'begin': index of its 'end'."""
    d = 0
    for k in range(i, len(toks)):
        if toks[k].text == "begin":
            d += 1
        elif toks[k].text == "end":
            d -= 1
            if d == 0:
                return k
    return len(toks) - 1


def split_top(toks):
    """Split a token list at commas outside (), [], {}."""
    parts, cur, d = [], [], 0
    for t in toks:
        if t.text in ("(", "[", "{"):
            d += 1
        elif t.text in (")", "]", "}"):
            d -= 1
        if t.text == "," and d == 0:
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        parts.append(cur)
    return parts


def skip_to(toks, i, text):
    while i < len(toks) and toks[i].text != text:
        i += 1
    return i


def lhs_names(lhs):
    """Base identifiers written by an lvalue: not inside [], not after '.', not a package scope."""
    names, d = [], 0
    for k, t in enumerate(lhs):
        if t.text == "[":
            d += 1
        elif t.text == "]":
            d -= 1
        elif d == 0 and t.kind == "id" and t.text not in KEYWORDS:
            prev = lhs[k - 1].text if k else ""
            nxt = lhs[k + 1].text if k + 1 < len(lhs) else ""
            if prev not in (".", "::") and nxt != "::":
                names.append(t)
    return names


ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>="}


def assignments(body, ops):
    """(lhs tokens, op token) for each assignment of the given operators at paren depth 0."""
    out, d, k = [], 0, 0
    while k < len(body):
        t = body[k].text
        if t == "(":
            d += 1
        elif t == ")":
            d -= 1
        elif d == 0 and t in ops:
            m, bd, lhs = k - 1, 0, []
            while m >= 0:
                tt = body[m].text
                if tt in ("]", "}"):
                    bd += 1
                elif tt in ("[", "{"):
                    bd -= 1
                elif bd == 0 and tt in (";", "begin", "end", "else", ":", ")", "default", "endcase"):
                    break
                lhs.insert(0, body[m])
                m -= 1
            out.append((lhs, body[k]))
            while k < len(body) and body[k].text != ";":  # the rest of the statement is its RHS
                k += 1
        k += 1
    return out


class Checker:
    def __init__(self, profile, req_ids, open_ids):
        self.profile, self.req_ids, self.open_ids = profile, req_ids, open_ids
        self.v = []

    def add(self, src, line, rule, msg):
        if self.profile == "construct" and rule not in CONSTRUCT:
            return
        self.v.append({"file": src.path, "line": line, "rule": rule, "msg": msg})

    # ------------------------------------------------------------------ file level
    def check_file(self, path):
        src = Source(path, open(path, encoding="utf-8").read())
        self.regex_rules(src)
        units = [(t.text, src.toks[k + 1].text, t.line, k) for k, t in enumerate(src.toks)
                 if t.text in ("module", "package") and k + 1 < len(src.toks)]
        stem = os.path.splitext(os.path.basename(path))[0]
        if len(units) != 1:
            self.add(src, 1, "F1", f"{len(units)} design units in the file, expected 1")
        for kind, name, line, k in units:
            if name != stem:
                self.add(src, line, "F1", f"{kind} {name} in file {os.path.basename(path)}")
            if kind == "module":
                if not MODULE_RE.match(name):
                    self.add(src, line, "N1", f"module name {name}")
                self.check_module(src, name, k)
            else:
                if not PACKAGE_RE.match(name):
                    self.add(src, line, "N12", f"package name {name}")
                self.check_package(src, name, k)
        if units:
            self.check_layout(src, units[0][1])
        self.check_tags(src, units[0][1] if units else stem)

    def regex_rules(self, src):
        for n, l in enumerate(src.code_lines, 1):
            ns = n in src.nosynth
            if l.lstrip().startswith("`") and not l.lstrip().startswith("`define"):
                continue  # compiler directive (`default_nettype wire is not a wire)
            for m in re.finditer(r"\b(reg|wire|integer)\b", l):
                self.add(src, n, "R7", f"'{m.group(1)}' (use logic)")
            if re.search(r"\b(casex|casez)\b", l):
                self.add(src, n, "P3", "casex/casez")
            if re.search(r"\bdefparam\b", l):
                self.add(src, n, "P4", "defparam")
            if re.search(r"\balways\s*@", l) or re.search(r"\balways_latch\b", l) or re.search(r"\balways\b(?!_)", l):
                self.add(src, n, "P6", "always other than always_ff / always_comb")
            m = re.search(r"\balways\s*@\s*(\*|\(([^)]*)\))", l)
            if m and not re.search(r"\b(posedge|negedge)\b", m.group(2) or ""):
                self.add(src, n, "R2", "combinational always @ (use always_comb)")
            if re.search(r"\binout\b", l):
                self.add(src, n, "P11", "inout")
            if not ns:
                if re.search(r"(?<![#\w'])#\s*[\d.]", l):
                    self.add(src, n, "P1", "#delay")
                if re.search(r"\binitial\b", l):
                    self.add(src, n, "P2", "initial outside `ifndef SYNTHESIS")
                for m in re.finditer(r"\$(\w+)", l):
                    if m.group(1) not in SYS_FUNCS_OK:
                        self.add(src, n, "P10", f"${m.group(1)} outside `ifndef SYNTHESIS")
            m = re.match(r"\s*`define\s+(\w+)", l)
            if m and not DEFINE_RE.match(m.group(1)):
                self.add(src, n, "N3", f"define {m.group(1)}")

    def check_layout(self, src, unit):
        code = [(n, l.strip()) for n, l in enumerate(src.code_lines, 1) if l.strip()]
        if len(code) < 4:
            self.add(src, 1, "F2", "file too short for the required layout")
            return
        if re.sub(r"\s+", " ", code[0][1]) != "`timescale 1ns/1ps":
            self.add(src, code[0][0], "F2", f"first line must be `timescale 1ns/1ps, found '{code[0][1][:40]}'")
        if re.sub(r"\s+", " ", code[1][1]) != "`default_nettype none":
            self.add(src, code[1][0], "F2", "`default_nettype none must follow `timescale")
            self.add(src, code[1][0], "P5", "`default_nettype none missing after `timescale")
        if not re.match(r"(module|package)\b", code[2][1]):
            self.add(src, code[2][0], "F2", "the design unit must follow `default_nettype none")
        if re.sub(r"\s+", " ", code[-1][1]) != "`default_nettype wire":
            self.add(src, code[-1][0], "F2", "last line must be `default_nettype wire")
        self.check_header(src, unit, code[0][0])

    def header_fields(self, src, first_code_line):
        fields, cur = {}, None
        for n in range(1, first_code_line):
            for raw in src.raw_comments.get(n, []):
                m = re.match(r"\s*(" + "|".join(re.escape(f) for f in HEADER_FIELDS) + r")\s*:\s*(.*)$", raw)
                if m:
                    cur = m.group(1)
                    fields[cur] = m.group(2).strip()
                elif cur and raw.startswith("   ") and raw.strip():
                    fields[cur] += " " + raw.strip()
                else:
                    cur = None
        return fields

    def check_header(self, src, unit, first_code_line):
        text = " ".join(c for n in range(1, first_code_line) for c in src.comments.get(n, []))
        if "Copyright (c)" not in text or "Evolution History" not in text:
            self.add(src, 1, "F3", "header without the FTEL copyright block or the Evolution History")
        f = self.header_fields(src, first_code_line)
        for k in F3_REQUIRED:
            if not f.get(k):
                self.add(src, 1, "F3", f"header field '{k}' missing or empty")
        if f.get("Module") and f["Module"] != unit:
            self.add(src, 1, "F3", f"header Module '{f['Module']}' differs from {unit}")
        if f.get("HAS") and not re.match(r"draft v\d+\.\d+, §", f["HAS"]):
            self.add(src, 1, "T1", f"header HAS field '{f['HAS'][:40]}' is not 'draft vX.Y, §…'")
        if f.get("OPEN") and f["OPEN"] != "none":
            for oid in re.findall(OPEN_ID, f["OPEN"]):
                if oid not in self.open_ids:
                    self.add(src, 1, "T3", f"header OPEN id {oid} is not in Table 9-1")
        self.header = f

    def check_tags(self, src, unit):
        first_code = next((n for n, l in enumerate(src.code_lines, 1) if l.strip()), 1)
        body_reqs = set()
        for n, cs in src.comments.items():
            for c in cs:
                for r in REQ_RE.findall(c):
                    if self.req_ids is not None and r not in self.req_ids:
                        self.add(src, n, "T6", f"{r} is not in structured_spec.json")
                    if n > first_code:
                        body_reqs.add(r)
                if n > first_code and c.startswith("OPEN"):
                    m = OPEN_TAG_RE.match(c)
                    if not m:
                        self.add(src, n, "T3", f"OPEN tag not in the form 'OPEN <id> REQ-xxx: <default>': {c[:60]}")
                    else:
                        for oid in re.findall(OPEN_ID, m.group(1)):
                            if oid not in self.open_ids:
                                self.add(src, n, "T3", f"OPEN id {oid} is not in Table 9-1")
                if "CDC_GATING" in c and unit != GATING_MODULE:
                    self.add(src, n, "K7", f"CDC_GATING outside {GATING_MODULE}")
        if unit == GATING_MODULE and not any("CDC_GATING" in c for cs in src.comments.values() for c in cs):
            self.add(src, 1, "K7", f"{GATING_MODULE} has no CDC_GATING tag")
        hdr = getattr(self, "header", {}) or {}
        head_reqs = set(REQ_RE.findall(hdr.get("REQ-IDs", "")))
        for r in sorted(body_reqs - head_reqs):
            self.add(src, 1, "T1", f"{r} tagged in the body but not in the header REQ-IDs")
        for r in sorted(head_reqs - body_reqs):
            self.add(src, 1, "T1", f"{r} in the header REQ-IDs but tagged nowhere in the body")

    # ------------------------------------------------------------------ package
    def check_package(self, src, name, k):
        toks = src.toks
        end = next((j for j in range(k, len(toks)) if toks[j].text == "endpackage"), len(toks))
        i = k + 3  # 'package' name ';'
        while i < end:
            t = toks[i].text
            if t in ("localparam", "parameter"):
                i = self.param_stmt(src, toks, i, body=True)
            elif t == "typedef":
                i = self.typedef(src, toks, i)
            elif t == "function":
                i = skip_to(toks, i, "endfunction") + 1
            else:
                i = skip_to(toks, i, ";") + 1

    def typedef(self, src, toks, i):
        j = i + 1
        if toks[j].text in ("enum", "struct", "union"):
            kind = toks[j].text
            b = skip_to(toks, j, "{")
            e = match_close(toks, b, "{", "}")
            if kind == "enum":
                for part in split_top(toks[b + 1:e]):
                    if part and part[0].kind == "id" and not UPPER_RE.match(part[0].text):
                        self.add(src, part[0].line, "N7", f"enum member {part[0].text} not upper case")
            else:
                d, member = 0, []
                for t in toks[b + 1:e]:
                    if t.text == ";" and d == 0:
                        names = lhs_names(member)
                        if names and not LOWER_RE.match(names[-1].text):
                            self.add(src, names[-1].line, "N7", f"struct member {names[-1].text} not lower case")
                        member = []
                        continue
                    if t.text in ("[", "("):
                        d += 1
                    elif t.text in ("]", ")"):
                        d -= 1
                    member.append(t)
            j = e + 1
        semi = skip_to(toks, j, ";")
        tname = toks[semi - 1]
        if tname.kind == "id" and not TYPE_RE.match(tname.text):
            self.add(src, tname.line, "N12", f"type name {tname.text} (suffix _t, lower case)")
        return semi + 1

    def param_stmt(self, src, toks, i, body):
        kw = toks[i].text
        semi = skip_to(toks, i, ";")
        for part in split_top(toks[i + 1:semi]):
            names = [part[q - 1] for q in range(1, len(part)) if part[q].text == "=" and part[q - 1].kind == "id"]
            for nm in names[:1]:
                if kw == "localparam" or body:
                    if kw == "parameter":
                        self.add(src, nm.line, "N9", f"parameter {nm.text} in a body: use localparam C_<NAME>")
                    elif not LOCALPARAM_RE.match(nm.text):
                        self.add(src, nm.line, "N9", f"localparam {nm.text}")
        return semi + 1

    # ------------------------------------------------------------------ module
    def check_module(self, src, name, k):
        toks = src.toks
        end = next((j for j in range(k, len(toks)) if toks[j].text == "endmodule"), len(toks))
        i = k + 2
        while i < end and toks[i].text == "import":
            i = skip_to(toks, i, ";") + 1
        self.ports, self.inputs = {}, set()
        if i < end and toks[i].text == "#":
            close = match_close(toks, i + 1)
            for part in split_top(toks[i + 2:close]):
                nm = next((part[q - 1] for q in range(1, len(part)) if part[q].text == "="), None)
                if nm is not None and not PARAM_RE.match(nm.text):
                    self.add(src, nm.line, "N2", f"parameter {nm.text}")
            i = close + 1
        if i < end and toks[i].text == "(":
            close = match_close(toks, i)
            direction = None
            for part in split_top(toks[i + 1:close]):
                if not part:
                    continue
                if part[0].text in ("input", "output", "inout"):
                    direction = part[0].text
                nm, d = None, 0
                for t in reversed(part):
                    if t.text == "]":
                        d += 1
                    elif t.text == "[":
                        d -= 1
                    elif d == 0 and t.kind == "id":
                        nm = t
                        break
                if nm is None:
                    continue
                self.ports[nm.text] = (direction, part[0].line, nm.line)
                if direction == "input":
                    self.inputs.add(nm.text)
                if not PORT_RE.match(nm.text):
                    self.add(src, nm.line, "N5", f"port {nm.text}")
                if (direction == "input" and (nm.text == "i_cfg" or nm.text.startswith("i_cfg_"))
                        and name not in (WRAP,)):
                    tags = src.comment_block_above(part[0].line) + [c for ln in range(part[0].line, nm.line + 1)
                                                                    for c in src.comments.get(ln, [])]
                    if not any(QUASI_TAG_RE.search(c) for c in tags):
                        self.add(src, nm.line, "K6", f"configuration input {nm.text} without CDC_QUASI_STATIC tag")
            i = close + 1
        if name in CELL_PORTS and set(self.ports) != CELL_PORTS[name]:
            self.add(src, toks[k].line, "K10", f"{name} ports {sorted(self.ports)} != {sorted(CELL_PORTS[name])}")
        if name not in N11_EXEMPT:
            # Clock inputs and active-low reset inputs of a block; generated resets (outputs) and the
            # PPI reset request phy_core_rst (HAS name, feeds the reset synchronizers) are not covered.
            for p in self.inputs:
                if p.endswith("_clk") and not BLOCK_CLK_RE.match(p):
                    self.add(src, self.ports[p][2], "N11", f"clock input {p}")
                if re.search(r"_rst_n$|_reset_n$", p) and not BLOCK_RST_RE.match(p):
                    self.add(src, self.ports[p][2], "N11", f"reset input {p}")
        self.module = name
        self.decls, self.ff_written, self.comb_written, self.assign_groups = {}, set(), set(), []
        self.has_rst_sync = any(t.text == "m_ftel_dphy_rx_rst_sync" for t in toks[k:end])
        self.items(src, toks, i + 1, end, generate=False)
        for nm, line in self.decls.items():
            if nm.startswith("reg_") and nm not in self.ff_written:
                self.add(src, line, "N4", f"{nm} is not assigned in an always_ff")
        self.check_assign_groups(src)

    def items(self, src, toks, i, end, generate):
        while i < end:
            t = toks[i]
            x = t.text
            if x in ("generate", "endgenerate", ";"):
                i += 1
            elif x in ("always_ff", "always_comb", "always", "always_latch", "initial", "final"):
                i = self.always(src, toks, i)
            elif x == "assign":
                i = self.assign(src, toks, i)
            elif x in ("localparam", "parameter"):
                i = self.param_stmt(src, toks, i, body=True)
            elif x == "typedef":
                i = self.typedef(src, toks, i)
            elif x in ("import", "genvar", "defparam"):
                i = skip_to(toks, i, ";") + 1
            elif x == "function":
                i = skip_to(toks, i, "endfunction") + 1
            elif x == "task":
                i = skip_to(toks, i, "endtask") + 1
            elif x in ("property", "sequence"):
                i = skip_to(toks, i, "end" + x) + 1
            elif x == "for":
                close = match_close(toks, i + 1)
                i = self.gen_block(src, toks, close + 1, t.line, end)
            elif x == "if":
                close = match_close(toks, i + 1)
                i = self.gen_block(src, toks, close + 1, t.line, end)
                while i < end and toks[i].text == "else":
                    if toks[i + 1].text == "if":
                        close = match_close(toks, i + 2)
                        i = self.gen_block(src, toks, close + 1, toks[i].line, end)
                    else:
                        i = self.gen_block(src, toks, i + 1, toks[i].line, end)
            elif x == "begin":
                i = self.gen_block(src, toks, i, t.line, end)
            elif x in ("assert", "assume", "cover"):
                self.add(src, t.line, "N13", f"{x} without an a_<name> label")
                i = skip_to(toks, i, ";") + 1
            elif t.kind == "id" and i + 1 < end and toks[i + 1].text == ":":
                if toks[i + 2].text in ("assert", "assume", "cover"):
                    if not re.match(r"^a_[a-z0-9_]+$", x):
                        self.add(src, t.line, "N13", f"assertion label {x}")
                    i = skip_to(toks, i, ";") + 1
                else:
                    i += 2
            elif t.kind == "id":
                i = self.decl_or_instance(src, toks, i, end)
            else:
                i += 1
        return i

    def gen_block(self, src, toks, i, line, end):
        if i < end and toks[i].text == "begin":
            e = match_end(toks, i)
            if toks[i + 1].text == ":":
                if not re.match(r"^g_[a-z0-9_]+$", toks[i + 2].text):
                    self.add(src, toks[i + 2].line, "N13", f"generate label {toks[i + 2].text}")
                start = i + 3
            else:
                self.add(src, line, "N13", "generate block without a g_<name> label")
                start = i + 1
            self.items(src, toks, start, e, generate=True)
            j = e + 1
            if j < end and toks[j].text == ":":
                j += 2
            return j
        self.add(src, line, "N13", "generate block without begin : g_<name>")
        return self.items_one(src, toks, i, end)

    def items_one(self, src, toks, i, end):
        semi = skip_to(toks, i, ";")
        self.items(src, toks, i, min(semi + 1, end), generate=True)
        return semi + 1

    def always(self, src, toks, i):
        kw, line = toks[i].text, toks[i].line
        j = i + 1
        sens = None
        if j < len(toks) and toks[j].text == "@":
            if toks[j + 1].text == "(":
                close = match_close(toks, j + 1)
                sens = toks[j + 2:close]
                j = close + 1
            else:
                j += 2
        if kw == "always_ff":
            self.check_sens(src, line, sens)
        label = None
        if j < len(toks) and toks[j].text == "begin":
            e = match_end(toks, j)
            if toks[j + 1].text == ":":
                label = toks[j + 2].text
                body = [toks[j]] + toks[j + 3:e + 1]  # the label is not part of the first statement
            else:
                body = toks[j:e + 1]
            nxt = e + 1
            if nxt < len(toks) and toks[nxt].text == ":":
                nxt += 2
        else:
            e = skip_to(toks, j, ";")
            body = toks[j:e + 1]
            nxt = e + 1
        if kw in ("always_ff", "always_comb"):
            if label is None:
                self.add(src, line, "R8", f"{kw} without 'begin : p_<name>'")
            elif not re.match(r"^p_[a-z0-9_]+$", label):
                self.add(src, line, "N13", f"always label {label}")
            if not any(TRACE_RE.search(c) for c in src.comment_block_above(line)):
                self.add(src, line, "T2", f"{kw} {label or ''} without a REQ / D-n tag")
        if kw == "always_ff":
            for lhs, _ in assignments(body, {"<="}):
                for nm in lhs_names(lhs):
                    self.ff_written.add(nm.text)
                    if not nm.text.startswith("reg_"):
                        self.add(src, nm.line, "N4", f"{nm.text} assigned in always_ff")
        elif kw == "always_comb":
            for lhs, _ in assignments(body, ASSIGN_OPS):
                for nm in lhs_names(lhs):
                    self.comb_written.add(nm.text)
                    if not (nm.text.startswith("w_") or nm.text.startswith("o_")):
                        self.add(src, nm.line, "N10", f"{nm.text} assigned in always_comb (w_ / o_)")
        return nxt

    def check_sens(self, src, line, sens):
        if not sens:
            self.add(src, line, "R1", "always_ff without an edge list")
            return
        terms, cur = [], []
        for t in sens:
            if t.text in ("or", ","):
                terms.append(cur)
                cur = []
            else:
                cur.append(t)
        terms.append(cur)
        ok = (1 <= len(terms) <= 2 and len(terms[0]) == 2 and terms[0][0].text == "posedge"
              and (len(terms) == 1 or (len(terms[1]) == 2 and terms[1][0].text == "negedge")))
        if not ok:
            self.add(src, line, "R1", "edge list is not 'posedge <clk> [or negedge <rst>]'")
        for n, term in enumerate(terms):
            if term and term[0].text == "negedge" and n != 1:
                self.add(src, line, "P12", "negedge on a clock")
        if ok and self.profile == "ip" and getattr(self, "module", None) not in N11_EXEMPT:
            clk = terms[0][1].text
            if not (BLOCK_CLK_RE.match(clk) and clk in self.inputs):
                self.add(src, line, "N11", f"clock {clk} is not an input i_<core|byte|cfg>_clk")
            if len(terms) == 2:
                rst = terms[1][1].text
                if not ((BLOCK_RST_RE.match(rst) and rst in self.inputs) or
                        (LOCAL_RST_RE.match(rst) and self.has_rst_sync)):
                    self.add(src, line, "N11", f"reset {rst} is not an input i_<d>_rst_n "
                                               f"(or w_<d>_rst_n from a reset synchronizer of this module)")

    def assign(self, src, toks, i):
        semi = skip_to(toks, i, ";")
        stmt = toks[i + 1:semi]
        eq = next((q for q, t in enumerate(stmt) if t.text == "="), None)
        if eq is not None:
            for nm in lhs_names(stmt[:eq]):
                if not (nm.text.startswith("w_") or nm.text.startswith("o_")):
                    self.add(src, nm.line, "N10", f"{nm.text} driven by assign (w_ / o_)")
        self.assign_groups.append((toks[i].line, toks[semi].line if semi < len(toks) else toks[i].line))
        return semi + 1

    def check_assign_groups(self, src):
        groups = []
        for a, b in sorted(self.assign_groups):
            if groups and a == groups[-1][1] + 1:
                groups[-1][1] = b
            else:
                groups.append([a, b])
        for a, b in groups:
            tags = src.comment_block_above(a) + [c for ln in range(a, b + 1) for c in src.comments.get(ln, [])]
            if not any(TRACE_RE.search(c) for c in tags):
                self.add(src, a, "T2", f"assign group at lines {a}-{b} without a REQ / D-n tag")

    def decl_or_instance(self, src, toks, i, end):
        t0 = toks[i]
        x = t0.text
        nxt = toks[i + 1] if i + 1 < end else None
        # instance: <type> [#(...)] <name> ( ... ) ;
        if nxt is not None and (nxt.text == "#" or (nxt.kind == "id" and i + 2 < end and toks[i + 2].text == "(")) \
                and x not in KEYWORDS:
            j = i + 1
            if nxt.text == "#":
                close = match_close(toks, j + 1)
                for part in split_top(toks[j + 2:close]):
                    if part and part[0].text != ".":
                        self.add(src, part[0].line, "F6", f"positional parameter override in instance of {x}")
                j = close + 1
            inst = toks[j]
            if not INST_RE.match(inst.text):
                self.add(src, inst.line, "N6", f"instance name {inst.text}")
            close = match_close(toks, j + 1)
            parts = split_top(toks[j + 2:close])
            for part in parts:
                if not part:
                    continue
                if part[0].text == "." and len(part) > 1 and part[1].text == "*":
                    self.add(src, part[0].line, "F6", f".* in instance {inst.text}")
                elif part[0].text != ".":
                    self.add(src, part[0].line, "F6", f"positional connection in instance {inst.text}")
            tags = src.comment_block_above(t0.line)
            if x in CELL_PORTS and not any(CDC_TAG_RE.search(c) for c in tags):
                self.add(src, t0.line, "K5", f"instance {inst.text} of {x} without a CDC_CROSSING tag")
            if not any(TRACE_RE.search(c) for c in tags):
                self.add(src, t0.line, "T2", f"instance {inst.text} without a REQ / D-n / CDC tag")
            return skip_to(toks, close, ";") + 1
        # declaration: <type> [::type] [signed] [dims] name [dims] [= ...] {, name ...} ;
        semi = skip_to(toks, i, ";")
        j = i
        if j + 2 < semi and toks[j + 1].text == "::":
            j += 2
        j += 1
        while j < semi and toks[j].text in ("signed", "unsigned"):
            j += 1
        while j < semi and toks[j].text == "[":
            j = match_close(toks, j, "[", "]") + 1
        for part in split_top(toks[j:semi]):
            if not part or part[0].kind != "id":
                continue
            nm = part[0]
            if x in ("int", "bit", "byte", "shortint", "longint", "integer"):
                self.add(src, nm.line, "R7", f"{x} signal {nm.text} (use logic)")
            if nm.text in self.ports:
                continue
            self.decls[nm.text] = nm.line
            if not SIGNAL_RE.match(nm.text):
                self.add(src, nm.line, "N10", f"internal signal {nm.text} (reg_ / w_, lower case)")
        return semi + 1


def load_req_ids(structured):
    if not structured or not os.path.exists(structured):
        return None
    d = json.load(open(structured, encoding="utf-8"))
    return {r["req_id"] for r in d.get("requirements", [])}


def load_open_ids(spec):
    ids = set()
    if not spec or not os.path.exists(spec):
        return ids
    lines = open(spec, encoding="utf-8").read().splitlines()
    start = next((n for n, l in enumerate(lines) if l.startswith("**Table 9-1")), None)
    if start is None:
        return ids
    for l in lines[start + 1:]:
        if l.startswith("|"):
            cell = l.split("|")[1].strip()
            if cell in ("ID",) or set(cell) <= set("-: "):
                continue
            ids.update(x.strip() for x in cell.split("/"))
        elif ids:
            break
    return ids


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(".sv"))
        else:
            files.append(p)
    return files


def run(paths, profile="ip", structured=None, spec=None):
    req_ids = load_req_ids(structured) if profile == "ip" else None
    open_ids = load_open_ids(spec) if profile == "ip" else set()
    ck = Checker(profile, req_ids, open_ids)
    files = collect(paths)
    for f in files:
        ck.header = {}
        ck.check_file(f)
    return ck.v, files


def report(v, files, profile):
    for x in sorted(v, key=lambda x: (x["file"], x["line"], x["rule"])):
        print(f"{os.path.relpath(x['file'])}:{x['line']}: {x['rule']} {x['msg']}")
    c = Counter(x["rule"] for x in v)
    print(f"check_rtl_rules ({profile}): {len(files)} file(s), {len(v)} violation(s)"
          + (": " + ", ".join(f"{k} {n}" for k, n in sorted(c.items())) if c else ""))


# ---------------------------------------------------------------------- negative selftest
HEADER = """//------------------------------------------------------------------------------
// Copyright (c) 2026 FPT Telecom. All rights reserved.
//
// This RTL source code and the associated design are the proprietary
// and confidential information of FPT Telecom.
// Any unauthorized use, reproduction, or disclosure is strictly prohibited.
//------------------------------------------------------------------------------
// Author          : selftest
// Email           : selftest
// Created Date    : 2026-10-03
// Module          : {unit}
// Description     : Selftest fixture of check_rtl_rules.py.
// Parent          : none
// HAS             : draft v0.11, §4.1
// Clock domains   : {dom}
// REQ-IDs         : {reqs}
// OPEN            : {open}
//
// Evolution History:
// -----------------------------------------------------------------------------
// Date         Version    Author        Description
// 2026-10-03   0.1        selftest      Fixture.
//------------------------------------------------------------------------------
"""

FIX_PKG = """`timescale 1ns/1ps
`default_nettype none
package ftel_dphy_rx_demo_pkg;
  // {R1}
  localparam int C_DEMO_W = 4;
  // {RO}
  // OPEN {OID} {RO}: 16
  localparam int C_DEMO_LIMIT = 16;
  // {R1}
  typedef enum logic [1:0] { DEMO_IDLE, DEMO_RUN } demo_state_t;
  // {R1}
  typedef struct packed {
    logic [3:0] demo_limit;
    logic       demo_en;
  } demo_cfg_t;
endpackage
`default_nettype wire
"""

FIX_SYNC = """`timescale 1ns/1ps
`default_nettype none
module m_ftel_dphy_rx_sync #(
  parameter int PARA_LEVELS = 2
) (
  input  logic i_clk,
  input  logic i_rstn,
  input  logic i_data_in,
  output logic o_data_out
);
  logic [PARA_LEVELS-1:0] reg_sync;

  // {R1}
  always_ff @(posedge i_clk or negedge i_rstn) begin : p_sync
    if (!i_rstn) begin
      reg_sync <= '0;
    end else begin
      reg_sync <= {reg_sync[PARA_LEVELS-2:0], i_data_in};
    end
  end

  // {R1}
  assign o_data_out = reg_sync[PARA_LEVELS-1];
endmodule
`default_nettype wire
"""

FIX_DEMO = """`timescale 1ns/1ps
`default_nettype none
module m_ftel_dphy_rx_demo
  import ftel_dphy_rx_demo_pkg::*;
#(
  parameter int PARA_DEMO_W = C_DEMO_W
) (
  // ---- clock / reset ----
  input  logic                   i_core_clk,
  input  logic                   i_core_rst_n,
  // ---- control ----
  input  logic                   i_async_req,
  // ---- status ----
  output logic                   o_done,
  // ---- configuration ----
  // CDC_QUASI_STATIC: demo_limit (HAS §4.1)
  input  logic [PARA_DEMO_W-1:0] i_cfg_demo_limit
);
  localparam int C_ONE = 1;

  demo_state_t            reg_state;
  logic [PARA_DEMO_W-1:0] reg_cnt;
  logic                   w_req;
  logic                   w_cnt_done;
  demo_state_t            w_state_nxt;

  // {R1}
  assign w_cnt_done = (reg_cnt == i_cfg_demo_limit);

  // {R1}
  always_comb begin : p_state_nxt
    w_state_nxt = reg_state;
    case (reg_state)
      DEMO_IDLE: if (w_req) w_state_nxt = DEMO_RUN;
      DEMO_RUN:  if (w_cnt_done) w_state_nxt = DEMO_IDLE;
      default:   w_state_nxt = DEMO_IDLE;
    endcase
  end

  // {R1}
  always_ff @(posedge i_core_clk or negedge i_core_rst_n) begin : p_state_reg
    if (!i_core_rst_n) begin
      reg_state <= DEMO_IDLE;
      reg_cnt   <= '0;
    end else begin
      reg_state <= w_state_nxt;
      reg_cnt   <= (reg_state == DEMO_RUN) ? reg_cnt + PARA_DEMO_W'(C_ONE) : '0;
    end
  end

  // CDC_CROSSING: async -> core: i_async_req (HAS §4.1, Table 4-2)
  m_ftel_dphy_rx_sync #(
    .PARA_LEVELS (2)
  ) u_sync_0 (
    .i_clk      (i_core_clk),
    .i_rstn     (i_core_rst_n),
    .i_data_in  (i_async_req),
    .o_data_out (w_req)
  );

  // {R2}
  assign o_done = w_cnt_done;

`ifndef SYNTHESIS
  // {R2}
  a_done_in_run : assert property (@(posedge i_core_clk) disable iff (!i_core_rst_n)
                                   o_done |-> reg_state == DEMO_RUN);
`endif
endmodule
`default_nettype wire
"""

# Pre-registered negative tests: (name, file, old text, new text, rule that must be reported).
NEGATIVE = [
    ("N1 module without m_", "demo", "module m_ftel_dphy_rx_demo", "module ftel_dphy_rx_demo", "N1"),
    ("N2 parameter without PARA_", "demo", "PARA_DEMO_W", "DEMO_W", "N2"),
    ("N3 define without DEF_", "demo", "`default_nettype none\n", "`default_nettype none\n`define DEMO_X 1\n", "N3"),
    ("N4 flop without reg_", "demo", "reg_cnt", "cnt_q", "N4"),
    ("N5 port without i_/o_", "demo", "o_done", "done_o", "N5"),
    ("N6 instance without _<n>", "demo", "u_sync_0", "u_sync", "N6"),
    ("N7 enum member lower case", "pkg", "DEMO_IDLE, DEMO_RUN }", "DEMO_IDLE, DEMO_RUN, demo_halt }", "N7"),
    ("N7 struct member upper case", "pkg", "logic       demo_en;", "logic       DEMO_EN;", "N7"),
    ("N9 localparam without C_", "demo", "C_ONE", "ONE", "N9"),
    ("N10 net without w_", "demo", "w_req", "req_s", "N10"),
    ("N10 assign to a reg_", "demo", "assign w_cnt_done", "assign reg_cnt_done", "N10"),
    ("N11 block clock not i_<domain>_clk", "demo", "i_core_clk", "i_clk", "N11"),
    ("N12 type without _t", "pkg", "} demo_state_t;", "} demo_state;", "N12"),
    ("N12 package name", "pkg", "package ftel_dphy_rx_demo_pkg;", "package dphy_demo_pkg;", "N12"),
    ("N13 always label without p_", "demo", "p_state_reg", "state_reg", "N13"),
    ("N13 assertion label without a_", "demo", "a_done_in_run", "done_in_run", "N13"),
    ("F1 two units in one file", "demo", "endmodule\n", "endmodule\nmodule m_ftel_dphy_rx_extra;\nendmodule\n", "F1"),
    ("F2 `default_nettype none missing", "demo", "`default_nettype none\n", "", "F2"),
    ("F2 `default_nettype wire missing at the end", "demo", "endmodule\n`default_nettype wire\n", "endmodule\n", "F2"),
    ("F3 header field REQ-IDs missing", "demo", "// REQ-IDs         :", "// REQ-LIST        :", "F3"),
    ("F6 positional connection", "demo", ".i_clk      (i_core_clk),\n    .i_rstn     (i_core_rst_n),\n"
     "    .i_data_in  (i_async_req),\n    .o_data_out (w_req)", "i_core_clk, i_core_rst_n, i_async_req, w_req", "F6"),
    ("F6 .* connection", "demo", ".i_clk      (i_core_clk),", ".*,", "F6"),
    ("F6 positional parameter override", "demo", ".PARA_LEVELS (2)", "2", "F6"),
    ("R1 second edge not negedge", "demo", "or negedge i_core_rst_n) begin : p_state_reg",
     "or posedge i_core_rst_n) begin : p_state_reg", "R1"),
    ("R7 wire", "demo", "logic                   w_req;", "wire                    w_req;", "R7"),
    ("R7 int signal", "demo", "logic                   w_req;", "int                     w_req;", "R7"),
    ("R8 always_comb without label", "demo", "begin : p_state_nxt", "begin", "R8"),
    ("P1 #delay", "demo", "reg_state <= w_state_nxt;", "reg_state <= #1 w_state_nxt;", "P1"),
    ("P2 initial", "demo", "  // {R2}\n  assign o_done", "  initial reg_cnt = '0;\n  // {R2}\n  assign o_done", "P2"),
    ("P3 casez", "demo", "case (reg_state)", "casez (reg_state)", "P3"),
    ("P4 defparam", "demo", "  // {R2}\n  assign o_done", "  defparam u_sync_0.PARA_LEVELS = 3;\n  // {R2}\n  assign o_done", "P4"),
    ("P5 `default_nettype none missing", "demo", "`default_nettype none\n", "", "P5"),
    ("R2 combinational always @(*)", "demo", "always_comb begin : p_state_nxt", "always @(*) begin : p_state_nxt", "R2"),
    ("P6 always @*", "demo", "always_comb begin : p_state_nxt", "always @* begin : p_state_nxt", "P6"),
    ("P10 $display", "demo", "w_state_nxt = reg_state;", "w_state_nxt = reg_state;\n    $display(\"x\");", "P10"),
    ("P11 inout", "demo", "input  logic                   i_async_req,", "inout  logic                   i_async_req,", "P11"),
    ("P12 negedge clock", "demo", "always_ff @(posedge i_core_clk or negedge i_core_rst_n)",
     "always_ff @(negedge i_core_clk or negedge i_core_rst_n)", "P12"),
    ("K5 sync cell without CDC_CROSSING", "demo", "  // CDC_CROSSING: async -> core: i_async_req (HAS §4.1, Table 4-2)\n",
     "  // REQ-TAG {R1}\n", "K5"),
    ("K6 configuration input without CDC_QUASI_STATIC", "demo", "  // CDC_QUASI_STATIC: demo_limit (HAS §4.1)\n", "", "K6"),
    ("K7 CDC_GATING outside the PPI stage", "demo", "  // {R2}\n  assign o_done", "  // {R2} CDC_GATING (HAS §4.9)\n  assign o_done", "K7"),
    ("K10 sync cell port renamed", "sync", "i_rstn", "i_rst_n", "K10"),
    ("T1 header REQ-IDs misses a tagged REQ", "demo", "// REQ-IDs         : {R1}, {R2}", "// REQ-IDs         : {R1}", "T1"),
    ("T2 always_comb without tag", "demo", "  // {R1}\n  always_comb", "  always_comb", "T2"),
    ("T2 instance without tag", "demo", "  // CDC_CROSSING: async -> core: i_async_req (HAS §4.1, Table 4-2)\n", "", "T2"),
    ("T3 OPEN id not in Table 9-1", "pkg", "// OPEN {OID} {RO}: 16", "// OPEN K99 {RO}: 16", "T3"),
    ("T3 OPEN tag without default", "pkg", "// OPEN {OID} {RO}: 16", "// OPEN {OID} {RO}", "T3"),
    ("T6 REQ-ID not in structured_spec.json", "demo", "  // {R2}\n  assign o_done", "  // REQ-999\n  assign o_done", "T6"),
]


def selftest_negative(workdir):
    structured = os.path.join(IP_DIR, "req", "structured_spec.json")
    spec = os.path.join(IP_DIR, "doc", "spec.md")
    d = json.load(open(structured, encoding="utf-8"))
    reqs = d["requirements"]
    r1, r2 = reqs[0]["req_id"], reqs[1]["req_id"]
    ro = next(r for r in reqs if r.get("needs_human_decision") and r.get("open_item_ref"))
    oid = ro["open_item_ref"][0]
    sub = {"{R1}": r1, "{R2}": r2, "{RO}": ro["req_id"], "{OID}": oid}

    def fill(s):
        for k, v in sub.items():
            s = s.replace(k, v)
        return s

    base = {
        "pkg": ("ftel_dphy_rx_demo_pkg.sv", HEADER.format(unit="ftel_dphy_rx_demo_pkg", dom="none",
                reqs="{R1}, {RO}", open="{OID}") + FIX_PKG),
        "sync": ("m_ftel_dphy_rx_sync.sv", HEADER.format(unit="m_ftel_dphy_rx_sync", dom="any (one)",
                 reqs="{R1}", open="none") + FIX_SYNC),
        "demo": ("m_ftel_dphy_rx_demo.sv", HEADER.format(unit="m_ftel_dphy_rx_demo", dom="core",
                 reqs="{R1}, {R2}", open="none") + FIX_DEMO),
    }
    work = os.path.join(workdir, "check_rtl_rules_selftest")
    results = []

    def run_case(name, mutate, expect):
        shutil.rmtree(work, ignore_errors=True)
        os.makedirs(work)
        applied = mutate is None
        for key, (fname, text) in base.items():
            if mutate and mutate[0] == key:
                applied = mutate[1] in text
                text = text.replace(mutate[1], mutate[2])
            open(os.path.join(work, fname), "w", encoding="utf-8").write(fill(text))
        v, _ = run([work], "ip", structured, spec)
        rules = sorted({x["rule"] for x in v})
        if expect is None:
            ok = not v
            detail = "clean" if ok else "; ".join(f"{x['rule']}:{x['line']} {x['msg']}" for x in v[:6])
        else:
            ok = applied and expect in rules
            detail = ("mutation not applied" if not applied else f"reported {rules}")
        results.append((name, ok, detail))

    run_case("baseline fixture is clean", None, None)
    for name, key, old, new, rule in NEGATIVE:
        run_case(name, (key, old, new), rule)
    documented = set(re.findall(r"^\| (\w+) \[M\]", open(RULE_DOC, encoding="utf-8").read(), re.M))
    covered = {rule for _, _, _, _, rule in NEGATIVE}
    results.append(("[M] rules of rtl_rule.md = rules implemented", documented == set(RULES),
                    f"doc only {sorted(documented - set(RULES))}, code only {sorted(set(RULES) - documented)}"))
    results.append(("every rule has a negative test", covered == set(RULES),
                    f"untested {sorted(set(RULES) - covered)}"))
    print("NEGATIVE SELFTEST (check_rtl_rules)")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}   ({detail})")
    allok = all(ok for _, ok, _ in results)
    print("RESULT:", f"{sum(ok for _, ok, _ in results)}/{len(results)}", "PASS" if allok else "FAIL")
    shutil.rmtree(work, ignore_errors=True)
    return 0 if allok else 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--profile", choices=["ip", "construct"], default="ip")
    ap.add_argument("--structured", default=os.path.join(IP_DIR, "req", "structured_spec.json"))
    ap.add_argument("--spec", default=os.path.join(IP_DIR, "doc", "spec.md"))
    ap.add_argument("--json", help="write the violations as JSON")
    ap.add_argument("--selftest-negative", action="store_true")
    ap.add_argument("--workdir")
    a = ap.parse_args()
    if a.selftest_negative:
        if not a.workdir:
            ap.error("--selftest-negative needs --workdir")
        sys.exit(selftest_negative(a.workdir))
    if not a.paths:
        ap.error("give RTL files or directories")
    v, files = run(a.paths, a.profile, a.structured, a.spec)
    report(v, files, a.profile)
    if a.json:
        json.dump({"profile": a.profile, "files": files, "violations": v}, open(a.json, "w", encoding="utf-8"), indent=1)
    sys.exit(1 if v else 0)


if __name__ == "__main__":
    main()
