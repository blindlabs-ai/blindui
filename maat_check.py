#!/usr/bin/env python3
"""
Maat Static Validator (MAAT-01 .. MAAT-16, compatible with BUI-01 .. BUI-11).

Zero external dependencies (Python 3 stdlib + sibling build_maat.py only).
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
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import build_maat as build_blindui  # noqa: E402

# Hex-decoded vendor trademark patterns so this repo has 0 raw literal hits.
_VENDOR_HEX_COMBO: Tuple[str, ...] = tuple(
    bytes.fromhex(h).decode("ascii")
    for h in (
        "23343238356634",
        "23666262633034",
        "23333461383533",
        "23656134333335",
    )
)
_VENDOR_TRIANGLE_PATH = bytes.fromhex("4d382e35203468376c362031302e35").decode("ascii").lower()
_EXTERNAL_CDN_RE = re.compile(
    r"(?:https?:)?//(?:fonts\.googleapis\.com|fonts\.gstatic\.com|unpkg\.com|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|ajax\.googleapis\.com)",
    re.IGNORECASE,
)
_CSS_EXTERNAL_IMPORT_RE = re.compile(
    r"@import\s+(?:url\s*\(\s*)?['\"]?(?:https?:)?//[^)'\"\s]+",
    re.IGNORECASE,
)
_VENDOR_JS_BASENAMES = frozenset({
    "maat.js", "maat.min.js", "maat-kit.js", "maat-kit.min.js",
    "maat-layout-lint.js", "maat-layout-lint.min.js",
    "blindui.js", "blindui.min.js", "blindui-kit.js", "blindui-kit.min.js",
    "blindui-layout-lint.js", "blindui-layout-lint.min.js",
})

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
    r"#\s*(?:maat|blindui)-route\s*:\s*(GET|POST|PUT|DELETE|PATCH)\s+(/\S*)",
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
    """Single-pass HTMLParser collecting XSS, controls, IDs, CSP/waterfall tags, SVG text, and visible text."""

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
        self.module_script_srcs: List[str] = []
        self.external_script_srcs: List[str] = []
        self.local_script_srcs: List[str] = []
        self.stylesheet_links: List[str] = []
        self.external_link_hrefs: List[str] = []
        self.iframe_srcs: List[str] = []
        self.bad_img_srcs: List[str] = []
        self.svg_stack: List[Dict[str, Any]] = []
        self.erd_lbl_g_depth = 0
        self.svg_raw_midpoint_texts: List[str] = []

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

        if self.in_template == 0:
            if t == "script":
                src_v = attr_map.get("src", "").strip()
                stype = attr_map.get("type", "").strip().lower()
                if src_v:
                    if stype == "module":
                        self.module_script_srcs.append(src_v)
                    if src_v.lower().startswith(("http://", "https://", "//")):
                        self.external_script_srcs.append(src_v)
                    elif not src_v.lower().startswith(("data:", "blob:")):
                        self.local_script_srcs.append(src_v)
            elif t == "link":
                rel_v = attr_map.get("rel", "").strip().lower()
                href_v = attr_map.get("href", "").strip()
                if "stylesheet" in rel_v.split() and href_v:
                    self.stylesheet_links.append(href_v)
                if href_v.lower().startswith(("http://", "https://", "//")):
                    self.external_link_hrefs.append(href_v)
            elif t == "iframe":
                src_v = attr_map.get("src", "").strip()
                if src_v and src_v.lower() != "about:blank":
                    self.iframe_srcs.append(src_v)
            elif t == "img":
                src_v = attr_map.get("src", "").strip()
                if src_v and not src_v.lower().startswith("data:"):
                    self.bad_img_srcs.append(src_v)
            elif t == "svg":
                self.svg_stack.append({"has_edge": False, "raw_texts": []})
            elif self.svg_stack:
                if t in ("line", "path", "polyline"):
                    self.svg_stack[-1]["has_edge"] = True
                elif t == "g":
                    gcls = attr_map.get("class", "").split()
                    if "erd-edge-lbl" in gcls or "erd-lbl-group" in gcls or self.erd_lbl_g_depth > 0:
                        self.erd_lbl_g_depth += 1
                elif t == "text":
                    anchor = attr_map.get("text-anchor", "").strip().lower()
                    is_mid = anchor == "middle" or attr_map.get("data-midpoint", "").strip().lower() == "true"
                    has_offset = any(k in attr_map for k in ("dy", "dx", "transform", "data-offset"))
                    if is_mid and not has_offset and self.erd_lbl_g_depth == 0:
                        tid = attr_map.get("id", "") or f"x={attr_map.get('x', '?')},y={attr_map.get('y', '?')}"
                        self.svg_stack[-1]["raw_texts"].append(tid)

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
            static_opt = (
                attr_map.get("data-blindui-static", "").strip().lower() == "true"
                or attr_map.get("data-maat-static", "").strip().lower() == "true"
            )
            self.controls.append({
                "id": el_id,
                "tag": t,
                "classes": classes,
                "data_attrs": data_attrs,
                "parent_form_id": parent_form_id,
                "is_submit": is_submit,
                "static_opt_out": static_opt,
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
        if t == "g" and self.erd_lbl_g_depth > 0:
            self.erd_lbl_g_depth -= 1
        if t == "svg" and self.svg_stack:
            info = self.svg_stack.pop()
            if info["has_edge"] and info["raw_texts"]:
                self.svg_raw_midpoint_texts.extend(info["raw_texts"])
        if self.skip_qs_depth > 0:
            self.skip_qs_depth -= 1
        if t == "form" and self.form_stack:
            self.form_stack.pop()

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        self.handle_starttag(tag, attrs)
        if t == "script" and self.in_script > 0:
            self.in_script -= 1
        elif t == "style" and self.in_style > 0:
            self.in_style -= 1
        elif t == "svg" and self.svg_stack:
            info = self.svg_stack.pop()
            if info["has_edge"] and info["raw_texts"]:
                self.svg_raw_midpoint_texts.extend(info["raw_texts"])
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


def _adding_finding(
    findings: List[Dict[str, str]],
    rule: str,
    detail: str,
    suggested_fix: Optional[str] = None,
) -> None:
    item: Dict[str, str] = {"rule": rule, "detail": detail}
    if suggested_fix:
        item["suggested_fix"] = suggested_fix
    findings.append(item)


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
            elif v == "api" and i >= 2 and toks[i - 1][1] == "." and toks[i - 2][1] in ("BlindUI", "Maat") and i + 1 < n and toks[i + 1][1] == "(":
                caller = toks[i - 2][1] + ".api"
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
    server_path: Optional[Path],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-09 / MAAT-09: Bundle budget (< 28672 B), deterministic build parity, and vendored SHA-256 parity."""
    if blindui_path is None:
        return
    if not blindui_path.is_file():
        _adding_finding(findings, "BUI-09", f"--blindui/--maat target not found: {blindui_path}")
        return
    raw = blindui_path.read_bytes()
    if len(raw) >= build_blindui.MAX_BUNDLE_BYTES:
        _adding_finding(
            findings,
            "BUI-09",
            f"{blindui_path.name} size {len(raw)} B >= budget {build_blindui.MAX_BUNDLE_BYTES} B",
        )
    src_candidate: Optional[Path] = None
    for cand_name in ("maat.js", "blindui.js"):
        c = blindui_path.with_name(cand_name)
        if c.is_file():
            src_candidate = c
            break
    if src_candidate is None:
        for cand_name in ("maat.js", "blindui.js"):
            c = _HERE / cand_name
            if c.is_file():
                src_candidate = c
                break
    if src_candidate is not None and src_candidate.is_file():
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
    parents = [ui_path.resolve().parent]
    if server_path is not None:
        parents.append(server_path.resolve().parent)
    for parent in parents:
        for sib_name in ("maat.min.js", "blindui.min.js"):
            sib = parent / sib_name
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


