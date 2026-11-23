#!/usr/bin/env python3
"""Real headless Chrome browser self-test for BlindUI.notionEditor (Desktop + Mobile)."""

from __future__ import annotations

from pathlib import Path
import shutil
import unittest

BLINDUI_DIR = Path(__file__).resolve().parent
MIN_PATH = BLINDUI_DIR / "blindui.min.js"

_STYLED_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: #090b10; color: #f1f5f9; font-family: system-ui, sans-serif; }
  .wrap { display: flex; flex-direction: column; width: 100%; height: 640px; background: #11151f; }
  .host {
    display: flex; flex-direction: column; flex: 1 1 auto; width: 100%;
    min-height: 180px; overflow-y: auto; padding: 16px 16px 48px; cursor: text;
    font-size: 14px; line-height: 24px;
  }
  .bui-nb { position: relative; margin-bottom: 4px; }
  .bui-nb-ed {
    position: relative; outline: none; min-height: 28px; line-height: 24px;
    margin: 0; padding: 2px 4px; caret-color: #00E08A; cursor: text;
  }
  .bui-nb-ed[data-placeholder]:empty::before,
  .bui-nb-ed.bui-nb-empty[data-placeholder]::before {
    content: attr(data-placeholder); position: absolute; left: 4px; right: 4px; top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    color: #94a3b8; opacity: 0.72; pointer-events: none;
  }
  @media (max-width: 768px) {
    .host, .host .bui-nb, .host .bui-nb-ed { font-size: 16px !important; line-height: 24px; }
  }
</style>
</head>
<body>
<div class="wrap" id="wrap">
  <div class="host" id="editor"></div>
  <textarea id="backing"></textarea>
</div>
</body>
</html>
"""

_UNSTYLED_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;">
<div id="editor" style="min-height:480px;padding:16px;"></div>
</body>
</html>
"""


def _find_chrome() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_viewport_scenario(browser, *, mobile: bool, styled: bool) -> dict:
    ctx_kwargs = (
        {"viewport": {"width": 390, "height": 844}, "has_touch": True, "is_mobile": True}
        if mobile
        else {"viewport": {"width": 1440, "height": 900}, "has_touch": False, "is_mobile": False}
    )
    ctx = browser.new_context(**ctx_kwargs)
    page = ctx.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda err: errors.append(f"pageerror:{err}"))
    page.on("console", lambda msg: errors.append(f"console:{msg.text}") if msg.type == "error" else None)

    try:
        page.set_content(_STYLED_HTML if styled else _UNSTYLED_HTML)
        page.add_script_tag(path=str(MIN_PATH))
        page.evaluate(
            """() => {
              const host = document.getElementById("editor");
              const ta = document.getElementById("backing");
              const opts = {
                placeholder: "Write your message... (# Heading, **bold**, - list, > quote)"
              };
              if (ta) opts.textarea = ta;
              window.__ed = window.BlindUI.notionEditor(host, opts);
            }"""
        )

        # 1. Click/tap lower empty body at hostRect.top + 150px
        box = page.locator("#editor").bounding_box()
        assert box is not None
        tap_x = box["x"] + 60
        tap_y = box["y"] + 150
        if mobile:
            page.touchscreen.tap(tap_x, tap_y)
        else:
            page.mouse.click(tap_x, tap_y)

        page.keyboard.type("Hello from lower body")
        lower_state = page.evaluate(
            """() => {
              const host = document.getElementById("editor");
              const blocks = [...host.children];
              const activeIdx = blocks.findIndex((b) => b.contains(document.activeElement));
              const texts = blocks.map((b) => b.textContent || "");
              const edEl = blocks[activeIdx]?.querySelector(".bui-nb-ed");
              const cs = edEl ? getComputedStyle(edEl) : null;
              return {
                row: activeIdx,
                apiRow: window.__ed.getActiveRow(),
                blockCount: blocks.length,
                texts,
                md: window.__ed.getMarkdown(),
                fontSize: cs ? cs.fontSize : "",
                caretColor: cs ? cs.caretColor : ""
              };
            }"""
        )

        # 2. Roundtrip via setMarkdown(getMarkdown()) preserves exact row
        roundtrip_state = page.evaluate(
            """() => {
              const saved = window.__ed.getMarkdown();
              window.__ed.setMarkdown(saved);
              const host = document.getElementById("editor");
              const texts = [...host.children].map((b) => b.textContent || "");
              return { md: window.__ed.getMarkdown(), saved, texts };
            }"""
        )

        # 3. Row 1 click right below row 0 has zero dead zone
        page.evaluate("() => window.__ed.setMarkdown('')")
        r0 = page.evaluate("() => document.querySelector('#editor .bui-nb').getBoundingClientRect()")
        row1_x = r0["left"] + 40
        row1_y = r0["bottom"] + 12
        if mobile:
            page.touchscreen.tap(row1_x, row1_y)
        else:
            page.mouse.click(row1_x, row1_y)
        row1_idx = page.evaluate("() => window.__ed.getActiveRow()")

        # 4. Existing line click keeps caret on that line
        page.evaluate("() => window.__ed.setMarkdown('Line zero\\n\\nLine one\\n\\nLine two')")
        r1 = page.evaluate(
            "() => document.querySelectorAll('#editor .bui-nb-ed')[1].getBoundingClientRect()"
        )
        ex_x = r1["left"] + 24
        ex_y = r1["top"] + r1["height"] / 2
        if mobile:
            page.touchscreen.tap(ex_x, ex_y)
        else:
            page.mouse.click(ex_x, ex_y)
        existing_row = page.evaluate("() => window.__ed.getActiveRow()")

        # 5. Live Markdown compilation (**bold**, *italic*, # H1)
        page.evaluate("() => { window.__ed.setMarkdown(''); window.__ed.focus(); }")
        page.keyboard.type("# Heading")
        page.keyboard.press("Enter")
        page.keyboard.type("Mix **bold** and *italic* text")
        md_compile = page.evaluate(
            """() => {
              const host = document.getElementById("editor");
              return {
                hasH1: !!host.querySelector("h1"),
                hasStrong: !!host.querySelector("strong"),
                hasEm: !!host.querySelector("em"),
                strongText: host.querySelector("strong")?.textContent || "",
                emText: host.querySelector("em")?.textContent || "",
                md: window.__ed.getMarkdown()
              };
            }"""
        )

        return {
            "lower": lower_state,
            "roundtrip": roundtrip_state,
            "row1_idx": row1_idx,
            "existing_row": existing_row,
            "md_compile": md_compile,
            "errors": errors,
        }
    finally:
        ctx.close()


