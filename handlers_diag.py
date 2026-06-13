"""web-tools · Diagnostic handlers — Email, Blacklist, Ports, SMTP, Geo, Full Check (SDK 5.2.0 / SDL)."""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from handlers_ui import blacklist_ui, full_audit_ui, _check_detail
from schemas_sdl_builders import (
    EmailAuthResult, BlacklistResult, PortScanResult,
    SmtpResult, GeoCheckResult, DomainAuditResult,
    build_email_auth, build_blacklist, build_port_scan,
    build_smtp, build_geo, build_domain_audit,
)
# Import at MODULE LOAD time (not lazily inside the handler). The kernel loader
# (I-EXT-MODULE-ISOLATION) rebinds bare sibling module names to an ext-unique
# namespace after load; a call-time `from handlers_scan import ...` would be
# re-resolved against whichever extension currently owns the bare `app` name,
# causing `cannot import name 'WEB_TOOLS_URL' from 'app'`. Loading here keeps
# the binding correct and namespaced as a unit.
from handlers_scan import _run_domain_checks

log = logging.getLogger(__name__)


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
               description="Geographic reachability — probes domain FROM 4 world regions (EU/US/SG/MD). "
               "ROUTING RULES — pick check_type based on what the user is asking: "
               "→ 'loading speed', 'response time', 'скорость загрузки', 'how fast from X country' → check_type=http (HTTP response time + status per region). "
               "→ 'latency', 'ping', 'ms from region', 'reachable from X' → check_type=ping (RTT ms + packet loss per region). "
               "→ 'dns from different countries', 'dns propagation per region', 'different DNS results per location' → check_type=dns. "
               "→ 'ssl from different regions', 'ssl reachable from US' → check_type=ssl. "
               "→ 'traceroute', 'network path', 'routing path from region' → check_type=traceroute. "
               "→ 'full geo audit', 'all geo checks', 'complete geo report' → check_type=full (runs ALL: dns+ping+http+ssl+traceroute — slowest, only use when explicitly requested). "
               "NEVER default to check_type=full for a simple speed or reachability question — use http or ping. "
               "NOTE: this tool tests REACHABILITY and SPEED from regions only. "
               "For SSL certificate quality/grade → use ssl_check. For HTTP security headers grade → use http_check. For DNS record values → use dns_lookup.")
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
    checks: list[Literal["dns", "ssl", "whois", "http", "email", "blacklist", "geo", "seo", "ports", "smtp"]] = Field(
        default=["dns", "ssl", "http", "email", "blacklist"],
        description="Checks to run in parallel. Defaults to dns+ssl+http+email+blacklist. Add 'geo' for multi-region reachability (slowest), 'whois' for ownership, 'seo' for meta/title issues, 'ports' for open-port scan, 'smtp' for mail-server connectivity.",
    )
    include_raw: bool = Field(
        False,
        description="When false (default) the data payload carries only per-check status + a one-line summary (compact). Set true to also return the full raw check results (large — only when explicitly asked for raw data).",
    )


@chat.function("domain_full_check", action_type="read",
               data_model=DomainAuditResult,
               description="INSTANT one-shot domain audit — no monitors or setup required, works on ANY domain. Runs selected checks in parallel and shows a summary table. Use this when: user mentions a domain and asks for 'full check', 'analysis', 'audit', 'show everything', 'what can you do on this domain', 'check this site'. Default checks: dns + ssl (certificate grade) + http (security headers grade) + email (SPF/DMARC/DKIM) + blacklist (spam lists). Optional extra checks: 'geo' (reachability from EU/US/SG/MD), 'whois' (ownership), 'seo' (meta/title issues), 'ports' (open ports), 'smtp' (mail-server connectivity). Returns a compact per-check status summary by default; set include_raw=true only when the user explicitly wants the full raw data. Do NOT use run_scan, list_monitors or get_scan_results for ad-hoc domain checks — those are for recurring monitor automation only.")
async def fn_domain_full_check(ctx, params: DomainFullCheckParams) -> ActionResult:
    """INSTANT one-shot domain audit — no monitors or setup required, works on ANY domain."""
    try:
        results = await _run_domain_checks(ctx, params.domain, params.checks)
        # Compact data payload (default): per-check status + one-line summary, no raw blobs.
        # The full audit table (full_audit_ui) is always rendered from the full results;
        # raw per-check payloads are only echoed into data when explicitly requested.
        if params.include_raw:
            payload = results
        else:
            payload = {
                check: {
                    "status": (data.get("status", "unknown") if isinstance(data, dict) else "unknown"),
                    "summary": _check_detail(check, data),
                }
                for check, data in results.items()
            }
        issues = sum(
            1 for d in results.values()
            if isinstance(d, dict) and d.get("status") in ("warning", "critical")
        )
        return ActionResult.success(
            data=build_domain_audit(params.domain, payload),
            summary=f"Full audit for {params.domain} — {len(params.checks)} check(s), {issues} issue(s)",
            ui=full_audit_ui(params.domain, results),
        )
    except Exception as exc:
        log.error("domain_full_check failed for %s: %s", params.domain, exc)
        return ActionResult.error(
            "Domain audit failed — please try again.", retryable=True,
        )
