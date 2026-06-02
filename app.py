"""web-tools · Web Diagnostics Extension (SDK v5.2.0 / SDL)."""
from __future__ import annotations

import os

from imperal_sdk import Extension
from imperal_sdk.chat import ChatExtension

# ─── Extension Setup ──────────────────────────────────────────────────────── #

ext = Extension(
    "web-tools",
    version="1.5.0",
    display_name="Web Tools",
    description=(
        "Domain health monitoring — DNS, SSL, HTTP headers grade, blacklist 30 DNSBL, "
        "WHOIS, SEO, email SPF/DMARC/DKIM, geo probes from 4 regions, port scans, "
        "SMTP test, recurring automated monitors with alerts."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["store:read", "store:write"],
)

# URL of the web-tools-api backend. Override via env var for self-hosted deployments.
WEB_TOOLS_URL = os.getenv("WEB_TOOLS_API_URL", "https://api.webhostmost.com/web-tools")

# SDK 5.0.0+: ChatExtension is a @chat.function bundle — no LLM router, no system_prompt.
# LLM guidance lives in Extension(description=...) + per-@chat.function(description=...).
chat = ChatExtension(
    ext=ext,
    tool_name="tool_web_tools_chat",
    description=(
        "Web Tools extension has two modes: "
        "1) INSTANT DIAGNOSTICS (no setup needed, works on any domain/IP right now): "
        "domain_full_check=full audit table in one call; "
        "dns_lookup=DNS records A/MX/NS/TXT/CNAME/DNSSEC/propagation; "
        "ssl_check=certificate quality grade A-F expiry chain; "
        "http_check=security headers grade HSTS CSP XFO missing headers; "
        "whois_lookup=registrar dates nameservers for domain or ASN org for IP; "
        "seo_check=meta tags robots.txt sitemap Google indexing; "
        "email_check=SPF DMARC DKIM BIMI grade generate records trace headers; "
        "blacklist_check=29 DNSBL spam lists verdict clean/listed/critical; "
        "port_scan=TCP ports web/mail/database presets or single port; "
        "smtp_test=SMTP connectivity STARTTLS AUTH banner; "
        "geo_check=reachability FROM EU/US/SG/MD ping latency HTTP DNS SSL per region; "
        "network_check=ping traceroute for domains; ip_lookup reverse_dns ASN for IPs only. "
        "2) RECURRING MONITORS (scheduled automation for own domains): "
        "create_monitor_full=set up automated domain monitoring; "
        "list_monitors=show existing scheduled monitors; "
        "run_scan=trigger immediate scan on an existing monitor; "
        "run_scan_tool=bulk scan up to 10 domains; run_ip_scan=bulk scan up to 5 IPs."
    ),
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
