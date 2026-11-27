# Maat (formerly Zero-UI / BlindUI)

Standalone zero-dependency, Feather-of-Truth web substrate: `28 KB` (`27,742` bytes minified) Safe-DOM and linear-time Safe-Markdown ES2020 browser runtime, `8 KB` (`8,169` bytes minified) standardized component kit, `8 KB` (`8,130` bytes minified) DOM/SVG layout & overlap linter, `4 KB` (`4,094` bytes) obsidian design token stylesheet, deterministic minifier, self-immune static validator (`MAAT-01..MAAT-16`), and single-bundle app synthesizer (`maat_forge.py`) by [Blind Labs](https://blindlabs.ai).

`window.Maat` and `window.BlindUI` (as well as `maat_check.py` / `blindui_check.py` and `build_maat.py` / `build_blindui.py`) are 100% backwards-compatible aliases (`window.Maat === window.BlindUI`).

| Property | Specification |
| :--- | :--- |
| **Website** | https://blindlabs.ai |
| **Repository** | https://github.com/blindlabs-ai/zero-ui |
| **Core Bundle** | `27,742` bytes (`maat.min.js` / `blindui.min.js`, verified `< 28 KB` hard budget) |
| **Component Kit** | `8,169` bytes (`maat-kit.min.js` / `blindui-kit.min.js`, verified `<= 8 KB` hard budget) |
| **Layout Linter** | `8,130` bytes (`maat-layout-lint.min.js` / `blindui-layout-lint.min.js`, verified `<= 8 KB` hard budget) |
| **Design Tokens** | `4,094` bytes (`maat-tokens.css` / `blindui-tokens.css`, verified `<= 4 KB` hard budget) |
| **Runtime Dependencies** | `0` `npm` packages, `0` `pip` packages (pure ES2020 + Python 3 stdlib) |
| **Security & Quality Gate** | Strict allowlists, `O(n)` Safe-Markdown, `MAAT-01..MAAT-16` (`BUI-01..BUI-11` compat) + `MAAT-16 --self` |
| **App Synthesizer** | `maat_forge.py` (4 archetypes: `tactile-inbox`, `workspace-drive`, `sql-studio`, `openapi-console`) |
| **License** | Apache License, Version 2.0 ([LICENSE](LICENSE) & [NOTICE](NOTICE)) |

---

## The Feather-of-Truth Philosophy

Every Maat artifact is weighed against strict deterministic budgets before shipping:

- **Featherweight Byte Ceilings:** Core runtime `< 28 KB`, component kit `<= 8 KB`, DOM/SVG layout linter `<= 8 KB`, and obsidian tokens `<= 4 KB` -- deterministically minified and byte-synced with `blindui*` compatibility mirrors via `build_maat.py`.
- **Synchronous Frame-1 Boot (`< 15 ms`):** No `async` boot waterfalls or blocking network/crypto calls before first paint (`MAAT-12`).
- **Safe-DOM & Strict CSP Portability (`MAAT-01`, `MAAT-14`):** Allowlisted `Maat.h`, `Maat.svg`, `Maat.md`, and `Maat.sanitizeUrl` eliminate raw HTML injection sinks, third-party CDNs, external `<img>` loads, and `<iframe>` embeds.
- **Bespoke Visual Identity & Tactile Mobile Safety (`MAAT-11`, `MAAT-13`, `MAAT-15`):** Rejects trademark palette/SVG clones, enforces `flex-shrink: 0` + touch containment on mobile scroll/swipe rows, and requires collision-free pill labels on SVG/ERD diagrams.
- **Self-Immune Verification (`MAAT-16`):** `python3 maat_check.py --self` audits Maat's own JS/CSS/Python sources, bundle budgets, mirror parity, and all four `maat_forge.py` archetypes.

---

## Quickstart

Load `maat.min.js` alongside `maat-tokens.css`, `maat-kit.min.js`, and `maat-layout-lint.min.js` (`window.Maat === window.BlindUI`):

```html
<link rel="stylesheet" href="./maat-tokens.css">
<div id="app"></div>
<script src="./maat.min.js"></script>
<script src="./maat-kit.min.js"></script>
<script src="./maat-layout-lint.min.js"></script>
<script>
  const { h, md, bindAction, kit, lintLayout } = window.Maat;

  const main = h(
    "div",
    { className: "bui-col" },
    kit.kpiStrip([
      { label: "Core Bundle", value: "27,742 B", tone: "ok", sub: "< 28 KB budget" },
      { label: "Kit Bundle", value: "8,169 B", tone: "ok", sub: "<= 8 KB budget" },
      { label: "Layout Linter", value: "8,130 B", tone: "ok", sub: "<= 8 KB budget" },
      { label: "CSS Tokens", value: "4,094 B", tone: "ok", sub: "<= 4 KB budget" }
    ]),
    h(
      "section",
      { className: "bui-card" },
      h("h2", null, "Feather-Verified Workspace"),
      md("Verified **Safe-DOM** rendering with `0` unsafe HTML sinks."),
      h("button", { id: "verify-btn", className: "bui-btn bui-btn-primary", type: "button" }, "Verify Layout")
    )
  );

  kit.shell({
    mount: document.getElementById("app"),
    surface: "developers",
    main,
    footer: "Powered by Maat"
  });

  bindAction("verify-btn", () => console.log("Findings:", lintLayout(document.body).length));
</script>
```

### App Forge (`maat_forge.py`)

Synthesize a complete strict-CSP, single-bundle application from a JSON blueprint and self-verify it statically (`MAAT-01..16`) and in headless Chromium (`Maat.lintLayout` at `1280x800` and `375x812`):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 maat_forge.py \
  --spec examples/app-forge/workspace_spec.json \
  --out /tmp/maat-workspace \
  --verify --json
```

Supported archetypes: `tactile-inbox`, `workspace-drive`, `sql-studio`, and `openapi-console`. See the runnable bad-legacy-vs-forged walkthrough in [examples/app-forge/](examples/app-forge/).

### Public Runtime Surface (`window.Maat` / `window.BlindUI`)

| Export | Purpose |
| :--- | :--- |
| `h(tag, props, ...children)` | Construct allowlisted HTML elements with safe attributes, styles, datasets, and listeners |
| `svg(tag, props, ...children)` | Construct allowlisted vector graphics (`svg`, `g`, `path`, `rect`, `circle`, `line`, `polygon`, ...) |
| `sanitizeUrl(url, options?)` | Validate `https:` and header-safe `mailto:` URLs (plus opt-in `allowRelative` / `allowDownloadBlob`) |
| `md(markdownText)` | Render untrusted Markdown in `O(n)` time into a safe `DocumentFragment` |
| `bindMdEditor(opts)` | Bind toolbar formatting, live Safe-Markdown preview, and keyboard shortcuts to a `<textarea>` |
| `notionEditor(container, opts)` | Mount an interactive block-structured + raw Markdown editor with click-anywhere vertical placement (`focusAtPoint`, `getActiveRow`) |
| `modal(id, opts?)` | Accessible modal / docked panel / mobile-sheet state machine (`open`, `close`, `dock`, `expand`) |
| `bindAction(id, fn, event?)` | Bind an event handler by element ID and register the binding for static `MAAT-04` (`BUI-04`) verification |
| `bindGroup(selector, fn, event?)` | Delegate events cleanly across matching child elements without inline event attributes |
| `defineRoutes(map)` / `api(route, opts?)` | Declare typed client route schemas and execute schema-checked, optionally signed `fetch` calls |
| `kit.*` | Eight Safe-DOM primitives (`icon`, `shell`, `kpiStrip`, `stepRail`, `keyCard`, `codeBlock`, `statusPill`, `tryItPanel`) |
| `lintLayout(root?, opts?)` | Live DOM/SVG geometry auditor (`LINT-FLEX-SHRINK-CLIP`, `LINT-SIBLING-OVERLAP`, `LINT-SVG-TEXT-OVERLAP`, `LINT-TEXT-CLIPPED`, `LINT-VIEWPORT-BLEED-X`) |

### Static Validator Rules (`MAAT-01..MAAT-16` / `BUI-01..BUI-11`)

| Rule | Alias | Check |
| :--- | :--- | :--- |
| `MAAT-01..10` | `BUI-01..10` | XSS sinks, duplicate hoisted functions, JS syntax, unwired controls, route parity, user-facing jargon, ASCII/no-dot-clamp, key-safety, bundle parity, CSP headers |
| `MAAT-11` | `BUI-11` | Static CSS layout traps (flex-scroll shrink-clip, negative margins, fixed bottom nav/FAB clearance) |
| `MAAT-12` | -- | No async boot waterfall (`await` before frame-1 `render()`, max 2 module scripts & 2 stylesheets) |
| `MAAT-13` | -- | No third-party vendor trademark color-combo or SVG path clones |
| `MAAT-14` | -- | Strict CSP portability (no `<iframe src=...>`, no non-`data:` `<img src=...>`, no external CDN/font URLs or CSS `@import`) |
| `MAAT-15` | -- | Tactile mobile & SVG safety (pill/offset SVG midpoint text, mobile row `flex-shrink: 0`, swipe container containment) |
| `MAAT-16` | -- | Self-immune audit (`python3 maat_check.py --self`) verifying Maat's own bundles, mirrors, sources, and forged archetypes |

See also the mobile inbox layout linter counterfactual walkthrough in [examples/layout-linter/](examples/layout-linter/).

---

## Repository Layout

```text
maat.js / maat.min.js                      # Core ES2020 Safe-DOM, Safe-Markdown, editor, modal & API runtime (27,742 B)
maat-kit.js / maat-kit.min.js              # Standardized 8-primitive component kit (8,169 B)
maat-layout-lint.js / maat-layout-lint.min.js # Runtime DOM/SVG layout & overlap auditor (8,130 B)
maat-tokens.css                            # Obsidian design token & component utility stylesheet (4,094 B)
blindui*.js / blindui-tokens.css           # Byte-synced backwards-compatibility mirrors (window.BlindUI === window.Maat)
build_maat.py / build_blindui.py           # Zero-dependency deterministic ES2020 minifier & bundle/mirror verifier
maat_check.py / blindui_check.py           # Static security, route-parity, layout & self-immune validator (MAAT-01..16)
maat_forge.py                              # Zero-dependency 4-archetype strict-CSP single-bundle app synthesizer
examples/layout-linter/                    # Broken vs. fixed mobile inbox HTML demo, Playwright runner & sample report
examples/app-forge/                        # Bad legacy app vs. forged workspace demo, blueprint spec & sample report
test_blindui*.mjs / test_blindui*.py       # Node & Python core, kit, layout linter, and BUI-01..11 test suites
test_maat_forge_and_rules.py               # Counterfactual MAAT-12..16, App Forge, and window.Maat parity suite
LICENSE / NOTICE                           # Apache License, Version 2.0 & attribution notice
```

---

## Verification & Test Suite

```bash
# 1. Verify deterministic minified bundles, byte budgets, and BlindUI mirrors
PYTHONDONTWRITEBYTECODE=1 python3 build_maat.py --check --require-node
PYTHONDONTWRITEBYTECODE=1 python3 build_blindui.py --check --require-node

# 2. Run MAAT-16 self-immune audit across Maat sources, bundles, and all 4 forge archetypes
PYTHONDONTWRITEBYTECODE=1 python3 maat_check.py --self

# 3. Run Node.js core, kit, and runtime layout linter suites
node test_blindui.mjs
node --test test_blindui_kit.mjs test_blindui_layout_lint.mjs

# 4. Run Python static rules, App Forge, and browser verification suites
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_blindui_check.py test_blindui.py test_maat_forge_and_rules.py

# 5. Run interactive browser counterfactual demos (requires Playwright + Chromium)
PYTHONDONTWRITEBYTECODE=1 python3 examples/layout-linter/run_lint_demo.py
PYTHONDONTWRITEBYTECODE=1 python3 examples/app-forge/run_forge_demo.py
PYTHONDONTWRITEBYTECODE=1 python3 test_blindui_browser.py
```

---

## Acknowledgments

Special thanks and a public shoutout to the **Ripwire** team for building zero-dependency static code analysis, AST lint checks, structural clone detection, and ranked symbol mapping tooling. Ripwire's commitment to structural clarity and zero-bloat engineering helped keep Maat's runtime, component kit, minifier, app forge, and static security gate small and auditable.

---

## License

Licensed under the Apache License, Version 2.0 ([LICENSE](LICENSE) and [NOTICE](NOTICE)).

Copyright 2026 Blind Labs (https://blindlabs.ai).
