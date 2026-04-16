"""web-tools · Left sidebar — monitors navigation + health summary."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import status_badge


# ─── Sidebar builder ──────────────────────────────────────────────────────── #

async def build_sidebar(ctx) -> ui.UINode:
    """Compact navigation: health alert, monitor list, action buttons."""
    mon_page, grp_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
    )

    skel      = getattr(ctx, "skeleton_data", {}).get("skeleton_refresh_web_tools", {})
    skel_mons = skel.get("monitors", {})
    grp_map   = {g.id: g.data["name"] for g in grp_page.data}

    # Load actual snapshot statuses directly — skeleton is cached and can be
    # stale right after a scan (skeleton refreshes on its own schedule)
    async def _snap_status(m):
        sid = m.data.get("last_snapshot_id")
        if not sid:
            return m.id, "unknown"
        snap = await ctx.store.get("wt_snapshots", sid)
        return m.id, (snap.data.get("status", "unknown") if snap else "unknown")

    status_pairs = await asyncio.gather(*[_snap_status(m) for m in mon_page.data])
    live_status  = dict(status_pairs)

    # ── Health summary (1 line) ───────────────────────────────────────────── #
    n_total   = len(mon_page.data)
    n_scanned = sum(1 for m in mon_page.data if m.data.get("last_snapshot_id"))

    # Use live snapshot statuses — skeleton can be stale right after a scan
    n_crit    = sum(1 for s in live_status.values() if s == "critical")
    n_ok_live = sum(1 for s in live_status.values() if s == "ok")

    if n_crit:
        health: ui.UINode = ui.Alert(
            type="error", message=f"{n_crit} critical issue(s) detected")
    elif n_total and n_scanned == n_total and n_ok_live == n_total:
        health = ui.Alert(type="success", message="All monitors healthy")
    else:
        count_lbl = f"{n_total} monitor{'s' if n_total != 1 else ''}"
        health = ui.Text(content=count_lbl, variant="caption")

    # ── Empty state ───────────────────────────────────────────────────────── #
    if not mon_page.data:
        return ui.Stack([
            health,
            ui.Divider(),
            ui.Empty(message="No monitors yet", icon="Monitor"),
            ui.Button("Get Started →", icon="ArrowRight", variant="primary",
                      full_width=True,
                      on_click=ui.Call("__panel__setup")),
        ])

    # ── Monitor list ──────────────────────────────────────────────────────── #
    mon_items = []
    for m in mon_page.data:
        skel_m   = skel_mons.get(m.id, {})
        grp_name = grp_map.get(m.data.get("group_id", ""), "—")
        status   = skel_m.get("status", "unknown")
        skel_sum = skel_m.get("summary", {})
        last_run = (skel_m.get("last_run_at") or "")[:10]

        if skel_sum and skel_sum.get("total_domains"):
            total = skel_sum["total_domains"]
            # prefer domain-level count; fallback for old snapshots uses check-level capped at total
            n_ok  = skel_sum.get("domains_ok", min(skel_sum.get("ok", 0), total))
            sub   = f"{grp_name} · {n_ok}/{total} OK · {last_run or 'never'}"
        else:
            sub = f"{grp_name} · {m.data['interval_hours']}h · never scanned"

        mon_items.append(ui.ListItem(
            id=m.id,
            title=m.data["name"],
            subtitle=sub,
            badge=status_badge(live_status.get(m.id, "unknown")),
            meta=last_run or "—",
            on_click=ui.Call("__panel__detail", monitor_id=m.id),
            actions=[
                {"icon": "Play",   "label": "Scan Now",
                 "on_click": ui.Call("run_scan", monitor_id=m.id)},
                {"icon": "Trash2", "label": "Delete",
                 "on_click": ui.Call("delete_monitor", monitor_id=m.id),
                 "confirm": f"Delete '{m.data['name']}'?"},
            ],
        ))

    return ui.Stack([
        health,
        ui.Divider(label="MONITORS"),
        ui.List(items=mon_items),
        ui.Divider(),
        ui.Stack([
            ui.Button("+ New Monitor", icon="Plus", variant="ghost",
                      size="sm", full_width=True,
                      on_click=ui.Call("__panel__setup", show_form="new_monitor")),
            ui.Button("Setup", icon="Settings", variant="ghost",
                      size="sm", full_width=True,
                      on_click=ui.Call("__panel__setup")),
        ], gap=1),
    ])
