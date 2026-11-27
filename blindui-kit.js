/* Maat Kit v1.0.0 (formerly BlindUI Kit) - Safe-DOM components over Maat core (ES2020). */
((R) => {
  "use strict";

  let N = null,
    S = String,
    I = Array.isArray,
    A = Object.assign,
    X = R.Maat || R.BlindUI || (typeof require < "u" && require("./maat.js")),
    rb = ".row .between",
    sm = ".sm .muted",
    C = A(Object.create(N), {
      blog: "M4 20h16M7 16l9-9 3 3-9 9H7z",
      benchmarks: "M6 19v-6m6 6V5m6 14v-9",
      apps: "M4 4h6v6H4zm10 0h6v6h-6zM4 14h6v6H4zm10 0h6v6h-6z",
      developers: "M4 17l6-5-6-5m8 11h8",
      chain: "M9 15l6-6M5 13l4 4 3-3M12 10l3-3 4 4",
      mail: "M3 6h18v12H3zm0 1l9 6 9-6",
      sign: "M12 3l8 4v5q0 6-8 9-8-3-8-9V7zm-3 9l2 2 4-4",
      social: "M4 5h16v11H9l-5 4z",
      finance: "M4 17l5-5 4 4 7-8m-5 0h5v5",
      live: "M12 12h.1M8 7q-4 5 0 10m8-10q4 5 0 10",
      call: "M3 7h12v10H3zm12 3l6-3v10l-6-3",
      cdn: "M12 3l9 5-9 5-9-5zm-9 9l9 5 9-5m-18 4l9 5 9-5",
      github: "M6 5v14M18 8q0 6-12 6M5 5h2M5 19h2M17 8h2",
      home: "M3 11l9-7 9 7M6 10v10h12V10"
    }),
    P = (v) => typeof v == "string",
    G = (v) => typeof v == "function",
    Y = (v) => !!v && typeof v == "object" && !I(v),
    B = Number.isFinite,
    T = (v) => Y(v) && B(v.nodeType),
    O = (v) => Y(v) ? v : {},
    L = (v, d) => I(v) && v.length ? v : d,
    tx = (v, d = "") => v != N && (v = S(v)) || d,
    st = (e, v) => (e.textContent = v),
    H = (t, c, ...k) => {
      c = P(c) ? { className: c } : I(c) ? A({ id: c[0] || N, className: c[1] || N }, c[2]) : c;
      if (c?.className) c.className = c.className.replace(/\./g, "bui-").replace(/%/g, "bk-");
      return X.h(t, c, ...k);
    },
    D = (c, ...k) => H("div", c, ...k),
    E = (c, ...k) => H("span", c, ...k),
    K = (i, c, t, f, p) => H("button", [i, c == ".tab" ? c : ".btn" + (c ? " .btn-" + c : ""), A({ type: "button" }, f && { onclick: f }, p)], t),
    M = (m, e) => (G(m?.appendChild) && (st(m, ""), m.appendChild(e)), e),
    J = (v) => v == N ? "" : P(v) ? v : JSON.stringify(v, N, 2),
    sa = (e, k, v) => e?.setAttribute?.(k, v),
    tc = (t) => /^(ok|warn|err)$/.test(t) ? " ." + t : "",
    rd = (v) => Math.max(0, Math.round(v)),
    V = (n, d, p) => X.svg(
      "svg",
      A({ width: n, height: n, viewBox: "0 0 24 24", fill: "none", "aria-hidden": "true" }, p),
      X.svg("path", { d: d, stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" })
    ),
    W = (g, f) => async function () {
      let b = this, t = g();
      if (t == N) return;
      try { await R.navigator?.clipboard?.writeText?.(S(t)); } catch {}
      st(b, "Copied");
      R.setTimeout?.(() => b.textContent == "Copied" && st(b, "Copy"), 1600);
      G(f) && await f(t);
    },
    Q = (l, s, i, a) => l.map((p, k) => {
      let u = p.id == i;
      sa(s[k], a, S(u));
      s[k].classList?.toggle("bui-on", u);
    }),
    F = (b, f) => {
      if (!b || !G(f)) return;
      let i = b.id, y;
      if (i && R.document?.getElementById?.(i) == b && X.bindAction) return X.bindAction(i, f, "click", { lock: !0 });
      b.addEventListener?.("click", async (e) => {
        if (y) return;
        y = 1;
        sa(b, "aria-busy", "true");
        try { return await f.call(b, e); } finally { y = 0; b.removeAttribute?.("aria-busy"); }
      });
    },
    U = (a) => (
      a = O(a),
      M(a.mount, E(
        [a.id, ".pill" + tc(a.tone)],
        E([N, ".dot", { "aria-hidden": "true" }]),
        E(N, tx(a.label, "IDLE"))
      ))
    ),
    xh = (t, p, ...k) => X.h(t, p, ...k),
    lc = (s) => S(s).toLowerCase(),
    op = (o) => P(o) ? { value: o } : O(o),
    TM = { b: "strong", i: "em", h5: "h4", h6: "h4" },
    NM = { class: "className" },
    BO = /^(disabled|checked|readOnly|hidden|selected|required|multiple|open|noValidate|spellcheck)$/,
    VT = /^(id|class|style|x|y|dx|dy|fill|stroke|transform|font-|text-|dominant-|opacity|data-|aria-)/,
    _nm = "colSpan rowSpan tabIndex readOnly noValidate maxLength minLength formAction viewBox preserveAspectRatio".split(" ").map((k) => (NM[lc(k)] = k)),
    Z = {
      version: "1.0.0",
      icon: (i, n) => {
        let k = tx(i).toLowerCase(), d = C[k];
        return V(B(n) && n > 0 ? n : 14, d || C.apps, { class: "bk-ic", "data-surface": d ? k : N });
      },
      statusPill: U,
      shell: (a) => {
        a = O(a);
        let s = tx(a.surface),
          e = (u) => X.sanitizeUrl(u, { allowRelative: true }),
          g = (u, c, p, ...k) => H(u ? "a" : "span", [N, c, A({ href: u || N }, p)], ...k),
          l = L(a.navItems, "Developers Mail Sign Social Finance".split(" ").map((i, k) => ({ id: k = i.toLowerCase(), label: i, href: "/" + k + "/" }))),
          h = e(a.brandHref ?? "/"),
          b = a.brand ?? "Blind Labs";
        return M(a.mount, D(
          [a.id, ".shell .col"],
          H("header", ".topbar", D("%in " + rb,
            T(b) ? b : g(h, ".brand", N, V(18, "M4 4h16v16H4zm8 5a3 3 0 100 6 3 3 0 100-6"), S(b)),
            H("nav", [N, "%bar", { "aria-label": "Suite navigation" }], l.map((u) => {
              u = O(u);
              let d = e(u.href), k = tx(u.surface || u.id), c = u.icon,
                v = u.active === true || !!s && (u.id == s || u.surface == s || u.href == "/" + s + "/");
              return g(
                d,
                ".tab" + (v ? " .on" : ""),
                { "aria-current": v ? "page" : N, "data-surface": k || N },
                T(c) ? c : c !== false && Z.icon(P(c) ? c : k),
                S(u.label || u.id || "App")
              );
            })), a.ssoSlot)),
          H("main", "%in .main .col", a.main),
          a.footer != N && H("footer", ".footer", D("%in " + sm, a.footer))
        ));
      },
      kpiStrip: (a) => {
        let p = O(a);
        return M(p.mount, H("section", [p.id, "%grid"], L(I(a) ? a : p.items, []).map((u) => {
          u = O(u);
          let b = tx(u.sub);
          return D(
            [u.id, ".card" + tc(u.tone)],
            D("%kl .muted", S(u.label || "Metric")),
            D("%kv .num", tx(u.value, "None yet")),
            b && D(".sm .subtle", b)
          );
        })));
      },
      stepRail: (a) => {
        let p = O(a);
        return M(p.mount, H("section", [p.id, ".col %st"], L(I(a) ? a : p.steps, []).map((u, i) => {
          u = O(u);
          let s = u.state == "active" || u.state == "done" ? u.state : "todo", b = tx(u.summary);
          return D(
            [u.id, ".card" + ({ active: " %act", done: " %dn" }[s] || ""), { "data-step-state": s }],
            D(
              ".row",
              E("%sn .num", s == "done" ? V(14, "M5 13l4 4L19 7") : S(u.num ?? i + 1)),
              H("strong", N, S(u.title || "Step " + (i + 1))),
              b && E("%ss " + sm, b)
            ),
            s != "done" && u.body != N && D("%sb", u.body)
          );
        })));
      },
      keyCard: (a) => {
        a = O(a);
        let i = tx(a.id, "bui-key"), h = i + "-", p = P(a.prefix) ? a.prefix.trim() : "",
          s = tx(a.status, p ? "ACTIVE" : "NONE"),
          u = s.toUpperCase(),
          t = a.statusTone || (/^(ACTIVE|VERIFIED|OK|READY)$/.test(u) ? "ok" : /429|LIMIT|^(WARN|PENDING)$/.test(u) ? "warn" : /^(REVOKED|ERROR|EXPIRED|DENIED)$/.test(u) ? "err" : N),
          q = a.quota, n = B(q?.used) ? q.used : 0,
          g = Y(q) && B(q.limit) && q.limit > 0 && D(
            [N, ".col", { style: { gap: "6px" } }],
            D(rb + " .sm", E(".muted", S(q.label || "Daily Quota")), E(".num", n + " / " + q.limit + (q.unit ? " " + q.unit : ""))),
            D("%qb", D([N, "%qf", { style: { width: Math.min(100, rd(n / q.limit * 100)) + "%" } }]))
          ),
          d = N,
          c = G(a.onRotate) && K(h + "rotate", "", "Rotate Key"),
          v = G(a.onRevoke) && K(h + "revoke", "danger", "Revoke Key"),
          k = P(a.secretOnce) && a.secretOnce;

        if (k) {
          let e = H("code", [h + "secret", ".box .mono"], k);
          d = D(
            [h + "once", ".card %once .col"],
            D(".sm", "Shown once. Save it now."),
            e,
            D(".row",
              K(h + "copy", "primary", "Copy", W(() => k || N, a.onCopy)),
              K(h + "dismiss", "ghost", "Dismiss", () => { k = ""; st(e, ""); d.parentNode?.removeChild(d); })
            )
          );
        }

        i = H(
          "section",
          [i, ".card .col %st"],
          D(rb, H("strong", N, S(a.title || "API Key")), U({ id: h + "status", tone: t, label: s })),
          D([h + "prefix", ".box .mono"], p ? (p.endsWith("...") ? p : p + "...") : "No active key"),
          D(".row " + sm, E(".num", "Created: " + (a.createdAt || "None yet")), E(".num", "Last used: " + (a.lastUsedAt || "Never"))),
          g,
          d,
          (c || v) && D(".row", c, v)
        );
        M(a.mount, i);
        F(c, a.onRotate);
        F(v, a.onRevoke);
        return i;
      },
      codeBlock: (a) => {
        a = O(a);
        let i = tx(a.id, "bui-code"),
          l = L(a.tabs, [{ id: "code", label: "Code", code: tx(a.code), lang: a.lang }]).map((u, k) => (
            u = O(u),
            { id: S(u.id || "t" + k), label: S(u.label || u.id || "Tab " + (k + 1)), code: S(u.code ?? ""), lang: tx(u.lang) }
          )),
          m = l.find((t) => t.id == a.activeTab) || l[0],
          e = H("code", ".mono", m.code),
          f = (t) => {
            m = t;
            st(e, t.code);
            /^[\w-]{1,24}$/.test(t.lang) ? sa(e, "data-lang", t.lang) : e.removeAttribute?.("data-lang");
            Q(l, s, t.id, "aria-selected");
          },
          s = l.map((t) => K(i + "-tab-" + t.id, ".tab", t.label, () => f(t), { role: "tab" }));
        f(m);
        return M(a.mount, H(
          "section",
          [i, ".card .code"],
          D("%cb " + rb, D([N, "%bar", { role: "tablist" }], s), K(i + "-copy", "ghost", "Copy", W(() => m.code, (v) => G(a.onCopy) && a.onCopy(v, m)))),
          H("pre", ".pre", e)
        ));
      },
      tryItPanel: (a) => {
        a = O(a);
        let i = tx(a.id, "bui-try"), p = i + "-",
          l = L(a.presets, [{ id: "default", label: "Health Check", method: "GET", path: "/api/v1/pricing" }]).map((u, k) => (
            u = O(u),
            {
              id: S(u.id || "p" + k),
              label: S(u.label || u.id || "Preset " + (k + 1)),
              method: S(u.method || "GET").toUpperCase(),
              path: S(u.path || u.route || "/"),
              body: u.body,
              headers: Y(u.headers) ? u.headers : N,
              sign: !!u.sign
            }
          )),
          m = l.find((t) => t.id == a.activePreset) || l[0],
          d = D([p + "route", ".mono " + sm]),
          e = H("textarea", [p + "body", ".input", { rows: 4, placeholder: "Payload (optional)" }]),
          b = K(p + "run", "primary", S(a.runLabel || "Run Live")),
          g = E(),
          h = E([p + "latency", ".num " + sm], "0 ms"),
          q = E([p + "quota", ".num " + sm]),
          v = H("code", ".mono", "Run to see response."),
          y = H("pre", ".pre .box", v),
          w = D([p + "output"], y),
          f = (t) => {
            m = t;
            st(d, t.method + " " + t.path);
            e.value = J(t.body);
            Q(l, s, t.id, "aria-pressed");
          },
          u = (t, c) => U({ id: p + "status", tone: t, label: c, mount: g }),
          s = l.map((t) => K(p + "preset-" + t.id, "", t.label, () => f(t)));
        u(N, "READY");
        f(m);
        i = H(
          "section",
          [i, ".card .col %st"],
          D(rb, H("strong", N, S(a.title || "Live Runner")), d),
          D("%grid %pre", s),
          e,
          D(rb, b, D(".row", g, h, q)),
          w
        );
        M(a.mount, i);
        F(b, async () => {
          let n = S(e.value || ""), c = N, t = () => R.performance?.now?.() ?? Date.now(), k = t(), z;
          if (n.trim()) try { c = JSON.parse(n); } catch { c = n; }
          u(N, "RUNNING");
          try {
            z = G(a.onRun)
              ? await a.onRun(A({ preset: m, bodyText: n }, m, { body: c }))
              : await X.api(m.path, A({}, m, { body: /^(GET|HEAD)$/.test(m.method) ? N : c }));
          } catch (t) {
            z = { ok: false, status: 0, error: S(t?.message || "") };
          }
          z = Y(z) ? z : { ok: true, status: 200, data: z };
          t = rd(B(z.latencyMs) ? z.latencyMs : t() - k);
          k = B(z.status) ? z.status : z.ok === false ? 0 : 200;
          n = !!(z.ok ?? (k >= 200 && k < 300));
          c = !n && k == 429;
          u(n ? "ok" : c ? "warn" : "err", c ? "429 LIMITED" : (k > 0 ? k + " " : "") + (n ? "OK" : "ERROR"));
          st(h, t + " ms");
          st(q, tx(z.quota));
          if (G(a.renderResult)) {
            st(w, "");
            c = a.renderResult(z, w);
            c != N && c !== false && w.appendChild(T(c) ? c : D(N, c));
          } else {
            st(v, P(z.text) ? z.text : z.data != N ? J(z.data) : S(z.error || "Request failed"));
            w.firstChild !== y && M(w, y);
          }
          return z;
        });
        return i;
      },
      bindTactileList: (c, a) => {
        a = O(a);
        let hm = a.holdMs ?? 380, dp = a.driftPx ?? 10, th = a.swipeThresholdPx ?? 76, mx = a.maxSwipePx ?? 118, df = a.dampFactor ?? .35,
          sel = a.selected instanceof Set ? a.selected : new Set(I(a.selected) ? a.selected : []),
          { abs: ab, min: mn, round: rn } = Math, tp = "tactile-press", sws = "swiping", cl = [], tm = setTimeout,
          ev = (e, k, f, p) => e?.[(p == 2 ? "remove" : "add") + "EventListener"]?.(k, f, p < 2 ? { passive: !!p } : N),
          nt = (i) => a.onSelectChange?.(sel, i),
          tg = (i) => { if (i == N || i === "") return false; let u = !sel.has(i); u ? sel.add(i) : sel.delete(i); nt(i); return u; },
          bR = (w, r, it) => {
            if (!r) return;
            let ds = r.dataset, rl = r.classList, wl = w?.classList, id = G(a.getId) ? a.getId(it ?? r) : P(it) ? it : it?.id ?? ds?.id ?? "", sx = 0, sy = 0, dx = 0, sw = 0, sc = 0, lp = 0, hs = 0, ti = N, ac = 0,
              ok = (f) => !G(f) || !!f(it, r), ch = () => ti != N && (clearTimeout(ti), ti = N), up = () => rl?.remove(tp),
              rs = () => { rl?.remove(sws, tp); wl?.remove(sws + "-right", sws + "-left", "swipe-armed"); r.style && (r.style.transform = ""); },
              t1 = (e) => e?.touches?.length === 1 && e.touches[0],
              fl = (k, ms) => ds && (ds[k] = "1", tm(() => { delete ds[k]; }, ms)),
              ts = (e) => {
                let t = t1(e); if (!t || !ok(a.isEnabled)) return;
                sx = t.clientX; sy = t.clientY; dx = sw = sc = lp = hs = 0; ac = 1; rl?.add(tp); ch();
                ti = tm(() => { ti = N; if (!ac || sw || sc) return; lp = 1; up(); fl("justLongPressed", 420); a.onHaptic?.("medium"); G(a.onLongPress) ? a.onLongPress(id, it, r) : tg(id); }, hm);
              },
              tv = (e) => {
                let t = ac && t1(e); if (!t) return;
                let rx = t.clientX - sx, ry = t.clientY - sy;
                if (!sw && !sc) {
                  (ab(rx) > dp || ab(ry) > dp) && ch();
                  if (ab(ry) > 12 && ab(ry) > ab(rx)) return (sc = 1, up());
                  if (ab(rx) > 14 && ab(rx) > ab(ry) * 1.25) { sw = 1; up(); rl?.add(sws); }
                }
                if (!sw || lp) return;
                let aR = ok(a.canSwipeRight), aL = ok(a.canSwipeLeft), ad = ab(rx = rx > 0 ? (aR ? rx : 0) : aL ? rx : 0);
                dx = ad <= th ? rx : (rx < 0 ? -1 : 1) * mn(mx, th + (ad - th) * df);
                let ar = ab(dx) >= th;
                ar && !hs ? (hs = 1, a.onHaptic?.("light")) : !ar && hs && ab(dx) < th - 4 && (hs = 0);
                r.style && (r.style.transform = "translateX(" + rn(dx) + "px)");
                wl && (wl.toggle(sws + "-right", dx > 18 && aR), wl.toggle(sws + "-left", dx < -18 && aL), wl.toggle("swipe-armed", ar));
                ab(dx) > 14 && e.cancelable !== false && e.preventDefault?.();
              },
              te = () => {
                if (!ac) return; ac = 0; ch(); up();
                if (!sw) return rs();
                let fx = dx, dir = fx > 0 ? "Right" : "Left", okD = ok(a["canSwipe" + dir]); rs();
                if (ab(fx) < th || !okD) return;
                fl("justSwiped", 320);
                a["onSwipe" + dir]?.(id, (f) => G(f) ? f() : a.onUndo?.(id, it, lc(dir)), it, r);
              },
              tc0 = () => { ac = 0; ch(); rs(); },
              ls = [["start", ts, 1], ["move", tv, 0], ["end", te, 1], ["cancel", tc0, 1]],
              avE = a.bindAvatar !== false && r.querySelector?.(tx(a.avatarSelector, ".avatar,[data-tactile-avatar]")),
              avF = avE && ((e) => { e?.stopPropagation?.(); tg(id); a.onHaptic?.("light"); });
            ls.map(([k, f, p]) => ev(r, "touch" + k, f, p));
            avE && ev(avE, "click", avF, 1);
            cl.push(() => { ch(); ls.map(([k, f]) => ev(r, "touch" + k, f, 2)); avE && ev(avE, "click", avF, 2); });
          };
        if (c && P(a.rowSelector) && G(c.querySelectorAll)) for (let r of c.querySelectorAll(a.rowSelector)) bR(r.parentNode, r, r.dataset?.id ?? r);
        return { selected: sel, toggle: tg, clear: () => (sel.clear(), nt(N)), selectAll: (xs) => ((xs || []).map((x) => sel.add(x)), nt(N)), bindRow: bR, destroy: () => cl.splice(0).map((f) => f()) };
      },
      pillSelect: (a) => {
        a = O(a);
        let m = !!a.multi, vs = new Set(m && I(a.values) ? a.values : a.value != N ? [a.value] : []),
          cc = tx(a.chipClass, "bui-tab"), ac = tx(a.activeClass, "bui-on"), dk = tx(a.dataKey, "val"), ap = "aria-pressed", bs = [];
        return M(a.mount, H("div", [a.id, tx(a.className, ".row"), a.attrs], a.label && E(sm, S(a.label)), L(a.options, []).map((o) => {
          o = op(o); let v = S(o.value ?? o.id ?? o.label ?? ""), on = o.active === !0 || vs.has(v),
            b = K(N, N, S(o.label ?? v), () => { m && vs.has(v) ? vs.delete(v) : (!m && vs.clear(), vs.add(v)); bs.map(([x, xv, u = vs.has(xv)]) => (sa(x, ap, S(u)), x.classList?.toggle(ac, u))); a.onChange?.(m ? [...vs] : v, o); }, A({ className: cc + (o.cls ? " " + o.cls : "") + (on ? " " + ac : ""), [ap]: S(on) }, o.attrs, a.dataAct && { "data-act": S(a.dataAct) }, dk && { ["data-" + dk]: v }));
          return (bs.push([b, v]), b);
        })));
      },
      paramField: (a) => {
        a = O(a);
        let t = tx(a.type, "text"), v = a.value,
          ip = A({ id: a.id || N, className: tx(a.inputClass, "bui-input"), "aria-label": a.ariaLabel || N }, a.attrs,
            a.dataParam && { "data-param": S(a.dataParam) }, v != N && { value: S(v) },
            G(a.onChange) && { onchange: (e) => a.onChange(e.target?.value, e) }, G(a.onInput) && { oninput: (e) => a.onInput(e.target?.value, e) });
        "name placeholder min max step rows".split(" ").map((k) => a[k] != N && (ip[k] = S(a[k])));
        let el = t == "select" ? xh("select", ip, L(a.options, []).map((o) => { o = op(o); let x = S(o.value ?? o.label ?? ""); return xh("option", { value: x, selected: v != N && S(v) == x }, S(o.label ?? x)); }))
          : t == "textarea" ? xh("textarea", ip, v != N ? S(v) : "") : xh("input", A(ip, { type: t }));
        return M(a.mount, D(tx(a.className, ".col"), a.label && H("label", [N, ".sm", { for: a.id || N }], S(a.label)), el));
      },
      railCard: (a) => {
        a = O(a);
        return M(a.mount, D([a.id, tx(a.className, ".card") + (a.active ? " active" : ""), A({}, a.attrs, G(a.onSelect) && { onclick: (e) => a.onSelect(a, e) })],
          D(rb, H("strong", N, tx(a.name || a.title)), a.status && E(tx(a.statusCls, ".pill"), S(a.status))),
          a.subtitle && D(sm, S(a.subtitle)),
          I(a.stats) && a.stats.map((x) => P(x) ? D(".sm", x) : D(rb + " .sm", E(".muted", tx(x.label)), E(".num", tx(x.value)))),
          a.badge && D(".sm", S(a.badge)),
          a.actionLabel && K(N, N, S(a.actionLabel), G(a.onAction) && ((e) => (e?.stopPropagation?.(), a.onAction(a, e))), a.actionAttrs)
        ));
      },
      stepTracker: (ls, idx, a) => {
        a = O(a);
        let ai = B(idx) ? idx : -1;
        return M(a.mount, D([a.id, tx(a.className, ".col")], L(ls, []).map((s, i) => {
          s = O(s); let q = s.state || (ai < 0 ? "" : i < ai ? "done" : i == ai ? "active" : "todo");
          return D([N, tx(a.itemClass, ".card") + (s.cls ? " " + s.cls : "") + (q ? " " + q : ""), { "data-step-state": q || N }],
            D(".row", E(".num", S(s.num ?? i + 1)), s.code && H("code", s.codeCls || ".mono", S(s.code)), H("strong", N, tx(s.title, "Step " + (i + 1)))),
            s.headerName && D(".mono .sm", S(s.headerName) + ": " + tx(s.headerVal)),
            s.meta && D(sm, S(s.meta))
          );
        })));
      },
      mountSafe: (el, v) => {
        if (!el) return el;
        let d = el.ownerDocument || R.document, tn = (x) => d.createTextNode(x), oe = Object.entries,
          ap = (ns) => el.replaceChildren ? el.replaceChildren(...ns) : (st(el, ""), ns.map((n) => el.appendChild(n)));
        if (v == N || v === "") return (ap([]), el);
        if (T(v)) return (ap([v]), el);
        if (I(v)) return (ap(v.filter((x) => x != N && x !== false).map((x) => T(x) ? x : tn(S(x)))), el);
        let rn = [], sk = N, st0 = [{ c: rn, svg: /svg/i.test(el.namespaceURI + el.tagName), t: "" }],
          top = () => st0[st0.length - 1],
          push = (n) => { let y = top(); y.c ? y.c.push(n) : y.n.appendChild(n); },
          dc = (t) => t.replace(/&(#\d+|#x[\da-f]+|[a-z]+);/gi, (m, k) => k[0] == "#" ? S.fromCharCode(+(k[1] == "x" || k[1] == "X" ? "0" + k.slice(1) : k.slice(1))) : ({ amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\xa0" }[lc(k)] || m)),
          ps = (t) => { let o = {}; S(t).replace(/([a-z-]+)\s*:\s*([^;]+)/gi, (_, k, val) => { val = val.trim(); val && !/url\s*\(|expression\s*\(|javascript:/i.test(val) && (o[lc(k).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = val); }); return o; },
          re = /<!--[\s\S]*?-->|<\/([a-z][\w:-]*)\s*>|<([a-z][\w:-]*)([^<>]*)>|([^<]+|<)/gi, m;
        while ((m = re.exec(S(v)))) {
          if (m[4]) { !sk && push(tn(dc(m[4]))); continue; }
          if (m[1]) {
            let ct = lc(m[1]);
            if (sk) { ct == sk && (sk = N); continue; }
            for (let k = st0.length, mt = TM[ct] || ct; --k > 0;) if (st0[k].t == mt) { st0.length = k; break; }
            continue;
          }
          if (!m[2] || sk) continue;
          let t = lc(m[2]), as = m[3] || "", sc = /\/\s*$/.test(as);
          sc && (as = as.replace(/\/\s*$/, ""));
          if (/^(script|style|iframe|object|embed|template)$/.test(t)) { !sc && (sk = t); continue; }
          let inSvg = top().svg || t == "svg", pr = {}, ar = /([a-z_:][\w:.-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/gi, am, nd;
          while ((am = ar.exec(as))) {
            let kl = lc(am[1]), dv = dc(am[2] ?? am[3] ?? am[4] ?? "");
            if (/^on/.test(kl) || kl == "srcdoc" || inSvg && /href/i.test(kl)) continue;
            if (kl == "style") { let so = ps(dv); for (let _ in so) pr.style = so; }
            else if (inSvg) pr[NM[kl] || kl] = dv;
            else {
              let nk = NM[kl] || kl;
              if (BO.test(nk)) pr[nk] = true;
              else if (/^(href|src|action|formAction)$/.test(nk)) { let u = X.sanitizeUrl(dv, { allowRelative: true }); u && (pr[nk] = u); }
              else pr[nk] = dv;
            }
          }
          if (inSvg) {
            if (t == "text" || t == "tspan") {
              nd = d.createElementNS("http://www.w3.org/2000/svg", t);
              for (let [k, val] of oe(pr)) VT.test(k) && (k == "style" ? A(nd.style, val) : sa(nd, k, S(val)));
            } else { try { nd = X.svg(t, pr); } catch { continue; } }
            push(nd); !sc && st0.push({ n: nd, svg: 1, t: t });
          } else {
            let ht = TM[t] || t;
            try { nd = xh(ht, pr); } catch {
              let ok = {};
              try { xh(ht, {}); } catch { continue; }
              for (let [k, val] of oe(pr)) try { xh(ht, { [k]: val }); ok[k] = val; } catch {}
              nd = xh(ht, ok);
            }
            push(nd); !sc && !/^(br|hr|input|img|col|meta|link)$/.test(ht) && st0.push({ n: nd, svg: 0, t: ht });
          }
        }
        return (ap(rn), el);
      }
    };

  X && (X.kit = Z, "bindTactileList pillSelect paramField railCard stepTracker mountSafe".split(" ").map((k) => (X[k] = Z[k])));
  typeof module < "u" && module?.exports && (module.exports = Z);
})(globalThis);
