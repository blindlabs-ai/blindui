// Zero-dependency Node.js test suite for blindui-layout-lint.js & blindui-layout-lint.min.js.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC_PATH = path.join(HERE, "blindui-layout-lint.js");
const MIN_PATH = path.join(HERE, "blindui-layout-lint.min.js");
const require = createRequire(import.meta.url);

const lintSrc = require(SRC_PATH);
const lintMin = require(MIN_PATH);
const TARGETS = [
  ["source", lintSrc],
  ["minified", lintMin],
];

// Synthetic minimal DOM element factory for deterministic geometry unit tests.
function mkEl(tag, opts = {}) {
  const el = {
    tagName: tag.toUpperCase(),
    namespaceURI: opts.svg ? "http://www.w3.org/2000/svg" : "http://www.w3.org/1999/xhtml",
    id: opts.id || "",
    className: opts.className || "",
    attrs: Object.assign({}, opts.attrs || {}),
    textContent: opts.text || "",
    children: [],
    parentElement: null,
    parentNode: null,
    clientWidth: opts.clientWidth ?? (opts.rect ? opts.rect.w : 0),
    scrollWidth: opts.scrollWidth ?? (opts.rect ? opts.rect.w : 0),
    clientHeight: opts.clientHeight ?? (opts.rect ? opts.rect.h : 0),
    scrollHeight: opts.scrollHeight ?? (opts.rect ? opts.rect.h : 0),
    _style: Object.assign({ display: "block", position: "static", overflow: "visible" }, opts.style || {}),
    _rect: opts.rect || { x: 0, y: 0, w: 0, h: 0 },
    getAttribute(k) {
      if (k === "class") return this.className;
      if (k === "id") return this.id;
      return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null;
    },
    getBoundingClientRect() {
      const r = this._rect;
      return {
        x: r.x,
        y: r.y,
        left: r.x,
        top: r.y,
        width: r.w,
        height: r.h,
        right: r.x + r.w,
        bottom: r.y + r.h,
      };
    },
    append(...kids) {
      for (const k of kids) {
        k.parentElement = this;
        k.parentNode = this;
        this.children.push(k);
      }
      return this;
    },
  };
  return el;
}

const gcs = (el) => el._style || {};

test("bundle budget, 7-bit ASCII, zero clamp, zero forbidden sinks", () => {
  const srcText = fs.readFileSync(SRC_PATH, "utf8");
  const minBytes = fs.readFileSync(MIN_PATH);
  const minText = minBytes.toString("utf8");

  assert.ok(minBytes.length <= 8192, `Expected <= 8192 B, got ${minBytes.length}`);
  for (const [name, txt] of [["source", srcText], ["minified", minText]]) {
    for (let i = 0; i < txt.length; i++) {
      assert.ok(txt.charCodeAt(i) <= 127, `${name} contains non-ASCII at index ${i}`);
    }
    const banned = [
      "." + "cl" + "amp(",
      "inner" + "HTML",
      "outer" + "HTML",
      "insertAdjacent" + "HTML",
      "document." + "write",
      "ev" + "al(",
      "new " + "Function",
    ];
    for (const tok of banned) {
      assert.equal(txt.includes(tok), false, `${name} contains forbidden token ${tok}`);
    }
  }
});

