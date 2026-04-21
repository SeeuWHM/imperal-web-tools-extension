"""web-tools · Left sidebar — Domain Scan / IP Scan (manual tab buttons)."""
from __future__ import annotations

from imperal_sdk import ui

from panels_ui import scan_tool_items, ip_scan_items

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
        defaults={"ssl": True, "http": True, "email": True, "blacklist": True,
                  "geo": False, "whois": False, "ports": False},
        children=[
            ui.TagInput(
                values=[], param_name="domains", delimiters=[","],
                placeholder="domain.com — press Enter to add",
                validate=_DOMAIN_RE,
                validate_message="Enter a valid domain",
            ),
            ui.Stack([
                ui.Toggle(label="SSL",   param_name="ssl",       value=True),
                ui.Toggle(label="HTTP",  param_name="http",      value=True),
                ui.Toggle(label="Email", param_name="email",     value=True),
                ui.Toggle(label="BL",    param_name="blacklist", value=True),
                ui.Toggle(label="Geo",   param_name="geo",       value=False),
                ui.Toggle(label="WHOIS", param_name="whois",     value=False),
                ui.Toggle(label="Ports", param_name="ports",     value=False),
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
            results_section = [
                ui.Divider(label=ts),
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
            items = ip_scan_items(rdata)
            results_section = [
                ui.Divider(label=ts),
                ui.List(items=items),
            ]
    return ui.Stack([_tabs("ip"), form, *results_section])
