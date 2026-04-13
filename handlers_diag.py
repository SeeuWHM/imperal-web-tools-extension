"""web-tools · Diagnostic handlers — Email, Blacklist, Ports, SMTP, Geo, Full Check."""
from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult

# ─── Email ────────────────────────────────────────────────────────────────── #

class EmailCheckParams(BaseModel):
    """Email infrastructure check parameters."""
    domain: str
    check_type: Literal["spf", "dmarc", "dkim", "bimi", "full", "trace", "generate_spf", "generate_dmarc"] = Field(
        default="full",
        description="spf/dmarc/dkim/bimi=individual check, full=grade A-F, trace=parse raw headers, generate_spf/generate_dmarc=build record",
    )
    dkim_selector: str = Field(default="google", description="DKIM selector (for 'dkim' check)")
    raw_headers: str = Field(default="", description="Raw Received: headers to parse (for 'trace')")
    spf_includes: list[str] = Field(default_factory=list, description="SPF include domains (for 'generate_spf')")
    dmarc_policy: Literal["none", "quarantine", "reject"] = Field(default="quarantine", description="DMARC policy (for 'generate_dmarc')")


@chat.function("email_check", action_type="read",
               description="Email deliverability — SPF/DMARC/DKIM/BIMI check, full grade A-F with findings, parse raw email headers (trace originating IP), generate SPF/DMARC records")
async def fn_email_check(ctx, params: EmailCheckParams) -> ActionResult:
    base = WEB_TOOLS_URL
    if params.check_type == "dkim":
        resp = await ctx.http.get(f"{base}/v1/email/dkim/{params.domain}",
                                  params={"selector": params.dkim_selector})
    elif params.check_type in ("spf", "dmarc", "bimi"):
        resp = await ctx.http.get(f"{base}/v1/email/{params.check_type}/{params.domain}")
    elif params.check_type == "full":
        resp = await ctx.http.get(f"{base}/v1/email/full/{params.domain}")
    elif params.check_type == "trace":
        resp = await ctx.http.post(f"{base}/v1/email/trace",
                                   json={"headers": params.raw_headers})
    elif params.check_type == "generate_spf":
        resp = await ctx.http.post(f"{base}/v1/email/spf/generate",
                                   json={"includes": params.spf_includes, "ips": [], "all_mechanism": "~all"})
    else:  # generate_dmarc
        resp = await ctx.http.post(f"{base}/v1/email/dmarc/generate",
                                   json={"policy": params.dmarc_policy, "pct": 100, "rua": "",
                                         "aspf": "r", "adkim": "r", "subdomain_policy": ""})
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "Email check failed"), retryable=False)
    return ActionResult.success(
        data={"domain": params.domain, "check_type": params.check_type, "result": body["data"]},
        summary=f"Email {params.check_type} for {params.domain}",
    )


# ─── Blacklist ────────────────────────────────────────────────────────────── #

class BlacklistParams(BaseModel):
    """Blacklist check parameters."""
    target: str = Field(description="IPv4 address or domain name")
    target_type: Literal["ip", "domain"] = Field(
        default="ip",
        description="'ip' checks 30 DNSBL in parallel, 'domain' resolves to IP then checks SURBL",
    )


@chat.function("blacklist_check", action_type="read",
               description="Blacklist reputation — IP against 30 DNSBL (Spamhaus ZEN/SBL/XBL, SpamCop, Barracuda) or domain SURBL. Verdict: clean/listed/critical")
async def fn_blacklist_check(ctx, params: BlacklistParams) -> ActionResult:
    resp = await ctx.http.get(f"{WEB_TOOLS_URL}/v1/blacklist/{params.target_type}/{params.target}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "Blacklist check failed"), retryable=False)
    return ActionResult.success(
        data={"target": params.target, "type": params.target_type, "result": body["data"]},
        summary=f"Blacklist check for {params.target}",
    )


# ─── Ports ────────────────────────────────────────────────────────────────── #

class PortScanParams(BaseModel):
    """Port scan parameters."""
    host: str
    port: int = Field(default=0, description="Specific port to check (0 = preset scan)")
    preset: Literal["web", "mail", "database", "all"] = Field(
        default="web",
        description="Port preset: web (80/443/8080/8443), mail (25/587/465/993/995), database (3306/5432/6379), all",
    )


@chat.function("port_scan", action_type="read",
               description="TCP ports — single port status (open/closed/filtered) or preset scan: web/mail/database/all ports in parallel")
async def fn_port_scan(ctx, params: PortScanParams) -> ActionResult:
    base = WEB_TOOLS_URL
    if params.port > 0:
        resp = await ctx.http.get(f"{base}/v1/ports/check/{params.host}/{params.port}")
        summary = f"Port {params.port} on {params.host}"
    else:
        resp = await ctx.http.get(f"{base}/v1/ports/scan/{params.host}",
                                  params={"preset": params.preset})
        summary = f"Port scan ({params.preset}) on {params.host}"
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "Port scan failed"), retryable=False)
    return ActionResult.success(
        data={"host": params.host, "result": body["data"]},
        summary=summary,
    )


