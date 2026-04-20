"""web-tools · Left sidebar — monitors navigation + health summary."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import status_badge, fmt_interval


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

    # Load snapshot status + summary directly — skeleton is cached and can be
    # stale right after a scan (skeleton refreshes on its own schedule)
    async def _snap_data(m):
        sid = m.data.get("last_snapshot_id")
        if not sid:
            return m.id, "unknown", {}
        snap = await ctx.store.get("wt_snapshots", sid)
        if snap:
            return m.id, snap.data.get("status", "unknown"), snap.data.get("summary", {})
        return m.id, "unknown", {}

    snap_rows    = await asyncio.gather(*[_snap_data(m) for m in mon_page.data])
    live_status  = {mid: st   for mid, st, _   in snap_rows}
    live_summary = {mid: summ for mid, _,  summ in snap_rows}

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
            ui.Button("Set Up Web Tools", icon="Settings", variant="primary",
                      full_width=True,
                      on_click=ui.Call("__panel__overview", show_setup="1")),
        ])

    # ── Monitor list ──────────────────────────────────────────────────────── #
    mon_items = []
    for m in mon_page.data:
        grp_name = grp_map.get(m.data.get("group_id", ""), "—")
        last_run = (m.data.get("last_run_at") or "")[:10]    # live from store, not skeleton
        snap_sum = live_summary.get(m.id, {})

        if snap_sum and snap_sum.get("total_domains"):
            total = snap_sum["total_domains"]
            n_ok  = snap_sum.get("domains_ok", min(snap_sum.get("ok", 0), total))
            sub   = f"{grp_name} · {n_ok}/{total} OK · {last_run or 'never'}"
        else:
            sub = f"{grp_name} · {fmt_interval(m.data['interval_hours'])} · never scanned"

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
        ui.Button("Setup", icon="Settings", variant="secondary",
                  size="md", full_width=True,
                  on_click=ui.Call("__panel__overview", show_setup="1")),
    ])
