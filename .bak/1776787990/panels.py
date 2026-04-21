"""web-tools · Panel routing — registers @ext.panel decorators, delegates to builders."""
from __future__ import annotations

from app import ext

from panels_left     import build_sidebar
from panels_overview import build_overview
from panels_detail   import build_detail

# ─── Refresh triggers ─────────────────────────────────────────────────────── #

# Left (Scan Tool): refresh after run_scan_tool (via refresh_panels), also on
# scheduled scans completing so sidebar results don't go stale if open
_LEFT_REFRESH  = "on_event:scan.tool"

# Right (Monitors): refresh when scheduler runs a monitor scan (status update)
_RIGHT_REFRESH = "on_event:scan.completed"


# ─── Panel handlers ───────────────────────────────────────────────────────── #

@ext.panel("sidebar", slot="left", title="Web Tools", icon="Globe",
           refresh=_LEFT_REFRESH)
async def panel_sidebar(ctx, view: str = "domain", **kwargs):
    """Left panel: Domain Scan / IP Scan (tab buttons)."""
    return await build_sidebar(ctx, view=view)


@ext.panel("overview", slot="right", title="Domain Health", icon="Activity",
           refresh=_RIGHT_REFRESH)
async def panel_overview(ctx, view: str = "monitors", **kwargs):
    """Right panel: Monitors view or New Monitor view (manual tab buttons)."""
    return await build_overview(ctx, view=view)


@ext.panel("detail", slot="right", title="Monitor Detail", icon="BarChart2",
           refresh=_RIGHT_REFRESH)
async def panel_detail(ctx, monitor_id: str = "", **kwargs):
    """Right panel: per-monitor scan results, domain list, settings."""
    if not monitor_id:
        return await build_overview(ctx)
    return await build_detail(ctx, monitor_id)
