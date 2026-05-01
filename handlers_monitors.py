"""web-tools · Domain Health Monitors — CRUD + atomic create-full."""
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
    count = await ctx.store.count("wt_monitors", where={"owner_id": ctx.user.imperal_id})
    if count >= MAX_MONITORS:
        return ActionResult.error(f"Limit reached: {MAX_MONITORS} monitors max.", retryable=False)
    grp = await ctx.store.get("wt_groups", params.group_id)
    if not grp or grp.data.get("owner_id") != ctx.user.imperal_id:
        return ActionResult.error("Domain group not found.", retryable=False)
    prf = await ctx.store.get("wt_profiles", params.profile_id)
    if not prf or prf.data.get("owner_id") != ctx.user.imperal_id:
        return ActionResult.error("Check profile not found.", retryable=False)
    interval = max(1, params.interval_hours)
    doc = await ctx.store.create("wt_monitors", {
        "owner_id":         ctx.user.imperal_id,
        "name":             params.name[:50],
        "group_id":         params.group_id,
        "profile_id":       params.profile_id,
        "interval_hours":   interval,
        "enabled":          True,
        "last_run_at":      None,
        "last_snapshot_id": None,
        "created_at":       datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    return ActionResult.success(
        data={"monitor_id": doc.id, "name": params.name,
              "group": grp.data["name"], "profile": prf.data["name"], "interval_hours": interval},
        summary=f"Created domain health monitor '{params.name}' — {grp.data['name']} every {interval}h",
        refresh_panels=["__panel__sidebar", "__panel__overview"],
    )


# ─── List Monitors ─────────────────────────────────────────────────────────── #

@chat.function("list_monitors", action_type="read",
               description="List all domain health monitors with group, check profile, interval, and last scan time")
async def fn_list_monitors(ctx) -> ActionResult:
    page = await ctx.store.query("wt_monitors", where={"owner_id": ctx.user.imperal_id}, limit=10)
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
    if not doc or doc.data.get("owner_id") != ctx.user.imperal_id:
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
        refresh_panels=["__panel__sidebar", "__panel__overview"],
    )


# ─── Delete Monitor ─────────────────────────────────────────────────────────── #

class DeleteMonitorParams(BaseModel):
    """Delete domain health monitor parameters."""
    monitor_id: str


@chat.function("delete_monitor", action_type="destructive", event="monitor.deleted",
               description="Delete a domain health monitor (does not delete the domain group or check profile)")
async def fn_delete_monitor(ctx, params: DeleteMonitorParams) -> ActionResult:
    doc = await ctx.store.get("wt_monitors", params.monitor_id)
    if not doc or doc.data.get("owner_id") != ctx.user.imperal_id:
        return ActionResult.error("Monitor not found.", retryable=False)
    name = doc.data["name"]
    # Cascade: delete all snapshots for this monitor
    snap_page = await ctx.store.query("wt_snapshots",
                                      where={"owner_id": ctx.user.imperal_id,
                                             "monitor_id": params.monitor_id},
                                      limit=200)
    if snap_page.data:
        await asyncio.gather(*[ctx.store.delete("wt_snapshots", s.id)
                                for s in snap_page.data])
    await ctx.store.delete("wt_monitors", params.monitor_id)
    return ActionResult.success(
        data={"monitor_id": params.monitor_id},
        summary=f"Deleted domain health monitor '{name}'",
        refresh_panels=["__panel__sidebar", "__panel__overview"],
    )


# ─── Create Monitor Full (panel: atomic group + profile + monitor) ─────────── #

_VALID_CHECKS = {"ssl", "http", "email", "blacklist", "geo", "whois", "ports"}


class CreateMonitorFullParams(BaseModel):
    name:           str       = Field(description="Monitor name")
    domains:        list[str] = Field(default_factory=list, description="Domains to monitor (max 20)")
    interval_hours: int       = Field(default=24, description="Scan interval in hours")
    # Chat callers pass checks as list; panel form passes individual boolean toggles
    # Defaults match panel form visual defaults (sdk may omit unchanged toggle values)
    checks:    list[str] = Field(default_factory=list,
                                  description="Check types (chat API)")
    ssl:       bool = Field(default=True)
    http:      bool = Field(default=True)
    email:     bool = Field(default=True)
    blacklist: bool = Field(default=True)
    geo:       bool = Field(default=False)
    whois:     bool = Field(default=False)


@chat.function("create_monitor_full", action_type="write", event="monitor.created",
               description="Create a domain health monitor from the panel — provide name, domains, checks and interval. Atomically creates group, profile and monitor in one step.")
async def fn_create_monitor_full(ctx, params: CreateMonitorFullParams) -> ActionResult:
    count = await ctx.store.count("wt_monitors", where={"owner_id": ctx.user.imperal_id})
    if count >= MAX_MONITORS:
        return ActionResult.error(f"Limit reached: {MAX_MONITORS} monitors max.", retryable=False)

    name = (params.name or "").strip()[:50]
    if not name:
        return ActionResult.error("Monitor name is required.", retryable=False)

    domains = list(dict.fromkeys(
        d.strip().lower() for d in (params.domains or []) if d.strip()
    ))[:20]
    if not domains:
        return ActionResult.error("Add at least one domain.", retryable=False)

    # Build checks: from list (chat) or from boolean toggles (panel form)
    checks = list(dict.fromkeys(
        c for c in (params.checks or [
            k for k, v in {
                "ssl": params.ssl, "http": params.http, "email": params.email,
                "blacklist": params.blacklist, "geo": params.geo, "whois": params.whois,
            }.items() if v
        ]) if c in _VALID_CHECKS
    ))
    if not checks:
        return ActionResult.error("Select at least one check type.", retryable=False)

    interval = max(1, int(params.interval_hours or 24))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    grp = await ctx.store.create("wt_groups", {
        "owner_id": ctx.user.imperal_id, "name": name,
        "domains": domains, "description": "", "created_at": now,
    })
    prf = await ctx.store.create("wt_profiles", {
        "owner_id": ctx.user.imperal_id, "name": name,
        "checks": checks, "created_at": now,
    })
    doc = await ctx.store.create("wt_monitors", {
        "owner_id": ctx.user.imperal_id, "name": name,
        "group_id": grp.id, "profile_id": prf.id,
        "interval_hours": interval, "enabled": True,
        "last_run_at": None, "last_snapshot_id": None, "created_at": now,
    })
    return ActionResult.success(
        data={"monitor_id": doc.id, "name": name,
              "domains": len(domains), "checks": checks, "interval_hours": interval},
        summary=f"Created monitor '{name}' — {len(domains)} domain(s), every {interval}h",
        refresh_panels=["__panel__sidebar", "__panel__overview"],
    )
