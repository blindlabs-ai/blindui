#!/usr/bin/env python3
"""
BlindUI Static Validator (BUI-01 .. BUI-10) - Elysia-style JS-to-Server Parity & XSS/Hygiene Gate.

Zero external dependencies (Python 3 stdlib + sibling build_blindui.py only).
Never executes target server/UI Python modules; uses ast.parse() and HTMLParser exclusively.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import build_blindui  # noqa: E402

# Dynamically constructed needles so this file never carries raw forbidden sink literals.
_SINK_INNER_HTML = "inner" + "HTML"
_SINK_OUTER_HTML = "outer" + "HTML"
_SINK_INSERT_ADJ_HTML = "insertAdjacent" + "HTML"
_SINK_DOC_WRITE = "document." + "write"
_SINK_DOC_WRITELN = "document." + "writeln"
_SINK_EVAL_NAME = "ev" + "al"
_SINK_FUNC_CTOR = "Function"
_SCRIPT_CLOSE_TAG = "</" + "script>"
_SCRIPT_BLOCK_RE = re.compile(r"<script\b([^>]*)>([\s\S]*?)" + "</" + r"script>", re.IGNORECASE)
_CLAMP_RE = re.compile(r"\." + "cl" + r"amp\s*\(")

_CANONICAL_SSO_ROUTES: Set[Tuple[str, str]] = {
    ("POST", "/mail/api/v1/auth/register"),
    ("POST", "/mail/api/v1/auth/login"),
    ("POST", "/mail/api/v1/auth/salt"),
    ("GET", "/mail/api/v1/auth/salt"),
}

_JARGON_CASE_SENSITIVE = frozenset({"JWK", "ECDSA", "P-256", "WebCrypto", "AES-GCM/AES-256"})

JARGON_PATTERNS: List[Tuple[str, str]] = [
    ("WebCrypto", r"\bWebCrypto\b"),
    ("P-256", r"\bP-256\b"),
    ("ECDSA", r"\bECDSA\b"),
    ("ECDH/ecdh_", r"\bECDH\b|ecdh_"),
    ("Self-sovereign", r"Self-sovereign|self-sovereign"),
    ("AES-GCM/AES-256", r"\bAES-(?:GCM|256(?:-GCM)?)\b"),
    ("HKDF/PBKDF2/Argon2", r"\b(?:HKDF|PBKDF2|Argon2)\b"),
    ("JWK", r"\bJWK\b"),
    ("pubkey", r"\bpubkey\b|pubkey_id"),
    ("ciphertext", r"\bciphertext\b"),
    ("keypair/provisioned", r"\b(?:keypair|provisioned)\b"),
    ("O(1)/shred", r"\bO\(1\)|\bshred(?:ded)?\b"),
    ("Ed25519/X25519/RSA/SHA-256", r"\b(?:Ed25519|X25519|RSA-\d+|SHA-256|secp256k1)\b"),
    ("raw_hex_id", r"\b(?:bf_[0-9a-f]{8,}|0x[0-9a-fA-F]{12,}|[0-9a-f]{24,})\b"),
    ("node_handle", r"\bnode_[0-9a-f]{4,}\b"),
    ("Epoch_jargon", r"\bEpoch\s*\d+|\(E\d+\)"),
    ("relay_jargon", r"\b(?:the relay|relay shred|blind relay)\b"),
    ("crypto.subtle", r"crypto\.subtle"),
]

_INLINE_HANDLER_RE = re.compile(r"^on[a-z]+$", re.IGNORECASE)
_BAD_URL_SCHEME_RE = re.compile(r"^\s*(?:javascript|vbscript):|^\s*data\s*:\s*text/html", re.IGNORECASE)
_JS_URL_CALLERS = frozenset({
    "fetch", "apiFetch", "apiGet", "apiPost", "apiPut", "apiDelete", "apiJson",
})
_JS_DIALOG_CALLERS = frozenset({
    "confirm", "alert", "prompt", "showToast", "toast", "setText", "showBanner",
})
_JS_SELECTOR_CALLERS = frozenset({
    "querySelector", "querySelectorAll", "closest", "bindGroup", "matches",
})
_MAIL_ADMIN_FLOW_FNS = frozenset({
    "registerMailboxFlow", "zkRegisterFlow", "sendCompose",
})
_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"})
_BLINDUI_ROUTE_COMMENT_RE = re.compile(
    r"#\s*blindui-route\s*:\s*(GET|POST|PUT|DELETE|PATCH)\s+(/\S*)",
    re.IGNORECASE,
)


def _unquote_js_string(tok: str) -> str:
    """Decode a JS single- or double-quoted string literal token into Python text."""
    if len(tok) < 2 or tok[0] != tok[-1] or tok[0] not in ("'", '"'):
        return tok
    body = tok[1:-1]
    out: List[str] = []
    i = 0
    n = len(body)
    esc_map = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "'": "'", '"': '"', "0": "\0"}
    while i < n:
        ch = body[i]
        if ch == "\\" and i + 1 < n:
            nxt = body[i + 1]
            if nxt in esc_map:
                out.append(esc_map[nxt])
                i += 2
                continue
            if nxt == "x" and i + 3 < n:
                try:
                    out.append(chr(int(body[i + 2:i + 4], 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
            if nxt == "u" and i + 5 < n:
                try:
                    out.append(chr(int(body[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _resolve_static_path(node: ast.AST, base_dir: Path, env: Dict[str, Any]) -> Optional[Path]:
    """Statically evaluate simple Path(__file__) / os.path expressions without executing code."""
    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return base_dir / "__init__.py"
        val = env.get(node.id)
        if isinstance(val, Path):
            return val
        if isinstance(val, str):
            p = Path(val)
            return p if p.is_absolute() else (base_dir / p)
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        p = Path(node.value)
        return p if p.is_absolute() else (base_dir / p)
    if isinstance(node, ast.Attribute):
        if node.attr == "parent":
            inner = _resolve_static_path(node.value, base_dir, env)
            return inner.parent if inner is not None else None
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _resolve_static_path(node.left, base_dir, env)
        right = _eval_static_str(node.right, base_dir, env)
        if left is not None and isinstance(right, str):
            return left / right
        return None
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "Path" and len(node.args) == 1:
            return _resolve_static_path(node.args[0], base_dir, env)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "resolve" and not node.args:
                return _resolve_static_path(node.func.value, base_dir, env)
            if node.func.attr == "with_name" and len(node.args) == 1:
                base_p = _resolve_static_path(node.func.value, base_dir, env)
                name = _eval_static_str(node.args[0], base_dir, env)
                if base_p is not None and isinstance(name, str):
                    return base_p.with_name(name)
            if node.func.attr == "dirname" and len(node.args) == 1:
                inner = _resolve_static_path(node.args[0], base_dir, env)
                return inner.parent if inner is not None else None
            if node.func.attr == "join" and node.args:
                first = _resolve_static_path(node.args[0], base_dir, env)
                if first is None:
                    return None
                cur = first
                for arg in node.args[1:]:
                    part = _eval_static_str(arg, base_dir, env)
                    if not isinstance(part, str):
                        return None
                    cur = cur / part
                return cur
    return None


def _eval_static_str(node: ast.AST, base_dir: Path, env: Dict[str, Any]) -> Optional[str]:
    """Statically evaluate string constants, +, f-strings, .replace(), and sibling read_text()."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        val = env.get(node.id)
        return val if isinstance(val, str) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _eval_static_str(node.left, base_dir, env)
        right = _eval_static_str(node.right, base_dir, env)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.JoinedStr):
        parts: List[str] = []
        for val in node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                parts.append(val.value)
            elif isinstance(val, ast.FormattedValue):
                ev = _eval_static_str(val.value, base_dir, env)
                if ev is None:
                    return None
                parts.append(ev)
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr == "replace" and len(node.args) in (2, 3):
                target = _eval_static_str(node.func.value, base_dir, env)
                old = _eval_static_str(node.args[0], base_dir, env)
                new = _eval_static_str(node.args[1], base_dir, env)
                if target is not None and old is not None and new is not None:
                    if len(node.args) == 3 and isinstance(node.args[2], ast.Constant) and isinstance(node.args[2].value, int):
                        return target.replace(old, new, node.args[2].value)
                    return target.replace(old, new)
                return None
            if attr in ("strip", "lstrip", "rstrip"):
                target = _eval_static_str(node.func.value, base_dir, env)
                if target is not None:
                    arg = _eval_static_str(node.args[0], base_dir, env) if node.args else None
                    return getattr(target, attr)(arg)
                return None
            if attr == "read_text":
                path_obj = _resolve_static_path(node.func.value, base_dir, env)
                if path_obj is not None and path_obj.is_file():
                    return path_obj.read_text("utf-8", errors="replace")
                return None
            if attr == "read" and isinstance(node.func.value, ast.Call):
                inner_call = node.func.value
                if isinstance(inner_call.func, ast.Name) and inner_call.func.id == "open" and inner_call.args:
                    path_obj = _resolve_static_path(inner_call.args[0], base_dir, env)
                    if path_obj is not None and path_obj.is_file():
                        return path_obj.read_text("utf-8", errors="replace")
                return None
    return None


