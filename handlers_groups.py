"""web-tools · Domain Groups — CRUD handlers (SDK 5.2.0 / SDL)."""
from __future__ import annotations

import asyncio
import datetime
import re

from pydantic import BaseModel, Field

_DOMAIN_RE = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$'
)

from app import chat
from imperal_sdk import ActionResult
from schemas_sdl_builders import (
    DomainGroupEntity, DomainGroupPage, WtOpResult,
    build_domain_group, build_domain_group_page, build_wt_op,
)

MAX_GROUPS  = 5
MAX_DOMAINS = 20


# ─── Domain Groups ────────────────────────────────────────────────────────── #

class CreateGroupParams(BaseModel):
    """Create domain group parameters."""
    name: str = Field(description="Group name")
    domains: list[str] = Field(default_factory=list,
                               description=f"Domain names (max {MAX_DOMAINS}). From TagInput or chat.")
    domains_csv: str = Field(default="",
                             description="Comma/newline-separated domains (legacy CSV fallback)")
    description: str = ""


class EmptyParams(BaseModel):
    """No parameters — satisfies V17 for parameterless handlers."""


@chat.function("create_domain_group", action_type="write", event="group.created",
               effects=["create:domain_group"],
               data_model=DomainGroupEntity,
               description=f"Create a named group of domains for monitoring (max {MAX_GROUPS} groups, max {MAX_DOMAINS} domains each). Required before creating a monitor with create_monitor.")
async def fn_create_domain_group(ctx, params: CreateGroupParams) -> ActionResult:
    """Comma/newline-separated domains (legacy CSV fallback)"""
    domain_list = params.domains
    if not domain_list and params.domains_csv:
        domain_list = [d.strip() for d in
                       params.domains_csv.replace("\n", ",").split(",") if d.strip()]
    count = await ctx.store.count("wt_groups", where={"owner_id": ctx.user.imperal_id})
    if count >= MAX_GROUPS:
        return ActionResult.error(f"Limit reached: {MAX_GROUPS} domain groups max. Delete one first.", retryable=False)
    if not domain_list:
        return ActionResult.error("At least one domain is required.", retryable=False)
    invalid = [d for d in domain_list if not _DOMAIN_RE.match(d)]
    if invalid:
        examples = ", ".join(invalid[:3]) + ("…" if len(invalid) > 3 else "")
        return ActionResult.error(
            f"Invalid domain format: {examples}. Expected: domain.tld (e.g. example.com)",
            retryable=False,
        )
    if len(domain_list) > MAX_DOMAINS:
        return ActionResult.error(f"Too many domains ({len(domain_list)}). Max {MAX_DOMAINS} per group.", retryable=False)
    doc = await ctx.store.create("wt_groups", {
        "owner_id":    ctx.user.imperal_id,
        "name":        params.name[:50],
        "domains":     domain_list,
        "description": params.description,
        "created_at":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })
    return ActionResult.success(
        data=build_domain_group(doc.id, params.name, domain_list),
        summary=f"Created domain group '{params.name}' with {len(domain_list)} domain(s)",
        refresh_panels=["sidebar", "overview"],
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
               effects=["update:domain_group"],
               id_projection="group_id",
               data_model=DomainGroupEntity,
               description=f"Add, remove or replace domains in an existing group, or rename it (max {MAX_DOMAINS} domains). Use list_domain_groups first to get the group_id.")
async def fn_update_domain_group(ctx, params: UpdateGroupParams) -> ActionResult:
    """Domains to remove (chat)"""
    doc = await ctx.store.get("wt_groups", params.group_id)
    if not doc or doc.data.get("owner_id") != ctx.user.imperal_id:
        return ActionResult.error("Domain group not found.", retryable=False)
    if params.domains:
        new_domains = [d.strip() for d in params.domains if d.strip()]
    elif params.add_domains or params.remove_domains:
        existing = set(doc.data["domains"])
        existing -= set(params.remove_domains)
        existing |= set(params.add_domains)
        new_domains = list(existing)
    else:
        new_domains = doc.data["domains"]
    if new_domains:
        invalid = [d for d in new_domains if not _DOMAIN_RE.match(d)]
        if invalid:
            examples = ", ".join(invalid[:3]) + ("…" if len(invalid) > 3 else "")
            return ActionResult.error(
                f"Invalid domain format: {examples}. Expected: domain.tld",
                retryable=False,
            )
    if len(new_domains) > MAX_DOMAINS:
        return ActionResult.error(f"Too many domains ({len(new_domains)}). Max {MAX_DOMAINS}.", retryable=False)
    patch: dict = {"domains": new_domains}
    if params.name:
        patch["name"] = params.name[:50]
    updated = await ctx.store.update("wt_groups", params.group_id, patch)
    return ActionResult.success(
        data=build_domain_group(params.group_id, updated.data["name"], new_domains),
        summary=f"Updated domain group '{updated.data['name']}' — {len(new_domains)} domain(s)",
        refresh_panels=["sidebar", "overview"],
    )


@chat.function("list_domain_groups", action_type="read",
               data_model=DomainGroupPage,
               description="Show all domain groups — names, domain lists and domain count. Call before create_monitor to pick the right group_id.")
async def fn_list_domain_groups(ctx, params: EmptyParams) -> ActionResult:
    """Show all domain groups — names, domain lists and domain count."""
    page = await ctx.store.query("wt_groups", where={"owner_id": ctx.user.imperal_id}, limit=10)
    groups = [
        {"group_id": d.id, "name": d.data["name"],
         "domains": d.data["domains"], "domain_count": len(d.data["domains"])}
        for d in page.data
    ]
    return ActionResult.success(
        data=build_domain_group_page(groups),
        summary=f"{len(groups)} domain group(s)",
    )


class DeleteGroupParams(BaseModel):
    """Delete domain group parameters."""
    group_id: str


@chat.function("delete_domain_group", action_type="destructive", event="group.deleted",
               effects=["delete:domain_group"],
               id_projection="group_id",
               data_model=WtOpResult,
               description="Permanently delete a domain group and cascade-delete all monitors that use it. Cannot be undone — confirm group_id with list_domain_groups first.")
async def fn_delete_domain_group(ctx, params: DeleteGroupParams) -> ActionResult:
    """Permanently delete a domain group and cascade-delete all monitors that use it."""
    doc = await ctx.store.get("wt_groups", params.group_id)
    if not doc or doc.data.get("owner_id") != ctx.user.imperal_id:
        return ActionResult.error("Domain group not found.", retryable=False)
    name = doc.data["name"]
    await ctx.store.delete("wt_groups", params.group_id)

    mon_page = await ctx.store.query("wt_monitors",
                                     where={"owner_id": ctx.user.imperal_id, "group_id": params.group_id},
                                     limit=10)

    async def _delete_monitor(m):
        snap_page = await ctx.store.query(
            "wt_snapshots",
            where={"owner_id": ctx.user.imperal_id, "monitor_id": m.id},
            limit=100,
        )
        await asyncio.gather(*[ctx.store.delete("wt_snapshots", s.id) for s in snap_page.data])
        await ctx.store.delete("wt_monitors", m.id)

    await asyncio.gather(*[_delete_monitor(m) for m in mon_page.data])
    return ActionResult.success(
        data=build_wt_op(params.group_id, f"Deleted group '{name}'",
                         monitors_removed=len(mon_page.data)),
        summary=f"Deleted group '{name}' and {len(mon_page.data)} monitor(s)",
        refresh_panels=["sidebar", "overview"],
    )
