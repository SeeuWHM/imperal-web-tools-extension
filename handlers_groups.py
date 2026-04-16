"""web-tools · Domain Groups and Check Profiles — CRUD handlers."""
from __future__ import annotations

import asyncio
import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app import chat
from imperal_sdk import ActionResult

# ─── Limits ───────────────────────────────────────────────────────────────── #

MAX_GROUPS   = 5
MAX_DOMAINS  = 20
MAX_PROFILES = 5
MAX_CHECKS   = 5

# ─── Domain Groups ────────────────────────────────────────────────────────── #

class CreateGroupParams(BaseModel):
    """Create domain group parameters."""
    name: str = Field(description="Group name")
    domains: list[str] = Field(default_factory=list,
                               description=f"Domain names (max {MAX_DOMAINS}). From TagInput or chat.")
    domains_csv: str = Field(default="",
                             description="Comma/newline-separated domains (legacy CSV fallback)")
    description: str = ""


@chat.function("create_domain_group", action_type="write", event="group.created",
               description=f"Create a domain group — organizes domains for monitoring (max {MAX_GROUPS} groups, max {MAX_DOMAINS} domains each)")
async def fn_create_domain_group(ctx, params: CreateGroupParams) -> ActionResult:
    # Panel form sends domains_csv (plain text); chat sends domains (list)
    domain_list = params.domains
    if not domain_list and params.domains_csv:
        domain_list = [d.strip() for d in
                       params.domains_csv.replace("\n", ",").split(",") if d.strip()]
    count = await ctx.store.count("wt_groups", where={"owner_id": ctx.user.id})
    if count >= MAX_GROUPS:
        return ActionResult.error(f"Limit reached: {MAX_GROUPS} domain groups max. Delete one first.", retryable=False)
    if not domain_list:
        return ActionResult.error("At least one domain is required.", retryable=False)
    if len(domain_list) > MAX_DOMAINS:
        return ActionResult.error(f"Too many domains ({len(domain_list)}). Max {MAX_DOMAINS} per group.", retryable=False)
    doc = await ctx.store.create("wt_groups", {
        "owner_id":    ctx.user.id,
        "name":        params.name[:50],
        "domains":     domain_list,
        "description": params.description,
        "created_at":  datetime.datetime.utcnow().isoformat(),
    })
    return ActionResult.success(
        data={"group_id": doc.id, "name": params.name, "domains": params.domains},
        summary=f"Created domain group '{params.name}' with {len(domain_list)} domain(s)",
    )


class UpdateGroupParams(BaseModel):
    """Update domain group parameters."""
    group_id: str
    name: str = Field(default="", description="New name (empty = keep current)")
    domains: list[str] = Field(default_factory=list,
                               description="Full replacement domain list (from TagInput panel edit)")
    add_domains: list[str] = Field(default_factory=list, description="Domains to add (chat)")
    remove_domains: list[str] = Field(default_factory=list, description="Domains to remove (chat)")


@chat.function("update_domain_group", action_type="write", event="group.updated",
               description=f"Update a domain group — rename, add or remove domains (max {MAX_DOMAINS} total)")
async def fn_update_domain_group(ctx, params: UpdateGroupParams) -> ActionResult:
    doc = await ctx.store.get("wt_groups", params.group_id)
    if not doc or doc.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Domain group not found.", retryable=False)
    if params.domains:
        # Full replacement from TagInput panel edit
        new_domains = [d.strip() for d in params.domains if d.strip()]
    elif params.add_domains or params.remove_domains:
        # Incremental update from chat
        existing = set(doc.data["domains"])
        existing -= set(params.remove_domains)
        existing |= set(params.add_domains)
        new_domains = list(existing)
    else:
        new_domains = doc.data["domains"]  # no domain change
    if len(new_domains) > MAX_DOMAINS:
        return ActionResult.error(f"Too many domains ({len(new_domains)}). Max {MAX_DOMAINS}.", retryable=False)
    patch: dict = {"domains": new_domains}
    if params.name:
        patch["name"] = params.name[:50]
    updated = await ctx.store.update("wt_groups", params.group_id, patch)
    return ActionResult.success(
        data={"group_id": params.group_id, "name": updated.data["name"], "domains": new_domains},
        summary=f"Updated domain group '{updated.data['name']}' — {len(new_domains)} domain(s)",
    )


@chat.function("list_domain_groups", action_type="read",
               description="List all domain groups with their domains and count")
async def fn_list_domain_groups(ctx) -> ActionResult:
    page = await ctx.store.query("wt_groups", where={"owner_id": ctx.user.id}, limit=10)
    groups = [
        {"group_id": d.id, "name": d.data["name"],
         "domains": d.data["domains"], "domain_count": len(d.data["domains"])}
        for d in page.data
    ]
    return ActionResult.success(
        data={"groups": groups, "total": len(groups)},
        summary=f"{len(groups)} domain group(s)",
    )


