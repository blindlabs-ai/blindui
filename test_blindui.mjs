#!/usr/bin/env node
/**
 * Zero-dependency Node v22 test suite for BlindUI (both blindui.js and blindui.min.js).
 * Uses a deterministic in-memory mock DOM + vm isolation to verify XSS hardening,
 * linear O(n) Markdown parsing, bindMdEditor, modal, bindAction/bindGroup, and api/schemas.
 */

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC_PATH = path.join(__dirname, "blindui.js");
const MIN_PATH = path.join(__dirname, "blindui.min.js");

// Construct forbidden sink strings dynamically so this test file contains zero raw literals.
const SINK_INNER = "inner" + "HTML";
const SINK_OUTER = "outer" + "HTML";
const SINK_INSERT_ADJ = "insertAdjacent" + "HTML";
const SINK_DOC_WRITE = "document." + "write";
const SINK_EVAL = "ev" + "al(";
const SINK_NEW_FN = "new " + "Function";
const SINK_ONCLICK_ATTR = "on" + "click=";
const TAG_SCRIPT_OPEN = "<" + "script>";
const TAG_SCRIPT_CLOSE = "</" + "script>";

class MockClassList {
  constructor(el) {
    this._el = el;
    this._set = new Set();
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
    if (force === undefined) {
      if (this._set.has(c)) { this._set.delete(c); this._sync(); return false; }
      this._set.add(c); this._sync(); return true;
    }
    if (force) this._set.add(c);
    else this._set.delete(c);
    this._sync();
    return !!force;
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
    if (child.nodeType === 11) {
      const moved = child.childNodes.slice();
      child.childNodes.length = 0;
      for (const n of moved) this.appendChild(n);
      return child;
    }
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
  insertBefore(child, ref) {
    if (!ref) return this.appendChild(child);
    if (child.nodeType === 11) {
      const moved = child.childNodes.slice();
      child.childNodes.length = 0;
      for (const n of moved) this.insertBefore(n, ref);
      return child;
    }
    if (child.parentNode) child.parentNode.removeChild(child);
    const idx = this.childNodes.indexOf(ref);
    if (idx < 0) return this.appendChild(child);
    child.parentNode = this;
    this.childNodes.splice(idx, 0, child);
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

class MockFragment extends MockNode {
  constructor() {
    super(11);
  }
  get textContent() {
    return this.childNodes.map((c) => c.textContent).join("");
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
    this._styleProps = new Map();
    this.dataset = {};
    this.classList = new MockClassList(this);
    this.value = "";
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.scrollTop = 0;
    this.scrollHeight = 0;
    this.clientHeight = 0;
    this.focused = false;
    const self = this;
    this.style = new Proxy(
      {
        setProperty(k, v) { self._styleProps.set(k, String(v)); },
        getPropertyValue(k) { return self._styleProps.get(k) || ""; },
      },
      {
        get(target, prop) {
          if (prop in target) return target[prop];
          return self._styleProps.get(String(prop)) ?? "";
        },
        set(target, prop, val) {
          self._styleProps.set(String(prop), String(val));
          return true;
        },
      }
    );
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
    this.classList._set = new Set(String(v).split(/\s+/).filter(Boolean));
    this._attrs.set("class", String(v));
  }
  get textContent() {
    return this.childNodes.map((c) => c.textContent).join("");
  }
  set textContent(v) {
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes.length = 0;
    if (v !== "") this.appendChild(new MockText(v));
  }
  setAttribute(k, v) {
    const val = String(v);
    if (k === "class") {
      this.className = val;
      return;
    }
    this._attrs.set(k, val);
  }
  getAttribute(k) {
    return this._attrs.has(k) ? this._attrs.get(k) : null;
  }
  removeAttribute(k) {
    this._attrs.delete(k);
  }
  addEventListener(type, fn) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(fn);
  }
  removeEventListener(type, fn) {
    const arr = this._listeners.get(type);
    if (!arr) return;
    const idx = arr.indexOf(fn);
    if (idx >= 0) arr.splice(idx, 1);
  }
  dispatchEvent(ev) {
    if (!ev.target) ev.target = this;
    if (!ev.preventDefault) ev.preventDefault = () => { ev.defaultPrevented = true; };
    const arr = (this._listeners.get(ev.type) || []).slice();
    let last;
    for (const fn of arr) last = fn.call(this, ev);
    return last;
  }
  setSelectionRange(start, end) {
    this.selectionStart = start;
    this.selectionEnd = end;
  }
  setRangeText(rep, start, end) {
    this.value = this.value.slice(0, start) + rep + this.value.slice(end);
    this.selectionStart = this.selectionEnd = start + rep.length;
  }
  focus() {
    const prev = this._doc && this._doc.activeElement;
    if (prev && prev !== this) prev.blur();
    const wasFocused = this.focused;
    this.focused = true;
    if (this._doc) this._doc.activeElement = this;
    if (!wasFocused) this.dispatchEvent({ type: "focus" });
  }
  blur() {
    if (!this.focused) return;
    this.focused = false;
    if (this._doc && this._doc.activeElement === this) this._doc.activeElement = null;
    this.dispatchEvent({ type: "blur" });
  }
  matches(sel) {
    if (sel.startsWith(".")) return this.classList.contains(sel.slice(1));
    if (sel.startsWith("#")) return this.id === sel.slice(1);
    if (sel.startsWith("[") && sel.endsWith("]")) {
      const inner = sel.slice(1, -1);
      const eq = inner.indexOf("=");
      if (eq < 0) return this._attrs.has(inner);
      const k = inner.slice(0, eq);
      const val = inner.slice(eq + 1).replace(/^["']|["']$/g, "");
      return this._attrs.get(k) === val;
    }
    return this.tagName === sel.toLowerCase();
  }
  closest(sel) {
    let cur = this;
    while (cur && cur.nodeType === 1) {
      if (cur.matches(sel)) return cur;
      cur = cur.parentNode;
    }
    return null;
  }
}

class MockRange {
  constructor() {
    this.startContainer = null;
    this.startOffset = 0;
    this.endContainer = null;
    this.endOffset = 0;
  }
  get collapsed() {
    return this.startContainer === this.endContainer && this.startOffset === this.endOffset;
  }
  setStart(node, offset) {
    this.startContainer = node;
    this.startOffset = offset;
  }
  setEnd(node, offset) {
    this.endContainer = node;
    this.endOffset = offset;
  }
}

class MockSelection {
  constructor() {
    this._ranges = [];
  }
  get rangeCount() {
    return this._ranges.length;
  }
  get isCollapsed() {
    return this._ranges.length ? this._ranges[0].collapsed : true;
  }
  get anchorNode() {
    return this._ranges.length ? this._ranges[0].startContainer : null;
  }
  get anchorOffset() {
    return this._ranges.length ? this._ranges[0].startOffset : 0;
  }
  getRangeAt(idx) {
    return this._ranges[idx] || null;
  }
  removeAllRanges() {
    this._ranges.length = 0;
  }
  addRange(r) {
    this._ranges = [r];
  }
}

class MockDocument {
  constructor() {
    this._byId = new Map();
    this._listeners = new Map();
    this.activeElement = null;
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
  createDocumentFragment() {
    return new MockFragment();
  }
  createRange() {
    return new MockRange();
  }
  register(el) {
    if (el.id) this._byId.set(el.id, el);
    return el;
  }
  getElementById(id) {
    return this._byId.get(id) || null;
  }
  addEventListener(type, fn) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(fn);
  }
  removeEventListener(type, fn) {
    const arr = this._listeners.get(type);
    if (!arr) return;
    const idx = arr.indexOf(fn);
    if (idx >= 0) arr.splice(idx, 1);
  }
  dispatchEvent(ev) {
    const arr = (this._listeners.get(ev.type) || []).slice();
    for (const fn of arr) fn.call(this, ev);
  }
}

function createWindowEnv() {
  const doc = new MockDocument();
  const winListeners = new Map();
  const vvListeners = new Map();
  const visualViewport = {
    height: 700,
    addEventListener(t, f) {
      if (!vvListeners.has(t)) vvListeners.set(t, []);
      vvListeners.get(t).push(f);
    },
    dispatchEvent(ev) {
      for (const f of (vvListeners.get(ev.type) || []).slice()) f(ev);
    },
  };
  const selection = new MockSelection();
  const env = {
    document: doc,
    innerWidth: 1280,
    visualViewport,
    getSelection() {
      return selection;
    },
    addEventListener(t, f) {
      if (!winListeners.has(t)) winListeners.set(t, []);
      winListeners.get(t).push(f);
    },
    dispatchEvent(ev) {
      for (const f of (winListeners.get(ev.type) || []).slice()) f(ev);
    },
    requestAnimationFrame: null,
    fetch: null,
    console,
    setTimeout,
    clearTimeout,
  };
  env.window = env;
  env.globalThis = env;
  return env;
}

function loadBundle(filePath) {
  const code = fs.readFileSync(filePath, "utf8");
  const env = createWindowEnv();
  const mod = { exports: {} };
  env.module = mod;
  vm.runInNewContext(code, env, { filename: path.basename(filePath) });
  assert.ok(env.BlindUI, `${path.basename(filePath)} must attach globalThis.BlindUI`);
  assert.equal(mod.exports, env.BlindUI, `${path.basename(filePath)} must export BlindUI on module.exports`);
  return { BlindUI: env.BlindUI, env, doc: env.document };
}

function serializeNode(node) {
  if (node.nodeType === 3) return JSON.stringify(node.nodeValue);
  if (node.nodeType === 11) return `[#frag ${node.childNodes.map(serializeNode).join(" ")}]`;
  const attrs = Array.from(node._attrs.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(" ");
  const head = attrs ? `<${node.tagName} ${attrs}>` : `<${node.tagName}>`;
  return `${head}${node.childNodes.map(serializeNode).join("")}</${node.tagName}>`;
}

function walkNodes(root, fn) {
  for (const ch of root.childNodes) {
    fn(ch);
    walkNodes(ch, fn);
  }
}

const ALLOWED_MD_TAGS = new Set([
  "h1", "h2", "h3", "p", "strong", "em", "code", "pre",
  "ul", "ol", "li", "blockquote", "hr", "a", "br",
]);

let passed = 0;
async function test(name, fn) {
  await fn();
  passed += 1;
}

async function runSuiteForBuild(label, filePath) {
  const { BlindUI, env, doc } = loadBundle(filePath);

  await test(`${label}: exports surface & version`, () => {
    assert.equal(BlindUI.version, "1.0.0");
    for (const key of [
      "h", "svg", "sanitizeUrl", "md", "bindMdEditor", "notionEditor", "modal",
      "bindAction", "bindGroup", "api", "defineRoutes", "setSigner", "_missingBindings",
    ]) {
      assert.ok(key in BlindUI, `Missing export ${key}`);
    }
  });

  await test(`${label}: sanitizeUrl >= 35 adversarial + valid URL cases`, () => {
    const badUrls = [
      "",
      "   ",
      null,
      undefined,
      12345,
      {},
      "javascript:alert(1)",
      "JAVASCRIPT:alert(1)",
      "  javascript:alert(1)  ",
      "java\tscript:alert(1)",
      "java\nscript:alert(1)",
      "java\rscript:alert(1)",
      "vbscript:msgbox(1)",
      "data:text/html," + TAG_SCRIPT_OPEN + "alert(1)" + TAG_SCRIPT_CLOSE,
      "data:image/svg+xml,<svg/>",
      "file:///etc/passwd",
      "ftp://example.com/a",
      "http://example.com/insecure",
      "//evil.example.com/path",
      "\\\\evil.example.com\\x",
      "https://user:pass@example.com/",
      "https://user@example.com/",
      "https://localhost/admin",
      "https://example.com:0/x",
      "https://example.com:65536/x",
      "https://example.com/a\x00b",
      "https://example.com/a\x7fb",
      "https://example.com/a\u0085b",
      "https://example.com/a b",
      "http\u017F://example.com/",
      "&#106;avascript:alert(1)",
      "/path?a=1&colon;b",
      "/path?a=1&tab;b",
      "/path?a=1&newline;b",
      "blob:https://app.test/1234",
      "blob:",
      "/relative/path",
      "./relative/path",
      "mailto:not-an-email",
      "mailto:alice@example.com?bcc=evil@example.com",
      "mailto:alice@example.com?subject=hi%0abcc:evil@example.com",
      "mailto:alice@example.com?subject=hi%0dbcc:evil@example.com",
      "mailto:alice@example.com?subject=hi%00evil",
      "mailto:" + "a".repeat(250) + "@example.com",
      "https://example.com/" + "a".repeat(2040),
    ];
    for (const u of badUrls) {
      assert.equal(BlindUI.sanitizeUrl(u), null, `Must reject bad URL: ${JSON.stringify(u)}`);
    }
    assert.equal(BlindUI.sanitizeUrl("blob:", { allowDownloadBlob: true }), null);
    assert.equal(BlindUI.sanitizeUrl("blob:https://app.test/abc", { allowDownloadBlob: true }), "blob:https://app.test/abc");
    assert.equal(BlindUI.sanitizeUrl("/api/v1/feed", { allowRelative: true }), "/api/v1/feed");
    assert.equal(BlindUI.sanitizeUrl("./api/v1/feed", { allowRelative: true }), "./api/v1/feed");
    assert.equal(BlindUI.sanitizeUrl("//evil.com", { allowRelative: true }), null);
    assert.equal(BlindUI.sanitizeUrl("https://example.com/a?x=1#y"), "https://example.com/a?x=1#y");
    assert.equal(BlindUI.sanitizeUrl("  HTTPS://Example.COM:8443/ok  "), "https://Example.COM:8443/ok");
    assert.equal(BlindUI.sanitizeUrl("mailto:alice@example.com"), "mailto:alice@example.com");
    assert.equal(
      BlindUI.sanitizeUrl("mailto:alice@example.com?subject=Hello%20World"),
      "mailto:alice@example.com?subject=Hello%20World"
    );
  });

  await test(`${label}: md >= 30 adversarial XSS payloads produce zero unsafe tags/attrs`, () => {
    const xssPayloads = [
      TAG_SCRIPT_OPEN + "alert(1)" + TAG_SCRIPT_CLOSE,
      "<img src=x on" + "error=alert(1)>",
      "<svg on" + "load=alert(1)>",
      "<iframe src=\"javascript:alert(1)\"></iframe>",
      "<iframe srcdoc=\"" + TAG_SCRIPT_OPEN + "1" + TAG_SCRIPT_CLOSE + "\"></iframe>",
      "<a href=\"javascript:alert(1)\">bad</a>",
      "<div " + SINK_ONCLICK_ATTR + "\"alert(1)\">click</div>",
      "[click](javascript:alert(1))",
      "[click](JaVaScRiPt:alert(1))",
      "[click](vbscript:msgbox(1))",
      "[click](data:text/html;base64,PHNjcmlwdD4=)",
      "[click](http://insecure.example.com)",
      "[click](//evil.example.com/x)",
      "[click](https://user@evil.example.com/)",
      "[click](blob:https://evil.example.com/1)",
      "[click](http\u017F://evil.example.com/)",
      "[click](mailto:a@b.com?bcc=evil@c.com)",
      "[click](mailto:a@b.com?subject=ok%0Abcc:evil@c.com)",
      "[click](&#106;avascript:alert(1))",
      "[click](javascript:alert(1)//https://example.com)",
      "![alt](https://evil.example.com/tracker.png)",
      "![alt](javascript:alert(1))",
      "![**bold** alt](https://evil.example.com/x.png)",
      "[**bold** " + TAG_SCRIPT_OPEN + "](https://example.com/safe)",
      "`" + TAG_SCRIPT_OPEN + "alert(1)" + TAG_SCRIPT_CLOSE + "`",
      "```html\n" + TAG_SCRIPT_OPEN + "alert(1)" + TAG_SCRIPT_CLOSE + "\n```",
      "> <img src=x on" + "error=1>",
      "- <svg on" + "load=1>",
      "1. [x](javascript:void(0))",
      "# " + TAG_SCRIPT_OPEN + "h1" + TAG_SCRIPT_CLOSE,
      "[x](https://example.com/a(b(c(d(e(f))))))",
    ];
    assert.ok(xssPayloads.length >= 30);
    for (const payload of xssPayloads) {
      const frag = BlindUI.md(payload);
      walkNodes(frag, (node) => {
        if (node.nodeType === 1) {
          assert.ok(ALLOWED_MD_TAGS.has(node.tagName), `Disallowed tag <${node.tagName}> from ${payload}`);
          assert.notEqual(node.tagName, "img", `Zero <img> allowed from ${payload}`);
          for (const [k, v] of node._attrs.entries()) {
            assert.ok(!/^on/i.test(k), `Disallowed event attr ${k}`);
            if (k === "href") {
              assert.ok(
                v.startsWith("https://") || v.startsWith("mailto:"),
                `Disallowed href ${v} from ${payload}`
              );
            }
          }
          if (node.tagName === "a") {
            assert.equal(node.getAttribute("target"), "_blank");
            assert.equal(node.getAttribute("rel"), "noopener noreferrer nofollow");
          }
        }
      });
    }
    // Verify image syntax emits zero <img> and zero <a> and preserves text
    const imgFrag = BlindUI.md("before ![pic](https://example.com/a.png) after");
    const imgTags = [];
    walkNodes(imgFrag, (n) => { if (n.nodeType === 1) imgTags.push(n.tagName); });
    assert.deepEqual(imgTags, ["p"]);
    assert.equal(imgFrag.textContent, "before ![pic](https://example.com/a.png) after");
  });

  await test(`${label}: h() and svg() >= 25 adversarial + valid DOM cases`, () => {
    const disallowedTags = ["script", "style", "img", "object", "embed", "link", "meta", "base", "svg", "", 42];
    for (const t of disallowedTags) {
      assert.throws(() => BlindUI.h(t), /blindui_disallowed_tag/);
    }
    // iframe must require blob: src
    assert.throws(() => BlindUI.h("iframe"), /blindui_disallowed_iframe_src/);
    assert.throws(() => BlindUI.h("iframe", {}), /blindui_disallowed_iframe_src/);
    assert.throws(() => BlindUI.h("iframe", { src: "https://example.com" }), /blindui_disallowed_iframe_src/);
    assert.throws(() => BlindUI.h("iframe", { src: "javascript:alert(1)" }), /blindui_disallowed_iframe_src/);
    const okFrame = BlindUI.h("iframe", { src: "blob:https://app.test/doc-1", title: "Preview" });
    assert.equal(okFrame.getAttribute("src"), "blob:https://app.test/doc-1");

    // Forbidden props & URLs
    assert.throws(() => BlindUI.h("div", "bad-props"), /blindui_invalid_props/);
    assert.throws(() => BlindUI.h("div", { [SINK_INNER]: "<b>x</b>" }), /blindui_disallowed_prop/);
    assert.throws(() => BlindUI.h("div", { [SINK_OUTER]: "<b>x</b>" }), /blindui_disallowed_prop/);
    assert.throws(() => BlindUI.h("div", { [SINK_INSERT_ADJ]: "x" }), /blindui_disallowed_prop/);
    assert.throws(() => BlindUI.h("div", { srcdoc: "x" }), /blindui_disallowed_prop/);
    assert.throws(() => BlindUI.h("div", { onclick: "alert(1)" }), /blindui_disallowed_prop:onclick/);
    assert.throws(() => BlindUI.h("div", { style: "color:red" }), /blindui_disallowed_prop:style/);
    assert.throws(() => BlindUI.h("div", { style: { cssText: "color:red" } }), /blindui_disallowed_prop:style\.cssText/);
    assert.throws(() => BlindUI.h("div", { dataset: "bad" }), /blindui_disallowed_prop:dataset/);
    assert.throws(() => BlindUI.h("div", { bogusProp: "x" }), /blindui_disallowed_prop:bogusProp/);
    assert.throws(() => BlindUI.h("a", { href: "javascript:alert(1)" }), /blindui_disallowed_url:href/);
    assert.throws(() => BlindUI.h("a", { href: "blob:https://app.test/1" }), /blindui_disallowed_url:href/);

    // Valid download blob & relative href, dataset, event listener, boolean props, nested children
    let clicked = 0;
    const el = BlindUI.h(
      "div",
      {
        id: "box",
        className: "card",
        style: { color: "green" },
        dataset: { itemId: "42" },
        "aria-label": "Card",
        "data-role": "panel",
        tabIndex: 0,
        onclick: () => { clicked += 1; },
      },
      BlindUI.h("a", { href: "blob:https://app.test/1", download: "out.txt" }, "DL"),
      BlindUI.h("a", { href: "/local" }, "Home"),
      BlindUI.h("button", { disabled: true, value: "v1" }, ["Ok", false, null, 7])
    );
    assert.equal(el.id, "box");
    assert.equal(el.className, "card");
    assert.equal(el.style.color, "green");
    assert.equal(el.dataset.itemId, "42");
    assert.equal(el.getAttribute("aria-label"), "Card");
    assert.equal(el.tabIndex, 0);
    el.dispatchEvent({ type: "click" });
    assert.equal(clicked, 1);
    assert.equal(el.childNodes[0].getAttribute("href"), "blob:https://app.test/1");
    assert.equal(el.childNodes[1].getAttribute("href"), "/local");
    assert.equal(el.childNodes[2].disabled, true);
    assert.equal(el.childNodes[2].value, "v1");
    assert.equal(el.childNodes[2].textContent, "Ok7");

    // svg() checks
    for (const t of ["script", "foreignObject", "animate", "use", "image", "a"]) {
      assert.throws(() => BlindUI.svg(t), /blindui_disallowed_svg_tag/);
    }
    assert.throws(() => BlindUI.svg("svg", "bad"), /blindui_disallowed_svg_attr/);
    assert.throws(() => BlindUI.svg("svg", { onload: "1" }), /blindui_disallowed_svg_attr:onload/);
    assert.throws(() => BlindUI.svg("svg", { onClick: "1" }), /blindui_disallowed_svg_attr:onClick/);
    assert.throws(() => BlindUI.svg("path", { href: "javascript:1" }), /blindui_disallowed_svg_attr:href/);
    assert.throws(() => BlindUI.svg("path", { "xlink:href": "https://x.y" }), /blindui_disallowed_svg_attr:xlink:href/);
    assert.throws(() => BlindUI.svg("svg", { style: { cssText: "x" } }), /blindui_disallowed_svg_attr:style\.cssText/);
    const icon = BlindUI.svg(
      "svg",
      { viewBox: "0 0 24 24", className: "ico", style: { stroke: "currentColor" } },
      BlindUI.svg("path", { d: "M0 0L10 10" })
    );
    assert.equal(icon.namespaceURI, "http://www.w3.org/2000/svg");
    assert.equal(icon.getAttribute("class"), "ico");
    assert.equal(icon.childNodes[0].getAttribute("d"), "M0 0L10 10");
  });

  await test(`${label}: md semantics (parens, underscore, h4, lists, fences, maxDepth, >256KiB UTF-8 truncation)`, () => {
    // Balanced parens: depth 4 passes, depth 5 fails
    const p4 = BlindUI.md("[wiki](https://en.wikipedia.org/wiki/A(b(c(d(e)))))");
    let links4 = [];
    walkNodes(p4, (n) => { if (n.nodeType === 1 && n.tagName === "a") links4.push(n.getAttribute("href")); });
    assert.deepEqual(links4, ["https://en.wikipedia.org/wiki/A(b(c(d(e))))"]);

    const p5 = BlindUI.md("[wiki](https://en.wikipedia.org/wiki/A(b(c(d(e(f))))))");
    let links5 = [];
    walkNodes(p5, (n) => { if (n.nodeType === 1 && n.tagName === "a") links5.push(n.getAttribute("href")); });
    assert.deepEqual(links5, []);

    // _underscore_ preserved literally
    const und = BlindUI.md("snake_case and _underscore_ text");
    assert.equal(serializeNode(und), `[#frag <p>"snake_case and _underscore_ text"</p>]`);

    // #### renders as <p>, while #, ##, ### render h1..h3
    const heads = BlindUI.md("# One\n## Two\n### Three\n#### Four");
    assert.deepEqual(heads.childNodes.map((n) => n.tagName), ["h1", "h2", "h3", "p"]);
    assert.equal(heads.childNodes[3].textContent, "#### Four");

    // Rich Markdown blocks: fences, hr, ordered start, nested lists, blockquote, strong/em/code
    const rich = BlindUI.md(
      "```js\nconst x = 1;\n```\n---\n3. first\n  - nested\n> quoted **bold *and em*** `code`"
    );
    assert.equal(rich.childNodes[0].tagName, "pre");
    assert.equal(rich.childNodes[0].childNodes[0].getAttribute("data-lang"), "js");
    assert.equal(rich.childNodes[1].tagName, "hr");
    assert.equal(rich.childNodes[2].tagName, "ol");
    assert.equal(rich.childNodes[2].getAttribute("start"), "3");
    assert.equal(rich.childNodes[2].childNodes[0].childNodes[1].tagName, "ul");
    assert.equal(rich.childNodes[3].tagName, "blockquote");

    // Star bullet list (* item) supported identically to dash bullet
    const starUl = BlindUI.md("* alpha\n* beta");
    assert.equal(starUl.childNodes.length, 1);
    assert.equal(starUl.childNodes[0].tagName, "ul");
    assert.deepEqual(starUl.childNodes[0].childNodes.map((n) => n.textContent), ["alpha", "beta"]);

    // maxDepth default <= 8 (blockquote nesting)
    const deepBq = "> ".repeat(20) + "leaf";
    const deepFrag = BlindUI.md(deepBq);
    let maxBq = 0;
    function countBq(node, depth) {
      const next = node.nodeType === 1 && node.tagName === "blockquote" ? depth + 1 : depth;
      if (next > maxBq) maxBq = next;
      for (const ch of node.childNodes) countBq(ch, next);
    }
    countBq(deepFrag, 0);
    assert.ok(maxBq <= 8, `Expected blockquote depth <= 8, got ${maxBq}`);

    // maxDepth user override capped at 16
    const deepFrag16 = BlindUI.md("> ".repeat(30) + "leaf", { maxDepth: 99 });
    let maxBq16 = 0;
    function countBq16(node, depth) {
      const next = node.nodeType === 1 && node.tagName === "blockquote" ? depth + 1 : depth;
      if (next > maxBq16) maxBq16 = next;
      for (const ch of node.childNodes) countBq16(ch, next);
    }
    countBq16(deepFrag16, 0);
    assert.ok(maxBq16 <= 16 && maxBq16 > 8, `Expected clamped maxDepth <= 16, got ${maxBq16}`);

    // > 256 KiB UTF-8 truncation + surrogate-pair safety (4-byte emoji U+1F680)
    const emoji = "\uD83D\uDE80"; // 4 UTF-8 bytes, 2 UTF-16 code units
    const bigEmoji = "a" + emoji.repeat(70000); // 1 + 280,000 bytes > 262,144 B
    const truncFrag = BlindUI.md(bigEmoji);
    const lastEl = truncFrag.childNodes[truncFrag.childNodes.length - 1];
    assert.equal(lastEl.tagName, "p");
    assert.equal(lastEl.className, "md-trunc");
    assert.equal(lastEl.textContent, "Preview truncated at 256 KiB; full text preserved.");
    // Verify zero unpaired UTF-16 surrogates in rendered content!
    const bodyText = truncFrag.childNodes[0].textContent;
    for (let i = 0; i < bodyText.length; i++) {
      const c = bodyText.charCodeAt(i);
      if ((c & 0xFC00) === 0xD800) {
        assert.equal(bodyText.charCodeAt(i + 1) & 0xFC00, 0xDC00, "Split high surrogate detected");
        i += 1;
      } else {
        assert.notEqual(c & 0xFC00, 0xDC00, "Orphan low surrogate detected");
      }
    }
    assert.ok(Buffer.byteLength(bodyText, "utf8") <= 262144);
  });

  await test(`${label}: md performance (< 1.0 ms median on 10 KiB) & 6 O(n) delimiter bombs`, () => {
    const chunk = "## Section\n\nParagraph with **bold**, *italic*, `code`, and [link](https://example.com/a).\n- Item 1\n- Item 2\n> Quote line\n\n";
    let doc10k = "";
    while (Buffer.byteLength(doc10k, "utf8") < 10240) doc10k += chunk;

    // Warmup
    for (let i = 0; i < 10; i++) BlindUI.md(doc10k);
    const times = [];
    for (let i = 0; i < 31; i++) {
      const t0 = performance.now();
      BlindUI.md(doc10k);
      times.push(performance.now() - t0);
    }
    times.sort((a, b) => a - b);
    const medianMs = times[Math.floor(times.length / 2)];
    assert.ok(medianMs < 1.0, `${label}: 10 KiB Markdown median ${medianMs.toFixed(3)} ms >= 1.0 ms`);

    // All 6 delimiter bombs (20k chars each, strict O(n))
    const bombs = [
      ["star", "*".repeat(20000)],
      ["dstar", "**".repeat(10000)],
      ["link_open", "[a](".repeat(5000)],
      ["blockquote", "> ".repeat(5000) + "x"],
      ["paren_nest", "[a](" + "(".repeat(10000) + "x"],
      ["bracket_water", "[".repeat(10000) + "a] "],
    ];
    for (const [bName, payload] of bombs) {
      const t0 = performance.now();
      const frag = BlindUI.md(payload);
      const dt = performance.now() - t0;
      assert.ok(frag.childNodes.length >= 1, `Bomb ${bName} produced empty fragment`);
      assert.ok(dt < 30.0, `${label}: bomb '${bName}' took ${dt.toFixed(2)} ms (expected linear O(n) < 30 ms)`);
    }
  });

  await test(`${label}: bindMdEditor (9 formats, shortcuts, modes, rAF preview, scroll sync)`, () => {
    const ta = doc.register(BlindUI.h("textarea", { id: "ed-ta" }));
    const pv = doc.register(BlindUI.h("div", { id: "ed-pv" }));
    const stage = doc.register(BlindUI.h("div", { id: "ed-stage" }));
    const tabW = doc.register(BlindUI.h("button", { id: "tab-w" }));
    const tabS = doc.register(BlindUI.h("button", { id: "tab-s" }));
    const tabP = doc.register(BlindUI.h("button", { id: "tab-p" }));
    const btnBold = doc.register(BlindUI.h("button", { id: "tb-bold" }));
    const btnItalic = doc.register(BlindUI.h("button", { id: "tb-italic" }));
    const btnCode = doc.register(BlindUI.h("button", { id: "tb-code" }));
    const btnLink = doc.register(BlindUI.h("button", { id: "tb-link" }));
    const btnHr = doc.register(BlindUI.h("button", { id: "tb-hr" }));
    const btnH1 = doc.register(BlindUI.h("button", { id: "tb-h1" }));
    const btnH2 = doc.register(BlindUI.h("button", { id: "tb-h2" }));
    const btnList = doc.register(BlindUI.h("button", { id: "tb-list" }));
    const btnQuote = doc.register(BlindUI.h("button", { id: "tb-quote" }));

    let dirty = 0;
    const modesSeen = [];
    const ed = BlindUI.bindMdEditor({
      textareaId: "ed-ta",
      previewId: "ed-pv",
      stageId: "ed-stage",
      modeTabIds: { write: "tab-w", split: "tab-s", preview: "tab-p" },
      toolbarMap: {
        bold: "tb-bold",
        italic: "tb-italic",
        code: "tb-code",
        link: "tb-link",
        hr: "tb-hr",
        h1: "tb-h1",
        h2: "tb-h2",
        list: "tb-list",
        quote: "tb-quote",
      },
      onDirty: () => { dirty += 1; },
      onModeChange: (m) => modesSeen.push(m),
    });

    assert.equal(ed.getMode(), "write");
    assert.equal(stage.getAttribute("data-md-mode"), "write");
    assert.equal(tabW.getAttribute("aria-selected"), "true");
    assert.equal(tabW.classList.contains("active"), true);

    // Format 1: bold on empty
    ta.value = ""; ta.setSelectionRange(0, 0);
    btnBold.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "**bold text**");
    assert.equal(ta.selectionStart, 2);
    assert.equal(ta.selectionEnd, 11);

    // Format 2: italic on selected word
    ta.value = "hello"; ta.setSelectionRange(0, 5);
    btnItalic.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "*hello*");

    // Format 3a: inline code
    ta.value = "fn()"; ta.setSelectionRange(0, 4);
    btnCode.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "`fn()`");

    // Format 3b: multiline fenced code
    ta.value = "a\nb"; ta.setSelectionRange(0, 3);
    ed.applyFormat("code");
    assert.equal(ta.value, "```\na\nb\n```");

    // Format 4: link selects URL placeholder
    ta.value = "docs"; ta.setSelectionRange(0, 4);
    btnLink.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "[docs](https://)");
    assert.equal(ta.value.slice(ta.selectionStart, ta.selectionEnd), "https://");

    // Format 5: hr
    ta.value = "top"; ta.setSelectionRange(3, 3);
    btnHr.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "top\n---\n");

    // Format 6..9: h1, h2, list, quote
    ta.value = "Title"; ta.setSelectionRange(0, 5);
    btnH1.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "# Title");

    ta.value = "Sub"; ta.setSelectionRange(0, 3);
    btnH2.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "## Sub");

