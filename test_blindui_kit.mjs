#!/usr/bin/env node
/**
 * Zero-dependency Node v22 test suite for BlindUI Kit (blindui-kit.js & blindui-kit.min.js).
 * Tests all 8 primitives (icon, shell, kpiStrip, stepRail, keyCard, codeBlock, statusPill, tryItPanel),
 * XSS escaping, single-flight aria-busy locks, secretOnce clearing, CSS motion/layout, and bundle budgets.
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { describe, test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CORE_MIN_PATH = path.join(__dirname, "blindui.min.js");
const KIT_SRC_PATH = path.join(__dirname, "blindui-kit.js");
const KIT_MIN_PATH = path.join(__dirname, "blindui-kit.min.js");
const TOKENS_PATH = path.join(__dirname, "blindui-tokens.css");

// Dynamic sink tokens so this file carries zero raw forbidden literals.
const SINK_NEEDLES = [
  "inner" + "HTML",
  "outer" + "HTML",
  "insertAdjacent" + "HTML",
  "document." + "write",
  "ev" + "al(",
  "new " + "Function",
  "on" + "click=",
  "</" + "script",
];
const CLAMP_RE = new RegExp("\\." + "cl" + "amp\\s*\\(");
const XSS_TAG = "<" + "script>alert(1)<" + "/script><img src=x on" + "error=alert(2)>";
const XSS_JS_URL = "java" + "script:alert(1)";

class MockClassList {
  constructor(el) {
    this._el = el;
    this._set = new Set();
  }
  _load(str) {
    this._set.clear();
    for (const c of String(str || "").split(/\s+/)) if (c) this._set.add(c);
  }
  add(...cls) {
    for (const c of cls) if (c) this._set.add(c);
    this._sync();
  }
  remove(...cls) {
    for (const c of cls) this._set.delete(c);
    this._sync();
  }
  contains(c) {
    return this._set.has(c);
  }
  toggle(c, force) {
    const on = force === undefined ? !this._set.has(c) : !!force;
    if (on) this._set.add(c);
    else this._set.delete(c);
    this._sync();
    return on;
  }
  _sync() {
    this._el._attrs.set("class", Array.from(this._set).join(" "));
  }
}

class MockNode {
  constructor(nodeType) {
    this.nodeType = nodeType;
    this.childNodes = [];
    this.parentNode = null;
  }
  get firstChild() {
    return this.childNodes[0] || null;
  }
  appendChild(child) {
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }
  removeChild(child) {
    const idx = this.childNodes.indexOf(child);
    if (idx >= 0) {
      this.childNodes.splice(idx, 1);
      child.parentNode = null;
    }
    return child;
  }
}

class MockText extends MockNode {
  constructor(text) {
    super(3);
    this.nodeValue = String(text);
  }
  get textContent() {
    return this.nodeValue;
  }
  set textContent(v) {
    this.nodeValue = String(v);
  }
}

class MockElement extends MockNode {
  constructor(tagName, ns = null, ownerDoc = null) {
    super(1);
    this.tagName = ns ? tagName : tagName.toLowerCase();
    this.namespaceURI = ns;
    this._doc = ownerDoc;
    this._attrs = new Map();
    this._listeners = new Map();
    this.dataset = {};
    this.classList = new MockClassList(this);
    this.value = "";
    this.disabled = false;
    this.style = {};
  }
  get id() {
    return this._attrs.get("id") || "";
  }
  set id(v) {
    this._attrs.set("id", String(v));
  }
  get className() {
    return this._attrs.get("class") || "";
  }
  set className(v) {
    const s = String(v || "");
    this._attrs.set("class", s);
    this.classList._load(s);
  }
  get textContent() {
    return this.childNodes.map((c) => c.textContent).join("");
  }
  set textContent(v) {
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes.length = 0;
    const s = String(v);
    if (s) this.appendChild(new MockText(s));
  }
  setAttribute(k, v) {
    const s = String(v);
    this._attrs.set(k, s);
    if (k === "class") this.classList._load(s);
  }
  getAttribute(k) {
    return this._attrs.has(k) ? this._attrs.get(k) : null;
  }
  removeAttribute(k) {
    this._attrs.delete(k);
    if (k === "class") this.classList._load("");
  }
  addEventListener(type, fn) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(fn);
  }
  removeEventListener(type, fn) {
    const arr = this._listeners.get(type);
    if (!arr) return;
    const i = arr.indexOf(fn);
    if (i >= 0) arr.splice(i, 1);
  }
  dispatchEvent(ev) {
    const event = Object.assign({ type: "click", target: this, preventDefault() {} }, ev);
    const list = (this._listeners.get(event.type) || []).slice();
    const results = [];
    for (const fn of list) results.push(fn.call(this, event));
    return results;
  }
  click() {
    return this.dispatchEvent({ type: "click" });
  }
}

class MockDocument {
  constructor() {
    this.body = new MockElement("body", null, this);
  }
  createElement(tag) {
    return new MockElement(tag, null, this);
  }
  createElementNS(ns, tag) {
    return new MockElement(tag, ns, this);
  }
  createTextNode(text) {
    return new MockText(text);
  }
  getElementById(id) {
    const walk = (node) => {
      if (node.nodeType === 1 && node.id === id) return node;
      for (const c of node.childNodes) {
        const hit = walk(c);
        if (hit) return hit;
      }
      return null;
    };
    return walk(this.body);
  }
}

function findAll(root, pred) {
  const out = [];
  const walk = (n) => {
    if (pred(n)) out.push(n);
    for (const c of n.childNodes) walk(c);
  };
  walk(root);
  return out;
}

function findById(root, id) {
  return findAll(root, (n) => n.nodeType === 1 && n.id === id)[0] || null;
}

function loadKitEnv(kitPath, opts = {}) {
  const document = new MockDocument();
  const clipboardWrites = [];
  const timers = [];
  const fetchCalls = [];
  let nowVal = 1000;

  const sandbox = {
    document,
    console,
    navigator: {
      clipboard: {
        writeText: async (text) => {
          clipboardWrites.push(String(text));
        },
      },
    },
    performance: {
      now: () => {
        nowVal += 12;
        return nowVal;
      },
    },
    setTimeout: (fn, ms) => {
      timers.push({ fn, ms });
      return timers.length;
    },
    fetch: opts.fetch || (async (url, init) => {
      fetchCalls.push({ url, init });
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ pong: true, url }),
      };
    }),
  };
  sandbox.globalThis = sandbox;
  sandbox.window = sandbox;

  const ctx = vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(CORE_MIN_PATH, "utf8"), ctx, { filename: "blindui.min.js" });
  vm.runInContext(fs.readFileSync(kitPath, "utf8"), ctx, { filename: path.basename(kitPath) });

  return {
    ctx,
    document,
    BlindUI: ctx.BlindUI,
    kit: ctx.BlindUI.kit,
    clipboardWrites,
    timers,
    fetchCalls,
  };
}

for (const [label, kitPath] of [
  ["blindui-kit.js", KIT_SRC_PATH],
  ["blindui-kit.min.js", KIT_MIN_PATH],
]) {
  describe(`BlindUI.kit (${label})`, () => {
    test("attaches version 1.0.0 and all 8 primitives onto BlindUI.kit", () => {
      const { kit } = loadKitEnv(kitPath);
      assert.equal(kit.version, "1.0.0");
      for (const fn of ["icon", "shell", "kpiStrip", "stepRail", "keyCard", "codeBlock", "statusPill", "tryItPanel"]) {
        assert.equal(typeof kit[fn], "function", `missing BlindUI.kit.${fn}`);
      }
    });

    test("icon renders 14 distinct surface SVGs with non-empty path d, safe fallbacks, and size validation", () => {
      const { kit } = loadKitEnv(kitPath);
      const surfaces = [
        "blog", "benchmarks", "apps", "developers", "chain", "mail", "sign",
        "social", "finance", "live", "call", "cdn", "github", "home",
      ];
      const pathBySurface = new Map();
      for (const id of surfaces) {
        const el = kit.icon(id);
        assert.equal(el.tagName, "svg");
        assert.equal(el.getAttribute("class"), "bk-ic");
        assert.equal(el.getAttribute("data-surface"), id);
        assert.equal(el.getAttribute("width"), "14");
        assert.equal(el.getAttribute("height"), "14");
        const paths = findAll(el, (n) => n.nodeType === 1 && n.tagName === "path");
        assert.equal(paths.length, 1, `expected 1 <path> for ${id}`);
        const d = paths[0].getAttribute("d");
        assert.ok(typeof d === "string" && d.length >= 10, `empty or mangled <path d> for ${id}: ${d}`);
        pathBySurface.set(id, d);
      }
      assert.equal(new Set(pathBySurface.values()).size, 14, "all 14 surface icons must have distinct <path d>");

      // Case-insensitive lookup works cleanly.
      const upper = kit.icon("BLOG");
      assert.equal(upper.getAttribute("data-surface"), "blog");
      assert.equal(findAll(upper, (n) => n.nodeType === 1 && n.tagName === "path")[0].getAttribute("d"), pathBySurface.get("blog"));

      // Unknown / prototype-pollution IDs fall back to apps path with no data-surface attribute.
      for (const badId of ["unknown", "toString", "__proto__", null, undefined]) {
        const fb = kit.icon(badId);
        assert.equal(fb.tagName, "svg");
        assert.equal(fb.getAttribute("class"), "bk-ic");
        assert.equal(fb.getAttribute("data-surface"), null);
        const d = findAll(fb, (n) => n.nodeType === 1 && n.tagName === "path")[0].getAttribute("d");
        assert.equal(d, pathBySurface.get("apps"));
      }

      // Valid numeric size applies; invalid sizes fall back to 14.
      const big = kit.icon("blog", 18);
      assert.equal(big.getAttribute("width"), "18");
      assert.equal(big.getAttribute("height"), "18");
      for (const badSize of [0, -5, NaN, Infinity, "xss"]) {
        const def = kit.icon("blog", badSize);
        assert.equal(def.getAttribute("width"), "14");
        assert.equal(def.getAttribute("height"), "14");
      }
    });

    test("statusPill renders tone, dot, default IDLE, mount, and escapes XSS", () => {
      const { document, kit } = loadKitEnv(kitPath);
      const def = kit.statusPill();
      assert.equal(def.className, "bui-pill");
      assert.equal(def.textContent, "IDLE");

      const host = document.createElement("div");
      const ok = kit.statusPill({ id: "p-ok", tone: "ok", label: XSS_TAG, mount: host });
      assert.equal(host.firstChild, ok);
      assert.equal(ok.id, "p-ok");
      assert.ok(ok.classList.contains("bui-pill"));
      assert.ok(ok.classList.contains("bui-ok"));
      assert.equal(ok.textContent, XSS_TAG);
      // Must be plain text node, zero <script> or <img> elements created.
      assert.equal(findAll(ok, (n) => n.nodeType === 1 && (n.tagName === "script" || n.tagName === "img")).length, 0);

      // Unknown tone is ignored safely.
      const badTone = kit.statusPill({ tone: "evil" + " xss", label: "WAIT" });
      assert.equal(badTone.className, "bui-pill");
    });

    test("shell builds 5-surface suite nav, active state, URL sanitization, and XSS safety", () => {
      const { document, BlindUI, kit } = loadKitEnv(kitPath);
      const sso = document.createElement("div");
      sso.id = "sso-slot";
      const mainNode = document.createElement("p");
      mainNode.textContent = "Hello portal";

      const el = kit.shell({
        id: "dev-shell",
        surface: "developers",
        brand: XSS_TAG,
        brandHref: XSS_JS_URL,
        ssoSlot: sso,
        main: mainNode,
        footer: "Copyright Blind Labs",
        mount: document.body,
      });

      assert.equal(document.body.firstChild, el);
      assert.equal(el.id, "dev-shell");

      // Malicious brandHref must degrade to <span> with no href.
      const brandEl = findAll(el, (n) => n.nodeType === 1 && n.classList.contains("bui-brand"))[0];
      assert.ok(brandEl);
      assert.equal(brandEl.tagName, "span");
      assert.equal(brandEl.getAttribute("href"), null);
      assert.ok(brandEl.textContent.includes(XSS_TAG));
      assert.equal(findAll(el, (n) => n.nodeType === 1 && n.tagName === "script").length, 0);

      // Default 5 nav items with developers active and surface SVG icons.
      const navLinks = findAll(el, (n) => n.nodeType === 1 && n.classList.contains("bui-tab"));
      assert.equal(navLinks.length, 5);
      for (const link of navLinks) {
        const surf = link.getAttribute("data-surface");
        const svgs = findAll(link, (n) => n.nodeType === 1 && n.tagName === "svg");
        assert.equal(svgs.length, 1);
        assert.equal(svgs[0].getAttribute("class"), "bk-ic");
        assert.equal(svgs[0].getAttribute("data-surface"), surf);
        const p = findAll(svgs[0], (n) => n.nodeType === 1 && n.tagName === "path")[0];
        assert.ok(p && p.getAttribute("d") && p.getAttribute("d").length >= 10);
      }
      const brandPath = findAll(brandEl, (n) => n.nodeType === 1 && n.tagName === "path")[0];
      assert.ok(brandPath && brandPath.getAttribute("d") && brandPath.getAttribute("d").length >= 10);
      const devLink = navLinks.find((n) => n.getAttribute("data-surface") === "developers");
      assert.ok(devLink);
      assert.equal(devLink.tagName, "a");
      assert.equal(devLink.getAttribute("href"), "/developers/");
      assert.equal(devLink.getAttribute("aria-current"), "page");
      assert.ok(devLink.classList.contains("bui-on"));

      // Custom navItems: dangerous href degrades to <span>, plus icon:false, icon:"mail", and custom SVG passthrough.
      const customSvg = BlindUI.svg("svg", { id: "custom-svg", width: 14, height: 14, viewBox: "0 0 24 24" });
      const mailPath = findAll(kit.icon("mail"), (n) => n.nodeType === 1 && n.tagName === "path")[0].getAttribute("d");
      const custom = kit.shell({
        brandHref: "/developers/",
        navItems: [
          { id: "bad", label: "Evil", href: XSS_JS_URL, icon: false },
          { id: "good", label: "Docs", href: "https://blindlabs.example/docs", active: true, icon: "mail" },
          { id: "cust", label: "Custom", href: "/custom/", icon: customSvg },
        ],
      });
      const brandA = findAll(custom, (n) => n.nodeType === 1 && n.classList.contains("bui-brand"))[0];
      assert.equal(brandA.tagName, "a");
      assert.equal(brandA.getAttribute("href"), "/developers/");
      const tabs = findAll(custom, (n) => n.nodeType === 1 && n.classList.contains("bui-tab"));
      assert.equal(tabs[0].tagName, "span");
      assert.equal(tabs[0].getAttribute("href"), null);
      assert.equal(findAll(tabs[0], (n) => n.nodeType === 1 && n.tagName === "svg").length, 0);
      assert.equal(tabs[1].tagName, "a");
      assert.equal(tabs[1].getAttribute("href"), "https://blindlabs.example/docs");
      assert.equal(tabs[1].getAttribute("aria-current"), "page");
      const tab1Svg = findAll(tabs[1], (n) => n.nodeType === 1 && n.tagName === "svg")[0];
      assert.equal(tab1Svg.getAttribute("data-surface"), "mail");
      assert.equal(findAll(tab1Svg, (n) => n.nodeType === 1 && n.tagName === "path")[0].getAttribute("d"), mailPath);
      assert.equal(findAll(tabs[2], (n) => n.nodeType === 1 && n.id === "custom-svg").length, 1);
    });

    test("kpiStrip supports array shorthand, object options, empty fallback, and XSS escaping", () => {
      const { kit } = loadKitEnv(kitPath);
      const strip = kit.kpiStrip({
        id: "kpis",
        items: [
          { id: "k1", label: "Requests", value: 42, tone: "ok", sub: "24h" },
          { id: "k2", label: XSS_TAG, value: "" },
        ],
      });
      assert.equal(strip.id, "kpis");
      const k1 = findById(strip, "k1");
      const k2 = findById(strip, "k2");
      assert.ok(k1.classList.contains("bui-ok"));
      assert.ok(k1.textContent.includes("42"));
      assert.ok(k1.textContent.includes("24h"));
      assert.ok(k2.textContent.includes("None yet"));
      assert.ok(k2.textContent.includes(XSS_TAG));
      assert.equal(findAll(strip, (n) => n.nodeType === 1 && n.tagName === "script").length, 0);

      const arrOnly = kit.kpiStrip([{ label: "Quota", value: "90%" }]);
      assert.ok(arrOnly.textContent.includes("90%"));
    });

    test("stepRail renders todo/active/done states, SVG check on done, and hides done body", () => {
      const { kit } = loadKitEnv(kitPath);
      const rail = kit.stepRail({
        id: "steps",
        steps: [
          { id: "s1", title: "Sign in", state: "done", summary: "alice@blindmail", body: "HIDDEN_BODY" },
          { id: "s2", title: "Create key", state: "active", body: "ACTIVE_BODY" },
          { id: "s3", title: XSS_TAG, state: "todo", num: "3", body: "TODO_BODY" },
        ],
      });
      const s1 = findById(rail, "s1");
      const s2 = findById(rail, "s2");
      const s3 = findById(rail, "s3");
      assert.equal(s1.getAttribute("data-step-state"), "done");
      assert.ok(s1.classList.contains("bk-dn"));
      assert.ok(!s1.textContent.includes("HIDDEN_BODY"));
      assert.equal(findAll(s1, (n) => n.nodeType === 1 && n.tagName === "svg").length, 1);
      const chkPath = findAll(s1, (n) => n.nodeType === 1 && n.tagName === "path")[0];
      assert.ok(chkPath && chkPath.getAttribute("d") && chkPath.getAttribute("d").length >= 8);

      assert.equal(s2.getAttribute("data-step-state"), "active");
      assert.ok(s2.classList.contains("bk-act"));
      assert.ok(s2.textContent.includes("ACTIVE_BODY"));

      assert.equal(s3.getAttribute("data-step-state"), "todo");
      assert.ok(s3.textContent.includes(XSS_TAG));
      assert.equal(findAll(s3, (n) => n.nodeType === 1 && n.tagName === "script").length, 0);
    });

    test("keyCard handles prefix, quota bar, secretOnce copy+dismiss clearing, and single-flight locks", async () => {
      const { document, kit, clipboardWrites, timers } = loadKitEnv(kitPath);
      let copiedSecret = null;
      let rotateCalls = 0;
      let releaseRotate;
      let revokeCalls = 0;

      const card = kit.keyCard({
        id: "kc",
        title: "Production Key",
        prefix: "bl_live_abc123",
        status: "ACTIVE",
        createdAt: "2026-11-20",
        lastUsedAt: "2026-11-21",
        quota: { label: "Daily Calls", used: 150, limit: 100, unit: "req" },
        secretOnce: "bl_live_abc123_SECRET_TOKEN",
        onCopy: (v) => { copiedSecret = v; },
        onRotate: () => {
          rotateCalls += 1;
          return new Promise((resolve) => { releaseRotate = resolve; });
        },
        onRevoke: () => { revokeCalls += 1; },
        mount: document.body,
      });

      assert.equal(findById(card, "kc-prefix").textContent, "bl_live_abc123...");
      assert.ok(findById(card, "kc-status").classList.contains("bui-ok"));
      const fill = findAll(card, (n) => n.nodeType === 1 && n.classList.contains("bk-qf"))[0];
      assert.equal(fill.style.width, "100%");

      // Copy secretOnce -> writes clipboard, flashes Copied, invokes onCopy.
      const copyBtn = findById(card, "kc-copy");
      await Promise.all(copyBtn.click());
      assert.deepEqual(clipboardWrites, ["bl_live_abc123_SECRET_TOKEN"]);
      assert.equal(copiedSecret, "bl_live_abc123_SECRET_TOKEN");
      assert.equal(copyBtn.textContent, "Copied");
      timers[0].fn();
      assert.equal(copyBtn.textContent, "Copy");

      // Dismiss clears secret from DOM & removes panel; subsequent Copy does not leak secret.
      const secretCode = findById(card, "kc-secret");
      const dismissBtn = findById(card, "kc-dismiss");
      dismissBtn.click();
      assert.equal(secretCode.textContent, "");
      assert.equal(findById(card, "kc-once"), null);
      await Promise.all(copyBtn.click());
      assert.equal(clipboardWrites.length, 1);

      // Mounted rotate button uses BlindUI.bindAction single-flight lock.
      const rotateBtn = findById(card, "kc-rotate");
      const p1 = Promise.all(rotateBtn.click());
      assert.equal(rotateBtn.getAttribute("aria-busy"), "true");
      rotateBtn.click(); // Blocked while in flight!
      assert.equal(rotateCalls, 1);
      releaseRotate();
      await p1;
      assert.equal(rotateBtn.getAttribute("aria-busy"), null);

      // Revoke fires callback cleanly.
      findById(card, "kc-revoke").click();
      assert.equal(revokeCalls, 1);

      // Detached keyCard (not mounted in document.body) still enforces aria-busy single-flight lock.
      let detCalls = 0;
      let releaseDet;
      const detached = kit.keyCard({
        id: "kc-det",
        status: "REVOKED",
        onRotate: () => {
          detCalls += 1;
          return new Promise((resolve) => { releaseDet = resolve; });
        },
      });
      assert.ok(findById(detached, "kc-det-status").classList.contains("bui-err"));
      const detRot = findById(detached, "kc-det-rotate");
      const dp = Promise.all(detRot.click());
      assert.equal(detRot.getAttribute("aria-busy"), "true");
      detRot.click();
      assert.equal(detCalls, 1);
      releaseDet();
      await dp;
      assert.equal(detRot.getAttribute("aria-busy"), null);
    });

    test("codeBlock switches tabs, updates data-lang & aria-selected, copies active code, escapes XSS", async () => {
      const { kit, clipboardWrites } = loadKitEnv(kitPath);
      const copyEvents = [];
      const block = kit.codeBlock({
        id: "cb",
        activeTab: "py",
        tabs: [
          { id: "curl", label: "cURL", code: "curl /api/v1/pricing", lang: "bash" },
          { id: "py", label: "Python", code: XSS_TAG, lang: "python" },
          { id: "raw", label: "Raw", code: "plain", lang: "bad lang!!" },
        ],
        onCopy: (code, tab) => copyEvents.push({ code, id: tab.id }),
      });

      const codeEl = findAll(block, (n) => n.nodeType === 1 && n.tagName === "code")[0];
      assert.equal(codeEl.textContent, XSS_TAG);
      assert.equal(codeEl.getAttribute("data-lang"), "python");
      assert.equal(findById(block, "cb-tab-py").getAttribute("aria-selected"), "true");
      assert.equal(findById(block, "cb-tab-curl").getAttribute("aria-selected"), "false");

      // Switch to curl and copy.
      findById(block, "cb-tab-curl").click();
      assert.equal(codeEl.textContent, "curl /api/v1/pricing");
      assert.equal(codeEl.getAttribute("data-lang"), "bash");
      assert.equal(findById(block, "cb-tab-curl").getAttribute("aria-selected"), "true");
      await Promise.all(findById(block, "cb-copy").click());
      assert.deepEqual(clipboardWrites, ["curl /api/v1/pricing"]);
      assert.deepEqual(copyEvents, [{ code: "curl /api/v1/pricing", id: "curl" }]);

      // Invalid lang removes data-lang attribute.
      findById(block, "cb-tab-raw").click();
      assert.equal(codeEl.getAttribute("data-lang"), null);
    });

    test("tryItPanel switches presets, runs onRun & BlindUI.api fallback, handles 429/errors/renderResult", async () => {
      const { document, kit, fetchCalls } = loadKitEnv(kitPath);
      const seenCalls = [];

      // 1) Custom onRun + 200 OK + 429 LIMITED + error path.
      let nextResp = { ok: true, status: 200, latencyMs: 18, quota: "9 / 100", data: { ok: true, msg: XSS_TAG } };
      const panel = kit.tryItPanel({
        id: "try1",
        title: "API Playground",
        activePreset: "post",
        presets: [
          { id: "get", label: "Pricing", method: "GET", path: "/api/v1/pricing" },
          { id: "post", label: "Sign", method: "POST", route: "/api/v1/sign", body: { doc: "a" } },
        ],
        onRun: async (req) => {
          seenCalls.push(req);
          if (nextResp instanceof Error) throw nextResp;
          return nextResp;
        },
        mount: document.body,
      });

      assert.equal(findById(panel, "try1-route").textContent, "POST /api/v1/sign");
      assert.equal(findById(panel, "try1-preset-post").getAttribute("aria-pressed"), "true");
      assert.ok(findById(panel, "try1-body").value.includes('"doc": "a"'));

      const runBtn = findById(panel, "try1-run");
      await Promise.all(runBtn.click());
      assert.equal(seenCalls.length, 1);
      assert.equal(JSON.stringify(seenCalls[0].body), JSON.stringify({ doc: "a" }));
      assert.equal(findById(panel, "try1-status").textContent, "200 OK");
      assert.ok(findById(panel, "try1-status").classList.contains("bui-ok"));
      assert.equal(findById(panel, "try1-latency").textContent, "18 ms");
      assert.equal(findById(panel, "try1-quota").textContent, "9 / 100");
      assert.ok(findById(panel, "try1-output").textContent.includes(XSS_TAG));
      assert.equal(findAll(panel, (n) => n.nodeType === 1 && n.tagName === "script").length, 0);

      // 429 rate-limited response -> warn tone + "429 LIMITED".
      nextResp = { ok: false, status: 429, error: "rate_limited" };
      await Promise.all(runBtn.click());
      assert.equal(findById(panel, "try1-status").textContent, "429 LIMITED");
      assert.ok(findById(panel, "try1-status").classList.contains("bui-warn"));

      // Thrown error -> err tone + message rendered safely.
      nextResp = new Error("network_down");
      await Promise.all(runBtn.click());
      assert.equal(findById(panel, "try1-status").textContent, "ERROR");
      assert.ok(findById(panel, "try1-status").classList.contains("bui-err"));
      assert.equal(findById(panel, "try1-output").textContent, "network_down");

      // Switch preset updates route and clears body.
      findById(panel, "try1-preset-get").click();
      assert.equal(findById(panel, "try1-route").textContent, "GET /api/v1/pricing");
      assert.equal(findById(panel, "try1-body").value, "");

      // 2) BlindUI.api fallback + custom renderResult (returns safe node).
      const apiPanel = kit.tryItPanel({
        id: "try2",
        presets: [{ id: "echo", label: "Echo", method: "POST", path: "/api/v1/echo", body: { x: 1 }, headers: { "X-Test": "1" } }],
        renderResult: (res) => {
          const box = document.createElement("div");
          box.id = "custom-res";
          box.textContent = "STATUS=" + res.status;
          return box;
        },
      });
      await Promise.all(findById(apiPanel, "try2-run").click());
      assert.equal(fetchCalls.length, 1);
      assert.equal(fetchCalls[0].url, "/api/v1/echo");
      assert.equal(fetchCalls[0].init.method, "POST");
      assert.equal(fetchCalls[0].init.headers["X-Test"], "1");
      assert.equal(findById(apiPanel, "custom-res").textContent, "STATUS=200");
    });
  });
}

describe("BlindUI Kit Budgets & Hygiene", () => {
  test("core < 28,672B, kit <= 16,384B, tokens <= 4,096B, 100% ASCII, 0 sinks and 0 dot-clamp", () => {
    const coreRaw = fs.readFileSync(CORE_MIN_PATH);
    const kitRaw = fs.readFileSync(KIT_MIN_PATH);
    const tokRaw = fs.readFileSync(TOKENS_PATH);
    assert.ok(coreRaw.length < 28672, `blindui.min.js ${coreRaw.length} >= 28672`);
    assert.ok(kitRaw.length <= 16384, `blindui-kit.min.js ${kitRaw.length} > 16384`);
    assert.ok(tokRaw.length <= 4096, `blindui-tokens.css ${tokRaw.length} > 4096`);

    for (const p of [KIT_SRC_PATH, KIT_MIN_PATH, TOKENS_PATH]) {
      const raw = fs.readFileSync(p);
      for (const b of raw) assert.ok(b <= 0x7f, `${path.basename(p)} has non-ASCII byte 0x${b.toString(16)}`);
      const txt = raw.toString("ascii");
      const low = txt.toLowerCase();
      for (const needle of SINK_NEEDLES) {
        assert.ok(!low.includes(needle.toLowerCase()), `${path.basename(p)} contains forbidden literal ${needle}`);
      }
      assert.equal(CLAMP_RE.test(txt), false, `${path.basename(p)} contains forbidden dot-clamp call`);
    }

    // CSS token invariants: 0 gradients, prefers-reduced-motion:reduce, >= 8 distinct @keyframes, .bk-in width:100%.
    const tokTxt = tokRaw.toString("ascii");
    for (const g of ["linear-gradient", "radial-gradient", "conic-gradient"]) {
      assert.equal(tokTxt.includes(g), false, `blindui-tokens.css contains forbidden ${g}`);
    }
    assert.ok(tokTxt.includes("prefers-reduced-motion:reduce"), "blindui-tokens.css missing prefers-reduced-motion:reduce");
    const kfNames = new Set(Array.from(tokTxt.matchAll(/@keyframes\s+([a-zA-Z0-9_-]+)/g), (m) => m[1]));
    assert.ok(kfNames.size >= 8, `blindui-tokens.css needs >= 8 distinct @keyframes, got ${kfNames.size}`);
    assert.match(tokTxt, /\.bk-in[^{}]*\{[^}]*width:100%/, "blindui-tokens.css missing width:100% on .bk-in");
    assert.match(tokTxt, /\.bk-bar,\.bui-box,\.bui-pre\{[^}]*max-width:100%/, "blindui-tokens.css missing max-width:100% on overflow boxes");
  });
});
