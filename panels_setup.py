"""web-tools · Setup panel — domain groups, check profiles, monitors.

Embedded in __panel__overview via show_setup param — preserves visibility across
refreshAll() calls (GAP-1 workaround). Header: ↺ Refresh + ✕ Close.
"""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import INTERVAL_OPTS, fmt_interval, PROFILE_CHECK_DEFAULTS, build_check_toggles

_DEFAULT_CHECKS = PROFILE_CHECK_DEFAULTS


# ─── Section builders ─────────────────────────────────────────────────────── #

def _onboarding(has_grp: bool, has_prf: bool, has_mon: bool) -> ui.UINode:
    if has_grp and has_prf and has_mon:
        return ui.Alert(type="success", message="All set — groups, profiles, and monitors created.")
    steps = [
        ui.Text(
            content="✓ Domain group created" if has_grp
            else "① Add a domain group — enter the domains you want to monitor",
            variant="caption",
        ),
        ui.Text(
            content="✓ Check profile created" if has_prf
            else "② Create a check profile — choose which diagnostics to run",
            variant="caption",
        ),
        ui.Text(
            content="✓ Monitor created" if has_mon
            else "③ Create a monitor — link group + profile and set the schedule",
            variant="caption",
        ),
    ]
    return ui.Stack(steps, gap=1)


def _groups_section(grp_data: list) -> ui.UINode:
    n = len(grp_data)

    if n >= 5:
        create_form: ui.UINode = ui.Alert(
            type="info", message="5/5 groups used — delete one to add more.")
    else:
        create_form = ui.Form(
            action="create_domain_group", submit_label="Create Group",
            children=[
                ui.Text(content="Group name *", variant="label"),
                ui.Input(placeholder="e.g. Production, Staging",
                         param_name="name"),
                ui.Text(content="Domains", variant="label"),
                ui.TagInput(
                    values=[],
                    placeholder="domain.com — Enter, Space or comma",
                    param_name="domains",
                    delimiters=[" ", ","],
                    validate=r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$",
                    validate_message="Enter a valid domain: example.com",
                ),
                ui.Text(content="Max 20 domains per group", variant="caption"),
            ],
        )

    items = []
    for g in grp_data:
        domains = g.data.get("domains", [])
        preview = ", ".join(domains[:3]) + ("…" if len(domains) > 3 else "")
        edit_form = ui.Form(
            action="update_domain_group", submit_label="Save",
            defaults={"group_id": g.id},
            children=[
                ui.Text(content="Group name", variant="label"),
                ui.Input(value=g.data["name"], param_name="name"),
                ui.Text(content="Domains", variant="label"),
                ui.TagInput(
                    values=domains,
                    placeholder="domain.com — Enter, Space or comma",
                    param_name="domains",
                    delimiters=[" ", ","],
                    validate=r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$",
                    validate_message="Enter a valid domain: example.com",
                ),
            ],
        )
        items.append(ui.ListItem(
            id=g.id,
            title=g.data["name"],
            subtitle=f"{len(domains)} domain(s): {preview}" if domains else "empty",
            icon="Globe",
            expandable=True,
            expanded_content=[edit_form],
            actions=[{
                "icon": "Trash2", "label": "Delete",
                "on_click": ui.Call("delete_domain_group", group_id=g.id),
                "confirm": f"Delete '{g.data['name']}' and all its monitors?",
            }],
        ))

    grp_list: ui.UINode = (
        ui.List(items=items) if items
        else ui.Empty(message="No groups yet", icon="Globe")
    )
    return ui.Stack([
        ui.Divider(label=f"DOMAIN GROUPS  {n}/5"),
        ui.Accordion(sections=[{
            "id": "new_grp", "title": "+ Add Group", "children": [create_form],
        }]),
        grp_list,
    ], gap=2)


def _profiles_section(prf_data: list) -> ui.UINode:
    n = len(prf_data)

    if n >= 5:
        create_form: ui.UINode = ui.Alert(
            type="info", message="5/5 profiles used — delete one to add more.")
    else:
        create_form = ui.Form(
            action="create_check_profile", submit_label="Create Profile",
            defaults={"panel_mode": True},
            children=[
                ui.Text(content="Profile name *", variant="label"),
                ui.Input(placeholder="e.g. Full Audit, Quick SSL Check",
                         param_name="name"),
                ui.Text(content="Checks to run (max 5)", variant="label"),
                build_check_toggles(_DEFAULT_CHECKS),
            ],
        )

    items = []
    for p in prf_data:
        checks = p.data.get("checks", [])
        edit_form = ui.Form(
            action="update_check_profile", submit_label="Save",
            defaults={"profile_id": p.id, "panel_mode": True},
            children=[
                ui.Text(content="Profile name", variant="label"),
                ui.Input(value=p.data["name"], param_name="name"),
                ui.Text(content="Checks to run (max 5)", variant="label"),
                build_check_toggles(checks),
            ],
        )
        items.append(ui.ListItem(
            id=p.id,
            title=p.data["name"],
            subtitle=", ".join(checks) if checks else "—",
            icon="ClipboardList",
            expandable=True,
            expanded_content=[edit_form],
            actions=[{
                "icon": "Trash2", "label": "Delete",
                "on_click": ui.Call("delete_check_profile", profile_id=p.id),
                "confirm": f"Delete '{p.data['name']}' and all its monitors?",
            }],
        ))

    prf_list: ui.UINode = (
        ui.List(items=items) if items
        else ui.Empty(message="No profiles yet", icon="ClipboardList")
    )
    return ui.Stack([
        ui.Divider(label=f"CHECK PROFILES  {n}/5"),
        ui.Accordion(sections=[{
            "id": "new_prf", "title": "+ Add Profile", "children": [create_form],
        }]),
        prf_list,
    ], gap=2)