    ta.value = "one\ntwo"; ta.setSelectionRange(0, 7);
    btnList.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "- one\n- two");

    ta.value = "q1\nq2"; ta.setSelectionRange(0, 5);
    btnQuote.dispatchEvent({ type: "click" });
    assert.equal(ta.value, "> q1\n> q2");

    // Keyboard shortcuts Ctrl+B, Ctrl+I, Ctrl+K (and ignore Ctrl+Alt+B)
    ta.value = "x"; ta.setSelectionRange(0, 1);
    const evB = { type: "keydown", ctrlKey: true, key: "b" };
    ta.dispatchEvent(evB);
    assert.equal(ta.value, "**x**");
    assert.equal(evB.defaultPrevented, true);

    ta.value = "y"; ta.setSelectionRange(0, 1);
    ta.dispatchEvent({ type: "keydown", metaKey: true, key: "I" });
    assert.equal(ta.value, "*y*");

    ta.value = "z"; ta.setSelectionRange(0, 1);
    ta.dispatchEvent({ type: "keydown", ctrlKey: true, key: "k" });
    assert.equal(ta.value, "[z](https://)");

    ta.value = "keep"; ta.setSelectionRange(0, 4);
    ta.dispatchEvent({ type: "keydown", ctrlKey: true, altKey: true, key: "b" });
    assert.equal(ta.value, "keep");

    // Mode switch to split + rAF preview + scroll sync
    let rafQueue = [];
    env.requestAnimationFrame = (cb) => { rafQueue.push(cb); };
    tabS.dispatchEvent({ type: "click" });
    assert.equal(ed.getMode(), "split");
    assert.equal(stage.getAttribute("data-md-mode"), "split");
    assert.equal(tabS.getAttribute("aria-selected"), "true");
    assert.equal(tabW.classList.contains("active"), false);

    ta.value = "# Live **Preview**";
    ta.dispatchEvent({ type: "input" });
    ta.dispatchEvent({ type: "input" }); // debounced into single rAF
    assert.equal(rafQueue.length, 1);
    rafQueue.shift()();
    assert.equal(pv.childNodes[0].tagName, "h1");
    assert.equal(pv.textContent, "Live Preview");

    ta.scrollHeight = 1000; ta.clientHeight = 200; ta.scrollTop = 400;
    pv.scrollHeight = 600; pv.clientHeight = 200; pv.scrollTop = 0;
    ta.dispatchEvent({ type: "scroll" });
    assert.equal(pv.scrollTop, 200);

    tabP.dispatchEvent({ type: "click" });
    assert.equal(ed.getMode(), "preview");
    assert.ok(dirty > 10);
    assert.deepEqual(modesSeen, ["write", "split", "preview"]);
  });

  await test(`${label}: modal (states, Escape stack, focus restore, onBeforeClose, backdrop, mobile resize/visualViewport)`, () => {
    assert.throws(() => BlindUI.modal("no-such-modal"), /blindui_missing_id:no-such-modal/);

    const trigger = doc.register(BlindUI.h("button", { id: "open-btn" }));
    const mEl = doc.register(BlindUI.h("div", { id: "cmp-modal" }));
    const bdEl = doc.register(BlindUI.h("div", { id: "cmp-bd" }));
    const dlgEl = doc.register(BlindUI.h("div", { id: "dlg-modal" }));
    const dlgBd = doc.register(BlindUI.h("div", { id: "dlg-bd" }));

    const transitions = [];
    let allowClose = true;
    const dock = BlindUI.modal("cmp-modal", {
      mode: "dock",
      backdropId: "cmp-bd",
      closeOnBackdrop: "shrink",
      onBeforeClose: () => allowClose,
      onStateChange: (next, prev) => transitions.push(`${prev}->${next}`),
    });

    assert.equal(dock.getState(), "CLOSED");
    assert.equal(mEl.getAttribute("data-modal-state"), "CLOSED");
    assert.equal(mEl.style.display, "none");

    trigger.focus();
    dock.open();
    assert.equal(dock.getState(), "DOCKED");
    assert.equal(mEl.style.display, "");
    assert.equal(bdEl.style.display, "none");

    dock.expand();
    assert.equal(dock.getState(), "EXPANDED");
    assert.equal(bdEl.style.display, "");
    assert.equal(mEl.getAttribute("aria-modal"), "true");

    // Backdrop click with closeOnBackdrop="shrink" shrinks EXPANDED -> DOCKED
    bdEl.dispatchEvent({ type: "click" });
    assert.equal(dock.getState(), "DOCKED");

    // Escape on EXPANDED shrinks to DOCKED; Escape on DOCKED calls close(false)
    dock.expand();
    doc.dispatchEvent({ type: "keydown", key: "Escape" });
    assert.equal(dock.getState(), "DOCKED");

    // Cancel close via onBeforeClose
    allowClose = false;
    assert.equal(dock.close(false), false);
    assert.equal(dock.getState(), "DOCKED");
    // Forced close bypasses onBeforeClose and restores focus
    trigger.focused = false;
    assert.equal(dock.close(true), true);
    assert.equal(dock.getState(), "CLOSED");
    assert.equal(trigger.focused, true);

    // MINIMIZED ignores Escape
    allowClose = true;
    dock.open();
    dock.minimize();
    assert.equal(dock.getState(), "MINIMIZED");
    doc.dispatchEvent({ type: "keydown", key: "Escape" });
    assert.equal(dock.getState(), "MINIMIZED");

    // Stack order: open dialog on top of dock
    const dlg = BlindUI.modal("dlg-modal", { backdropId: "dlg-bd" });
    dlg.open();
    assert.equal(dlg.getState(), "OPEN");
    assert.equal(dlgBd.style.display, "");
    doc.dispatchEvent({ type: "keydown", key: "Escape" });
    assert.equal(dlg.getState(), "CLOSED");
    assert.equal(dock.getState(), "MINIMIZED");

    // Mobile breakpoint + visualViewport --cmp-vvh
    dock.dock();
    assert.equal(dock.getState(), "DOCKED");
    env.innerWidth = 390;
    env.visualViewport.height = 612.4;
    env.dispatchEvent({ type: "resize" });
    assert.equal(dock.getState(), "MOBILE_SHEET");
    assert.equal(mEl.style.getPropertyValue("--cmp-vvh"), "612px");

    env.visualViewport.height = 480.7;
    env.visualViewport.dispatchEvent({ type: "resize" });
    assert.equal(mEl.style.getPropertyValue("--cmp-vvh"), "481px");

    // Resize back to desktop -> DOCKED
    env.innerWidth = 1280;
    env.dispatchEvent({ type: "resize" });
    assert.equal(dock.getState(), "DOCKED");
    assert.ok(transitions.includes("CLOSED->DOCKED"));
    assert.ok(transitions.includes("DOCKED->MOBILE_SHEET"));
  });

  await test(`${label}: bindAction (missing ID, async lock, aria-busy) and bindGroup`, async () => {
    const beforeLen = BlindUI._missingBindings.length;
    assert.throws(() => BlindUI.bindAction("missing-strict", () => {}), /blindui_missing_id:missing-strict/);
    assert.equal(BlindUI._missingBindings[beforeLen], "missing-strict");

    const noop = BlindUI.bindAction("missing-lax", () => {}, "click", { strict: false });
    assert.equal(typeof noop, "function");
    assert.equal(BlindUI._missingBindings[beforeLen + 1], "missing-lax");

    const btn = doc.register(BlindUI.h("button", { id: "act-btn" }));
    let calls = 0;
    let resolvePending;
    const unbind = BlindUI.bindAction("act-btn", () => {
      calls += 1;
      return new Promise((res) => { resolvePending = res; });
    });
    assert.equal(env.__blindui_bound_ids["act-btn"], true);

    const p1 = btn.dispatchEvent({ type: "click" });
    assert.equal(btn.getAttribute("aria-busy"), "true");
    assert.equal(calls, 1);
    // Re-entrant click ignored while locked
    btn.dispatchEvent({ type: "click" });
    assert.equal(calls, 1);
    resolvePending("done");
    assert.equal(await p1, "done");
    assert.equal(btn.getAttribute("aria-busy"), null);

    unbind();
    btn.dispatchEvent({ type: "click" });
    assert.equal(calls, 1);

    // Sync throw still clears aria-busy
    const errBtn = doc.register(BlindUI.h("button", { id: "err-btn" }));
    BlindUI.bindAction("err-btn", () => { throw new Error("boom"); });
    assert.throws(() => errBtn.dispatchEvent({ type: "click" }), /boom/);
    assert.equal(errBtn.getAttribute("aria-busy"), null);

    // bindGroup delegation
    const parent = BlindUI.h("div", { className: "row" });
    const child = BlindUI.h("span", null, "inner");
    parent.appendChild(child);
    let delegated = null;
    const unbindGrp = BlindUI.bindGroup(".row", (ev, matched) => { delegated = matched; });
    assert.equal(env.__blindui_bound_selectors[".row"], true);
    doc.dispatchEvent({ type: "click", target: child });
    assert.equal(delegated, parent);
    delegated = null;
    unbindGrp();
    doc.dispatchEvent({ type: "click", target: child });
    assert.equal(delegated, null);
  });

  await test(`${label}: api, defineRoutes, setSigner, client/response schemas, query & errors`, async () => {
    const fetchCalls = [];
    let nextResp = { ok: true, status: 200, text: async () => JSON.stringify({ id: "m1", count: 2 }) };
    env.fetch = async (url, init) => {
      fetchCalls.push({ url, init });
      return nextResp;
    };

    BlindUI.defineRoutes({
      "POST ./api/v1/messages": {
        auth: "mailbox_sig",
        req: {
          t: "obj",
          req: true,
          fields: {
            to: { t: "email", req: true },
            subject: { t: "str", req: true, min: 1, max: 100 },
            priority: { t: "int", min: 1, max: 5 },
            flag: { t: "bool" },
            tags: { t: "arr", max: 3, of: { t: "str", vals: ["a", "b"] } },
          },
        },
        res: {
          t: "obj",
          fields: {
            id: { t: "str", req: true },
            count: { t: "int", req: true },
          },
        },
      },
    });

    // Fail-fast client_schema_error before fetch
    const badEmail = await BlindUI.api("POST /api/v1/messages", {
      body: { to: "not-email", subject: "hi" },
    });
    assert.equal(badEmail.ok, false);
    assert.equal(badEmail.status, 0);
    assert.equal(badEmail.error, "client_schema_error");
    assert.equal(badEmail.detail, "body.to:email");
    assert.equal(fetchCalls.length, 0);

    const badInt = await BlindUI.api("POST /api/v1/messages", {
      body: { to: "a@b.com", subject: "hi", priority: 2.5 },
    });
    assert.equal(badInt.error, "client_schema_error");
    assert.equal(badInt.detail, "body.priority:int");

    const badEnum = await BlindUI.api("POST /api/v1/messages", {
      body: { to: "a@b.com", subject: "hi", tags: ["a", "z"] },
    });
    assert.equal(badEnum.error, "client_schema_error");
    assert.equal(badEnum.detail, "body.tags[1]:enum");

    // missing_signer when auth=mailbox_sig and signer unset
    const noSign = await BlindUI.api("POST /api/v1/messages", {
      body: { to: "a@b.com", subject: "hi" },
    });
    assert.equal(noSign.ok, false);
    assert.equal(noSign.error, "missing_signer");
    assert.equal(fetchCalls.length, 0);

    // Valid signed call with query params
    let signerArgs = null;
    BlindUI.setSigner(async (method, canon, bodyText, authKind) => {
      signerArgs = { method, canon, bodyText, authKind };
      return { "X-Mailbox-Sig": "sig123" };
    });

    const okRes = await BlindUI.api("POST ./api/v1/messages", {
      query: { limit: 10, skip: null, tag: "a b" },
      body: { to: "a@b.com", subject: "Hello", priority: 2, flag: true, tags: ["a"] },
    });
    assert.equal(okRes.ok, true);
    assert.equal(okRes.status, 200);
    assert.deepEqual(JSON.parse(JSON.stringify(okRes.data)), { id: "m1", count: 2 });
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0].url, "./api/v1/messages?limit=10&tag=a%20b");
    assert.equal(fetchCalls[0].init.headers["X-Mailbox-Sig"], "sig123");
    assert.equal(fetchCalls[0].init.headers["Content-Type"], "application/json");
    assert.equal(signerArgs.canon, "/api/v1/messages");
    assert.equal(signerArgs.authKind, "mailbox_sig");

    // response_schema_error
    nextResp = { ok: true, status: 200, text: async () => JSON.stringify({ id: "m1", count: "wrong" }) };
    const badRes = await BlindUI.api("POST /api/v1/messages", {
      body: { to: "a@b.com", subject: "Hello" },
    });
    assert.equal(badRes.ok, false);
    assert.equal(badRes.error, "response_schema_error");
    assert.equal(badRes.detail, "res.count:int");

    // HTTP error with JSON error field vs plain text
    nextResp = { ok: false, status: 403, text: async () => JSON.stringify({ error: "forbidden_box" }) };
    const err1 = await BlindUI.api("GET /api/v1/inbox");
    assert.equal(err1.ok, false);
    assert.equal(err1.status, 403);
    assert.equal(err1.error, "forbidden_box");

    nextResp = { ok: false, status: 502, text: async () => "bad gateway" };
    const err2 = await BlindUI.api("GET /api/v1/inbox");
    assert.equal(err2.ok, false);
    assert.equal(err2.status, 502);
    assert.equal(err2.error, "http_502");
    assert.equal(err2.data, "bad gateway");

    // fetch_unavailable
    env.fetch = null;
    const noFetch = await BlindUI.api("GET /api/v1/inbox");
    assert.equal(noFetch.ok, false);
    assert.equal(noFetch.error, "fetch_unavailable");
  });

  const findBlockEd = (host, idx = 0) => {
    const blk = host.childNodes[idx];
    if (!blk) return null;
    let found = null;
    walkNodes(blk, (n) => {
      if (!found && n.nodeType === 1 && (n.classList.contains("bui-nb-ed") || n.tagName === "textarea" || n.tagName === "hr")) {
        found = n;
      }
    });
    return found;
  };
  const setSel = (startNode, startOff, endNode = startNode, endOff = startOff) => {
    const sel = env.getSelection();
    const r = doc.createRange();
    r.setStart(startNode, startOff);
    r.setEnd(endNode, endOff);
    sel.removeAllRanges();
    sel.addRange(r);
  };
  const setEdText = (el, text, caret = text.length) => {
    if (el.tagName === "textarea") {
      el.value = text;
      el.setSelectionRange(caret, caret);
    } else {
      el.textContent = text;
      if (el.firstChild) setSel(el.firstChild, caret);
      else setSel(el, 0);
    }
    el.dispatchEvent({ type: "input" });
  };
  const typeChars = (el, chars) => {
    const sel = env.getSelection();
    for (const ch of chars) {
      let r = sel.rangeCount > 0 ? sel.getRangeAt(0) : null;
      if (!r) {
        r = doc.createRange();
        r.setStart(el, el.childNodes.length);
        r.setEnd(el, el.childNodes.length);
        sel.addRange(r);
      }
      if (r.startContainer.nodeType === 3) {
        const tn = r.startContainer;
        const off = r.startOffset;
        tn.nodeValue = tn.nodeValue.slice(0, off) + ch + tn.nodeValue.slice(off);
        setSel(tn, off + ch.length);
      } else {
        const parent = r.startContainer;
        const off = r.startOffset;
        const tn = doc.createTextNode(ch);
        parent.insertBefore(tn, parent.childNodes[off] || null);
        setSel(tn, ch.length);
      }
      el.dispatchEvent({ type: "input" });
    }
  };

  await test(`${label}: notionEditor missing container & live block transforms (#, ##, ###, -, *, 1., >, fence, ---)`, () => {
    assert.throws(() => BlindUI.notionEditor("no-such-container"), /blindui_missing_container/);
    assert.throws(() => BlindUI.notionEditor(null), /blindui_missing_container/);

    const host = doc.register(BlindUI.h("div", { id: "ne-host-1" }));
    const ed = BlindUI.notionEditor("ne-host-1", { placeholder: "Write here..." });
    assert.equal(host.classList.contains("bui-notion"), true);
    assert.equal(host.getAttribute("data-bui-mode"), "notion");
    const initEd = findBlockEd(host, 0);
    assert.equal(initEd.getAttribute("contenteditable"), "true");
    assert.equal(initEd.getAttribute("data-placeholder"), "Write here...");
    assert.equal(initEd.classList.contains("bui-nb-empty"), true);

    const typeInto = (idx, text, caret = text.length) => {
      const el = findBlockEd(host, idx);
      el.focus();
      setEdText(el, text, caret);
      return findBlockEd(host, idx);
    };

    // Live # / ## / ### / - / * / 1. / > / ```lang / ``` transforms
    const transforms = [
      ["# Heading One", "h1", "Heading One", "# Heading One"],
      ["## Heading Two", "h2", "Heading Two", "## Heading Two"],
      ["### Heading Three", "h3", "Heading Three", "### Heading Three"],
      ["- Bullet item", "ul", "Bullet item", "- Bullet item"],
      ["* Star item", "ul", "Star item", "* Star item"],
      ["1. First item", "ol", "First item", "1. First item"],
      ["> Quoted text", "bq", "Quoted text", "> Quoted text"],
      ["```js ", "code", "", "```js\n\n```"],
      ["```", "code", "", "```\n\n```"],
    ];
    for (const [typed, expType, expVal, expMd] of transforms) {
      ed.clear();
      const active = typeInto(0, typed);
      assert.equal(host.childNodes[0].getAttribute("data-block-type"), expType, `Failed transform for ${JSON.stringify(typed)}`);
      const actualVal = active.tagName === "textarea" ? active.value : active.textContent;
      assert.equal(actualVal, expVal, `Unexpected value after transform for ${JSON.stringify(typed)}`);
      assert.equal(ed.getMarkdown(), expMd, `Unexpected markdown after transform for ${JSON.stringify(typed)}`);
    }

    // No premature fence trigger on ```j (stays paragraph until space/newline)
    ed.clear();
    typeInto(0, "```j");
    assert.equal(host.childNodes[0].getAttribute("data-block-type"), "p");
    assert.equal(ed.getMarkdown(), "```j");

    // Live --- transform creates hr + focuses trailing phantom paragraph; hr Enter/Backspace/Delete work
    ed.clear();
    typeInto(0, "---");
    assert.equal(host.childNodes[0].getAttribute("data-block-type"), "hr");
    assert.equal(host.childNodes.length, 2);
    assert.equal(host.childNodes[1].getAttribute("data-block-type"), "p");
    assert.equal(ed.getMarkdown(), "---");

    const hrEl = findBlockEd(host, 0);
    assert.equal(hrEl.tagName, "hr");
    hrEl.focus();
    const evHrEnter = { type: "keydown", key: "Enter" };
    hrEl.dispatchEvent(evHrEnter);
    assert.equal(evHrEnter.defaultPrevented, true);
    assert.equal(doc.activeElement, findBlockEd(host, 1));

    hrEl.focus();
    const evHrDel = { type: "keydown", key: "Delete" };
    hrEl.dispatchEvent(evHrDel);
    assert.equal(evHrDel.defaultPrevented, true);
    assert.equal(host.childNodes.length, 1);
    assert.equal(host.childNodes[0].getAttribute("data-block-type"), "p");

    // Also test Backspace directly on focused hr block
    ed.clear();
    typeInto(0, "---");
    const hrEl2 = findBlockEd(host, 0);
    hrEl2.focus();
    hrEl2.dispatchEvent({ type: "keydown", key: "Backspace" });
    assert.equal(host.childNodes.length, 1);
    assert.equal(host.childNodes[0].getAttribute("data-block-type"), "p");
    assert.equal(ed.getMarkdown(), "");
  });

  await test(`${label}: notionEditor TRUE as-you-type inline compile, ZWS Backspace, click-empty-space & paste XSS`, () => {
    const host = doc.register(BlindUI.h("div", { id: "ne-host-2" }));
    const ed = BlindUI.notionEditor(host, {
      value: "First **bold** *italic* `code` [docs](https://example.com/a)\n\nSecond paragraph",
    });

    assert.equal(host.childNodes.length, 2);
    const wrap0 = host.childNodes[0];
    const wrap1 = host.childNodes[1];
    const ed0 = findBlockEd(host, 0);
    const ed1 = findBlockEd(host, 1);

    // Always-live DOM compiles bold, italic, code, and safe https link directly inside contenteditable
    const tags0 = [];
    let linkEl = null;
    walkNodes(ed0, (n) => {
      if (n.nodeType === 1) {
        tags0.push(n.tagName);
        if (n.tagName === "a") linkEl = n;
      }
    });
    assert.ok(tags0.includes("strong"));
    assert.ok(tags0.includes("em"));
    assert.ok(tags0.includes("code"));
    assert.ok(linkEl, "Expected rendered <a> element");
    assert.equal(linkEl.getAttribute("href"), "https://example.com/a");
    assert.equal(linkEl.getAttribute("rel"), "noopener noreferrer nofollow");

    // Focus-to-edit sets bui-nb-focus and preserves sibling wrap1 DOM identity
    ed0.focus();
    assert.equal(wrap0.classList.contains("bui-nb-focus"), true);
    assert.equal(host.childNodes[0], wrap0);
    assert.equal(host.childNodes[1], wrap1);

    // Focusing block 1 blurs block 0 and focuses block 1
    ed1.focus();
    assert.equal(wrap0.classList.contains("bui-nb-focus"), false);
    assert.equal(wrap1.classList.contains("bui-nb-focus"), true);

    // Real-time char-by-char as-you-type falsifier (ZERO blur!)
    const liveHost = doc.register(BlindUI.h("div", { id: "ne-host-live" }));
    const liveEd = BlindUI.notionEditor(liveHost, { placeholder: "Write here..." });
    liveEd.focus();
    const pEd = findBlockEd(liveHost, 0);
    assert.equal(doc.activeElement, pEd);

    // Typing "Hello **bold*" must NOT misfire <em> or <strong> prematurely
    typeChars(pEd, "Hello **bold*");
    const preTags = [];
    walkNodes(pEd, (n) => { if (n.nodeType === 1) preTags.push(n.tagName); });
    assert.deepEqual(preTags, [], "Partial **bold* must not misfire <em> or <strong>");
    assert.equal(doc.activeElement, pEd);

    // Final "*" compiles <strong>bold</strong> IMMEDIATELY while still focused, caret on ZWS outside <strong>
    typeChars(pEd, "*");
    assert.equal(doc.activeElement, pEd);
    const strongEl = pEd.childNodes.find((n) => n.nodeType === 1 && n.tagName === "strong");
    assert.ok(strongEl, "Expected immediate <strong> without blur");
    assert.equal(strongEl.textContent, "bold");
    const rAfterBold = env.getSelection().getRangeAt(0);
    assert.equal(rAfterBold.startContainer.nodeType, 3);
    assert.equal(rAfterBold.startContainer.nodeValue, "\u200b");
    assert.equal(rAfterBold.startOffset, 1);
    assert.equal(rAfterBold.startContainer.parentNode, pEd, "Caret ZWS must sit outside <strong>");

    // Next space strips ZWS and stays outside <strong>
    typeChars(pEd, " ");
    const rAfterSpace = env.getSelection().getRangeAt(0);
    assert.equal(rAfterSpace.startContainer.nodeValue, " ");
    assert.equal(rAfterSpace.startContainer.parentNode, pEd);

    // Continue typing *italic* `code` [ok](https://blindlabs.ai) after WITHOUT blur
    typeChars(pEd, "*italic* `code` [ok](https://blindlabs.ai) after");
    assert.equal(doc.activeElement, pEd, "Editor must remain focused throughout live typing");
    const liveStrong = pEd.childNodes.find((n) => n.nodeType === 1 && n.tagName === "strong");
    const liveEm = pEd.childNodes.find((n) => n.nodeType === 1 && n.tagName === "em");
    const liveCode = pEd.childNodes.find((n) => n.nodeType === 1 && n.tagName === "code");
    const liveA = pEd.childNodes.find((n) => n.nodeType === 1 && n.tagName === "a");
    assert.equal(liveStrong?.textContent, "bold");
    assert.equal(liveEm?.textContent, "italic");
    assert.equal(liveCode?.textContent, "code");
    assert.equal(liveA?.textContent, "ok");
    assert.equal(liveA?.getAttribute("href"), "https://blindlabs.ai");
    assert.equal(liveA?.getAttribute("rel"), "noopener noreferrer nofollow");
    const lastNode = pEd.childNodes[pEd.childNodes.length - 1];
    assert.equal(lastNode.nodeType, 3);
    assert.equal(lastNode.nodeValue, " after");
    assert.equal(lastNode.parentNode, pEd, "Text typed after link must sit outside <a>");
    assert.equal(liveEd.getMarkdown(), "Hello **bold** *italic* `code` [ok](https://blindlabs.ai) after");

    // Chrome contenteditable inserts NBSP (\u00a0) after ZWS/inline tags; serialization, DOM non-trailing NBSP, & shortcuts must normalize to ASCII space
    liveEd.clear();
    liveEd.focus();
    const pNbsp = findBlockEd(liveHost, 0);
    typeChars(pNbsp, "Hello **bold**\u00a0*italic*\u00a0`a\u00a0b`\u00a0[ok](https://blindlabs.ai)\u00a0after");
    assert.equal(liveEd.getMarkdown(), "Hello **bold** *italic* `a b` [ok](https://blindlabs.ai) after");
    assert.equal(pNbsp.textContent.includes("\u00a0"), false, "Non-trailing NBSP must normalize in live DOM too");
    liveEd.clear();
    liveEd.focus();
    const pNbspH = findBlockEd(liveHost, 0);
    typeChars(pNbspH, "#\u00a0");
    assert.equal(liveHost.childNodes[0].getAttribute("data-block-type"), "h1");
    typeChars(findBlockEd(liveHost, 0), "Title");
    assert.equal(liveEd.getMarkdown(), "# Title");

    // 1-press Backspace right after <strong>bold</strong> (on ZWS) moves caret cleanly into "bold" text node
    liveEd.clear();
    liveEd.focus();
    const pBs = findBlockEd(liveHost, 0);
    typeChars(pBs, "**bold**");
    const strongBs = pBs.childNodes.find((n) => n.nodeType === 1 && n.tagName === "strong");
    assert.ok(strongBs);
    const zwsBefore = env.getSelection().getRangeAt(0).startContainer;
    assert.equal(zwsBefore.nodeValue, "\u200b");
    const evBsZws = { type: "keydown", key: "Backspace" };
    pBs.dispatchEvent(evBsZws);
    assert.equal(evBsZws.defaultPrevented, undefined, "Native Backspace should delete last char in 1 press");
    assert.equal(zwsBefore.parentNode, null, "ZWS node must be removed on Backspace");
    const rAfterBs = env.getSelection().getRangeAt(0);
    assert.equal(rAfterBs.startContainer, strongBs.firstChild);
    assert.equal(rAfterBs.startOffset, 4);

    // Click empty space on non-empty doc appends & focuses one idempotent phantom paragraph
    const clickHost = doc.register(BlindUI.h("div", { id: "ne-host-click" }));
    const clickEd = BlindUI.notionEditor(clickHost, { value: "Top block" });
    assert.equal(clickHost.childNodes.length, 1);
    clickHost.dispatchEvent({ type: "click", target: clickHost });
    assert.equal(clickHost.childNodes.length, 2);
    assert.equal(clickHost.childNodes[1].getAttribute("data-block-type"), "p");
    const newEd = findBlockEd(clickHost, 1);
    assert.equal(doc.activeElement, newEd);
    assert.equal(clickEd.getMarkdown(), "Top block");
    // Second empty-space click must NOT duplicate
    clickHost.dispatchEvent({ type: "click", target: clickHost });
    assert.equal(clickHost.childNodes.length, 2);
    assert.equal(doc.activeElement, newEd);
    // Typing into the newly appended block updates markdown cleanly
    typeChars(newEd, "Second block");
    assert.equal(clickEd.getMarkdown(), "Top block\n\nSecond block");

    // Click further down with real clientY + getBoundingClientRect places caret vertically where clicked
    const yHost = doc.register(BlindUI.h("div", { id: "ne-host-click-y" }));
    const yEd = BlindUI.notionEditor(yHost, { value: "Top block" });
    yHost.childNodes[0].getBoundingClientRect = () => ({ top: 100, bottom: 128, height: 28 });
    // dy = 283 - 128 = 155, lineH = 28, Math.round(155 / 31) = 5 new blocks -> 6 total
    yHost.dispatchEvent({ type: "click", target: yHost, clientY: 283 });
    assert.equal(yHost.childNodes.length, 6);
    const botEd = findBlockEd(yHost, 5);
    assert.equal(doc.activeElement, botEd);
    assert.equal(yEd.getMarkdown(), "Top block");
    // Clicking even further down from a focused phantom block preserves prior spacers and appends more
    yHost.childNodes[5].getBoundingClientRect = () => ({ top: 255, bottom: 283, height: 28 });
    yHost.dispatchEvent({ type: "click", target: yHost, clientY: 345 });
    assert.equal(yHost.childNodes.length, 8);
    const botEd2 = findBlockEd(yHost, 7);
    assert.equal(doc.activeElement, botEd2);
    typeChars(botEd2, "Bottom line");
    assert.equal(yEd.getMarkdown(), "Top block\n\nBottom line");
    // Extreme clientY caps appended blocks at 18
    const capHost = doc.register(BlindUI.h("div", { id: "ne-host-click-cap" }));
    BlindUI.notionEditor(capHost, { value: "" });
    capHost.childNodes[0].getBoundingClientRect = () => ({ top: 50, bottom: 78, height: 28 });
    capHost.dispatchEvent({ type: "click", target: capHost, clientY: 1500 });
    assert.equal(capHost.childNodes.length, 19);
    assert.equal(doc.activeElement, findBlockEd(capHost, 18));

    // Single-line paste XSS falsifier: <img onerror> and [bad](javascript:alert(1))
    const pasteHost = doc.register(BlindUI.h("div", { id: "ne-host-paste" }));
    const pasteEd = BlindUI.notionEditor(pasteHost);
    pasteEd.focus();
    const pPaste = findBlockEd(pasteHost, 0);
    const evImgPaste = {
      type: "paste",
      clipboardData: { getData: (t) => (t === "text/plain" ? "<img src=x on" + "error=alert(1)>" : "") },
    };
    pPaste.dispatchEvent(evImgPaste);
    assert.equal(evImgPaste.defaultPrevented, true);
    walkNodes(pasteHost, (n) => {
      if (n.nodeType === 1) {
        assert.notEqual(n.tagName, "img", "Zero <img> allowed from paste");
        for (const [k] of n._attrs.entries()) assert.ok(!/^on/i.test(k), `Zero on* attr allowed from paste: ${k}`);
      }
    });

    pasteEd.clear();
    pasteEd.focus();
    const pPaste2 = findBlockEd(pasteHost, 0);
    const evJsLinkPaste = {
      type: "paste",
      clipboardData: { getData: (t) => (t === "text/plain" ? "[bad](javascript:alert(1))" : "") },
    };
    pPaste2.dispatchEvent(evJsLinkPaste);
    assert.equal(evJsLinkPaste.defaultPrevented, true);
    walkNodes(pasteHost, (n) => {
      if (n.nodeType === 1) {
        assert.notEqual(n.tagName, "a", "Zero <a> allowed for javascript: link paste");
        for (const [k] of n._attrs.entries()) assert.ok(!/^on/i.test(k), `Zero on* attr allowed: ${k}`);
      }
    });
  });

  await test(`${label}: notionEditor keyboard ergonomics (Enter, lists, code, Backspace, Arrows, Escape, shortcuts, paste)`, () => {
    const host = doc.register(BlindUI.h("div", { id: "ne-host-3" }));
    const ed = BlindUI.notionEditor(host, { value: "HelloWorld" });

    // Enter splits paragraph at caret
    ed.focus();
    let el = findBlockEd(host, 0);
    setSel(el.firstChild, 5);
    const evSplit = { type: "keydown", key: "Enter" };
    el.dispatchEvent(evSplit);
    assert.equal(evSplit.defaultPrevented, true);
    assert.equal(ed.getMarkdown(), "Hello\n\nWorld");
    assert.equal(host.childNodes.length, 2);

    // Backspace at start of second paragraph merges back into first
    el = findBlockEd(host, 1);
    setSel(el.firstChild, 0);
    el.dispatchEvent({ type: "keydown", key: "Backspace" });
    assert.equal(ed.getMarkdown(), "HelloWorld");
    assert.equal(host.childNodes.length, 1);

    // Shift+Enter inside paragraph is NOT prevented (allows soft newline)
    el = findBlockEd(host, 0);
    const evShift = { type: "keydown", key: "Enter", shiftKey: true };
    el.dispatchEvent(evShift);
    assert.equal(evShift.defaultPrevented, undefined);

    // Ordered list: Enter increments 1. -> 2., empty Enter exits list to paragraph
    ed.setMarkdown("1. First");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 5);
    el.dispatchEvent({ type: "keydown", key: "Enter" });
    assert.equal(ed.getMarkdown(), "1. First\n2. ");
    el = findBlockEd(host, 1);
    setEdText(el, "Second", 6);
    el.dispatchEvent({ type: "keydown", key: "Enter" });
    assert.equal(ed.getMarkdown(), "1. First\n2. Second\n3. ");
    // Empty 3. + Enter exits list to paragraph (phantom trailing p)
    el = findBlockEd(host, 2);
    setSel(el, 0);
    el.dispatchEvent({ type: "keydown", key: "Enter" });
    assert.equal(host.childNodes[2].getAttribute("data-block-type"), "p");
    assert.equal(ed.getMarkdown(), "1. First\n2. Second");

    // Unordered list continues on Enter, Backspace at offset 0 de-types to paragraph
    ed.setMarkdown("- Alpha");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 5);
    el.dispatchEvent({ type: "keydown", key: "Enter" });
    assert.equal(ed.getMarkdown(), "- Alpha\n- ");
    el = findBlockEd(host, 1);
    setSel(el, 0);
    el.dispatchEvent({ type: "keydown", key: "Backspace" });
    assert.equal(host.childNodes[1].getAttribute("data-block-type"), "p");

    // Code block: plain Enter not prevented; Ctrl+Enter exits to new paragraph
    ed.setMarkdown("```js\nlet a = 1;\n```");
    ed.focus();
    el = findBlockEd(host, 0);
    assert.equal(el.tagName, "textarea");
    const evCodePlain = { type: "keydown", key: "Enter" };
    el.dispatchEvent(evCodePlain);
    assert.equal(evCodePlain.defaultPrevented, undefined);
    const evCodeExit = { type: "keydown", key: "Enter", ctrlKey: true };
    el.dispatchEvent(evCodeExit);
    assert.equal(evCodeExit.defaultPrevented, true);
    assert.equal(host.childNodes.length, 2);
    assert.equal(host.childNodes[1].getAttribute("data-block-type"), "p");

    // Backspace after hr deletes hr block
    ed.setMarkdown("---");
    el = findBlockEd(host, 1);
    el.focus();
    setSel(el, 0);
    el.dispatchEvent({ type: "keydown", key: "Backspace" });
    assert.equal(host.childNodes.length, 1);
    assert.equal(host.childNodes[0].getAttribute("data-block-type"), "p");
    assert.equal(ed.getMarkdown(), "");

    // ArrowDown / ArrowUp navigation and Escape blurs active block
    ed.setMarkdown("Top\n\nBottom");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 3);
    el.dispatchEvent({ type: "keydown", key: "ArrowDown" });
    assert.equal(host.childNodes[1].classList.contains("bui-nb-focus"), true);
    el = findBlockEd(host, 1);
    setSel(el.firstChild, 0);
    el.dispatchEvent({ type: "keydown", key: "ArrowUp" });
    assert.equal(host.childNodes[0].classList.contains("bui-nb-focus"), true);
    el = findBlockEd(host, 0);
    el.dispatchEvent({ type: "keydown", key: "Escape" });
    assert.equal(host.childNodes[0].classList.contains("bui-nb-focus"), false);
    assert.equal(el.focused, false);

    // Inline keyboard shortcuts Ctrl+B / Cmd+I / Ctrl+K
    ed.setMarkdown("word");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 0, el.firstChild, 4);
    el.dispatchEvent({ type: "keydown", ctrlKey: true, key: "b" });
    assert.equal(ed.getMarkdown(), "**word**");

    ed.setMarkdown("word");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 0, el.firstChild, 4);
    el.dispatchEvent({ type: "keydown", metaKey: true, key: "i" });
    assert.equal(ed.getMarkdown(), "*word*");

    ed.setMarkdown("docs");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 0, el.firstChild, 4);
    el.dispatchEvent({ type: "keydown", ctrlKey: true, key: "k" });
    assert.equal(ed.getMarkdown(), "[docs](https://)");

    // Multi-line paste splits into proper structured blocks
    ed.setMarkdown("Start");
    ed.focus();
    el = findBlockEd(host, 0);
    setSel(el.firstChild, 5);
    const evPaste = {
      type: "paste",
      clipboardData: { getData: (t) => (t === "text/plain" ? "\n\n## Pasted\n\n- Item A" : "") },
    };
    el.dispatchEvent(evPaste);
    assert.equal(evPaste.defaultPrevented, true);
    assert.deepEqual(
      JSON.parse(JSON.stringify(ed.getBlocks())).map((b) => [b.type, b.text]),
      [["p", "Start"], ["h2", "Pasted"], ["ul", "Item A"]]
    );
  });

  await test(`${label}: notionEditor applyFormat across blur, textarea sync, setRawMode, onChange, getBlocks & readOnly`, () => {
    const host = doc.register(BlindUI.h("div", { id: "ne-host-4" }));
    const backingTa = doc.register(BlindUI.h("textarea", { id: "ne-ta-4", value: "alpha" }));
    const changes = [];
    const ed = BlindUI.notionEditor("ne-host-4", {
      textareaId: "ne-ta-4",
      onChange: (mdText) => changes.push(mdText),
    });

    // Backing textarea is hidden and kept synced
    assert.equal(backingTa.style.display, "none");
    assert.equal(ed.getMarkdown(), "alpha");
    assert.equal(ed.isRawMode(), false);

    // Subscribe & unsubscribe secondary onChange listener
    const extraChanges = [];
    const unsub = ed.onChange((s) => extraChanges.push(s));

    // Select "alpha", blur (simulating toolbar button click stealing focus), then applyFormat remembers lastIdx/lastSel
    ed.focus();
    const ed0 = findBlockEd(host, 0);
    setSel(ed0.firstChild, 0, ed0.firstChild, 5);
    ed0.blur();
    assert.equal(host.childNodes[0].classList.contains("bui-nb-focus"), false);

    ed.applyFormat("bold");
    assert.equal(ed.getMarkdown(), "**alpha**");
    assert.equal(backingTa.value, "**alpha**");
    assert.equal(extraChanges[extraChanges.length - 1], "**alpha**");

    unsub();
    const countBeforeUnsub = extraChanges.length;

    // Test all toolbar formats: italic, code, link, h1, h2, h3, list, ol, quote, codeblock, hr
    ed.setMarkdown("term");
    ed.focus();
    const edIt = findBlockEd(host, 0);
    setSel(edIt.firstChild, 0, edIt.firstChild, 4);
    ed.applyFormat("italic");
    assert.equal(ed.getMarkdown(), "*term*");
    assert.equal(extraChanges.length, countBeforeUnsub);

    ed.setMarkdown("fn()");
    ed.focus();
    const edCode = findBlockEd(host, 0);
    setSel(edCode.firstChild, 0, edCode.firstChild, 4);
    ed.applyFormat("code");
    assert.equal(ed.getMarkdown(), "`fn()`");

    ed.setMarkdown("site");
    ed.focus();
    const edLink = findBlockEd(host, 0);
    setSel(edLink.firstChild, 0, edLink.firstChild, 4);
    ed.applyFormat("link");
    assert.equal(ed.getMarkdown(), "[site](https://)");

    for (const [fmt, expPrefix] of [
      ["h1", "# "],
      ["h2", "## "],
      ["h3", "### "],
      ["list", "- "],
      ["ol", "1. "],
      ["quote", "> "],
    ]) {
      ed.setMarkdown("Body");
      ed.applyFormat(fmt);
      assert.equal(ed.getMarkdown(), expPrefix + "Body", `applyFormat(${fmt}) failed`);
      // Toggling same block format restores paragraph
      ed.applyFormat(fmt);
      assert.equal(ed.getMarkdown(), "Body", `applyFormat(${fmt}) toggle-off failed`);
    }

    ed.setMarkdown("x = 1");
    ed.applyFormat("codeblock");
    assert.equal(ed.getMarkdown(), "```\nx = 1\n```");

    ed.setMarkdown("Above");
    ed.applyFormat("hr");
    assert.equal(ed.getMarkdown(), "Above\n\n---");
    assert.deepEqual(
      JSON.parse(JSON.stringify(ed.getBlocks())).map((b) => b.type),
      ["p", "hr"]
    );

    // Toggle raw mode with backing textarea: shows backingTa, hides host, syncs edits back on exit
    assert.equal(ed.setRawMode(true), true);
    assert.equal(ed.isRawMode(), true);
    assert.equal(host.getAttribute("data-bui-mode"), "raw");
    assert.equal(host.style.display, "none");
    assert.equal(backingTa.style.display, "");
    backingTa.value = "## Raw Edit\n\n- From raw";
    backingTa.dispatchEvent({ type: "input" });
    assert.equal(ed.getMarkdown(), "## Raw Edit\n\n- From raw");

    assert.equal(ed.setRawMode(false), false);
    assert.equal(ed.isRawMode(), false);
    assert.equal(host.getAttribute("data-bui-mode"), "notion");
    assert.equal(host.style.display, "");
    assert.equal(backingTa.style.display, "none");
    assert.deepEqual(
      JSON.parse(JSON.stringify(ed.getBlocks())).map((b) => [b.type, b.text]),
      [["h2", "Raw Edit"], ["ul", "From raw"]]
    );

    // Standalone setRawMode(true) without backing textarea creates internal raw textarea inside container
    const soloHost = doc.register(BlindUI.h("div", { id: "ne-solo" }));
    const soloEd = BlindUI.notionEditor(soloHost, { value: "# Solo" });
    soloEd.setRawMode(true);
    const rawTa = soloHost.childNodes[0];
    assert.equal(rawTa.tagName, "textarea");
    assert.equal(rawTa.value, "# Solo");
    rawTa.value = "> Solo raw";
    rawTa.dispatchEvent({ type: "input" });
    soloEd.setRawMode(false);
    assert.equal(soloEd.getMarkdown(), "> Solo raw");
    assert.equal(soloEd.getBlocks()[0].type, "bq");

    // readOnly mode blocks click/focus/applyFormat mutations and renders <pre><code> without contenteditable
    const roHost = doc.register(BlindUI.h("div", { id: "ne-ro" }));
    const roEd = BlindUI.notionEditor(roHost, { value: "Locked\n\n```py\nprint(1)\n```", readOnly: true });
    assert.equal(findBlockEd(roHost, 0).getAttribute("contenteditable"), null);
    assert.equal(roHost.childNodes[1].childNodes[0].tagName, "pre");
    roHost.dispatchEvent({ type: "click", target: roHost });
    roEd.focus();
    roEd.applyFormat("bold");
    assert.equal(roHost.childNodes[0].classList.contains("bui-nb-focus"), false);
    assert.equal(roEd.getMarkdown(), "Locked\n\n```py\nprint(1)\n```");
    assert.ok(changes.length >= 3);
  });

  await test(`${label}: notionEditor lossless getMarkdown/setMarkdown roundtrip & XSS payload neutralization`, () => {
    const host = doc.register(BlindUI.h("div", { id: "ne-host-5" }));
    const ed = BlindUI.notionEditor(host);

    // Lossless bit-exact roundtrip across tricky whitespace, CRLF, fences, headings, and lists
    const roundtripCases = [
      "",
      "\n\n",
      "a\n",
      "a\r\nb\r\n",
      "#   Title",
      "```\na\n",
      "````\n```\n````",
      "---",
      "#### h4",
      "  - x",
      "# Title\n\nParagraph with **bold** and [ok](https://example.com/p)\n\n- a\n- b\n\n1. one\n2. two\n\n> quoted\n> line 2\n\n```py\nprint(1)\n```\n\n---\n",
    ];
    for (const sample of roundtripCases) {
      ed.setMarkdown(sample);
      assert.equal(ed.getMarkdown(), sample, `Lossless roundtrip mismatch for ${JSON.stringify(sample)}`);
    }

    // Adversarial XSS payloads rendered inside notionEditor produce zero unsafe DOM tags or event attrs
    const xssSamples = [
      TAG_SCRIPT_OPEN + "alert(1)" + TAG_SCRIPT_CLOSE,
      "<img src=x on" + "error=alert(1)>",
      "<svg on" + "load=alert(1)>",
      "<div " + SINK_ONCLICK_ATTR + "\"alert(1)\">click</div>",
      "# " + TAG_SCRIPT_OPEN + "h1" + TAG_SCRIPT_CLOSE,
      "> <iframe src=\"javascript:alert(1)\"></iframe>",
      "- [bad](javascript:alert(1))\n- ![tracker](https://evil.example.com/px.png)",
      "1. [bad](data:text/html," + TAG_SCRIPT_OPEN + "1" + TAG_SCRIPT_CLOSE + ")",
      "```html\n" + TAG_SCRIPT_OPEN + "alert(1)" + TAG_SCRIPT_CLOSE + "\n```",
      "[bad](vbscript:msgbox(1)) and [ok](https://example.com/safe)",
    ];
    const allowedWrapperTags = new Set([...ALLOWED_MD_TAGS, "div", "span", "textarea"]);
    for (const payload of xssSamples) {
      ed.setMarkdown(payload);
      assert.equal(ed.getMarkdown(), payload);
      walkNodes(host, (node) => {
        if (node.nodeType === 1) {
          assert.ok(allowedWrapperTags.has(node.tagName), `Disallowed tag <${node.tagName}> in notionEditor from ${payload}`);
          assert.notEqual(node.tagName, "img", `Zero <img> allowed in notionEditor from ${payload}`);
          for (const [k, v] of node._attrs.entries()) {
            assert.ok(!/^on/i.test(k), `Disallowed event attr ${k} in notionEditor`);
            if (k === "href") {
              assert.ok(v.startsWith("https://") || v.startsWith("mailto:"), `Disallowed href ${v}`);
            }
          }
        }
      });
    }
  });
}

