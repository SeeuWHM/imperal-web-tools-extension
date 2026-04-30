"""web-tools · Diagnostic handlers — DNS, SSL, WHOIS, HTTP, Network, SEO."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult

# ─── DNS ──────────────────────────────────────────────────────────────────── #

class DnsLookupParams(BaseModel):
    """DNS lookup parameters."""
    domain: str
    record_type: Literal["A","AAAA","IP","MX","NS","TXT","CNAME","SRV","DNSSEC","all","propagation"] = "A"
    authoritative: bool = Field(default=False, description="Query from domain's own authoritative NS (A/AAAA/MX/NS/TXT/CNAME)")
    propagation_type: Literal["A","MX","NS","TXT","CNAME"] = Field(default="A", description="Record type for propagation check")


@chat.function("dns_lookup", action_type="read",
               description="DNS records — A/AAAA/IP/MX/NS/TXT/CNAME/SRV/DNSSEC/all types, global propagation check, authoritative NS direct query")
async def fn_dns_lookup(ctx, params: DnsLookupParams) -> ActionResult:
    base = WEB_TOOLS_URL
    if params.record_type == "propagation":
        resp = await ctx.http.get(f"{base}/v1/dns/propagation/{params.domain}",
                                  params={"record_type": params.propagation_type})
    elif params.authoritative and params.record_type in ("A", "AAAA", "MX", "NS", "TXT", "CNAME"):
        resp = await ctx.http.get(f"{base}/v1/dns/authoritative/{params.record_type.lower()}/{params.domain}")
    else:
        resp = await ctx.http.get(f"{base}/v1/dns/{params.record_type.lower()}/{params.domain}")
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "DNS lookup failed"), retryable=False)
    return ActionResult.success(
        data={"domain": params.domain, "type": params.record_type, "records": body["data"]},
        summary=f"DNS {params.record_type} for {params.domain}",
    )


# ─── SSL ──────────────────────────────────────────────────────────────────── #

class SslCheckParams(BaseModel):
    """SSL certificate check parameters."""
    domain: str
    full: bool = Field(default=False, description="Full check — adds chain, SANs, fingerprint, TLS version support")
    port: int = 443


@chat.function("ssl_check", action_type="read",
               description="SSL certificate — validity, issuer, expiry days, grade A-F. Full mode: chain, SANs, fingerprint, TLS protocols")
async def fn_ssl_check(ctx, params: SslCheckParams) -> ActionResult:
    suffix = "/full" if params.full else ""
    resp = await ctx.http.get(f"{WEB_TOOLS_URL}/v1/ssl/{params.domain}{suffix}",
                              params={"port": params.port})
    resp.raise_for_status()
    body = resp.json()
    if not body.get("success"):
        return ActionResult.error(body.get("error", "SSL check failed"), retryable=False)
    return ActionResult.success(
        data={"domain": params.domain, "port": params.port, **body["data"]},
        summary=f"SSL {'full ' if params.full else ''}check for {params.domain}",
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
               description="WHOIS — domain registrar/dates/nameservers/status or IP ASN/org/country. Detail: quick/full/dates/registrar/availability")
async def fn_whois_lookup(ctx, params: WhoisParams) -> ActionResult:
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
        return ActionResult.error(body.get("error", "WHOIS lookup failed"), retryable=False)
    return ActionResult.success(
        data={"target": params.target, "type": params.target_type, "data": body.get("data")},
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
               description="HTTP — security headers grade A+ to F (HSTS/CSP/XFO/XCTO), missing headers with fix tips, redirect chain, status/response time")
async def fn_http_check(ctx, params: HttpCheckParams) -> ActionResult:
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
        return ActionResult.error(body.get("error", "HTTP check failed"), retryable=False)
    return ActionResult.success(
        data={"domain": params.domain, "check_type": params.check_type, "result": body["data"]},
        summary=f"HTTP {params.check_type} for {params.domain}",
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
               description="Network — ICMP ping RTT/loss, MTR traceroute per-hop stats, PTR reverse DNS, IP geolocation+ASN, ASN WHOIS prefixes")
async def fn_network_check(ctx, params: NetworkCheckParams) -> ActionResult:
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
        return ActionResult.error(body.get("error", "Network check failed"), retryable=False)
    return ActionResult.success(
        data={"target": params.target, "check_type": params.check_type, "result": body["data"]},
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
               description="SEO — meta tags (title/description lengths/issues), robots.txt rules, sitemap.xml validation, Google indexing status")
async def fn_seo_check(ctx, params: SeoCheckParams) -> ActionResult:
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
        return ActionResult.error(body.get("error", "SEO check failed"), retryable=False)
    return ActionResult.success(
        data={"target": params.target, "check_type": params.check_type, "result": body["data"]},
        summary=f"SEO {params.check_type} for {params.target}",
    )
