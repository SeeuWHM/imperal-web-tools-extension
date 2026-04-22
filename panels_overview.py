"""web-tools · Right panel: Monitors / New Monitor (header button nav)."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import status_badge, fmt_interval, INTERVAL_OPTS, PROFILE_CHECK_OPTS

MAX_MONITORS = 5


# ─── Public entry ─────────────────────────────────────────────────────────── #

async def build_overview(ctx, view: str = "monitors") -> ui.UINode:
    if view == "new":
        return await _build_new_view(ctx)
    return await _build_monitors_view(ctx)


# ─── Monitors view ────────────────────────────────────────────────────────── #

async def _build_monitors_view(ctx) -> ui.UINode:
    mon_page, grp_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
    )
    grp_map = {g.id: g.data["name"] for g in grp_page.data}

    header = ui.Stack([
        ui.Text(content="Domain Health", variant="subheading"),
        ui.Tooltip(
            content="Create a new domain health monitor",
            children=ui.Button("New Monitor", icon="Plus", variant="primary",
                               size="md",
                               on_click=ui.Call("__panel__overview", view="new")),
        ),
    ], direction="h", justify="between", sticky=True, wrap=False)

    if not mon_page.data:
        return ui.Stack([
            header,
            ui.Empty(message="No monitors yet — click '+ New Monitor'",
                     icon="Monitor"),
        ])

    async def _snap(sid):
        return await ctx.store.get("wt_snapshots", sid) if sid else None

    snaps    = await asyncio.gather(*[_snap(m.data.get("last_snapshot_id"))
                                       for m in mon_page.data])
    snap_map = {mon_page.data[i].id: snaps[i] for i in range(len(mon_page.data))}

    n_crit = sum(1 for s in snaps if s and s.data.get("status") == "critical")
    n_warn = sum(1 for s in snaps if s and s.data.get("status") == "warning")
    n_ok   = sum(1 for s in snaps if s and s.data.get("status") == "ok")

    stats = ui.Stats([
        ui.Stat(label="Monitors", value=len(mon_page.data), icon="Monitor"),
        ui.Stat(label="OK",       value=n_ok,   icon="CheckCircle",   color="green"),
        ui.Stat(label="Warning",  value=n_warn, icon="AlertTriangle",  color="yellow"),
        ui.Stat(label="Critical", value=n_crit, icon="XCircle",        color="red"),
    ])

    chart_data = []
    for m in mon_page.data:
        snap = snap_map.get(m.id)
        if snap:
            s = snap.data.get("summary", {})
            if s.get("total_domains"):
                lbl = (m.data["name"][:11].rstrip() + "…"
                       if len(m.data["name"]) > 12 else m.data["name"])
                chart_data.append({
                    "name":     lbl,
                    "OK":       s.get("domains_ok",       0),
                    "Warning":  s.get("domains_warning",  0),
                    "Critical": s.get("domains_critical", 0),
                    "Unknown":  s.get("domains_unknown",  0),
                })
    chart_block: list = []
    if chart_data:
        chart_block = [ui.Chart(
            data=chart_data, type="bar", x_key="name", height=140,
            colors={"OK": "#22c55e", "Warning": "#eab308",
                    "Critical": "#ef4444", "Unknown": "#6b7280"},
        )]

    crit_alert: list = []
    if n_crit:
        crit_alert = [ui.Alert(type="error",
                               message=f"{n_crit} monitor(s) critical — scan now")]

    _order = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    sorted_mons = sorted(
        mon_page.data,
        key=lambda m: _order.get(
            (snap_map.get(m.id) and snap_map[m.id].data.get("status")) or "unknown", 3),
    )
    mon_cards = [_monitor_card(m, snap_map.get(m.id),
                                grp_map.get(m.data.get("group_id", ""), "—"))
                 for m in sorted_mons]

    return ui.Stack([header, stats, *crit_alert, *chart_block, *mon_cards])


# ─── New Monitor view ─────────────────────────────────────────────────────── #

async def _build_new_view(ctx) -> ui.UINode:
    count  = await ctx.store.count("wt_monitors", where={"owner_id": ctx.user.id})
    header = ui.Stack([
        ui.Tooltip(
            content="Back to monitors",
            children=ui.Button("", icon="ArrowLeft", variant="ghost", size="md",
                               on_click=ui.Call("__panel__overview", view="monitors")),
        ),
    ], direction="h", gap=2, sticky=True, wrap=False)

    if count >= MAX_MONITORS:
        return ui.Stack([
            header,
            ui.Alert(type="warn",
                     message=f"Monitor limit reached ({MAX_MONITORS}/{MAX_MONITORS}). "
                              "Delete a monitor to add a new one."),
        ])

    form = ui.Card(
        title="New Monitor",
        subtitle="Monitor domains on a recurring schedule",
        content=ui.Form(
            action="create_monitor_full",
            submit_label="Create Monitor",
            defaults={
                "interval_hours": "24",
                "ssl": True, "http": True, "email": True, "blacklist": True,
                "geo": False, "whois": False,
            },
            children=[
                ui.Input(placeholder="Monitor name...", param_name="name"),
                ui.TagInput(
                    values=[],
                    placeholder="domain.com — Enter · space · comma to add",
                    param_name="domains",
                    delimiters=[",", " "],
                    validate=r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+$",
                    validate_message="Enter a valid domain (e.g. example.com)",
                ),
                ui.Stack([
                    ui.Toggle(label="SSL",   param_name="ssl",       value=True),
                    ui.Toggle(label="HTTP",  param_name="http",      value=True),
                    ui.Toggle(label="Email", param_name="email",     value=True),
                    ui.Toggle(label="BL",    param_name="blacklist", value=True),
                    ui.Toggle(label="Geo",   param_name="geo",       value=False),
                    ui.Toggle(label="WHOIS", param_name="whois",     value=False),
                ], direction="h", gap=2, wrap=True),
                ui.Select(options=INTERVAL_OPTS, value="24",
                          param_name="interval_hours"),
            ],
        ),
    )
    return ui.Stack([header, form])


# ─── Monitor card ─────────────────────────────────────────────────────────── #

def _monitor_card(m, snap, grp_name: str) -> ui.UINode:
    mon_status = (snap and snap.data.get("status")) or "unknown"
    last_run   = (m.data.get("last_run_at") or "")[:10]
    ssum       = snap.data.get("summary", {}) if snap else {}
    total      = ssum.get("total_domains", 0)
    n_ok_dom   = ssum.get("domains_ok", min(ssum.get("ok", 0), total))
    pct_ok     = int(n_ok_dom / total * 100) if total else 0

    if total:
        content: ui.UINode = ui.Stack([
            ui.Stack([status_badge(mon_status),
                      ui.Text(content=f"{n_ok_dom}/{total} OK", variant="caption")],
                     direction="h", gap=2),
            ui.Progress(value=pct_ok, label=f"{pct_ok}%", variant="bar",
                        color="red" if pct_ok < 40 else
                              "yellow" if pct_ok < 70 else "green"),
        ])
    else:
        content = ui.Stack([status_badge(mon_status),
                            ui.Text(content="Never scanned", variant="caption")],
                           direction="h", gap=2)

    return ui.Card(
        title=m.data["name"],
        subtitle=f"{grp_name} · {fmt_interval(m.data['interval_hours'])}",
        content=content,
        footer=ui.Stack([
            ui.Text(content=f"Last: {last_run or 'Never'}", variant="caption"),
            ui.Tooltip(content="Run health scan now",
                       children=ui.Button(
                           "Scan Now", icon="Play", variant="ghost", size="sm",
                           on_click=ui.Call("run_scan", monitor_id=m.id))),
        ], direction="h", justify="between"),
        on_click=ui.Call("__panel__detail", monitor_id=m.id),
    )
