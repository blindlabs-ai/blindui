#!/usr/bin/env python3
"""Maat App Forge: zero-dependency strict-CSP single-bundle app synthesizer and verifier."""

from __future__ import annotations

import argparse, html as html_lib, json, re, shutil, sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path: sys.path.insert(0, str(_HERE))

import maat_check  # noqa: E402

ARCHETYPES: Tuple[str, ...] = ("tactile-inbox", "workspace-drive", "sql-studio", "openapi-console")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_ASSETS = ("maat.min.js", "maat-kit.min.js", "maat-layout-lint.min.js", "maat-tokens.css")
_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "tactile-inbox": {
        "surface": "mail", "tagline": "Tactile zero-latency inbox with swipe containment and offline-first privacy.",
        "items": [
            {"title": "Q4 Launch Readiness", "meta": "Product Team | 2m", "badge": "Unread", "body": "All **strict-CSP** bundles verified within budget and ready for rollout."},
            {"title": "Mobile Gesture Sign-Off", "meta": "Design Systems | 18m", "badge": "Pinned", "body": "Touch rows keep `flex-shrink: 0` and `44px` tap targets with zero overlap."},
            {"title": "Weekly Telemetry Digest", "meta": "Operations | 1h", "badge": "Inbox", "body": "Frame-1 sync boot averaged **3.2 ms** across desktop and mobile viewports."},
        ],
        "routes": [{"method": "GET", "path": "/api/v1/threads", "desc": "List tactile inbox threads"}, {"method": "POST", "path": "/api/v1/threads/archive", "desc": "Archive selected thread"}],
    },
    "workspace-drive": {
        "surface": "apps", "tagline": "Local-first workspace documents with instant preview and clean obsidian typography.",
        "items": [
            {"title": "Architecture Blueprint", "meta": "Doc | 48 KB", "badge": "Synced", "body": "Single-bundle **Safe-DOM** rendering with zero external CDNs or iframes."},
            {"title": "Layout Invariants Guide", "meta": "Note | 19 KB", "badge": "Verified", "body": "Every scroll row declares `flex-shrink: 0` and clean mobile bottom clearance."},
            {"title": "Release Checklist", "meta": "Sheet | 32 KB", "badge": "Ready", "body": "Automated static `MAAT-01..16` and runtime `Maat.lintLayout()` gates pass."},
        ],
        "routes": [{"method": "GET", "path": "/api/v1/items", "desc": "List workspace files"}, {"method": "POST", "path": "/api/v1/items", "desc": "Create workspace document"}],
    },
    "sql-studio": {
        "surface": "developers", "tagline": "Schema-aware SQL workspace with pill-protected ERD diagrams and instant inspection.",
        "items": [
            {"title": "accounts (4 cols)", "meta": "PK id | indexed email", "badge": "Table", "body": "`SELECT id, handle, plan FROM accounts ORDER BY created_at DESC LIMIT 20;`"},
            {"title": "workspaces (5 cols)", "meta": "FK owner_id -> accounts", "badge": "Table", "body": "`SELECT w.name, count(d.id) FROM workspaces w JOIN docs d ON d.ws_id = w.id GROUP BY 1;`"},
            {"title": "audit_events (4 cols)", "meta": "Append-only log", "badge": "Stream", "body": "`SELECT action, count(*) FROM audit_events GROUP BY action;`"},
        ],
        "routes": [{"method": "POST", "path": "/api/v1/query", "desc": "Run read-only SQL statement"}, {"method": "GET", "path": "/api/v1/schema", "desc": "Inspect live table graph"}],
    },
    "openapi-console": {
        "surface": "developers", "tagline": "Interactive API explorer with typed presets, copyable examples, and status telemetry.",
        "items": [
            {"title": "GET /api/v1/status", "meta": "200 OK | 4 ms", "badge": "Live", "body": "Returns service health, active version, and layout gate verification state."},
            {"title": "POST /api/v1/records", "meta": "201 Created | 9 ms", "badge": "Typed", "body": "Validates payload schema client-side before transmitting to the API gateway."},
            {"title": "GET /api/v1/metrics", "meta": "200 OK | 6 ms", "badge": "JSON", "body": "Exposes compact tabular counters for latency, throughput, and error rate."},
        ],
        "routes": [{"method": "GET", "path": "/api/v1/status", "desc": "Service health probe"}, {"method": "POST", "path": "/api/v1/records", "desc": "Create typed record"}],
    },
}


