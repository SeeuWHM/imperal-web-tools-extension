"""web-tools · Diagnostic handlers — DNS, SSL, WHOIS, HTTP, Network, SEO (SDK 5.2.0 / SDL)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from handlers_ui import ssl_ui, dns_ui, http_ui
from schemas_sdl_builders import (
    DomainCheckResult, SslResult,
    build_domain_check, build_ssl,
)


# ─── DNS ──────────────────────────────────────────────────────────────────── #

class DnsLookupParams(BaseModel):
    """DNS lookup parameters."""
    domain: str
    record_type: Literal["A","AAAA","IP","MX","NS","TXT","CNAME","SRV","DNSSEC","all","propagation"] = "A"
    authoritative: bool = Field(default=False, description="Query from domain's own authoritative NS (A/AAAA/MX/NS/TXT/CNAME)")
    propagation_type: Literal["A","MX","NS","TXT","CNAME"] | None = Field(default=None, description="Record type for propagation check (default: A). Use NS when user updated NS records, MX for mail, TXT for SPF/DMARC.")


@chat.function("dns_lookup", action_type="read",
               data_model=DomainCheckResult,
               description="DNS record lookup — use this for ANY request about DNS records of a domain. IMPORTANT: use record_type='all' when user asks for 'all DNS records', 'все записи', 'show all', 'all types' — returns A+AAAA+MX+NS+TXT+CNAME+SRV in ONE call. Use record_type='propagation' + propagation_type='NS' when user says 'NS records updated, did they propagate?', 'did my DNS update?', 'already propagated?'. Use specific type (MX/TXT/NS/A) only when user asks for that specific type. Use authoritative=true to query domain's own NS directly. This function does NOT need any monitors to exist — works on any domain instantly.")
async def fn_dns_lookup(ctx, params: DnsLookupParams) -> ActionResult:
    """DNS record lookup — use this for ANY request about DNS records of a domain."""
    base = WEB_TOOLS_URL
    if params.record_type == "propagation":
        prop_type = params.propagation_type or "A"  # None-safe: LLM may pass null
        resp = await ctx.http.get(f"{base}/v1/dns/propagation/{params.domain}",
                                  params={"record_type": prop_type})
    elif params.authoritative and params.record_type in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"):
        resp = await ctx.http.get(f"{base}/v1/dns/authoritative/{params.record_type.lower()}/{params.domain}")
    else:
        resp = await ctx.http.get(f"{base}/v1/dns/{params.record_type.lower()}/{params.domain}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "DNS lookup failed", retryable=False)
    return ActionResult.success(
        data=build_domain_check(params.domain, params.record_type, body["data"]),
        summary=f"DNS {params.record_type} for {params.domain}",
        ui=dns_ui(params.domain, params.record_type, body["data"]),
    )


# ─── SSL ──────────────────────────────────────────────────────────────────── #

class SslCheckParams(BaseModel):
    """SSL certificate check parameters."""
    domain: str
    full: bool = Field(default=False, description="Full check — adds chain, SANs, fingerprint, TLS version support")
    port: int = 443


@chat.function("ssl_check", action_type="read",
               data_model=SslResult,
               description="SSL certificate QUALITY — grade A-F, days until expiry, issuer, TLS version support. Full mode adds chain, SANs, fingerprint. Use this to answer 'how good is my SSL cert?'. To check if SSL is accessible FROM different world regions, use geo_check with check_type=ssl instead.")
async def fn_ssl_check(ctx, params: SslCheckParams) -> ActionResult:
    """SSL certificate QUALITY — grade A-F, days until expiry, issuer, TLS version support."""
    suffix = "/full" if params.full else ""
    resp = await ctx.http.get(f"{WEB_TOOLS_URL}/v1/ssl/{params.domain}{suffix}",
                              params={"port": params.port})
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "SSL check failed", retryable=False)
    return ActionResult.success(
        data=build_ssl(params.domain, params.port, body["data"]),
        summary=f"SSL {'full ' if params.full else ''}check for {params.domain}",
        ui=ssl_ui(params.domain, body["data"]),
    )


# ─── WHOIS ────────────────────────────────────────────────────────────────── #

class WhoisParams(BaseModel):
    """WHOIS lookup parameters."""
    target: str = Field(description="Domain name or IP address")
    target_type: Literal["domain", "ip"] = "domain"
    detail: Literal["full", "quick", "dates", "registrar", "availability"] = Field(
        default="quick",
        description="'quick' — key fields, 'full' — complete, 'dates'/'registrar'/'availability' — specific section",
    )


@chat.function("whois_lookup", action_type="read",
               data_model=DomainCheckResult,
               description="WHOIS ownership data — for domains: registrar, creation/expiry dates, nameservers, status. For IPs: owner org, ASN, country, abuse contact. Use target_type=ip for IP addresses. NOTE: for IP geolocation (city, latitude, latitude) use network_check with check_type=ip_lookup instead.")
async def fn_whois_lookup(ctx, params: WhoisParams) -> ActionResult:
    """WHOIS ownership data — for domains: registrar, creation/expiry dates, nameservers, status."""
    base = WEB_TOOLS_URL
    if params.target_type == "ip":
        resp = await ctx.http.get(f"{base}/v1/whois/ip/{params.target}")
    elif params.detail == "full":
        resp = await ctx.http.get(f"{base}/v1/whois/{params.target}")
    elif params.detail == "quick":
        resp = await ctx.http.get(f"{base}/v1/whois/{params.target}/quick")
    else:
        resp = await ctx.http.get(f"{base}/v1/whois/{params.target}/{params.detail}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "WHOIS lookup failed", retryable=False)
    return ActionResult.success(
        data=build_domain_check(params.target, f"whois_{params.detail}", body.get("data")),
        summary=f"WHOIS {params.detail} for {params.target}",
    )


# ─── HTTP ─────────────────────────────────────────────────────────────────── #

class HttpCheckParams(BaseModel):
    """HTTP analysis parameters."""
    domain: str
    check_type: Literal["headers", "grade", "quick", "missing", "status", "status_quick", "redirects"] = Field(
        default="grade",
        description="headers=full analysis, grade=score only, quick=grade+counts, missing=broken headers+fixes, status, redirects",
    )
    mode: Literal["standard", "strict"] = Field(default="standard", description="standard=6 headers, strict=8 headers")


@chat.function("http_check", action_type="read",
               data_model=DomainCheckResult,
               description="HTTP security headers QUALITY — grade A+ to F (HSTS/CSP/X-Frame-Options/X-Content-Type-Options), missing headers with fix tips, redirect chain, response time. Use to answer 'how secure are my HTTP headers?'. To check if site responds from different world regions, use geo_check with check_type=http instead.")
async def fn_http_check(ctx, params: HttpCheckParams) -> ActionResult:
    """HTTP security headers QUALITY — grade A+ to F (HSTS/CSP/X-Frame-Options/X-Content-Type-Options), missing headers with..."""
    base = WEB_TOOLS_URL
    if params.check_type in ("headers", "grade", "quick", "missing"):
        suffix = "" if params.check_type == "headers" else f"/{params.check_type}"
        resp = await ctx.http.get(f"{base}/v1/http/headers/{params.domain}{suffix}",
                                  params={"mode": params.mode})
    elif params.check_type == "status":
        resp = await ctx.http.get(f"{base}/v1/http/status", params={"url": params.domain})
    elif params.check_type == "status_quick":
        resp = await ctx.http.get(f"{base}/v1/http/status/quick", params={"url": params.domain})
    else:
        resp = await ctx.http.get(f"{base}/v1/http/redirects", params={"url": params.domain})
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "HTTP check failed", retryable=False)
    return ActionResult.success(
        data=build_domain_check(params.domain, params.check_type, body["data"]),
        summary=f"HTTP {params.check_type} for {params.domain}",
        ui=http_ui(params.domain, body["data"]) if params.check_type in ("grade","quick","headers","missing") else None,
    )


# ─── Network ──────────────────────────────────────────────────────────────── #

class NetworkCheckParams(BaseModel):
    """Network diagnostic parameters."""
    target: str = Field(description="Domain name or IP address")
    check_type: Literal["ping", "traceroute", "reverse_dns", "ip_lookup", "ip_lookup_quick", "asn"] = Field(
        default="ping",
        description="ping=RTT/loss, traceroute=MTR per-hop, reverse_dns=PTR, ip_lookup=geo+ASN, asn=ASN WHOIS",
    )

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


@chat.function("network_check", action_type="read",
               data_model=DomainCheckResult,
               description="Network diagnostics. Works with BOTH domains and IPs: ping (latency/packet loss), traceroute (per-hop MTR path). Works with IP ADDRESSES ONLY — never use on a domain name: ip_lookup (geolocation: city/lat/lon/country — different from whois_lookup which gives ownership), reverse_dns (PTR record — who is this IP?), asn (ASN WHOIS prefix list). Example: ping for 'amplica.md', ip_lookup for '104.18.15.2'.")
async def fn_network_check(ctx, params: NetworkCheckParams) -> ActionResult:
    """Network diagnostics."""
    paths = {
        "ping":            f"/v1/network/ping/{params.target}",
        "traceroute":      f"/v1/network/traceroute/{params.target}",
        "reverse_dns":     f"/v1/network/reverse/{params.target}",
        "ip_lookup":       f"/v1/network/ip-lookup/{params.target}",
        "ip_lookup_quick": f"/v1/network/ip-lookup/{params.target}/quick",
        "asn":             f"/v1/network/asn/{params.target}",
    }
    resp = await ctx.http.get(f"{WEB_TOOLS_URL}{paths[params.check_type]}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "Network check failed", retryable=False)
    return ActionResult.success(
        data=build_domain_check(params.target, params.check_type, body["data"]),
        summary=f"Network {params.check_type} for {params.target}",
    )


# ─── SEO ──────────────────────────────────────────────────────────────────── #

class SeoCheckParams(BaseModel):
    """SEO check parameters."""
    target: str = Field(description="Domain or full URL (full URL for meta check)")
    check_type: Literal["meta", "robots", "sitemap", "indexing"] = Field(
        default="meta",
        description="meta=title/description/issues, robots=robots.txt rules, sitemap=sitemap.xml, indexing=Google status",
    )


@chat.function("seo_check", action_type="read",
               data_model=DomainCheckResult,
               description="SEO check — meta title/description length and issues, robots.txt rules, sitemap.xml validation, Google indexing status. Use check_type to target a specific area.")
async def fn_seo_check(ctx, params: SeoCheckParams) -> ActionResult:
    """SEO check — meta title/description length and issues, robots.txt rules, sitemap.xml validation, Google indexing status."""
    base = WEB_TOOLS_URL
    use_url = params.check_type == "meta"
    param_key = "url" if use_url else "domain"
    endpoints = {
        "meta":     f"{base}/v1/seo/meta",
        "robots":   f"{base}/v1/seo/robots",
        "sitemap":  f"{base}/v1/seo/sitemap",
        "indexing": f"{base}/v1/seo/indexing-status",
    }
    resp = await ctx.http.get(endpoints[params.check_type], params={param_key: params.target})
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error") or "SEO check failed", retryable=False)
    return ActionResult.success(
        data=build_domain_check(params.target, params.check_type, body["data"]),
        summary=f"SEO {params.check_type} for {params.target}",
    )