class DeleteGroupParams(BaseModel):
    """Delete domain group parameters."""
    group_id: str


@chat.function("delete_domain_group", action_type="destructive", event="group.deleted",
               description="Delete a domain group and all monitors that use it")
async def fn_delete_domain_group(ctx, params: DeleteGroupParams) -> ActionResult:
    doc = await ctx.store.get("wt_groups", params.group_id)
    if not doc or doc.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Domain group not found.", retryable=False)
    name = doc.data["name"]
    await ctx.store.delete("wt_groups", params.group_id)

    mon_page = await ctx.store.query("wt_monitors",
                                     where={"owner_id": ctx.user.id, "group_id": params.group_id},
                                     limit=10)

    async def _delete_monitor(m):
        snap_page = await ctx.store.query(
            "wt_snapshots",
            where={"owner_id": ctx.user.id, "monitor_id": m.id},
            limit=100,
        )
        await asyncio.gather(*[ctx.store.delete("wt_snapshots", s.id)
                                for s in snap_page.data])
        await ctx.store.delete("wt_monitors", m.id)

    await asyncio.gather(*[_delete_monitor(m) for m in mon_page.data])

    return ActionResult.success(
        data={"group_id": params.group_id, "monitors_removed": len(mon_page.data)},
        summary=f"Deleted group '{name}' and {len(mon_page.data)} monitor(s)",
    )


# ─── Check Profiles ───────────────────────────────────────────────────────── #

_VALID_CHECKS = {"dns", "ssl", "whois", "http", "email", "blacklist", "geo"}


class CreateProfileParams(BaseModel):
    """Create check profile parameters."""
    name: str = Field(description="Profile name")
    # Panel form: individual toggles per check type (v1.5.4 SDK)
    ssl:       bool = Field(default=False)
    http:      bool = Field(default=False)
    email:     bool = Field(default=False)
    blacklist: bool = Field(default=False)
    geo:       bool = Field(default=False)
    whois:     bool = Field(default=False)
    dns:       bool = Field(default=False)
    # Chat/AI: list of check names
    checks: list[str] = Field(default_factory=list,
                              description=f"Check types (max {MAX_CHECKS}): dns/ssl/whois/http/email/blacklist/geo")
    checks_csv: str = Field(default="", description="Comma-separated check types (legacy)")


@chat.function("create_check_profile", action_type="write", event="profile.created",
               description=f"Create a check profile — defines which diagnostics to run per domain health scan (max {MAX_PROFILES} profiles, max {MAX_CHECKS} checks each)")
async def fn_create_check_profile(ctx, params: CreateProfileParams) -> ActionResult:
    _BOOL_KEYS = ("ssl", "http", "email", "blacklist", "geo", "whois", "dns")
    # 1. Panel form: individual bool toggles
    check_list = [k for k in _BOOL_KEYS if getattr(params, k, False)]
    # 2. Chat/AI: list of check names
    if not check_list and params.checks:
        check_list = [c for c in params.checks if c in _VALID_CHECKS]
    # 3. Legacy CSV fallback
    if not check_list and params.checks_csv:
        check_list = [c.strip() for c in params.checks_csv.split(",")
                      if c.strip() in _VALID_CHECKS]
    count = await ctx.store.count("wt_profiles", where={"owner_id": ctx.user.id})
    if count >= MAX_PROFILES:
        return ActionResult.error(f"Limit reached: {MAX_PROFILES} check profiles max.", retryable=False)
    if not check_list:
        valid = ", ".join(sorted(_VALID_CHECKS))
        return ActionResult.error(
            f"No valid checks provided. Allowed: {valid}", retryable=False)
    if len(check_list) > MAX_CHECKS:
        return ActionResult.error(f"Too many checks ({len(check_list)}). Max {MAX_CHECKS}.", retryable=False)
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
                                     where={"owner_id": ctx.user.id, "profile_id": params.profile_id},
                                     limit=10)

    async def _delete_monitor(m):
        snap_page = await ctx.store.query(
            "wt_snapshots",
            where={"owner_id": ctx.user.id, "monitor_id": m.id},
            limit=100,
        )
        await asyncio.gather(*[ctx.store.delete("wt_snapshots", s.id)
                                for s in snap_page.data])
        await ctx.store.delete("wt_monitors", m.id)

    await asyncio.gather(*[_delete_monitor(m) for m in mon_page.data])

    return ActionResult.success(
        data={"profile_id": params.profile_id, "monitors_removed": len(mon_page.data)},
        summary=f"Deleted profile '{name}' and {len(mon_page.data)} monitor(s)",
    )