# ─── SMTP ─────────────────────────────────────────────────────────────────── #

class SmtpTestParams(BaseModel):
    """SMTP test parameters."""
    target: str = Field(description="Domain name (uses MX) or specific mail server hostname")
    port: int = Field(default=0, description="Specific port to test (0 = auto-try 587/25/465 via MX)")


@chat.function("smtp_test", action_type="read",
               description="SMTP server test — connect via MX or direct host, EHLO handshake, STARTTLS, AUTH methods, server banner and software")
async def fn_smtp_test(ctx, params: SmtpTestParams) -> ActionResult:
    base = WEB_TOOLS_URL
    if params.port > 0:
        resp = await ctx.http.get(f"{base}/v1/smtp/test/host/{params.target}",
                                  params={"port": params.port})
    else:
        resp = await ctx.http.get(f"{base}/v1/smtp/test/{params.target}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "SMTP test failed"), retryable=False)
    return ActionResult.success(
        data={"target": params.target, "result": body["data"]},
        summary=f"SMTP test for {params.target}",
    )


# ─── Geo ──────────────────────────────────────────────────────────────────── #

class GeoCheckParams(BaseModel):
    """Multi-region geo probe parameters."""
    target: str
    check_type: Literal["dns", "ping", "http", "ssl", "traceroute", "full"] = Field(
        default="full",
        description="Probe from EU/US/SG/MD: dns=resolution+mismatch, ping=latency, http=status, ssl=validity, traceroute, full=dns+http+ssl",
    )
    dns_type: Literal["A", "MX", "NS", "TXT", "CNAME"] = "A"


@chat.function("geo_check", action_type="read",
               description="Multi-region probe from EU/US/SG/MD — DNS mismatch (anycast), ping latency, HTTP availability, SSL validity, MTR traceroute per region")
async def fn_geo_check(ctx, params: GeoCheckParams) -> ActionResult:
    base = WEB_TOOLS_URL
    if params.check_type == "dns":
        resp = await ctx.http.get(f"{base}/v1/geo/dns/{params.target}",
                                  params={"type": params.dns_type})
    else:
        resp = await ctx.http.get(f"{base}/v1/geo/{params.check_type}/{params.target}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "Geo check failed"), retryable=False)
    return ActionResult.success(
        data={"target": params.target, "check_type": params.check_type, "regions": body["data"]},
        summary=f"Geo {params.check_type} for {params.target} (EU/US/SG/MD)",
    )


# ─── Full Domain Check ────────────────────────────────────────────────────── #

class DomainFullCheckParams(BaseModel):
    """Full parallel domain audit parameters."""
    domain: str
    checks: list[Literal["dns", "ssl", "whois", "http", "email", "blacklist", "geo"]] = Field(
        default=["dns", "ssl", "http", "email", "blacklist"],
        description="Checks to run in parallel. Add 'geo' for multi-region probe (slowest). Add 'whois' for ownership data.",
    )


@chat.function("domain_full_check", action_type="read",
               description="Full parallel domain audit — DNS+SSL+WHOIS+HTTP+email+blacklist+geo simultaneously. Best for complete domain health check")
async def fn_domain_full_check(ctx, params: DomainFullCheckParams) -> ActionResult:
    check_urls = {
        "dns":       f"/v1/dns/all/{params.domain}",
        "ssl":       f"/v1/ssl/{params.domain}",
        "whois":     f"/v1/whois/{params.domain}/quick",
        "http":      f"/v1/http/headers/{params.domain}/grade",
        "email":     f"/v1/email/full/{params.domain}",
        "blacklist": f"/v1/blacklist/domain/{params.domain}",
        "geo":       f"/v1/geo/full/{params.domain}",
    }

    async def _check(name: str) -> tuple[str, object]:
        try:
            resp = await ctx.http.get(f"{WEB_TOOLS_URL}{check_urls[name]}")
            body = resp.json()
            return name, body.get("data") if body.get("success") else {"error": body.get("error")}
        except Exception as exc:
            return name, {"error": str(exc)}

    sem = asyncio.Semaphore(5)

    async def _limited(name: str) -> tuple[str, object]:
        async with sem:
            return await _check(name)

    results = dict(await asyncio.gather(*[_limited(c) for c in params.checks]))
    return ActionResult.success(
        data={"domain": params.domain, "checks": results},
        summary=f"Full audit for {params.domain} ({len(params.checks)} checks completed)",
    )
