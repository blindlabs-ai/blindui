# BlindUI

Standalone zero-dependency `26 KB` (`26,042` bytes minified) Safe-DOM and linear-time Safe-Markdown ES2020 browser runtime, deterministic minifier, and static UI-to-server security validator by [Blind Labs](https://blindlabs.ai).

| Property | Specification |
| :--- | :--- |
| **Website** | https://blindlabs.ai |
| **Repository** | https://github.com/blindlabs-ai/blindui |
| **Minified Bundle** | `26,042` bytes (`blindui.min.js`, verified `< 28 KB` hard budget) |
| **Runtime Dependencies** | `0` `npm` packages, `0` `pip` packages (pure ES2020 + Python 3 stdlib) |
| **Security Posture** | Strict tag/attribute/URL allowlists, `O(n)` Safe-Markdown, `BUI-01..BUI-10` static AST/HTML gate |
| **License** | Apache License, Version 2.0 ([LICENSE](LICENSE) & [NOTICE](NOTICE)) |

---

## Why BlindUI?

- **Safe-DOM Construction by Default (`BlindUI.h`, `BlindUI.svg`, `BlindUI.sanitizeUrl`):** Strictly allowlists HTML and SVG tags/attributes, enforces `blob:` origin isolation on `<iframe>` previews, validates `https:` and header-safe `mailto:` URLs, and eliminates raw HTML parsing or dynamic script-execution sinks across the entire runtime.
- **Linear-Time Safe-Markdown & Rich Editors (`BlindUI.md`, `BlindUI.bindMdEditor`, `BlindUI.notionEditor`):** Single-pass `O(n)` Markdown rendering and block/raw editing tested against 30+ XSS payload classes and pathological nested inputs without catastrophic regex backtracking (ReDoS).
- **Zero-Framework UI Primitives (`BlindUI.modal`, `BlindUI.bindAction`, `BlindUI.bindGroup`, `BlindUI.defineRoutes`, `BlindUI.api`):** Responsive docked/sheet modal controller with focus restoration, delegated selector/action wiring, optional request signing (`setSigner`), and client-side request/response schema validation.
- **Static Full-Stack Contract & Hygiene Gate (`blindui_check.py` + `build_blindui.py`):** Audits web frontends and Python backends via `ast.parse()` and `HTMLParser` (never executing target code) for unsafe DOM sinks, unescaped templating, unbound UI actions, route drift, CSP headers, and byte-exact `blindui.min.js` reproducibility.

---

## Quickstart

Load `blindui.min.js` directly via `<script src="./blindui.min.js"></script>` (`window.BlindUI`) or `require("./blindui.min.js")` in CommonJS/Node test harnesses:

```html
<div id="app"></div>
<script src="./blindui.min.js"></script>
<script>
  const { h, md, bindAction } = window.BlindUI;

  const card = h(
    "section",
    { className: "card" },
    h("h2", null, "Zero-Knowledge Workspace"),
    md("Verified **Safe-DOM** rendering with `0` unsafe HTML sinks."),
    h("button", { id: "verify-btn", type: "button" }, "Verify Session")
  );

  document.getElementById("app").appendChild(card);
  bindAction("verify-btn", () => console.log("BlindUI v" + window.BlindUI.version));
</script>
```

### Public Runtime Surface (`window.BlindUI`)

| Export | Purpose |
| :--- | :--- |
| `h(tag, props, ...children)` | Construct allowlisted HTML elements with safe attributes, styles, datasets, and listeners |
| `svg(tag, props, ...children)` | Construct allowlisted vector graphics (`svg`, `g`, `path`, `rect`, `circle`, `line`, `polygon`, ...) |
| `sanitizeUrl(url, options?)` | Validate `https:` and header-safe `mailto:` URLs (plus opt-in `allowRelative` / `allowDownloadBlob`) |
| `md(markdownText)` | Render untrusted Markdown in `O(n)` time into a safe `DocumentFragment` |
| `bindMdEditor(opts)` | Bind toolbar formatting, live Safe-Markdown preview, and keyboard shortcuts to a `<textarea>` |
| `notionEditor(container, opts)` | Mount an interactive block-structured + raw Markdown editor with live serialization |
| `modal(id, opts?)` | Accessible modal / docked panel / mobile-sheet state machine (`open`, `close`, `dock`, `expand`) |
| `bindAction(id, fn, event?)` | Bind an event handler by element ID and register the binding for static `BUI-04` verification |
| `bindGroup(selector, fn, event?)` | Delegate events cleanly across matching child elements without inline event attributes |
| `defineRoutes(map)` / `api(route, opts?)` | Declare typed client route schemas and execute schema-checked, optionally signed `fetch` calls |

---

## Repository Layout

```text
blindui.js               # Readable ES2020 Safe-DOM, Safe-Markdown, editor, modal, and API runtime
blindui.min.js           # Deterministic minified production bundle (26,042 bytes)
build_blindui.py         # Zero-dependency deterministic ES2020 minifier & bundle verifier (--check)
blindui_check.py         # Static UI-to-server contract & XSS hygiene validator (rules BUI-01..BUI-10)
test_blindui.mjs         # Zero-dep Node.js test suite (32 tests across source + minified bundles)
test_blindui_check.py    # Python unittest suite for blindui_check.py (14 static analysis tests)
LICENSE                  # Apache License, Version 2.0
NOTICE                   # Attribution, trademark reservation, and server-side scope notice
```

---

## Verification & Test Suite

```bash
# 1. Verify deterministic minified bundle matches blindui.js (< 28 KB budget)
PYTHONDONTWRITEBYTECODE=1 python3 build_blindui.py --check

# 2. Run Safe-DOM, Safe-Markdown, URL sanitizer, editor, modal, and XSS suite (32/32 tests)
node --test test_blindui.mjs

# 3. Run static security & route-parity analyzer suite (14/14 tests)
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_blindui_check.py
```

---

## Acknowledgments

Special thanks and a public shoutout to the **Ripwire** team for building zero-dependency static code analysis, AST lint checks, structural clone detection, and ranked symbol mapping tooling. Ripwire's commitment to structural clarity and zero-bloat engineering helped keep BlindUI's runtime, minifier, and static security gate small and auditable.

---

## License

Licensed under the Apache License, Version 2.0 ([LICENSE](LICENSE)). See [NOTICE](NOTICE) for attribution, trademark reservations, and proprietary server-side scope boundaries.

Copyright 2026 Blind Labs (https://blindlabs.ai).
