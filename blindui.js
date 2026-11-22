/* BlindUI v1.0.0 - Zero-dep Safe-DOM & linear Safe-Markdown runtime (ES2020). */
((R) => {
  "use strict";

  let N = null,
    S = String,
    I = Array.isArray,
    m0 = "tabIndex colSpan rowSpan",
    d0 = "id title value " + m0,
    [H, V, B, U, A, D, M] = [
      "div span p a button input textarea select option label form ul ol li " +
      "h1 h2 h3 h4 strong em small code pre blockquote hr br table thead tbody " +
      "tr th td section header footer nav main aside article details summary " +
      "dl dt dd canvas iframe",
      "svg g path rect circle ellipse line polyline polygon",
      "disabled checked readOnly hidden selected required multiple open noValidate spellcheck",
      "href src action formAction",
      d0 + " role name type placeholder autocomplete rows cols maxLength minLength " +
      "min max step pattern accept for target rel download start scope alt width height dir lang",
      d0,
      m0
    ].map((s) => new Set(s.split(" "))),
    MR = /^[a-z\d.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z\d-]+(?:\.[a-z\d-]+)+$/i,
    RL = /^( *)(?:([-*]) |(\d{1,3})\. )(.*)$/,
    RB = /^[ \t]*$/,
    RF = /^(`{3,})\s*(.*)$/,
    RC = /^(`{3,}) *$/,
    RH = /^(#{1,3}) +(.*)$/,
    RR = /^-{3,} *$/,
    RP = /^(?:[ \t]*$|>|`{3,}|#{1,3} +|-{3,} *$| *(?:[-*] |\d{1,3}\. ))/,
    RG = /^[\w-]{1,24}$/,
    BK = { h1: "# ", h2: "## ", h3: "### ", ul: "- ", ol: "1. ", bq: "> " },
    _n = "\n",
    _p = "p",
    _h = "hr",
    _c = "code",
    _d = "---",
    _st = "strong",
    _u = "ul",
    _o = "ol",
    _q = "bq",
    _b = "br",
    _nb = "bui-nb",
    _nf = "bui-nb-focus",
    _ne = "bui-nb-empty",
    _dp = "data-placeholder",
    isS = (v) => typeof v == "string",
    isF = (v) => typeof v == "function",
    isN = (v) => typeof v == "number",
    isO = (v) => !!v && typeof v == "object" && !I(v),
    isL = (k) => k == _u || k == _o,
    ln = (x) => x.length,
    sl = (s, a, b) => s.slice(a, b),
    ix = (a, b, c) => a.indexOf(b, c),
    doc = () => R?.document || N,
    ce = (d, t) => d.createElement(t),
    tn = (d, s) => d.createTextNode(s),
    ap = (p, c) => p.appendChild(c),
    ins = (p, c, r) => p.insertBefore(c, r),
    rm = (p, c) => p.removeChild(c),
    sa = (e, k, v) => e?.setAttribute?.(k, v),
    on = (e, t, f) => e?.addEventListener?.(t, f),
    cl = (e, k, x) => e?.classList?.[x ? "add" : "remove"](k),
    byId = (i, d = doc()) => d?.getElementById?.(i),
    lc = (s) => s.toLowerCase(),
    cc = (s, i) => s.charCodeAt(i),
    nt = (n) => n?.nodeType,
    tg = (n) => lc(n?.tagName || ""),
    ent = (o) => Object.entries(o),
    getR = () => { let s = R?.getSelection?.(); return [s, s && s.rangeCount > 0 ? s.getRangeAt(0) : N]; },
    fail = (m) => { throw new Error("blindui_" + m); },
    failD = (m) => fail("disallowed_" + m),

    /* Strict URL allowlist: https, mailto (no header injection), optional relative/blob. */
    su = (a, o, r, b) => {
      if (!isS(a)) return N;
      let s = a.replace(/^ +| +$/g, ""), i = ix(s, ":"), p, k, m, j, q;
      if (!s || ln(s) > 2048 || /^\/\/|[\x00-\x20\x7f\\\x80-\x9f]/.test(s)) return N;
      if (i < 0) return /&#|&(?:colon|tab|newline);/i.test(s) ? N : (r || o?.allowRelative === true) && /^\.?\//.test(s) ? s : N;
      if (!/^[a-z]+$/i.test(p = sl(s, 0, i))) return N;
      k = lc(p);
      return (b || o?.allowDownloadBlob === true) && k == "blob" ? (ln(s) > 5 ? s : N)
        : k == "https" ? ((m = /^https:\/\/[a-z\d-]+(?:\.[a-z\d-]+)+(?::([1-9]\d{0,4}))?(?:[/?#]|$)/i.exec(s)) && (!m[1] || +m[1] <= 65535) ? "https://" + sl(s, 8) : N)
        : k == "mailto" ? ((p = sl(s, 7), j = ix(p, "?"), m = j < 0 ? p : sl(p, 0, j), q = j < 0 ? N : sl(p, j + 1), m && ln(m) <= 254 && MR.test(m) && (q === N || !/%0[ad0]/i.test(q) && /^subject=(?:[a-z\d._~+\-!'()*,:@\/]|%[\da-f]{2})*$/i.test(q))) ? "mailto:" + p : N)
        : N;
    },

    addCh = (d, p, c) => {
      if (c != N && c !== false) I(c) ? c.map((x) => addCh(d, p, x)) : ap(p, isO(c) && isN(c.nodeType) ? c : tn(d, S(c)));
      return p;
    },

    setSt = (e, v, t) => {
      !isO(v) && failD(t + "style");
      for (let [k, x] of ent(v)) k == "cssText" ? failD(t + "style.cssText") : x != N && (e.style[k] = S(x));
    },

    /* Linear inline Safe-Markdown parser shared by BlindUI.md and BlindUI.notionEditor. */
    ch = (n) => [...(n?.childNodes || n?.children || [])],
    tx = (n) => n.nodeValue ?? n.data ?? "",
    setTx = (n, v) => { "nodeValue" in n ? (n.nodeValue = v) : (n.data = v); },
    zws = "\u200b",
    stripZ = (s) => s.replace(/\u200b/g, ""),
    normS = (s) => stripZ(s).replace(/\u00a0/g, " "),
    sTx = (n) => normS(tx(n)),
    elE = (d, u, t, x) => { let e = ce(d, t); x != N && ap(e, tn(d, x)); return ap(u, e); },
    mkA = (d, h) => { let e = ce(d, "a"); sa(e, "href", h); sa(e, "target", "_blank"); sa(e, "rel", "noopener noreferrer nofollow"); return e; },
    /* Balanced-paren URL end scanner (max nesting 4). */
    mdG = (t, i, e) => {
      for (let x = 0; i < e; i++) {
        let c = cc(t, i);
        if (c == 40 && ++x > 4) return -2;
        if (c == 41 && !x--) return i;
      }
      return -1;
    },
    /* Emphasis closer scanner (* or **). */
    mdK = (t, i, e, b) => {
      let n = b ? 2 : 1, k = i + n + 1, r;
      if (i + n >= e || cc(t, i + n) == 32) return -2;
      for (; k + n <= e; k++)
        if (cc(t, k) == 42 && (!b || cc(t, k + 1) == 42)) {
          for (r = k; r + 1 < e && cc(t, r + 1) == 42;) r++;
          if ((b || r - k != 1) && cc(t, k - 1) != 32) return r - n + 1;
          k = r;
        }
      return -1;
    },
    /* Linear inline parser with failed-delimiter bitmask and failed-bracket watermark. */
    mdP = (d, q, t, j, e, u, x, l) => {
      if (j >= e) return;
      if (x >= q) { ap(u, tn(d, sl(t, j, e))); return; }
      let m = 0, v = -1, b = j, i = j, W = (k) => k > b && ap(u, tn(d, sl(t, b, k)));
      while (i < e) {
        let c = cc(t, i);
        if (c == 96 && !(m & 4)) {
          let k = ix(t, "`", i + 1);
          k < 0 || k >= e ? (m |= 4, i++) : k > i + 1 ? (W(i), elE(d, u, _c, sl(t, i + 1, k)), i = b = k + 1) : i += 2;
        } else if (c == 42) {
          let f = i + 1 < e && cc(t, i + 1) == 42, k = f ? 1 : 2, n = 1 + f, r;
          if (!(m & k) && (r = mdK(t, i, e, f)) >= 0) { W(i); mdP(d, q, t, i + n, r, elE(d, u, f ? "strong" : "em"), x + 1, l); i = b = r + n; }
          else { r == -1 && (m |= k); i += f && i + 2 < e && cc(t, i + 2) == 32 ? 2 : 1; }
        } else if (c == 91 && !l || c == 33 && i + 1 < e && cc(t, i + 1) == 91) {
          let f = c == 33, n = i + f, k, r, z;
          if (!(m & 8) && n >= v) {
            k = ix(t, "]", n + 1);
            if (k < 0 || k >= e) m |= 8;
            else if (k + 1 < e && cc(t, k + 1) == 40) {
              r = mdG(t, k + 2, e);
              if (r >= 0) {
                if (f) { i = r + 1; continue; }
                if (k > n + 1) {
                  z = su(sl(t, k + 2, r)); W(i);
                  if (z) mdP(d, q, t, n + 1, k, ap(u, mkA(d, z)), x + 1, true);
                  else ap(u, tn(d, sl(t, n + 1, k)));
                  i = b = r + 1; continue;
                }
              } else r == -1 ? (m |= 8) : (v = k);
            } else v = k;
          }
          i += 1 + f;
        } else i++;
      }
      W(e);
    },

    /* Linear O(n) safe Markdown renderer (15 tags, <= 256 KiB UTF-8, maxDepth <= 8). */
    md = (a, o = {}) => {
      let d = doc(), p = d.createDocumentFragment();
      if (a == N) return p;
      let g = o.maxBytes > 0 ? o.maxBytes : 262144,
        q = o.maxDepth >= 1 ? Math.min(o.maxDepth, 16) : 8,
        s = S(a), w = false,
        E = (u, t, x) => elE(d, u, t, x),
        F = (u, x) => ap(u, tn(d, x)),
        Q = (t, u, x) => mdP(d, q, t, 0, ln(t), u, x, false),
        X = (t) => { let m = RL.exec(t); return m && [m[3] ? "ol" : "ul", ln(m[1]), m[3] ? +m[3] : 1, m[4]]; },
        Y = (t, i, u, x) => {
          let f = X(t[i]), e = E(u, f[0]), c, k, b, r;
          f[0] == "ol" && f[2] != 1 && sa(e, "start", S(f[2]));
          while (i < ln(t) && (c = X(t[i])) && c[1] == f[1] && c[0] == f[0]) {
            k = E(e, "li"); Q(c[3], k, x); b = [];
            while (++i < ln(t) && (r = X(t[i])) && r[1] > f[1]) b.push(t[i]);
            if (x + 1 < q) for (let j = 0; j < ln(b);) j = Y(b, j, k, x + 1);
            else b.map((y) => (E(k, "br"), F(k, y)));
          }
          return i;
        },
        Z = (t, u, x) => {
          for (let i = 0; i < ln(t);) {
            let c = t[i], m, b, e, k, r, j;
            if (RB.test(c)) i++;
            else if ((m = RF.exec(c))) {
              for (b = [], k = ln(m[1]), i++; i < ln(t); i++) {
                if ((j = RC.exec(t[i])) && ln(j[1]) >= k) { i++; break; }
                b.push(t[i]);
              }
              e = E(E(u, "pre"), _c, b.join(_n));
              RG.test(r = m[2].trim()) && sa(e, "data-lang", r);
            } else if ((m = RH.exec(c))) { Q(m[2], E(u, "h" + ln(m[1])), x); i++; }
            else if (RR.test(c)) { E(u, _h); i++; }
            else if (c[0] == ">") {
              for (b = []; i < ln(t) && t[i][0] == ">";) { r = t[i++]; b.push(sl(r, r[1] == " " ? 2 : 1)); }
              x >= q ? (e = E(u, _p), b.map((y, n) => (n && E(e, _b), F(e, y)))) : Z(b, E(u, "blockquote"), x + 1);
            } else if (RL.test(c)) i = Y(t, i, u, x);
            else for (e = E(u, _p), j = 0; i < ln(t) && !RP.test(t[i]); j++, i++) { j && E(e, _b); Q(t[i], e, x); }
          }
        };
      if (ln(s) * 3 > g)
        for (let b = 0, i = 0; i < ln(s);) {
          let c = cc(s, i), r = (c & 64512) == 55296 && (cc(s, i + 1) & 64512) == 56320;
          if ((b += c < 128 ? 1 : c < 2048 ? 2 : r ? 4 : 3) > g) { s = sl(s, 0, i); w = true; break; }
          i += 1 + r;
        }
      s && Z(s.split(/\r?\n/), p, 0);
      w && (E(p, _p, "Preview truncated at " + Math.max(1, g / 1024 + .5 | 0) + " KiB; full text preserved.").className = (isS(o.classPrefix) ? o.classPrefix : "md-") + "trunc");
      return p;
    },

    mb = [],
    markB = (b, k) => R && ((R[b] = isO(R[b]) ? R[b] : Object.create(N))[k] = true),

    ba = (i, f, v = "click", o = {}) => {
      let e = byId(i);
      if (!e) { mb.push(i); o.strict !== false && fail("missing_id:" + i); return () => {}; }
      markB("__blindui_bound_ids", i);
      let l = o.lock !== false, b = false,
        z = () => { b = false; l && e.removeAttribute?.("aria-busy"); },
        g = (x) => {
          if (l && b) return;
          b = true; l && sa(e, "aria-busy", "true");
          let r;
          try { r = f.call(e, x); } catch (k) { z(); throw k; }
          return r && isF(r.then) ? r.then((u) => (z(), u), (k) => { z(); throw k; }) : (z(), r);
        };
      on(e, v, g);
      return () => e.removeEventListener(v, g);
    },

    ms = [],
    ct = Object.create(N),
    eb = N,
    sg = N,
    np = (r) => r.split("?", 1)[0].replace(/^(?:\.\/|([^/]))/, "/$1"),
    spR = (r, m) => { let i = ix(r, " "); return i > 0 ? [sl(r, 0, i).toUpperCase(), sl(r, i + 1)] : [(m || "GET").toUpperCase(), r]; },

    cs = (v, s, p) => {
      if (!s) return N;
      let E = (x) => p + ":" + x, t = s.t, g = (n) => s.min != N && n < s.min ? E("min") : s.max != N && n > s.max ? E("max") : N, e;
      if (v == N) return s.req ? E("required") : N;
      e = t == "str" ? (!isS(v) ? E(t) : g(ln(v)))
        : t == "email" ? (!isS(v) || ln(v) > 254 || !MR.test(v) ? E(t) : N)
        : t == "int" || t == "num" ? (!Number.isFinite(v) || t == "int" && v % 1 ? E(t) : g(v))
        : t == "bool" ? (typeof v != "boolean" ? E(t) : N)
        : t == "arr" ? (!I(v) ? E(t) : g(ln(v)) || s.of && v.reduce((a, x, i) => a || cs(x, s.of, p + "[" + i + "]"), N))
        : t == "obj" ? (!isO(v) ? E(t) : ent(s.fields || {}).reduce((a, [k, f]) => a || cs(v[k], f, p + "." + k), N))
        : N;
      return e || (I(s.vals) && !s.vals.includes(v) ? E("enum") : N);
    },

    clr = (u) => { while (u.firstChild) rm(u, u.firstChild); },
    vis = (u, k) => u && (sa(u, "aria-hidden", S(!k)), u.style && (u.style.display = k ? "" : "none")),
    pd = (e) => e.preventDefault?.(),
    keyFmt = (e) => (e.ctrlKey || e.metaKey) && !e.altKey && { b: "bold", i: "italic", k: "link" }[lc(e.key || "")],

    fmtMd = (v, i, j, k) => {
      k = k == "list" ? "ul" : k == "quote" ? "bq" : k;
      let x = sl(v, i, j), u, b, e, p = BK[k], y;
      if (p) {
        u = (x || { h1: "Heading", h2: "Section", h3: "Subsection" }[k] || "Item").split(_n).map((l) => p + l).join(_n);
        return [u, i + ln(p), i + ln(u)];
      }
      y = {
        bold: ["**", "bold text"],
        italic: ["*", "italic text"],
        code: x.includes(_n) ? ["```\n", "", "\n```"] : ["`", _c],
        codeblock: ["```\n", "", "\n```"],
        link: ["[", "link text", "](https://)"],
        hr: ["\n---\n", "", ""]
      }[k];
      if (!y) return N;
      x = k == _h ? "" : x || y[1];
      u = y[0] + x + (y[2] ?? y[0]);
      b = i + ln(y[0]); e = b + ln(x);
      k == "link" && (b = e + 2, e = b + 8);
      return [u, b, e];
    },

    sel = (t) => { let v = t.value || "", n = ln(v); return [v, t.selectionStart ?? n, t.selectionEnd ?? n]; },
    mkB = (q, k = _p, m = "", v = "", g = _n + _n, r = N) => ({ k: k, m: m, v: v, g: g, r: r, q: q }),

    fmtTa = (a, k) => {
      if (!a) return false;
      let [v, i, j] = sel(a), r = fmtMd(v, i, j, k);
      if (!r) return false;
      a.setRangeText ? a.setRangeText(r[0], i, j, "end") : (a.value = sl(v, 0, i) + r[0] + sl(v, j));
      a.setSelectionRange?.(r[1], r[2]); a.focus?.();
      return true;
    },

    /* Lossless block parser & serializer for BlindUI.notionEditor (bit-exact roundtrip). */
    parseN = (s) => {
      let L = s.split(/(\r?\n)/), b = [], g = "", i = 0, c, e, m, f, r, p, a, q,
        P = (k, m, v, r, q) => (b.push(mkB(q, k, m, v, g, r)), g = p),
        W = (fn, x) => {
          for (r = c, a = x ? [] : [x === 0 ? sl(c, c[1] == " " ? 2 : 1) : c]; i < ln(L) && fn(c = L[i]);) {
            r += p + c; p = L[i + 1] || ""; i += 2;
            if (x && (m = RC.exec(c)) && ln(m[1]) >= f) break;
            a.push(x === 0 ? sl(c, c[1] == " " ? 2 : 1) : c);
          }
          return a.join(_n);
        };
      ln(L) > 1 && !L[ln(L) - 1] && L.pop();
      for (; i < ln(L);) {
        c = L[i]; p = e = L[i + 1] || ""; i += 2;
        RB.test(c) ? (g += c + e)
        : (m = RF.exec(c)) ? (f = ln(m[1]), q = m[2].trim(), P(_c, RG.test(q) ? q : "", W(() => 1, 1), r))
        : (m = RH.exec(c)) ? P("h" + ln(m[1]), m[1] + " ", m[2], c)
        : RR.test(c) ? P(_h, _d, "", c)
        : c[0] == ">" ? P(_q, "> ", W((z) => z[0] == ">", 0), r)
        : (m = RL.exec(c)) ? P(m[3] ? _o : _u, m[1] + (m[3] ? m[3] + ". " : m[2] + " "), m[4], c)
        : P(_p, "", W((z) => !RP.test(z)), r);
      }
      !ln(b) ? b.push(mkB(0, _p, "", "", "", "")) : b[ln(b) - 1].k == _h && b.push(mkB(1));
      return [b, g];
    },

    serN = (b) => {
      if (b.r != N) return b.r;
      let k = b.k, v = b.v, f = "```";
      if (k == _c) { while (v.includes(f)) f += "`"; return f + (b.m || "") + _n + v + _n + f; }
      return k == _h ? b.m || _d : k == "bq" ? v.split(_n).map((l) => "> " + l).join(_n) : (k == _p ? "" : b.m) + v;
    },

    isIn = (p, n) => { for (; n; n = n.parentNode) if (n == p) return 1; },
    hasAnc = (r, n, t) => { for (; n && n != r; n = n.parentNode) if (nt(n) == 1 && tg(n) == t) return n; },
    txtOf = (n) => nt(n) == 3 ? tx(n) : ch(n).reduce((a, c) => a + txtOf(c), ""),
    lastTx = (n) => !n ? N : nt(n) == 3 ? n : ch(n).reduceRight((r, c) => r || lastTx(c), N),
    lastIdx = (k, t) => { let i = ln(k) - 1; if (t) while (i >= 0 && nt(k[i]) == 3 && !sTx(k[i])) i--; return i; },
    cleanZ = (u) => { for (let n of ch(u)) nt(n) == 3 ? (tx(n) == zws ? rm(u, n) : ix(tx(n), zws) >= 0 && setTx(n, sTx(n))) : cleanZ(n); },
    fillSeg = (u, s, q) => {
      let d = doc(), L = s.split(_n), i = 0;
      for (; i < ln(L); i++) { i && ap(u, ce(d, _b)); L[i] && mdP(d, q, L[i], 0, ln(L[i]), u, 0, false); }
    },
    fillEd = (u, v, q) => { clr(u); fillSeg(u, v, q); v && cc(v, ln(v) - 1) == 10 && ap(u, ce(doc(), _b)); },
    tagW = (c) => {
      let t = tg(c), h, m = { strong: "**", b: "**", em: "*", i: "*", code: "`" }[t], s;
      if (m) return (s = t == _c ? normS(txtOf(c)) : serDom(c, 0)) ? [m, m, s] : ["", "", ""];
      return t == "a" ? ((s = serDom(c, 0)) && (h = su(c.getAttribute?.("href") || "")) ? ["[", "](" + h + ")", s] : ["", "", s]) : N;
    },
    serDom = (u, t = 1) => {
      let k = ch(u), n = ln(k), o = "", i = 0, l = lastIdx(k, t);
      for (; i < n; i++) {
        let c = k[i], y = nt(c);
        if (y == 3) o += sTx(c);
        else if (y == 1) {
          let a = tg(c), w = tagW(c);
          if (a == _b) { if (!t || i < l) o += _n; }
          else if (w) o += w[0] + w[2] + w[1];
          else { let s = serDom(c, 0); if ((a == "div" || a == _p) && o) o += _n; o += s; }
        }
      }
      return o;
    },
    domMap = (u, x, y) => {
      let a = 0, r = N, f = isN(x), w = (p, t) => {
        let k = ch(p), n = ln(k), l = lastIdx(k, t), i = 0;
        for (; i < n && !r; i++) {
          if (!f && p == x && i == y) { r = 1; return; }
          let c = k[i], z = nt(c);
          if (z == 3) {
            let s = tx(c), m = ln(stripZ(s));
            if (!f) {
              if (c == x) { a += ln(stripZ(sl(s, 0, y))); r = 1; return; }
            } else if (x <= a + m) {
              if (s == zws) { r = [c, 1]; return; }
              let j = 0, v = 0;
              for (; j < ln(s) && v < x - a; j++) s[j] != zws && v++;
              r = [c, j]; return;
            }
            a += m;
          } else if (z == 1) {
            if (tg(c) == _b) {
              if (f && x <= a) { r = [p, i]; return; }
              if (!t || i < l) a++;
              if (f && x <= a) { r = [p, i + 1]; return; }
            } else {
              let v = tagW(c) || ["", "", f ? serDom(c, 0) : ""], o = ln(v[0]), m = ln(v[2]);
              if (f && x < a + o) { r = [p, i]; return; }
              a += o;
              if (!f) { w(c, 0); r || (a += ln(v[1])); }
              else if (x <= a + m) { w(c, 0); r || (r = [c, ln(ch(c))]); return; }
              else if (x <= (a += m + ln(v[1]))) { let q = k[i + 1]; r = q && nt(q) == 3 ? [q, tx(q) == zws ? 1 : 0] : [p, i + 1]; return; }
            }
          }
        }
        if (!f && !r && p == x && y >= n) r = 1;
      };
      w(u, 1);
      if (!f) return a;
      if (r) return r;
      let k = ch(u), n = ln(k), l = k[n - 1];
      return !n || n == 1 && nt(l) == 1 && tg(l) == _b ? [u, 0] : nt(l) == 3 ? [l, ln(tx(l))] : [u, n];
    },
    matchEnd = (u, n, s) => {
      if (!s || hasAnc(u, n, _c)) return N;
      let c = cc(s, ln(s) - 1), m, k, d = 0, p = -1, b = -1;
      if (c == 42) {
        if (!hasAnc(u, n, _st) && (m = /\*\*([^\s*\n](?:[^*\n]*[^\s*\n])?)\*\*$/.exec(s))) return [m.index, _st, m[1]];
        if (!hasAnc(u, n, "em") && (m = /(^|[^*])\*([^\s*\n](?:[^*\n]*[^\s*\n])?)\*$/.exec(s))) return [m.index + ln(m[1]), "em", m[2]];
      } else if (c == 96) {
        if ((m = /`([^`\n]+)`$/.exec(s))) return [m.index, _c, m[1]];
      } else if (c == 41 && !hasAnc(u, n, "a")) {
        for (k = ln(s) - 1; k >= 0; k--) {
          let x = cc(s, k);
          if (x == 41) { if (++d > 5) return N; }
          else if (x == 40 && !--d) { p = k; break; }
        }
        if (p < 3 || cc(s, p - 1) != 93) return N;
        for (k = p - 2; k >= 0; k--) {
          let x = cc(s, k);
          if (x == 93 || x == 10) return N;
          if (x == 91) { b = k; break; }
        }
        if (b < 0 || b > 0 && cc(s, b - 1) == 33) return N;
        let l = sl(s, b + 1, p - 1), h = su(sl(s, p + 1, ln(s) - 1));
        if (l && h) return [b, "a", l, h];
      }
      return N;
    },
    setRng = (s, a, b, c, e) => {
      let r = doc()?.createRange?.();
      if (s && r) { r.setStart(a, b); r.setEnd(c, e); s.removeAllRanges(); s.addRange(r); }
    },
    liveComp = (u, q) => {
      let d = doc(), [s, r] = getR(),
        sp = (n, h, a) => {
          let p = n.parentNode, e = h[1] == "a" ? mkA(d, h[3]) : ce(d, h[1]);
          h[1] == "a" ? mdP(d, q, h[2], 0, ln(h[2]), e, 1, true) : ap(e, tn(d, h[2]));
          a && ins(p, tn(d, a), n);
          ins(p, e, n);
          return p;
        };
      if (r && isIn(u, r.startContainer)) {
        if (!r.collapsed) return 0;
        let n = r.startContainer, o = r.startOffset;
        if (nt(n) == 1 && o > 0 && nt(ch(n)[o - 1]) == 3) { n = ch(n)[o - 1]; o = ln(tx(n)); }
        if (nt(n) != 3) return 0;
        let a = tx(n);
        if (a != zws && ix(a, zws) >= 0) {
          let k = ln(sl(a, 0, o)) - ln(stripZ(sl(a, 0, o)));
          a = stripZ(a); setTx(n, a); o = o > k ? o - k : 0; setRng(s, n, o, n, o);
        }
        let a0 = a.replace(/\u00a0(?!$)/g, " ");
        if (a0 != a) { a = a0; setTx(n, a); setRng(s, n, o, n, o); }
        let b = sl(a, 0, o), e = sl(a, o), h = matchEnd(u, n, b);
        if (!h) return 0;
        let p = sp(n, h, sl(b, 0, h[0])), t = tn(d, e || zws);
        ins(p, t, n); rm(p, n);
        setRng(s, t, e ? 0 : 1, t, e ? 0 : 1);
        return 1;
      }
      if (s) return 0;
      let f = 0, w = (x) => {
        for (let n of ch(x)) {
          if (nt(n) == 1) { tg(n) != _c && w(n); continue; }
          if (nt(n) != 3) continue;
          let a = sTx(n), c = n;
          for (let k = 1; k <= ln(a); k++) {
            let y = cc(a, k - 1), h;
            if ((y == 42 || y == 96 || y == 41) && (h = matchEnd(u, c, sl(a, 0, k)))) {
              let e = sl(a, k), p = sp(c, h, sl(a, 0, h[0]));
              f = 1;
              if (e) { let t = tn(d, e); ins(p, t, c); rm(p, c); c = t; a = e; k = 0; }
              else { rm(p, c); break; }
            }
          }
        }
      };
      w(u); return f;
    },

    BUI = {
      version: "1.0.0",

      h: (a, b, ...c) => {
        (!isS(a) || !H.has(a)) && failD("tag:" + a);
        let d = doc(), e = d.createElement(a), f = a == "iframe", g = "prop:", E = (u) => /^blob:/i.test(u);
        f && !E(su(b?.src, N, 0, 1)) && failD("iframe_src");
        if (b != N) {
          !isO(b) && fail("invalid_props");
          for (let [k, v] of ent(b)) {
            if (/^on[a-z]+$/.test(k)) { !isF(v) && failD(g + k); on(e, sl(k, 2), v); }
            else if (B.has(k)) e[k] = !!v;
            else if (k == "className" || k == "textContent") v != N && (e[k] = S(v));
            else if (k == "style") v != N && setSt(e, v, g);
            else if (k == "dataset") {
              if (v != N) {
                !isO(v) && failD(g + k);
                for (let [x, y] of ent(v)) y != N && (e.dataset ? (e.dataset[x] = S(y)) : sa(e, lc("data-" + x.replace(/[A-Z]/g, "-$&")), S(y)));
              }
            } else if (U.has(k)) {
              if (v != N) {
                let u = su(v, N, !f, b.download || f);
                (!u || f && !E(u)) && failD("url:" + k);
                sa(e, lc(k), u);
              }
            } else if (A.has(k)) {
              if (v != N) {
                D.has(k) && (e[k] = M.has(k) ? +v : S(v));
                k != "value" && sa(e, lc(k), S(v));
              }
            } else if (/^(?:aria|data)-[a-z\d-]+$/.test(k)) v != N && sa(e, k, S(v));
            else failD(g + k);
          }
        }
        return addCh(d, e, c);
      },

      svg: (a, b, ...c) => {
        (!isS(a) || !V.has(a)) && failD("svg_tag:" + a);
        let d = doc(), e = d.createElementNS("http://www.w3.org/2000/svg", a), g = "svg_attr:";
        if (b != N) {
          !isO(b) && failD("svg_attr");
          for (let [k, v] of ent(b)) {
            (!/^[a-z][\w-]*$/i.test(k) || /^on|href/i.test(k)) && failD(g + k);
            k == "style" ? (v != N && setSt(e, v, g)) : v != N && sa(e, k == "className" ? "class" : k, S(v));
          }
        }
        return addCh(d, e, c);
      },

      sanitizeUrl: su,
      md: md,

      bindMdEditor: (c) => {
        let d = doc(), a = byId(c.textareaId, d), p = byId(c.previewId, d),
          g = c.stageEl || c.stageId && byId(c.stageId, d), t = c.modeTabIds || {},
          w = ["write", "split", "preview"], m = c.initialMode || w[0], r = false,
          E = () => { if (!a || !p) return; clr(p); ap(p, md(a.value, c.mdOpts)); },
          F = () => {
            if (m == w[0] || r) return;
            r = true;
            let u = () => { r = false; E(); };
            R?.requestAnimationFrame ? R.requestAnimationFrame(u) : u();
          },
          G = (k) => { fmtTa(a, k) && (F(), c.onDirty?.()); },
          K = (k) => {
            if (!w.includes(k)) return;
            m = k; sa(g, "data-md-mode", k);
            for (let u of w) { let e = t[u] && byId(t[u], d), q = u == k; e && (sa(e, "aria-selected", S(q)), e.classList?.toggle("active", q)); }
            k != w[0] && E();
            c.onModeChange?.(k);
          },
          L = (o, f) => o && ent(o).map(([k, i]) => i && ba(i, () => f(k), "click", { lock: false }));
        on(a, "input", () => { F(); c.onDirty?.(); });
        on(a, "keydown", (e) => { let k = keyFmt(e); k && (pd(e), G(k)); });
        on(a, "scroll", () => {
          if (m != w[1] || !p) return;
          let x = a.scrollHeight - a.clientHeight, y = p.scrollHeight - p.clientHeight;
          x > 0 && y > 0 && (p.scrollTop = a.scrollTop / x * y + .5 | 0);
        });
        L(c.toolbarMap, G); L(t, K); K(m);
        return { setMode: K, renderPreview: E, applyFormat: G, getMode: () => m };
      },

      notionEditor: (c, o = {}) => {
        c = isS(c) ? byId(c) : c;
        (!isO(c) || !isN(nt(c))) && fail("missing_container");
        let a = o.textarea || o.textareaId && byId(o.textareaId) || N, u = N,
          p = isS(o.placeholder) ? o.placeholder : "", r = !!o.readOnly, w = o.mdOpts,
          X = w?.maxDepth >= 1 ? Math.min(w.maxDepth, 16) : 8,
          f = isF(o.onChange) ? [o.onChange] : [],
          B = [], g = "", W = [], A = -1, V = N, L = 0, Q = [0, 0], q = false, S0 = N, C0 = false, h = BUI.h,
          T = () => a || u,
          M = (x) => sa(c, "data-bui-mode", x),
          K = (x, j = ln(B) - 1, i = 0) => x < i ? i : x > j ? j : x,
          U = (b, k, m, v) => { b.k = k; b.m = m; v != N && (b.v = v); b.r = N; b.q = 0; },
          O = (t) => { let s = t?.style; s && (s.height = "auto", t.scrollHeight > 0 && (s.height = t.scrollHeight + "px")); },
          G = () => q ? T()?.value || "" : B.reduce((s, b) => b.q ? s : s + b.g + serN(b), "") + g,
          E = () => {
            ln(B) == 1 && B[0].k == _p && !B[0].v && B[0].r == N && (g = "");
            let s = G();
            a && !q && (a.value = s);
            [...f].map((x) => x(s));
          },
          H0 = () => {
            let e = p && ln(B) == 1 && B[0].k == _p && !B[0].v && !B[0].q ? W[0]?._ed : N;
            if (S0 && S0 != e) { S0.removeAttribute?.(_dp); cl(S0, _ne, 0); S0 = N; }
            if (e) { sa(e, _dp, p); cl(e, _ne, 1); S0 = e; }
          },
          inS = (e) => { let [s, z] = getR(); return z ? isIn(e, z.startContainer) : !s && V == e && isN(e.selectionStart); },
          gS = (e, b) => {
            if (!e) return [0, 0];
            if (b.k == _c) { let [, x, y] = sel(e); return [x, y]; }
            let [s, z] = getR(), n = ln(b.v), a = z?.startContainer, d = z?.endContainer;
            if (z && isIn(e, a) && isIn(e, d)) {
              let x = domMap(e, a, z.startOffset), y = z.collapsed ? x : domMap(e, d, z.endOffset);
              return x <= y ? [x, y] : [y, x];
            }
            if (!s && isN(e.selectionStart) && isN(e.selectionEnd)) return [K(e.selectionStart, n), K(e.selectionEnd, n)];
            return [K(Q[0], n), K(Q[1], n)];
          },
          sS = (e, x, y) => {
            let s = R?.getSelection?.();
            if (s && doc()?.createRange) {
              let [a, b] = domMap(e, x), [d, m] = x == y ? [a, b] : domMap(e, y);
              setRng(s, a, b, d, m);
            } else { e.selectionStart = x; e.selectionEnd = y; }
          },
          nav = (i, e, t, k, v, x, y) =>
            k == "Escape" ? (pd(e), t.blur?.(), 1) :
            k == "ArrowUp" && i && !sl(v, 0, x).includes(_n) ? (pd(e), Y(i - 1), 1) :
            k == "ArrowDown" && i < ln(B) - 1 && ix(v, _n, y) < 0 && (pd(e), Y(i + 1, 0), 1),
          C = (t) => {
            on(t, "input", () => q && E());
            on(t, "keydown", (e) => { let k = q && keyFmt(e); k && (pd(e), F(k)); });
          },
          J = (b, x) => (e) => { let i = ix(B, b); i >= 0 && x(i, e); },
          mkW = (b) => {
            let z = h("div");
            on(z, "click", (e) => {
              let i = ix(W, z), t = z._ed;
              if (!r && !q && i >= 0 && t && e?.target != t && !isIn(t, e?.target)) Y(i);
            });
            P(z, b); return z;
          },
          I = (i, b, x) => {
            let z = mkW(b);
            B.splice(i, 0, b); W.splice(i, 0, z);
            c.insertBefore ? ins(c, z, W[i + 1] || N) : (clr(c), W.map((y) => ap(c, y)));
            H0(); x && Y(i, 0, 0, 1);
          },
          D = (i) => {
            B.splice(i, 1);
            let z = W.splice(i, 1)[0];
            z?.parentNode == c && rm(c, z);
            H0();
          },
          Z = () => { S0 = N; clr(c); W = B.map((b) => ap(c, mkW(b))); H0(); },
          R0 = (i, m) => {
            let b = B[i];
            U(b, _p, "");
            i && b.g == _n && (b.g += _n);
            m && (b.q = 1);
            P(W[i], b); H0(); Y(i, 0, 0, 1);
          },
          Y = (i, x, y, e) => {
            if (r || q || !ln(B)) return;
            i = K(i);
            let b = B[i], t = W[i]?._ed;
            if (!t) return;
            A = L = i; V = t;
            if (b.k == _h) { Q = [0, 0]; t.focus?.(); }
            else {
              let n = ln(b.k == _c ? t.value : b.v);
              x = x == N ? n : K(x, n); y = y == N ? x : K(y, n, x);
              Q = [x, y]; t.focus?.();
              b.k == _c ? (t.setSelectionRange?.(x, y), O(t)) : sS(t, x, y);
            }
            e && E();
          },
          P = (z, b) => {
            clr(z);
            let k = b.k, t, m,
              onF = J(b, (i) => { A = L = i; V = t; cl(z, _nf, 1); k == _h ? (Q = [0, 0]) : k == _c && O(t); }),
              onB = J(b, (i) => {
                L = i;
                if (k == _c) { let [, x, y] = sel(t); Q = [x, y]; }
                else if (k != _h && inS(t)) Q = gS(t, b);
                A == i && (A = -1, V = N);
                cl(z, _nf, 0);
                if (k != _h && k != _c) cleanZ(t);
              });
            z.className = _nb + " " + _nb + "-" + k + " md-prose";
            sa(z, "data-block-type", k);
            if (k == _h) {
              t = h(_h, r ? N : {
                tabIndex: 0, onfocus: onF, onblur: onB,
                onkeydown: J(b, (i, e) => {
                  let y = e.key || "";
                  if (nav(i, e, t, y, "", 0, 0)) return;
                  if (y == "Enter") return pd(e), i < ln(B) - 1 ? Y(i + 1, 0) : I(i + 1, mkB(1), 1);
                  if (y == "Backspace" || y == "Delete") {
                    pd(e); D(i);
                    !ln(B) && I(0, mkB(0, _p, "", "", "", ""));
                    !i && B[0] && (B[0].g = "");
                    H0(); Y(K(i - 1), N, N, 1);
                  }
                })
              });
              ap(z, t); return z._ed = t;
            }
            if (k == _c) {
              if (r) {
                let e = h(_c, N, b.v);
                b.m && sa(e, "data-lang", b.m);
                ap(z, h("pre", N, e)); return z._ed = N;
              }
              let sv = J(b, (i) => { let [, x, y] = sel(t); L = i; Q = [x, y]; });
              t = h("textarea", {
                className: _nb + "-inp", rows: 1, spellcheck: false, value: b.v,
                onfocus: onF, onblur: onB, onkeyup: sv, onmouseup: sv,
                oninput: J(b, (i) => { let [v, x, y] = sel(t); L = i; Q = [x, y]; b.v = v; b.r = N; v && (b.q = 0); O(t); E(); }),
                onkeydown: J(b, (i, e) => {
                  let y = e.key || "", [v, x, j] = sel(t);
                  L = i; Q = [x, j];
                  if (nav(i, e, t, y, v, x, j)) return;
                  if (y == "Enter") return (e.ctrlKey || e.metaKey) && (pd(e), I(i + 1, mkB(i == ln(B) - 1), 1));
                  if (y == "Backspace" && !x && !j) return pd(e), R0(i);
                })
              });
              ap(z, h("span", { className: _nb + "-mark", "aria-hidden": "true" }, b.m || _c));
              ap(z, t); O(t); return z._ed = t;
            }
            let tg0 = isL(k) ? "li" : k == _q ? _p : k,
              sv = (i) => { L = i; inS(t) && (Q = gS(t, b)); },
              inp = (i) => {
                if (C0) return;
                let v = serDom(t), e, j;
                if (!v && ln(ch(t))) { clr(t); sS(t, 0, 0); }
                if (b.k == _p) {
                  if (v == _d) { U(b, _h, _d, ""); P(W[i], b); return I(i + 1, mkB(i == ln(B) - 1), 1); }
                  if ((e = /^(?:(#{1,3}|[-*]|\d{1,3}\.|>) |```(?:$|([\w-]{0,24})[ \n]))([\s\S]*)$/.exec(v))) {
                    let [x, y] = gS(t, b), d0;
                    j = e[1];
                    U(b, !j ? _c : j[0] == "#" ? "h" + ln(j) : j == ">" ? _q : ln(j) > 1 ? _o : _u, j ? j + " " : e[2] || "", e[3]);
                    d0 = ln(v) - ln(e[3]);
                    P(W[i], b); H0(); return Y(i, x - d0, y - d0, 1);
                  }
                }
                liveComp(t, X);
                v = serDom(t);
                b.v = v; b.r = N; v && (b.q = 0);
                H0(); sv(i); E();
              };
            t = h(tg0, r ? { className: _nb + "-ed" } : {
              className: _nb + "-ed",
              oncompositionstart: () => { C0 = true; },
              oncompositionend: J(b, (i) => { C0 = false; inp(i); }),
              onfocus: onF, onblur: onB, onkeyup: J(b, sv), onmouseup: J(b, sv), oninput: J(b, inp),
              onkeydown: J(b, (i, e) => {
                let y = e.key || "", j = keyFmt(e), m = b.k, n = ln(B) - 1, v = b.v, [x, s] = gS(t, b);
                L = i; Q = [x, s];
                if (j) return pd(e), F(j);
                if (nav(i, e, t, y, v, x, s)) return;
                if (y == "Enter") {
                  if (e.shiftKey || e.ctrlKey || e.metaKey) return;
                  pd(e);
                  if (isL(m) && !v) return R0(i, i == n);
                  let a = sl(v, 0, x), d = sl(v, s), l = isL(m) ? m : _p,
                    o = m == _u ? b.m : m == _o ? b.m.replace(/\d+/, (q) => Math.min(999, +q + 1)) : "";
                  b.v = a; b.r = N; (a || d) && (b.q = 0);
                  fillEd(t, a, X);
                  return I(i + 1, mkB(l == _p && !d && i == n, l, o, d, l == _p ? _n + _n : _n), 1);
                }
                if (y == "Backspace") {
                  let [q, r] = getR(), c = r?.startContainer;
                  if (r && q.isCollapsed && nt(c) == 3 && tx(c) == zws && r.startOffset == 1 && isIn(t, c)) {
                    let p = c.parentNode, k = ch(p), o = ix(k, c), v = o > 0 ? k[o - 1] : N;
                    if (v) {
                      let l = lastTx(v);
                      rm(p, c);
                      if (l) { setRng(q, l, ln(tx(l)), l, ln(tx(l))); return; }
                    }
                  }
                  if (!x && !s) {
                    if (m != _p) return pd(e), R0(i);
                    if (i) {
                      pd(e); let v = B[i - 1];
                      if (v.k == _h) return D(i - 1), i == 1 && (b.g = ""), b.q && ln(B) == 1 && U(b, _p, ""), H0(), Y(i - 1, 0, 0, 1);
                      let o = ln(v.v); U(v, v.k, v.m, v.v + b.v); D(i); P(W[i - 1], v); H0(); return Y(i - 1, o, o, 1);
                    }
                  }
                }
              }),
              onpaste: J(b, (i, e) => {
                pd(e);
                let x = e?.clipboardData?.getData?.("text/plain");
                if (!isS(x)) return;
                x = x.replace(/\r\n/g, _n);
                let [a, d] = gS(t, b), v = b.v;
                if (!x.includes(_n)) {
                  let s = sl(v, 0, a) + x + sl(v, d), o = a + ln(x);
                  b.v = s; b.r = N; s && (b.q = 0);
                  fillEd(t, s, X);
                  b.v = serDom(t); H0();
                  o = Math.min(o, ln(b.v));
                  return Y(i, o, o, 1);
                }
                let m = parseN(serN({ k: b.k, m: b.m, v: sl(v, 0, a) }) + x + sl(v, d))[0].filter((n) => !n.q);
                if (!ln(m)) return;
                m[0].g = b.g; m.map((n) => (n.r = N));
                B.splice(i, 1, ...m); A = -1; V = N; Z();
                let o = i + ln(m) - 1;
                o == ln(B) - 1 && B[o].k == _h && (I(ln(B), mkB(1)), o++);
                Y(o, N, N, 1);
              })
            });
            !r && sa(t, "contenteditable", "true");
            fillEd(t, b.v, X);
            if (isL(k)) {
              let l = h(k, N, t);
              k == _o && (m = /(\d+)/.exec(b.m)) && +m[1] != 1 && sa(l, "start", m[1]);
              ap(z, l);
            } else ap(z, k == _q ? h("blockquote", N, t) : t);
            return z._ed = t;
          },
          F = (k) => {
            if (r) return;
            if (q) return fmtTa(T(), k) && E();
            let i = A >= 0 ? A : K(L), b = B[i], t = W[i]?._ed,
              v = b.k == _h ? b.m || _d : b.v, n = ln(v),
              [x, y] = A >= 0 && t && inS(t) ? gS(t, b) : Q,
              s = k == "list" ? _u : k == "quote" ? _q : k, m = BK[s], j, e;
            x = K(x ?? n, n); y = K(y ?? n, n, x);
            if (k == _h) return b.k == _p && !b.v ? (U(b, _h, _d, ""), P(W[i], b), H0()) : I(++i, mkB(0, _h, _d)), I(i + 1, mkB(1), 1);
            if (m || k == "codeblock" || k == _c && sl(v, x, y).includes(_n))
              return j = m ? s : _c, e = b.k == j && k != _c, U(b, e ? _p : j, e ? "" : m || ""), P(W[i], b), H0(), Y(i, x, y, 1);
            if ((j = fmtMd(v, x, y, k))) {
              let o = b.k == _h, a = sl(v, 0, x), d = sl(v, y);
              U(b, o ? _p : b.k, o ? "" : b.m, a + j[0] + d);
              if (o) t = P(W[i], b);
              if (b.k == _c) t.value = b.v;
              else if (k == "link") { clr(t); a && fillSeg(t, a, X); ap(t, tn(doc(), j[0])); d && fillSeg(t, d, X); }
              else fillEd(t, b.v, X);
              H0(); Y(i, j[1], j[2], 1);
            }
          },
          d = (s, x) => {
            let t = s == N ? "" : S(s), [b, y] = parseN(t);
            B = b; g = y; A = -1; V = N; L = 0; Q = [0, 0];
            q ? T() && (T().value = t) : (Z(), a && (a.value = t));
            x && E();
          };
        cl(c, "bui-notion", 1);
        M("notion");
        a && (vis(a, false), C(a));
        on(c, "click", (e) => {
          if (r || q || e?.target != c) return;
          let z = B[ln(B) - 1], w = W[ln(W) - 1], n = 0;
          if (e.clientY && isF(w?.getBoundingClientRect)) {
            let b = w.getBoundingClientRect(),
              h = Math.max(24, b.height > 0 && b.height <= 48 ? b.height : 28),
              d = e.clientY - b.bottom;
            if (d > h) {
              n = Math.round(d / (h + 3));
              n = n > 18 ? 18 : n;
            }
          }
          if (n > 0) {
            for (let i = 0; i < n; i++) I(ln(B), mkB(1), i == n - 1);
          } else {
            z && (z.k != _p || z.v) ? I(ln(B), mkB(1), 1) : Y(ln(B) - 1);
          }
        });
        d(o.value != N ? o.value : a ? a.value : "");
        return {
          getMarkdown: G,
          setMarkdown: d,
          focus: () => {
            if (q) return T()?.focus?.();
            if (r) return;
            if (A >= 0 && V) return V.focus?.();
            let i = K(L);
            B[i]?.k == _h && i + 1 < ln(B) && i++;
            Y(i);
          },
          clear: (x) => d("", x),
          onChange: (x) => !isF(x) ? () => {} : (f.push(x), () => { let j = ix(f, x); j >= 0 && f.splice(j, 1); }),
          applyFormat: F,
          setRawMode: (x) => {
            if ((x = !!x) == q) return q;
            let s = G(), t;
            M((q = x) ? "raw" : "notion");
            if (x) {
              A = -1; V = N; S0 = N;
              t = a || (u || (u = h("textarea", { className: _nb + "-inp bui-raw", placeholder: p, readOnly: r }), C(u), u));
              t.value = s;
              a ? (vis(c, false), vis(a, true)) : (clr(c), W = [], ap(c, t));
              t.focus?.();
            } else a && (vis(a, false), vis(c, true)), d(s);
            return q;
          },
          isRawMode: () => q,
          getBlocks: () => B.filter((b) => !b.q).map((b) => ({ type: b.k, meta: b.m, text: b.v, markdown: serN(b) }))
        };
      },

      modal: (i, o = {}) => {
        let d = doc(), e = byId(i, d), Q = "CLOSED", W = "EXPANDED", X = "MOBILE_SHEET", Y = "DOCKED";
        d && eb != d && (eb = d, on(d, "keydown", (x) => {
          let k = x.key == "Escape" && ms[ln(ms) - 1], u = k && k.getState();
          u == W ? k.dock() : u && u != "MINIMIZED" && u != Q && k.close(false);
        }));
        !e && fail("missing_id:" + i);
        let m = o.mode == "dock", b = o.mobileBreakpoint ?? 640, p = o.backdropId && byId(o.backdropId, d), s = Q, f = N,
          E = () => isN(R?.innerWidth) && R.innerWidth <= b,
          F = () => { let x = R?.visualViewport?.height; s == X && x > 0 && e.style?.setProperty?.("--cmp-vvh", (x + .5 | 0) + "px"); },
          G = () => { let j = ix(ms, c); j >= 0 && ms.splice(j, 1); },
          P = (x) => {
            let v = s, l = x == Q, u = x == W || x == "OPEN" && !m;
            s = x;
            sa(e, "data-modal-state", x); sa(e, "aria-modal", S(u || x == X)); vis(e, !l); vis(p, u);
            if (l) { G(); try { f?.focus?.(); } catch {} f = N; }
            else { v == Q && d.activeElement && (f = d.activeElement); G(); ms.push(c); x == X && F(); }
            v != x && o.onStateChange?.(x, v);
          },
          Z = (x) => m && P(E() ? X : x),
          c = {
            open: (r) => P(E() && m ? X : r || (m ? Y : "OPEN")),
            close: (r) => s == Q || (!r && o.onBeforeClose?.(false) === false ? false : (P(Q), true)),
            minimize: () => m && !E() && P("MINIMIZED"),
            expand: () => Z(W),
            dock: () => Z(Y),
            getState: () => s
          };
        on(p, "click", () => { let x = o.closeOnBackdrop; x !== false && (x == "shrink" && s == W ? c.dock() : c.close(false)); });
        on(R, "resize", () => s != Q && m && (E() ? s != X && P(X) : s == X && P(Y)));
        on(R?.visualViewport, "resize", F);
        P(Q); return c;
      },

      bindAction: ba,

      bindGroup: (s, f, v = "click") => {
        let d = doc(), g = (e) => { let m = e?.target?.closest?.(s); if (m) return f.call(m, e, m); };
        markB("__blindui_bound_selectors", s);
        on(d, v, g);
        return () => d?.removeEventListener?.(v, g);
      },

      defineRoutes: (m) => isO(m) && ent(m).map(([k, v]) => { let [a, b] = spR(k); ct[a + " " + np(b)] = v; }),

      setSigner: (f) => { sg = isF(f) ? f : N; },

      api: async (r, o = {}) => {
        let [m, u] = spR(S(r || ""), o.method), p = np(u), c = ct[m + " " + p], e,
          x = o.body, b = x != N, t = b ? (isS(x) ? x : JSON.stringify(x)) : "",
          F = Object.assign,
          E = (z, y, j = 0, v = N) => F({ ok: false, status: j, data: v, error: z }, y && { detail: y }),
          h = F({}, isO(o.headers) && o.headers), G = encodeURIComponent, a = c?.auth;
        if (c?.req && (e = cs(x, c.req, "body"))) return E("client_schema_error", e);
        b && !h["Content-Type"] && !h["content-type"] && (h["Content-Type"] = "application/json");
        isO(o.query) && (e = ent(o.query).flatMap(([k, v]) => v != N ? G(k) + "=" + G(S(v)) : []).join("&")) && (u += (u.includes("?") ? "&" : "?") + e);
        if (o.sign || a == "mailbox_sig" || a == "admin_sig") {
          if (!sg) return E("missing_signer");
          let k = await sg(m, p, t, a || "mailbox_sig");
          isO(k) && F(h, k);
        }
        let f = R?.fetch;
        if (!isF(f)) return E("fetch_unavailable");
        let g = await f(u, F({ method: m, headers: h }, b && m != "GET" && m != "HEAD" && { body: t }, o.signal && { signal: o.signal })),
          s = await g.text(), d = N;
        if (s) try { d = JSON.parse(s); } catch { d = s; }
        return g.ok
          ? (c?.res && (e = cs(d, c.res, "res")) ? E("response_schema_error", e, g.status, d) : { ok: true, status: g.status, data: d, error: N })
          : E(isO(d) && d.error ? S(d.error) : "http_" + g.status, N, g.status, d);
      },

      _missingBindings: mb
    };

  typeof module == "object" && module?.exports && (module.exports = BUI);
  R && (R.BlindUI = BUI);
})(typeof globalThis != "undefined" ? globalThis : this);
