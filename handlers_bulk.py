"""web-tools · Bulk scan handlers — run_scan_tool + run_ip_scan (SDK 5.2.0 / SDL).

Split from handlers_quick.py (300-line rule) — registered via main.py.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from handlers_scan import _run_domain_checks
from schemas_sdl_builders import ScanOpResult, build_scan_op


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
               effects=["create:scan_result"],
               data_model=ScanOpResult,
               description="Bulk domain scan (max 10) with chosen checks via toggles — results appear in the left panel. Use when user provides a list of domains to check simultaneously.")
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

    await ctx.progress(percent=0, message=f"Starting scan: {len(domains)} domain(s), {len(checks)} check(s)…")
    dom_sem  = asyncio.Semaphore(3)
    done     = [0]

    async def _scan(d: str) -> tuple[str, dict]:
        async with dom_sem:
            result = await _run_domain_checks(ctx, d, checks)
            done[0] += 1
            pct = int(done[0] / len(domains) * 90)
            await ctx.progress(percent=pct, message=f"Scanned {done[0]}/{len(domains)}: {d}")
            return d, result

    results = dict(await asyncio.gather(*[_scan(d) for d in domains]))
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    spage = await ctx.store.query("wt_scan_results",
                                   where={"owner_id": ctx.user.imperal_id}, limit=1)
    doc = {"owner_id": ctx.user.imperal_id, "domains": domains,
           "checks": checks, "results": results, "created_at": now}
    if spage.data:
        await ctx.store.update("wt_scan_results", spage.data[0].id, doc)
    else:
        await ctx.store.create("wt_scan_results", doc)

    issues = sum(1 for dr in results.values()
                 for r in dr.values() if r.get("status") in ("warning", "critical"))
    return ActionResult.success(
        data=build_scan_op(
            target=",".join(domains[:3]) + ("…" if len(domains) > 3 else ""),
            preset="bulk", scanned=len(domains), issues=issues, checks=checks,
        ),
        summary=f"Scanned {len(domains)} domain(s) — {issues} issue(s)",
        refresh_panels=["sidebar"],
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
               effects=["create:scan_result"],
               data_model=ScanOpResult,
               description="Bulk IP scan (max 5) — geolocation + ASN, 29 DNSBL blacklist, reverse DNS (PTR), open ports, ping from EU/US/SG/MD. Use for IP-specific investigations.")
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
    now     = datetime.datetime.now(datetime.timezone.utc).isoformat()

    spage = await ctx.store.query("wt_ip_scan_results",
                                   where={"owner_id": ctx.user.imperal_id}, limit=1)
    doc = {"owner_id": ctx.user.imperal_id, "ips": ips, "checks": list(checks),
           "results": results, "created_at": now}
    if spage.data:
        await ctx.store.update("wt_ip_scan_results", spage.data[0].id, doc)
    else:
        await ctx.store.create("wt_ip_scan_results", doc)

    issues = sum(1 for ir in results.values()
                 for r in ir.values() if r.get("status") in ("warning", "critical"))
    return ActionResult.success(
        data=build_scan_op(
            target=",".join(ips[:3]) + ("…" if len(ips) > 3 else ""),
            preset="ip_bulk", scanned=len(ips), issues=issues, checks=list(checks),
        ),
        summary=f"Scanned {len(ips)} IP(s) — {issues} issue(s)",
        refresh_panels=["sidebar"],
    )
