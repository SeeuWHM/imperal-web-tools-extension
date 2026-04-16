"""web-tools · Setup panel — SlideOver with TagInput domains and toggle check types.

Requires SDK v1.5.4+ (TagInput and SlideOver fixed).
"""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import CHECKS_INFO, INTERVAL_OPTS, fmt_interval


# ─── Check toggle rows ────────────────────────────────────────────────────── #

def _check_toggles(selected: list[str] | None = None) -> list:
    """One Toggle+Tooltip row per check type. Defaults: ssl/http/email/blacklist ON."""
    defaults = {"ssl", "http", "email", "blacklist"}
    rows = []
    for key, (label, tip) in CHECKS_INFO.items():
        is_on = key in (selected if selected is not None else defaults)
        rows.append(ui.Stack([
            ui.Toggle(label=label, param_name=key, value=is_on),
            ui.Tooltip(content=tip,
                       children=ui.Icon("Info", size=13, color="text-gray-400")),
        ], direction="horizontal", gap=2, align="center"))
    return rows


# ─── Section builders ─────────────────────────────────────────────────────── #

def _onboarding(has_grp: bool, has_prf: bool, has_mon: bool) -> ui.UINode:
    if has_grp and has_prf and has_mon:
        return ui.Alert(type="success", message="All set — groups, profiles, and monitors created.")
    steps = [
        ui.Text(content="✓ Domain group created" if has_grp
                else "① Add a domain group — enter domains to monitor",
                variant="caption"),
        ui.Text(content="✓ Check profile created" if has_prf
                else "② Create a check profile — choose which checks to run",
                variant="caption"),
        ui.Text(content="✓ Monitor created" if has_mon
                else "③ Create a monitor — link group + profile and set schedule",
                variant="caption"),
    ]
    return ui.Stack(steps, gap=1)


def _groups_section(grp_data: list) -> ui.UINode:
    n = len(grp_data)
    if n >= 5:
        create_form: ui.UINode = ui.Alert(type="info", message="5/5 groups used — delete one to add more.")
    else:
        create_form = ui.Form(
            action="create_domain_group", submit_label="Create Group",
            children=[
                ui.Input(placeholder="Group name — e.g. Production, Staging", param_name="name"),
                ui.Text(content="Domains", variant="label"),
                ui.TagInput(
                    values=[],
                    placeholder="domain.com — press Enter or Space to add",
                    param_name="domains",
                ),
                ui.Text(content="Max 20 domains per group", variant="caption"),
            ],
        )

    items = []
    for g in grp_data:
        domains = g.data.get("domains", [])
        edit_form = ui.Form(
            action="update_domain_group", submit_label="Save Changes",
            defaults={"group_id": g.id},
            children=[
                ui.Input(value=g.data["name"], param_name="name", placeholder="Group name"),
                ui.Text(content="Domains", variant="label"),
                ui.TagInput(values=domains,
                            placeholder="add domain and press Enter...",
                            param_name="domains"),
            ],
        )
        items.append(ui.ListItem(
            id=g.id,
            title=g.data["name"],
            subtitle=f"{len(domains)} domain(s): {', '.join(domains[:3])}" +
                     ("…" if len(domains) > 3 else ""),
            icon="Globe",
            expandable=True,
            expanded_content=[edit_form],
            actions=[{
                "icon": "Trash2", "label": "Delete",
                "on_click": ui.Call("delete_domain_group", group_id=g.id),
                "confirm": f"Delete '{g.data['name']}' and all its monitors?",
            }],
        ))

    grp_list: ui.UINode = (ui.List(items=items) if items
                           else ui.Empty(message="No groups yet", icon="Globe"))
    return ui.Stack([
        ui.Divider(label=f"DOMAIN GROUPS  {n}/5"),
        ui.Accordion(sections=[{"id": "new_grp", "title": "+ Add Group", "children": [create_form]}]),
        grp_list,
    ], gap=2)