def _normalize_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    arch = str(spec.get("archetype") or "workspace-drive").strip()
    if arch not in ARCHETYPES:
        raise ValueError(f"Unsupported archetype {arch!r}; expected one of {ARCHETYPES}")
    raw_name = str(spec.get("name") or f"Maat {arch.replace('-', ' ').title()}").strip()
    name = "".join(ch for ch in raw_name if 32 <= ord(ch) <= 126)[:64] or "Maat App"
    color = str(spec.get("brandColor") or "#38bdf8").strip()
    color = color if _HEX_RE.match(color) else "#38bdf8"
    d = _DEFAULTS[arch]
    items: List[Dict[str, str]] = []
    for idx, it in enumerate((spec.get("collections") or [])[:8]):
        if isinstance(it, dict):
            meta = str(it.get("meta") or " | ".join(str(p) for p in (it.get("kind"), it.get("updated"), it.get("size")) if p) or "Active")[:64]
            items.append({"title": str(it.get("title") or f"Item {idx + 1}")[:64], "meta": meta, "badge": str(it.get("badge") or it.get("kind") or "Ready")[:20], "body": str(it.get("body") or it.get("summary") or "Verified Safe-DOM workspace entry.")[:240]})
        elif isinstance(it, str) and it.strip():
            items.append({"title": it.strip()[:64], "meta": "Collection", "badge": "Active", "body": "Verified Safe-DOM workspace entry."})
    routes = [
        {"method": str(rt.get("method") or "GET").upper()[:8], "path": str(rt.get("path") or "/api/v1/health")[:64], "desc": str(rt.get("desc") or "API endpoint")[:96]}
        if isinstance(rt, dict) else {"method": "GET", "path": str(rt).strip()[:64], "desc": "API endpoint"}
        for rt in (spec.get("routes") or [])[:6] if isinstance(rt, dict) or (isinstance(rt, str) and rt.strip())
    ]
    return {"name": name, "archetype": arch, "surface": d["surface"], "tagline": d["tagline"], "brandColor": color, "e2ee": bool(spec.get("e2ee", True)), "tactileMobile": bool(spec.get("tactileMobile", True)), "items": items or list(d["items"]), "routes": routes or list(d["routes"])}


