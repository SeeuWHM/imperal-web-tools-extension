"""web-tools · Left sidebar — Scan Tool: on-demand multi-domain checks."""
from __future__ import annotations

from imperal_sdk import ui

from panels_ui import scan_tool_items


# ─── Scan Tool ────────────────────────────────────────────────────────────── #

_DOMAIN_RE = r"^[a-zA-Z0-9][a-zA-Z0-9.\-]+$"

async def build_sidebar(ctx) -> ui.UINode:
    """Scan Tool: TagInput domains + check toggles + results."""
    spage = await ctx.store.query("wt_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)

    # ── Scan form ─────────────────────────────────────────────────────────── #
    scan_form = ui.Form(
        action="run_scan_tool",
        submit_label="Scan",
        defaults={
            "ssl": True, "http": True, "email": True, "blacklist": True,
            "geo": False, "whois": False, "ports": False,
        },
        children=[
            ui.TagInput(
                values=[],
                placeholder="domain.com or IP — Enter, comma or space",
                param_name="domains",
                delimiters=[" ", ","],
                validate=_DOMAIN_RE,
                validate_message="Enter a valid domain or IP address",
            ),
            ui.Stack([
                ui.Toggle(label="SSL",   param_name="ssl",       value=True),
                ui.Toggle(label="HTTP",  param_name="http",      value=True),
                ui.Toggle(label="Email", param_name="email",     value=True),
                ui.Toggle(label="BL",    param_name="blacklist", value=True),
                ui.Toggle(label="Geo",   param_name="geo",       value=False),
                ui.Toggle(label="WHOIS", param_name="whois",     value=False),
                ui.Toggle(label="Ports", param_name="ports",     value=False),
            ], direction="h", gap=1, wrap=True),
        ],
    )

    # ── Last scan results ─────────────────────────────────────────────────── #
    results_section: list = []
    if spage.data:
        last   = spage.data[0].data
        r_data = last.get("results", {})
        if r_data:
            ts    = last.get("created_at", "")[:16].replace("T", " ")
            items = scan_tool_items(r_data)
            results_section = [
                ui.Divider(label=ts),
                ui.List(items=items, searchable=len(items) > 3),
            ]

    return ui.Stack([scan_form, *results_section])
