"""web-tools · Quick check (one-off panel check) + panel data for LLM context."""
from __future__ import annotations

import asyncio
import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult


# ─── Quick Check ──────────────────────────────────────────────────────────── #

class QuickCheckParams(BaseModel):
    domain: str = Field(description="Domain name or IP address to check")
    preset: Literal["full", "dns", "ssl", "http", "email",
                    "blacklist", "geo", "ports"] = Field(
        default="full",
        description="Check type: full=5 checks parallel, or single check type",
    )


@chat.function("quick_check", action_type="write", event="quick.completed",
               description="Quick domain check from panel — DNS/SSL/HTTP/email/blacklist/geo/ports. Result stored and shown in right panel.")
async def fn_quick_check(ctx, params: QuickCheckParams) -> ActionResult:
    d = params.domain.strip()
    if not d:
        return ActionResult.error("Enter a domain or IP address.", retryable=False)

    base = WEB_TOOLS_URL
    now  = datetime.datetime.utcnow().isoformat()

    if params.preset == "full":
        _urls = {
            "dns":       f"/v1/dns/all/{d}",
            "ssl":       f"/v1/ssl/{d}",
            "http":      f"/v1/http/headers/{d}/grade",
            "email":     f"/v1/email/full/{d}",
            "blacklist": f"/v1/blacklist/domain/{d}",
        }
        sem = asyncio.Semaphore(5)

        async def _fetch(name: str, url: str) -> tuple[str, object]:
            async with sem:
                try:
                    r = await ctx.http.get(f"{base}{url}")
                    b = r.json()
                    return name, b.get("data") if b.get("success") else {"error": b.get("error")}
                except Exception as exc:
                    return name, {"error": str(exc)}

        results = dict(await asyncio.gather(*[_fetch(n, u) for n, u in _urls.items()]))
        result_data = {"domain": d, "preset": "full", "results": results,
                       "result": None, "created_at": now}
        summary = f"Full audit for {d} — 5 checks completed"
    else:
        _single: dict[str, str] = {
            "dns":       f"/v1/dns/all/{d}",
            "ssl":       f"/v1/ssl/{d}/full",
            "http":      f"/v1/http/headers/{d}/grade",
            "email":     f"/v1/email/full/{d}",
            "blacklist": f"/v1/blacklist/domain/{d}",
            "geo":       f"/v1/geo/full/{d}",
            "ports":     f"/v1/ports/scan/{d}",
        }
        resp = await ctx.http.get(f"{base}{_single[params.preset]}")
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            return ActionResult.error(body.get("error", "Check failed"), retryable=False)
        result_data = {"domain": d, "preset": params.preset,
                       "result": body["data"], "results": None, "created_at": now}
        summary = f"{params.preset.upper()} check for {d} — done"

    qpage = await ctx.store.query("wt_quick_results",
                                  where={"owner_id": ctx.user.id}, limit=1)
    doc = {"owner_id": ctx.user.id, **result_data}
    if qpage.data:
        await ctx.store.update("wt_quick_results", qpage.data[0].id, doc)
    else:
        await ctx.store.create("wt_quick_results", doc)

    return ActionResult.success(
        data=result_data, summary=summary,
        refresh_panels=["__panel__sidebar", "__panel__overview"],
    )


# ─── Panel Data (chat LLM context) ────────────────────────────────────────── #

@chat.function("get_panel_data", action_type="read",
               description="Panel summary — monitors, groups, profiles counts and statuses")
async def fn_get_panel_data(ctx) -> ActionResult:
    mon_page, grp_page, prf_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.id}, limit=10),
    )
    skel = getattr(ctx, "skeleton_data", {}).get("skeleton_refresh_web_tools", {})
    return ActionResult.success(data={
        "monitors":      len(mon_page.data),
        "domain_groups": len(grp_page.data),
        "profiles":      len(prf_page.data),
        "critical":      skel.get("critical", 0),
        "warning":       skel.get("warning",  0),
        "ok":            skel.get("ok",        0),
    }, summary=f"Web Tools: {len(mon_page.data)} monitor(s)")