_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>([\s\S]*?)</style>", re.IGNORECASE)
_LINK_CSS_RE = re.compile(r"<link\b([^>]+)>", re.IGNORECASE)
_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})
_BUI11_NEG_MARGIN_SEL_RE = re.compile(
    r"(?:\b(?:button|a|input)\b|\.(?:[a-z0-9_-]*(?:btn|star|chip|tab|pill|badge|link|action|msg-row|list-item|nav-item)[a-z0-9_-]*))",
    re.IGNORECASE,
)
_BUI11_FAB_NAV_RE = re.compile(
    r"(?:fab|bottom-nav|bottom-bar|tab-bar|sticky-bar|footer-bar|dock)",
    re.IGNORECASE,
)
_BUI11_LIST_SCROLL_RE = re.compile(
    r"(?:list|feed|inbox|timeline|stream|rows|threads|messages)",
    re.IGNORECASE,
)
_BUI11_OVERLAY_SCROLL_RE = re.compile(
    r"(?:drawer|modal|dialog|overlay|compose|editor|sheet|popover)",
    re.IGNORECASE,
)


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def _parse_css_decls(body: str) -> Dict[str, str]:
    decls: Dict[str, str] = {}
    for part in body.split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        kl = k.strip().lower()
        vl = v.strip()
        if kl and vl:
            decls[kl] = vl
    return decls


def _parse_css_rules(css: str, scope: str = "base") -> List[Tuple[str, str, Dict[str, str]]]:
    """Recursively parse CSS blocks into [(scope, selector, decls_dict), ...]."""
    out: List[Tuple[str, str, Dict[str, str]]] = []
    n = len(css)
    i = 0
    while i < n:
        while i < n and css[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        start = i
        while i < n and css[i] not in "{;":
            i += 1
        if i >= n:
            break
        if css[i] == ";":
            i += 1
            continue
        header = re.sub(r"\s+", " ", css[start:i]).strip()
        depth = 1
        i += 1
        bstart = i
        while i < n and depth > 0:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        body = css[bstart:i - 1]
        if not header:
            continue
        if header.startswith("@"):
            low_h = header.lower()
            if low_h.startswith(("@media", "@supports", "@layer", "@container")):
                out.extend(_parse_css_rules(body, scope=header))
            continue
        decls = _parse_css_decls(body)
        if not decls:
            continue
        for raw_sel in header.split(","):
            sel = re.sub(r"\s+", " ", raw_sel).strip()
            if sel:
                out.append((scope, sel, decls))
    return out


def _css_len_px(tok: str) -> Optional[float]:
    t = tok.strip().lower()
    if t == "0":
        return 0.0
    m = re.match(r"^(-?\d+(?:\.\d+)?)(px|rem|em)$", t)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2)
    return val * 16.0 if unit in ("rem", "em") else val


def _extract_neg_margins(decls: Dict[str, str]) -> List[Tuple[str, str, float]]:
    hits: List[Tuple[str, str, float]] = []
    for prop in ("margin-top", "margin-bottom", "margin-left", "margin-right"):
        if prop in decls:
            raw = decls[prop].replace("!important", "").strip()
            px = _css_len_px(raw)
            if px is not None and px <= -4.0:
                hits.append((prop, decls[prop], px))
    if "margin" in decls:
        raw = decls["margin"].replace("!important", "").strip()
        parts = raw.split()
        if 1 <= len(parts) <= 4:
            for tok in parts:
                px = _css_len_px(tok)
                if px is not None and px <= -4.0:
                    hits.append(("margin", decls["margin"], px))
                    break
    return hits


def _has_no_shrink(decls: Dict[str, str]) -> bool:
    fs = decls.get("flex-shrink", "").replace("!important", "").strip().lower()
    if fs == "0" or (fs.startswith("0.") and float(fs) == 0.0):
        return True
    fx = decls.get("flex", "").replace("!important", "").strip().lower()
    if fx == "none":
        return True
    if fx:
        parts = fx.split()
        if len(parts) >= 2 and parts[1] == "0":
            return True
    return False


def _is_flex_grow_fill(decls: Dict[str, str]) -> bool:
    """Return True if an element explicitly flex-grows to fill remaining space (e.g. flex: 1)."""
    fg = decls.get("flex-grow", "").replace("!important", "").strip().lower()
    if fg and fg != "0":
        return True
    fx = decls.get("flex", "").replace("!important", "").strip().lower()
    if fx and fx not in ("none", "initial", "0"):
        parts = fx.split()
        if parts and parts[0] not in ("0", "auto", "none") and not parts[0].endswith(("px", "%", "rem", "em", "vh", "vw")):
            return True
    return False


def _sel_leaf_tokens(sel: str) -> Set[str]:
    """Return class/id tokens from the rightmost compound selector (ignoring pseudo-classes)."""
    right = re.split(r"[\s>+~]+", sel.strip())[-1]
    right = re.sub(r"::?(?:[a-zA-Z0-9_-]+(?:\([^)]*\))?)", "", right)
    toks: Set[str] = set()
    for m in re.finditer(r"([.#][A-Za-z0-9_-]+)", right):
        toks.add(m.group(1))
    return toks


