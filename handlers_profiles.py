"""web-tools · Check Profiles — CRUD handlers."""
from __future__ import annotations

import asyncio
import datetime

from pydantic import BaseModel, Field

from app import chat
from imperal_sdk import ActionResult

MAX_PROFILES = 5
MAX_CHECKS   = 5
_VALID_CHECKS = {"dns", "ssl", "whois", "http", "email", "blacklist", "geo"}


# ─── Create ───────────────────────────────────────────────────────────────── #

class CreateProfileParams(BaseModel):
    """Create check profile parameters."""
    name: str = Field(description="Profile name")
    checks: list[str] = Field(
        default_factory=list,
        description=f"Check types (max {MAX_CHECKS}): ssl/http/email/blacklist/geo/whois/dns",
    )
    checks_csv: str = Field(default="", description="Comma-separated check types (legacy)")


@chat.function("create_check_profile", action_type="write", event="profile.created",
               description=f"Create a check profile — defines which checks to run per domain "
                           f"health scan (max {MAX_PROFILES} profiles, max {MAX_CHECKS} checks each)")
async def fn_create_check_profile(ctx, params: CreateProfileParams) -> ActionResult:
    check_list = [c for c in params.checks if c in _VALID_CHECKS]
    if not check_list and params.checks_csv:
        check_list = [c.strip() for c in params.checks_csv.split(",")
                      if c.strip() in _VALID_CHECKS]
    count = await ctx.store.count("wt_profiles", where={"owner_id": ctx.user.id})
    if count >= MAX_PROFILES:
        return ActionResult.error(f"Limit reached: {MAX_PROFILES} profiles max.", retryable=False)
    if not check_list:
        return ActionResult.error(
            f"No valid checks. Allowed: {', '.join(sorted(_VALID_CHECKS))}", retryable=False)
    if len(check_list) > MAX_CHECKS:
        return ActionResult.error(
            f"Too many checks ({len(check_list)}). Max {MAX_CHECKS}.", retryable=False)
    deduped = list(dict.fromkeys(check_list))
    doc = await ctx.store.create("wt_profiles", {
        "owner_id":   ctx.user.id,
        "name":       params.name[:50],
        "checks":     deduped,
        "created_at": datetime.datetime.utcnow().isoformat(),
    })
    return ActionResult.success(
        data={"profile_id": doc.id, "name": params.name, "checks": deduped},
        summary=f"Created check profile '{params.name}': {', '.join(deduped)}",
    )


# ─── List ─────────────────────────────────────────────────────────────────── #

@chat.function("list_check_profiles", action_type="read",
               description="List all check profiles with their configured check types")
async def fn_list_check_profiles(ctx) -> ActionResult:
    page = await ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10)
    profiles = [
        {"profile_id": d.id, "name": d.data["name"], "checks": d.data["checks"]}
        for d in page.data
    ]
    return ActionResult.success(
        data={"profiles": profiles, "total": len(profiles)},
        summary=f"{len(profiles)} check profile(s)",
    )


# ─── Update ───────────────────────────────────────────────────────────────── #

class UpdateProfileParams(BaseModel):
    """Update check profile — rename or change check types."""
    profile_id: str
    name: str = Field(default="", description="New name (empty = keep current)")
    checks: list[str] = Field(default_factory=list,
                              description="New check list (empty = keep current)")


@chat.function("update_check_profile", action_type="write", event="profile.updated",
               description="Update a check profile — rename or change which checks it runs")
async def fn_update_check_profile(ctx, params: UpdateProfileParams) -> ActionResult:
    doc = await ctx.store.get("wt_profiles", params.profile_id)
    if not doc or doc.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Check profile not found.", retryable=False)
    patch: dict = {}
    if params.checks:
        check_list = [c for c in params.checks if c in _VALID_CHECKS]
        if not check_list:
            return ActionResult.error(
                f"No valid checks. Allowed: {', '.join(sorted(_VALID_CHECKS))}", retryable=False)
        if len(check_list) > MAX_CHECKS:
            return ActionResult.error(f"Too many checks. Max {MAX_CHECKS}.", retryable=False)
        patch["checks"] = list(dict.fromkeys(check_list))
    if params.name:
        patch["name"] = params.name[:50]
    if not patch:
        return ActionResult.error("Nothing to update.", retryable=False)
    updated = await ctx.store.update("wt_profiles", params.profile_id, patch)
    checks_str = ", ".join(updated.data.get("checks", []))
    return ActionResult.success(
        data={"profile_id": params.profile_id, "name": updated.data["name"],
              "checks": updated.data.get("checks", [])},
        summary=f"Updated profile '{updated.data['name']}': {checks_str}",
    )


# ─── Delete ───────────────────────────────────────────────────────────────── #

class DeleteProfileParams(BaseModel):
    """Delete check profile parameters."""
    profile_id: str


@chat.function("delete_check_profile", action_type="destructive", event="profile.deleted",
               description="Delete a check profile and all monitors that use it")
async def fn_delete_check_profile(ctx, params: DeleteProfileParams) -> ActionResult:
    doc = await ctx.store.get("wt_profiles", params.profile_id)
    if not doc or doc.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Check profile not found.", retryable=False)
    name = doc.data["name"]
    await ctx.store.delete("wt_profiles", params.profile_id)
    mon_page = await ctx.store.query("wt_monitors",
                                     where={"owner_id": ctx.user.id,
                                            "profile_id": params.profile_id},
                                     limit=10)

    async def _del_mon(m):
        snaps = await ctx.store.query("wt_snapshots",
                                      where={"owner_id": ctx.user.id, "monitor_id": m.id},
                                      limit=100)
        await asyncio.gather(*[ctx.store.delete("wt_snapshots", s.id) for s in snaps.data])
        await ctx.store.delete("wt_monitors", m.id)

    await asyncio.gather(*[_del_mon(m) for m in mon_page.data])
    return ActionResult.success(
        data={"profile_id": params.profile_id, "monitors_removed": len(mon_page.data)},
        summary=f"Deleted profile '{name}' and {len(mon_page.data)} monitor(s)",
    )
