"""web-tools · Right panel: overview dashboard — stats, chart, quick check, monitors."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import status_badge, quick_kv, PRESET_OPTS, fmt_interval


# ─── Overview builder ─────────────────────────────────────────────────────── #

async def build_overview(ctx) -> ui.UINode:
    """Health dashboard: 4-stat row, bar chart, quick check, monitor cards."""
    mon_page, grp_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
    )
    grp_map = {g.id: g.data["name"] for g in grp_page.data}

    # ── Quick Check (always shown) ────────────────────────────────────────── #
    quick_form = ui.Form(
        action="quick_check", submit_label="Check Now",
        defaults={"preset": "full"},
        children=[
            ui.Input(placeholder="domain.com or IP address...", param_name="domain"),
            ui.Select(options=PRESET_OPTS, value="full", param_name="preset"),
        ],
    )
    qpage = await ctx.store.query("wt_quick_results",
                                  where={"owner_id": ctx.user.id}, limit=1)
    last_result: list = []
    if qpage.data:
        q  = qpage.data[0].data
        kv = quick_kv(q)
        if kv:
            last_result = [ui.Card(
                title=q.get("domain", ""),
                subtitle=(f"{q.get('preset','').upper()} · "
                          f"{q.get('created_at','')[:16].replace('T', ' ')}"),
                content=ui.KeyValue(items=kv, columns=2),
            )]

    # ── Empty state ───────────────────────────────────────────────────────── #
    if not mon_page.data:
        return ui.Stack([
            ui.Divider(label="Quick Check"),
            quick_form,
            *last_result,
            ui.Divider(label="Monitors"),
            ui.Empty(
                message="Set up a domain group, check profile, and monitor to start.",
                icon="Monitor",
                action=ui.Call("__panel__overview", show_setup="1"),
            ),
        ])

    # ── Load snapshots in parallel ────────────────────────────────────────── #
    async def _snap(sid):
        return await ctx.store.get("wt_snapshots", sid) if sid else None

    snaps    = await asyncio.gather(
        *[_snap(m.data.get("last_snapshot_id")) for m in mon_page.data]
    )
    snap_map = {mon_page.data[i].id: snaps[i] for i in range(len(mon_page.data))}

    n_crit = sum(1 for s in snaps if s and s.data.get("status") == "critical")
    n_warn = sum(1 for s in snaps if s and s.data.get("status") == "warning")
    n_ok   = sum(1 for s in snaps if s and s.data.get("status") == "ok")

    # ── Stats row ─────────────────────────────────────────────────────────── #
    stats = ui.Stats([
        ui.Stat(label="Monitors", value=len(mon_page.data), icon="Monitor"),
        ui.Stat(label="OK",       value=n_ok,               icon="CheckCircle",
                color="green"),
        ui.Stat(label="Warning",  value=n_warn,             icon="AlertTriangle",
                color="yellow"),
        ui.Stat(label="Critical", value=n_crit,             icon="XCircle",
                color="red"),
    ])

    # ── Bar chart: domain health per monitor ──────────────────────────────── #
    chart_data = []
    for m in mon_page.data:
        snap = snap_map.get(m.id)
        if snap:
            ssum = snap.data.get("summary", {})
            if ssum.get("total_domains"):
                chart_data.append({
                    "name":     (m.data["name"][:11].rstrip() + "…"
                                 if len(m.data["name"]) > 12
                                 else m.data["name"]),
                    "OK":       ssum.get("domains_ok", 0),
                    "Warning":  ssum.get("domains_warning", 0),
                    "Critical": ssum.get("domains_critical", 0),
                    "Unknown":  ssum.get("domains_unknown", 0),
                })

    chart_block: list = []
    if chart_data:
        chart_block = [
            ui.Text(content="Domain Health by Monitor", variant="label"),
            ui.Chart(
                data=chart_data, type="bar", x_key="name", height=160,
                colors={"OK": "#22c55e", "Warning": "#eab308", "Critical": "#ef4444", "Unknown": "#6b7280"},
            ),
        ]

    # ── Critical alert ────────────────────────────────────────────────────── #
    crit_alert: list = []
    if n_crit:
        crit_alert = [ui.Alert(
            type="error",
            message=f"{n_crit} monitor(s) have critical issues — scan now",
        )]

    # ── Monitor cards (sorted: critical → warning → ok → unknown) ─────────── #
    _order = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    sorted_mons = sorted(
        mon_page.data,
        key=lambda m: _order.get(
            (snap_map.get(m.id) and snap_map.get(m.id).data.get("status")) or "unknown",
            3,
        ),
    )

    mon_cards: list = []
    for m in sorted_mons:
        snap       = snap_map.get(m.id)
        mon_status = (snap and snap.data.get("status")) or "unknown"
        grp_name   = grp_map.get(m.data.get("group_id", ""), "—")
        last_run   = (m.data.get("last_run_at") or "")[:10]
        ssum       = snap.data.get("summary", {}) if snap else {}
        total      = ssum.get("total_domains", 0)
        # prefer domain-level count; fallback for old snapshots caps at total
        n_ok_dom   = ssum.get("domains_ok", min(ssum.get("ok", 0), total))
        pct_ok     = int(n_ok_dom / total * 100) if total else 0

        if total:
            health_line: ui.UINode = ui.Stack([
                status_badge(mon_status),
                ui.Text(content=f"{n_ok_dom}/{total} domains OK", variant="caption"),
            ], direction="horizontal", gap=2)
            _pct_color = "red" if pct_ok < 40 else "yellow" if pct_ok < 70 else "green"
            progress: ui.UINode = ui.Progress(
                value=pct_ok,
                label=f"{pct_ok}%",
                variant="bar",
                color=_pct_color,
            )
            card_content: ui.UINode = ui.Stack([health_line, progress])
        else:
            card_content = ui.Stack([
                status_badge(mon_status),
                ui.Text(content="Never scanned", variant="caption"),
            ], direction="horizontal", gap=2)

        mon_cards.append(ui.Card(
            title=m.data["name"],
            subtitle=f"{grp_name} · {fmt_interval(m.data['interval_hours'])}",
            content=card_content,
            footer=ui.Stack([
                ui.Text(content=f"Last: {last_run or 'Never'}", variant="caption"),
                ui.Button("Scan Now", icon="Play", variant="ghost", size="sm",
                          on_click=ui.Call("run_scan", monitor_id=m.id)),
            ], direction="horizontal", justify="between"),
            on_click=ui.Call("__panel__detail", monitor_id=m.id),
        ))

    return ui.Stack([
        stats,
        *crit_alert,
        *chart_block,
        ui.Divider(label="Quick Check"),
        quick_form,
        *last_result,
        ui.Divider(label="Monitors"),
        *mon_cards,
    ])