def _monitors_section(grp_data: list, prf_data: list, mon_data: list,
                       has_grp: bool, has_prf: bool) -> ui.UINode:
    n = len(mon_data)
    grp_map = {g.id: g.data["name"] for g in grp_data}

    if not has_grp or not has_prf:
        create_form: ui.UINode = ui.Alert(
            type="info", message="Create a domain group and check profile first.")
    elif n >= 5:
        create_form = ui.Alert(
            type="info", message="5/5 monitors used — delete one to add more.")
    else:
        create_form = ui.Form(
            action="create_monitor", submit_label="Create Monitor",
            children=[
                ui.Text(content="Monitor name *", variant="label"),
                ui.Input(placeholder="e.g. Production Health", param_name="name"),
                ui.Select(
                    options=[{"value": g.id, "label": g.data["name"]}
                             for g in grp_data],
                    placeholder="Domain group…", param_name="group_id",
                ),
                ui.Select(
                    options=[{"value": p.id, "label": p.data["name"]}
                             for p in prf_data],
                    placeholder="Check profile…", param_name="profile_id",
                ),
                ui.Select(options=INTERVAL_OPTS, value="24",
                          param_name="interval_hours"),
            ],
        )

    items = []
    for m in mon_data:
        grp_name = grp_map.get(m.data.get("group_id", ""), "—")
        edit_form = ui.Form(
            action="update_monitor", submit_label="Save",
            defaults={"monitor_id": m.id},
            children=[
                ui.Text(content="Monitor name", variant="label"),
                ui.Input(value=m.data["name"], param_name="name"),
                ui.Text(content="Check interval", variant="label"),
                ui.Select(options=INTERVAL_OPTS,
                          value=str(m.data["interval_hours"]),
                          param_name="interval_hours"),
            ],
        )
        items.append(ui.ListItem(
            id=m.id,
            title=m.data["name"],
            subtitle=f"{grp_name} · {fmt_interval(m.data['interval_hours'])}",
            icon="Activity",
            expandable=True,
            expanded_content=[edit_form],
            actions=[{
                "icon": "Trash2", "label": "Delete",
                "on_click": ui.Call("delete_monitor", monitor_id=m.id),
                "confirm": f"Delete monitor '{m.data['name']}'?",
            }],
        ))

    mon_list: ui.UINode = (
        ui.List(items=items) if items
        else ui.Empty(message="No monitors yet", icon="Activity")
    )
    return ui.Stack([
        ui.Divider(label=f"MONITORS  {n}/5"),
        ui.Accordion(sections=[{
            "id": "new_mon", "title": "+ Add Monitor", "children": [create_form],
        }]),
        mon_list,
    ], gap=2)


# ─── Main builder ─────────────────────────────────────────────────────────── #

async def build_setup(ctx) -> ui.UINode:
    """Setup panel — auto-refreshes on group/profile/monitor events."""
    grp_page, prf_page, mon_page = await asyncio.gather(
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
    )
    has_grp = bool(grp_page.data)
    has_prf = bool(prf_page.data)
    has_mon = bool(mon_page.data)

    header = ui.Stack([
        ui.Stack([
            ui.Text(content="Web Tools Setup", variant="subheading"),
            ui.Text(content="Groups · profiles · monitors", variant="caption"),
        ], gap=0),
        ui.Stack([
            ui.Button("Refresh", icon="RefreshCw", variant="ghost", size="sm",
                      on_click=ui.Call("__panel__overview", show_setup="1")),
            ui.Button("Close", icon="X", variant="ghost", size="sm",
                      on_click=ui.Call("__panel__overview", show_setup="")),
        ], direction="horizontal", gap=1),
    ], direction="horizontal", justify="between", align="center", sticky=True)

    return ui.Stack([
        header,
        _onboarding(has_grp, has_prf, has_mon),
        _groups_section(grp_page.data),
        _profiles_section(prf_page.data),
        _monitors_section(grp_page.data, prf_page.data, mon_page.data,
                          has_grp, has_prf),
    ], gap=3)
