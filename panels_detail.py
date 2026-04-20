"""web-tools · Right panel: monitor detail — pie chart, domain list, settings."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import status_badge, domain_items, INTERVAL_OPTS, fmt_interval


# ─── Detail builder ───────────────────────────────────────────────────────── #

async def build_detail(ctx, monitor_id: str) -> ui.UINode:
    """Per-monitor view: toolbar, pie chart, domain list, inline settings."""
    mon_page, grp_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
    )
    grp_map = {g.id: g.data["name"] for g in grp_page.data}
    mon = next((m for m in mon_page.data if m.id == monitor_id), None)

    if not mon:
        return ui.Stack([
            ui.Button("← Overview", icon="ArrowLeft", variant="ghost", size="sm",
                      on_click=ui.Call("__panel__overview")),
            ui.Error(message="Monitor not found.",
                     retry=ui.Call("__panel__overview")),
        ])

    snap_id  = mon.data.get("last_snapshot_id")
    snap     = await ctx.store.get("wt_snapshots", snap_id) if snap_id else None
    status   = snap.data.get("status", "unknown") if snap else "unknown"
    domains  = snap.data.get("domains", {}) if snap else {}
    last     = (mon.data.get("last_run_at") or "")[:10]
    grp_name = grp_map.get(mon.data.get("group_id", ""), "—")
    interval = fmt_interval(mon.data["interval_hours"])

    # ── Sticky toolbar ────────────────────────────────────────────────────── #
    toolbar = ui.Stack([
        ui.Tooltip(
            content="Back to overview",
            children=ui.Button("Overview", icon="ArrowLeft", variant="ghost", size="sm",
                               on_click=ui.Call("__panel__overview")),
        ),
        ui.Stack([
            ui.Text(content=mon.data["name"], variant="subheading"),
            status_badge(status),
        ], direction="horizontal", gap=2),
        ui.Tooltip(
            content="Run health scan now for all domains in this monitor",
            children=ui.Button("Scan Now", icon="Play", variant="secondary", size="sm",
                               on_click=ui.Call("run_scan", monitor_id=mon.id)),
        ),
    ], direction="horizontal", gap=2, justify="between", sticky=True, wrap=False)

    caption = ui.Text(
        content=f"{grp_name} · {interval}" + (f" · Last scan: {last}" if last else " · Never scanned"),
        variant="caption",
    )

    # ── Inline settings (collapsed Card) ─────────────────────────────────── #
    settings = ui.Accordion(sections=[{
        "id": "settings", "title": "⚙ Settings",
        "children": [ui.Stack([
            ui.Text(content="Rename monitor or change scan frequency.",
                    variant="caption"),
            ui.Form(
                action="update_monitor", submit_label="Save Changes",
                defaults={"monitor_id": mon.id},
                children=[
                    ui.Input(placeholder="Monitor name", param_name="name",
                             value=mon.data["name"]),
                    ui.Select(options=INTERVAL_OPTS,
                              value=str(mon.data["interval_hours"]),
                              param_name="interval_hours"),
                ],
            ),
        ], gap=2)],
    }])

    # ── No scan yet ───────────────────────────────────────────────────────── #
    if not domains:
        return ui.Stack([
            toolbar, caption,
            ui.Empty(message="No scan results yet — press Scan Now", icon="Activity"),
            settings,
        ])

    # ── Check-level counts ────────────────────────────────────────────────── #
    all_chks = [c for d in domains.values() for c in d.values()]
    n_ok   = sum(1 for c in all_chks if c.get("status") == "ok")
    n_warn = sum(1 for c in all_chks if c.get("status") == "warning")
    n_crit = sum(1 for c in all_chks if c.get("status") == "critical")
    n_unk  = sum(1 for c in all_chks if c.get("status") == "unknown")

    # ── Pie chart: check status breakdown ────────────────────────────────── #
    pie_data = [{"status": s, "value": v} for s, v in [
        ("OK", n_ok), ("Warning", n_warn),
        ("Critical", n_crit), ("Unavailable", n_unk),
    ] if v]
    chart_block: list = []
    if pie_data:
        chart_block = [
            ui.Text(content="Check Results Breakdown", variant="label"),
            ui.Chart(
                data=pie_data, type="pie", x_key="status", height=180,
                colors={"OK": "#22c55e", "Warning": "#eab308",
                        "Critical": "#ef4444", "Unavailable": "#8b5cf6"},
            ),
        ]

    n_dom  = len(domains)
    ssum   = snap.data.get("summary", {}) if snap else {}
    n_d_ok = ssum.get("domains_ok",       sum(1 for d in domains.values()
                       if all(c.get("status") == "ok" for c in d.values())))
    summary_parts = [f"{n_dom} domain{'s' if n_dom != 1 else ''}",
                     f"{n_d_ok} OK"]
    if ssum.get("domains_warning", n_warn):
        summary_parts.append(f"{ssum.get('domains_warning', n_warn)} warning")
    if ssum.get("domains_critical", n_crit):
        summary_parts.append(f"{ssum.get('domains_critical', n_crit)} critical")
    if ssum.get("domains_unknown", n_unk):
        summary_parts.append(f"{ssum.get('domains_unknown', n_unk)} unavailable")
    summary = ui.Text(content=" · ".join(summary_parts), variant="caption")

    crit_alert: list = []
    if n_crit:
        crit_alert = [ui.Alert(
            type="error",
            message=f"{n_crit} critical check(s) — review domains below",
        )]

    return ui.Stack([
        toolbar,
        caption,
        *chart_block,
        summary,
        *crit_alert,
        ui.List(items=domain_items(domains), searchable=True),
        settings,
    ])
