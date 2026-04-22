"""web-tools · Left sidebar — Domain Scan / IP Scan with expandable results."""
from __future__ import annotations

from imperal_sdk import ui

from panels_ui import scan_tool_items, status_badge, _REGION_DISPLAY

_DOMAIN_RE = r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+$"

# ─── Toggle definitions ───────────────────────────────────────────────────── #

_DOMAIN_TOGGLES = [
    # (param_name, label, description shown under toggle, default)
    ("ssl",         "SSL",         "certificate grade A-F · days until expiry · issuer",      True),
    ("http",        "HTTP",        "security headers: HSTS · CSP · X-Frame-Options, grade A-F", True),
    ("email",       "Email",       "SPF · DMARC · DKIM auth — deliverability grade A-F",      True),
    ("blacklist",   "Blacklist",   "29 DNSBL — Spamhaus · SpamCop · Barracuda reputation",    True),
    ("geo",         "Geo",         "HTTP reachability from WEU · US · AS · EEU regions",      False),
    ("whois",       "WHOIS",       "registrar name · expiry date · days remaining",            False),
    ("smtp",        "SMTP",        "mail server test — ports 587/25/465 · STARTTLS support",  False),
    ("propagation", "Propagation", "DNS spread — 6 global resolvers (Google, CF, Quad9...)",  False),
    ("ports",       "Ports",       "TCP scan: web 80/443 · mail 25/587 · DB 3306/5432/6379",  False),
]

_IP_TOGGLES = [
    ("ip_lookup", "Info",      "country · organization · ASN · network range",           True),
    ("blacklist", "Blacklist", "29 DNSBL — Spamhaus · SpamCop · Barracuda reputation",   True),
    ("reverse",   "PTR",       "reverse DNS — hostname assigned to this IP address",     True),
    ("geo_ping",  "Geo Ping",  "ICMP ping latency from WEU · US · AS · EEU",            True),
    ("ports",     "Ports",     "TCP scan: web 80/443 · mail 25/587 · DB 3306/5432/6379", False),
]


# ─── Public entry ─────────────────────────────────────────────────────────── #

async def build_sidebar(ctx, view: str = "domain") -> ui.UINode:
    if view == "ip":
        return await _ip_view(ctx)
    return await _domain_view(ctx)


# ─── Tab bar ──────────────────────────────────────────────────────────────── #

def _tabs(active: str) -> ui.UINode:
    return ui.Stack([
        ui.Button("Domain",
                  variant="secondary" if active == "domain" else "ghost",
                  size="sm",
                  on_click=ui.Call("__panel__sidebar", view="domain")),
        ui.Button("IP",
                  variant="secondary" if active == "ip" else "ghost",
                  size="sm",
                  on_click=ui.Call("__panel__sidebar", view="ip")),
    ], direction="h", gap=0, sticky=True, wrap=False)


def _toggle_stack(toggles: list) -> ui.UINode:
    """Vertical stack of Toggles with inline description text."""
    return ui.Stack([
        ui.Stack([
            ui.Toggle(label=lbl, param_name=key, value=default),
            ui.Text(content=desc, variant="caption"),
        ], direction="h", gap=2, align="center")
        for key, lbl, desc, default in toggles
    ], direction="v", gap=2)


# ─── Domain Scan ──────────────────────────────────────────────────────────── #

