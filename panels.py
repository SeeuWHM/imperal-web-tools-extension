"""web-tools · Panel UI — Left sidebar + Right stats."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from app import ext
from panels_ui import (
    CHECKS_OPTS, PRESET_OPTS, INTERVAL_OPTS,
    status_label, domain_items, quick_kv,
)

# ─── Refresh triggers ─────────────────────────────────────────────────────── #

_LEFT_REFRESH = (
    "on_event:scan.completed,monitor.created,monitor.deleted,"
    "group.created,group.deleted,profile.created,profile.deleted"
)
_RIGHT_REFRESH = "on_event:scan.completed,monitor.created,monitor.deleted,quick.completed"


# ─── Left Panel ───────────────────────────────────────────────────────────── #

@ext.panel("sidebar", slot="left", title="Web Tools", icon="Globe", refresh=_LEFT_REFRESH)
async def panel_sidebar(ctx, **kwargs):
    """Monitors list, quick scan form, setup accordions."""
    mon_page, grp_page, prf_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
    )

    grp_map   = {g.id: {"name": g.data["name"],
                         "count": len(g.data.get("domains", []))}
                 for g in grp_page.data}
    skel_mons = getattr(ctx, "skeleton_data", {}) \
        .get("skeleton_refresh_web_tools", {}).get("monitors", {})

    mon_items = [
        ui.ListItem(
            id=m.id,
            title=m.data["name"],
            subtitle=(
                f"{grp_map.get(m.data.get('group_id', ''), {}).get('name', '—')}"
                f"  ·  {grp_map.get(m.data.get('group_id', ''), {}).get('count', 0)} domains"
                f"  ·  every {m.data['interval_hours']}h"
            ),
            meta=status_label(skel_mons.get(m.id, {}).get("status", "unknown")),
            on_click=ui.Call("__panel__stats", selected_monitor_id=m.id),
            actions=[
                {"icon": "Play",   "label": "Scan Now",
                 "on_click": ui.Call("run_scan", monitor_id=m.id)},
                {"icon": "Trash2",
                 "on_click": ui.Call("delete_monitor", monitor_id=m.id),
                 "confirm": f"Delete monitor '{m.data['name']}'?"},
            ],
        )
        for m in mon_page.data
    ]

    if grp_page.data and prf_page.data:
        new_mon_form = ui.Form(
            action="create_monitor", submit_label="Create Monitor",
            children=[
                ui.Input(placeholder="Monitor name", param_name="name"),
                ui.Select(
                    options=[{"value": g.id, "label": g.data["name"]} for g in grp_page.data],
                    placeholder="Domain group...", param_name="group_id"),
                ui.Select(
                    options=[{"value": p.id, "label": p.data["name"]} for p in prf_page.data],
                    placeholder="Check profile...", param_name="profile_id"),
                ui.Select(options=INTERVAL_OPTS, value="24", param_name="interval_hours"),
            ],
        )
    else:
        new_mon_form = ui.Alert(
            message="Create a domain group and check profile in Setup tab first.",
            type="info",
        )

    monitors_tab = ui.Stack([
        ui.Accordion(sections=[
            {"id": "new_mon", "title": "+ New Monitor", "children": [new_mon_form]},
        ]),
        ui.List(items=mon_items, page_size=10) if mon_items
        else ui.Empty(message="No monitors yet. Create one above.", icon="Monitor"),
    ])

    quick_tab = ui.Form(
        action="quick_check", submit_label="Check Now",
        children=[
            ui.Input(placeholder="domain.com or IP address...", param_name="domain"),
            ui.Select(options=PRESET_OPTS, value="full", param_name="preset"),
        ],
    )

    setup_tab = ui.Accordion(sections=[
        {"id": "new_grp", "title": "+ New Domain Group", "children": [
            ui.Form(
                action="create_domain_group", submit_label="Create Group",
                children=[
                    ui.Input(placeholder="Group name", param_name="name"),
                    ui.TagInput(placeholder="Type domain, press Enter...", param_name="domains"),
                ],
            ),
        ]},
        {"id": "new_prf", "title": "+ New Check Profile", "children": [
            ui.Form(
                action="create_check_profile", submit_label="Create Profile",
                children=[
                    ui.Input(placeholder="Profile name", param_name="name"),
                    ui.MultiSelect(options=CHECKS_OPTS,
                                   placeholder="Select checks...", param_name="checks"),
                ],
            ),
        ]},
    ])

    skel      = getattr(ctx, "skeleton_data", {}).get("skeleton_refresh_web_tools", {})
    stats_row = ui.Grid([
        ui.Stat(label="Monitors", value=skel.get("total",    len(mon_page.data)), icon="Monitor"),
        ui.Stat(label="Critical", value=skel.get("critical", 0),                  icon="XCircle"),
        ui.Stat(label="Warning",  value=skel.get("warning",  0),                  icon="AlertTriangle"),
    ], columns=3)

    return ui.Stack([
        stats_row,
        ui.Tabs(tabs=[
            {"label": f"Monitors ({len(mon_page.data)})", "content": monitors_tab},
            {"label": "Quick Scan",                       "content": quick_tab},
            {"label": "Setup",                            "content": setup_tab},
        ]),
    ])


# ─── Right Panel ──────────────────────────────────────────────────────────── #

@ext.panel("stats", slot="right", refresh=_RIGHT_REFRESH)
async def panel_stats(ctx, selected_monitor_id: str = "", **kwargs):
    """Scan results overview or detail for one monitor."""
    mon_page = await ctx.store.query("wt_monitors",
                                     where={"owner_id": ctx.user.id}, limit=10)

    if not mon_page.data:
        return ui.Alert(
            title="No monitors yet",
            message="Set up a domain group, check profile, and monitor in the left panel.",
            type="info",
        )

    async def _snap(sid):
        return await ctx.store.get("wt_snapshots", sid) if sid else None

    snaps    = await asyncio.gather(*[_snap(m.data.get("last_snapshot_id"))
                                      for m in mon_page.data])
    snap_map = {mon_page.data[i].id: snaps[i] for i in range(len(mon_page.data))}

    critical = sum(1 for s in snaps if s and s.data.get("status") == "critical")
    warning  = sum(1 for s in snaps if s and s.data.get("status") == "warning")
    ok_count = sum(1 for s in snaps if s and s.data.get("status") == "ok")

    stats_row = ui.Grid([
        ui.Stat(label="Monitors", value=len(mon_page.data), icon="Monitor"),
        ui.Stat(label="Critical", value=critical,           icon="XCircle"),
        ui.Stat(label="Warning",  value=warning,            icon="AlertTriangle"),
        ui.Stat(label="OK",       value=ok_count,           icon="CheckCircle"),
    ], columns=4)

    if selected_monitor_id:
        mon = next((m for m in mon_page.data if m.id == selected_monitor_id), None)
        if mon:
            snap    = snap_map.get(mon.id)
            status  = snap.data.get("status", "unknown") if snap else "unknown"
            domains = snap.data.get("domains", {}) if snap else {}
            last    = (mon.data.get("last_run_at") or "Never")[:10]

            header = ui.Stack([
                ui.Button("All Monitors", icon="ArrowLeft", variant="ghost", size="sm",
                          on_click=ui.Call("__panel__stats")),
                ui.Stack([
                    ui.Text(f"{mon.data['name']}  ·  {status_label(status)}  ·  {last}",
                            variant="subheading"),
                    ui.Button("Scan Now", variant="secondary", size="sm",
                              on_click=ui.Call("run_scan", monitor_id=mon.id)),
                ], direction="h", justify="between"),
            ])

            body = (ui.List(items=domain_items(domains)) if domains
                    else ui.Empty(message="No scan results — press Scan Now", icon="Activity"))

            return ui.Stack([stats_row, ui.Divider(), header, body])

    blocks: list = [stats_row, ui.Divider()]

    for m in mon_page.data:
        snap    = snap_map.get(m.id)
        status  = snap.data.get("status", "unknown") if snap else "unknown"
        domains = snap.data.get("domains", {}) if snap else {}
        last    = (m.data.get("last_run_at") or "Never")[:10]

        blocks.append(ui.Stack([
            ui.Text(f"{m.data['name']}  ·  {status_label(status)}  ·  {last}",
                    variant="subheading"),
            ui.Button("Scan Now", variant="secondary", size="sm",
                      on_click=ui.Call("run_scan", monitor_id=m.id)),
        ], direction="h", justify="between"))

        blocks.append(
            ui.List(items=domain_items(domains)) if domains
            else ui.Empty(message="No scan results yet — press Scan Now", icon="Activity")
        )
        blocks.append(ui.Divider())

    qpage = await ctx.store.query("wt_quick_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    if qpage.data:
        q   = qpage.data[0].data
        kv  = quick_kv(q)
        if kv:
            blocks += [
                ui.Divider("Last Quick Check"),
                ui.Text(f"{q.get('domain', '')}  ·  {q.get('preset', '')}  ·  "
                        f"{q.get('created_at', '')[:16]}", variant="caption"),
                ui.KeyValue(items=kv, columns=2),
            ]

    return ui.Stack(blocks)
