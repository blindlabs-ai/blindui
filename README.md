# BlindUI

Standalone zero-dependency `26 KB` (`26,042` bytes minified) Safe-DOM and linear-time Safe-Markdown ES2020 browser runtime, `8 KB` (`8,138` bytes minified) standardized component kit, `4 KB` (`4,091` bytes) obsidian design token stylesheet, deterministic minifier, and static UI-to-server security validator by [Blind Labs](https://blindlabs.ai).

| Property | Specification |
| :--- | :--- |
| **Website** | https://blindlabs.ai |
| **Repository** | https://github.com/blindlabs-ai/blindui |
| **Core Bundle** | `26,042` bytes (`blindui.min.js`, verified `< 28 KB` hard budget) |
| **Component Kit** | `8,138` bytes (`blindui-kit.min.js`, verified `<= 8 KB` hard budget) |
| **Design Tokens** | `4,091` bytes (`blindui-tokens.css`, verified `<= 4 KB` hard budget) |
| **Runtime Dependencies** | `0` `npm` packages, `0` `pip` packages (pure ES2020 + Python 3 stdlib) |
| **Security Posture** | Strict tag/attribute/URL allowlists, `O(n)` Safe-Markdown, `BUI-01..BUI-10` static AST/HTML gate |
| **License** | Apache License, Version 2.0 ([LICENSE](LICENSE) & [NOTICE](NOTICE)) |

---

## Why BlindUI?

- **Safe-DOM Construction by Default (`BlindUI.h`, `BlindUI.svg`, `BlindUI.sanitizeUrl`):** Strictly allowlists HTML and SVG tags/attributes, enforces `blob:` origin isolation on `<iframe>` previews, validates `https:` and header-safe `mailto:` URLs, and eliminates raw HTML parsing or dynamic script-execution sinks across the entire runtime.
- **Linear-Time Safe-Markdown & Rich Editors (`BlindUI.md`, `BlindUI.bindMdEditor`, `BlindUI.notionEditor`):** Single-pass `O(n)` Markdown rendering and block/raw editing tested against 30+ XSS payload classes and pathological nested inputs without catastrophic regex backtracking (ReDoS).
- **Zero-Framework UI Primitives (`BlindUI.modal`, `BlindUI.bindAction`, `BlindUI.bindGroup`, `BlindUI.defineRoutes`, `BlindUI.api`):** Responsive docked/sheet modal controller with focus restoration, delegated selector/action wiring, optional request signing (`setSigner`), and client-side request/response schema validation.
- **Standardized Component Kit & Obsidian Tokens (`BlindUI.kit.*` + `blindui-tokens.css`):** Companion `8,138`-byte library built strictly on `BlindUI.h` and `BlindUI.svg` providing ready-to-mount application shells, KPI strips, step rails, one-time secret API key cards, tabbed code blocks, status pills, and live API runner panels styled by a `4,091`-byte obsidian CSS token sheet.
- **Static Full-Stack Contract & Hygiene Gate (`blindui_check.py` + `build_blindui.py`):** Audits web frontends and Python backends via `ast.parse()` and `HTMLParser` (never executing target code) for unsafe DOM sinks, unescaped templating, unbound UI actions, route drift, CSP headers, and byte-exact `blindui.min.js` / `blindui-kit.min.js` reproducibility.

---

## Quickstart

Load `blindui.min.js` (and optionally `blindui-tokens.css` + `blindui-kit.min.js`) directly via `<link>` / `<script>` tags (`window.BlindUI`, `window.BlindUI.kit`) or `require(...)` in CommonJS/Node test harnesses:

```html
<link rel="stylesheet" href="./blindui-tokens.css">
<div id="app"></div>
<script src="./blindui.min.js"></script>
<script src="./blindui-kit.min.js"></script>
<script>
  const { h, md, bindAction, kit } = window.BlindUI;

  const main = h(
    "div",
    { className: "bui-col" },
    kit.kpiStrip([
      { label: "Core Bundle", value: "26,042 B", tone: "ok", sub: "< 28 KB budget" },
      { label: "Kit Bundle", value: "8,138 B", tone: "ok", sub: "<= 8 KB budget" },
      { label: "CSS Tokens", value: "4,091 B", tone: "ok", sub: "<= 4 KB budget" }
    ]),
    h(
      "section",
      { className: "bui-card" },
      h("h2", null, "Zero-Knowledge Workspace"),
      md("Verified **Safe-DOM** rendering with `0` unsafe HTML sinks."),
      h("button", { id: "verify-btn", className: "bui-btn bui-btn-primary", type: "button" }, "Verify Session")
    )
  );

  kit.shell({
    mount: document.getElementById("app"),
    surface: "developers",
    main,
    footer: "Powered by BlindUI"
  });

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

### Standardized Component Kit (`window.BlindUI.kit`)

Load `blindui-kit.min.js` (`8,138` bytes) alongside `blindui-tokens.css` (`4,091` bytes) after `blindui.min.js` to attach seven reusable Safe-DOM primitives to `window.BlindUI.kit`:

| Export | Purpose |
| :--- | :--- |
| `kit.shell(opts)` | Sticky suite header, sanitized brand/nav links with active surface state, main container, and optional footer |
| `kit.kpiStrip(opts \| items)` | Responsive metric card grid with tabular numerals, semantic tones (`ok`, `warn`, `err`), and safe empty fallbacks |
| `kit.stepRail(opts \| steps)` | Multi-step workflow rail (`todo`, `active`, `done`) with SVG checkmarks and collapsed completed bodies |
| `kit.keyCard(opts)` | API key lifecycle card with prefix display, quota progress bar, one-time dismissible `secretOnce` reveal/copy, and single-flight `aria-busy` rotate/revoke locks |
| `kit.codeBlock(opts)` | Accessible tabbed code snippet viewer (`role="tablist"`, `aria-selected`, `data-lang`) with clipboard copy button |
| `kit.statusPill(opts)` | Compact uppercase status badge with indicator dot and allowlisted semantic tone classes |
| `kit.tryItPanel(opts)` | Interactive preset-driven API runner with JSON/text payload editor, `BlindUI.api` fallback, latency/quota readout, and `429`/error handling |

---

## Repository Layout

```text
blindui.js               # Readable ES2020 Safe-DOM, Safe-Markdown, editor, modal, and API runtime
blindui.min.js           # Deterministic minified core production bundle (26,042 bytes)
blindui-kit.js           # Readable ES2020 standardized 7-primitive component kit (BlindUI.kit)
blindui-kit.min.js       # Deterministic minified component kit bundle (8,138 bytes, <= 8 KB)
blindui-tokens.css       # Obsidian design token & component utility stylesheet (4,091 bytes, <= 4 KB)
build_blindui.py         # Zero-dependency deterministic ES2020 minifier & bundle/token verifier (--check)
blindui_check.py         # Static UI-to-server contract & XSS hygiene validator (rules BUI-01..BUI-10)
test_blindui.mjs         # Zero-dep Node.js core test suite (32 tests across source + minified bundles)
test_blindui_kit.mjs     # Zero-dep Node.js kit test suite (17 tests across source + minified bundles + budgets)
test_blindui_check.py    # Python unittest suite for blindui_check.py (15 static analysis tests)
LICENSE                  # Apache License, Version 2.0
NOTICE                   # Attribution, trademark reservation, and server-side scope notice
```

---

## Verification & Test Suite

```bash
# 1. Verify deterministic minified bundles & token CSS match sources and byte budgets
PYTHONDONTWRITEBYTECODE=1 python3 build_blindui.py --check --require-node

# 2. Run core Safe-DOM, Safe-Markdown, URL sanitizer, editor, modal, and XSS suite (32/32 tests)
node --test test_blindui.mjs

# 3. Run component kit, XSS escaping, single-flight lock, and budget suite (17/17 tests)
node --test test_blindui_kit.mjs

# 4. Run static security & route-parity analyzer suite (15/15 tests)
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_blindui_check.py
```

---

## Acknowledgments

Special thanks and a public shoutout to the **Ripwire** team for building zero-dependency static code analysis, AST lint checks, structural clone detection, and ranked symbol mapping tooling. Ripwire's commitment to structural clarity and zero-bloat engineering helped keep BlindUI's runtime, component kit, minifier, and static security gate small and auditable.

---

## License

Licensed under the Apache License, Version 2.0 ([LICENSE](LICENSE)). See [NOTICE](NOTICE) for attribution, trademark reservations, and proprietary server-side scope boundaries.

Copyright 2026 Blind Labs (https://blindlabs.ai).
