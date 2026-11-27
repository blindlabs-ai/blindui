# Maat App Forge Example: Bad Legacy App vs. Forged Workspace

Self-contained counterfactual demonstration comparing a broken legacy waterfall page (`bad_legacy_app.html`) against a strict-CSP, single-bundle application synthesized from `workspace_spec.json` by `maat_forge.py`.

## Counterfactual Comparison

1. **`bad_legacy_app.html` (Static `MAAT-12..15` Failures):**
   - Loads 4 `<script type="module">` waterfall tags (`MAAT-12`, max 2).
   - Loads 3 `<link rel="stylesheet">` tags including an external font CDN (`MAAT-12` + `MAAT-14`).
   - Runs `async function boot()` awaiting network I/O before frame-1 `render()` (`MAAT-12`).
   - Embeds `<img src="/assets/legacy-banner.png">` and `<iframe src="https://example.com/legacy-embed">` violating strict CSP portability (`MAAT-14`).
   - Declares `.inbox-row` and `.msg-swipe-wrap` without `flex-shrink: 0` or touch containment (`MAAT-15`).
2. **Forged `workspace_spec.json` (`0` Static & `0` Runtime Findings):**
   - Synthesized via `python3 maat_forge.py --spec examples/app-forge/workspace_spec.json --out /tmp/forged --verify`.
   - Strict CSP `<meta>` header, zero inline scripts/handlers, zero external CDNs/iframes, bespoke geometric SVG mark, tactile rows with `flex-shrink: 0; touch-action: pan-y;`, and `< 15 ms` synchronous frame-1 paint.
   - Passes `maat_check.py` (`0` findings across `MAAT-01..16`) and headless Chromium `Maat.lintLayout(document.body)` (`0` findings at `1280x800` and `375x812`).

## Run the Demo

```bash
PYTHONDONTWRITEBYTECODE=1 python3 examples/app-forge/run_forge_demo.py
```

See [sample_forge_report.json](sample_forge_report.json) for a captured machine-readable run report.
