"""web-tools · Skeleton — background monitor status refresh."""
from __future__ import annotations

import asyncio

from app import ext


@ext.skeleton(
    "web_tools",
    ttl=300,
    description="Refresh web-tools monitor statuses from last scan snapshots. "
                "Provides instant Webbee context: how many monitors are critical/warning.",
)
async def on_refresh(ctx) -> dict:
    """Load monitors + their last snapshot statuses for instant AI context."""
    try:
        page = await ctx.store.query("wt_monitors", where={"owner_id": ctx.user.imperal_id}, limit=10)
        if not page.data:
            return {"response": {
                "monitors": {}, "total": 0, "critical": 0, "warning": 0, "ok": 0,
            }}

        # Load all snapshots in parallel instead of sequentially
        snap_ids = [m.data.get("last_snapshot_id") for m in page.data]

        async def _get_snap(snap_id):
            if snap_id:
                return await ctx.store.get("wt_snapshots", snap_id)
            return None

        snaps = await asyncio.gather(*[_get_snap(sid) for sid in snap_ids])

        monitors: dict = {}
        critical = warning = ok = 0

        for m, snap in zip(page.data, snaps):
            status   = "unknown"
            summary: dict = {}
            last_run = m.data.get("last_run_at")

            if snap:
                status  = snap.data.get("status", "unknown")
                summary = snap.data.get("summary", {})

            if status == "critical":
                critical += 1
            elif status == "warning":
                warning += 1
            elif status == "ok":
                ok += 1

            monitors[m.id] = {
                "name":           m.data["name"],
                "status":         status,
                "last_run_at":    last_run,
                "interval_hours": m.data["interval_hours"],
                "summary":        summary,
            }

        return {"response": {
            "monitors": monitors,
            "total":    len(monitors),
            "critical": critical,
            "warning":  warning,
            "ok":       ok,
        }}

    except Exception as exc:
        return {"response": {
            "error": str(exc), "monitors": {}, "total": 0, "critical": 0, "warning": 0, "ok": 0,
        }}
