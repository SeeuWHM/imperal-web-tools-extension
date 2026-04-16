"""web-tools · Setup panel — Stack layout (no SlideOver) with sticky close header.

Uses ui.MultiSelect for check profiles (direct Form child — reliable).
Uses ui.TagInput for domain groups (fixed in SDK v1.5.4).

Why Stack, not SlideOver: SlideOver re-animates on every panel refresh (e.g. after
group.created fires), making it look like the popup closes and reopens. Stack
re-renders in place — stays open between actions, closes only when user clicks ✕.
"""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import INTERVAL_OPTS, fmt_interval

# ─── Check options for MultiSelect ───────────────────────────────────────── #

_CHECK_OPTS = [
    {"value": "ssl",       "label": "SSL Certificate — grade A-F, expiry days"},
    {"value": "http",      "label": "HTTP Headers — security grade A-F"},
    {"value": "email",     "label": "Email Delivery — SPF · DMARC · DKIM"},
    {"value": "blacklist", "label": "Blacklist — 30 DNSBL lists"},
    {"value": "geo",       "label": "Geo Probe — EU · US · SG · MD"},
    {"value": "whois",     "label": "WHOIS — registrar, expiry date"},
    {"value": "dns",       "label": "DNS Records — A · MX · NS · TXT"},
]
_DEFAULT_CHECKS = ["ssl", "http", "email", "blacklist"]


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
                ui.Input(placeholder="Group name — e.g. Production, Staging",
                         param_name="name"),
                ui.Text(content="Domains", variant="label"),
                ui.TagInput(
                    values=[],
                    placeholder="domain.com — press Enter to add",
                    param_name="domains",
                ),
                ui.Text(content="Max 20 domains · press Enter to add each domain",
                        variant="caption"),
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
                ui.Input(value=g.data["name"], param_name="name",
                         placeholder="Group name"),
                ui.Text(content="Domains", variant="label"),
                ui.TagInput(values=domains,
                            placeholder="add domain, press Enter…",
                            param_name="domains"),
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
            children=[
                ui.Input(placeholder="Profile name — e.g. Full Audit, Quick SSL",
                         param_name="name"),
                ui.Text(content="Checks to run (select at least 1, max 5)",
                        variant="label"),
                ui.MultiSelect(
                    options=_CHECK_OPTS,
                    values=_DEFAULT_CHECKS,
                    placeholder="Select check types…",
                    param_name="checks",
                ),
            ],
        )

    items = []
    for p in prf_data:
        checks = p.data.get("checks", [])
        edit_form = ui.Form(
            action="update_check_profile", submit_label="Save",
            defaults={"profile_id": p.id},
            children=[
                ui.Input(value=p.data["name"], param_name="name",
                         placeholder="Profile name"),
                ui.Text(content="Checks to run", variant="label"),
                ui.MultiSelect(
                    options=_CHECK_OPTS,
                    values=checks,
                    placeholder="Select check types…",
                    param_name="checks",
                ),
            ],
        )
        items.append(ui.ListItem(
            id=p.id,
            title=p.data["name"],
            subtitle=", ".join(checks) if checks else "—",
            icon="CheckSquare",
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
        else ui.Empty(message="No profiles yet", icon="CheckSquare")
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
                ui.Input(placeholder="Monitor name", param_name="name"),
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

async def build_setup(ctx, show_form: str = "") -> ui.UINode:
    """Setup panel as Stack (not SlideOver) — stays open on refresh, closes on ✕ only."""
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
        ui.Button("Close", icon="X", variant="ghost", size="sm",
                  on_click=ui.Call("__panel__overview")),
    ], direction="horizontal", justify="between", align="center", sticky=True)

    return ui.Stack([
        header,
        _onboarding(has_grp, has_prf, has_mon),
        _groups_section(grp_page.data),
        _profiles_section(prf_page.data),
        _monitors_section(grp_page.data, prf_page.data, mon_page.data,
                          has_grp, has_prf),
    ], gap=3)
