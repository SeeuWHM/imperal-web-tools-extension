"""web-tools · Panel UI — Left sidebar + Right content."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from app import ext
from panels_ui import (
    CHECKS_OPTS, PRESET_OPTS, INTERVAL_OPTS,
    status_badge, domain_items, quick_kv, group_items, profile_items,
    build_detail_view,
)

# ─── Refresh triggers ─────────────────────────────────────────────────────── #

_LEFT_REFRESH = (
    "on_event:scan.completed,monitor.created,monitor.deleted,monitor.updated,"
    "group.created,group.deleted,group.updated,profile.created,profile.deleted"
)
_RIGHT_REFRESH = (
    "on_event:scan.completed,monitor.created,monitor.deleted,monitor.updated,quick.completed"
)


# ─── Left Panel ───────────────────────────────────────────────────────────── #

@ext.panel("sidebar", slot="left", title="Web Tools", icon="Globe", refresh=_LEFT_REFRESH)
async def panel_sidebar(ctx, **kwargs):
    """Monitors list + Setup (groups, profiles). No Quick Check here — use right panel."""
    mon_page, grp_page, prf_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
    )

    skel      = getattr(ctx, "skeleton_data", {}).get("skeleton_refresh_web_tools", {})
    skel_mons = skel.get("monitors", {})
    grp_map   = {g.id: {"name": g.data["name"],
                         "count": len(g.data.get("domains", []))}
                 for g in grp_page.data}

    # ── Alert banner ──────────────────────────────────────────────────────── #
    n_critical = sum(1 for d in skel_mons.values() if d.get("status") == "critical")
    n_scanned  = sum(1 for m in mon_page.data if m.data.get("last_snapshot_id"))
    n_ok_mons  = sum(1 for d in skel_mons.values() if d.get("status") == "ok")
    alert_items: list = []
    if n_critical:
        alert_items = [ui.Alert(
            type="error",
            message=f"{n_critical} monitor(s) have critical issues",
        )]
    elif mon_page.data and n_scanned == len(mon_page.data) and n_ok_mons == len(mon_page.data):
        alert_items = [ui.Alert(type="success", message="All monitors healthy")]

    # ── New Monitor form ──────────────────────────────────────────────────── #
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
            message="Create a domain group and check profile first.",
            type="info",
        )

    # ── Monitor list ──────────────────────────────────────────────────────── #
    mon_items = []
    for m in mon_page.data:
        skel_m   = skel_mons.get(m.id, {})
        grp_info = grp_map.get(m.data.get("group_id", ""), {})
        grp_name = grp_info.get("name", "—")
        skel_sum = skel_m.get("summary", {})
        last_run = (skel_m.get("last_run_at") or "")[:10]
        if skel_sum:
            total_dom = skel_sum.get("total_domains", 0)
            n_ok_dom  = skel_sum.get("ok", 0)
            last_lbl  = last_run or "Never"
            subtitle  = f"{grp_name} · {n_ok_dom}/{total_dom} OK · {last_lbl}"
        else:
            dom_count = grp_info.get("count", 0)
            subtitle  = f"{grp_name} · {dom_count} dom · {m.data['interval_hours']}h"
        mon_items.append(ui.ListItem(
            id=m.id,
            title=m.data["name"],
            subtitle=subtitle,
            badge=status_badge(skel_m.get("status", "unknown")),
            meta=last_run or "Never",
            on_click=ui.Call("__panel__stats", selected_monitor_id=m.id),
            actions=[
                {"icon": "Play",   "label": "Scan Now",
                 "on_click": ui.Call("run_scan", monitor_id=m.id)},
                {"icon": "Trash2", "label": "Delete",
                 "on_click": ui.Call("delete_monitor", monitor_id=m.id),
                 "confirm": f"Delete monitor '{m.data['name']}'?"},
            ],
        ))

    # ── Setup: Groups + Profiles ──────────────────────────────────────────── #
    setup_section = ui.Stack([
        ui.Section(title="Domain Groups", children=[
            ui.Accordion(sections=[
                {"id": "new_grp", "title": "+ Add Group", "children": [
                    ui.Form(
                        action="create_domain_group", submit_label="Create Group",
                        children=[
                            ui.Input(placeholder="Group name", param_name="name"),
                            ui.TagInput(placeholder="Type domain, press Enter...",
                                        param_name="domains"),
                        ],
                    ),
                ]},
            ]),
            ui.List(items=group_items(grp_page.data)) if grp_page.data
            else ui.Empty(message="No groups yet", icon="Globe"),
        ]),
        ui.Divider(),
        ui.Section(title="Check Profiles", children=[
            ui.Accordion(sections=[
                {"id": "new_prf", "title": "+ Add Profile", "children": [
                    ui.Form(
                        action="create_check_profile", submit_label="Create Profile",
                        children=[
                            ui.Input(placeholder="Profile name", param_name="name"),
                            ui.Text(content="Select up to 5 checks:", variant="caption"),
                            ui.MultiSelect(options=CHECKS_OPTS,
                                           placeholder="Select checks...", param_name="checks"),
                        ],
                    ),
                ]},
            ]),
            ui.List(items=profile_items(prf_page.data)) if prf_page.data
            else ui.Empty(message="No profiles yet", icon="CheckSquare"),
        ]),
    ])

    return ui.Stack([
        *alert_items,
        ui.Divider(label="MONITORS"),
        ui.Accordion(sections=[
            {"id": "new_mon", "title": "+ New Monitor", "children": [new_mon_form]},
        ]),
        ui.List(items=mon_items) if mon_items
        else ui.Empty(message="No monitors yet — create one above.", icon="Monitor"),
        ui.Divider(label="SETUP"),
        setup_section,
    ])


# ─── Right Panel ──────────────────────────────────────────────────────────── #

@ext.panel("stats", slot="right", title="Domain Status", icon="Activity",
           refresh=_RIGHT_REFRESH)
async def panel_stats(ctx, selected_monitor_id: str = "", **kwargs):
    """Per-monitor domain detail view, or overview with Quick Check + monitor list."""
    mon_page, grp_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
    )

    grp_map = {g.id: g.data["name"] for g in grp_page.data}

    # ── Detail view ───────────────────────────────────────────────────────── #
    if selected_monitor_id and mon_page.data:
        mon = next((m for m in mon_page.data if m.id == selected_monitor_id), None)
        if mon:
            snap_id  = mon.data.get("last_snapshot_id")
            snap     = await ctx.store.get("wt_snapshots", snap_id) if snap_id else None
            grp_name = grp_map.get(mon.data.get("group_id", ""), "—")
            return build_detail_view(mon, grp_name, snap)

    # ── Overview: Stats + alert + Quick Check + monitor list ─────────────── #

    # Quick Check form
    quick_form = ui.Form(
        action="quick_check", submit_label="Check Now",
        children=[
            ui.Input(placeholder="domain.com or IP address...", param_name="domain"),
            ui.Select(options=PRESET_OPTS, value="full", param_name="preset"),
        ],
    )

    # Last Quick Check result
    qpage = await ctx.store.query("wt_quick_results",
                                  where={"owner_id": ctx.user.id}, limit=1)
    quick_result_block: list = []
    if qpage.data:
        q  = qpage.data[0].data
        kv = quick_kv(q)
        if kv:
            quick_result_block = [ui.Card(
                title=q.get("domain", ""),
                subtitle=(
                    f"{q.get('preset', '').upper()} · "
                    f"{q.get('created_at', '')[:16].replace('T', ' ')}"
                ),
                content=ui.KeyValue(items=kv, columns=2),
            )]

    if not mon_page.data:
        return ui.Stack([
            ui.Divider(label="Quick Check"),
            quick_form,
            *quick_result_block,
            ui.Divider(label="Monitors"),
            ui.Empty(
                message="Set up a domain group, check profile, and monitor in the left panel.",
                icon="Monitor",
            ),
        ])

    # Load snapshots in parallel
    async def _snap(sid):
        return await ctx.store.get("wt_snapshots", sid) if sid else None

    snaps    = await asyncio.gather(*[_snap(m.data.get("last_snapshot_id"))
                                      for m in mon_page.data])
    snap_map = {mon_page.data[i].id: snaps[i] for i in range(len(mon_page.data))}

    n_crit = sum(1 for s in snaps if s and s.data.get("status") == "critical")
    n_warn = sum(1 for s in snaps if s and s.data.get("status") == "warning")
    n_ok   = sum(1 for s in snaps if s and s.data.get("status") == "ok")

    stats_row = ui.Grid([
        ui.Stat(label="Monitors", value=len(mon_page.data), icon="Monitor"),
        ui.Stat(label="OK",       value=n_ok,               icon="CheckCircle"),
        ui.Stat(label="Warning",  value=n_warn,             icon="AlertTriangle"),
        ui.Stat(label="Critical", value=n_crit,             icon="XCircle"),
    ], columns=4)

    crit_alert_items: list = []
    if n_crit:
        crit_alert_items = [ui.Alert(
            type="error",
            message=f"{n_crit} monitor(s) have critical issues — scan now",
        )]

    # Sort: critical → warning → ok → unknown
    _order = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    sorted_mons = sorted(
        mon_page.data,
        key=lambda m: _order.get(
            (snap_map.get(m.id) and snap_map.get(m.id).data.get("status")) or "unknown", 3
        ),
    )

    mon_list_items = []
    for m in sorted_mons:
        snap       = snap_map.get(m.id)
        mon_status = (snap and snap.data.get("status")) or "unknown"
        grp_name   = grp_map.get(m.data.get("group_id", ""), "—")
        last_run   = (m.data.get("last_run_at") or "")[:10]
        if snap:
            ssum      = snap.data.get("summary", {})
            total_dom = ssum.get("total_domains", 0)
            n_ok_dom  = ssum.get("ok", 0)
            subtitle  = f"{grp_name} · {n_ok_dom}/{total_dom} OK · {last_run or 'Never'}"
        else:
            subtitle  = f"{grp_name} · {last_run or 'Never'}"
        mon_list_items.append(ui.ListItem(
            id=m.id,
            title=m.data["name"],
            subtitle=subtitle,
            badge=status_badge(mon_status),
            meta=f"every {m.data['interval_hours']}h",
            on_click=ui.Call("__panel__stats", selected_monitor_id=m.id),
            actions=[
                {"icon": "Play", "label": "Scan Now",
                 "on_click": ui.Call("run_scan", monitor_id=m.id)},
            ],
        ))

    return ui.Stack([
        stats_row,
        *crit_alert_items,
        ui.Divider(label="Quick Check"),
        quick_form,
        *quick_result_block,
        ui.Divider(label="Monitors"),
        ui.List(items=mon_list_items),
    ])