class TestBlindUiBrowserClickAnywhere(unittest.TestCase):
    def test_desktop_and_mobile_click_anywhere_parity(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            self.skipTest(f"playwright unavailable: {exc}")

        chrome_path = _find_chrome()
        launch_kwargs = {"headless": True}
        if chrome_path:
            launch_kwargs["executable_path"] = chrome_path

        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            try:
                desk = _run_viewport_scenario(browser, mobile=False, styled=True)
                mob = _run_viewport_scenario(browser, mobile=True, styled=True)

                for name, res in (("desktop", desk), ("mobile", mob)):
                    self.assertEqual(res["errors"], [], f"{name} console/page errors: {res['errors']}")
                    row = res["lower"]["row"]
                    self.assertNotEqual(row, 0, f"{name}: counterfactual knockout failed (stuck at row 0)")
                    self.assertGreaterEqual(row, 4, f"{name}: expected row >= 4, got {row}")
                    self.assertEqual(res["lower"]["apiRow"], row)
                    self.assertEqual(res["lower"]["texts"][row], "Hello from lower body")
                    lines = res["lower"]["md"].split("\n")
                    self.assertGreater(len(lines), row)
                    self.assertEqual(lines[row], "Hello from lower body")
                    self.assertEqual(res["roundtrip"]["md"], res["roundtrip"]["saved"])
                    self.assertEqual(res["roundtrip"]["texts"][row], "Hello from lower body")
                    self.assertEqual(res["row1_idx"], 1, f"{name}: row 1 dead zone detected")
                    self.assertEqual(res["existing_row"], 1, f"{name}: existing line click missed row 1")
                    self.assertTrue(res["md_compile"]["hasH1"], f"{name}: missing live <h1>")
                    self.assertTrue(res["md_compile"]["hasStrong"], f"{name}: missing live <strong>")
                    self.assertTrue(res["md_compile"]["hasEm"], f"{name}: missing live <em>")
                    self.assertEqual(res["md_compile"]["strongText"], "bold")
                    self.assertEqual(res["md_compile"]["emText"], "italic")
                    self.assertEqual(res["lower"]["caretColor"], "rgb(0, 224, 138)")

                self.assertEqual(
                    desk["lower"]["row"],
                    mob["lower"]["row"],
                    f"Desktop row {desk['lower']['row']} != Mobile row {mob['lower']['row']}",
                )
                self.assertEqual(mob["lower"]["fontSize"], "16px")

                # Unstyled standalone HTML check (zero custom CSS): empty <p> must not collapse to 0px
                bare_d = _run_viewport_scenario(browser, mobile=False, styled=False)
                bare_m = _run_viewport_scenario(browser, mobile=True, styled=False)
                self.assertEqual(bare_d["errors"], [])
                self.assertEqual(bare_m["errors"], [])
                self.assertNotEqual(bare_d["lower"]["row"], 0)
                self.assertGreaterEqual(bare_d["lower"]["row"], 4)
                self.assertEqual(bare_d["lower"]["row"], bare_m["lower"]["row"])
                self.assertEqual(bare_d["lower"]["texts"][bare_d["lower"]["row"]], "Hello from lower body")
                self.assertEqual(bare_m["lower"]["texts"][bare_m["lower"]["row"]], "Hello from lower body")
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