def _render_css(cfg: Dict[str, Any]) -> str:
    ac = cfg["brandColor"]
    return (
        f":root{{--mf-brand:{ac};--mf-brand-soft:{ac}24}}\n"
        ".mf-root{min-height:100vh;background:radial-gradient(circle at 12% 0%,var(--mf-brand-soft),transparent 42%),#090b10}\n"
        ".mf-hero{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;border-color:color-mix(in srgb,var(--mf-brand) 38%,transparent)}\n"
        ".mf-hero-id{display:flex;align-items:center;gap:12px;min-width:0}\n"
        ".mf-hero-title{margin:0;font-size:20px;line-height:1.25}.mf-hero-sub{margin:4px 0 0;color:#94a3b8;font-size:13px}\n"
        ".mf-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:14px;align-items:start}\n"
        ".mf-list{display:flex;flex-direction:column;gap:10px;max-height:460px;overflow-y:auto;padding-bottom:16px}\n"
        ".msg-swipe-wrap{display:block;flex-shrink:0;overflow:hidden;touch-action:pan-y;border-radius:10px;border:1px solid #fff1;background:#11151f}\n"
        ".inbox-row,.file-row,.list-row{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-shrink:0;touch-action:pan-y;width:100%;padding:12px 14px;background:transparent;border:0;text-align:left;cursor:pointer}\n"
        ".inbox-row:hover,.file-row:hover,.list-row:hover,.mf-row-on{background:var(--mf-brand-soft)}\n"
        ".mf-row-main{display:flex;flex-direction:column;gap:2px;min-width:0;flex:1}\n"
        ".mf-row-title{font-weight:600;color:#f1f5f9;font-size:14px;line-height:1.3}.mf-row-meta{color:#94a3b8;font-size:12px;line-height:1.3}\n"
        ".mf-pane{display:flex;flex-direction:column;gap:12px}\n"
        ".mf-erd-wrap{width:100%;overflow:hidden;border-radius:8px;border:1px solid #fff1;background:#0b0f17;padding:8px}\n"
        ".mf-erd-svg{display:block;width:100%;height:auto;max-height:190px}\n"
        ".mf-route-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:8px 10px;border-radius:8px;background:#0d111a;border:1px solid #fff1;font-size:12px}\n"
        ".mf-method{font-weight:700;color:var(--mf-brand);font-family:var(--bui-mono)}.mf-mobile-nav{display:none}\n"
        "@media(max-width:768px){\n"
        "  .mf-grid{grid-template-columns:1fr}.mf-list{max-height:none;padding-bottom:calc(120px + env(safe-area-inset-bottom))}\n"
        "  .mf-mobile-nav{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:20;gap:8px;padding:10px 12px calc(10px + env(safe-area-inset-bottom));background:#0d111ae8;border-top:1px solid #fff1;justify-content:space-around}\n"
        "  .mf-mobile-nav button{flex:1;min-height:44px}.bui-main{padding-bottom:calc(96px + env(safe-area-inset-bottom))}\n"
        "}\n"
    )


