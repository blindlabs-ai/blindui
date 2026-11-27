#!/usr/bin/env python3
"""
Top-level Python verification suite for Zero-UI bundles, BUI-11 layout guards,
and the mobile inbox layout-linter example counterfactual.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import blindui_check as bc  # noqa: E402
import build_blindui as bb  # noqa: E402


class TestBlindUiSuite(unittest.TestCase):
    def test_build_check_all_bundles_within_budget(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HERE / "build_blindui.py"), "--check", "--require-node"],
            cwd=str(HERE),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, f"build_blindui --check failed:\n{proc.stdout}\n{proc.stderr}")
        lint_min = HERE / "blindui-layout-lint.min.js"
        self.assertTrue(lint_min.is_file())
        self.assertLessEqual(lint_min.stat().st_size, bb.MAX_LINT_BYTES)

    def test_bui_11_example_html_counterfactual(self) -> None:
        ex_dir = HERE / "examples" / "layout-linter"
        broken_p = ex_dir / "broken_mobile_inbox.html"
        fixed_p = ex_dir / "fixed_mobile_inbox.html"
        self.assertTrue(broken_p.is_file() and fixed_p.is_file())

        def _run_bui11(path: Path) -> list[dict]:
            html = path.read_text("utf-8")
            scripts = bc.extract_scripts(html)
            tok_scripts = [
                (sc, bb.tokenize_js(sc["body"]))
                for sc in scripts
                if sc["is_js"] and sc["body"].strip()
            ]
            findings: list[dict] = []
            bc._check_bui_11(html, path, tok_scripts, findings)
            return findings

        broken_f = _run_bui11(broken_p)
        fixed_f = _run_bui11(fixed_p)
        self.assertGreater(len(broken_f), 0, "Expected BUI-11 findings on broken_mobile_inbox.html")
        self.assertTrue(all(f.get("suggested_fix") for f in broken_f), broken_f)
        self.assertNotEqual(broken_f, fixed_f)
        self.assertEqual(fixed_f, [], f"Expected 0 BUI-11 findings on fixed_mobile_inbox.html: {fixed_f}")

    def test_layout_linter_browser_demo_counterfactual(self) -> None:
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("Playwright not installed")
        if not (shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")):
            self.skipTest("Chromium binary not found")
        demo_py = HERE / "examples" / "layout-linter" / "run_lint_demo.py"
        proc = subprocess.run(
            [sys.executable, str(demo_py)],
            cwd=str(HERE),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, f"run_lint_demo.py failed:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn('"ok": true', proc.stdout)
        self.assertIn('"LINT-FLEX-SHRINK-CLIP"', proc.stdout)
        self.assertIn('"LINT-SIBLING-OVERLAP"', proc.stdout)


if __name__ == "__main__":
    unittest.main()
