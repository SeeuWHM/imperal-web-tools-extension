"""web-tools · Quick check (chat) + panel data (SDK 5.2.0 / SDL).

Bulk scan handlers (run_scan_tool, run_ip_scan) moved to handlers_bulk.py
to keep this file under 300 lines.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from imperal_sdk.chat import TaskCancelled
from handlers_scan import _run_domain_checks, _check_status
from schemas_sdl_builders import (
    ScanOpResult, PanelDataResult,
    build_scan_op, build_panel_data,
)


# ─── Quick Check ──────────────────────────────────────────────────────────── #

class QuickCheckParams(BaseModel):
    domain: str = Field(description="Domain name or IP address to check")
    preset: Literal["full", "dns", "ssl", "http", "email",
                    "blacklist", "geo", "ports"] = Field(
        default="full",
        description="Check type: full=5 checks parallel, or single check type",
    )


class EmptyParams(BaseModel):
    """No parameters — satisfies V17 for parameterless handlers."""


@chat.function("quick_check", action_type="write", event="quick.completed",
               effects=["create:scan_result"],
               data_model=ScanOpResult,
               description="Single-domain ad-hoc check from the panel. Presets: full=5 checks (dns+ssl+http+email+blacklist) in parallel, dns=DNS records, ssl=certificate quality grade, http=security headers grade, email=SPF/DMARC/DKIM, blacklist=spam lists, geo=reachability from EU/US/SG/MD (slowest), ports=TCP port scan. Result replaces left panel display.")
async def fn_quick_check(ctx, params: QuickCheckParams) -> ActionResult:
    """Single-domain ad-hoc check from the panel."""
    d = params.domain.strip()
    if not d:
        return ActionResult.error("Enter a domain or IP address.", retryable=False)

    base = WEB_TOOLS_URL
    now  = datetime.datetime.now(datetime.timezone.utc).isoformat()

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
        issues = sum(
            1 for name, r in results.items()
            if isinstance(r, dict) and not r.get("error")
            and _check_status(name, r) in ("warning", "critical")
        ) if results else 0
        sdl_data = build_scan_op(d, "full", 1, issues, list(results.keys()), results=results)
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
        try:
            resp = await ctx.http.get(f"{base}{_single[params.preset]}")
            resp.raise_for_status()
            body = resp.json()
        except Exception as exc:
            return ActionResult.error(f"{params.preset.upper()} check failed: {exc}", retryable=True)
        if not body.get("success"):
            return ActionResult.error(body.get("error") or "Check failed", retryable=False)
        result_data = {"domain": d, "preset": params.preset,
                       "result": body["data"], "results": None, "created_at": now}
        summary = f"{params.preset.upper()} check for {d} — done"
        sdl_data = build_scan_op(d, params.preset, 1, 0, [params.preset],
                                 results={params.preset: body["data"]})

    qpage = await ctx.store.query("wt_quick_results",
                                  where={"owner_id": ctx.user.imperal_id}, limit=1)
    doc = {"owner_id": ctx.user.imperal_id, **result_data}
    if qpage.data:
        await ctx.store.update("wt_quick_results", qpage.data[0].id, doc)
    else:
        await ctx.store.create("wt_quick_results", doc)

    return ActionResult.success(
        data=sdl_data, summary=summary,
        refresh_panels=["sidebar", "overview"],
    )


# ─── Panel Data ───────────────────────────────────────────────────────────── #

@chat.function("get_panel_data", action_type="read",
               data_model=PanelDataResult,
               description="Panel data helper — returns counts and statuses for monitors, groups and profiles. Called by the panel on load; not needed in regular LLM chat.")
async def fn_get_panel_data(ctx, params: EmptyParams) -> ActionResult:
    """Panel data helper — returns counts and statuses for monitors, groups and profiles."""
    mon_page, grp_page, prf_page = await asyncio.gather(
        ctx.store.query("wt_monitors", where={"owner_id": ctx.user.imperal_id}, limit=10),
        ctx.store.query("wt_groups",   where={"owner_id": ctx.user.imperal_id}, limit=10),
        ctx.store.query("wt_profiles", where={"owner_id": ctx.user.imperal_id}, limit=10),
    )
    snap_ids = [m.data.get("last_snapshot_id") for m in mon_page.data]

    async def _snap(sid):
        if sid:
            return await ctx.store.get("wt_snapshots", sid)
        return None

    snaps = await asyncio.gather(*[_snap(sid) for sid in snap_ids])
    critical = warning = ok = 0
    for s in snaps:
        if s:
            st = s.data.get("status", "unknown")
            if st == "critical":  critical += 1
            elif st == "warning": warning  += 1
            elif st == "ok":      ok       += 1

    return ActionResult.success(
        data=build_panel_data(
            monitors=len(mon_page.data),
            domain_groups=len(grp_page.data),
            profiles=len(prf_page.data),
            critical=critical, warning=warning, ok=ok,
        ),
        summary=f"Web Tools: {len(mon_page.data)} monitor(s)",
    )