def _render_js(cfg: Dict[str, Any]) -> str:
    spec_json = json.dumps(cfg, separators=(",", ":"))
    return f"""(function(){{
  "use strict";
  var t0 = performance.now();
  var M = window.Maat || window.BlindUI, h = M.h, svg = M.svg, md = M.md, kit = M.kit;
  var CFG = {spec_json}, state = {{ idx: 0 }};
  var rowCls = CFG.archetype === "tactile-inbox" ? "inbox-row" : (CFG.archetype === "workspace-drive" ? "file-row" : "list-row");
  function brandMark(){{
    return svg("svg", {{ viewBox: "0 0 36 36", width: 34, height: 34, "aria-hidden": "true" }},
      svg("rect", {{ x: 2, y: 2, width: 32, height: 32, rx: 9, fill: CFG.brandColor, "fill-opacity": "0.16", stroke: CFG.brandColor, "stroke-width": 1.6 }}),
      svg("polygon", {{ points: "18,7 27,18 18,29 9,18", fill: "none", stroke: CFG.brandColor, "stroke-width": 1.8 }}),
      svg("circle", {{ cx: 18, cy: 18, r: 3.2, fill: CFG.brandColor }}));
  }}
  function svgText(attrs, txt){{
    var el = document.createElementNS("http://www.w3.org/2000/svg", "text");
    for (var k in attrs) el.setAttribute(k, String(attrs[k]));
    el.textContent = txt; return el;
  }}
  function buildErd(){{
    function node(x, stroke, title, r1, r2){{
      return svg("g", {{ className: "erd-node" }},
        svg("rect", {{ x: x, y: 34, width: 130, height: 88, rx: 10, fill: "#131926", stroke: stroke, "stroke-width": 1.4 }}),
        svgText({{ x: x + 14, y: 62, fill: "#f1f5f9", "font-size": 13, "font-weight": 700 }}, title),
        svgText({{ x: x + 14, y: 84, fill: "#94a3b8", "font-size": 11 }}, r1),
        svgText({{ x: x + 14, y: 104, fill: "#94a3b8", "font-size": 11 }}, r2));
    }}
    return h("div", {{ className: "mf-erd-wrap" }},
      svg("svg", {{ className: "mf-erd-svg", viewBox: "0 0 420 156", role: "img", "aria-label": "Schema relation graph" }},
        svg("line", {{ x1: 146, y1: 78, x2: 274, y2: 78, stroke: CFG.brandColor, "stroke-width": 2 }}),
        node(16, CFG.brandColor, "accounts", "id (pk) | handle", "plan | created_at"),
        node(274, "#64748b", "workspaces", "id (pk) | owner_id", "name | status"),
        svg("g", {{ className: "erd-edge-lbl", transform: "translate(0,-14)" }},
          svg("rect", {{ className: "erd-lbl-bg", x: 174, y: 65, width: 72, height: 22, rx: 11, fill: "#090b10", stroke: CFG.brandColor, "stroke-width": 1.2 }}),
          svgText({{ x: 210, y: 80, fill: "#f1f5f9", "font-size": 11, "text-anchor": "middle" }}, "1 : N owns"))));
  }}
  function mkBtn(cls, fn){{
    var b = h("button", {{ type: "button", className: cls }});
    for (var k = 2; k < arguments.length; k++) b.appendChild(typeof arguments[k] === "string" ? document.createTextNode(arguments[k]) : arguments[k]);
    b.addEventListener("click", fn); return b;
  }}
  function render(){{
    var root = document.getElementById("app"), active = CFG.items[state.idx] || CFG.items[0];
    var listEl = h("div", {{ className: "mf-list", role: "list" }}, CFG.items.map(function(item, i){{
      return h("div", {{ className: "msg-swipe-wrap", role: "listitem" }},
        mkBtn(rowCls + (i === state.idx ? " mf-row-on" : ""), function(){{ state.idx = i; render(); }},
          h("span", {{ className: "mf-row-main" }}, h("span", {{ className: "mf-row-title" }}, item.title), h("span", {{ className: "mf-row-meta" }}, item.meta)),
          kit.statusPill({{ label: item.badge, tone: i === state.idx ? "ok" : "muted" }})));
    }}));
    var detail = [
      h("div", {{ className: "bui-row bui-between" }}, h("h3", {{ style: {{ margin: 0, fontSize: "16px" }} }}, active.title), kit.statusPill({{ label: active.badge, tone: "ok" }})),
      h("div", {{ className: "bui-muted bui-sm" }}, active.meta),
      h("div", {{ className: "bui-box" }}, md(active.body))
    ];
    if (CFG.archetype === "sql-studio") detail.push(buildErd());
    if (CFG.archetype === "openapi-console") detail.push(kit.codeBlock({{ tabs: [
      {{ id: "curl", label: "cURL", lang: "bash", code: "curl -s https://localhost:8443" + CFG.routes[0].path }},
      {{ id: "json", label: "JSON", lang: "json", code: '{{"ok":true,"archetype":"openapi-console","layoutFindings":0}}' }}
    ] }}));
    detail.push(h("div", {{ className: "bui-col", style: {{ gap: "6px" }} }}, CFG.routes.map(function(rt){{
      return h("div", {{ className: "mf-route-row" }}, h("span", {{ className: "mf-method" }}, rt.method), h("span", {{ className: "bui-mono" }}, rt.path), h("span", {{ className: "bui-muted" }}, rt.desc));
    }})));
    var main = h("div", {{ className: "bui-col", style: {{ gap: "14px" }} }},
      h("section", {{ className: "bui-card mf-hero" }},
        h("div", {{ className: "mf-hero-id" }}, brandMark(), h("div", null, h("h1", {{ className: "mf-hero-title" }}, CFG.name), h("p", {{ className: "mf-hero-sub" }}, CFG.tagline))),
        h("div", {{ className: "bui-row" }}, kit.statusPill({{ label: CFG.archetype, tone: "ok" }}), kit.statusPill({{ label: CFG.e2ee ? "Private Local Lock" : "Local Session", tone: "ok" }}), h("span", {{ id: "mf-lint-badge" }}, kit.statusPill({{ label: "Feather Gate Ready", tone: "ok" }})))),
      kit.kpiStrip({{ items: [
        {{ id: "mf-kpi-boot", label: "Sync Frame-1 Boot", value: (window.__MAAT_MOUNT_MS__ != null ? window.__MAAT_MOUNT_MS__ + " ms" : "< 15 ms"), tone: "ok", sub: "Zero async waterfall" }},
        {{ label: "Active Items", value: String(CFG.items.length), tone: "ok", sub: "Tactile Safe-DOM rows" }},
        {{ label: "Strict CSP", value: "0 CDNs", tone: "ok", sub: "Single local bundle" }},
        {{ id: "mf-kpi-lint", label: "Layout Gate", value: (window.__MAAT_LINT_COUNT__ != null ? String(window.__MAAT_LINT_COUNT__) : "0") + " issues", tone: "ok", sub: "Maat.lintLayout()" }}
      ] }}),
      h("div", {{ className: "mf-grid" }},
        h("section", {{ className: "bui-card bui-col", style: {{ gap: "10px" }} }}, h("div", {{ className: "bui-row bui-between" }}, h("strong", null, "Workspace Feed"), h("span", {{ className: "bui-muted bui-sm" }}, CFG.tactileMobile ? "Touch-ready" : "Desktop")), listEl),
        h("section", {{ className: "bui-card mf-pane" }}, detail)),
      h("nav", {{ className: "mf-mobile-nav", "aria-label": "Quick actions" }},
        mkBtn("bui-btn bui-btn-primary", function(){{ state.idx = 0; render(); }}, "Primary"),
        mkBtn("bui-btn", function(){{ state.idx = (state.idx + 1) % CFG.items.length; render(); }}, "Next Item")));
    kit.shell({{ mount: root, surface: CFG.surface, brand: CFG.name, brandHref: "#top", main: main, footer: "Forged by Maat App Forge | Zero-Dependency Safe-DOM" }});
  }}
  render();
  window.__MAAT_MOUNT_MS__ = Math.round((performance.now() - t0) * 100) / 100;
  var findings = typeof M.lintLayout === "function" ? M.lintLayout(document.body) : [];
  window.__MAAT_LINT_COUNT__ = findings.length;
  var bootEl = document.querySelector("#mf-kpi-boot .bk-kv");
  if (bootEl) bootEl.textContent = window.__MAAT_MOUNT_MS__ + " ms";
  var badge = document.getElementById("mf-lint-badge");
  if (badge) badge.replaceChildren(kit.statusPill({{ label: findings.length === 0 ? "0 Layout Issues" : findings.length + " Layout Issues", tone: findings.length === 0 ? "ok" : "err" }}));
}})();
"""


