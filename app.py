"""web-tools · Web Diagnostics Extension."""
from __future__ import annotations

import os
from pathlib import Path

from imperal_sdk import Extension
from imperal_sdk.chat import ChatExtension

# ─── Extension Setup ──────────────────────────────────────────────────────── #

ext = Extension("web-tools", version="1.1.0")

# URL of the web-tools-api backend. Override via env var for self-hosted deployments.
WEB_TOOLS_URL = os.getenv("WEB_TOOLS_API_URL", "https://api.webhostmost.com/web-tools")

_SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()

chat = ChatExtension(
    ext=ext,
    tool_name="tool_web_tools_chat",
    description=(
        "Web diagnostics for any domain or IP — DNS records A AAAA MX NS TXT CNAME SRV DNSSEC "
        "propagation authoritative, SSL certificate validity issuer expiry grade chain SANs TLS, "
        "WHOIS domain registrar dates nameservers registrant status, HTTP security headers grade "
        "A+ to F HSTS CSP XFO XCTO redirects chain status response time, SEO meta tags title "
        "description robots.txt sitemap.xml Google indexing, email deliverability SPF DMARC DKIM "
        "BIMI grade generate record trace headers, IP blacklist 30 DNSBL Spamhaus SpamCop Barracuda "
        "verdict clean listed critical, TCP port scan web mail database preset open closed filtered, "
        "SMTP test MX connectivity EHLO STARTTLS AUTH banner, IP geolocation ASN country org, "
        "multi-region geo probe EU US SG MD latency mismatch anycast, full domain audit parallel, "
        "domain groups check profiles monitors create_monitor run_scan trigger scan immediate scan "
        "wt_snapshots domain health snapshot scan results list_monitors list_domain_groups"
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
