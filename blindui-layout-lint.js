/* Maat Layout Linter v1.0.0 - Runtime DOM/SVG layout & overlap auditor (ES2020). */
((G) => {
  "use strict";

  let M = Math, P = parseFloat, S = String, F = Number.isFinite, A = Array.isArray,
    SN = "http://www.w3.org/2000/svg",
    SR = /^(?:svg|g|text|tspan|rect|circle|path|line|polygon|polyline|ellipse)$/,
    AR = /^(?:button|select|textarea)$/,
    RR = /^(?:button|tab|link|menuitem|checkbox|radio|switch)$/,
    HR = /^(?:hidden|clip)$/,
    KR = /^(?:auto|scroll)$/,
    OR = /^(?:auto|scroll|hidden|clip)$/,
    XR = /^(?:input|textarea|select|html|body)$/,
    R = ["FLEX-SHRINK-CLIP", "SIBLING-OVERLAP", "SVG-TEXT-OVERLAP", "TEXT-CLIPPED", "VIEWPORT-BLEED-X"].map((x) => "LINT-" + x),
    fn = (v) => typeof v == "function",
    rd = (v) => M.round((+v || 0) * 100) / 100,
    tg = (e) => S(e?.tagName || "").toLowerCase(),
    pe = (e) => e?.parentElement,
    pn = (e) => e && (e.parentElement || e.parentNode),
    tx = (e) => S(e.textContent || "").trim(),
    isSvg = (e) => !!e && (e.namespaceURI == SN || SR.test(tg(e))),
    at = (e, k) => {
      let v = e && (fn(e.getAttribute) ? e.getAttribute(k) : e[k]);
      return v == null ? "" : S(v);
    },
    cls = (e) => {
      let r = at(e, "class") || (typeof e?.className == "string" ? e.className : e?.className?.baseVal || "");
      return r ? S(r).trim().split(/\s+/).filter(Boolean) : [];
    },
    hasC = (e, c) => cls(e).includes(c),
    sel = (e) => {
      if (!e) return "(null)";
      let t = tg(e) || "el", c = cls(e);
      return e.id ? t + "#" + e.id : c.length ? t + "." + c.slice(0, 2).join(".") : t;
    },
    ovD = (a, b, ar, w) => sel(a) + " overlaps " + (w ? w + " " : "") + sel(b) + " (" + rd(ar) + " px^2)",
    box = (e) => {
      let r = fn(e?.getBoundingClientRect) && e.getBoundingClientRect();
      if (!r) return null;
      let x = F(r.left) ? r.left : +r.x || 0, y = F(r.top) ? r.top : +r.y || 0,
        w = F(r.width) ? r.width : M.max(0, (+r.right || 0) - x),
        h = F(r.height) ? r.height : M.max(0, (+r.bottom || 0) - y);
      return { x: x, y: y, w: w, h: h, r: x + w, b: y + h };
    },
    pub = (b) => b ? { x: rd(b.x), y: rd(b.y), w: rd(b.w), h: rd(b.h) } : null,
    ovA = (a, b) => {
      if (!a || !b) return 0;
      let w = M.min(a.r, b.r) - M.max(a.x, b.x), h = M.min(a.b, b.b) - M.max(a.y, b.y);
      return w > 0 && h > 0 ? w * h : 0;
    },
    clipB = (a, c) => {
      if (!a || !c) return a;
      let x = M.max(a.x, c.x), y = M.max(a.y, c.y), r = M.min(a.r, c.r), b = M.min(a.b, c.b);
      return { x: x, y: y, w: M.max(0, r - x), h: M.max(0, b - y), r: M.max(x, r), b: M.max(y, b) };
    },
    hid = (s) => !s || s.display == "none" || /^(?:hidden|collapse)$/.test(s.visibility) || (s.opacity !== "" && s.opacity != null && P(s.opacity) === 0),
    vis = (s, b) => !hid(s) && !!b && b.w > 0.5 && b.h > 0.5,
    ov = (s, k) => s["overflow" + k] || s.overflow || "",
    isAct = (e) => {
      let t = tg(e);
      return AR.test(t) || (t == "a" && !!at(e, "href")) || (t == "input" && at(e, "type").toLowerCase() != "hidden") || RR.test(at(e, "role").toLowerCase());
    },
    negM = (s) => !!s && ["Top", "Bottom", "Left", "Right"].some((k) => P(s["margin" + k]) < -0.5),
    isAnc = (a, b) => {
      if (!a || !b) return false;
      if (fn(a.contains)) return a.contains(b);
      for (let c = b; c; c = pn(c)) if (c == a) return true;
      return false;
    },
    nearSvg = (e) => {
      for (let c = e; c; c = pn(c)) if (tg(c) == "svg") return c;
      return null;
    },
    ownPill = (l, r, lb, rb, sb) => {
      if (hasC(r, "erd-lbl-bg") || hasC(r, "erd-edge-lbl") || !!at(r, "data-erd-label-bg")) return true;
      let rp = pn(r);
      if (rp && (hasC(rp, "erd-edge-lbl") || (rp == pn(l) && tg(rp) == "g"))) return true;
      if (sb && sb.w > 0 && sb.h > 0 && (rb.w * rb.h) / (sb.w * sb.h) >= 0.85) return true;
      let pL = lb.x - rb.x, pR = rb.r - lb.r, pT = lb.y - rb.y, pB = rb.b - lb.b;
      return pL >= -2 && pR >= -2 && pT >= -2 && pB >= -2 && pL <= 20 && pR <= 20 && pT <= 16 && pB <= 16;
    };

  const lintLayout = (root, opts) => {
    let o = opts || {},
      doc = G.document,
      base = root || doc?.body || doc?.documentElement;
    if (base?.nodeType == 9) base = base.body || base.documentElement;
    if (!base) return [];

    let gcs = fn(o.getComputedStyle) ? o.getComputedStyle : (fn(G.getComputedStyle) ? G.getComputedStyle.bind(G) : () => ({})),
      minA = F(o.minOverlapArea) ? o.minOverlapArea : 1,
      cTol = F(o.clipTol) ? o.clipTol : 2,
      maxF = F(o.maxFindings) ? o.maxFindings : 200,
      rL = A(o.rules) ? o.rules : R,
      on = (r) => rL.includes(r),
      out = [],
      add = (rule, el, detail, a, b, fix) => {
        if (out.length < maxF) out.push({ rule: rule, selector: sel(el), detail: detail, rectA: pub(a), rectB: pub(b), suggestedFix: fix });
      },
      all = [base],
      stk = [base];
    while (stk.length) {
      let ch = stk.pop().children || [];
      for (let i = ch.length - 1; i >= 0; i--) all.push(ch[i]), stk.push(ch[i]);
    }

    let idM = new WeakMap(), csM = new WeakMap(), bxM = new WeakMap(),
      st = (e) => {
        let s = csM.get(e);
        if (s) return s;
        try { s = gcs(e) || {}; } catch { s = {}; }
        csM.set(e, s);
        return s;
      },
      bx = (e) => bxM.has(e) ? bxM.get(e) : (bxM.set(e, box(e)), bxM.get(e)),
      kids = (p) => {
        let res = [], w = (n) => {
          for (let c of n?.children || []) st(c).display == "contents" ? w(c) : res.push(c);
        };
        w(p);
        return res;
      },
      fClip = new WeakSet(),
      idx = 0;
    for (let e of all) idM.set(e, ++idx), st(e), bx(e);

    // 1. LINT-FLEX-SHRINK-CLIP
    if (on(R[0])) {
      for (let el of all) {
        let cs = st(el), d = cs.display;
        if ((d != "flex" && d != "inline-flex") || hid(cs)) continue;
        let eb = bx(el), col = S(cs.flexDirection || "row").startsWith("column");
        for (let c of kids(el)) {
          let s = st(c), p = s.position;
          if (hid(s) || p == "absolute" || p == "fixed" || !(P(s.flexShrink) > 0)) continue;
          if (KR.test(ov(s, col ? "Y" : "X"))) continue;
          let cw = +(col ? c.clientHeight : c.clientWidth) || 0,
            sw = +(col ? c.scrollHeight : c.scrollWidth) || 0;
          if (!col && s.whiteSpace == "nowrap" && s.textOverflow == "ellipsis" && !c.children?.length) continue;
          if (sw > cw + 1) {
            fClip.add(c);
            let sc = sel(c), se = sel(el);
            add(R[0], c, sc + " shrunk " + rd(cw) + "<" + rd(sw) + "px in " + se, bx(c), eb, "Add flex-shrink: 0 to " + sc);
          }
        }
      }
    }

    // 2. LINT-SIBLING-OVERLAP
    if (on(R[1])) {
      let seen = {},
        skip = (e, s, b) => {
          let p = s.position;
          return !vis(s, b) || isSvg(e) || p == "fixed" || p == "sticky" || (p == "absolute" && s.pointerEvents == "none");
        },
        rep = (a, sa, ba, b, sb, bb, ar) => {
          let ia = idM.get(a) || 0, ib = idM.get(b) || 0, k = ia < ib ? ia + ":" + ib : ib + ":" + ia;
          if (seen[k]) return;
          seen[k] = 1;
          let na = negM(sa), nb = negM(sb);
          add(
            R[1], a, ovD(a, b, ar), ba, bb,
            na || nb ? "Remove negative margin on " + sel(na ? a : b) + "; use gap/padding" : "Add flex-shrink: 0 or gap between " + sel(a) + " and " + sel(b)
          );
        };
      for (let el of all) {
        if (isSvg(el) || hid(st(el))) continue;
        let vs = [];
        for (let c of kids(el)) {
          let s = st(c), b = bx(c);
          if (!skip(c, s, b)) vs.push([c, s, b]);
        }
        for (let x = 0; x < vs.length; x++) {
          for (let y = x + 1; y < vs.length; y++) {
            let a = ovA(vs[x][2], vs[y][2]);
            if (a > minA) rep(vs[x][0], vs[x][1], vs[x][2], vs[y][0], vs[y][1], vs[y][2], a);
          }
        }
      }
      for (let el of all) {
        let cs = st(el), eb = bx(el);
        if (!isAct(el) || skip(el, cs, eb)) continue;
        for (let cur = pe(el), dep = 0, eff = eb; cur && dep < 2;) {
          let ps = st(cur);
          if (ps.display == "contents") { cur = pe(cur); continue; }
          if (ps.position == "fixed" || ps.position == "sticky") break;
          if (HR.test(ov(ps, "X")) || HR.test(ov(ps, "Y"))) {
            eff = clipB(eff, bx(cur));
            if (eff.w <= 0.5 || eff.h <= 0.5) break;
          }
          let gp = pe(cur);
          if (!gp || isSvg(gp)) break;
          for (let un of kids(gp)) {
            if (un == cur || isAnc(un, el) || isAnc(el, un)) continue;
            let us = st(un), ub = bx(un), a = skip(un, us, ub) ? 0 : ovA(eff, ub);
            if (a > minA) rep(el, cs, eff, un, us, ub, a);
          }
          cur = gp;
          dep++;
        }
      }
    }

    // 3. LINT-SVG-TEXT-OVERLAP
    if (on(R[2])) {
      let lbs = [], cds = [], rcs = [];
      for (let el of all) {
        let s = st(el), b = bx(el);
        if (!vis(s, b)) continue;
        let t = tg(el);
        if ((t == "text" || hasC(el, "erd-lbl") || !!at(el, "data-erd-label")) && tx(el)) lbs.push([el, b]);
        if (hasC(el, "erd-card") || hasC(el, "erd-node") || !!at(el, "data-erd-card")) cds.push([el, b]);
        else if (t == "rect" && b.w >= 24 && b.h >= 16) rcs.push([el, b, nearSvg(el)]);
      }
      for (let i = 0; i < lbs.length; i++) {
        let la = lbs[i][0], ba = lbs[i][1], sl = sel(la), ls = nearSvg(la), lsb = ls && bx(ls);
        for (let j = i + 1; j < lbs.length; j++) {
          let lb = lbs[j][0], bb = lbs[j][1];
          if (!isAnc(la, lb) && !isAnc(lb, la)) {
            let a = ovA(ba, bb);
            if (a > minA) add(R[2], la, ovD(la, lb, a), ba, bb, "Offset SVG/ERD labels or increase spacing");
          }
        }
        for (let c of cds) {
          if (!isAnc(c[0], la) && !isAnc(la, c[0])) {
            let a = ovA(ba, c[1]);
            if (a > minA) add(R[2], la, ovD(la, c[0], a, "card"), ba, c[1], "Route " + sl + " outside " + sel(c[0]));
          }
        }
        for (let r of rcs) {
          if (!isAnc(r[0], la) && !isAnc(la, r[0])) {
            let a = ovA(ba, r[1]);
            if (a > minA && !ownPill(la, r[0], ba, r[1], r[2] ? bx(r[2]) : lsb)) {
              add(R[2], la, ovD(la, r[0], a, "rect"), ba, r[1], "Move " + sl + " off " + sel(r[0]) + " or add class='erd-lbl-bg'");
            }
          }
        }
      }
    }

    // 4. LINT-TEXT-CLIPPED
    if (on(R[3])) {
      for (let el of all) {
        if (isSvg(el) || fClip.has(el) || XR.test(tg(el))) continue;
        let s = st(el), b = bx(el);
        if (!vis(s, b) || !tx(el) || P(s.webkitLineClamp || s.lineClamp) > 0) continue;
        let ch = +el.clientHeight || 0, sh = +el.scrollHeight || 0, cw = +el.clientWidth || 0, sw = +el.scrollWidth || 0, se = sel(el);
        if (HR.test(ov(s, "Y")) && ch > 1 && sh > ch + cTol) {
          add(R[3], el, "Clip Y " + se + " " + rd(ch) + "<" + rd(sh) + "px", b, null, "Use min-height or overflow-y: auto on " + se);
        } else if (HR.test(ov(s, "X")) && cw > 1 && sw > cw + cTol && s.textOverflow != "ellipsis" && (!el.children?.length || s.whiteSpace == "nowrap")) {
          add(R[3], el, "Clip X " + se + " " + rd(cw) + "<" + rd(sw) + "px", b, null, "Add text-overflow: ellipsis or wrap on " + se);
        }
      }
    }

    // 5. LINT-VIEWPORT-BLEED-X
    if (on(R[4])) {
      let de = doc?.documentElement, rb = bx(base), isR = !doc || base == doc.body || base == de,
        vpL = isR ? 0 : (rb ? rb.x : 0),
        vpW = F(o.viewportWidth) ? o.viewportWidth : (isR ? (+G.innerWidth || +de?.clientWidth || (rb ? rb.w : 0)) : (rb ? rb.w : 0)),
        vpR = vpL + vpW, ih = +G.innerHeight || 0;
      if (vpW > 0) {
        let dsw = isR ? M.max(+de?.scrollWidth || 0, +base.scrollWidth || 0) : (+base.scrollWidth || 0);
        if (dsw > vpW + 1) {
          add(R[4], base, "Root X overflow " + rd(dsw) + ">" + rd(vpW) + "px", rb, { x: vpL, y: 0, w: vpW, h: ih, r: vpR, b: ih }, "Constrain wide children (min-width: 0; max-width: 100%)");
        }
        for (let i = 1; i < all.length; i++) {
          let el = all[i], s = st(el), b = bx(el);
          if (isSvg(el) || !vis(s, b) || (b.r <= vpR + 1 && b.x >= vpL - 1)) continue;
          if (s.position == "fixed" && (b.r <= vpL + 1 || b.x >= vpR - 1)) continue;
          let clp = false;
          for (let c = pe(el); c && c != base && c != de; c = pe(c)) {
            if (OR.test(ov(st(c), "X"))) { clp = true; break; }
          }
          if (!clp) {
            let se = sel(el);
            add(R[4], el, se + " X bleed [" + rd(b.x) + "," + rd(b.r) + "]", b, { x: vpL, y: b.y, w: vpW, h: b.h, r: vpR, b: b.b }, "Add max-width: 100%; min-width: 0 on " + se);
          }
        }
      }
    }

    return out;
  };

  let u = G.Maat || G.BlindUI;
  (G.Maat = G.BlindUI = typeof u == "object" && u || {}).lintLayout = lintLayout;
  if (typeof module != "undefined" && module?.exports) module.exports = lintLayout;
})(typeof globalThis != "undefined" ? globalThis : this);