def extract_html_from_ui(ui_path: Path, html_var: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract HTML from a .html/.htm file or via ast.parse() from a .py file.
    Returns (html_text, error_message).
    """
    if not ui_path.is_file():
        return None, f"UI file not found: {ui_path}"
    if ui_path.suffix.lower() in (".html", ".htm"):
        return ui_path.read_text("utf-8", errors="replace"), None

    src = ui_path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(ui_path))
    except SyntaxError as exc:
        return None, f"Failed to AST-parse UI Python file {ui_path}: {exc}"

    base_dir = ui_path.resolve().parent
    env: Dict[str, Any] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            val_str = _eval_static_str(stmt.value, base_dir, env)
            val_path = None if val_str is not None else _resolve_static_path(stmt.value, base_dir, env)
            val = val_str if val_str is not None else val_path
            if val is not None:
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        env[tgt.id] = val
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
            val_str = _eval_static_str(stmt.value, base_dir, env)
            val_path = None if val_str is not None else _resolve_static_path(stmt.value, base_dir, env)
            val = val_str if val_str is not None else val_path
            if val is not None:
                env[stmt.target.id] = val

    candidates = [html_var] if html_var else ["INDEX_HTML", "APP_HTML"]
    for name in candidates:
        if name and isinstance(env.get(name), str):
            return env[name], None
    return None, f"Could not statically resolve HTML variable ({', '.join(c for c in candidates if c)}) in {ui_path}"


def extract_scripts(html: str) -> List[Dict[str, Any]]:
    """Extract <script> blocks with index, attributes, body, line offset, and JS flag."""
    scripts: List[Dict[str, Any]] = []
    for idx, match in enumerate(_SCRIPT_BLOCK_RE.finditer(html)):
        attrs_raw = match.group(1) or ""
        body = match.group(2) or ""
        line = html.count("\n", 0, match.start(2)) + 1
        type_m = re.search(r'\btype\s*=\s*["\']?([^"\'\s>]+)', attrs_raw, re.IGNORECASE)
        script_type = (type_m.group(1).lower() if type_m else "")
        is_js = script_type in ("", "text/javascript", "application/javascript", "module")
        scripts.append({
            "index": idx,
            "attrs": attrs_raw,
            "body": body,
            "line": line,
            "is_js": is_js,
        })
    return scripts


class _DomInspector(HTMLParser):
    """Single-pass HTMLParser collecting XSS attr findings, controls, all IDs, and visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_script = 0
        self.in_style = 0
        self.in_template = 0
        self.skip_qs_depth = 0
        self.form_stack: List[Optional[str]] = []
        self.all_ids: Set[str] = set()
        self.controls: List[Dict[str, Any]] = []
        self.xss_findings: List[str] = []
        self.visible_chunks: List[str] = []
        self.raw_attr_ids_and_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if self.in_script or self.in_style:
            return
        if t == "script":
            self.in_script += 1
        elif t == "style":
            self.in_style += 1
        elif t == "template":
            self.in_template += 1

        attr_map: Dict[str, str] = {}
        for k, v in attrs:
            kl = k.lower()
            val = "" if v is None else v
            attr_map[kl] = val
            if _INLINE_HANDLER_RE.match(kl):
                self.xss_findings.append(f"inline event attribute <{t} {kl}=...>")
            elif kl == "srcdoc":
                self.xss_findings.append(f"disallowed srcdoc attribute on <{t}>")
            elif kl in ("href", "src", "action", "formaction") and _BAD_URL_SCHEME_RE.search(val):
                self.xss_findings.append(f"dangerous URL scheme in <{t} {kl}={val[:40]!r}>")

        el_id = attr_map.get("id", "").strip()
        if self.skip_qs_depth > 0:
            self.skip_qs_depth += 1
        elif el_id == "qs-code":
            self.skip_qs_depth = 1

        if t in ("script", "style", "template") or self.in_template > 0:
            return

        if el_id:
            self.all_ids.add(el_id)
            self.raw_attr_ids_and_text.append(el_id)

        if t == "form":
            self.form_stack.append(el_id or None)

        role = attr_map.get("role", "").strip().lower()
        input_type = attr_map.get("type", "").strip().lower()
        is_control = (
            t == "button"
            or t == "form"
            or (t == "input" and input_type == "submit")
            or role in ("tab", "button")
        )
        if is_control and el_id:
            classes = [c for c in attr_map.get("class", "").split() if c]
            data_attrs = [k for k in attr_map.keys() if k.startswith("data-")]
            parent_form_id: Optional[str] = None
            for fid in reversed(self.form_stack):
                if fid:
                    parent_form_id = fid
                    break
            if t == "form":
                parent_form_id = None
            is_submit = (
                (t == "input" and input_type == "submit")
                or (t == "button" and input_type in ("", "submit"))
            )
            self.controls.append({
                "id": el_id,
                "tag": t,
                "classes": classes,
                "data_attrs": data_attrs,
                "parent_form_id": parent_form_id,
                "is_submit": is_submit,
                "static_opt_out": attr_map.get("data-blindui-static", "").strip().lower() == "true",
            })

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "script" and self.in_script > 0:
            self.in_script -= 1
            return
        if t == "style" and self.in_style > 0:
            self.in_style -= 1
            return
        if self.in_script or self.in_style:
            return
        if t == "template" and self.in_template > 0:
            self.in_template -= 1
        if self.skip_qs_depth > 0:
            self.skip_qs_depth -= 1
        if t == "form" and self.form_stack:
            self.form_stack.pop()

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        self.handle_starttag(tag, attrs)
        if t not in ("script", "style"):
            if self.skip_qs_depth > 0 and any(k.lower() == "id" and (v or "").strip() == "qs-code" for k, v in attrs):
                self.skip_qs_depth -= 1
            elif self.skip_qs_depth > 1:
                self.skip_qs_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_script or self.in_style or self.in_template or self.skip_qs_depth > 0:
            return
        if data:
            self.visible_chunks.append(data)


def _adding_finding(findings: List[Dict[str, str]], rule: str, detail: str) -> None:
    findings.append({"rule": rule, "detail": detail})


def _check_bui_01(
    html: str,
    dom: _DomInspector,
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-01: Zero XSS sinks across HTML attributes, JS AST/tokens, and raw HTML."""
    for item in dom.xss_findings:
        _adding_finding(findings, "BUI-01", f"HTML sink: {item}")

    for sc, toks in tokenized_scripts:
        idx_lbl = f"script[{sc['index']}]@L{sc['line']}"
        n = len(toks)
        saw_dom_parser = False
        saw_text_html = False
        for i, (k, v, _) in enumerate(toks):
            prev_k, prev_v = (toks[i - 1][0], toks[i - 1][1]) if i > 0 else ("", "")
            next_k, next_v = (toks[i + 1][0], toks[i + 1][1]) if i + 1 < n else ("", "")
            if k == "ident" and prev_k == "punct" and prev_v in (".", "?."):
                if v in (_SINK_INNER_HTML, _SINK_OUTER_HTML, _SINK_INSERT_ADJ_HTML, "srcdoc"):
                    _adding_finding(findings, "BUI-01", f"{idx_lbl}: disallowed DOM sink property .{v}")
                elif v in ("write", "writeln") and i >= 2 and toks[i - 2][0] == "ident" and toks[i - 2][1] == "document":
                    _adding_finding(findings, "BUI-01", f"{idx_lbl}: disallowed document.{v}() call")
            elif k == "ident" and v == _SINK_EVAL_NAME and next_k == "punct" and next_v == "(" and prev_v not in (".", "?."):
                _adding_finding(findings, "BUI-01", f"{idx_lbl}: disallowed dynamic {_SINK_EVAL_NAME}() call")
            elif k == "ident" and v == _SINK_FUNC_CTOR and prev_k == "ident" and prev_v == "new":
                _adding_finding(findings, "BUI-01", f"{idx_lbl}: disallowed new {_SINK_FUNC_CTOR} constructor")
            elif k == "ident" and v in ("setTimeout", "setInterval") and next_k == "punct" and next_v == "(":
                if prev_v not in (".", "?.") or (i >= 2 and toks[i - 2][1] in ("window", "globalThis")):
                    if i + 2 < n and toks[i + 2][0] in ("str", "tmpl"):
                        _adding_finding(findings, "BUI-01", f"{idx_lbl}: string-eval {v}() call")
            elif k == "ident" and v == "DOMParser":
                saw_dom_parser = True
            elif k in ("str", "tmpl") and "text/html" in v.lower():
                saw_text_html = True
        if saw_dom_parser and saw_text_html:
            _adding_finding(findings, "BUI-01", f"{idx_lbl}: DOMParser paired with text/html literal")

    # Raw HTML scan (case-insensitive) for forbidden sink substrings.
    html_low = html.lower()
    for needle in (_SINK_INNER_HTML, _SINK_OUTER_HTML, _SINK_INSERT_ADJ_HTML, _SINK_DOC_WRITE, _SINK_DOC_WRITELN):
        if needle.lower() in html_low:
            _adding_finding(findings, "BUI-01", f"Raw HTML contains forbidden sink literal ({needle})")


def _check_bui_02(
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-02: Zero duplicate hoisted JS function declarations at depth <= 1 in the same scope."""
    expr_prev_punct = frozenset({"=", "(", "[", ":", ",", "?", "&&", "||", "!", "+", "-", "=>"})
    expr_prev_ident = frozenset({"return", "throw", "yield", "await", "new", "typeof", "void", "delete"})

    for sc, toks in tokenized_scripts:
        idx_lbl = f"script[{sc['index']}]@L{sc['line']}"
        scope_stack: List[int] = [0]
        next_scope_id = 1
        seen: Dict[Tuple[int, str], int] = {}
        n = len(toks)
        for i, (k, v, _) in enumerate(toks):
            if k == "punct" and v == "{":
                scope_stack.append(next_scope_id)
                next_scope_id += 1
                continue
            if k == "punct" and v == "}":
                if len(scope_stack) > 1:
                    scope_stack.pop()
                continue
            depth = len(scope_stack) - 1
            if depth <= 1 and k == "ident" and v == "function":
                if i + 2 >= n or toks[i + 1][0] != "ident" or toks[i + 2][0] != "punct" or toks[i + 2][1] != "(":
                    continue
                # Check whether this is a statement declaration (possibly preceded by `async`).
                check_idx = i - 1
                if check_idx >= 0 and toks[check_idx][0] == "ident" and toks[check_idx][1] == "async":
                    check_idx -= 1
                if check_idx >= 0:
                    pk, pv, _ = toks[check_idx]
                    if pk == "punct" and pv in expr_prev_punct:
                        continue
                    if pk == "ident" and pv in expr_prev_ident:
                        continue
                fn_name = toks[i + 1][1]
                key = (scope_stack[-1], fn_name)
                if key in seen:
                    _adding_finding(findings, "BUI-02", f"{idx_lbl}: duplicate hoisted function '{fn_name}'")
                else:
                    seen[key] = i


def _check_bui_03(
    scripts: List[Dict[str, Any]],
    blindui_path: Optional[Path],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-03: JS syntax validation via node --check on every JS <script> block (+ --blindui)."""
    for sc in scripts:
        if not sc["is_js"] or not sc["body"].strip():
            continue
        errs = build_blindui.run_node_check(sc["body"], f"script[{sc['index']}]@L{sc['line']}", require_node=True)
        for err in errs:
            _adding_finding(findings, "BUI-03", err)
    if blindui_path is not None and blindui_path.is_file():
        errs = build_blindui.run_node_check(blindui_path.read_text("utf-8", errors="replace"), blindui_path.name, require_node=True)
        for err in errs:
            _adding_finding(findings, "BUI-03", err)


def _split_call_args(tokens: List[Tuple[str, str, bool]], open_paren_idx: int) -> Tuple[List[List[Tuple[str, str, bool]]], int]:
    """Split tokens inside (...) starting at open_paren_idx into argument token lists."""
    args: List[List[Tuple[str, str, bool]]] = []
    cur: List[Tuple[str, str, bool]] = []
    depth = 1
    i = open_paren_idx + 1
    n = len(tokens)
    while i < n and depth > 0:
        tk, tv, tnl = tokens[i]
        if tk == "punct" and tv in ("(", "[", "{"):
            depth += 1
            cur.append((tk, tv, tnl))
        elif tk == "punct" and tv in (")", "]", "}"):
            depth -= 1
            if depth == 0:
                if cur or args:
                    args.append(cur)
                return args, i
            cur.append((tk, tv, tnl))
        elif depth == 1 and tk == "punct" and tv == ",":
            args.append(cur)
            cur = []
        else:
            cur.append((tk, tv, tnl))
        i += 1
    if cur:
        args.append(cur)
    return args, i


def _check_bui_04(
    dom: _DomInspector,
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-04: HTML button/form ID wiring coverage + BlindUI.bindAction reverse check."""
    literal_strings: Set[str] = set()
    selector_strings: List[str] = []
    bind_action_ids: List[Tuple[str, str]] = []

    for sc, toks in tokenized_scripts:
        idx_lbl = f"script[{sc['index']}]@L{sc['line']}"
        n = len(toks)
        for i, (k, v, _) in enumerate(toks):
            if k == "str":
                val = _unquote_js_string(v)
                literal_strings.add(val)
            elif k == "tmpl":
                # Also extract static prefix/exact text from simple templates without ${...}
                if "${" not in v and len(v) >= 2:
                    literal_strings.add(v[1:-1])
            elif k == "ident" and v in _JS_SELECTOR_CALLERS and i + 1 < n and toks[i + 1][1] == "(":
                args, _ = _split_call_args(toks, i + 1)
                if args:
                    for ak, av, _ in args[0]:
                        if ak == "str":
                            selector_strings.append(_unquote_js_string(av))
                        elif ak == "tmpl":
                            selector_strings.append(av[1:-1])
            elif k == "ident" and v == "bindAction" and i + 1 < n and toks[i + 1][1] == "(":
                args, _ = _split_call_args(toks, i + 1)
                if args and len(args[0]) == 1 and args[0][0][0] == "str":
                    bind_action_ids.append((idx_lbl, _unquote_js_string(args[0][0][1])))

    def _id_referenced(el_id: str) -> bool:
        if el_id in literal_strings or ("#" + el_id) in literal_strings:
            return True
        needle = "#" + el_id
        for sel in selector_strings:
            if needle in sel:
                return True
        return False

    for ctrl in dom.controls:
        if ctrl["static_opt_out"]:
            continue
        cid = ctrl["id"]
        if _id_referenced(cid):
            continue
        if ctrl["is_submit"] and ctrl["parent_form_id"] and _id_referenced(ctrl["parent_form_id"]):
            continue
        covered_by_sel = False
        for sel in selector_strings:
            for cls in ctrl["classes"]:
                if re.search(r"\." + re.escape(cls) + r"(?![A-Za-z0-9_-])", sel):
                    covered_by_sel = True
                    break
            if covered_by_sel:
                break
            for da in ctrl["data_attrs"]:
                if ("[" + da) in sel:
                    covered_by_sel = True
                    break
            if covered_by_sel:
                break
        if not covered_by_sel:
            _adding_finding(findings, "BUI-04", f"Unwired HTML control <{ctrl['tag']} id={cid!r}> has no JS handler/selector reference")

    for lbl, bid in bind_action_ids:
        if bid not in dom.all_ids:
            _adding_finding(findings, "BUI-04", f"{lbl}: bindAction({bid!r}) references missing HTML id")


def _collect_js_string_consts(toks: List[Tuple[str, str, bool]]) -> Dict[str, str]:
    """Collect simple const/let/var string constants (supporting str + str and template concat)."""
    consts: Dict[str, str] = {}
    n = len(toks)

    def eval_expr(sub: List[Tuple[str, str, bool]]) -> Optional[str]:
        if not sub:
            return None
        parts: List[str] = []
        i = 0
        while i < len(sub):
            tk, tv, _ = sub[i]
            if tk == "str":
                parts.append(_unquote_js_string(tv))
            elif tk == "tmpl":
                body = tv[1:-1]
                ok = True
                def repl(m: re.Match[str]) -> str:
                    nonlocal ok
                    key = m.group(1).strip()
                    if key in consts:
                        return consts[key]
                    ok = False
                    return ""
                expanded = re.sub(r"\$\{([^}]+)\}", repl, body)
                if not ok:
                    return None
                parts.append(expanded)
            elif tk == "ident" and tv in consts:
                parts.append(consts[tv])
            elif tk == "punct" and tv == "+":
                i += 1
                continue
            else:
                return None
            i += 1
        return "".join(parts)

    i = 0
    while i < n:
        k, v, _ = toks[i]
        if k == "ident" and v in ("const", "let", "var"):
            j = i + 1
            while j < n:
                if j + 2 < n and toks[j][0] == "ident" and toks[j + 1][1] == "=":
                    name = toks[j][1]
                    expr_toks: List[Tuple[str, str, bool]] = []
                    m = j + 2
                    depth = 0
                    while m < n:
                        mk, mv, mnl = toks[m]
                        if depth == 0 and ((mk == "punct" and mv in (";", ",", ")")) or (mnl and expr_toks and expr_toks[-1][1] != "+")):
                            break
                        if mk == "punct" and mv in ("(", "[", "{"):
                            depth += 1
                        elif mk == "punct" and mv in (")", "]", "}"):
                            if depth == 0:
                                break
                            depth -= 1
                        expr_toks.append(toks[m])
                        m += 1
                    val = eval_expr(expr_toks)
                    if val is not None:
                        consts[name] = val
                    j = m + 1 if (m < n and toks[m][1] == ",") else m
                    if m >= n or toks[m][1] != ",":
                        break
                else:
                    break
            i = j
            continue
        i += 1
    return consts


def _eval_js_url_expr(expr: List[Tuple[str, str, bool]], consts: Dict[str, str]) -> Optional[str]:
    """Reconstruct a normalized URL pattern from a JS call argument token list."""
    if not expr:
        return None
    # Split top-level '+' concatenation operands.
    operands: List[List[Tuple[str, str, bool]]] = []
    cur: List[Tuple[str, str, bool]] = []
    depth = 0
    for tk, tv, tnl in expr:
        if tk == "punct" and tv in ("(", "[", "{"):
            depth += 1
            cur.append((tk, tv, tnl))
        elif tk == "punct" and tv in (")", "]", "}"):
            depth -= 1
            cur.append((tk, tv, tnl))
        elif depth == 0 and tk == "punct" and tv == "+":
            operands.append(cur)
            cur = []
        else:
            cur.append((tk, tv, tnl))
    if cur:
        operands.append(cur)

    # Handle conditional ternary (cond ? urlA : urlB) by picking nothing here (handled by caller if needed)
    pieces: List[str] = []
    has_slash_literal = False
    for op in operands:
        if len(op) == 1 and op[0][0] == "str":
            s = _unquote_js_string(op[0][1])
            if "/" in s:
                has_slash_literal = True
            pieces.append(s)
        elif len(op) == 1 and op[0][0] == "tmpl":
            body = op[0][1][1:-1]
            def _repl_tmpl(m: re.Match[str]) -> str:
                inner = m.group(1).strip()
                if inner in consts:
                    return consts[inner]
                return "{param}"
            # Only handle non-nested ${...} cleanly; collapse nested template exprs safely.
            expanded = re.sub(r"\$\{[^}]+\}", _repl_tmpl, body)
            if "/" in expanded:
                has_slash_literal = True
            pieces.append(expanded)
        elif len(op) == 1 and op[0][0] == "ident" and op[0][1] in consts:
            s = consts[op[0][1]]
            if "/" in s:
                has_slash_literal = True
            pieces.append(s)
        else:
            pieces.append("{param}")

    if not has_slash_literal:
        return None
    raw = "".join(pieces).strip()
    if not raw:
        return None
    low = raw.lower()
    if low.startswith(("http://", "https://", "data:", "blob:", "mailto:", "//", "#")):
        return None
    return raw


def _extract_method_from_opts(opts_toks: List[Tuple[str, str, bool]]) -> Optional[str]:
    """Extract method: 'POST' from a JS object literal token list (at top brace level)."""
    if not opts_toks or opts_toks[0][1] != "{":
        return None
    depth = 0
    n = len(opts_toks)
    for i, (k, v, _) in enumerate(opts_toks):
        if k == "punct" and v in ("{", "[", "("):
            depth += 1
        elif k == "punct" and v in ("}", "]", ")"):
            depth -= 1
        elif depth == 1 and ((k == "ident" and v == "method") or (k == "str" and _unquote_js_string(v) == "method")):
            if i + 2 < n and opts_toks[i + 1][1] == ":" and opts_toks[i + 2][0] == "str":
                m = _unquote_js_string(opts_toks[i + 2][1]).strip().upper()
                if m in _HTTP_METHODS:
                    return m
    return None


def _normalize_js_route(method: str, raw_url: str) -> Optional[Tuple[str, str]]:
    """Normalize (method, raw_url) to canonical (METHOD, /path/with/{param})."""
    u = raw_url.strip()
    # Handle BlindUI.api("POST /api/...") embedded method prefix
    parts = u.split(" ", 1)
    if len(parts) == 2 and parts[0].upper() in _HTTP_METHODS:
        method = parts[0].upper()
        u = parts[1].strip()
    u = u.split("?", 1)[0].split("#", 1)[0]
    if not u:
        return None
    low = u.lower()
    if low.startswith(("http://", "https://", "data:", "blob:", "mailto:", "//")):
        return None
    if u.startswith("./"):
        u = u[1:]
    if not u.startswith("/"):
        u = "/" + u
    # Strip trailing '{param}' that came from dynamic query string concatenation without '?'
    u = re.sub(r"/+", "/", u)
    if u.startswith("/{param}") and u.count("/") == 1:
        return None
    return (method.upper(), u)


def extract_js_routes(tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]]) -> List[Tuple[str, str, str]]:
    """Extract [(method, normalized_path, source_label)] from all JS <script> blocks."""
    routes: List[Tuple[str, str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    for sc, toks in tokenized_scripts:
        idx_lbl = f"script[{sc['index']}]@L{sc['line']}"
        consts = _collect_js_string_consts(toks)
        n = len(toks)
        for i, (k, v, _) in enumerate(toks):
            if k != "ident":
                continue
            caller: Optional[str] = None
            open_idx = -1
            if v in _JS_URL_CALLERS and i + 1 < n and toks[i + 1][1] == "(":
                prev_v = toks[i - 1][1] if i > 0 else ""
                if prev_v not in (".", "?.") or (i >= 2 and toks[i - 2][1] in ("window", "globalThis")):
                    caller = v
                    open_idx = i + 1
            elif v == "api" and i >= 2 and toks[i - 1][1] == "." and toks[i - 2][1] == "BlindUI" and i + 1 < n and toks[i + 1][1] == "(":
                caller = "BlindUI.api"
                open_idx = i + 1

            if caller is None:
                continue
            args, _ = _split_call_args(toks, open_idx)
            if not args:
                continue

            # Support simple ternary in arg0: cond ? urlA : urlB
            url_variants: List[List[Tuple[str, str, bool]]] = []
            arg0 = args[0]
            q_idx = -1
            col_idx = -1
            depth = 0
            for j, (ak, av, _) in enumerate(arg0):
                if ak == "punct" and av in ("(", "[", "{"):
                    depth += 1
                elif ak == "punct" and av in (")", "]", "}"):
                    depth -= 1
                elif depth == 0 and ak == "punct" and av == "?" and q_idx < 0:
                    q_idx = j
                elif depth == 0 and ak == "punct" and av == ":" and q_idx >= 0 and col_idx < 0:
                    col_idx = j
            if q_idx >= 0 and col_idx > q_idx:
                url_variants.append(arg0[q_idx + 1:col_idx])
                url_variants.append(arg0[col_idx + 1:])
            else:
                url_variants.append(arg0)

            default_method = {
                "apiGet": "GET",
                "apiPost": "POST",
                "apiPut": "PUT",
                "apiDelete": "DELETE",
            }.get(caller, "GET")
            method = default_method
            if len(args) >= 2 and args[1]:
                if caller == "apiJson" and len(args[1]) == 1 and args[1][0][0] == "str":
                    cand = _unquote_js_string(args[1][0][1]).strip().upper()
                    if cand in _HTTP_METHODS:
                        method = cand
                else:
                    opt_m = _extract_method_from_opts(args[1])
                    if opt_m:
                        method = opt_m

            for variant in url_variants:
                raw_url = _eval_js_url_expr(variant, consts)
                if not raw_url:
                    continue
                norm = _normalize_js_route(method, raw_url)
                if norm is None:
                    continue
                if norm not in seen:
                    seen.add(norm)
                    routes.append((norm[0], norm[1], idx_lbl))
    return routes


class _ServerRouteSet:
    """Routes extracted statically from a Python BaseHTTPRequestHandler server file."""

    def __init__(self) -> None:
        self.exact: Dict[str, Set[str]] = {}
        self.prefixes: Dict[str, List[Tuple[str, Optional[str], Optional[str]]]] = {}
        self.regexes: Dict[str, List[re.Pattern[str]]] = {}
        self.templates: Dict[str, List[List[Optional[str]]]] = {}

    def add_exact(self, method: str, path: str) -> None:
        self.exact.setdefault(method, set()).add(path)

    def add_prefix(self, method: str, prefix: str, suffix: Optional[str] = None, contains: Optional[str] = None) -> None:
        self.prefixes.setdefault(method, []).append((prefix, suffix, contains))

    def add_regex(self, method: str, pattern: str) -> None:
        try:
            self.regexes.setdefault(method, []).append(re.compile(pattern))
        except re.error:
            pass

    def add_template(self, method: str, segs: List[Optional[str]]) -> None:
        self.templates.setdefault(method, []).append(segs)

    def matches(self, method: str, js_path: str) -> bool:
        if js_path in self.exact.get(method, ()):
            return True
        # Expand {param} into dummy path values for regex and prefix checks.
        dummy_a = js_path.replace("{param}", "abc12345")
        dummy_b = js_path.replace("{param}", "123456")
        js_segs = [s for s in js_path.split("/") if s]

        # Exact-template comparison (if server exact route contains {param} via blindui-route comment)
        for ex in self.exact.get(method, ()):
            if "{" in ex:
                ex_segs = [s for s in ex.split("/") if s]
                if len(ex_segs) == len(js_segs) and all(
                    (a.startswith("{") and a.endswith("}")) or (b.startswith("{") and b.endswith("}")) or a == b
                    for a, b in zip(ex_segs, js_segs)
                ):
                    return True

        for segs in self.templates.get(method, ()):
            if len(segs) == len(js_segs) and all(
                s is None or j == "{param}" or s == j
                for s, j in zip(segs, js_segs)
            ):
                return True

        for rx in self.regexes.get(method, ()):
            if rx.match(dummy_a) or rx.match(dummy_b):
                return True

        for pref, suf, cont in self.prefixes.get(method, ()):
            for cand in (js_path, dummy_a, dummy_b):
                if cand.startswith(pref):
                    if suf and not cand.endswith(suf):
                        continue
                    if cont and cont not in cand:
                        continue
                    return True
        return False


def _extract_parts_constraints(node: ast.AST) -> List[List[Optional[str]]]:
    """Extract segment templates from `len(parts) == N and parts[0] == 'api' ...` checks."""
    exact_len: Optional[int] = None
    seg_choices: Dict[int, List[str]] = {}

    def visit(expr: ast.AST) -> None:
        nonlocal exact_len
        if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.And):
            for v in expr.values:
                visit(v)
            return
        if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and len(expr.comparators) == 1:
            op = expr.ops[0]
            left, right = expr.left, expr.comparators[0]
            # len(parts) == N
            if (
                isinstance(op, ast.Eq)
                and isinstance(left, ast.Call)
                and isinstance(left.func, ast.Name)
                and left.func.id == "len"
                and len(left.args) == 1
                and isinstance(right, ast.Constant)
                and isinstance(right.value, int)
            ):
                exact_len = right.value
                return
            # parts[i] == "seg" or parts[i] in ("a", "b")
            if isinstance(left, ast.Subscript) and isinstance(left.slice, ast.Constant) and isinstance(left.slice.value, int):
                idx = left.slice.value
                if idx >= 0:
                    if isinstance(op, ast.Eq) and isinstance(right, ast.Constant) and isinstance(right.value, str):
                        seg_choices[idx] = [right.value]
                    elif isinstance(op, ast.In) and isinstance(right, (ast.Tuple, ast.List, ast.Set)):
                        vals = [e.value for e in right.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                        if vals:
                            seg_choices[idx] = vals

    visit(node)
    if exact_len is None or exact_len <= 0 or not seg_choices:
        return []
    # Build cartesian product of constrained segments (bounded small)
    results: List[List[Optional[str]]] = [[None] * exact_len]
    for idx, vals in sorted(seg_choices.items()):
        if idx >= exact_len:
            continue
        next_res: List[List[Optional[str]]] = []
        for tpl in results:
            for val in vals:
                copy = list(tpl)
                copy[idx] = val
                next_res.append(copy)
        results = next_res[:64]
    return results


def _collect_routes_from_expr(
    expr: ast.AST,
    method: str,
    regex_map: Dict[str, str],
    out: _ServerRouteSet,
) -> None:
    """Collect route patterns from a boolean condition expression inside do_<METHOD>."""
    # Check segment-based `parts` dispatch
    for tpl in _extract_parts_constraints(expr):
        out.add_template(method, tpl)

    # Check compound startswith + endswith/in in BoolOp(And)
    if isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.And):
        prefixes: List[str] = []
        suffixes: List[str] = []
        contains: List[str] = []
        for v in expr.values:
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.args:
                if v.func.attr == "startswith" and isinstance(v.args[0], ast.Constant) and isinstance(v.args[0].value, str):
                    if v.args[0].value.startswith("/"):
                        prefixes.append(v.args[0].value)
                elif v.func.attr == "endswith" and isinstance(v.args[0], ast.Constant) and isinstance(v.args[0].value, str):
                    suffixes.append(v.args[0].value)
            elif isinstance(v, ast.Compare) and len(v.ops) == 1 and isinstance(v.ops[0], ast.In):
                if isinstance(v.left, ast.Constant) and isinstance(v.left.value, str) and "/" in v.left.value:
                    contains.append(v.left.value)
        if prefixes and (suffixes or contains):
            for p in prefixes:
                out.add_prefix(method, p, suffixes[0] if suffixes else None, contains[0] if contains else None)
            # Continue descending into sub-expressions too

    for node in ast.walk(expr):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            op = node.ops[0]
            left, right = node.left, node.comparators[0]
            if isinstance(op, ast.Eq):
                for side in (right, left):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str) and side.value.startswith("/"):
                        out.add_exact(method, side.value)
            elif isinstance(op, ast.In):
                if isinstance(right, (ast.Tuple, ast.List, ast.Set)):
                    for elt in right.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and elt.value.startswith("/"):
                            out.add_exact(method, elt.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr == "startswith" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str) and arg0.value.startswith("/"):
                    out.add_prefix(method, arg0.value)
                elif isinstance(arg0, ast.Tuple):
                    for elt in arg0.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str) and elt.value.startswith("/"):
                            out.add_prefix(method, elt.value)
            elif attr in ("match", "fullmatch"):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in regex_map:
                    out.add_regex(method, regex_map[node.func.value.id])
                elif (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "re"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    out.add_regex(method, node.args[0].value)


def extract_server_routes(server_path: Path) -> Tuple[Optional[_ServerRouteSet], Optional[str]]:
    """Parse a Python HTTP server file via ast.parse() and extract all declared HTTP routes."""
    if not server_path.is_file():
        return None, f"Server file not found: {server_path}"
    src = server_path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(server_path))
    except SyntaxError as exc:
        return None, f"Failed to AST-parse server Python file {server_path}: {exc}"

    routes = _ServerRouteSet()
    # 1. Explicit # blindui-route: METHOD /pattern comments
    for m in _BLINDUI_ROUTE_COMMENT_RE.finditer(src):
        routes.add_exact(m.group(1).upper(), m.group(2))

    # 2. Module-level (and nested) re.compile(...) definitions
    regex_map: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if (
                isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "compile"
                and node.value.args
                and isinstance(node.value.args[0], ast.Constant)
                and isinstance(node.value.args[0].value, str)
            ):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        regex_map[tgt.id] = node.value.args[0].value

    # 3. Walk ALL ast.ClassDef nodes (including nested classes inside create_server())
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        method_defs: Dict[str, ast.FunctionDef] = {
            n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)
        }
        for fn_name, fn_node in method_defs.items():
            if not fn_name.startswith("do_"):
                continue
            http_method = fn_name[3:].upper()
            if http_method not in _HTTP_METHODS:
                continue

            visited_fns: Set[str] = set()
            queue: List[ast.FunctionDef] = [fn_node]
            while queue:
                cur_fn = queue.pop(0)
                if cur_fn.name in visited_fns:
                    continue
                visited_fns.add(cur_fn.name)
                for sub in ast.walk(cur_fn):
                    if isinstance(sub, ast.If):
                        _collect_routes_from_expr(sub.test, http_method, regex_map, routes)
                    elif isinstance(sub, ast.Assign) and isinstance(sub.value, (ast.Call, ast.BoolOp)):
                        # e.g., m = _V2_ENV_GET_RE.match(path) or _V1_RE.fullmatch(path)
                        _collect_routes_from_expr(sub.value, http_method, regex_map, routes)
                    elif isinstance(sub, ast.NamedExpr):
                        _collect_routes_from_expr(sub.value, http_method, regex_map, routes)
                    elif (
                        isinstance(sub, ast.Call)
                        and isinstance(sub.func, ast.Attribute)
                        and isinstance(sub.func.value, ast.Name)
                        and sub.func.value.id == "self"
                        and sub.func.attr in method_defs
                        and sub.func.attr not in visited_fns
                        and not sub.func.attr.startswith("do_")
                    ):
                        queue.append(method_defs[sub.func.attr])

    return routes, None


