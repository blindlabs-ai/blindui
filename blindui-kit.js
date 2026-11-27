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
      if (i && R.document?.getElementById?.(i) === b && X.bindAction) return X.bindAction(i, f, "click", { lock: true });
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
      }
    };

  X && (X.kit = Z);
  typeof module < "u" && module?.exports && (module.exports = Z);
})(globalThis);
