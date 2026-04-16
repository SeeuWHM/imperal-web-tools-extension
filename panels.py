"""web-tools · Panel routing — registers @ext.panel decorators, delegates to builders."""
from __future__ import annotations

from app import ext

from panels_left     import build_sidebar
from panels_overview import build_overview
from panels_detail   import build_detail
from panels_setup    import build_setup

# ─── Refresh triggers ─────────────────────────────────────────────────────── #

_LEFT_REFRESH = (
    "on_event:scan.completed,monitor.created,monitor.deleted,monitor.updated,"
    "group.created,group.deleted,group.updated,profile.created,profile.deleted"
)
# Right panel handles BOTH overview and setup (show_setup param).
# refreshAll() after any action preserves show_setup via param merging —
# so setup stays visible after saves/deletes without navigating away.
_RIGHT_REFRESH = (
    "on_event:scan.completed,monitor.created,monitor.deleted,monitor.updated,"
    "quick.completed,group.created,group.deleted,group.updated,"
    "profile.created,profile.deleted,profile.updated"
)
_SETUP_REFRESH = ""  # Kept but unused — setup now lives inside panel_overview


# ─── Panel handlers ───────────────────────────────────────────────────────── #

@ext.panel("sidebar", slot="left", title="Web Tools", icon="Globe",
           refresh=_LEFT_REFRESH)
async def panel_sidebar(ctx, **kwargs):
    """Left sidebar: health summary + monitor navigation."""
    return await build_sidebar(ctx)


@ext.panel("overview", slot="right", title="Domain Health", icon="Activity",
           refresh=_RIGHT_REFRESH)
async def panel_overview(ctx, show_setup: str = "", **kwargs):
    """Right: overview dashboard, OR setup when show_setup='1'.

    Setup lives here so refreshAll() after any action preserves show_setup param
    via param merging — setup stays open between saves/deletes.
    """
    if show_setup:
        return await build_setup(ctx)
    return await build_overview(ctx)


@ext.panel("detail", slot="right", title="Monitor Detail", icon="BarChart2",
           refresh=_RIGHT_REFRESH)
async def panel_detail(ctx, monitor_id: str = "", **kwargs):
    """Right: per-monitor pie chart, domain list, settings."""
    if not monitor_id:
        return await build_overview(ctx)
    return await build_detail(ctx, monitor_id)


@ext.panel("setup", slot="right", title="Setup", icon="Settings",
           refresh=_SETUP_REFRESH)
async def panel_setup(ctx, show_form: str = "", **kwargs):
    """Right: onboarding wizard, domain groups, check profiles."""
    return await build_setup(ctx, show_form)
