# BlindUI Layout Linter Example: Mobile Inbox Overlap

Minimal, self-contained reproduction of a classic mobile flex-list collapse and negative-margin overlap bug, paired with its verified fix and automated Playwright + static `BUI-11` audit.

## What Breaks in `broken_mobile_inbox.html`

1. **CSS Flexbox 4.5 Min-Height Collapse (`LINT-FLEX-SHRINK-CLIP`):**
   - `.msg-list` is a scrolling flex column (`display: flex; flex-direction: column; overflow-y: auto;`).
   - Each `.msg-swipe-wrap` child sets `overflow: hidden` without `flex-shrink: 0`.
   - Per CSS Flexbox section 4.5, a flex item whose `overflow` is not `visible` has an automatic minimum height of `0` instead of `min-content`, so 15+ rows compress vertically into overlapping ~36px strips instead of scrolling.
2. **Negative-Margin Interactive Bleed (`LINT-SIBLING-OVERLAP`):**
   - `.star-btn` applies `margin: -10px -8px -10px 0` to inflate its touch box, causing its 44x44 hitbox to collide directly with `.msg-subject-line` and `.msg-badges` above/below it.

## What Fixes It in `fixed_mobile_inbox.html`

- Add `flex-shrink: 0;` to `.msg-swipe-wrap` and `.msg-row`.
- Reserve bottom scroll clearance on `.msg-list` (`padding: 0 0 calc(144px + env(safe-area-inset-bottom));`).
- Replace negative margin on `.star-btn` with `margin: 0;` and align `.msg-snippet-line` with `align-items: center;`.

## Run the Automated Counterfactual Demo

```bash
# Requires Python 3 + Playwright + Chromium
PYTHONDONTWRITEBYTECODE=1 python3 examples/layout-linter/run_lint_demo.py
```

Expected result:
- `broken_mobile_inbox.html` reports `> 0` findings (`LINT-FLEX-SHRINK-CLIP` + `LINT-SIBLING-OVERLAP`) with concrete `suggestedFix` guidance.
- `fixed_mobile_inbox.html` reports `0` findings (`0.0 px^2` overlap).
- See [sample_report.json](sample_report.json) for a captured machine-readable report.
