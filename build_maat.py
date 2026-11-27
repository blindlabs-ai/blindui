#!/usr/bin/env python3
"""
Pure-Python deterministic minifier and integrity verifier for Maat (formerly BlindUI).

Zero external dependencies (Python 3 stdlib only; optional `node --check` gate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

MAX_BUNDLE_BYTES = 28672
MAX_KIT_BYTES = 16384
MAX_TOKENS_BYTES = 4096
MAX_LINT_BYTES = 8192

# Constructed dynamically so this file itself never contains raw sink literals.
_FORBIDDEN_SUBSTRINGS: Tuple[Tuple[str, str], ...] = (
    ("sink_inner_html", "inner" + "HTML"),
    ("sink_outer_html", "outer" + "HTML"),
    ("sink_insert_adj_html", "insertAdjacent" + "HTML"),
    ("sink_doc_write", "document." + "write"),
    ("sink_eval_call", "ev" + "al("),
    ("sink_new_func", "new " + "Function"),
    ("sink_inline_onclick", "on" + "click="),
    ("script_close_tag", "</" + "script"),
)
_FORBIDDEN_CLAMP_RE = re.compile(r"\." + "cl" + r"amp\s*\(")

_REGEX_PREV_KEYWORDS = frozenset({
    "return", "throw", "case", "typeof", "void", "delete",
    "in", "of", "else", "do", "new", "yield", "await",
})

_REGEX_PREV_PUNCT = frozenset({
    "(", "[", "{", ",", ";", ":", "=", "!", "&", "|", "?",
    "+", "-", "*", "%", "^", "~", "<", ">",
    "==", "!=", "===", "!==", "<=", ">=", "&&", "||", "??",
    "=>", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "<<", ">>", ">>>", "<<=", ">>=", ">>>=", "**", "**=",
})

_ASI_FORCE_PREV = frozenset({"return", "throw", "break", "continue", "++", "--"})
_STMT_END_KINDS = frozenset({"ident", "num", "str", "tmpl", "regex"})
_STMT_END_VALS = frozenset({")", "]", "}", "++", "--"})
_STMT_START_KINDS = frozenset({"ident", "num", "str", "tmpl", "regex"})
_STMT_START_VALS = frozenset({"(", "[", "{", "+", "-", "!", "~", "++", "--"})

_MULTI_OPS = (
    ">>>=", "===", "!==", ">>>", "<<=", ">>=", "**=",
    "&&=", "||=", "??=", "==", "!=", "<=", ">=", "&&", "||",
    "??", "=>", "++", "--", "+=", "-=", "*=", "/=", "%=",
    "&=", "|=", "^=", "<<", ">>", "**", "...", "?.",
)

_JS_RESERVED = frozenset({
    "abstract", "arguments", "async", "await", "boolean", "break", "byte",
    "case", "catch", "char", "class", "const", "continue", "debugger",
    "default", "delete", "do", "double", "else", "enum", "eval", "export",
    "extends", "false", "final", "finally", "float", "for", "from", "function",
    "get", "goto", "if", "implements", "import", "in", "instanceof", "int",
    "interface", "let", "long", "native", "new", "null", "of", "package",
    "private", "protected", "public", "return", "set", "short", "static",
    "super", "switch", "synchronized", "this", "throw", "throws", "transient",
    "true", "try", "typeof", "undefined", "var", "void", "volatile", "while",
    "with", "yield",
    # Common JS/DOM globals never mangled
    "Array", "Boolean", "Date", "Error", "Function", "Infinity", "JSON",
    "Map", "Math", "NaN", "Number", "Object", "Promise", "RegExp", "Set",
    "String", "Symbol", "TypeError", "WeakMap", "WeakSet", "console",
    "decodeURIComponent", "document", "encodeURIComponent", "fetch",
    "globalThis", "isFinite", "isNaN", "module", "parseFloat", "parseInt",
    "window",
})

_MANGLE_HEAD = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$"
_MANGLE_TAIL = _MANGLE_HEAD + "0123456789"


def _gen_short_names(avoid: set[str]):
    for c in _MANGLE_HEAD:
        if c not in avoid:
            yield c
    for c1 in _MANGLE_HEAD:
        for c2 in _MANGLE_TAIL:
            name = c1 + c2
            if name not in avoid:
                yield name
    for c1 in _MANGLE_HEAD:
        for c2 in _MANGLE_TAIL:
            for c3 in _MANGLE_TAIL:
                name = c1 + c2 + c3
                if name not in avoid:
                    yield name


def _fold_string_concats(tokens: List[Tuple[str, str, bool]]) -> List[Tuple[str, str, bool]]:
    """Fold adjacent string literal concatenations (`"a" + "b"` -> `"ab"`)."""
    out: List[Tuple[str, str, bool]] = []
    i = 0
    n = len(tokens)
    while i < n:
        if (
            i + 2 < n
            and tokens[i][0] == "str"
            and tokens[i + 1][0] == "punct"
            and tokens[i + 1][1] == "+"
            and tokens[i + 2][0] == "str"
            and tokens[i][1][0] == tokens[i + 2][1][0]
        ):
            q = tokens[i][1][0]
            merged = tokens[i][1][:-1] + tokens[i + 2][1][1:]
            nl = tokens[i][2]
            i += 3
            while (
                i + 1 < n
                and tokens[i][0] == "punct"
                and tokens[i][1] == "+"
                and tokens[i + 1][0] == "str"
                and tokens[i + 1][1][0] == q
            ):
                merged = merged[:-1] + tokens[i + 1][1][1:]
                i += 2
            out.append(("str", merged, nl))
        else:
            out.append(tokens[i])
            i += 1
    return out


def _collect_binding_names(tokens: List[Tuple[str, str, bool]]) -> set[str]:
    """Collect lexically bound identifiers from const/let/var, function, catch, and arrow params."""
    bound: set[str] = set()
    n = len(tokens)

    def add_pattern(idx: int) -> int:
        if idx >= n:
            return idx
        k, v, _ = tokens[idx]
        if k == "punct" and v == "...":
            idx += 1
            if idx >= n:
                return idx
            k, v, _ = tokens[idx]
        if k == "ident":
            bound.add(v)
            return idx + 1
        if k == "punct" and v == "[":
            depth = 1
            idx += 1
            while idx < n and depth > 0:
                tk, tv, _ = tokens[idx]
                if tk == "punct" and tv == "[":
                    depth += 1
                elif tk == "punct" and tv == "]":
                    depth -= 1
                elif tk == "ident":
                    prev_v = tokens[idx - 1][1] if idx > 0 else ""
                    if prev_v in ("[", ",", "..."):
                        bound.add(tv)
                idx += 1
            return idx
        return idx

    def collect_param_list(open_paren_idx: int) -> int:
        depth = 1
        j = open_paren_idx + 1
        expect_param = True
        while j < n and depth > 0:
            tk, tv, _ = tokens[j]
            if tk == "punct" and tv in ("(", "[", "{"):
                if expect_param and depth == 1 and tv == "[":
                    j = add_pattern(j)
                    expect_param = False
                    continue
                depth += 1
            elif tk == "punct" and tv in (")", "]", "}"):
                depth -= 1
            elif depth == 1 and tk == "punct" and tv == ",":
                expect_param = True
            elif depth == 1 and tk == "punct" and tv == "=":
                expect_param = False
            elif depth == 1 and expect_param and (tk == "ident" or (tk == "punct" and tv == "...")):
                j = add_pattern(j)
                expect_param = False
                continue
            j += 1
        return j

    i = 0
    while i < n:
        k, v, _ = tokens[i]
        if k == "ident" and v == "function":
            j = i + 1
            if j < n and tokens[j][0] == "ident":
                bound.add(tokens[j][1])
                j += 1
            if j < n and tokens[j][0] == "punct" and tokens[j][1] == "(":
                collect_param_list(j)
            i += 1
            continue
        if k == "ident" and v == "catch":
            if i + 2 < n and tokens[i + 1][1] == "(" and tokens[i + 2][0] == "ident":
                bound.add(tokens[i + 2][1])
            i += 1
            continue
        if k == "ident" and v in ("const", "let", "var"):
            j = i + 1
            depth = 0
            expect_decl = True
            while j < n:
                tk, tv, had_nl = tokens[j]
                if depth == 0 and (
                    (tk == "punct" and tv in (";", ")"))
                    or (tk == "ident" and tv in ("of", "in"))
                    or (had_nl and not expect_decl and tk == "ident" and tv in ("const", "let", "var", "function", "if", "for", "while", "return"))
                ):
                    break
                if depth == 0 and expect_decl and (tk == "ident" or (tk == "punct" and tv == "[")):
                    j = add_pattern(j)
                    expect_decl = False
                    continue
                if tk == "punct" and tv in ("(", "[", "{"):
                    depth += 1
                elif tk == "punct" and tv in (")", "]", "}"):
                    if depth == 0:
                        break
                    depth -= 1
                elif depth == 0 and tk == "punct" and tv == ",":
                    expect_decl = True
                j += 1
            i += 1
            continue
        if k == "punct" and v == "=>":
            if i >= 1 and tokens[i - 1][0] == "ident":
                bound.add(tokens[i - 1][1])
            elif i >= 1 and tokens[i - 1][0] == "punct" and tokens[i - 1][1] == ")":
                depth = 1
                j = i - 2
                while j >= 0 and depth > 0:
                    if tokens[j][0] == "punct" and tokens[j][1] == ")":
                        depth += 1
                    elif tokens[j][0] == "punct" and tokens[j][1] == "(":
                        depth -= 1
                    j -= 1
                if depth == 0:
                    collect_param_list(j + 1)
        i += 1

    return bound - _JS_RESERVED


def _is_prop_or_key(tokens: List[Tuple[str, str, bool]], idx: int) -> bool:
    prev_v = tokens[idx - 1][1] if idx > 0 else ""
    next_v = tokens[idx + 1][1] if idx + 1 < len(tokens) else ""
    if prev_v in (".", "?."):
        return True
    if next_v == ":" and prev_v in ("{", ","):
        return True
    return False


def _mangle_tokens(tokens: List[Tuple[str, str, bool]]) -> List[Tuple[str, str, bool]]:
    """Deterministically mangle lexically bound identifiers while preserving all property names and globals."""
    bound = _collect_binding_names(tokens)
    if not bound:
        return tokens

    freq: dict[str, int] = {}
    free_names: set[str] = set(_JS_RESERVED)
    for idx, (k, v, _) in enumerate(tokens):
        if k != "ident":
            continue
        if _is_prop_or_key(tokens, idx):
            continue
        if v in bound:
            freq[v] = freq.get(v, 0) + 1
        else:
            free_names.add(v)

    ordered = sorted(freq.keys(), key=lambda name: (-freq[name], name))
    gen = _gen_short_names(free_names)
    rename = {name: next(gen) for name in ordered}

    out: List[Tuple[str, str, bool]] = []
    n = len(tokens)
    for idx, (k, v, nl) in enumerate(tokens):
        next_v = tokens[idx + 1][1] if idx + 1 < n else ""
        if k == "ident" and v in rename and not _is_prop_or_key(tokens, idx):
            out.append(("ident", rename[v], nl))
        elif k == "ident" and v == "const" and not _is_prop_or_key(tokens, idx):
            out.append(("ident", "let", nl))
        elif k == "ident" and v == "true" and next_v != "." and not _is_prop_or_key(tokens, idx):
            out.append(("punct", "!", nl))
            out.append(("num", "0", False))
        elif k == "ident" and v == "false" and next_v != "." and not _is_prop_or_key(tokens, idx):
            out.append(("punct", "!", nl))
            out.append(("num", "1", False))
        else:
            out.append((k, v, nl))
    return out


def _simplify_arrows(tokens: List[Tuple[str, str, bool]]) -> List[Tuple[str, str, bool]]:
    """Drop parentheses around single-identifier arrow parameters: (x)=> -> x=>."""
    out: List[Tuple[str, str, bool]] = []
    i = 0
    n = len(tokens)
    while i < n:
        if (
            i + 3 < n
            and tokens[i][0] == "punct"
            and tokens[i][1] == "("
            and tokens[i + 1][0] == "ident"
            and tokens[i + 2][0] == "punct"
            and tokens[i + 2][1] == ")"
            and tokens[i + 3][0] == "punct"
            and tokens[i + 3][1] == "=>"
        ):
            out.append(("ident", tokens[i + 1][1], tokens[i][2]))
            out.append(tokens[i + 3])
            i += 4
        else:
            out.append(tokens[i])
            i += 1
    return out


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_" or ch == "$"


def _is_ident_part(ch: str) -> bool:
    return ch.isalnum() or ch == "_" or ch == "$"


def _read_quoted_string(src: str, pos: int) -> Tuple[str, int]:
    quote = src[pos]
    n = len(src)
    i = pos + 1
    while i < n:
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return src[pos:i + 1], i + 1
        i += 1
    raise ValueError(f"Unterminated string literal at offset {pos}")


def _read_template_literal(src: str, pos: int) -> Tuple[str, int]:
    n = len(src)
    i = pos + 1
    while i < n:
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "`":
            return src[pos:i + 1], i + 1
        if ch == "$" and i + 1 < n and src[i + 1] == "{":
            i += 2
            brace_depth = 1
            prev_kind: Optional[str] = None
            prev_val: Optional[str] = None
            while i < n and brace_depth > 0:
                c2 = src[i]
                if c2.isspace():
                    i += 1
                    continue
                if c2 in ("'", '"'):
                    _, i = _read_quoted_string(src, i)
                    prev_kind, prev_val = "str", None
                elif c2 == "`":
                    _, i = _read_template_literal(src, i)
                    prev_kind, prev_val = "str", None
                elif c2 == "/" and i + 1 < n and src[i + 1] == "/":
                    nl = src.find("\n", i + 2)
                    i = n if nl == -1 else nl + 1
                elif c2 == "/" and i + 1 < n and src[i + 1] == "*":
                    end_c = src.find("*/", i + 2)
                    if end_c == -1:
                        raise ValueError("Unterminated block comment inside template")
                    i = end_c + 2
                elif c2 == "/" and _can_start_regex(prev_kind, prev_val):
                    _, i = _read_regex_literal(src, i)
                    prev_kind, prev_val = "regex", None
                elif c2 == "{":
                    brace_depth += 1
                    i += 1
                    prev_kind, prev_val = "punct", "{"
                elif c2 == "}":
                    brace_depth -= 1
                    i += 1
                    prev_kind, prev_val = "punct", "}"
                elif _is_ident_start(c2):
                    j = i + 1
                    while j < n and _is_ident_part(src[j]):
                        j += 1
                    prev_kind, prev_val = "ident", src[i:j]
                    i = j
                elif c2.isdigit():
                    j = i + 1
                    while j < n and (src[j].isalnum() or src[j] in "._"):
                        j += 1
                    prev_kind, prev_val = "num", src[i:j]
                    i = j
                elif c2 in ("+", "-") and i + 1 < n and src[i + 1] == c2:
                    prev_kind, prev_val = "punct", c2 + c2
                    i += 2
                else:
                    prev_kind, prev_val = "punct", c2
                    i += 1
            continue
        i += 1
    raise ValueError(f"Unterminated template literal at offset {pos}")


def _read_regex_literal(src: str, pos: int) -> Tuple[str, int]:
    n = len(src)
    i = pos + 1
    in_class = False
    while i < n:
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            in_class = True
            i += 1
            continue
        if ch == "]" and in_class:
            in_class = False
            i += 1
            continue
        if ch == "/" and not in_class:
            i += 1
            while i < n and src[i].isalpha():
                i += 1
            return src[pos:i], i
        if ch == "\n":
            raise ValueError(f"Unterminated regex literal at offset {pos}")
        i += 1
    raise ValueError(f"Unterminated regex literal at offset {pos}")


def _can_start_regex(prev_kind: Optional[str], prev_val: Optional[str]) -> bool:
    if prev_kind is None:
        return True
    if prev_kind == "ident":
        return prev_val in _REGEX_PREV_KEYWORDS
    if prev_kind == "punct":
        return prev_val in _REGEX_PREV_PUNCT
    return False


def tokenize_js(src: str) -> List[Tuple[str, str, bool]]:
    """
    Tokenize ES2020 JS into [(kind, text, preceded_by_newline), ...].
    Strips whitespace and comments while tracking newline boundaries for ASI.
    """
    tokens: List[Tuple[str, str, bool]] = []
    n = len(src)
    i = 0
    saw_nl = False
    prev_kind: Optional[str] = None
    prev_val: Optional[str] = None

    while i < n:
        ch = src[i]

        if ch in " \t\r\n\f\v":
            if ch == "\n":
                saw_nl = True
            i += 1
            continue

        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            nl = src.find("\n", i + 2)
            if nl == -1:
                break
            saw_nl = True
            i = nl + 1
            continue

        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            end_c = src.find("*/", i + 2)
            if end_c == -1:
                raise ValueError(f"Unterminated block comment at offset {i}")
            if "\n" in src[i + 2:end_c]:
                saw_nl = True
            i = end_c + 2
            continue

        if ch in ("'", '"'):
            tok, i = _read_quoted_string(src, i)
            tokens.append(("str", tok, saw_nl))
            prev_kind, prev_val, saw_nl = "str", tok, False
            continue

        if ch == "`":
            tok, i = _read_template_literal(src, i)
            tokens.append(("tmpl", tok, saw_nl))
            prev_kind, prev_val, saw_nl = "tmpl", tok, False
            continue

        if ch == "/" and _can_start_regex(prev_kind, prev_val):
            tok, i = _read_regex_literal(src, i)
            tokens.append(("regex", tok, saw_nl))
            prev_kind, prev_val, saw_nl = "regex", tok, False
            continue

        if _is_ident_start(ch):
            start = i
            i += 1
            while i < n and _is_ident_part(src[i]):
                i += 1
            tok = src[start:i]
            tokens.append(("ident", tok, saw_nl))
            prev_kind, prev_val, saw_nl = "ident", tok, False
            continue

        if ch.isdigit() or (ch == "." and i + 1 < n and src[i + 1].isdigit()):
            start = i
            if ch == "0" and i + 1 < n and src[i + 1] in "xXbBoO":
                i += 2
                while i < n and (src[i].isalnum() or src[i] == "_"):
                    i += 1
            else:
                while i < n and (src[i].isdigit() or src[i] == "_"):
                    i += 1
                if i < n and src[i] == ".":
                    i += 1
                    while i < n and (src[i].isdigit() or src[i] == "_"):
                        i += 1
                if i < n and src[i] in "eE":
                    i += 1
                    if i < n and src[i] in "+-":
                        i += 1
                    while i < n and (src[i].isdigit() or src[i] == "_"):
                        i += 1
            tok = src[start:i]
            tokens.append(("num", tok, saw_nl))
            prev_kind, prev_val, saw_nl = "num", tok, False
            continue

        matched_op = None
        for op in _MULTI_OPS:
            if src.startswith(op, i):
                matched_op = op
                break
        if matched_op is not None:
            tokens.append(("punct", matched_op, saw_nl))
            prev_kind, prev_val, saw_nl = "punct", matched_op, False
            i += len(matched_op)
            continue

        tokens.append(("punct", ch, saw_nl))
        prev_kind, prev_val, saw_nl = "punct", ch, False
        i += 1

    return tokens


def _needs_space(pk: str, pv: str, ck: str, cv: str) -> bool:
    if pk in ("ident", "num") and ck in ("ident", "num"):
        return True
    if pk == "ident" and ck == "regex":
        return True
    if pv[-1] == "+" and cv[0] == "+":
        return True
    if pv[-1] == "-" and cv[0] == "-":
        return True
    if pv[-1] == "/" and cv[0] in ("/", "*"):
        return True
    if pk == "num" and cv == ".":
        return True
    return False


def _needs_asi_newline(pk: str, pv: str, ck: str, cv: str, had_nl: bool) -> bool:
    if not had_nl or cv == "}":
        return False
    if pv in _ASI_FORCE_PREV:
        return True
    prev_can_end = pk in _STMT_END_KINDS or pv in _STMT_END_VALS
    curr_can_start = ck in _STMT_START_KINDS or cv in _STMT_START_VALS
    if prev_can_end and curr_can_start:
        if pv == "}" and cv in ("else", "catch", "finally", "while"):
            return False
        return True
    return False


def minify_js(src: str, mangle: bool = True) -> str:
    """Deterministically minify ES2020 source code preserving semantics and ASI safety."""
    tokens = _fold_string_concats(tokenize_js(src))
    if mangle:
        tokens = _mangle_tokens(tokens)
    tokens = _simplify_arrows(tokens)
    out: List[str] = []
    pk: Optional[str] = None
    pv: Optional[str] = None
    paren_is_ctrl: List[bool] = []
    brace_is_block: List[bool] = []
    last_close_was_ctrl = False
    last_brace_was_block = False
    n = len(tokens)

    for idx, (ck, cv, had_nl) in enumerate(tokens):
        if (
            ck == "punct"
            and cv == ";"
            and idx + 1 < n
            and tokens[idx + 1][0] == "punct"
            and tokens[idx + 1][1] == "}"
            and pv not in ("else", "do", None)
            and not (pv == ")" and last_close_was_ctrl)
        ):
            continue
        if pk is not None and pv is not None:
            if not (pv == "}" and last_brace_was_block) and _needs_asi_newline(pk, pv, ck, cv, had_nl):
                out.append("\n")
            elif _needs_space(pk, pv, ck, cv):
                out.append(" ")
        if ck == "punct" and cv == "(":
            paren_is_ctrl.append(pk == "ident" and pv in ("if", "for", "while", "with", "switch", "catch"))
            last_close_was_ctrl = False
            last_brace_was_block = False
        elif ck == "punct" and cv == ")":
            last_close_was_ctrl = paren_is_ctrl.pop() if paren_is_ctrl else False
            last_brace_was_block = False
        elif ck == "punct" and cv == "{":
            is_blk = (
                (pv == ")" and last_close_was_ctrl)
                or (pk == "ident" and pv in ("else", "try", "finally", "do"))
                or (pk == "punct" and pv in (";", "{", "}"))
            )
            brace_is_block.append(is_blk)
            last_close_was_ctrl = False
            last_brace_was_block = False
        elif ck == "punct" and cv == "}":
            last_brace_was_block = brace_is_block.pop() if brace_is_block else False
            last_close_was_ctrl = False
        else:
            last_close_was_ctrl = False
            last_brace_was_block = False
        out.append(cv)
        pk, pv = ck, cv

    return "".join(out) + "\n"


def validate_bundle_text(
    text: str,
    label: str,
    enforce_size: bool = False,
    max_bytes: int = MAX_BUNDLE_BYTES,
    inclusive: bool = False,
) -> List[str]:
    """Validate ASCII, forbidden sinks, dot-clamp, and size budget."""
    errors: List[str] = []
    raw = text.encode("utf-8")
    non_ascii = sum(1 for b in raw if b > 0x7F)
    if non_ascii > 0:
        errors.append(f"{label}: found {non_ascii} non-ASCII byte(s)")
    if enforce_size:
        if inclusive and len(raw) > max_bytes:
            errors.append(f"{label}: {len(raw)} bytes > budget {max_bytes} bytes")
        elif not inclusive and len(raw) >= max_bytes:
            errors.append(f"{label}: {len(raw)} bytes >= budget {max_bytes} bytes")
    low = text.lower()
    for name, needle in _FORBIDDEN_SUBSTRINGS:
        if needle.lower() in low:
            errors.append(f"{label}: forbidden literal detected ({name})")
    if _FORBIDDEN_CLAMP_RE.search(text):
        errors.append(f"{label}: forbidden dot-clamp call detected")
    return errors


def validate_css_tokens(path: Path, max_bytes: int = MAX_TOKENS_BYTES) -> dict:
    """Validate blindui-tokens.css for ASCII, forbidden literals, balanced braces, and size cap."""
    errors: List[str] = []
    if not path.is_file():
        return {
            "ok": False,
            "path": str(path),
            "bytes": 0,
            "budget_bytes": max_bytes,
            "headroom_bytes": max_bytes,
            "sha256": "",
            "errors": [f"Tokens CSS not found: {path}"],
        }
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    errors.extend(
        validate_bundle_text(
            text,
            str(path.name),
            enforce_size=True,
            max_bytes=max_bytes,
            inclusive=True,
        )
    )
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                errors.append(f"{path.name}: unbalanced closing brace")
                break
    if depth > 0:
        errors.append(f"{path.name}: {depth} unclosed brace(s)")
    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "bytes": len(raw),
        "budget_bytes": max_bytes,
        "headroom_bytes": max_bytes - len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "errors": errors,
    }


def run_node_check(js_text: str, label: str, require_node: bool = False) -> List[str]:
    node_bin = shutil.which("node")
    if not node_bin:
        if require_node:
            return [f"{label}: node binary not found in PATH (--require-node set)"]
        return []
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="ascii", delete=False) as tf:
            tf.write(js_text)
            tmp_path = tf.name
        proc = subprocess.run(
            [node_bin, "--check", tmp_path],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[:300]
            return [f"{label}: node --check failed (rc={proc.returncode}): {detail}"]
        return []
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def build_and_verify(
    src_path: Path,
    out_path: Path,
    check_only: bool = False,
    sync_paths: Optional[List[Path]] = None,
    require_node: bool = False,
    max_bytes: int = MAX_BUNDLE_BYTES,
    inclusive: bool = False,
) -> dict:
    errors: List[str] = []
    if not src_path.is_file():
        return {"ok": False, "errors": [f"Source not found: {src_path}"]}

    src_text = src_path.read_text("utf-8")
    errors.extend(validate_bundle_text(src_text, str(src_path.name), enforce_size=False))
    errors.extend(run_node_check(src_text, str(src_path.name), require_node=require_node))

    min_1 = minify_js(src_text)
    min_2 = minify_js(src_text)
    if min_1 != min_2:
        errors.append("Minifier non-determinism detected across repeated runs")

    errors.extend(
        validate_bundle_text(
            min_1,
            str(out_path.name),
            enforce_size=True,
            max_bytes=max_bytes,
            inclusive=inclusive,
        )
    )
    errors.extend(run_node_check(min_1, str(out_path.name), require_node=require_node))

    min_bytes = min_1.encode("ascii", errors="replace")
    sha256_hex = hashlib.sha256(min_bytes).hexdigest()

    targets = [out_path] + list(sync_paths or [])
    if check_only:
        for tp in targets:
            if not tp.is_file():
                errors.append(f"--check failed: missing target {tp}")
            else:
                existing = tp.read_bytes()
                if existing != min_bytes:
                    errors.append(
                        f"--check failed: {tp} differs from deterministic build "
                        f"(existing={len(existing)}B vs built={len(min_bytes)}B)"
                    )
    elif not errors:
        for tp in targets:
            tp.parent.mkdir(parents=True, exist_ok=True)
            tp.write_bytes(min_bytes)

    return {
        "ok": len(errors) == 0,
        "src_bytes": len(src_text.encode("utf-8")),
        "min_bytes": len(min_bytes),
        "budget_bytes": max_bytes,
        "headroom_bytes": max_bytes - len(min_bytes),
        "sha256": sha256_hex,
        "check_only": check_only,
        "targets": [str(t) for t in targets],
        "errors": errors,
    }


def sync_exact_file(src_path: Path, dst_path: Path, check_only: bool = False) -> List[str]:
    if not src_path.is_file():
        return [f"Source not found: {src_path}"]
    src_bytes = src_path.read_bytes()
    if check_only:
        if not dst_path.is_file():
            return [f"--check failed: missing compatibility mirror {dst_path}"]
        if dst_path.read_bytes() != src_bytes:
            return [f"--check failed: {dst_path.name} differs from {src_path.name}"]
        return []
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(src_bytes)
    return []


def main(argv: Optional[List[str]] = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Deterministic pure-Python Maat minifier & verifier")
    parser.add_argument("--src", default=None, help="Path to readable JS source (default: build Maat + BlindUI mirrors)")
    parser.add_argument("--out", default=None, help="Output path for minified JS bundle")
    parser.add_argument("--max-bytes", type=int, default=None, help="Override size budget in bytes for single-target builds")
    parser.add_argument("--check", action="store_true", help="Verify existing bundle(s) match build byte-for-byte")
    parser.add_argument("--sync", nargs="*", default=[], help="Additional vendored maat.min.js/blindui.min.js paths to sync/check")
    parser.add_argument("--require-node", action="store_true", help="Fail if node binary is missing for --check")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args(argv)

    single_mode = args.src is not None or args.out is not None
    if single_mode:
        src_path = Path(args.src) if args.src else (here / "maat.js")
        out_path = Path(args.out) if args.out else (here / "maat.min.js")
        budget = args.max_bytes if args.max_bytes is not None else MAX_BUNDLE_BYTES
        inclusive = args.max_bytes is not None
        result = build_and_verify(
            src_path=src_path,
            out_path=out_path,
            check_only=args.check,
            sync_paths=[Path(p) for p in args.sync],
            require_node=args.require_node,
            max_bytes=budget,
            inclusive=inclusive,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["ok"]:
                op = "<=" if inclusive else "<"
                print(
                    f"OK: {out_path.name} {result['min_bytes']} bytes "
                    f"({op} {result['budget_bytes']}B, headroom {result['headroom_bytes']}B, "
                    f"sha256={result['sha256'][:16]})"
                )
            else:
                for err in result["errors"]:
                    print(f"FAIL: {err}", file=sys.stderr)
        return 0 if result["ok"] else 1

    mirror_errors: List[str] = []
    for src_name, dst_name in (
        ("maat.js", "blindui.js"),
        ("maat-kit.js", "blindui-kit.js"),
        ("maat-layout-lint.js", "blindui-layout-lint.js"),
        ("maat-tokens.css", "blindui-tokens.css"),
    ):
        mirror_errors.extend(sync_exact_file(here / src_name, here / dst_name, check_only=args.check))

    core_syncs = [here / "blindui.min.js"] + [Path(p) for p in args.sync]
    core_res = build_and_verify(
        src_path=here / "maat.js",
        out_path=here / "maat.min.js",
        check_only=args.check,
        sync_paths=core_syncs,
        require_node=args.require_node,
        max_bytes=MAX_BUNDLE_BYTES,
        inclusive=False,
    )
    kit_res = build_and_verify(
        src_path=here / "maat-kit.js",
        out_path=here / "maat-kit.min.js",
        check_only=args.check,
        sync_paths=[here / "blindui-kit.min.js"],
        require_node=args.require_node,
        max_bytes=MAX_KIT_BYTES,
        inclusive=True,
    )
    tokens_res = validate_css_tokens(here / "maat-tokens.css", max_bytes=MAX_TOKENS_BYTES)
    lint_res = build_and_verify(
        src_path=here / "maat-layout-lint.js",
        out_path=here / "maat-layout-lint.min.js",
        check_only=args.check,
        sync_paths=[here / "blindui-layout-lint.min.js"],
        require_node=args.require_node,
        max_bytes=MAX_LINT_BYTES,
        inclusive=True,
    )

    all_errors = (
        mirror_errors
        + list(core_res["errors"])
        + list(kit_res["errors"])
        + list(tokens_res["errors"])
        + list(lint_res["errors"])
    )
    combined = {
        "ok": len(all_errors) == 0,
        "core": core_res,
        "kit": kit_res,
        "tokens": tokens_res,
        "lint": lint_res,
        "errors": all_errors,
    }
    if args.json:
        print(json.dumps(combined, indent=2))
    else:
        if core_res["ok"]:
            print(
                f"OK: maat.min.js (+ blindui.min.js) {core_res['min_bytes']} bytes "
                f"(< {core_res['budget_bytes']}B, headroom {core_res['headroom_bytes']}B, "
                f"sha256={core_res['sha256'][:16]})"
            )
        if kit_res["ok"]:
            print(
                f"OK: maat-kit.min.js (+ blindui-kit.min.js) {kit_res['min_bytes']} bytes "
                f"(<= {kit_res['budget_bytes']}B, headroom {kit_res['headroom_bytes']}B, "
                f"sha256={kit_res['sha256'][:16]})"
            )
        if tokens_res["ok"]:
            print(
                f"OK: maat-tokens.css (+ blindui-tokens.css) {tokens_res['bytes']} bytes "
                f"(<= {tokens_res['budget_bytes']}B, headroom {tokens_res['headroom_bytes']}B, "
                f"sha256={tokens_res['sha256'][:16]})"
            )
        if lint_res["ok"]:
            print(
                f"OK: maat-layout-lint.min.js (+ blindui-layout-lint.min.js) {lint_res['min_bytes']} bytes "
                f"(<= {lint_res['budget_bytes']}B, headroom {lint_res['headroom_bytes']}B, "
                f"sha256={lint_res['sha256'][:16]})"
            )
        for err in all_errors:
            print(f"FAIL: {err}", file=sys.stderr)
    return 0 if combined["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
