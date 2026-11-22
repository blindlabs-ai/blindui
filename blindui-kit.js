/* BlindUI Kit v1.0.0 - Reusable Safe-DOM components over BlindUI core (ES2020). */
((R) => {
  "use strict";

  let N = null,
    S = String,
    I = Array.isArray,
    A = Object.assign,
    RD = Math.round,
    CC = "currentColor",
    RB = ".row .between",
    SM = ".sm .muted",
    BP = ".btn .btn-primary",
    BG = ".btn .btn-ghost",
    BM = ".box .mono",
    CS = ".card .col %st",
    RF = "Request failed",
    isS = (v) => typeof v == "string",
    isF = (v) => typeof v == "function",
    isO = (v) => !!v && typeof v == "object" && !I(v),
    isN = (v) => typeof v == "number" && isFinite(v),
    nd = (v) => isO(v) && isN(v.nodeType),
    O = (v) => isO(v) ? v : {},
    L = (v, d) => I(v) && v.length ? v : d,
    B = () => R?.BlindUI || (typeof require == "function" ? require("./blindui.js") : N),
    G = () => R?.document || N,
    tx = (v, d = "") => v != N && S(v) !== "" ? S(v) : d,
    st = (e, v) => (e.textContent = v),
    clr = (u) => { while (u?.firstChild) u.removeChild(u.firstChild); },
    ap = (p, c) => c != N && c !== false && (I(c) ? c.map((x) => ap(p, x)) : p.appendChild(nd(c) ? c : G().createTextNode(S(c)))),
    ec = (s) => s.replace(/(^| )\./g, "$1bui-").replace(/(^| )%/g, "$1bk-"),
    H = (t, c, ...k) => B().h(
      t,
      isS(c) ? { className: ec(c) } : I(c) ? A({}, c[0] && { id: S(c[0]) }, c[1] && { className: ec(c[1]) }, c[2]) : c,
      ...k
    ),
    vg = (t, p, ...k) => B().svg(t, p, ...k),
    D = (c, ...k) => H("div", c, ...k),
    E = (c, ...k) => H("span", c, ...k),
    SE = (i, c, ...k) => H("section", [i, c], ...k),
    K = (i, c, t, f, x) => {
      let b = H("button", [i, c, A({ type: "button" }, x)], t);
      f && on(b, f);
      return b;
    },
    M = (m, e) => (m && isF(m.appendChild) && (clr(m), m.appendChild(e)), e),
    J = (v) => v == N ? "" : isS(v) ? v : JSON.stringify(v, N, 2),
    Y = (o, d) => isS(o.id) && o.id || "bui-" + d,
    T = () => R?.performance?.now?.() ?? Date.now(),
    sa = (e, k, v) => e?.setAttribute?.(k, v),
    su = (u) => B().sanitizeUrl(u, { allowRelative: true }),
    on = (e, f) => e?.addEventListener?.("click", f),
    tc = (t) => /^(ok|warn|err)$/.test(t) ? " ." + t : "",
    V = (n, x, ...k) => vg("svg", { width: n, height: n, viewBox: "0 0 " + x + " " + x, fill: "none", "aria-hidden": "true" }, ...k),
    W = (b, g, f) => on(b, async () => {
      let t = g();
      if (t == N) return;
      try { await R?.navigator?.clipboard?.writeText?.(S(t)); } catch {}
      st(b, "Copied");
      R?.setTimeout?.(() => b.textContent == "Copied" && st(b, "Copy"), 1600);
      isF(f) && await f(t);
    }),
    Q = (l, s, i, a) => l.map((p, k) => {
      let u = p.id == i;
      sa(s[k], a, S(u));
      s[k].classList?.toggle("bui-on", u);
    }),
    F = (b, f) => {
      if (!b || !isF(f)) return;
      let i = b.id, x = B();
      if (i && G()?.getElementById?.(i) === b && isF(x.bindAction)) return x.bindAction(i, f, "click", { lock: true });
      let y, z = () => { y = 0; b.removeAttribute?.("aria-busy"); };
      on(b, (e) => {
        if (y) return;
        y = 1;
        sa(b, "aria-busy", "true");
        try {
          let r = f.call(b, e);
          return isF(r?.then) ? r.then((v) => (z(), v), (u) => { z(); throw u; }) : (z(), r);
        } catch (u) { z(); throw u; }
      });
    },
    U = (a) => {
      let o = O(a);
      return M(o.mount, E(
        [o.id, ".pill" + tc(o.tone)],
        E([N, ".dot", { "aria-hidden": "true" }]),
        E(N, tx(o.label, "IDLE"))
      ));
    },
    Z = {
      version: "1.0.0",
      statusPill: U,
      shell: (a) => {
        let o = O(a), s = isS(o.surface) ? o.surface : "",
          l = L(o.navItems, ["developers", "mail", "sign", "social", "finance"].map((i) => ({ id: i, label: i[0].toUpperCase() + i.slice(1), href: "/" + i + "/" }))),
          h = su(o.brandHref ?? "/"),
          b = o.brand ?? "Blind Labs",
          n = nd(b) ? b : H(h ? "a" : "span", [N, ".brand", h && { href: h }],
            V(18, 20,
              vg("rect", { x: 2, y: 2, width: 16, height: 16, rx: 4, stroke: CC, "stroke-width": 1.6 }),
              vg("circle", { cx: 10, cy: 10, r: 3, fill: CC })
            ), S(b));
        return M(o.mount, D(
          [o.id, ".shell .col"],
          H("header", ".topbar", D("%in " + RB, n, H("nav", [N, "%bar", { "aria-label": "Suite navigation" }], l.map((z) => {
            let u = O(z), r = su(u.href),
              v = u.active === true || !!s && (u.id == s || u.surface == s || u.href == "/" + s + "/");
            return H(
              r ? "a" : "span",
              [N, ".tab" + (v ? " .on" : ""), A({}, r && { href: r }, v && { "aria-current": "page" }, u.id && { "data-surface": S(u.id) })],
              S(u.label || u.id || "App")
            );
          })), o.ssoSlot)),
          H("main", "%in .main .col", o.main),
          o.footer != N && H("footer", ".footer", D("%in " + SM, o.footer))
        ));
      },
      kpiStrip: (a) => {
        let o = I(a) ? { items: a } : O(a);
        return M(o.mount, SE(o.id, "%grid", L(o.items, []).map((z) => {
          let u = O(z), b = tx(u.sub);
          return D(
            [u.id, ".card" + tc(u.tone)],
            D("%kl .muted", S(u.label || "Metric")),
            D("%kv .num", tx(u.value, "None yet")),
            b && D(".sm .subtle", b)
          );
        })));
      },
      stepRail: (a) => {
        let o = I(a) ? { steps: a } : O(a);
        return M(o.mount, SE(o.id, ".col %st", L(o.steps, []).map((z, i) => {
          let u = O(z), s = u.state == "active" || u.state == "done" ? u.state : "todo", b = tx(u.summary);
          return D(
            [u.id, ".card" + (s == "active" ? " %act" : s == "done" ? " %dn" : ""), { "data-step-state": s }],
            D(
              ".row",
              E("%sn .num", s == "done"
                ? V(14, 16, vg("path", { d: "M3.5 8.5L6.5 11.5L12.5 4.5", stroke: CC, "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round" }))
                : S(u.num ?? i + 1)),
              H("strong", N, S(u.title || "Step " + (i + 1))),
              b && E("%ss " + SM, b)
            ),
            s != "done" && u.body != N && D("%sb", u.body)
          );
        })));
      },
      keyCard: (a) => {
        let o = O(a), i = Y(o, "key"), p = isS(o.prefix) ? o.prefix.trim() : "",
          s = isS(o.status) && o.status || (p ? "ACTIVE" : "NONE"),
          u = s.toUpperCase(),
          t = o.statusTone || (/^(ACTIVE|VERIFIED|OK|READY)$/.test(u) ? "ok" : /429|LIMIT|^(WARN|PENDING)$/.test(u) ? "warn" : /^(REVOKED|ERROR|EXPIRED|DENIED)$/.test(u) ? "err" : "idle"),
          q = o.quota, n = isN(q?.used) ? q.used : 0,
          g = isO(q) && isN(q.limit) && q.limit > 0 && D(
            [N, ".col", { style: { gap: "6px" } }],
            D(RB + " .sm", E(".muted", S(q.label || "Daily Quota")), E(".num", n + " / " + q.limit + (q.unit ? " " + q.unit : ""))),
            D("%qb", D([N, "%qf", { style: { width: Math.max(0, Math.min(100, RD(n / q.limit * 100))) + "%" } }]))
          ),
          d = N,
          r = isF(o.onRotate) && K(i + "-rotate", ".btn", "Rotate Key"),
          v = isF(o.onRevoke) && K(i + "-revoke", ".btn .btn-danger", "Revoke Key"),
          k = isS(o.secretOnce) && o.secretOnce;

        if (k) {
          let e = H("code", [i + "-secret", BM], k),
            b = K(i + "-copy", BP, "Copy"),
            x = K(i + "-dismiss", BG, "Dismiss", () => { k = ""; st(e, ""); d.parentNode?.removeChild(d); });
          d = D([i + "-once", "%once .col"], D(".sm", "Shown once. Save it now."), e, D(".row", b, x));
          W(b, () => k || N, o.onCopy);
        }

        let c = SE(
          i,
          CS,
          D(RB, H("strong", N, S(o.title || "API Key")), U({ id: i + "-status", tone: t, label: s })),
          D([i + "-prefix", BM], p ? (p.endsWith("...") ? p : p + "...") : "No active key"),
          D(".row " + SM, E(".num", "Created: " + (o.createdAt || "None yet")), E(".num", "Last used: " + (o.lastUsedAt || "Never"))),
          g,
          d,
          (r || v) && D(".row", r, v)
        );
        M(o.mount, c);
        F(r, o.onRotate);
        F(v, o.onRevoke);
        return c;
      },
      codeBlock: (a) => {
        let o = O(a), i = Y(o, "code"),
          l = L(o.tabs, [{ id: "code", label: "Code", code: isS(o.code) ? o.code : "", lang: o.lang }]).map((z, k) => {
            let u = O(z);
            return { id: S(u.id || "t" + k), label: S(u.label || u.id || "Tab " + (k + 1)), code: S(u.code ?? ""), lang: isS(u.lang) ? u.lang : "" };
          }),
          m = l.find((t) => t.id == o.activeTab) || l[0],
          e = H("code", ".mono", m.code),
          f = (t) => {
            m = t;
            st(e, t.code);
            /^[\w-]{1,24}$/.test(t.lang) ? sa(e, "data-lang", t.lang) : e.removeAttribute?.("data-lang");
            Q(l, s, t.id, "aria-selected");
          },
          b = K(i + "-copy", BG, "Copy"),
          s = l.map((t) => K(i + "-tab-" + t.id, ".tab", t.label, () => f(t), { role: "tab" }));
        f(m);
        W(b, () => m.code, (v) => isF(o.onCopy) && o.onCopy(v, m));
        return M(o.mount, SE(
          i,
          ".card .code",
          D("%cb " + RB, D([N, "%bar", { role: "tablist" }], s), b),
          H("pre", ".pre", e)
        ));
      },
      tryItPanel: (a) => {
        let o = O(a), i = Y(o, "try"),
          l = L(o.presets, [{ id: "default", label: "Health Check", method: "GET", path: "/api/v1/pricing" }]).map((z, k) => {
            let u = O(z);
            return {
              id: S(u.id || "p" + k),
              label: S(u.label || u.id || "Preset " + (k + 1)),
              method: S(u.method || "GET").toUpperCase(),
              path: S(u.path || u.route || "/"),
              body: u.body,
              headers: isO(u.headers) ? u.headers : N,
              sign: !!u.sign
            };
          }),
          m = l.find((p) => p.id == o.activePreset) || l[0],
          d = D([i + "-route", ".mono " + SM]),
          e = H("textarea", [i + "-body", ".input", { rows: "4", placeholder: "Request payload (optional)" }]),
          b = K(i + "-run", BP, S(o.runLabel || "Run Live")),
          g = E(N, U({ id: i + "-status", tone: "idle", label: "READY" })),
          h = E([i + "-latency", ".num " + SM], "0 ms"),
          q = E([i + "-quota", ".num " + SM]),
          v = H("code", ".mono", "Run a request to see the response."),
          wp = H("pre", ".pre .box", v),
          w = D([i + "-output"], wp),
          f = (p) => {
            m = p;
            st(d, p.method + " " + p.path);
            e.value = J(p.body);
            Q(l, s, p.id, "aria-pressed");
          },
          u = (t, x) => U({ id: i + "-status", tone: t, label: x, mount: g }),
          r = async () => {
            let n = S(e.value || ""), p = N, k = T(), x;
            if (n.trim()) try { p = JSON.parse(n); } catch { p = n; }
            u("idle", "RUNNING");
            try {
              x = isF(o.onRun)
                ? await o.onRun(A({ preset: m, bodyText: n }, m, { body: p }))
                : await B().api(m.path, A(
                    { method: m.method },
                    m.headers && { headers: m.headers },
                    m.sign && { sign: true },
                    p != N && m.method != "GET" && m.method != "HEAD" && { body: p }
                  ));
            } catch (y) {
              x = { ok: false, status: 0, error: S(y?.message || RF) };
            }
            let z = isO(x) ? x : { ok: true, status: 200, data: x },
              y = isN(z.status) ? z.status : z.ok === false ? 0 : 200,
              c = z.ok != N ? !!z.ok : y >= 200 && y < 300,
              t = !c && y == 429;
            u(c ? "ok" : t ? "warn" : "err", t ? "429 LIMITED" : (y > 0 ? y + " " : "") + (c ? "OK" : "ERROR"));
            st(h, RD(isN(z.latencyMs) ? z.latencyMs : Math.max(0, T() - k)) + " ms");
            st(q, z.quota != N ? S(z.quota) : "");
            if (isF(o.renderResult)) {
              clr(w);
              ap(w, o.renderResult(z, w));
            } else {
              st(v, isS(z.text) ? z.text : z.data != N ? J(z.data) : S(z.error || RF));
              w.firstChild !== wp && M(w, wp);
            }
            return z;
          },
          s = l.map((p) => K(i + "-preset-" + p.id, ".btn", p.label, () => f(p)));
        f(m);
        let c = SE(
          i,
          CS,
          D(RB, H("strong", N, S(o.title || "Live Runner")), d),
          D("%grid %pre", s),
          e,
          D(RB, b, D(".row", g, h, q)),
          w
        );
        M(o.mount, c);
        F(b, r);
        return c;
      }
    };

  let x = B();
  x && (x.kit = Z);
  typeof module == "object" && module?.exports && (module.exports = Z);
})(typeof globalThis != "undefined" ? globalThis : this);
