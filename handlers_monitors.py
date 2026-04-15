"""web-tools · Domain Health Monitors — CRUD + update."""
from __future__ import annotations

import asyncio
import datetime

from pydantic import BaseModel, Field

from app import chat
from imperal_sdk import ActionResult

MAX_MONITORS = 5

# ─── Create Monitor ────────────────────────────────────────────────────────── #

class CreateMonitorParams(BaseModel):
    """Create domain health monitor parameters."""
    name: str = Field(description="Monitor name")
    group_id: str = Field(description="Domain group ID to monitor")
    profile_id: str = Field(description="Check profile ID defining which checks to run")
    interval_hours: int = Field(default=24, description="How often to run checks, in hours (1/6/12/24/48/168)")


@chat.function("create_monitor", action_type="write", event="monitor.created",
               description=(
                   f"Create a domain health monitor — saves a wt_monitors record that runs "
                   f"DNS/SSL/HTTP/email checks on a domain group at a recurring interval. "
                   f"Requires an existing domain group (group_id) and check profile (profile_id). "
                   f"NOT an automation rule. Max {MAX_MONITORS} monitors."
               ))
async def fn_create_monitor(ctx, params: CreateMonitorParams) -> ActionResult:
    count = await ctx.store.count("wt_monitors", where={"owner_id": ctx.user.id})
    if count >= MAX_MONITORS:
        return ActionResult.error(f"Limit reached: {MAX_MONITORS} monitors max.", retryable=False)
    grp = await ctx.store.get("wt_groups", params.group_id)
    if not grp or grp.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Domain group not found.", retryable=False)
    prf = await ctx.store.get("wt_profiles", params.profile_id)
    if not prf or prf.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Check profile not found.", retryable=False)
    interval = max(1, params.interval_hours)
    doc = await ctx.store.create("wt_monitors", {
        "owner_id":         ctx.user.id,
        "name":             params.name[:50],
        "group_id":         params.group_id,
        "profile_id":       params.profile_id,
        "interval_hours":   interval,
        "enabled":          True,
        "last_run_at":      None,
        "last_snapshot_id": None,
        "created_at":       datetime.datetime.utcnow().isoformat(),
    })
    return ActionResult.success(
        data={"monitor_id": doc.id, "name": params.name,
              "group": grp.data["name"], "profile": prf.data["name"], "interval_hours": interval},
        summary=f"Created domain health monitor '{params.name}' — {grp.data['name']} every {interval}h",
    )


# ─── List Monitors ─────────────────────────────────────────────────────────── #

@chat.function("list_monitors", action_type="read",
               description="List all domain health monitors with group, check profile, interval, and last scan time")
async def fn_list_monitors(ctx) -> ActionResult:
    page = await ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10)
    monitors = [
        {
            "monitor_id":       d.id,
            "name":             d.data["name"],
            "group_id":         d.data["group_id"],
            "profile_id":       d.data["profile_id"],
            "interval_hours":   d.data["interval_hours"],
            "enabled":          d.data["enabled"],
            "last_run_at":      d.data.get("last_run_at"),
            "last_snapshot_id": d.data.get("last_snapshot_id"),
        }
        for d in page.data
    ]
    return ActionResult.success(
        data={"monitors": monitors, "total": len(monitors)},
        summary=f"{len(monitors)} domain health monitor(s)",
    )


# ─── Update Monitor ─────────────────────────────────────────────────────────── #

class UpdateMonitorParams(BaseModel):
    """Update monitor — rename or change interval."""
    monitor_id: str
    name: str = Field(default="", description="New name (empty = keep current)")
    interval_hours: int = Field(default=0, description="New interval in hours (0 = keep current)")


@chat.function("update_monitor", action_type="write", event="monitor.updated",
               description="Update a domain health monitor — rename or change check interval")
async def fn_update_monitor(ctx, params: UpdateMonitorParams) -> ActionResult:
    doc = await ctx.store.get("wt_monitors", params.monitor_id)
    if not doc or doc.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Monitor not found.", retryable=False)
    patch: dict = {}
    if params.name:
        patch["name"] = params.name[:50]
    if params.interval_hours > 0:
        patch["interval_hours"] = max(1, params.interval_hours)
    if not patch:
        return ActionResult.error("Nothing to update — provide name or interval_hours.", retryable=False)
    updated = await ctx.store.update("wt_monitors", params.monitor_id, patch)
    name = updated.data["name"]
    interval = updated.data["interval_hours"]
    return ActionResult.success(
        data={"monitor_id": params.monitor_id, "name": name, "interval_hours": interval},
        summary=f"Updated monitor '{name}' — every {interval}h",
    )


# ─── Delete Monitor ─────────────────────────────────────────────────────────── #

class DeleteMonitorParams(BaseModel):
    """Delete domain health monitor parameters."""
    monitor_id: str


@chat.function("delete_monitor", action_type="destructive", event="monitor.deleted",
               description="Delete a domain health monitor (does not delete the domain group or check profile)")
async def fn_delete_monitor(ctx, params: DeleteMonitorParams) -> ActionResult:
    doc = await ctx.store.get("wt_monitors", params.monitor_id)
    if not doc or doc.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Monitor not found.", retryable=False)
    name = doc.data["name"]
    await ctx.store.delete("wt_monitors", params.monitor_id)
    return ActionResult.success(
        data={"monitor_id": params.monitor_id},
        summary=f"Deleted domain health monitor '{name}'",
    )
