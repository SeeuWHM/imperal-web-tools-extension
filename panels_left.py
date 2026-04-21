"""web-tools · Left sidebar — Domain Scan / IP Scan with expandable results."""
from __future__ import annotations

from imperal_sdk import ui

from panels_ui import scan_tool_items, status_badge

_DOMAIN_RE = r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+$"


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


# ─── Domain Scan ──────────────────────────────────────────────────────────── #

async def _domain_view(ctx) -> ui.UINode:
    spage = await ctx.store.query("wt_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    form = ui.Form(
        action="run_scan_tool", submit_label="Scan",
        defaults={
            "ssl": True, "http": True, "email": True, "blacklist": True,
            "geo": False, "whois": False, "ports": False,
            "smtp": False, "propagation": False,
        },
        children=[
            ui.TagInput(
                values=[], param_name="domains", delimiters=[","],
                placeholder="domain.com — press Enter to add",
                validate=_DOMAIN_RE,
                validate_message="Enter a valid domain",
            ),
            ui.Stack([
                ui.Toggle(label="SSL",    param_name="ssl",         value=True),
                ui.Toggle(label="HTTP",   param_name="http",        value=True),
                ui.Toggle(label="Email",  param_name="email",       value=True),
                ui.Toggle(label="BL",     param_name="blacklist",   value=True),
                ui.Toggle(label="Geo",    param_name="geo",         value=False),
                ui.Toggle(label="WHOIS",  param_name="whois",       value=False),
                ui.Toggle(label="SMTP",   param_name="smtp",        value=False),
                ui.Toggle(label="Prop",   param_name="propagation", value=False),
                ui.Toggle(label="Ports",  param_name="ports",       value=False),
            ], direction="h", gap=1, wrap=True),
        ],
    )
    results_section: list = []
    if spage.data:
        last  = spage.data[0].data
        rdata = last.get("results", {})
        if rdata:
            ts    = last.get("created_at", "")[:16].replace("T", " ")
            items = scan_tool_items(rdata)
            crit  = sum(1 for d in rdata.values()
                        for r in d.values() if r.get("status") == "critical")
            alert: list = [ui.Alert(type="error",
                                    message=f"{crit} critical issue(s) found")]  \
                          if crit else []
            results_section = [
                ui.Divider(label=ts),
                *alert,
                ui.List(items=items),
            ]
    return ui.Stack([_tabs("domain"), form, *results_section])


# ─── IP Scan ──────────────────────────────────────────────────────────────── #

async def _ip_view(ctx) -> ui.UINode:
    spage = await ctx.store.query("wt_ip_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    form = ui.Form(
        action="run_ip_scan", submit_label="Scan",
        defaults={"ip_lookup": True, "blacklist": True,
                  "reverse": True, "ports": False, "geo_ping": True},
        children=[
            ui.TagInput(
                values=[], param_name="domains", delimiters=[","],
                placeholder="1.2.3.4 — press Enter to add",
            ),
            ui.Stack([
                ui.Toggle(label="Info",  param_name="ip_lookup", value=True),
                ui.Toggle(label="BL",    param_name="blacklist", value=True),
                ui.Toggle(label="PTR",   param_name="reverse",   value=True),
                ui.Toggle(label="Ports", param_name="ports",     value=False),
                ui.Toggle(label="Ping",  param_name="geo_ping",  value=True),
            ], direction="h", gap=1, wrap=True),
        ],
    )
    results_section: list = []
    if spage.data:
        last  = spage.data[0].data
        rdata = last.get("results", {})
        if rdata:
            ts    = last.get("created_at", "")[:16].replace("T", " ")
            items = _ip_scan_items(rdata)
            crit  = sum(1 for ir in rdata.values()
                        for r in ir.values() if r.get("status") == "critical")
            alert: list = [ui.Alert(type="error",
                                    message=f"{crit} critical issue(s) found")]  \
                          if crit else []
            results_section = [
                ui.Divider(label=ts),
                *alert,
                ui.List(items=items),
            ]
    return ui.Stack([_tabs("ip"), form, *results_section])


# ─── IP Scan helpers (local — only used here) ─────────────────────────────── #

def _fmt_ip_val(chk: str, data: dict) -> str:
    """Compact one-line summary for a single IP check result (used in subtitle)."""
    if not data:
        return ""
    if chk == "ip_lookup":
        country = data.get("country", "")
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
        open_p = [str(p["port"]) for p in (data.get("ports") or [])
                  if p.get("status") == "open"]
        return f"Open: {', '.join(open_p[:4])}" if open_p else "All closed"
    if chk == "geo_ping":
        regions = data.get("regions", {})
        reach   = sum(1 for r in regions.values()
                      if isinstance(r, dict) and r.get("reachable"))
        return f"Ping {reach}/{len(regions)}"
    return chk.upper()


def _ip_expanded_kv(checks: dict) -> list:
    """Detailed KV rows for expanded IP scan result."""
    kv = []
    for chk, res in checks.items():
        data = res.get("data") or {}
        if not data:
            continue
        if chk == "ip_lookup":
            country = data.get("country", "—")
            org     = data.get("org", "—")
            asn_raw = data.get("asn", "")
            asn     = f"AS{asn_raw}" if asn_raw and not str(asn_raw).startswith("AS") else str(asn_raw)
            network = data.get("network", "")
            kv.append({"key": "Location", "value": f"{country} · {org}"})
            if asn:
                kv.append({"key": "ASN", "value": asn})
            if network:
                kv.append({"key": "Network", "value": str(network)})
        elif chk == "blacklist":
            verdict = data.get("verdict", "clean")
            checked = data.get("total_checked", 30)
            if verdict == "clean":
                kv.append({"key": "Blacklist", "value": f"Clean · {checked} lists"})
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
                      for p in (data.get("ports") or []) if p.get("status") == "open"]
            if open_p:
                port_str = ", ".join(f"{p}" + (f" ({s})" if s else "") for p, s in open_p[:6])
                kv.append({"key": "Open Ports", "value": port_str})
            else:
                kv.append({"key": "Ports", "value": "All closed"})
        elif chk == "geo_ping":
            regions = data.get("regions", {})
            lines   = []
            for name, r in regions.items():
                if not isinstance(r, dict):
                    continue
                sym    = "✓" if r.get("reachable") else "✗"
                avg_ms = r.get("avg_ms")
                ms_str = f" {avg_ms:.0f}ms" if avg_ms is not None else ""
                lines.append(f"{name} {sym}{ms_str}")
            kv.append({"key": "Geo Ping", "value": " · ".join(lines)})
    return kv


def _ip_scan_items(results: dict) -> list:
    """Expandable ListItems for IP Scan Tool — subtitle + full detail on expand."""
    items = []
    for ip, checks in sorted(results.items()):
        statuses = [c.get("status", "ok") for c in checks.values()]
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
            expanded_content=[ui.KeyValue(items=kv, columns=2)] if kv else [],
        ))
    return items
