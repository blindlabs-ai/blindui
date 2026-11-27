import { describe, test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");

function makeFakeDom() {
  class ClassList {
    constructor(el) { this._el = el; this._set = new Set(); }
    add(...xs) { for (const x of xs) if (x) this._set.add(x); this._sync(); }
    remove(...xs) { for (const x of xs) this._set.delete(x); this._sync(); }
    toggle(x, f) { const on = f === undefined ? !this._set.has(x) : !!f; on ? this._set.add(x) : this._set.delete(x); this._sync(); return on; }
    contains(x) { return this._set.has(x); }
    _sync() { this._el._attrs.class = [...this._set].join(" "); }
  }
  class Node {
    constructor(nodeType, tagName, ns) {
      this.nodeType = nodeType;
      this.tagName = tagName ? tagName.toUpperCase() : "";
      this.namespaceURI = ns || "http://www.w3.org/1999/xhtml";
      this.childNodes = [];
      this.parentNode = null;
      this._attrs = {};
      this.dataset = {};
      this.style = {};
      this._ev = {};
      this.classList = new ClassList(this);
      this.ownerDocument = null;
    }
    set className(v) {
      this.classList._set = new Set(String(v || "").split(/\s+/).filter(Boolean));
      this._attrs.class = String(v || "");
    }
    get className() { return this._attrs.class || ""; }
    set textContent(v) {
      this.childNodes = v ? [new Text(String(v))] : [];
    }
    get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
    appendChild(c) { c.parentNode = this; this.childNodes.push(c); return c; }
    replaceChildren(...ns) { this.childNodes = []; for (const n of ns) this.appendChild(n); }
    setAttribute(k, v) {
      this._attrs[k] = String(v);
      if (k === "class") this.className = v;
      if (k.startsWith("data-")) this.dataset[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = String(v);
    }
    getAttribute(k) { return k in this._attrs ? this._attrs[k] : null; }
    removeAttribute(k) { delete this._attrs[k]; }
    addEventListener(t, fn) { (this._ev[t] ||= []).push(fn); }
    removeEventListener(t, fn) { this._ev[t] = (this._ev[t] || []).filter((f) => f !== fn); }
    dispatch(t, ev = {}) { for (const fn of [...(this._ev[t] || [])]) fn(ev); }
    querySelector(sel) {
      const m = (n) => (sel.includes(".avatar") && n.classList.contains("avatar")) || (sel.includes("data-tactile-avatar") && n.getAttribute("data-tactile-avatar") !== null);
      for (const c of this.childNodes) {
        if (c.nodeType !== 1) continue;
        if (m(c)) return c;
        const r = c.querySelector(sel);
        if (r) return r;
      }
      return null;
    }
    querySelectorAll(sel) {
      const out = [];
      const walk = (n) => {
        for (const c of n.childNodes) {
          if (c.nodeType !== 1) continue;
          if (sel === ".row" && c.classList.contains("row")) out.push(c);
          walk(c);
        }
      };
      walk(this);
      return out;
    }
  }
  class Text {
    constructor(data) { this.nodeType = 3; this.nodeValue = data; this.data = data; }
    get textContent() { return this.data; }
  }
  const document = {
    createElement(t) { const n = new Node(1, t); n.ownerDocument = document; return n; },
    createElementNS(ns, t) { const n = new Node(1, t, ns); n.ownerDocument = document; return n; },
    createTextNode(s) { return new Text(String(s)); },
    getElementById() { return null; }
  };
  return { document, Node, Text };
}

function bootMaat() {
  const { document } = makeFakeDom();
  let now = 0;
  let tid = 1;
  const timers = new Map();
  const ctx = vm.createContext({
    document,
    console,
    setTimeout(fn, ms) { const id = tid++; timers.set(id, { fn, at: now + (ms || 0) }); return id; },
    clearTimeout(id) { timers.delete(id); },
    advance(ms) {
      now += ms;
      for (const [id, t] of [...timers.entries()]) {
        if (t.at <= now) { timers.delete(id); t.fn(); }
      }
    },
  });
  ctx.globalThis = ctx;
  ctx.window = ctx;
  vm.runInContext(fs.readFileSync(path.join(ROOT, "maat.min.js"), "utf8"), ctx);
  vm.runInContext(fs.readFileSync(path.join(ROOT, "maat-kit.min.js"), "utf8"), ctx);
  return { ctx, document, Maat: ctx.Maat };
}

describe("Maat Intrinsics (bindTactileList, pillSelect, paramField, railCard, stepTracker, mountSafe)", () => {
  test("all 6 intrinsics are exported directly on window.Maat and Maat.kit", () => {
    const { Maat } = bootMaat();
    for (const k of ["bindTactileList", "pillSelect", "paramField", "railCard", "stepTracker", "mountSafe"]) {
      assert.equal(typeof Maat[k], "function", `Maat.${k} missing`);
      assert.equal(Maat[k], Maat.kit[k], `Maat.${k} !== Maat.kit.${k}`);
    }
  });

  test("mountSafe normalizes HTML/SVG, preserves SVG <text>, and blocks XSS sinks/styles/URLs", () => {
    const { document, Maat } = bootMaat();
    const host = document.createElement("div");
    const badMarkup = [
      '<div class="box" style="color:red;background:url(javascript:alert(1));font-size:12px" onclick="alert(1)">',
      '<b>Bold</b><i>Ital</i><h5>H5</h5>',
      '<a href="javascript:alert(1)">bad</a>',
      '<a href="/api/v1/health">good</a>',
      '<input type="checkbox" checked readonly tabindex="2">',
      '<script>window.__pwn=1</script>',
      '<svg viewBox="0 0 100 40"><rect x="1" y="2" width="50" height="20" fill="#111"></rect><text x="10" y="20" font-size="11" text-anchor="middle">OK &amp; Safe</text></svg>',
      '</div>',
    ].join("");
    Maat.mountSafe(host, badMarkup);

    assert.equal(host.childNodes.length, 1);
    const box = host.childNodes[0];
    assert.equal(box.tagName, "DIV");
    assert.equal(box.className, "box");
    assert.equal(box.style.color, "red");
    assert.equal(box.style.fontSize, "12px");
    assert.equal(box.style.background, undefined);
    assert.equal(box._ev.click, undefined);
    assert.equal(host.textContent.includes("__pwn"), false);

    const tags = box.childNodes.map((n) => n.tagName);
    assert.deepEqual(tags, ["STRONG", "EM", "H4", "A", "A", "INPUT", "SVG"]);
    assert.equal(box.childNodes[3].getAttribute("href"), null);
    assert.equal(box.childNodes[4].getAttribute("href"), "/api/v1/health");
    assert.equal(box.childNodes[5].checked, true);
    assert.equal(box.childNodes[5].readOnly, true);
    assert.equal(box.childNodes[5].tabIndex, 2);

    const svg = box.childNodes[6];
    assert.equal(svg.namespaceURI, "http://www.w3.org/2000/svg");
    assert.equal(svg.getAttribute("viewBox"), "0 0 100 40");
    assert.equal(svg.childNodes[1].tagName, "TEXT");
    assert.equal(svg.childNodes[1].namespaceURI, "http://www.w3.org/2000/svg");
    assert.equal(svg.childNodes[1].getAttribute("text-anchor"), "middle");
    assert.equal(svg.childNodes[1].textContent, "OK & Safe");
  });

  test("bindTactileList handles 380ms hold, 10px drift cancel, avatar toggle, elastic swipe (88px at 110px) & undo", () => {
    const { ctx, document, Maat } = bootMaat();
    const wrap = document.createElement("div");
    const row = document.createElement("div");
    const av = document.createElement("div");
    av.className = "avatar";
    row.appendChild(av);
    wrap.appendChild(row);

    const events = [];
    let lastUndo = null;
    const ctl = Maat.bindTactileList(null, {
      onLongPress: (id) => { ctl.toggle(id); events.push(["lp", id]); },
      onSelectChange: (set, id) => events.push(["sel", id, set.size]),
      onHaptic: (k) => events.push(["hap", k]),
      onSwipeRight: (id, undo) => { lastUndo = undo; events.push(["sr", id]); },
      onSwipeLeft: (id, undo) => { lastUndo = undo; events.push(["sl", id]); },
      onUndo: (id, _it, dir) => events.push(["undo", id, dir]),
    });
    ctl.bindRow(wrap, row, { id: "m1" });

    // 1) Long-press >= 380ms selects item
    row.dispatch("touchstart", { touches: [{ clientX: 50, clientY: 50 }] });
    assert.equal(row.classList.contains("tactile-press"), true);
    ctx.advance(385);
    assert.equal(row.dataset.justLongPressed, "1");
    assert.equal(ctl.selected.has("m1"), true);
    row.dispatch("touchend", {});

    // 2) Drift > 10px cancels hold
    const beforeLp = events.filter((e) => e[0] === "lp").length;
    row.dispatch("touchstart", { touches: [{ clientX: 50, clientY: 50 }] });
    row.dispatch("touchmove", { touches: [{ clientX: 50, clientY: 75 }] });
    ctx.advance(450);
    assert.equal(events.filter((e) => e[0] === "lp").length, beforeLp);
    row.dispatch("touchend", {});

    // 3) Avatar click toggles selection off
    av.dispatch("click", { stopPropagation() {} });
    assert.equal(ctl.selected.has("m1"), false);

    // 4) Elastic swipe right: 110px raw -> 76 + (110 - 76) * 0.35 = 87.9 -> 88px
    row.dispatch("touchstart", { touches: [{ clientX: 20, clientY: 50 }] });
    row.dispatch("touchmove", { touches: [{ clientX: 130, clientY: 52 }], preventDefault() {} });
    assert.equal(row.style.transform, "translateX(88px)");
    assert.equal(wrap.classList.contains("swipe-armed"), true);
    assert.equal(wrap.classList.contains("swiping-right"), true);
    row.dispatch("touchend", {});
    assert.equal(row.dataset.justSwiped, "1");
    assert.ok(events.some((e) => e[0] === "sr" && e[1] === "m1"));
    lastUndo();
    assert.ok(events.some((e) => e[0] === "undo" && e[1] === "m1" && e[2] === "right"));
    ctl.destroy();
  });

  test("pillSelect, paramField, railCard, stepTracker construct Safe-DOM trees", () => {
    const { document, Maat } = bootMaat();
    let picked = null;
    const pills = Maat.pillSelect({
      label: "Mode",
      options: [{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }],
      value: "a",
      onChange: (v) => { picked = v; },
    });
    assert.equal(pills.childNodes[1].getAttribute("aria-pressed"), "true");
    pills.childNodes[2].dispatch("click");
    assert.equal(picked, "b");
    assert.equal(pills.childNodes[2].getAttribute("aria-pressed"), "true");

    const fld = Maat.paramField({ id: "p-limit", label: "Limit", type: "select", options: ["10", "50"], value: "50" });
    assert.equal(fld.childNodes[1].tagName, "SELECT");
    assert.equal(fld.childNodes[1].childNodes[1].selected, true);

    const card = Maat.railCard({ name: "Base USDC", status: "LIVE", stats: [{ label: "Fee", value: "$0.001" }], active: true });
    assert.equal(card.classList.contains("active"), true);
    assert.ok(card.textContent.includes("Base USDC"));

    const steps = Maat.stepTracker([
      { num: 1, code: "402", title: "Quote", headerName: "X-Price", headerVal: "100" },
      { num: 2, code: "SIG", title: "Sign" },
    ], 1);
    assert.equal(steps.childNodes[0].getAttribute("data-step-state"), "done");
    assert.equal(steps.childNodes[1].getAttribute("data-step-state"), "active");
  });
});
