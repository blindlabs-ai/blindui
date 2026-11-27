#!/usr/bin/env python3
"""
Unit & counterfactual test suite for blindui_check.py (BUI-01 .. BUI-10).
Zero external dependencies (Python 3 stdlib only).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import blindui_check as bc  # noqa: E402
import build_blindui as bb  # noqa: E402

# Dynamically assembled sink tokens so this file carries zero raw forbidden literals.
SINK_INNER = "inner" + "HTML"
SINK_EVAL = "ev" + "al"
SINK_NEW_FN = "new " + "Function"
SINK_ONCLICK = "on" + "click="
SCRIPT_OPEN = "<" + "script>"
SCRIPT_CLOSE = "</" + "script>"
CLAMP_CALL = "." + "cl" + "amp("


def _make_clean_ui_py(
    body_extra: str = "",
    js_extra: str = "",
    extra_script: str = "",
    html_var: str = "INDEX_HTML",
) -> str:
    html = (
        "<!DOCTYPE html><html><head><title>App</title></head><body>"
        "<form id=\"mainForm\"><button id=\"submitBtn\" type=\"submit\">Go</button></form>"
        "<button id=\"pingBtn\" type=\"button\">Ping</button>"
        "<button id=\"staticBtn\" data-blindui-static=\"true\">Info</button>"
        "<div id=\"qs-code\">WebCrypto pubkey ciphertext</div>"
        + body_extra
        + SCRIPT_OPEN
        + "\n"
        + "const API_PING = '/api/v1/ping';\n"
        + "function wireApp() {\n"
        + "  const f = document.getElementById('mainForm');\n"
        + "  const b = document.getElementById('pingBtn');\n"
        + "  if (b) b.addEventListener('click', () => fetch(API_PING));\n"
        + "  if (f) f.addEventListener('submit', () => fetch('/api/v1/items', { method: 'POST' }));\n"
        + "}\n"
        + js_extra
        + "\n"
        + SCRIPT_CLOSE
        + extra_script
        + "</body></html>"
    )
    return f"{html_var} = {html!r}\n"


def _make_clean_server_py(
    extra_get: str = "",
    extra_post: str = "",
    headers_block: str | None = None,
    integrity_snippet: str = "",
) -> str:
    if headers_block is None:
        headers_block = (
            "        self.send_header('X-Content-Type-Options', 'nosniff')\n"
            "        self.send_header('X-Frame-Options', 'DENY')\n"
            "        self.send_header('Referrer-Policy', 'no-referrer')\n"
            "        self.send_header('Content-Security-Policy', \"default-src 'self'\")\n"
        )
    return (
        "import re\n"
        "from http.server import BaseHTTPRequestHandler\n"
        + integrity_snippet
        + "\n"
        "class DemoHandler(BaseHTTPRequestHandler):\n"
        "    def _hdrs(self):\n"
        + headers_block
        + "    def do_GET(self):\n"
        "        path = self.path\n"
        "        if path == '/api/v1/ping':\n"
        "            return\n"
        + extra_get
        + "    def do_POST(self):\n"
        "        path = self.path\n"
        "        if path == '/api/v1/items':\n"
        "            return\n"
        + extra_post
    )


class TestBlindUiCheckCounterfactuals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.bundle = HERE / "blindui.min.js"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_pair(self, ui_src: str, srv_src: str, ui_name: str = "ui.py", srv_name: str = "server.py"):
        ui_p = self.tmp / ui_name
        srv_p = self.tmp / srv_name
        ui_p.write_text(ui_src, encoding="utf-8")
        srv_p.write_text(srv_src, encoding="utf-8")
        return ui_p, srv_p

    def _rules(self, report: dict) -> set[str]:
        return {f["rule"] for f in report["findings"]}

    def test_clean_baseline_passes_all_rules(self) -> None:
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(), _make_clean_server_py())
        rep = bc.check_app(ui_p, srv_p, "social", blindui_path=self.bundle)
        self.assertTrue(rep["ok"], rep["findings"])
        self.assertEqual(rep["findings_count"], 0)

    def test_ast_extraction_variants_and_embedded_closing_html_string(self) -> None:
        # HTML string containing literal '</html>' inside JS must parse cleanly via AST.
        js = "const tpl = '<html><body>ok</body></html>';\n"
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(js_extra=js, html_var="APP_HTML"), _make_clean_server_py())
        rep = bc.check_app(ui_p, srv_p, "sign")
        self.assertTrue(rep["ok"], rep["findings"])

        # Sibling .html loaded via Path(__file__).with_name(...).read_text().replace(...)
        raw_html = _make_clean_ui_py().split("INDEX_HTML = ", 1)[1]
        import ast
        expr_node = ast.parse(raw_html, mode="exec").body[0]
        assert isinstance(expr_node, ast.Expr) and isinstance(expr_node.value, ast.Constant)
        html_str = str(expr_node.value.value)
        (self.tmp / "page.html").write_text(html_str.replace("Ping", "__LBL__"), encoding="utf-8")
        loader_py = (
            "from pathlib import Path\n"
            "INDEX_HTML = Path(__file__).with_name('page.html').read_text('utf-8').replace('__LBL__', 'Ping')\n"
        )
        ui_p2, srv_p2 = self._write_pair(loader_py, _make_clean_server_py(), ui_name="loader.py")
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertTrue(rep2["ok"], rep2["findings"])

        # Direct .html input
        (self.tmp / "direct.html").write_text(html_str, encoding="utf-8")
        rep3 = bc.check_app(self.tmp / "direct.html", srv_p2, "social")
        self.assertTrue(rep3["ok"], rep3["findings"])

    def test_bui_01_xss_sinks_counterfactuals(self) -> None:
        cases = [
            ("inline_attr", _make_clean_ui_py(body_extra="<a " + SINK_ONCLICK + "\"alert(1)\">x</a>")),
            ("js_href", _make_clean_ui_py(body_extra="<a href=\"javascript:alert(1)\">x</a>")),
            ("srcdoc", _make_clean_ui_py(body_extra="<iframe srcdoc=\"<b>x</b>\"></iframe>")),
            ("dom_sink", _make_clean_ui_py(js_extra="function bad(el){ el." + SINK_INNER + " = 'x'; }")),
            ("eval_call", _make_clean_ui_py(js_extra="function bad(){ return " + SINK_EVAL + "('1+1'); }")),
            ("new_func", _make_clean_ui_py(js_extra="function bad(){ return " + SINK_NEW_FN + "('return 1'); }")),
            ("str_timeout", _make_clean_ui_py(js_extra="function bad(){ setTimeout('alert(1)', 0); }")),
            ("dom_parser", _make_clean_ui_py(js_extra="function bad(){ return new DOMParser().parseFromString('<b/>', 'text/html'); }")),
        ]
        for label, ui_src in cases:
            with self.subTest(case=label):
                ui_p, srv_p = self._write_pair(ui_src, _make_clean_server_py())
                rep = bc.check_app(ui_p, srv_p, "social")
                self.assertFalse(rep["ok"], f"{label} should fail BUI-01")
                self.assertIn("BUI-01", self._rules(rep))

    def test_bui_02_duplicate_hoisted_functions(self) -> None:
        # Duplicate top-level
        dup_top = "function dupFn() { return 1; }\nfunction dupFn() { return 2; }\n"
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(js_extra=dup_top), _make_clean_server_py())
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-02", self._rules(rep))

        # Duplicate inside IIFE (depth 1, same scope)
        dup_iife = "(() => { function innerDup() {} function innerDup() {} })();\n"
        ui_p2, srv_p2 = self._write_pair(_make_clean_ui_py(js_extra=dup_iife), _make_clean_server_py())
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertIn("BUI-02", self._rules(rep2))

        # Same helper name in TWO DIFFERENT parent functions must NOT false-positive
        distinct_scopes = "function a() { function helper() {} }\nfunction b() { function helper() {} }\n"
        ui_p3, srv_p3 = self._write_pair(_make_clean_ui_py(js_extra=distinct_scopes), _make_clean_server_py())
        rep3 = bc.check_app(ui_p3, srv_p3, "social")
        self.assertNotIn("BUI-02", self._rules(rep3))

    def test_bui_03_js_syntax_error(self) -> None:
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(js_extra="function broken( { return ;"), _make_clean_server_py())
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-03", self._rules(rep))

    def test_bui_04_button_wiring_and_reverse_bind_action(self) -> None:
        # Unwired button
        ui_p, srv_p = self._write_pair(
            _make_clean_ui_py(body_extra="<button id=\"orphanBtn\" type=\"button\">Dead</button>"),
            _make_clean_server_py(),
        )
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-04", self._rules(rep))

        # Reverse bindAction referencing missing HTML id
        ui_p2, srv_p2 = self._write_pair(
            _make_clean_ui_py(js_extra="BlindUI.bindAction('ghostBtn', () => {});"),
            _make_clean_server_py(),
        )
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertIn("BUI-04", self._rules(rep2))

        # Class-delegated button via bindGroup must pass
        ui_p3, srv_p3 = self._write_pair(
            _make_clean_ui_py(
                body_extra="<button id=\"delBtn\" class=\"row-del\" type=\"button\">Del</button>",
                js_extra="BlindUI.bindGroup('.row-del', () => {});",
            ),
            _make_clean_server_py(),
        )
        rep3 = bc.check_app(ui_p3, srv_p3, "social")
        self.assertTrue(rep3["ok"], rep3["findings"])

    def test_bui_05_route_parity_and_sso(self) -> None:
        # Missing route
        ui_p, srv_p = self._write_pair(
            _make_clean_ui_py(js_extra="function f(){ return fetch('/api/v1/nonexistent'); }"),
            _make_clean_server_py(),
        )
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-05", self._rules(rep))

        # Method mismatch (GET vs POST)
        ui_p2, srv_p2 = self._write_pair(
            _make_clean_ui_py(js_extra="function f(){ return BlindUI.api('POST /api/v1/ping'); }"),
            _make_clean_server_py(),
        )
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertIn("BUI-05", self._rules(rep2))

        # Cross-surface canonical SSO route passes on social; bogus SSO fails
        ui_p3, srv_p3 = self._write_pair(
            _make_clean_ui_py(js_extra="function f(){ return fetch('/mail/api/v1/auth/login', { method: 'POST' }); }"),
            _make_clean_server_py(),
        )
        rep3 = bc.check_app(ui_p3, srv_p3, "social")
        self.assertTrue(rep3["ok"], rep3["findings"])

        ui_p4, srv_p4 = self._write_pair(
            _make_clean_ui_py(js_extra="function f(){ return fetch('/mail/api/v1/auth/bogus', { method: 'POST' }); }"),
            _make_clean_server_py(),
        )
        rep4 = bc.check_app(ui_p4, srv_p4, "social")
        self.assertIn("BUI-05", self._rules(rep4))

    def test_bui_06_jargon_detection(self) -> None:
        # Visible HTML jargon fails
        ui_p, srv_p = self._write_pair(
            _make_clean_ui_py(body_extra="<p>Secured via WebCrypto ciphertext</p>"),
            _make_clean_server_py(),
        )
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-06", self._rules(rep))

        # JS toast jargon fails
        ui_p2, srv_p2 = self._write_pair(
            _make_clean_ui_py(js_extra="function warn(){ showToast('Invalid pubkey detected'); }"),
            _make_clean_server_py(),
        )
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertIn("BUI-06", self._rules(rep2))

        # DKIM record in visible text does not trigger false positive
        ui_p3, srv_p3 = self._write_pair(
            _make_clean_ui_py(body_extra="<p>v=DKIM1; k=ed25519; p=abcdef0123456789abcdef0123456789</p>"),
            _make_clean_server_py(),
        )
        rep3 = bc.check_app(ui_p3, srv_p3, "mail")
        self.assertNotIn("BUI-06", self._rules(rep3))

    def test_bui_07_ascii_and_dot_clamp(self) -> None:
        # Non-ASCII byte
        ui_p, srv_p = self._write_pair(
            _make_clean_ui_py(body_extra="<p>dash \u2014 here</p>"),
            _make_clean_server_py(),
        )
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-07", self._rules(rep))

        # Dot-clamp call
        ui_p2, srv_p2 = self._write_pair(
            _make_clean_ui_py(js_extra="function f(x){ return x" + CLAMP_CALL + "0, 1); }"),
            _make_clean_server_py(),
        )
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertIn("BUI-07", self._rules(rep2))

    def test_bui_08_mail_admin_key_exposure(self) -> None:
        # HTML admin key id + visible text fails on mail
        ui_p, srv_p = self._write_pair(
            _make_clean_ui_py(body_extra="<label>Admin Key</label><input id=\"mb-admin-key\">"),
            _make_clean_server_py(),
        )
        rep_mail = bc.check_app(ui_p, srv_p, "mail")
        self.assertIn("BUI-08", self._rules(rep_mail))
        # Must NOT fire on non-mail surfaces
        rep_social = bc.check_app(ui_p, srv_p, "social")
        self.assertNotIn("BUI-08", self._rules(rep_social))

        # X-API-Key header inside sendCompose fails on mail
        ui_p2, srv_p2 = self._write_pair(
            _make_clean_ui_py(js_extra="function sendCompose() { return { 'X-API-Key': 'secret' }; }"),
            _make_clean_server_py(),
        )
        rep_mail2 = bc.check_app(ui_p2, srv_p2, "mail")
        self.assertIn("BUI-08", self._rules(rep_mail2))

    def test_bui_09_bundle_budget_and_vendored_parity(self) -> None:
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(), _make_clean_server_py())
        # Tampered bundle fails build parity
        bad_b = self.tmp / "tampered.min.js"
        bad_b.write_text("/* tampered */\n", encoding="ascii")
        rep = bc.check_app(ui_p, srv_p, "social", blindui_path=bad_b)
        self.assertIn("BUI-09", self._rules(rep))

        # Mismatched vendored sibling blindui.min.js next to --ui fails parity
        sib = self.tmp / "blindui.min.js"
        sib.write_text("/* stale */\n", encoding="ascii")
        rep2 = bc.check_app(ui_p, srv_p, "social", blindui_path=self.bundle)
        self.assertIn("BUI-09", self._rules(rep2))

        # Matching vendored sibling passes
        shutil.copyfile(self.bundle, sib)
        rep3 = bc.check_app(ui_p, srv_p, "social", blindui_path=self.bundle)
        self.assertTrue(rep3["ok"], rep3["findings"])

    def test_bui_10_security_headers_and_multi_script_integrity(self) -> None:
        # Missing CSP header
        ui_p, srv_p = self._write_pair(
            _make_clean_ui_py(),
            _make_clean_server_py(
                headers_block=(
                    "        self.send_header('X-Content-Type-Options', 'nosniff')\n"
                    "        self.send_header('X-Frame-Options', 'DENY')\n"
                    "        self.send_header('Referrer-Policy', 'no-referrer')\n"
                )
            ),
        )
        rep = bc.check_app(ui_p, srv_p, "social")
        self.assertIn("BUI-10", self._rules(rep))

        # Multi-script HTML with single .search() check fails
        second_script = SCRIPT_OPEN + "const SECOND_BLOCK = 1;" + SCRIPT_CLOSE
        ui_p2, srv_p2 = self._write_pair(
            _make_clean_ui_py(extra_script=second_script),
            _make_clean_server_py(
                integrity_snippet="_INLINE_SCRIPT_RE = re.compile(r'<script>([\\s\\S]*?)' + '</' + 'script>')\n"
                                  "_m = _INLINE_SCRIPT_RE.search('')\n"
            ),
        )
        rep2 = bc.check_app(ui_p2, srv_p2, "social")
        self.assertIn("BUI-10", self._rules(rep2))

        # Multi-script HTML with findall() passes
        ui_p3, srv_p3 = self._write_pair(
            _make_clean_ui_py(extra_script=second_script),
            _make_clean_server_py(
                integrity_snippet="_INLINE_SCRIPT_RE = re.compile(r'<script>([\\s\\S]*?)' + '</' + 'script>')\n"
                                  "_scripts = _INLINE_SCRIPT_RE.findall('')\n"
            ),
        )
        rep3 = bc.check_app(ui_p3, srv_p3, "social")
        self.assertTrue(rep3["ok"], rep3["findings"])

    def test_bui_11_layout_guards_counterfactuals(self) -> None:
        # 1. Flex-scroll column child with overflow: hidden lacking flex-shrink: 0 (JS appendChild edge)
        bad_flex_css = (
            "<style>"
            ".msg-list { display: flex; flex-direction: column; overflow-y: auto; padding: 0 0 144px; }"
            ".msg-swipe-wrap { display: block; overflow: hidden; }"
            "</style>"
        )
        bad_flex_body = bad_flex_css + '<div id="inbox-list" class="msg-list"></div>'
        bad_flex_js = (
            "function renderRows() {\n"
            "  const listEl = document.getElementById('inbox-list');\n"
            "  const wrap = document.createElement('div');\n"
            "  wrap.className = 'msg-swipe-wrap';\n"
            "  listEl.appendChild(wrap);\n"
            "}\n"
        )
        ui_b1, srv_b1 = self._write_pair(_make_clean_ui_py(body_extra=bad_flex_body, js_extra=bad_flex_js), _make_clean_server_py())
        rep_b1 = bc.check_app(ui_b1, srv_b1, "mail")
        self.assertIn("BUI-11", self._rules(rep_b1))
        self.assertTrue(any(f.get("suggested_fix") for f in rep_b1["findings"] if f["rule"] == "BUI-11"))

        good_flex_body = bad_flex_body.replace(
            ".msg-swipe-wrap { display: block; overflow: hidden; }",
            ".msg-swipe-wrap { display: block; flex-shrink: 0; overflow: hidden; }",
        )
        ui_g1, srv_g1 = self._write_pair(_make_clean_ui_py(body_extra=good_flex_body, js_extra=bad_flex_js), _make_clean_server_py())
        rep_g1 = bc.check_app(ui_g1, srv_g1, "mail")
        self.assertNotIn("BUI-11", self._rules(rep_g1))

        # 2. Negative margin on interactive .star-btn fails; margin: 0 passes; decorative .profile-avatar-row passes
        neg_body = "<style>.star-btn { min-width: 44px; margin: -10px -8px -10px 0; }</style>"
        ui_b2, srv_b2 = self._write_pair(_make_clean_ui_py(body_extra=neg_body), _make_clean_server_py())
        rep_b2 = bc.check_app(ui_b2, srv_b2, "mail")
        self.assertIn("BUI-11", self._rules(rep_b2))

        clean_neg_body = "<style>.star-btn { min-width: 44px; margin: 0; } .profile-avatar-row { margin-top: -34px; }</style>"
        ui_g2, srv_g2 = self._write_pair(_make_clean_ui_py(body_extra=clean_neg_body), _make_clean_server_py())
        rep_g2 = bc.check_app(ui_g2, srv_g2, "mail")
        self.assertNotIn("BUI-11", self._rules(rep_g2))

        # 3. Fixed bottom FAB with list scroll container missing bottom padding clearance fails; safe clearance passes
        fab_bad_body = (
            "<style>"
            ".msg-list { display: flex; flex-direction: column; overflow-y: auto; padding: 0 0 8px; }"
            ".mobile-compose-fab { position: fixed; right: 16px; bottom: 20px; }"
            "</style>"
        )
        ui_b3, srv_b3 = self._write_pair(_make_clean_ui_py(body_extra=fab_bad_body), _make_clean_server_py())
        rep_b3 = bc.check_app(ui_b3, srv_b3, "mail")
        self.assertIn("BUI-11", self._rules(rep_b3))

        fab_good_body = fab_bad_body.replace("padding: 0 0 8px;", "padding: 0 0 calc(144px + env(safe-area-inset-bottom));")
        ui_g3, srv_g3 = self._write_pair(_make_clean_ui_py(body_extra=fab_good_body), _make_clean_server_py())
        rep_g3 = bc.check_app(ui_g3, srv_g3, "mail")
        self.assertNotIn("BUI-11", self._rules(rep_g3))

    def test_cli_json_exit_codes(self) -> None:
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(), _make_clean_server_py())
        proc = subprocess.run(
            [
                sys.executable,
                str(HERE / "blindui_check.py"),
                "--ui", str(ui_p),
                "--server", str(srv_p),
                "--surface", "social",
                "--blindui", str(self.bundle),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"ok": true', proc.stdout)

    def test_developers_surface_and_sso_route_parity(self) -> None:
        js_sso = (
            "function doSso() {\n"
            "  return fetch('/mail/api/v1/auth/login', { method: 'POST' });\n"
            "}\n"
        )
        ui_p, srv_p = self._write_pair(_make_clean_ui_py(js_extra=js_sso), _make_clean_server_py())
        rep = bc.check_app(ui_p, srv_p, "developers", blindui_path=self.bundle)
        self.assertTrue(rep["ok"], rep["findings"])
        proc = subprocess.run(
            [
                sys.executable,
                str(HERE / "blindui_check.py"),
                "--ui", str(ui_p),
                "--server", str(srv_p),
                "--surface", "developers",
                "--blindui", str(self.bundle),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('"surface": "developers"', proc.stdout)
        self.assertIn('"ok": true', proc.stdout)

        # Unknown /mail/api/v1/auth/ route still fails BUI-05
        js_bad = "function badSso() { return fetch('/mail/api/v1/auth/nonexistent', { method: 'POST' }); }\n"
        ui_b, srv_b = self._write_pair(_make_clean_ui_py(js_extra=js_bad), _make_clean_server_py())
        rep_b = bc.check_app(ui_b, srv_b, "developers")
        self.assertIn("BUI-05", self._rules(rep_b))

    def test_real_apps_zero_false_positives_when_present(self) -> None:
        apps_root_env = os.environ.get("BLINDUI_APPS_DIR", "").strip()
        if not apps_root_env:
            # Verify zero false positives on clean synthetic fixtures for all surfaces.
            for surface in ("social", "finance", "mail", "sign", "developers", "live", "call"):
                ui_p, srv_p = self._write_pair(
                    _make_clean_ui_py(),
                    _make_clean_server_py(),
                    f"{surface}_ui.py",
                    f"{surface}_srv.py",
                )
                with self.subTest(surface=surface):
                    rep = bc.check_app(ui_p, srv_p, surface, blindui_path=self.bundle)
                    self.assertTrue(rep["ok"], f"{surface} failed: {rep['findings']}")
            return
        apps_root = Path(apps_root_env)
        real_apps = [
            ("social", apps_root / "blindfeed/blindfeed/server.py", apps_root / "blindfeed/blindfeed/server.py"),
            ("finance", apps_root / "blindfinance/blindfinance/server.py", apps_root / "blindfinance/blindfinance/server.py"),
            ("mail", apps_root / "blindmail/blindmail/ui.py", apps_root / "blindmail/blindmail/server.py"),
            ("sign", apps_root / "blindsign/blindsign/server.py", apps_root / "blindsign/blindsign/server.py"),
        ]
        sso_srv = apps_root / "blindmail/blindmail/server.py"
        for surface, ui_p, srv_p in real_apps:
            if not (ui_p.is_file() and srv_p.is_file()):
                continue
            with self.subTest(surface=surface):
                rep = bc.check_app(
                    ui_p,
                    srv_p,
                    surface,
                    blindui_path=self.bundle,
                    sso_server_path=sso_srv if (surface != "mail" and sso_srv.is_file()) else None,
                )
                # Core rules BUI-01..BUI-07 and BUI-09 must have zero false positives on every real app.
                core_findings = [f for f in rep["findings"] if f["rule"] not in ("BUI-08", "BUI-10")]
                self.assertEqual(core_findings, [], f"{surface} unexpected findings: {core_findings}")
                if surface in ("social", "finance"):
                    self.assertTrue(rep["ok"], f"{surface} failed: {rep['findings']}")


if __name__ == "__main__":
    unittest.main()