async def _domain_view(ctx) -> ui.UINode:
    spage = await ctx.store.query("wt_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    defaults = {key: val for key, _, _, val in _DOMAIN_TOGGLES}
    form = ui.Form(
        action="run_scan_tool", submit_label="Scan",
        defaults=defaults,
        children=[
            ui.TagInput(
                values=[], param_name="domains", delimiters=[",", " "],
                placeholder="domain.com — Enter · space · comma to add",
                validate=_DOMAIN_RE,
                validate_message="Enter a valid domain (e.g. example.com)",
            ),
            _toggle_stack(_DOMAIN_TOGGLES),
        ],
    )
    results_section: list = []
    if spage.data:
        last  = spage.data[0].data
        rdata = last.get("results", {})
        if rdata:
            ts    = last.get("created_at", "")[:16].replace("T", " ")
            crit  = sum(1 for d in rdata.values()
                        for r in d.values() if r.get("status") == "critical")
            warn  = sum(1 for d in rdata.values()
                        for r in d.values() if r.get("status") == "warning")
            alert: list = ([ui.Alert(type="error",
                                     message=f"{crit} critical issue(s) detected")]
                           if crit else [])
            results_section = [
                ui.Divider(label=ts),
                *alert,
                ui.Text(content=f"{len(rdata)} domain(s) · {crit} critical · {warn} warning",
                        variant="caption"),
                ui.List(items=scan_tool_items(rdata)),
            ]
    return ui.Stack([_tabs("domain"), form, *results_section])


# ─── IP Scan ──────────────────────────────────────────────────────────────── #

async def _ip_view(ctx) -> ui.UINode:
    spage = await ctx.store.query("wt_ip_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    defaults = {key: val for key, _, _, val in _IP_TOGGLES}
    form = ui.Form(
        action="run_ip_scan", submit_label="Scan",
        defaults=defaults,
        children=[
            ui.TagInput(
                values=[], param_name="domains", delimiters=[",", " "],
                placeholder="1.2.3.4 — Enter · space · comma to add",
            ),
            _toggle_stack(_IP_TOGGLES),
        ],
    )
    results_section: list = []
    if spage.data:
        last  = spage.data[0].data
        rdata = last.get("results", {})
        if rdata:
            ts    = last.get("created_at", "")[:16].replace("T", " ")
            crit  = sum(1 for ir in rdata.values()
                        for r in ir.values() if r.get("status") == "critical")
            warn  = sum(1 for ir in rdata.values()
                        for r in ir.values() if r.get("status") == "warning")
            alert: list = ([ui.Alert(type="error",
                                     message=f"{crit} critical issue(s) detected")]
                           if crit else [])
            results_section = [
                ui.Divider(label=ts),
                *alert,
                ui.Text(content=f"{len(rdata)} IP(s) · {crit} critical · {warn} warning",
                        variant="caption"),
                ui.List(items=_ip_scan_items(rdata)),
            ]
    return ui.Stack([_tabs("ip"), form, *results_section])


# ─── IP Scan helpers (local — only used here) ─────────────────────────────── #

def _fmt_ip_val(chk: str, data: dict) -> str:
    if not data:
        return "—"
    if chk == "ip_lookup":
        country = data.get("country_name") or data.get("country") or ""
        org     = (data.get("org") or "")[:22]
        return f"{country} · {org}".strip(" ·") or "—"
    if chk == "blacklist":
        verdict = data.get("verdict", "clean")
        if verdict == "clean":
            return "BL Clean"
        total = data.get("listed_count", 0)
        names = [r["name"] for r in (data.get("results") or []) if r.get("listed")][:2]
        more  = f" +{total - len(names)}" if total > len(names) else ""
        return f"BL: {', '.join(names)}{more}" if names else f"BL Listed ({total})"
    if chk == "reverse":
        hn = data.get("hostname") or data.get("ptr")
        return f"PTR: {hn}" if hn else "No PTR"
    if chk == "ports":
        open_p = [str(p["port"]) for p in (data.get("results") or [])
                  if p.get("status") == "open"]
        return f"Open: {', '.join(open_p[:4])}" if open_p else "All closed"
    if chk == "geo_ping":
        regions = data.get("regions", {})
        reach   = sum(1 for r in regions.values()
                      if isinstance(r, dict) and r.get("reachable"))
        return f"Ping {reach}/{len(regions)}"
    return chk.upper()


def _ip_expanded_kv(checks: dict) -> list:
    kv = []
    for chk, res in checks.items():
        data = res.get("data") or {}
        if not data:
            err = res.get("error") or "No data returned"
            kv.append({"key": chk.upper(), "value": err[:60]})
            continue
        if chk == "ip_lookup":
            country = data.get("country_name") or data.get("country") or "—"
            org     = data.get("org") or "—"
            asn     = data.get("asn") or ""
            asn_d   = data.get("asn_description") or ""
            network = data.get("network") or ""
            netname = data.get("netname") or ""
            kv.append({"key": "Location", "value": f"{country} · {org}"})
            if asn:
                kv.append({"key": "ASN",
                           "value": asn + (f" · {asn_d}" if asn_d else "")})
            if network:
                kv.append({"key": "Network",
                           "value": network + (f" ({netname})" if netname else "")})
        elif chk == "blacklist":
            verdict = data.get("verdict", "clean")
            checked = data.get("total_checked", 30)
            if verdict == "clean":
                kv.append({"key": "Blacklist", "value": f"Clean · {checked} lists checked"})
            else:
                total = data.get("listed_count", 0)
                names = [r["name"] for r in (data.get("results") or []) if r.get("listed")][:3]
                kv.append({"key": "Blacklist",
                           "value": f"Listed on {total}: {', '.join(names)}"})
        elif chk == "reverse":
            hn = data.get("hostname") or data.get("ptr")
            kv.append({"key": "PTR", "value": hn or "No PTR record"})
        elif chk == "ports":
            open_p = [(str(p["port"]), p.get("service", ""))
                      for p in (data.get("results") or []) if p.get("status") == "open"]
            if open_p:
                port_str = ", ".join(
                    f"{p}" + (f" ({s})" if s else "") for p, s in open_p[:6])
                kv.append({"key": "Open Ports", "value": port_str})
            else:
                kv.append({"key": "Ports", "value": "All closed"})
        elif chk == "geo_ping":
            regions = data.get("regions", {})
            lines   = []
            for name, r in regions.items():
                if not isinstance(r, dict):
                    continue
                disp   = _REGION_DISPLAY.get(name, name)
                sym    = "✓" if r.get("reachable") else "✗"
                avg_ms = r.get("avg_ms")
                ms_str = f" {avg_ms:.0f}ms" if avg_ms is not None else ""
                lines.append(f"{disp} {sym}{ms_str}")
            kv.append({"key": "Geo Ping", "value": " · ".join(lines)})
    return kv


def _ip_scan_items(results: dict) -> list:
    items = []
    for ip, checks in sorted(results.items()):
        statuses = [c.get("status", "unknown") for c in checks.values()]
        overall  = (
            "critical" if "critical" in statuses else
            "warning"  if "warning"  in statuses else "ok"
        )
        parts    = [_fmt_ip_val(chk, (res.get("data") or {}))
                    for chk, res in checks.items()]
        subtitle = " · ".join(p for p in parts if p)
        kv       = _ip_expanded_kv(checks)
        items.append(ui.ListItem(
            id=ip, title=ip,
            subtitle=subtitle or "—",
            badge=status_badge(overall),
            expandable=bool(kv),
            expanded_content=[
                ui.Stack([ui.KeyValue(items=kv, columns=2)], className="select-text"),
            ] if kv else [],
        ))
    return items
