"""web-tools · Scan Tool (left panel bulk scan) + quick check (chat) + panel data."""
from __future__ import annotations

import asyncio
import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from handlers_scan import _run_domain_checks


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


# ─── Scan Tool (left panel — multi-domain, toggle checks) ────────────────── #

class ScanToolParams(BaseModel):
    domains:     list[str] = Field(default_factory=list, description="Domains or IPs to scan (max 10)")
    # Defaults match _DOMAIN_TOGGLES visual defaults — SDK may omit unchanged form values
    ssl:         bool = Field(default=True)
    http:        bool = Field(default=True)
    email:       bool = Field(default=True)
    blacklist:   bool = Field(default=True)
    geo:         bool = Field(default=False)
    whois:       bool = Field(default=False)
    ports:       bool = Field(default=False)
    smtp:        bool = Field(default=False)
    propagation: bool = Field(default=False)


@chat.function("run_scan_tool", action_type="write", event="scan.tool",
               description="Scan one or more domains/IPs on demand — select checks via toggles. Results shown in the left panel.")
async def fn_run_scan_tool(ctx, params: ScanToolParams) -> ActionResult:
    domains = list(dict.fromkeys(
        d.strip() for d in (params.domains or []) if d.strip()
    ))[:10]
    if not domains:
        return ActionResult.error("Add at least one domain or IP.", retryable=False)

    checks = [k for k, v in {
        "ssl": params.ssl, "http": params.http, "email": params.email,
        "blacklist": params.blacklist, "geo": params.geo, "whois": params.whois,
        "ports": params.ports, "smtp": params.smtp, "propagation": params.propagation,
    }.items() if v]
    if not checks:
        return ActionResult.error("Enable at least one check.", retryable=False)

    dom_sem = asyncio.Semaphore(3)

    async def _scan(d: str) -> tuple[str, dict]:
        async with dom_sem:
            return d, await _run_domain_checks(ctx, d, checks)

    results = dict(await asyncio.gather(*[_scan(d) for d in domains]))
    now = datetime.datetime.utcnow().isoformat()

    spage = await ctx.store.query("wt_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    doc = {"owner_id": ctx.user.id, "domains": domains,
           "checks": checks, "results": results, "created_at": now}
    if spage.data:
        await ctx.store.update("wt_scan_results", spage.data[0].id, doc)
    else:
        await ctx.store.create("wt_scan_results", doc)

    issues = sum(1 for dr in results.values()
                 for r in dr.values() if r.get("status") in ("warning", "critical"))
    return ActionResult.success(
        data={"scanned": len(domains), "checks": checks, "issues": issues},
        summary=f"Scanned {len(domains)} domain(s) — {issues} issue(s)",
        refresh_panels=["__panel__sidebar"],
    )


# ─── IP Scan Tool (left panel — IP-specific checks) ──────────────────────── #

class IpScanParams(BaseModel):
    domains:   list[str] = Field(default_factory=list, description="IP addresses to scan (max 5)")
    # Defaults match _IP_TOGGLES visual defaults — SDK may omit unchanged form values
    ip_lookup: bool = Field(default=True)
    blacklist: bool = Field(default=True)
    reverse:   bool = Field(default=True)
    ports:     bool = Field(default=False)
    geo_ping:  bool = Field(default=True)


def _ip_status(check: str, data: dict) -> str:
    if not data:
        return "unknown"
    if check == "blacklist":
        v = data.get("verdict", "clean")
        return "critical" if v == "critical" else "warning" if v == "listed" else "ok"
    if check == "geo_ping":
        regions = data.get("regions", {})
        total   = len(regions)
        if total > 0:
            reach = sum(1 for r in regions.values()
                        if isinstance(r, dict) and r.get("reachable"))
            if reach / total < 0.6:
                return "warning"
    return "ok"


@chat.function("run_ip_scan", action_type="write", event="scan.tool",
               description="Scan IP addresses — IP lookup (geo/ASN), blacklist (29 DNSBL), reverse DNS (PTR), port scan, geo ping from 4 regions.")
async def fn_run_ip_scan(ctx, params: IpScanParams) -> ActionResult:
    ips = list(dict.fromkeys(ip.strip() for ip in (params.domains or []) if ip.strip()))[:5]
    if not ips:
        return ActionResult.error("Enter at least one IP address.", retryable=False)

    checks = {k: v for k, v in {
        "ip_lookup": params.ip_lookup, "blacklist": params.blacklist,
        "reverse": params.reverse, "ports": params.ports, "geo_ping": params.geo_ping,
    }.items() if v}
    if not checks:
        return ActionResult.error("Enable at least one check.", retryable=False)

    base = WEB_TOOLS_URL
    _urls = {
        "ip_lookup": lambda ip: f"{base}/v1/network/ip-lookup/{ip}",
        "blacklist":  lambda ip: f"{base}/v1/blacklist/ip/{ip}",
        "reverse":    lambda ip: f"{base}/v1/network/reverse/{ip}",
        "ports":      lambda ip: f"{base}/v1/ports/scan/{ip}",
        "geo_ping":   lambda ip: f"{base}/v1/geo/ping/{ip}",
    }

    async def _chk(ip: str, chk: str) -> tuple[str, dict]:
        try:
            resp = await ctx.http.get(_urls[chk](ip))
            body = resp.json()
            if body.get("success"):
                d = body.get("data")
                return chk, {"status": _ip_status(chk, d or {}), "data": d}
            err = body.get("error") or body.get("message") or "Check failed"
            return chk, {"status": "unknown", "data": None, "error": err}
        except Exception as exc:
            return chk, {"status": "unknown", "data": None, "error": str(exc)}

    sem = asyncio.Semaphore(3)

    async def _scan(ip: str) -> tuple[str, dict]:
        async with sem:
            raw = await asyncio.gather(*[_chk(ip, c) for c in checks], return_exceptions=True)
            outcome: dict = {}
            for c, r in zip(checks, raw):
                if isinstance(r, tuple):
                    outcome[r[0]] = r[1]
                else:
                    outcome[c] = {"status": "unknown", "data": None, "error": type(r).__name__}
            return ip, outcome

    results = dict(await asyncio.gather(*[_scan(ip) for ip in ips]))
    now     = datetime.datetime.utcnow().isoformat()

    spage = await ctx.store.query("wt_ip_scan_results",
                                   where={"owner_id": ctx.user.id}, limit=1)
    doc = {"owner_id": ctx.user.id, "ips": ips, "checks": list(checks),
           "results": results, "created_at": now}
    if spage.data:
        await ctx.store.update("wt_ip_scan_results", spage.data[0].id, doc)
    else:
        await ctx.store.create("wt_ip_scan_results", doc)

    issues = sum(1 for ir in results.values()
                 for r in ir.values() if r.get("status") in ("warning", "critical"))
    return ActionResult.success(
        data={"scanned": len(ips), "checks": list(checks), "issues": issues},
        summary=f"Scanned {len(ips)} IP(s) — {issues} issue(s)",
        refresh_panels=["__panel__sidebar"],
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