def _render_html(cfg: Dict[str, Any]) -> str:
    title = html_lib.escape(cfg["name"], quote=True)
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
        "  <meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'self'; script-src 'self'; style-src 'self'; img-src data:; frame-src 'none'; object-src 'none'; base-uri 'none'\">\n"
        f"  <title>{title}</title>\n  <link rel=\"stylesheet\" href=\"./maat-tokens.css\">\n  <link rel=\"stylesheet\" href=\"./app.bundle.css\">\n"
        "</head>\n<body>\n  <div id=\"app\" class=\"mf-root\"></div>\n"
        "  <script src=\"./maat.min.js\"></script>\n  <script src=\"./maat-kit.min.js\"></script>\n"
        "  <script src=\"./maat-layout-lint.min.js\"></script>\n  <script src=\"./app.bundle.js\"></script>\n</body>\n</html>\n"
    )


def forge_app(spec: Dict[str, Any], out_dir: Path | str) -> Dict[str, Any]:
    """Synthesize a strict-CSP Maat single-bundle application into out_dir."""
    cfg, dest = _normalize_spec(spec), Path(out_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for asset in _ASSETS:
        shutil.copy2(_HERE / asset, dest / asset)
    (dest / "app.bundle.css").write_text(_render_css(cfg), encoding="ascii")
    (dest / "app.bundle.js").write_text(_render_js(cfg), encoding="ascii")
    (dest / "index.html").write_text(_render_html(cfg), encoding="ascii")
    return {"ok": True, "name": cfg["name"], "archetype": cfg["archetype"], "brandColor": cfg["brandColor"], "out_dir": str(dest), "files": [*_ASSETS, "app.bundle.css", "app.bundle.js", "index.html"]}


def verify_forged_app(out_dir: Path | str, browser: bool = True, screenshot: Optional[Path] = None) -> Dict[str, Any]:
    """Run static MAAT-01..16 audit and optional headless Chromium Maat.lintLayout() checks."""
    dest = Path(out_dir).resolve()
    static_rep = maat_check.check_app(ui_path=dest / "index.html", server_path=None, surface="app", blindui_path=dest / "maat.min.js", rule_prefix="MAAT")
    browser_rep: Dict[str, Any] = {"skipped": not browser}
    if browser:
        from playwright.sync_api import sync_playwright
        chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
        vp_results: Dict[str, Any] = {}
        with sync_playwright() as p:
            br = p.chromium.launch(executable_path=chrome, headless=True) if chrome else p.chromium.launch(headless=True)
            for label, w, ht, mob in (("desktop", 1280, 800, False), ("mobile", 375, 812, True)):
                ctx = br.new_context(viewport={"width": w, "height": ht}, has_touch=mob, is_mobile=mob)
                page, errs = ctx.new_page(), []
                page.on("pageerror", lambda e, bag=errs: bag.append(str(e)))
                page.goto((dest / "index.html").as_uri(), wait_until="load")
                res = page.evaluate("() => ({ mountMs: window.__MAAT_MOUNT_MS__, aliasOk: window.Maat === window.BlindUI && window.Maat.lintLayout === window.BlindUI.lintLayout, findings: window.Maat.lintLayout(document.body) })")
                if screenshot and label == "desktop":
                    screenshot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(screenshot), full_page=False)
                vp_results[label] = {"viewport": [w, ht], "mount_ms": res["mountMs"], "alias_ok": res["aliasOk"], "page_errors": errs, "findings_count": len(res["findings"]), "findings": res["findings"]}
                ctx.close()
            br.close()
        browser_ok = all(not v["page_errors"] and v["alias_ok"] and v["findings_count"] == 0 and isinstance(v["mount_ms"], (int, float)) and v["mount_ms"] < 15.0 for v in vp_results.values())
        browser_rep = {"ok": browser_ok, "viewports": vp_results}
    return {"ok": bool(static_rep["ok"]) and (True if not browser else bool(browser_rep.get("ok"))), "static": static_rep, "browser": browser_rep}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Maat App Forge: synthesize and verify strict-CSP single-bundle apps")
    ap.add_argument("--spec", required=True, help="Path to JSON app specification")
    ap.add_argument("--out", required=True, help="Output directory for forged app")
    ap.add_argument("--verify", action="store_true", help="Run maat_check + headless Chromium Maat.lintLayout verification")
    ap.add_argument("--no-browser", action="store_true", help="Skip headless Chromium during --verify")
    ap.add_argument("--screenshot", default=None, help="Optional PNG path for desktop screenshot during --verify")
    ap.add_argument("--json", action="store_true", help="Emit JSON report")
    args = ap.parse_args(argv)
    forged = forge_app(json.loads(Path(args.spec).read_text(encoding="utf-8")), Path(args.out))
    report: Dict[str, Any] = {"ok": True, "forged": forged}
    if args.verify:
        ver = verify_forged_app(Path(args.out), browser=not args.no_browser, screenshot=Path(args.screenshot) if args.screenshot else None)
        report["verify"], report["ok"] = ver, bool(ver["ok"])
    print(json.dumps(report, indent=2) if args.json else f"{'OK' if report['ok'] else 'FAIL'} [maat_forge]: {forged['archetype']} -> {forged['out_dir']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