def _check_bui_05(
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    server_routes: _ServerRouteSet,
    surface: str,
    sso_routes: Optional[_ServerRouteSet],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-05: Elysia-style JS-to-Server Route Parity."""
    js_routes = extract_js_routes(tokenized_scripts)
    for method, path, lbl in js_routes:
        if surface in ("sign", "social", "finance", "developers", "live", "call") and path.startswith("/mail/api/v1/auth/"):
            if sso_routes is not None:
                stripped = path[len("/mail"):]
                if sso_routes.matches(method, path) or sso_routes.matches(method, stripped):
                    continue
            elif (method, path) in _CANONICAL_SSO_ROUTES:
                continue
        if server_routes.matches(method, path):
            continue
        _adding_finding(findings, "BUI-05", f"{lbl}: JS route '{method} {path}' has no matching server route")


def _scan_jargon_text(text: str, source_lbl: str, findings: List[Dict[str, str]], strip_dkim: bool = False) -> None:
    filtered = re.sub(r"v=DKIM1;[^\n]*", "", text) if strip_dkim else text
    for label, pat in JARGON_PATTERNS:
        flags = 0 if label in _JARGON_CASE_SENSITIVE else re.IGNORECASE
        m = re.search(pat, filtered, flags=flags)
        if m:
            _adding_finding(findings, "BUI-06", f"{source_lbl}: crypto/programmer jargon '{label}' matched {m.group(0)!r}")


def _check_bui_06(
    dom: _DomInspector,
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-06: Zero raw crypto/programmer jargon in visible HTML text and JS dialog/toast strings."""
    visible_text = "\n".join(dom.visible_chunks)
    _scan_jargon_text(visible_text, "HTML visible text", findings, strip_dkim=True)

    for sc, toks in tokenized_scripts:
        idx_lbl = f"script[{sc['index']}]@L{sc['line']}"
        n = len(toks)
        for i, (k, v, _) in enumerate(toks):
            if k == "ident" and v in _JS_DIALOG_CALLERS and i + 1 < n and toks[i + 1][1] == "(":
                args, _ = _split_call_args(toks, i + 1)
                for arg in args:
                    for ak, av, _ in arg:
                        if ak == "str":
                            _scan_jargon_text(_unquote_js_string(av), f"{idx_lbl}:{v}()", findings, strip_dkim=True)
                        elif ak == "tmpl":
                            _scan_jargon_text(av[1:-1], f"{idx_lbl}:{v}()", findings, strip_dkim=True)


def _check_bui_07(paths: Sequence[Tuple[str, Path]], findings: List[Dict[str, str]]) -> None:
    """BUI-07: 100% 7-bit ASCII and zero dot-clamp calls across --ui, --server, --blindui."""
    seen_real: Set[Path] = set()
    for lbl, p in paths:
        if not p.is_file():
            continue
        rp = p.resolve()
        if rp in seen_real:
            continue
        seen_real.add(rp)
        raw = p.read_bytes()
        non_ascii = sum(1 for b in raw if b > 0x7F)
        if non_ascii > 0:
            _adding_finding(findings, "BUI-07", f"{lbl} ({p.name}): found {non_ascii} non-ASCII byte(s)")
        text = raw.decode("utf-8", errors="replace")
        if _CLAMP_RE.search(text):
            _adding_finding(findings, "BUI-07", f"{lbl} ({p.name}): forbidden dot-clamp call detected")


def _extract_js_function_body(toks: List[Tuple[str, str, bool]], fn_name: str) -> List[Tuple[str, str, bool]]:
    """Extract token slice for a named JS function body."""
    n = len(toks)
    for i, (k, v, _) in enumerate(toks):
        if k == "ident" and v == "function" and i + 2 < n and toks[i + 1][0] == "ident" and toks[i + 1][1] == fn_name:
            j = i + 2
            while j < n and toks[j][1] != "{":
                j += 1
            if j >= n:
                return []
            depth = 1
            start = j + 1
            j += 1
            while j < n and depth > 0:
                if toks[j][1] == "{":
                    depth += 1
                elif toks[j][1] == "}":
                    depth -= 1
                j += 1
            return toks[start:j - 1]
    return []


def _check_bui_08(
    surface: str,
    html: str,
    dom: _DomInspector,
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-08: Mail Admin-Key exposure check (active ONLY when --surface == 'mail')."""
    if surface != "mail":
        return
    for bad_id in ("mb-admin-key", "modal-mb-admin-key", "cmp-api-key"):
        if bad_id in dom.all_ids or bad_id in html:
            _adding_finding(findings, "BUI-08", f"Mail HTML exposes forbidden admin-key control/identifier '{bad_id}'")
    visible_text = "\n".join(dom.visible_chunks)
    if re.search(r"\badmin\s+key\b", visible_text, re.IGNORECASE):
        _adding_finding(findings, "BUI-08", "Mail visible HTML contains 'Admin Key' exposure")

    for sc, toks in tokenized_scripts:
        idx_lbl = f"script[{sc['index']}]@L{sc['line']}"
        for fn_name in sorted(_MAIL_ADMIN_FLOW_FNS):
            body = _extract_js_function_body(toks, fn_name)
            for tk, tv, _ in body:
                if tk in ("str", "tmpl") and "x-api-key" in tv.lower():
                    _adding_finding(findings, "BUI-08", f"{idx_lbl}: {fn_name}() assembles X-API-Key header")
                    break


def _check_bui_09(
    blindui_path: Optional[Path],
    ui_path: Path,
    server_path: Path,
    findings: List[Dict[str, str]],
) -> None:
    """BUI-09: Bundle budget (< 28672 B), deterministic build parity, and vendored SHA-256 parity."""
    if blindui_path is None:
        return
    if not blindui_path.is_file():
        _adding_finding(findings, "BUI-09", f"--blindui target not found: {blindui_path}")
        return
    raw = blindui_path.read_bytes()
    if len(raw) >= build_blindui.MAX_BUNDLE_BYTES:
        _adding_finding(
            findings,
            "BUI-09",
            f"{blindui_path.name} size {len(raw)} B >= budget {build_blindui.MAX_BUNDLE_BYTES} B",
        )
    src_candidate = blindui_path.with_name("blindui.js")
    if not src_candidate.is_file():
        src_candidate = _HERE / "blindui.js"
    if src_candidate.is_file():
        res = build_blindui.build_and_verify(
            src_path=src_candidate,
            out_path=blindui_path,
            check_only=True,
            require_node=True,
        )
        if not res["ok"]:
            for err in res["errors"]:
                _adding_finding(findings, "BUI-09", f"build_and_verify: {err}")
    else:
        for err in build_blindui.validate_bundle_text(raw.decode("utf-8", errors="replace"), blindui_path.name, enforce_size=True):
            _adding_finding(findings, "BUI-09", err)

    expected_sha = hashlib.sha256(raw).hexdigest()
    checked_siblings: Set[Path] = {blindui_path.resolve()}
    for parent in (ui_path.resolve().parent, server_path.resolve().parent):
        sib = parent / "blindui.min.js"
        if sib.is_file() and sib.resolve() not in checked_siblings:
            checked_siblings.add(sib.resolve())
            sib_sha = hashlib.sha256(sib.read_bytes()).hexdigest()
            if sib_sha != expected_sha:
                _adding_finding(
                    findings,
                    "BUI-09",
                    f"Vendored {sib} sha256 ({sib_sha[:12]}) != {blindui_path} ({expected_sha[:12]})",
                )


def _check_bui_10(
    server_path: Path,
    scripts: List[Dict[str, Any]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-10: Required security headers and multi-script integrity check (findall vs search)."""
    if not server_path.is_file():
        return
    src = server_path.read_text("utf-8", errors="replace")
    required_headers = (
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
        ("Content-Security-Policy", None),
    )
    for hdr, expected_val in required_headers:
        if hdr.lower() not in src.lower():
            _adding_finding(findings, "BUI-10", f"Server missing required security header '{hdr}'")
        elif expected_val is not None:
            pat = re.compile(re.escape(hdr) + r"[^\n]{0,120}" + re.escape(expected_val), re.IGNORECASE)
            if not pat.search(src):
                _adding_finding(findings, "BUI-10", f"Server header '{hdr}' missing expected value '{expected_val}'")

    js_scripts = [s for s in scripts if s["is_js"] and s["body"].strip()]
    if len(js_scripts) > 1:
        has_script_search = bool(re.search(r"(?:script[^>]*|INLINE_SCRIPT|SCRIPT_RE)[^\n]{0,80}\.search\s*\(|re\.search\s*\([^\n]*<script", src, re.IGNORECASE))
        has_script_findall = bool(re.search(r"(?:script[^>]*|INLINE_SCRIPT|SCRIPT_RE)[^\n]{0,80}\.findall\s*\(|re\.findall\s*\([^\n]*<script", src, re.IGNORECASE))
        if has_script_search and not has_script_findall:
            _adding_finding(
                findings,
                "BUI-10",
                f"HTML has {len(js_scripts)} <script> blocks but server integrity check uses single .search() instead of findall()",
            )


def check_app(
    ui_path: Path,
    server_path: Path,
    surface: str,
    html_var: Optional[str] = None,
    blindui_path: Optional[Path] = None,
    sso_server_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run all active BUI-01..BUI-10 rules and return a structured report."""
    findings: List[Dict[str, str]] = []

    html, html_err = extract_html_from_ui(ui_path, html_var=html_var)
    if html_err or html is None:
        _adding_finding(findings, "BUI-00", html_err or "Failed to extract HTML")
        return {
            "ok": False,
            "surface": surface,
            "ui": str(ui_path),
            "server": str(server_path),
            "findings": findings,
        }

    scripts = extract_scripts(html)
    dom = _DomInspector()
    dom.feed(html)
    dom.close()

    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]] = []
    for sc in scripts:
        if not sc["is_js"] or not sc["body"].strip():
            continue
        try:
            toks = build_blindui.tokenize_js(sc["body"])
        except ValueError as exc:
            _adding_finding(findings, "BUI-03", f"script[{sc['index']}]@L{sc['line']}: JS tokenization error: {exc}")
            toks = []
        tokenized_scripts.append((sc, toks))

    server_routes, srv_err = extract_server_routes(server_path)
    if srv_err or server_routes is None:
        _adding_finding(findings, "BUI-05", srv_err or "Failed to parse server routes")
        server_routes = _ServerRouteSet()

    sso_routes: Optional[_ServerRouteSet] = None
    if sso_server_path is not None:
        sso_routes, sso_err = extract_server_routes(sso_server_path)
        if sso_err:
            _adding_finding(findings, "BUI-05", sso_err)

    _check_bui_01(html, dom, tokenized_scripts, findings)
    _check_bui_02(tokenized_scripts, findings)
    _check_bui_03(scripts, blindui_path, findings)
    _check_bui_04(dom, tokenized_scripts, findings)
    _check_bui_05(tokenized_scripts, server_routes, surface, sso_routes, findings)
    _check_bui_06(dom, tokenized_scripts, findings)

    ascii_targets: List[Tuple[str, Path]] = [("ui", ui_path), ("server", server_path)]
    if blindui_path is not None:
        ascii_targets.append(("blindui", blindui_path))
    _check_bui_07(ascii_targets, findings)

    _check_bui_08(surface, html, dom, tokenized_scripts, findings)
    _check_bui_09(blindui_path, ui_path, server_path, findings)
    _check_bui_10(server_path, scripts, findings)

    by_rule: Dict[str, int] = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1

    return {
        "ok": len(findings) == 0,
        "surface": surface,
        "ui": str(ui_path),
        "server": str(server_path),
        "scripts_count": len(scripts),
        "controls_count": len(dom.controls),
        "findings_count": len(findings),
        "by_rule": by_rule,
        "findings": findings,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="BlindUI Elysia-style static validator (BUI-01..BUI-10)")
    parser.add_argument("--ui", required=True, help="Path to UI .py or .html file")
    parser.add_argument("--server", required=True, help="Path to server .py file")
    parser.add_argument("--surface", required=True, choices=["mail", "sign", "social", "finance", "developers", "live", "call"], help="Target app surface")
    parser.add_argument("--html-var", default=None, help="Python variable holding HTML (default: INDEX_HTML then APP_HTML)")
    parser.add_argument("--blindui", default=None, help="Path to blindui.min.js bundle to validate")
    parser.add_argument("--sso-server", default=None, help="Optional BlindMail server.py for cross-surface SSO route parity")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    report = check_app(
        ui_path=Path(args.ui),
        server_path=Path(args.server),
        surface=args.surface,
        html_var=args.html_var,
        blindui_path=Path(args.blindui) if args.blindui else None,
        sso_server_path=Path(args.sso_server) if args.sso_server else None,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report["ok"]:
            print(
                f"OK [{report['surface']}]: 0 findings "
                f"(scripts={report['scripts_count']}, controls={report['controls_count']})"
            )
        else:
            print(
                f"FAIL [{report['surface']}]: {report['findings_count']} finding(s) "
                f"({report['by_rule']})",
                file=sys.stderr,
            )
            for item in report["findings"]:
                print(f"  [{item['rule']}] {item['detail']}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
