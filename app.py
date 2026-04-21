"""web-tools · Web Diagnostics Extension."""
from __future__ import annotations

import os
from pathlib import Path

from imperal_sdk import Extension
from imperal_sdk.chat import ChatExtension

# ─── Extension Setup ──────────────────────────────────────────────────────── #

ext = Extension(
    "web-tools",
    version="1.4.0",
    capabilities=["store:read", "store:write"],
)

# URL of the web-tools-api backend. Override via env var for self-hosted deployments.
WEB_TOOLS_URL = os.getenv("WEB_TOOLS_API_URL", "https://api.webhostmost.com/web-tools")

_SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()

chat = ChatExtension(
    ext=ext,
    tool_name="tool_web_tools_chat",
    description=(
        "Web diagnostics and domain health monitoring — DNS A AAAA MX NS TXT CNAME SRV DNSSEC "
        "propagation authoritative nameserver, SSL grade A-F expiry chain SANs TLS versions, "
        "WHOIS domain registrar dates nameservers IP ASN org network, HTTP security headers grade "
        "A+ to F HSTS CSP XFO missing headers redirects chain status response time, SEO meta tags "
        "title description robots.txt sitemap.xml Google indexing, email SPF DMARC DKIM BIMI grade "
        "A-F generate records trace headers find originating IP, blacklist 29 DNSBL Spamhaus ZEN SBL "
        "XBL SpamCop Barracuda SURBL verdict clean listed critical, TCP ports web mail database all "
        "presets single port open closed filtered, SMTP test MX 587 25 465 STARTTLS AUTH banner, "
        "multi-region geo probe EU US SG MD ping latency HTTP availability DNS mismatch anycast SSL "
        "MTR traceroute, network ping traceroute PTR reverse DNS IP geolocation ASN WHOIS prefixes, "
        "domain health monitors recurring automated scan schedule hourly daily weekly, "
        "create_monitor_full one-step monitor setup domains checks interval, "
        "run_scan_tool bulk domain scan toggles ssl http email blacklist geo whois smtp propagation, "
        "run_ip_scan bulk IP scan ip_lookup blacklist reverse ports geo_ping"
    ),
    system_prompt=_SYSTEM_PROMPT,
    model="claude-haiku-4-5-20251001",
)

# ─── Health Check ─────────────────────────────────────────────────────────── #

@ext.health_check
async def health(ctx) -> dict:
    try:
        resp = await ctx.http.get(f"{WEB_TOOLS_URL}/v1/health")
        return {
            "status": "ok" if resp.status_code == 200 else "degraded",
            "version": ext.version,
        }
    except Exception:
        return {"status": "degraded", "version": ext.version}