for (const [label, lintLayout] of TARGETS) {
  test(`[${label}] LINT-FLEX-SHRINK-CLIP counterfactual (broken > 0 vs fixed == 0)`, () => {
    const mkTree = (shrinkZero) => {
      const list = mkEl("div", {
        id: "inbox-list",
        className: "msg-list",
        rect: { x: 0, y: 0, w: 375, h: 600 },
        style: { display: "flex", flexDirection: "column", overflowY: "auto" },
      });
      const row = mkEl("div", {
        className: "msg-swipe-wrap",
        rect: { x: 0, y: 0, w: 375, h: shrinkZero ? 96 : 26 },
        clientHeight: shrinkZero ? 96 : 26,
        scrollHeight: 96,
        style: {
          display: "block",
          overflow: "hidden",
          flexShrink: shrinkZero ? "0" : "1",
        },
      });
      list.append(row);
      return list;
    };

    const broken = lintLayout(mkTree(false), { getComputedStyle: gcs, viewportWidth: 375 });
    const fixed = lintLayout(mkTree(true), { getComputedStyle: gcs, viewportWidth: 375 });

    const flexHits = broken.filter((f) => f.rule === "LINT-FLEX-SHRINK-CLIP");
    assert.ok(flexHits.length > 0, "Expected LINT-FLEX-SHRINK-CLIP on broken flex child");
    assert.ok(flexHits[0].suggestedFix.includes("flex-shrink: 0"), flexHits[0].suggestedFix);
    assert.notDeepStrictEqual(broken, fixed);
    assert.equal(fixed.length, 0, JSON.stringify(fixed));
  });

  test(`[${label}] LINT-SIBLING-OVERLAP catches negative-margin button bleed & ignores swipe-bg`, () => {
    const mkRow = (negMargin) => {
      const wrap = mkEl("div", {
        className: "msg-swipe-wrap",
        rect: { x: 0, y: 0, w: 375, h: 96 },
        style: { position: "relative", overflow: "hidden" },
      });
      const swipeBg = mkEl("div", {
        className: "swipe-bg",
        rect: { x: 0, y: 0, w: 375, h: 96 },
        style: { position: "absolute", pointerEvents: "none" },
      });
      const row = mkEl("div", {
        className: "msg-row",
        rect: { x: 0, y: 0, w: 375, h: 96 },
        style: { display: "flex", position: "relative" },
      });
      const col = mkEl("div", {
        className: "msg-body-col",
        rect: { x: 56, y: 8, w: 305, h: 80 },
        style: { display: "flex", flexDirection: "column" },
      });
      const subj = mkEl("div", {
        className: "msg-subject-line",
        rect: { x: 56, y: 24, w: 305, h: 20 },
      });
      const snip = mkEl("div", {
        className: "msg-snippet-line",
        rect: { x: 56, y: 46, w: 305, h: 44 },
        style: { display: "flex", alignItems: "center" },
      });
      const star = mkEl("button", {
        className: "star-btn",
        text: "*",
        rect: { x: 317, y: negMargin ? 36 : 46, w: 44, h: 44 },
        style: { marginTop: negMargin ? "-10px" : "0px", marginBottom: negMargin ? "-10px" : "0px" },
      });
      snip.append(star);
      col.append(subj, snip);
      row.append(col);
      wrap.append(swipeBg, row);
      const nav = mkEl("nav", {
        id: "mobile-bottom-nav",
        rect: { x: 0, y: 761, w: 375, h: 51 },
        style: { position: "fixed", display: "flex" },
      });
      const tabBtn = mkEl("button", {
        id: "mob-tab-mail",
        text: "Mail",
        rect: { x: 6, y: 761, w: 90, h: 51 },
      });
      nav.append(tabBtn);
      const shell = mkEl("div", {
        className: "app-shell",
        rect: { x: 0, y: 0, w: 375, h: 812 },
      });
      const ws = mkEl("div", {
        className: "workspace-root",
        rect: { x: 0, y: 60, w: 375, h: 752 },
      });
      ws.append(wrap);
      shell.append(ws, nav);
      return shell;
    };

    const broken = lintLayout(mkRow(true), { getComputedStyle: gcs, viewportWidth: 375 });
    const fixed = lintLayout(mkRow(false), { getComputedStyle: gcs, viewportWidth: 375 });

    const hits = broken.filter((f) => f.rule === "LINT-SIBLING-OVERLAP");
    assert.ok(hits.length > 0, "Expected LINT-SIBLING-OVERLAP on negative-margin .star-btn");
    assert.ok(hits[0].suggestedFix.includes("negative margin"), hits[0].suggestedFix);
    assert.equal(fixed.length, 0, JSON.stringify(fixed));
  });

  test(`[${label}] LINT-SVG-TEXT-OVERLAP detects collisions & exempts erd-lbl-bg / erd-edge-lbl pills`, () => {
    const mkErd = (brokenCase) => {
      const svg = mkEl("svg", { svg: true, rect: { x: 0, y: 0, w: 800, h: 500 } });
      const bg = mkEl("rect", { svg: true, rect: { x: 0, y: 0, w: 800, h: 500 } });
      const card = mkEl("rect", {
        svg: true,
        className: "erd-card",
        rect: { x: 40, y: 40, w: 200, h: 120 },
      });
      // Own pill inside <g class="erd-edge-lbl"> must NEVER false-positive
      const edgeGrp = mkEl("g", { svg: true, className: "erd-edge-lbl", rect: { x: 300, y: 90, w: 72, h: 22 } });
      const pill = mkEl("rect", { svg: true, className: "erd-lbl-bg", rect: { x: 300, y: 90, w: 72, h: 22 } });
      const lbl = mkEl("text", {
        svg: true,
        className: "erd-lbl",
        text: "user_id",
        rect: brokenCase ? { x: 100, y: 80, w: 58, h: 14 } : { x: 307, y: 94, w: 58, h: 14 },
      });
      edgeGrp.append(pill, lbl);
      svg.append(bg, card, edgeGrp);
      return svg;
    };

    const broken = lintLayout(mkErd(true), { getComputedStyle: gcs, viewportWidth: 800 });
    const fixed = lintLayout(mkErd(false), { getComputedStyle: gcs, viewportWidth: 800 });

    assert.ok(broken.some((f) => f.rule === "LINT-SVG-TEXT-OVERLAP"), JSON.stringify(broken));
    assert.equal(fixed.length, 0, JSON.stringify(fixed));
  });

  test(`[${label}] LINT-TEXT-CLIPPED & LINT-VIEWPORT-BLEED-X counterfactuals`, () => {
    const mkRoot = (brokenCase) => {
      const body = mkEl("body", {
        rect: { x: 0, y: 0, w: 375, h: 800 },
        clientWidth: 375,
        scrollWidth: brokenCase ? 460 : 375,
      });
      const clipped = mkEl("div", {
        className: "summary-box",
        text: "Long summary text that overflows vertical container",
        rect: { x: 16, y: 20, w: 340, h: 20 },
        clientHeight: 20,
        scrollHeight: brokenCase ? 52 : 20,
        style: { overflowY: "hidden" },
      });
      const clamped = mkEl("div", {
        className: "clamped-note",
        text: "Intentional 2-line clamp",
        rect: { x: 16, y: 60, w: 340, h: 32 },
        clientHeight: 32,
        scrollHeight: 64,
        style: { overflowY: "hidden", webkitLineClamp: "2" },
      });
      const wide = mkEl("div", {
        className: "wide-card",
        rect: { x: 0, y: 120, w: brokenCase ? 450 : 350, h: 40 },
      });
      // Parked offscreen fixed drawer must NOT trigger viewport bleed
      const drawer = mkEl("aside", {
        className: "rail",
        rect: { x: -280, y: 0, w: 260, h: 800 },
        style: { position: "fixed" },
      });
      body.append(clipped, clamped, wide, drawer);
      return body;
    };

    const broken = lintLayout(mkRoot(true), { getComputedStyle: gcs, viewportWidth: 375 });
    const fixed = lintLayout(mkRoot(false), { getComputedStyle: gcs, viewportWidth: 375 });

    assert.ok(broken.some((f) => f.rule === "LINT-TEXT-CLIPPED"), JSON.stringify(broken));
    assert.ok(broken.some((f) => f.rule === "LINT-VIEWPORT-BLEED-X"), JSON.stringify(broken));
    assert.equal(fixed.length, 0, JSON.stringify(fixed));
  });
}
