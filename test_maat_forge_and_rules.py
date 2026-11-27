#!/usr/bin/env python3
"""
Counterfactual tests for Maat rules MAAT-12..16, App Forge (maat_forge.py),
template-literal regex tokenization in build_maat.py, and window.Maat === window.BlindUI parity.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import blindui_check  # noqa: E402
import build_maat  # noqa: E402
import maat_check  # noqa: E402
import maat_forge  # noqa: E402


class TestMaatForgeAndRules(unittest.TestCase):
    def test_maat_12_async_boot_and_waterfall_counterfactual(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maat12_") as td:
            bad = Path(td) / "bad.html"
            bad.write_text(
                "<!doctype html><html><head>"
                "<link rel='stylesheet' href='./a.css'>"
                "<link rel='stylesheet' href='./b.css'>"
                "<link rel='stylesheet' href='./c.css'>"
                "</head><body>"
                "<script type='module' src='./m1.js'></script>"
                "<script type='module' src='./m2.js'></script>"
                "<script type='module' src='./m3.js'></script>"
                "<script>function render(){} async function boot(){ await fetch('/x'); render(); } boot();</script>"
                "</body></html>",
                encoding="ascii",
            )
            rep = maat_check.check_app(bad, rule_prefix="MAAT")
            m12 = [f for f in rep["findings"] if f["rule"] == "MAAT-12"]
            self.assertGreaterEqual(len(m12), 3, f"Expected >= 3 MAAT-12 findings: {rep['findings']}")
            self.assertTrue(all(f.get("suggested_fix") for f in m12))

            good = Path(td) / "good.html"
            good.write_text(
                "<!doctype html><html><head><link rel='stylesheet' href='./a.css'></head><body>"
                "<script>function render(){} function boot(){ render(); } boot();</script>"
                "</body></html>",
                encoding="ascii",
            )
            rep_ok = maat_check.check_app(good, rule_prefix="MAAT")
            self.assertEqual([f for f in rep_ok["findings"] if f["rule"] == "MAAT-12"], [])

    def test_maat_13_vendor_palette_and_triangle_hex_decoded(self) -> None:
        # Hex-decode vendor palette and SVG path at runtime so 0 literals exist in repo.
        hexes = [bytes.fromhex(h).decode("ascii") for h in ("23343238356634", "23666262633034", "23333461383533", "23656134333335")]
        tri = bytes.fromhex("4d382e35203468376c362031302e35").decode("ascii")
        with tempfile.TemporaryDirectory(prefix="maat13_") as td:
            bad = Path(td) / "clone.html"
            bad.write_text(
                f"<!doctype html><html><head><style>.a{{color:{hexes[0]};background:{hexes[1]};border-color:{hexes[2]};outline-color:{hexes[3]}}}</style></head>"
                f"<body><svg viewBox='0 0 24 24'><path d='{tri}'/></svg></body></html>",
                encoding="ascii",
            )
            rep = maat_check.check_app(bad, rule_prefix="MAAT")
            m13 = [f for f in rep["findings"] if f["rule"] == "MAAT-13"]
            self.assertEqual(len(m13), 2, f"Expected 2 MAAT-13 findings: {rep['findings']}")
            self.assertTrue(all(f.get("suggested_fix") for f in m13))

    def test_maat_14_strict_csp_portability(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maat14_") as td:
            bad = Path(td) / "csp_bad.html"
            bad.write_text(
                "<!doctype html><html><head>"
                "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Inter'>"
                "<style>@import url('https://cdn.jsdelivr.net/npm/x/a.css');</style>"
                "</head><body>"
                "<img src='/assets/a.png' alt='x'>"
                "<iframe src='https://example.com'></iframe>"
                "</body></html>",
                encoding="ascii",
            )
            rep = maat_check.check_app(bad, rule_prefix="MAAT")
            m14 = [f for f in rep["findings"] if f["rule"] == "MAAT-14"]
            self.assertGreaterEqual(len(m14), 4, f"Expected >= 4 MAAT-14 findings: {rep['findings']}")
            self.assertTrue(all(f.get("suggested_fix") for f in m14))

    def test_maat_15_mobile_row_and_swipe_scoping(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maat15_") as td:
            bad = Path(td) / "bad_m15.html"
            bad.write_text(
                "<!doctype html><html><head><style>"
                ".inbox-row { display: flex; }"
                ".msg-swipe-wrap { display: block; }"
                "</style></head><body>"
                "<svg><text x='50' y='50'>raw</text></svg>"
                "<script>function draw(s,a,b){ var x=(a+b)/2; return svg('text',{x:x},'lbl'); }</script>"
                "</body></html>",
                encoding="ascii",
            )
            rep_bad = maat_check.check_app(bad, rule_prefix="MAAT")
            m15_bad = [f for f in rep_bad["findings"] if f["rule"] == "MAAT-15"]
            self.assertGreaterEqual(len(m15_bad), 3, f"Expected >= 3 MAAT-15 findings: {rep_bad['findings']}")

            # Verify no false positives on desktop .admin-list-item, descendant swipe state selectors,
            # or merged base + mobile @media declarations.
            good = Path(td) / "good_m15.html"
            good.write_text(
                "<!doctype html><html><head><style>"
                ".admin-list-item { display: flex; }"
                ".msg-swipe-wrap { display: contents; }"
                "@media (max-width: 768px) {"
                "  .msg-swipe-wrap { display: block; flex-shrink: 0; overflow: hidden; touch-action: pan-y; }"
                "  .msg-swipe-wrap.swiping-left .swipe-bg-trash { opacity: 1; }"
                "  .inbox-row { display: flex; flex-shrink: 0; touch-action: pan-y; }"
                "}"
                "</style></head><body></body></html>",
                encoding="ascii",
            )
            rep_good = maat_check.check_app(good, rule_prefix="MAAT")
            self.assertEqual([f for f in rep_good["findings"] if f["rule"] == "MAAT-15"], [])

    def test_template_literal_with_regex_containing_backtick(self) -> None:
        src = "const s = `a ${x.replace(/`/g, '\\\\`')} b`; function ok() { return s; }"
        toks = build_maat.tokenize_js(src)
        self.assertTrue(any(k == "ident" and v == "ok" for k, v, _ in toks))

    def test_bad_legacy_vs_forged_workspace_and_all_archetypes(self) -> None:
        bad_path = HERE / "examples" / "app-forge" / "bad_legacy_app.html"
        bad_rep = maat_check.check_app(bad_path, rule_prefix="MAAT")
        bad_12_14 = [f for f in bad_rep["findings"] if f["rule"] in ("MAAT-12", "MAAT-13", "MAAT-14")]
        self.assertGreaterEqual(len(bad_12_14), 4, f"Expected >= 4 MAAT-12..14 findings: {bad_rep['findings']}")
        self.assertTrue(all(f.get("suggested_fix") for f in bad_12_14))

        spec = json.loads((HERE / "examples" / "app-forge" / "workspace_spec.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="maat_forge_test_") as td:
            out_ws = Path(td) / "ws"
            maat_forge.forge_app(spec, out_ws)
            ver = maat_forge.verify_forged_app(out_ws, browser=True)
            self.assertTrue(ver["static"]["ok"], f"Static findings: {ver['static']['findings']}")
            self.assertTrue(ver["browser"]["ok"], f"Browser findings: {ver['browser']}")
            for vp in ("desktop", "mobile"):
                v = ver["browser"]["viewports"][vp]
                self.assertTrue(v["alias_ok"])
                self.assertEqual(v["findings_count"], 0)
                self.assertLess(v["mount_ms"], 15.0)

            # Verify all 4 archetypes forge cleanly and sql-studio passes live browser ERD pill lint.
            for arch in maat_forge.ARCHETYPES:
                out_a = Path(td) / arch
                maat_forge.forge_app({"name": f"Test {arch}", "archetype": arch, "brandColor": "#38bdf8"}, out_a)
                ver_a = maat_forge.verify_forged_app(out_a, browser=(arch == "sql-studio"))
                self.assertTrue(ver_a["ok"], f"{arch} verification failed: {ver_a}")

    def test_maat_self_audit_and_blindui_compat_aliases(self) -> None:
        self_rep = maat_check.run_self_audit(HERE)
        self.assertTrue(self_rep["ok"], f"Self audit failed: {self_rep['findings']}")
        self.assertEqual(set(self_rep["forged_archetypes"]), set(maat_forge.ARCHETYPES))

        # Verify blindui_check defaults to legacy BUI-* prefix for rules 01..11
        with tempfile.TemporaryDirectory(prefix="bui_compat_") as td:
            p = Path(td) / "x.html"
            p.write_text("<!doctype html><html><body><button id='orphan'>Go</button></body></html>", encoding="ascii")
            rep_bui = blindui_check.check_app(p)
            self.assertTrue(any(f["rule"] == "BUI-04" for f in rep_bui["findings"]))

        # Verify window.Maat === window.BlindUI in Node
        proc = subprocess.run(
            [
                "node",
                "-e",
                "globalThis.window = globalThis;"
                "require('./maat.min.js');"
                "require('./maat-kit.min.js');"
                "require('./maat-layout-lint.min.js');"
                "if (window.Maat !== window.BlindUI) process.exit(2);"
                "if (typeof window.Maat.lintLayout !== 'function') process.exit(3);"
                "if (window.Maat.lintLayout !== window.BlindUI.lintLayout) process.exit(4);"
                "if (window.Maat.kit !== window.BlindUI.kit) process.exit(5);",
            ],
            cwd=str(HERE),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"Node alias check failed: {proc.stderr}")


if __name__ == "__main__":
    unittest.main()
