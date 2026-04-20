"""web-tools · Right panel: monitors overview + inline New Monitor form."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import (
    status_badge, fmt_interval,
    PROFILE_CHECK_OPTS, PROFILE_CHECK_DEFAULTS, INTERVAL_OPTS,
)

MAX_MONITORS = 5

# ─── Overview builder ─────────────────────────────────────────────────────── #

async def build_overview(ctx) -> ui.UINode:
    """Stats + bar chart + monitor cards + inline New Monitor form."""
    mon_page, grp_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
    )
    grp_map = {g.id: g.data["name"] for g in grp_page.data}

    # ── New Monitor form (always at bottom) ───────────────────────────────── #
    if len(mon_page.data) >= MAX_MONITORS:
        new_mon_section: list = [
            ui.Divider(label="New Monitor"),
            ui.Alert(type="warn",
                     message=f"Monitor limit reached ({MAX_MONITORS}/{MAX_MONITORS}). "
                              "Delete one to add more."),
        ]
    else:
        new_mon_section = [
            ui.Divider(label="New Monitor"),
            ui.Form(
                action="create_monitor_full",
                submit_label="Create Monitor",
                defaults={"interval_hours": "24"},
                children=[
                    ui.Input(placeholder="Monitor name...", param_name="name"),
                    ui.TagInput(
                        values=[],
                        placeholder="site.com — Enter, comma or space",
                        param_name="domains",
                        delimiters=[" ", ","],
                        validate=r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+$",
                        validate_message="Enter a valid domain",
                    ),
                    ui.MultiSelect(
                        options=PROFILE_CHECK_OPTS,
                        values=PROFILE_CHECK_DEFAULTS,
                        param_name="checks",
                    ),
                    ui.Select(
                        options=INTERVAL_OPTS, value="24", param_name="interval_hours",
                    ),
                ],
            ),
        ]

    # ── Empty state ───────────────────────────────────────────────────────── #
    if not mon_page.data:
        return ui.Stack([
            ui.Empty(message="No monitors yet — create one below", icon="Monitor"),
            *new_mon_section,
        ])

    # ── Load snapshots ────────────────────────────────────────────────────── #
    async def _snap(sid):
        return await ctx.store.get("wt_snapshots", sid) if sid else None

    snaps    = await asyncio.gather(*[_snap(m.data.get("last_snapshot_id"))
                                       for m in mon_page.data])
    snap_map = {mon_page.data[i].id: snaps[i] for i in range(len(mon_page.data))}

    n_crit = sum(1 for s in snaps if s and s.data.get("status") == "critical")
    n_warn = sum(1 for s in snaps if s and s.data.get("status") == "warning")
    n_ok   = sum(1 for s in snaps if s and s.data.get("status") == "ok")

    # ── Stats ─────────────────────────────────────────────────────────────── #
    stats = ui.Stats([
        ui.Stat(label="Monitors", value=len(mon_page.data), icon="Monitor"),
        ui.Stat(label="OK",       value=n_ok,   icon="CheckCircle",  color="green"),
        ui.Stat(label="Warning",  value=n_warn, icon="AlertTriangle", color="yellow"),
        ui.Stat(label="Critical", value=n_crit, icon="XCircle",       color="red"),
    ])

    # ── Bar chart ─────────────────────────────────────────────────────────── #
    chart_data = []
    for m in mon_page.data:
        snap = snap_map.get(m.id)
        if snap:
            s = snap.data.get("summary", {})
            if s.get("total_domains"):
                label = m.data["name"][:11].rstrip() + "…" if len(m.data["name"]) > 12 \
                        else m.data["name"]
                chart_data.append({
                    "name": label,
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

    # ── Critical alert ────────────────────────────────────────────────────── #
    crit_alert: list = []
    if n_crit:
        crit_alert = [ui.Alert(type="error",
                               message=f"{n_crit} monitor(s) critical — scan now")]

    # ── Monitor cards (critical → warning → ok → unknown) ────────────────── #
    _order = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    sorted_mons = sorted(
        mon_page.data,
        key=lambda m: _order.get(
            (snap_map.get(m.id) and snap_map[m.id].data.get("status")) or "unknown", 3),
    )

    mon_cards: list = []
    for m in sorted_mons:
        snap       = snap_map.get(m.id)
        mon_status = (snap and snap.data.get("status")) or "unknown"
        grp_name   = grp_map.get(m.data.get("group_id", ""), "—")
        last_run   = (m.data.get("last_run_at") or "")[:10]
        ssum       = snap.data.get("summary", {}) if snap else {}
        total      = ssum.get("total_domains", 0)
        n_ok_dom   = ssum.get("domains_ok", min(ssum.get("ok", 0), total))
        pct_ok     = int(n_ok_dom / total * 100) if total else 0

        if total:
            content: ui.UINode = ui.Stack([
                ui.Stack([
                    status_badge(mon_status),
                    ui.Text(content=f"{n_ok_dom}/{total} OK", variant="caption"),
                ], direction="h", gap=2),
                ui.Progress(
                    value=pct_ok, label=f"{pct_ok}%", variant="bar",
                    color="red" if pct_ok < 40 else "yellow" if pct_ok < 70 else "green",
                ),
            ])
        else:
            content = ui.Stack([
                status_badge(mon_status),
                ui.Text(content="Never scanned", variant="caption"),
            ], direction="h", gap=2)

        mon_cards.append(ui.Card(
            title=m.data["name"],
            subtitle=f"{grp_name} · {fmt_interval(m.data['interval_hours'])}",
            content=content,
            footer=ui.Stack([
                ui.Text(content=f"Last: {last_run or 'Never'}", variant="caption"),
                ui.Tooltip(
                    content="Run health scan now",
                    children=ui.Button("Scan Now", icon="Play", variant="ghost",
                                       size="sm",
                                       on_click=ui.Call("run_scan", monitor_id=m.id)),
                ),
            ], direction="h", justify="between"),
            on_click=ui.Call("__panel__detail", monitor_id=m.id),
        ))

    return ui.Stack([
        stats,
        *crit_alert,
        *chart_block,
        *mon_cards,
        *new_mon_section,
    ])
