"""web-tools · Diagnostic handlers — Email, Blacklist, Ports, SMTP, Geo, Full Check (SDK 5.2.0 / SDL)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from handlers_ui import blacklist_ui, full_audit_ui
from schemas_sdl_builders import (
    EmailAuthResult, BlacklistResult, PortScanResult,
    SmtpResult, GeoCheckResult, DomainAuditResult,
    build_email_auth, build_blacklist, build_port_scan,
    build_smtp, build_geo, build_domain_audit,
)


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
               data_model=EmailAuthResult,
               description="Email authentication — SPF/DMARC/DKIM/BIMI checks or combined A-F grade, trace raw email headers to find originating IP, generate SPF or DMARC records.")
async def fn_email_check(ctx, params: EmailCheckParams) -> ActionResult:
    """Email authentication — SPF/DMARC/DKIM/BIMI checks or combined A-F grade, trace raw email headers to find originating..."""
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
        return ActionResult.error(body.get("error") or "Email check failed", retryable=False)
    return ActionResult.success(
        data=build_email_auth(params.domain, params.check_type, body["data"]),
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
               data_model=BlacklistResult,
               description="Spam blacklist check — IP against 30 DNSBL lists (Spamhaus, SpamCop, Barracuda) or domain against SURBL. Returns verdict: clean / listed / critical.")
async def fn_blacklist_check(ctx, params: BlacklistParams) -> ActionResult:
    """Spam blacklist check — IP against 30 DNSBL lists (Spamhaus, SpamCop, Barracuda) or domain against SURBL."""
    resp = await ctx.http.get(f"{WEB_TOOLS_URL}/v1/blacklist/{params.target_type}/{params.target}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "Blacklist check failed", retryable=False)
    return ActionResult.success(
        data=build_blacklist(params.target, params.target_type, body["data"]),
        summary=f"Blacklist check for {params.target}",
        ui=blacklist_ui(params.target, body["data"] or {}),
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
               data_model=PortScanResult,
               description="TCP port check — single port status (open/closed/filtered) or preset scan: web (80/443/8080/8443), mail (25/587/465/993/995), database (3306/5432/6379), all.")
async def fn_port_scan(ctx, params: PortScanParams) -> ActionResult:
    """TCP port check — single port status (open/closed/filtered) or preset scan: web (80/443/8080/8443), mail (25/587/465/9..."""
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
        return ActionResult.error(body.get("error") or "Port scan failed", retryable=False)
    return ActionResult.success(
        data=build_port_scan(params.host, body["data"]),
        summary=summary,
    )


# ─── SMTP ─────────────────────────────────────────────────────────────────── #

class SmtpTestParams(BaseModel):
    """SMTP test parameters."""
    target: str = Field(description="Domain name (uses MX) or specific mail server hostname")
    port: int = Field(default=0, description="Specific port to test (0 = auto-try 587/25/465 via MX)")


@chat.function("smtp_test", action_type="read",
               data_model=SmtpResult,
               description="SMTP server test — connects via MX record or direct host, verifies EHLO/STARTTLS/AUTH support, reads server banner. Use to diagnose email delivery problems.")
async def fn_smtp_test(ctx, params: SmtpTestParams) -> ActionResult:
    """SMTP server test — connects via MX record or direct host, verifies EHLO/STARTTLS/AUTH support, reads server banner."""
    base = WEB_TOOLS_URL
    if params.port > 0:
        resp = await ctx.http.get(f"{base}/v1/smtp/test/host/{params.target}",
                                  params={"port": params.port})
    else:
        resp = await ctx.http.get(f"{base}/v1/smtp/test/{params.target}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "SMTP test failed", retryable=False)
    return ActionResult.success(
        data=build_smtp(params.target, body["data"]),
        summary=f"SMTP test for {params.target}",
    )


# ─── Geo ──────────────────────────────────────────────────────────────────── #

class GeoCheckParams(BaseModel):
    """Multi-region geo probe parameters."""
    target: str = Field(description="Domain name or IP address")
    check_type: Literal["dns", "ping", "http", "ssl", "traceroute", "full"] = Field(
        default="full",
        description="Probe from EU/US/SG/MD: dns=resolution+mismatch, ping=latency, http=status, ssl=validity, traceroute, full=dns+http+ssl",
    )
    dns_type: Literal["A", "MX", "NS", "TXT", "CNAME"] = "A"

    @model_validator(mode="before")
    @classmethod
    def _accept_domains_alias(cls, v):
        if isinstance(v, dict) and not v.get("target"):
            d = v.get("domains") or v.get("domain") or v.get("host")
            if isinstance(d, list):
                d = d[0] if d else ""
            if d:
                v = {**v, "target": d}
        return v


@chat.function("geo_check", action_type="read",
               data_model=GeoCheckResult,
               description="Geographic reachability — probes domain FROM 4 world regions (EU/US/SG/MD). Use when user asks: 'loading speed from America/Asia/Europe', 'is site accessible from US', 'latency from Singapore', 'down for users in another country', 'скорость загрузки с Америки/Азии'. check_type=ping = latency from each region (ms). check_type=http = HTTP response time and status from each region (use for 'loading speed'). check_type=dns = DNS resolution consistency per region (finds anycast/Cloudflare issues). check_type=ssl = SSL reachability per region. check_type=traceroute = network path per region. check_type=full = ALL probes from all 4 regions in one call. NOTE: tests REACHABILITY and SPEED, not quality — for certificate grade use ssl_check, for header quality use http_check.")
async def fn_geo_check(ctx, params: GeoCheckParams) -> ActionResult:
    """Geographic reachability — probes domain FROM 4 world regions (EU/US/SG/MD)."""
    base = WEB_TOOLS_URL
    if params.check_type == "dns":
        resp = await ctx.http.get(f"{base}/v1/geo/dns/{params.target}",
                                  params={"type": params.dns_type})
    else:
        resp = await ctx.http.get(f"{base}/v1/geo/{params.check_type}/{params.target}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "Geo check failed", retryable=False)
    return ActionResult.success(
        data=build_geo(params.target, params.check_type, body["data"]),
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
               data_model=DomainAuditResult,
               description="INSTANT one-shot domain audit — no monitors or setup required, works on ANY domain. Runs selected checks in parallel and shows a summary table. Use this when: user mentions a domain and asks for 'full check', 'analysis', 'audit', 'show everything', 'what can you do on this domain', 'check this site'. Default checks: dns + ssl (certificate grade) + http (security headers grade) + email (SPF/DMARC/DKIM) + blacklist (spam lists). Add 'geo' for geographic reachability from EU/US/SG/MD. Do NOT use run_scan, list_monitors or get_scan_results for ad-hoc domain checks — those are for recurring monitor automation only.")
async def fn_domain_full_check(ctx, params: DomainFullCheckParams) -> ActionResult:
    """INSTANT one-shot domain audit — no monitors or setup required, works on ANY domain."""
    from handlers_scan import _run_domain_checks
    results = await _run_domain_checks(ctx, params.domain, params.checks)
    return ActionResult.success(
        data=build_domain_audit(params.domain, results),
        summary=f"Full audit for {params.domain} ({len(params.checks)} checks completed)",
        ui=full_audit_ui(params.domain, results),
    )
