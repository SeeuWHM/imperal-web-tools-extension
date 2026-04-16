"""web-tools · Right panel: setup — groups, profiles, monitors + onboarding wizard."""
from __future__ import annotations

import asyncio

from imperal_sdk import ui

from panels_ui import CHECKS_OPTS, INTERVAL_OPTS, group_items, profile_items


# ─── Setup builder ────────────────────────────────────────────────────────── #

async def build_setup(ctx, show_form: str = "") -> ui.UINode:
    """Setup view with inline accordion forms — no SlideOver (crashes frontend).
    show_form hint: 'new_group' | 'new_profile' | 'new_monitor' (reserved for future use).
    """
    grp_page, prf_page, mon_page = await asyncio.gather(
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
    )
    has_grp  = bool(grp_page.data)
    has_prf  = bool(prf_page.data)
    has_mon  = bool(mon_page.data)

    # ── Header ────────────────────────────────────────────────────────────── #
    header = ui.Stack([
        ui.Button("← Overview", icon="ArrowLeft", variant="ghost", size="sm",
                  on_click=ui.Call("__panel__overview")),
        ui.Header(text="Setup", level=3,
                  subtitle="Domain groups · Check profiles · Monitors"),
    ], direction="horizontal", gap=2, justify="between")

    # ── Onboarding timeline (shown until all 3 steps done) ───────────────── #
    wizard: list = []
    if not (has_grp and has_prf and has_mon):
        step1_col = "green" if has_grp else "gray"
        step2_col = "green" if has_prf else ("blue" if has_grp  else "gray")
        step3_col = "green" if has_mon else ("blue" if has_prf  else "gray")
        step1_ico = "CheckCircle" if has_grp else "Circle"
        step2_ico = "CheckCircle" if has_prf else "Circle"
        step3_ico = "CheckCircle" if has_mon else "Circle"

        wizard = [ui.Timeline(items=[
            {"title": "Domain Group",  "description": "Define domains to watch",
             "icon": step1_ico, "color": step1_col, "time": "Step 1"},
            {"title": "Check Profile", "description": "Choose which checks to run",
             "icon": step2_ico, "color": step2_col, "time": "Step 2"},
            {"title": "Monitor",       "description": "Set schedule and launch",
             "icon": step3_ico, "color": step3_col, "time": "Step 3"},
        ])]

    # ── Domain Groups section ─────────────────────────────────────────────── #
    grp_limit = len(grp_page.data) >= 5
    new_grp_form = ui.Form(
        action="create_domain_group", submit_label="Create Group",
        children=[
            ui.Input(placeholder="Group name", param_name="name"),
            ui.TagInput(placeholder="Type domain, press Enter...",
                        param_name="domains"),
        ],
    )
    groups_section = ui.Section(title="Domain Groups", children=[
        ui.Stack([
            ui.Text(content=f"{len(grp_page.data)}/5 groups used",
                    variant="caption"),
        ]),
        ui.Accordion(sections=[
            {"id": "new_grp", "title": "+ Add Group",
             "children": [new_grp_form if not grp_limit
                          else ui.Alert(type="info",
                                        message="Limit reached: 5 groups max.")]},
        ]),
        ui.List(items=group_items(grp_page.data)) if grp_page.data
        else ui.Empty(message="No groups yet", icon="Globe"),
    ])

    # ── Check Profiles section ────────────────────────────────────────────── #
    prf_limit = len(prf_page.data) >= 5
    new_prf_form = ui.Form(
        action="create_check_profile", submit_label="Create Profile",
        children=[
            ui.Input(placeholder="Profile name", param_name="name"),
            ui.Text(content="Select up to 5 checks:", variant="caption"),
            ui.MultiSelect(options=CHECKS_OPTS,
                           placeholder="Select checks...",
                           param_name="checks"),
        ],
    )
    profiles_section = ui.Section(title="Check Profiles", children=[
        ui.Stack([
            ui.Text(content=f"{len(prf_page.data)}/5 profiles used",
                    variant="caption"),
        ]),
        ui.Accordion(sections=[
            {"id": "new_prf", "title": "+ Add Profile",
             "children": [new_prf_form if not prf_limit
                          else ui.Alert(type="info",
                                        message="Limit reached: 5 profiles max.")]},
        ]),
        ui.List(items=profile_items(prf_page.data)) if prf_page.data
        else ui.Empty(message="No profiles yet", icon="CheckSquare"),
    ])

    # ── Monitors section ──────────────────────────────────────────────────── #
    mon_limit = len(mon_page.data) >= 5
    if not has_grp or not has_prf:
        new_mon_content: ui.UINode = ui.Alert(
            type="info",
            message="Create a domain group and check profile first.",
        )
    elif mon_limit:
        new_mon_content = ui.Alert(type="info",
                                   message="Limit reached: 5 monitors max.")
    else:
        new_mon_content = ui.Form(
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
    monitors_section = ui.Section(title="Monitors", children=[
        ui.Stack([
            ui.Text(content=f"{len(mon_page.data)}/5 monitors used",
                    variant="caption"),
        ]),
        ui.Accordion(sections=[
            {"id": "new_mon", "title": "+ Add Monitor",
             "children": [new_mon_content]},
        ]),
    ])

    return ui.Stack([
        header,
        *wizard,
        ui.Divider(),
        groups_section,
        ui.Divider(),
        profiles_section,
        ui.Divider(),
        monitors_section,
    ])