await runSuiteForBuild("blindui.js", SRC_PATH);
await runSuiteForBuild("blindui.min.js", MIN_PATH);

// Cross-build parity: identical serialized Markdown & DOM trees on both builds.
await test("parity: blindui.js === blindui.min.js output on complex Markdown", () => {
  const srcB = loadBundle(SRC_PATH).BlindUI;
  const minB = loadBundle(MIN_PATH).BlindUI;
  const sample = "# Title\n\n**bold** *em* `code` [ok](https://example.com/a(b))\n\n- a\n  1. b\n> quote\n\n---\n![noimg](https://example.com/x.png)";
  assert.equal(serializeNode(srcB.md(sample)), serializeNode(minB.md(sample)));
});

await test("parity: blindui.js === blindui.min.js notionEditor DOM & Markdown output", () => {
  const srcL = loadBundle(SRC_PATH);
  const minL = loadBundle(MIN_PATH);
  const sHost = srcL.doc.register(srcL.BlindUI.h("div", { id: "p-host" }));
  const mHost = minL.doc.register(minL.BlindUI.h("div", { id: "p-host" }));
  const sample = "# Title\n\nBody **bold** [link](https://example.com/x)\n\n- one\n* two\n\n1. first\n\n> quote\n\n```js\nlet n = 1;\n```\n\n---";
  const sEd = srcL.BlindUI.notionEditor(sHost, { value: sample });
  const mEd = minL.BlindUI.notionEditor(mHost, { value: sample });
  assert.equal(sEd.getMarkdown(), sample);
  assert.equal(mEd.getMarkdown(), sample);
  assert.deepEqual(JSON.parse(JSON.stringify(sEd.getBlocks())), JSON.parse(JSON.stringify(mEd.getBlocks())));
  assert.equal(serializeNode(sHost), serializeNode(mHost));
});

console.log(`PASS: ${passed} BlindUI Node v22 test suites passed (blindui.js + blindui.min.js).`);
