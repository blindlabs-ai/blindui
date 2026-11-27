#!/usr/bin/env python3
"""
Counterfactual App Forge demo runner for Maat.

Compares bad_legacy_app.html (>= 4 MAAT-12..14 findings with suggested_fix)
against an auto-synthesized workspace_spec.json app (0 MAAT-01..16 findings,
0 headless Chromium Maat.lintLayout() findings at 1280x800 and 375x812, and
< 15 ms synchronous frame-1 mount).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import maat_check  # noqa: E402
import maat_forge  # noqa: E402

WORKSPACE_SPEC = HERE / "workspace_spec.json"
BAD_LEGACY_HTML = HERE / "bad_legacy_app.html"
SAMPLE_REPORT = HERE / "sample_forge_report.json"


def run_demo(
    out_dir: Optional[Path] = None,
    screenshot: Optional[Path] = None,
    browser: bool = True,
) -> Dict[str, Any]:
    bad_rep = maat_check.check_app(
        ui_path=BAD_LEGACY_HTML,
        server_path=None,
        surface="app",
        rule_prefix="MAAT",
    )
    bad_maat_12_14 = [
        f for f in bad_rep["findings"]
        if f.get("rule") in ("MAAT-12", "MAAT-13", "MAAT-14")
    ]

    spec = json.loads(WORKSPACE_SPEC.read_text(encoding="utf-8"))
    if out_dir is not None:
        forged_info = maat_forge.forge_app(spec, out_dir)
        verify_rep = maat_forge.verify_forged_app(
            out_dir, browser=browser, screenshot=screenshot
        )
    else:
        with tempfile.TemporaryDirectory(prefix="maat_forge_demo_") as td:
            target = Path(td) / "workspace"
            forged_info = maat_forge.forge_app(spec, target)
            verify_rep = maat_forge.verify_forged_app(
                target, browser=browser, screenshot=screenshot
            )

    self_rep = maat_check.run_self_audit(REPO_ROOT)

    bad_ok = (
        len(bad_maat_12_14) >= 4
        and all(bool(f.get("suggested_fix")) for f in bad_maat_12_14)
    )
    forged_ok = bool(verify_rep["ok"]) and verify_rep["static"]["findings_count"] == 0
    overall_ok = bad_ok and forged_ok and bool(self_rep["ok"])

    return {
        "ok": overall_ok,
        "bad_legacy_app": {
            "findings_count": bad_rep["findings_count"],
            "maat_12_14_count": len(bad_maat_12_14),
            "by_rule": bad_rep["by_rule"],
            "sample_findings": bad_maat_12_14[:6],
        },
        "forged_workspace": {
            "name": forged_info["name"],
            "archetype": forged_info["archetype"],
            "brandColor": forged_info["brandColor"],
            "static_findings_count": verify_rep["static"]["findings_count"],
            "browser": verify_rep["browser"],
        },
        "self_audit": {
            "ok": self_rep["ok"],
            "findings_count": self_rep["findings_count"],
            "checked_files": len(self_rep["checked_files"]),
            "forged_archetypes": self_rep["forged_archetypes"],
        },
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run Maat App Forge counterfactual demo")
    parser.add_argument("--out", default=None, help="Optional persistent output directory for forged app")
    parser.add_argument("--screenshot", default=None, help="Optional PNG path for desktop screenshot")
    parser.add_argument("--no-browser", action="store_true", help="Skip headless Chromium verification")
    parser.add_argument("--write-sample", action="store_true", help="Write JSON report to sample_forge_report.json")
    args = parser.parse_args(argv)

    report = run_demo(
        out_dir=Path(args.out) if args.out else None,
        screenshot=Path(args.screenshot) if args.screenshot else None,
        browser=not args.no_browser,
    )
    text = json.dumps(report, indent=2) + "\n"
    if args.write_sample:
        SAMPLE_REPORT.write_text(text, encoding="ascii")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