class _NestingParser(HTMLParser):
    """Collect static HTML parent->child class/id relationships and id->classes mapping."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: List[Tuple[str, Set[str]]] = []
        self.edges: Dict[str, Set[str]] = {}
        self.id_classes: Dict[str, Set[str]] = {}
        self.in_raw = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if t in ("script", "style"):
            self.in_raw += 1
            return
        if self.in_raw:
            return
        toks: Set[str] = set()
        el_id = ""
        cls_set: Set[str] = set()
        for k, v in attrs:
            kl = k.lower()
            val = (v or "").strip()
            if kl == "id" and val:
                el_id = "#" + val
                toks.add(el_id)
            elif kl == "class" and val:
                for c in val.split():
                    cls_set.add("." + c)
                    toks.add("." + c)
        if el_id and cls_set:
            self.id_classes.setdefault(el_id, set()).update(cls_set)
        if self.stack and toks:
            ptoks = self.stack[-1][1]
            for pt in ptoks:
                self.edges.setdefault(pt, set()).update(toks)
        if t not in _VOID_TAGS:
            self.stack.append((t, toks))

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("script", "style"):
            if self.in_raw > 0:
                self.in_raw -= 1
            return
        if self.in_raw:
            return
        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == t:
                del self.stack[idx:]
                break


def _extract_js_dom_edges(
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    id_classes: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    """Correlate JS getElementById/querySelector/className with appendChild/append calls in order."""
    edges: Dict[str, Set[str]] = {}
    for _, toks in tokenized_scripts:
        var_toks: Dict[str, Set[str]] = {}
        n = len(toks)
        for i, (k, v, _) in enumerate(toks):
            # const listEl = document.getElementById("inbox-list") / querySelector("#x" / ".y")
            if k == "ident" and v in ("getElementById", "querySelector") and i + 3 < n and toks[i + 1][1] == "(" and toks[i + 2][0] == "str":
                arg = _unquote_js_string(toks[i + 2][1]).strip()
                target_toks: Set[str] = set()
                if v == "getElementById" and arg:
                    el_id = "#" + arg
                    target_toks.add(el_id)
                    target_toks.update(id_classes.get(el_id, ()))
                elif arg:
                    target_toks.update(_sel_leaf_tokens(arg))
                    for tok in list(target_toks):
                        if tok.startswith("#"):
                            target_toks.update(id_classes.get(tok, ()))
                j = i - 1
                while j >= 1 and toks[j][1] != "=" and i - j < 8:
                    j -= 1
                if j >= 1 and toks[j][1] == "=" and toks[j - 1][0] == "ident":
                    var_toks[toks[j - 1][1]] = set(target_toks)
            # const wrap = document.createElement("div") -> reset binding for this variable
            elif k == "ident" and v == "createElement" and i + 3 < n and toks[i + 1][1] == "(":
                j = i - 1
                while j >= 1 and toks[j][1] != "=" and i - j < 8:
                    j -= 1
                if j >= 1 and toks[j][1] == "=" and toks[j - 1][0] == "ident":
                    var_toks[toks[j - 1][1]] = set()
            # wrap.className = "msg-swipe-wrap"
            elif k == "ident" and v == "className" and i >= 2 and toks[i - 1][1] == "." and toks[i - 2][0] == "ident":
                if i + 2 < n and toks[i + 1][1] == "=" and toks[i + 2][0] == "str":
                    var = toks[i - 2][1]
                    var_toks[var] = {"." + c for c in _unquote_js_string(toks[i + 2][1]).split() if c}
            # wrap.classList.add("msg-swipe-wrap")
            elif k == "ident" and v == "add" and i >= 4 and toks[i - 1][1] == "." and toks[i - 2][1] == "classList" and toks[i - 3][1] == "." and toks[i - 4][0] == "ident":
                if i + 1 < n and toks[i + 1][1] == "(":
                    args, _ = _split_call_args(toks, i + 1)
                    var = toks[i - 4][1]
                    for arg in args:
                        if len(arg) == 1 and arg[0][0] == "str":
                            for c in _unquote_js_string(arg[0][1]).split():
                                var_toks.setdefault(var, set()).add("." + c)
            # parent.appendChild(child) / parent.append(child)
            elif k == "ident" and v in ("appendChild", "append") and i >= 2 and toks[i - 1][1] == "." and toks[i - 2][0] == "ident":
                if i + 1 < n and toks[i + 1][1] == "(":
                    pvar = toks[i - 2][1]
                    ptoks = var_toks.get(pvar)
                    if not ptoks:
                        continue
                    args, _ = _split_call_args(toks, i + 1)
                    for arg in args:
                        if len(arg) == 1 and arg[0][0] == "ident":
                            ctoks = var_toks.get(arg[0][1])
                            if ctoks:
                                for pt in ptoks:
                                    edges.setdefault(pt, set()).update(ctoks)
    return edges


def _check_bui_11(
    html: str,
    ui_path: Path,
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """BUI-11: Static CSS layout & overlap guard (flex-scroll shrink-clip, negative margins, fixed FAB clearance)."""
    css_chunks: List[str] = [m.group(1) for m in _STYLE_BLOCK_RE.finditer(html)]
    base_dir = ui_path.resolve().parent
    for m in _LINK_CSS_RE.finditer(html):
        attrs = m.group(1)
        if not re.search(r'\brel\s*=\s*["\']?stylesheet\b', attrs, re.IGNORECASE):
            continue
        hm = re.search(r'\bhref\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        if not hm:
            continue
        href = hm.group(1).strip()
        if href.lower().startswith(("http://", "https://", "//", "data:")):
            continue
        css_p = (base_dir / href.lstrip("/")).resolve() if not href.startswith("./") else (base_dir / href).resolve()
        if not css_p.is_file():
            css_p = (base_dir / href).resolve()
        if css_p.is_file():
            css_chunks.append(css_p.read_text("utf-8", errors="replace"))

    if not css_chunks:
        return

    all_rules: List[Tuple[str, str, Dict[str, str]]] = []
    for chunk in css_chunks:
        all_rules.extend(_parse_css_rules(_strip_css_comments(chunk)))
    if not all_rules:
        return

    # Merge declarations per (scope, selector) and compute effective maps (base + scope override).
    by_scope: Dict[str, Dict[str, Dict[str, str]]] = {}
    for sc, sel, decls in all_rules:
        by_scope.setdefault(sc, {}).setdefault(sel, {}).update(decls)
    base_map = by_scope.get("base", {})
    scopes = list(by_scope.keys())

    # Collect HTML + JS parent -> child relationships.
    nest = _NestingParser()
    nest.feed(html)
    nest.close()
    edges: Dict[str, Set[str]] = {k: set(v) for k, v in nest.edges.items()}
    for k, v in _extract_js_dom_edges(tokenized_scripts, nest.id_classes).items():
        edges.setdefault(k, set()).update(v)

    seen_flex: Set[Tuple[str, str, str]] = set()
    seen_neg: Set[Tuple[str, str, str]] = set()
    seen_fab: Set[Tuple[str, str]] = set()

    for sc in scopes:
        eff: Dict[str, Dict[str, str]] = {}
        all_sels = set(base_map.keys()) | set(by_scope.get(sc, {}).keys())
        for sel in all_sels:
            merged: Dict[str, str] = {}
            if sel in base_map:
                merged.update(base_map[sel])
            if sc != "base" and sel in by_scope.get(sc, {}):
                merged.update(by_scope[sc][sel])
            eff[sel] = merged

        # 1. Flex-scroll child shrink/clip trap
        flex_scroll_parents: List[Tuple[str, Set[str]]] = []
        for sel, decls in eff.items():
            disp = decls.get("display", "").replace("!important", "").strip().lower()
            fdir = decls.get("flex-direction", "").replace("!important", "").strip().lower()
            fflow = decls.get("flex-flow", "").replace("!important", "").strip().lower()
            ovy = decls.get("overflow-y", "").replace("!important", "").strip().lower()
            ov = decls.get("overflow", "").replace("!important", "").strip().lower()
            is_flex = disp in ("flex", "inline-flex")
            is_col = fdir.startswith("column") or "column" in fflow
            is_scroll = ovy in ("auto", "scroll") or ov in ("auto", "scroll")
            if is_flex and is_col and is_scroll:
                ptoks = _sel_leaf_tokens(sel)
                if ptoks:
                    flex_scroll_parents.append((sel, ptoks))

        for p_sel, ptoks in flex_scroll_parents:
            if _BUI11_OVERLAY_SCROLL_RE.search(p_sel):
                continue
            child_toks: Set[str] = set()
            for pt in ptoks:
                child_toks.update(edges.get(pt, ()))
            if not child_toks:
                continue
            for c_sel, c_decls in eff.items():
                if c_sel == p_sel:
                    continue
                ctoks = _sel_leaf_tokens(c_sel)
                if not (ctoks & child_toks):
                    continue
                c_disp = c_decls.get("display", "").replace("!important", "").strip().lower()
                c_pos = c_decls.get("position", "").replace("!important", "").strip().lower()
                if c_disp in ("none", "contents") or c_pos in ("absolute", "fixed"):
                    continue
                if _is_flex_grow_fill(c_decls) or "aspect-ratio" in c_decls:
                    continue
                c_ov = c_decls.get("overflow", "").replace("!important", "").strip().lower()
                c_ovy = c_decls.get("overflow-y", "").replace("!important", "").strip().lower()
                if (c_ov in ("hidden", "clip") or c_ovy in ("hidden", "clip")) and not _has_no_shrink(c_decls):
                    key = (sc, p_sel, c_sel)
                    if key not in seen_flex:
                        seen_flex.add(key)
                        _adding_finding(
                            findings,
                            "BUI-11",
                            f"Flex-scroll child '{c_sel}' inside '{p_sel}' ({sc}) sets overflow hidden without flex-shrink: 0 (CSS Flexbox 4.5 collapse trap)",
                            suggested_fix=f"Add 'flex-shrink: 0;' to {c_sel} inside flex scroll container {p_sel}",
                        )

        # 2. Negative-margin sibling/interactive collision (check declarations introduced in this scope)
        for sel, decls in by_scope.get(sc, {}).items():
            if not _BUI11_NEG_MARGIN_SEL_RE.search(sel):
                continue
            for prop, val, _ in _extract_neg_margins(decls):
                key = (sc, sel, prop)
                if key not in seen_neg:
                    seen_neg.add(key)
                    _adding_finding(
                        findings,
                        "BUI-11",
                        f"Negative margin ({prop}: {val}) on '{sel}' ({sc}) risks overlapping adjacent siblings",
                        suggested_fix=f"Remove negative margin on {sel} and use padding or parent flex/grid gap instead",
                    )

        # 3. Fixed bottom FAB/nav overlapping scroll container lacking bottom padding clearance
        fixed_bottom_bars: List[str] = []
        for sel, decls in eff.items():
            if not _BUI11_FAB_NAV_RE.search(sel):
                continue
            disp = decls.get("display", "").replace("!important", "").strip().lower()
            pos = decls.get("position", "").replace("!important", "").strip().lower()
            if disp == "none" or pos != "fixed":
                continue
            if "inset" in decls or ("top" in decls and "bottom" in decls):
                continue
            if "bottom" in decls:
                fixed_bottom_bars.append(sel)

        if fixed_bottom_bars:
            for p_sel, _ in flex_scroll_parents:
                if _BUI11_OVERLAY_SCROLL_RE.search(p_sel) or not _BUI11_LIST_SCROLL_RE.search(p_sel):
                    continue
                p_decls = eff.get(p_sel, {})
                pb_raw = p_decls.get("padding-bottom", "")
                pad_raw = p_decls.get("padding", "")
                has_clearance = False
                if "calc(" in pb_raw or "env(" in pb_raw or "calc(" in pad_raw or "env(" in pad_raw:
                    has_clearance = True
                elif pb_raw:
                    px = _css_len_px(pb_raw.replace("!important", "").strip())
                    if px is not None and px >= 48.0:
                        has_clearance = True
                elif pad_raw:
                    parts = pad_raw.replace("!important", "").strip().split()
                    btok = parts[0] if len(parts) == 1 else (parts[0] if len(parts) == 2 else parts[2])
                    px = _css_len_px(btok)
                    if px is not None and px >= 48.0:
                        has_clearance = True
                if not has_clearance:
                    key = (sc, p_sel)
                    if key not in seen_fab:
                        seen_fab.add(key)
                        _adding_finding(
                            findings,
                            "BUI-11",
                            f"Scroll container '{p_sel}' ({sc}) lacks bottom padding clearance for fixed {fixed_bottom_bars[0]}",
                            suggested_fix=f"Add bottom padding (e.g. 'padding-bottom: calc(120px + env(safe-area-inset-bottom));') to {p_sel}",
                        )


_BOOT_FN_RE = re.compile(r"^(?:boot|init)(?:[A-Z0-9_].*)?$")
_RENDER_FN_RE = re.compile(r"^(?:render|mount|paint|draw|shell)(?:[A-Z0-9_].*)?$")
_MAAT15_ROW_SEL_RE = re.compile(
    r"^\.[a-z0-9_-]*(?:inbox-row|thread-row|mail-row|msg-row|file-row|feed-row|list-row)$",
    re.IGNORECASE,
)
_MAAT15_MOBILE_ROW_SEL_RE = re.compile(
    r"^\.[a-z0-9_-]*(?:list-row|list-item|inbox-row|thread-row|mail-row|msg-row|file-row|feed-row)$",
    re.IGNORECASE,
)
_MAAT15_SWIPE_SEL_RE = re.compile(
    r"^(?:\.[a-z0-9_-]*swipe-(?:wrap|row)|\[data-swipe\])$",
    re.IGNORECASE,
)


def _load_local_css_chunks(html: str, ui_path: Path) -> Tuple[List[str], List[Path]]:
    css_chunks: List[str] = [m.group(1) for m in _STYLE_BLOCK_RE.finditer(html)]
    css_files: List[Path] = []
    base_dir = ui_path.resolve().parent
    for m in _LINK_CSS_RE.finditer(html):
        attrs = m.group(1)
        if not re.search(r'\brel\s*=\s*["\']?stylesheet\b', attrs, re.IGNORECASE):
            continue
        hm = re.search(r'\bhref\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        if not hm:
            continue
        href = hm.group(1).strip()
        if href.lower().startswith(("http://", "https://", "//", "data:")):
            continue
        css_p = (base_dir / href.lstrip("/")).resolve() if not href.startswith("./") else (base_dir / href).resolve()
        if not css_p.is_file():
            css_p = (base_dir / href).resolve()
        if css_p.is_file():
            css_files.append(css_p)
            css_chunks.append(css_p.read_text("utf-8", errors="replace"))
    return css_chunks, css_files


def _scan_async_boot_body(
    body: List[Tuple[str, str, bool]],
    idx_lbl: str,
    fn_label: str,
    findings: List[Dict[str, str]],
) -> None:
    first_await: Optional[int] = None
    first_render: Optional[int] = None
    m = len(body)
    for j, (tk, tv, _) in enumerate(body):
        if tk == "ident" and tv == "await" and first_await is None:
            first_await = j
        elif tk == "ident" and _RENDER_FN_RE.match(tv) and j + 1 < m and body[j + 1][1] == "(":
            if first_render is None:
                first_render = j
    if first_await is not None and (first_render is None or first_await < first_render):
        _adding_finding(
            findings,
            "MAAT-12",
            f"{idx_lbl}: async {fn_label} awaits before first synchronous render() (blocks frame-1 paint)",
            suggested_fix="Render the initial shell synchronously on frame 1, then run async crypto/network hydration in the background.",
        )


def _extract_brace_block(toks: List[Tuple[str, str, bool]], open_idx: int) -> List[Tuple[str, str, bool]]:
    n = len(toks)
    if open_idx >= n or toks[open_idx][1] != "{":
        return []
    depth = 1
    j = open_idx + 1
    while j < n and depth > 0:
        if toks[j][1] == "{":
            depth += 1
        elif toks[j][1] == "}":
            depth -= 1
        j += 1
    return toks[open_idx + 1:j - 1]


def _check_maat_12(
    dom: _DomInspector,
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """MAAT-12 (NO-ASYNC-BOOT-WATERFALL): No await before frame-1 render, <= 2 module scripts/stylesheets."""
    if len(dom.module_script_srcs) > 2:
        _adding_finding(
            findings,
            "MAAT-12",
            f"Entry HTML loads {len(dom.module_script_srcs)} external <script type='module'> waterfall tags (max 2)",
            suggested_fix="Bundle application code into a single synchronous ./app.bundle.js without module waterfall chains.",
        )
    if len(dom.stylesheet_links) > 2:
        _adding_finding(
            findings,
            "MAAT-12",
            f"Entry HTML loads {len(dom.stylesheet_links)} external <link rel='stylesheet'> waterfall tags (max 2)",
            suggested_fix="Consolidate stylesheets into <= 2 local files (e.g. ./maat-tokens.css and ./app.bundle.css).",
        )

    for sc, toks in tokenized_scripts:
        idx_lbl = sc.get("label") or f"script[{sc['index']}]@L{sc['line']}"
        n = len(toks)
        for i, (k, v, _) in enumerate(toks):
            # async function boot(...) { ... }
            if k == "ident" and v == "async" and i + 2 < n and toks[i + 1][1] == "function" and toks[i + 2][0] == "ident":
                fn_name = toks[i + 2][1]
                if _BOOT_FN_RE.match(fn_name):
                    j = i + 3
                    while j < n and toks[j][1] != "{":
                        j += 1
                    body = _extract_brace_block(toks, j)
                    _scan_async_boot_body(body, idx_lbl, f"{fn_name}()", findings)
            # const boot = async () => { ... }
            elif k == "ident" and _BOOT_FN_RE.match(v) and i + 2 < n and toks[i + 1][1] == "=" and toks[i + 2][1] == "async":
                j = i + 3
                while j < n and toks[j][1] not in ("{", ";"):
                    j += 1
                if j < n and toks[j][1] == "{":
                    body = _extract_brace_block(toks, j)
                    _scan_async_boot_body(body, idx_lbl, f"{v}()", findings)
            # addEventListener("DOMContentLoaded", async () => { ... })
            elif k == "ident" and v == "addEventListener" and i + 1 < n and toks[i + 1][1] == "(":
                args, _ = _split_call_args(toks, i + 1)
                if len(args) >= 2 and len(args[0]) == 1 and args[0][0][0] == "str":
                    evt = _unquote_js_string(args[0][0][1])
                    if evt in ("DOMContentLoaded", "load") and args[1] and args[1][0][1] == "async":
                        b_idx = next((ix for ix, tk in enumerate(args[1]) if tk[1] == "{"), -1)
                        if b_idx >= 0:
                            body = _extract_brace_block(args[1], b_idx)
                            _scan_async_boot_body(body, idx_lbl, f"{evt} handler", findings)


def _check_maat_13(
    combined_texts: Sequence[Tuple[str, str]],
    findings: List[Dict[str, str]],
) -> None:
    """MAAT-13 (NO-VENDOR-TRADEMARK-CLONES): Flag vendor 4-color hex combos or trademark Drive triangle paths."""
    merged_low = "\n".join(txt for _, txt in combined_texts).lower()
    matched_hexes = [hx for hx in _VENDOR_HEX_COMBO if hx in merged_low]
    if len(matched_hexes) >= 3:
        _adding_finding(
            findings,
            "MAAT-13",
            f"Detected third-party lookalike multi-color brand palette ({len(matched_hexes)}/4 trademark hex colors)",
            suggested_fix="Replace third-party trademark palette hexes with Maat obsidian tokens (--bui-accent) and original brand colors.",
        )
    norm_ws = re.sub(r"\s+", " ", merged_low)
    if _VENDOR_TRIANGLE_PATH in norm_ws:
        _adding_finding(
            findings,
            "MAAT-13",
            "Detected third-party lookalike Drive triangle SVG path",
            suggested_fix="Replace third-party triangle SVG paths with bespoke geometric Maat.kit.icon() vectors.",
        )


def _check_maat_14(
    dom: _DomInspector,
    css_chunks: Sequence[str],
    findings: List[Dict[str, str]],
) -> None:
    """MAAT-14 (STRICT-CSP-PORTABILITY): Flag <iframe src=...>, non-data: <img src=...>, and external CDN/font URLs."""
    for src_v in dom.iframe_srcs:
        _adding_finding(
            findings,
            "MAAT-14",
            f"Disallowed <iframe src={src_v[:60]!r}> violates strict CSP frame-src 'none' portability",
            suggested_fix="Remove <iframe src=...> or render content natively via Maat Safe-DOM primitives.",
        )
    for src_v in dom.bad_img_srcs:
        _adding_finding(
            findings,
            "MAAT-14",
            f"External/path <img src={src_v[:60]!r}> violates strict CSP img-src data: portability",
            suggested_fix="Replace external or path-based <img> tags with inline Maat.svg() vectors or data: URIs.",
        )
    for url in dom.external_script_srcs:
        _adding_finding(
            findings,
            "MAAT-14",
            f"External script URL {url[:64]!r} violates zero-dependency strict CSP portability",
            suggested_fix="Vendor or bundle scripts locally with relative ./ paths and zero third-party CDNs.",
        )
    for url in dom.external_link_hrefs:
        _adding_finding(
            findings,
            "MAAT-14",
            f"External <link href={url[:64]!r}> violates zero-dependency offline CSP portability",
            suggested_fix="Remove external font/CDN links and use local Maat CSS + system font stacks.",
        )
    for chunk in css_chunks:
        m_imp = _CSS_EXTERNAL_IMPORT_RE.search(chunk)
        if m_imp:
            _adding_finding(
                findings,
                "MAAT-14",
                f"CSS external @import {m_imp.group(0)[:64]!r} violates strict CSP portability",
                suggested_fix="Remove external CSS @import rules and inline local styles into app.bundle.css.",
            )
        m_cdn = _EXTERNAL_CDN_RE.search(chunk)
        if m_cdn:
            _adding_finding(
                findings,
                "MAAT-14",
                f"CSS references external font/CDN host {m_cdn.group(0)!r}",
                suggested_fix="Use local assets and system-ui / ui-monospace fonts instead of external CDNs.",
            )


def _check_maat_15(
    dom: _DomInspector,
    css_chunks: Sequence[str],
    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]],
    findings: List[Dict[str, str]],
) -> None:
    """MAAT-15 (TACTILE-MOBILE-AND-SVG-SAFETY): SVG midpoint text offsets & mobile row flex-shrink/touch containment."""
    for tid in dom.svg_raw_midpoint_texts:
        _adding_finding(
            findings,
            "MAAT-15",
            f"SVG <text> ({tid}) placed at raw midpoint without collision offset or pill wrapper",
            suggested_fix="Wrap edge labels in <g class='erd-edge-lbl'> with a .erd-lbl-bg pill or add explicit dy/transform collision offsets.",
        )

    # Check JS for raw midpoint SVG <text> creation without offset/pill
    for sc, toks in tokenized_scripts:
        idx_lbl = sc.get("label") or f"script[{sc['index']}]@L{sc['line']}"
        body = sc.get("body", "")
        if "text" in body and "/ 2" in body:
            has_svg_text = bool(re.search(r'(?:svg|createElementNS)\s*\([^)]*["\']text["\']', body))
            has_midpoint_calc = bool(re.search(r"\(\s*[a-zA-Z0-9_.]+\s*\+\s*[a-zA-Z0-9_.]+\s*\)\s*/\s*2", body))
            has_offset = bool(re.search(r"(?:erd-edge-lbl|erd-lbl-bg|\bdy\b|\btransform\b|labelOffset|collisionOffset)", body))
            if has_svg_text and has_midpoint_calc and not has_offset:
                _adding_finding(
                    findings,
                    "MAAT-15",
                    f"{idx_lbl}: SVG <text> computed at raw midpoint (/ 2) without collision offset or pill container",
                    suggested_fix="Add explicit dy/collisionOffset or wrap SVG edge text inside <g class='erd-edge-lbl'> with a .erd-lbl-bg pill.",
                )

    # Check CSS mobile list rows lacking flex-shrink: 0 and swipe rows lacking touch-action
    if not css_chunks:
        return
    all_rules: List[Tuple[str, str, Dict[str, str]]] = []
    for chunk in css_chunks:
        all_rules.extend(_parse_css_rules(_strip_css_comments(chunk)))
    if not all_rules:
        return

    by_scope: Dict[str, Dict[str, Dict[str, str]]] = {}
    for sc, sel, decls in all_rules:
        by_scope.setdefault(sc, {}).setdefault(sel.strip(), {}).update(decls)
    base_map = by_scope.get("base", {})
    mobile_scopes = [sc for sc in by_scope if sc != "base" and "max-width" in sc.lower()]
    other_scopes = [sc for sc in by_scope if sc != "base" and sc not in mobile_scopes]

    all_sels: Set[str] = set(base_map.keys())
    for scope_map in by_scope.values():
        all_sels.update(scope_map.keys())

    for sel in sorted(all_sels):
        merged: Dict[str, str] = {}
        if sel in base_map:
            merged.update(base_map[sel])
        for sc in other_scopes:
            if sel in by_scope[sc]:
                merged.update(by_scope[sc][sel])
        in_mobile = False
        for sc in mobile_scopes:
            if sel in by_scope[sc]:
                merged.update(by_scope[sc][sel])
                in_mobile = True

        disp = merged.get("display", "").replace("!important", "").strip().lower()
        is_row = bool(_MAAT15_ROW_SEL_RE.match(sel)) or (in_mobile and bool(_MAAT15_MOBILE_ROW_SEL_RE.match(sel)))
        if is_row and disp in ("flex", "inline-flex", "grid") and not _has_no_shrink(merged):
            _adding_finding(
                findings,
                "MAAT-15",
                f"Mobile/list row '{sel}' missing flex-shrink: 0 (risks flex-column compression)",
                suggested_fix=f"Add 'flex-shrink: 0; touch-action: pan-y;' to {sel}.",
            )
        if _MAAT15_SWIPE_SEL_RE.match(sel) and disp not in ("none", "contents"):
            ov = merged.get("overflow", "").replace("!important", "").strip().lower()
            ovx = merged.get("overflow-x", "").replace("!important", "").strip().lower()
            has_contain = ("touch-action" in merged) or (ov in ("hidden", "clip")) or (ovx in ("hidden", "clip"))
            if not has_contain:
                _adding_finding(
                    findings,
                    "MAAT-15",
                    f"Swipe container '{sel}' missing touch-action containment",
                    suggested_fix=f"Add 'touch-action: pan-y; overflow: hidden;' to {sel} to prevent horizontal gesture scroll bleed.",
                )
            if not _has_no_shrink(merged):
                _adding_finding(
                    findings,
                    "MAAT-15",
                    f"Swipe container '{sel}' missing flex-shrink: 0 (risks mobile flex-column collapse)",
                    suggested_fix=f"Add 'flex-shrink: 0; touch-action: pan-y;' to {sel}.",
                )


def _apply_rule_prefix(findings: List[Dict[str, str]], rule_prefix: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in findings:
        copy = dict(item)
        rule = copy["rule"]
        if rule.startswith("BUI-"):
            num = rule[4:]
            if rule_prefix == "MAAT":
                copy["rule"] = f"MAAT-{num}"
                copy["alias"] = f"BUI-{num}"
            else:
                copy["rule"] = f"BUI-{num}"
                copy["alias"] = f"MAAT-{num}"
        out.append(copy)
    return out


def run_self_audit(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """MAAT-16 (SELF-IMMUNE-AUDIT): Audit Maat runtime, kit, linter, tokens, checker, and forge templates."""
    root = (root_dir or _HERE).resolve()
    findings: List[Dict[str, str]] = []

    # 1. Verify deterministic builds, byte budgets, and BlindUI compatibility mirrors
    for src_name, dst_name in (
        ("maat.js", "blindui.js"),
        ("maat-kit.js", "blindui-kit.js"),
        ("maat-layout-lint.js", "blindui-layout-lint.js"),
        ("maat-tokens.css", "blindui-tokens.css"),
    ):
        for err in build_blindui.sync_exact_file(root / src_name, root / dst_name, check_only=True):
            _adding_finding(
                findings,
                "MAAT-16",
                f"Mirror drift: {err}",
                suggested_fix="Run 'python3 build_maat.py --require-node' to resync Maat and BlindUI mirrors.",
            )

    bundle_specs = (
        ("maat.js", "maat.min.js", "blindui.min.js", build_blindui.MAX_BUNDLE_BYTES, False),
        ("maat-kit.js", "maat-kit.min.js", "blindui-kit.min.js", build_blindui.MAX_KIT_BYTES, True),
        ("maat-layout-lint.js", "maat-layout-lint.min.js", "blindui-layout-lint.min.js", build_blindui.MAX_LINT_BYTES, True),
    )
    for src_n, out_n, mirror_n, budget, inc in bundle_specs:
        res = build_blindui.build_and_verify(
            src_path=root / src_n,
            out_path=root / out_n,
            check_only=True,
            sync_paths=[root / mirror_n],
            require_node=True,
            max_bytes=budget,
            inclusive=inc,
        )
        if not res["ok"]:
            for err in res["errors"]:
                _adding_finding(
                    findings,
                    "MAAT-16",
                    f"Bundle check ({out_n}): {err}",
                    suggested_fix="Run 'python3 build_maat.py --require-node' and ensure size stays within budget.",
                )

    tok_res = build_blindui.validate_css_tokens(root / "maat-tokens.css", max_bytes=build_blindui.MAX_TOKENS_BYTES)
    if not tok_res["ok"]:
        for err in tok_res["errors"]:
            _adding_finding(
                findings,
                "MAAT-16",
                f"Tokens check: {err}",
                suggested_fix="Keep maat-tokens.css 100% ASCII, balanced braces, and <= 4096 bytes.",
            )

    # 2. Audit Maat's own Python/JS/CSS sources for ASCII, dot-clamp, XSS sinks, vendor hexes, and CDN URLs
    self_files = [
        "maat.js", "maat-kit.js", "maat-layout-lint.js", "maat-tokens.css",
        "build_maat.py", "build_blindui.py", "maat_check.py", "blindui_check.py",
    ]
    if (root / "maat_forge.py").is_file():
        self_files.append("maat_forge.py")

    checked_files: List[str] = []
    for rel in self_files:
        fp = root / rel
        if not fp.is_file():
            _adding_finding(findings, "MAAT-16", f"Missing core Maat file: {rel}", suggested_fix=f"Restore {rel}.")
            continue
        checked_files.append(rel)
        raw = fp.read_bytes()
        non_ascii = sum(1 for b in raw if b > 0x7F)
        if non_ascii > 0:
            _adding_finding(findings, "MAAT-16", f"{rel}: contains {non_ascii} non-ASCII byte(s)", suggested_fix=f"Convert {rel} to 100% 7-bit ASCII.")
        text = raw.decode("utf-8", errors="replace")
        if _CLAMP_RE.search(text):
            _adding_finding(findings, "MAAT-16", f"{rel}: contains forbidden dot-clamp call", suggested_fix=f"Replace dot-clamp in {rel} with Math.min/Math.max.")
        low = text.lower()
        for needle in (_SINK_INNER_HTML, _SINK_OUTER_HTML, _SINK_INSERT_ADJ_HTML, _SINK_DOC_WRITE, _SINK_DOC_WRITELN):
            if needle.lower() in low:
                _adding_finding(findings, "MAAT-16", f"{rel}: contains raw forbidden sink literal ({needle})", suggested_fix=f"Remove or dynamically construct sink reference in {rel}.")
        if any(hx in low for hx in _VENDOR_HEX_COMBO) or _VENDOR_TRIANGLE_PATH in re.sub(r"\s+", " ", low):
            _adding_finding(findings, "MAAT-16", f"{rel}: contains raw vendor trademark hex/path literal", suggested_fix=f"Hex-decode or remove vendor trademark pattern in {rel}.")
        if rel.endswith((".js", ".css")) and _EXTERNAL_CDN_RE.search(text):
            _adding_finding(findings, "MAAT-16", f"{rel}: contains external CDN/font URL", suggested_fix=f"Remove external CDN URL from {rel}.")

    # 3. Synthesize and self-lint every maat_forge archetype when maat_forge.py is present
    forged_archetypes: List[str] = []
    if (root / "maat_forge.py").is_file():
        import maat_forge  # noqa: E402
        with tempfile.TemporaryDirectory(prefix="maat_self_") as td:
            for arch in maat_forge.ARCHETYPES:
                out_dir = Path(td) / arch
                spec = {
                    "name": f"Self Audit {arch}",
                    "archetype": arch,
                    "brandColor": "#38bdf8",
                    "e2ee": True,
                    "tactileMobile": True,
                }
                maat_forge.forge_app(spec, out_dir)
                rep = check_app(
                    ui_path=out_dir / "index.html",
                    server_path=None,
                    surface="app",
                    blindui_path=out_dir / "maat.min.js",
                    rule_prefix="MAAT",
                )
                forged_archetypes.append(arch)
                if not rep["ok"]:
                    for sub_f in rep["findings"]:
                        _adding_finding(
                            findings,
                            "MAAT-16",
                            f"Forge template '{arch}' failed [{sub_f['rule']}]: {sub_f['detail']}",
                            suggested_fix=sub_f.get("suggested_fix") or f"Fix {arch} template in maat_forge.py.",
                        )

    by_rule: Dict[str, int] = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    return {
        "ok": len(findings) == 0,
        "mode": "self",
        "root": str(root),
        "checked_files": checked_files,
        "forged_archetypes": forged_archetypes,
        "findings_count": len(findings),
        "by_rule": by_rule,
        "findings": findings,
    }


def check_app(
    ui_path: Path,
    server_path: Optional[Path] = None,
    surface: str = "app",
    html_var: Optional[str] = None,
    blindui_path: Optional[Path] = None,
    sso_server_path: Optional[Path] = None,
    rule_prefix: str = "MAAT",
) -> Dict[str, Any]:
    """Run all active MAAT-01..MAAT-15 (BUI-01..BUI-11 compatible) rules and return a structured report."""
    findings: List[Dict[str, str]] = []

    html, html_err = extract_html_from_ui(ui_path, html_var=html_var)
    if html_err or html is None:
        _adding_finding(findings, "BUI-00", html_err or "Failed to extract HTML")
        findings = _apply_rule_prefix(findings, rule_prefix)
        return {
            "ok": False,
            "surface": surface,
            "ui": str(ui_path),
            "server": str(server_path) if server_path is not None else None,
            "findings_count": len(findings),
            "by_rule": {findings[0]["rule"]: len(findings)},
            "findings": findings,
        }

    scripts = extract_scripts(html)
    dom = _DomInspector()
    dom.feed(html)
    dom.close()

    # Load local non-vendor <script src="./..."> files so strict-CSP single-bundle apps are fully audited.
    base_dir = ui_path.resolve().parent
    local_js_paths: List[Path] = []
    next_idx = len(scripts)
    for src_ref in dom.local_script_srcs:
        clean_ref = src_ref.split("?", 1)[0].split("#", 1)[0]
        if Path(clean_ref).name.lower() in _VENDOR_JS_BASENAMES:
            continue
        js_p = (base_dir / clean_ref.lstrip("/")).resolve() if not clean_ref.startswith("./") else (base_dir / clean_ref).resolve()
        if not js_p.is_file():
            js_p = (base_dir / clean_ref).resolve()
        if js_p.is_file() and js_p not in local_js_paths:
            local_js_paths.append(js_p)
            scripts.append({
                "index": next_idx,
                "attrs": f'src="{src_ref}"',
                "body": js_p.read_text("utf-8", errors="replace"),
                "line": 1,
                "is_js": True,
                "label": js_p.name,
            })
            next_idx += 1

    tokenized_scripts: List[Tuple[Dict[str, Any], List[Tuple[str, str, bool]]]] = []
    for sc in scripts:
        if not sc["is_js"] or not sc["body"].strip():
            continue
        try:
            toks = build_blindui.tokenize_js(sc["body"])
        except ValueError as exc:
            lbl = sc.get("label") or f"script[{sc['index']}]@L{sc['line']}"
            _adding_finding(findings, "BUI-03", f"{lbl}: JS tokenization error: {exc}")
            toks = []
        tokenized_scripts.append((sc, toks))

    server_routes: Optional[_ServerRouteSet] = None
    if server_path is not None:
        server_routes, srv_err = extract_server_routes(server_path)
        if srv_err or server_routes is None:
            _adding_finding(findings, "BUI-05", srv_err or "Failed to parse server routes")
            server_routes = _ServerRouteSet()

    sso_routes: Optional[_ServerRouteSet] = None
    if sso_server_path is not None:
        sso_routes, sso_err = extract_server_routes(sso_server_path)
        if sso_err:
            _adding_finding(findings, "BUI-05", sso_err)

    css_chunks, css_files = _load_local_css_chunks(html, ui_path)

    _check_bui_01(html, dom, tokenized_scripts, findings)
    _check_bui_02(tokenized_scripts, findings)
    _check_bui_03(scripts, blindui_path, findings)
    _check_bui_04(dom, tokenized_scripts, findings)
    if server_routes is not None:
        _check_bui_05(tokenized_scripts, server_routes, surface, sso_routes, findings)
    _check_bui_06(dom, tokenized_scripts, findings)

    ascii_targets: List[Tuple[str, Path]] = [("ui", ui_path)]
    if server_path is not None:
        ascii_targets.append(("server", server_path))
    if blindui_path is not None:
        ascii_targets.append(("maat", blindui_path))
    for jp in local_js_paths:
        ascii_targets.append(("script", jp))
    for cp in css_files:
        ascii_targets.append(("style", cp))
    _check_bui_07(ascii_targets, findings)

    _check_bui_08(surface, html, dom, tokenized_scripts, findings)
    _check_bui_09(blindui_path, ui_path, server_path, findings)
    if server_path is not None:
        _check_bui_10(server_path, scripts, findings)
    _check_bui_11(html, ui_path, tokenized_scripts, findings)

    # New Maat anti-bad-code rules (MAAT-12 .. MAAT-15)
    _check_maat_12(dom, tokenized_scripts, findings)
    combined_texts: List[Tuple[str, str]] = [("html", html)]
    for i, c in enumerate(css_chunks):
        combined_texts.append((f"css[{i}]", c))
    for sc, _ in tokenized_scripts:
        combined_texts.append((sc.get("label") or f"script[{sc['index']}]", sc["body"]))
    _check_maat_13(combined_texts, findings)
    _check_maat_14(dom, css_chunks, findings)
    _check_maat_15(dom, css_chunks, tokenized_scripts, findings)

    findings = _apply_rule_prefix(findings, rule_prefix)
    by_rule: Dict[str, int] = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1

    return {
        "ok": len(findings) == 0,
        "surface": surface,
        "ui": str(ui_path),
        "server": str(server_path) if server_path is not None else None,
        "scripts_count": len(scripts),
        "controls_count": len(dom.controls),
        "findings_count": len(findings),
        "by_rule": by_rule,
        "findings": findings,
    }


def main(argv: Optional[List[str]] = None, default_rule_prefix: str = "MAAT") -> int:
    parser = argparse.ArgumentParser(description="Maat static validator (MAAT-01..MAAT-16, BUI-01..BUI-11 compatible)")
    parser.add_argument("--self", dest="self_audit", action="store_true", help="Run MAAT-16 self-immune audit on Maat itself")
    parser.add_argument("--ui", default=None, help="Path to UI .py or .html file")
    parser.add_argument("--server", default=None, help="Optional path to server .py file for route/header parity")
    parser.add_argument(
        "--surface",
        default="app",
        choices=["app", "workspace", "studio", "openapi", "mail", "sign", "social", "finance", "developers", "live", "call"],
        help="Target app surface (default: app)",
    )
    parser.add_argument("--html-var", default=None, help="Python variable holding HTML (default: INDEX_HTML then APP_HTML)")
    parser.add_argument("--maat", "--blindui", dest="blindui", default=None, help="Path to maat.min.js / blindui.min.js bundle")
    parser.add_argument("--sso-server", default=None, help="Optional mail server.py for cross-surface SSO route parity")
    parser.add_argument("--legacy-rules", action="store_true", help="Report rules 01..11 with legacy BUI-* prefix")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    if args.self_audit:
        report = run_self_audit()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            if report["ok"]:
                print(
                    f"OK [MAAT-16 self-immune]: 0 findings "
                    f"(files={len(report['checked_files'])}, archetypes={len(report['forged_archetypes'])})"
                )
            else:
                print(f"FAIL [MAAT-16 self-immune]: {report['findings_count']} finding(s)", file=sys.stderr)
                for item in report["findings"]:
                    print(f"  [{item['rule']}] {item['detail']}", file=sys.stderr)
                    if item.get("suggested_fix"):
                        print(f"    Fix: {item['suggested_fix']}", file=sys.stderr)
        return 0 if report["ok"] else 1

    if not args.ui:
        parser.error("--ui is required unless --self is specified")

    prefix = "BUI" if args.legacy_rules else default_rule_prefix
    report = check_app(
        ui_path=Path(args.ui),
        server_path=Path(args.server) if args.server else None,
        surface=args.surface,
        html_var=args.html_var,
        blindui_path=Path(args.blindui) if args.blindui else None,
        sso_server_path=Path(args.sso_server) if args.sso_server else None,
        rule_prefix=prefix,
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
                if item.get("suggested_fix"):
                    print(f"    Fix: {item['suggested_fix']}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