def _profiles_section(prf_data: list) -> ui.UINode:
    n = len(prf_data)
    if n >= 5:
        create_form: ui.UINode = ui.Alert(type="info", message="5/5 profiles used — delete one to add more.")
    else:
        create_form = ui.Form(
            action="create_check_profile", submit_label="Create Profile",
            children=[
                ui.Input(placeholder="Profile name — e.g. Full Audit, Quick SSL",
                         param_name="name"),
                ui.Text(content="Which checks to run (select at least 1, max 5)",
                        variant="label"),
                *_check_toggles(),
            ],
        )

    items = []
    for p in prf_data:
        checks = p.data.get("checks", [])
        items.append(ui.ListItem(
            id=p.id,
            title=p.data["name"],
            subtitle=", ".join(checks) if checks else "—",
            icon="CheckSquare",
            actions=[{
                "icon": "Trash2", "label": "Delete",
                "on_click": ui.Call("delete_check_profile", profile_id=p.id),
                "confirm": f"Delete '{p.data['name']}' and all its monitors?",
            }],
        ))

    prf_list: ui.UINode = (ui.List(items=items) if items
                           else ui.Empty(message="No profiles yet", icon="CheckSquare"))
    return ui.Stack([
        ui.Divider(label=f"CHECK PROFILES  {n}/5"),
        ui.Accordion(sections=[{"id": "new_prf", "title": "+ Add Profile", "children": [create_form]}]),
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
        create_form = ui.Alert(type="info", message="5/5 monitors used — delete one to add more.")
    else:
        create_form = ui.Form(
            action="create_monitor", submit_label="Create Monitor",
            children=[
                ui.Input(placeholder="Monitor name", param_name="name"),
                ui.Select(options=[{"value": g.id, "label": g.data["name"]}
                                   for g in grp_data],
                          placeholder="Domain group…", param_name="group_id"),
                ui.Select(options=[{"value": p.id, "label": p.data["name"]}
                                   for p in prf_data],
                          placeholder="Check profile…", param_name="profile_id"),
                ui.Select(options=INTERVAL_OPTS, value="24", param_name="interval_hours"),
            ],
        )

    items = []
    for m in mon_data:
        grp_name = grp_map.get(m.data.get("group_id", ""), "—")
        items.append(ui.ListItem(
            id=m.id,
            title=m.data["name"],
            subtitle=f"{grp_name} · {fmt_interval(m.data['interval_hours'])}",
            icon="Activity",
            actions=[{
                "icon": "Trash2", "label": "Delete",
                "on_click": ui.Call("delete_monitor", monitor_id=m.id),
                "confirm": f"Delete monitor '{m.data['name']}'?",
            }],
        ))

    mon_list: ui.UINode = (ui.List(items=items) if items
                           else ui.Empty(message="No monitors yet", icon="Activity"))
    return ui.Stack([
        ui.Divider(label=f"MONITORS  {n}/5"),
        ui.Accordion(sections=[{"id": "new_mon", "title": "+ Add Monitor",
                                 "children": [create_form]}]),
        mon_list,
    ], gap=2)


# ─── Main builder ─────────────────────────────────────────────────────────── #

async def build_setup(ctx, show_form: str = "") -> ui.UINode:
    """Setup as a SlideOver — groups, profiles, monitors. Requires SDK v1.5.4+."""
    grp_page, prf_page, mon_page = await asyncio.gather(
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
    )
    has_grp = bool(grp_page.data)
    has_prf = bool(prf_page.data)
    has_mon = bool(mon_page.data)

    content = ui.Stack([
        _onboarding(has_grp, has_prf, has_mon),
        _groups_section(grp_page.data),
        _profiles_section(prf_page.data),
        _monitors_section(grp_page.data, prf_page.data, mon_page.data, has_grp, has_prf),
    ], gap=3)

    return ui.SlideOver(
        title="Web Tools Setup",
        subtitle="Domain groups · check profiles · monitors",
        width="lg",
        open=True,
        children=[content],
        on_close=ui.Call("__panel__overview"),
    )
