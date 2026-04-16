"""web-tools · Right panel: setup — groups, profiles, monitors."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import CHECKS_OPTS, INTERVAL_OPTS, group_items, profile_items


# ─── Setup builder ────────────────────────────────────────────────────────── #

async def build_setup(ctx, show_form: str = "") -> ui.UINode:
    """Setup view — domain groups, check profiles, monitors.
    Only uses confirmed-stable SDK components (Stack, Divider, Accordion,
    Form, Input, Select, TagInput, MultiSelect, List, Empty, Alert, Text, Button).
    No ui.Section / ui.Timeline — they cause e.map crashes on frontend.
    """
    grp_page, prf_page, mon_page = await asyncio.gather(
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
    )
    has_grp = bool(grp_page.data)
    has_prf = bool(prf_page.data)
    has_mon = bool(mon_page.data)

    # ── Header ────────────────────────────────────────────────────────────── #
    header = ui.Stack([
        ui.Button("← Overview", icon="ArrowLeft", variant="ghost", size="sm",
                  on_click=ui.Call("__panel__overview")),
        ui.Text(content="Setup", variant="subheading"),
    ], direction="horizontal", gap=2, justify="between")

    # ── Onboarding steps (text only — no ui.Timeline) ────────────────────── #
    onboarding: list = []
    if not (has_grp and has_prf and has_mon):
        steps = []
        steps.append(ui.Text(
            content=("✓ Domain Group created" if has_grp
                     else "① Create a Domain Group — add domains to monitor"),
            variant="caption",
        ))
        steps.append(ui.Text(
            content=("✓ Check Profile created" if has_prf
                     else "② Create a Check Profile — choose which checks to run"),
            variant="caption",
        ))
        steps.append(ui.Text(
            content=("✓ Monitor created" if has_mon
                     else "③ Create a Monitor — set schedule and launch"),
            variant="caption",
        ))
        onboarding = [ui.Stack(steps, gap=1)]

    # ── Domain Groups ─────────────────────────────────────────────────────── #
    new_grp_form: ui.UINode
    if len(grp_page.data) >= 5:
        new_grp_form = ui.Alert(type="info", message="Limit reached: 5 groups max.")
    else:
        new_grp_form = ui.Form(
            action="create_domain_group", submit_label="Create Group",
            children=[
                ui.Input(placeholder="Group name", param_name="name"),
                ui.Input(
                    placeholder="domain1.com, domain2.com, domain3.com ...",
                    param_name="domains_csv",
                ),
                ui.Text(content="Separate domains with commas (max 20)",
                        variant="caption"),
            ],
        )

    grp_list: ui.UINode = (ui.List(items=group_items(grp_page.data))
                           if grp_page.data
                           else ui.Empty(message="No groups yet", icon="Globe"))

    groups_block = ui.Stack([
        ui.Divider(label="DOMAIN GROUPS"),
        ui.Text(content=f"{len(grp_page.data)}/5 groups used", variant="caption"),
        ui.Accordion(sections=[
            {"id": "new_grp", "title": "+ Add Group",
             "children": [new_grp_form]},
        ]),
        grp_list,
    ])

    # ── Check Profiles ────────────────────────────────────────────────────── #
    new_prf_form: ui.UINode
    if len(prf_page.data) >= 5:
        new_prf_form = ui.Alert(type="info", message="Limit reached: 5 profiles max.")
    else:
        new_prf_form = ui.Form(
            action="create_check_profile", submit_label="Create Profile",
            children=[
                ui.Input(placeholder="Profile name", param_name="name"),
                ui.Input(
                    placeholder="dns, ssl, http, email, blacklist, geo, whois",
                    param_name="checks_csv",
                ),
                ui.Text(content="Comma-separated check types (max 5)",
                        variant="caption"),
            ],
        )

    prf_list: ui.UINode = (ui.List(items=profile_items(prf_page.data))
                           if prf_page.data
                           else ui.Empty(message="No profiles yet",
                                         icon="CheckSquare"))

    profiles_block = ui.Stack([
        ui.Divider(label="CHECK PROFILES"),
        ui.Text(content=f"{len(prf_page.data)}/5 profiles used", variant="caption"),
        ui.Accordion(sections=[
            {"id": "new_prf", "title": "+ Add Profile",
             "children": [new_prf_form]},
        ]),
        prf_list,
    ])

    # ── Monitors ──────────────────────────────────────────────────────────── #
    new_mon_form: ui.UINode
    if not has_grp or not has_prf:
        new_mon_form = ui.Alert(
            type="info",
            message="Create a domain group and check profile first.",
        )
    elif len(mon_page.data) >= 5:
        new_mon_form = ui.Alert(type="info", message="Limit reached: 5 monitors max.")
    else:
        new_mon_form = ui.Form(
            action="create_monitor", submit_label="Create Monitor",
            children=[
                ui.Input(placeholder="Monitor name", param_name="name"),
                ui.Select(
                    options=[{"value": g.id, "label": g.data["name"]}
                             for g in grp_page.data],
                    placeholder="Domain group...", param_name="group_id"),
                ui.Select(
                    options=[{"value": p.id, "label": p.data["name"]}
                             for p in prf_page.data],
                    placeholder="Check profile...", param_name="profile_id"),
                ui.Select(options=INTERVAL_OPTS, value="24",
                          param_name="interval_hours"),
            ],
        )

    monitors_block = ui.Stack([
        ui.Divider(label="MONITORS"),
        ui.Text(content=f"{len(mon_page.data)}/5 monitors used", variant="caption"),
        ui.Accordion(sections=[
            {"id": "new_mon", "title": "+ Add Monitor",
             "children": [new_mon_form]},
        ]),
    ])

    return ui.Stack([
        header,
        *onboarding,
        groups_block,
        profiles_block,
        monitors_block,
    ])
