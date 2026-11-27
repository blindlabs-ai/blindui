#!/usr/bin/env python3
"""
Counterfactual Playwright runner for the BlindUI Layout Linter mobile inbox example.
Verifies broken_mobile_inbox.html produces > 0 findings with suggestedFix and
fixed_mobile_inbox.html produces exactly 0 findings at 375x812.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BROKEN_HTML = HERE / "broken_mobile_inbox.html"
FIXED_HTML = HERE / "fixed_mobile_inbox.html"
SAMPLE_REPORT = HERE / "sample_report.json"


def _summarize(findings: list[dict]) -> dict:
    by_rule: dict[str, int] = {}
    for item in findings:
        r = str(item.get("rule", "UNKNOWN"))
        by_rule[r] = by_rule.get(r, 0) + 1
    samples = []
    seen_rules: set[str] = set()
    for item in findings:
        r = str(item.get("rule", ""))
        if r not in seen_rules:
            seen_rules.add(r)
            samples.append(item)
    return {
        "findings_count": len(findings),
        "by_rule": by_rule,
        "sample_findings": samples,
    }


def run_demo() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(f"Playwright is required to run the browser demo: {exc}") from exc

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    with sync_playwright() as p:
        browser = (
            p.chromium.launch(executable_path=chrome, headless=True)
            if chrome
            else p.chromium.launch(headless=True)
        )
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, has_touch=True, is_mobile=True)
        page = ctx.new_page()

        page.goto(BROKEN_HTML.as_uri(), wait_until="load")
        broken_findings = page.evaluate("() => window.BlindUI.lintLayout(document.body)")

        page.goto(FIXED_HTML.as_uri(), wait_until="load")
        fixed_findings = page.evaluate("() => window.BlindUI.lintLayout(document.body)")

        browser.close()

    broken_sum = _summarize(broken_findings)
    fixed_sum = _summarize(fixed_findings)
    ok = (
        broken_sum["findings_count"] > 0
        and broken_sum["by_rule"].get("LINT-FLEX-SHRINK-CLIP", 0) > 0
        and broken_sum["by_rule"].get("LINT-SIBLING-OVERLAP", 0) > 0
        and all(bool(item.get("suggestedFix")) for item in broken_sum["sample_findings"])
        and fixed_sum["findings_count"] == 0
    )
    return {
        "ok": ok,
        "viewport": {"width": 375, "height": 812},
        "broken": broken_sum,
        "fixed": fixed_sum,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BlindUI layout linter mobile inbox demo")
    parser.add_argument("--write-sample", action="store_true", help="Write report to sample_report.json")
    args = parser.parse_args(argv)

    report = run_demo()
    text = json.dumps(report, indent=2) + "\n"
    if args.write_sample:
        SAMPLE_REPORT.write_text(text, encoding="ascii")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
