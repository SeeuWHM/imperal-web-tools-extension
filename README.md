# imperal-web-tools-extension

[![Imperal SDK](https://img.shields.io/badge/imperal--sdk-1.5.0-blue)](https://pypi.org/project/imperal-sdk/)
[![Version](https://img.shields.io/badge/version-1.0.0-green)](https://github.com/SeeuWHM/imperal-web-tools-extension/releases)
[![License](https://img.shields.io/badge/license-LGPL--2.1-orange)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Imperal%20Cloud-purple)](https://panel.imperal.io)

**Web diagnostics and domain health monitoring extension for [Imperal Cloud](https://panel.imperal.io).**

Brings DNS, SSL, HTTP, email, blacklist, geo, and network diagnostics into your Imperal chat — plus a live monitoring dashboard that tracks multiple domain groups on a schedule.

---

## What It Does

Talk to it naturally:

```
"check webhostmost.com"
"is our SSL about to expire?"
"are any of our IPs blacklisted?"
"why is email going to spam on domain.com?"
"check DNS from EU, US, Singapore and Moldova"
"run full audit on all 8 domains in our infra group"
```

Or manage monitors from the panel — click a domain row to expand per-check details, press Scan Now, get instant results.

---

## Capabilities

### On-Demand Diagnostics

| Category | What it checks |
|----------|---------------|
| **DNS** | A, AAAA, MX, NS, TXT, CNAME, SRV, DNSSEC, global propagation, authoritative NS query |
| **SSL** | Validity, issuer, expiry days, grade A–F, certificate chain, SANs, TLS version support |
| **WHOIS** | Registrar, registration/expiry dates, nameservers, availability check |
| **HTTP** | Security headers grade A+–F (HSTS, CSP, X-Frame-Options, X-Content-Type), redirect chain |
| **Email** | SPF, DMARC, DKIM, BIMI + full deliverability grade A–F, SPF/DMARC generator, header trace |
| **Blacklist** | 30 DNSBL databases in parallel — Spamhaus ZEN/SBL/XBL, SpamCop, Barracuda, SURBL |
| **Ports** | Single port check or preset scan: web / mail / database / all |
| **SMTP** | Full handshake — EHLO, STARTTLS, AUTH methods, banner via MX or direct host |
| **Network** | ICMP ping, MTR traceroute, PTR reverse DNS, IP geolocation + ASN |
| **SEO** | Meta tags, robots.txt, sitemap.xml, Google indexing status |
| **Geo Probe** | DNS/ping/HTTP/SSL/traceroute from EU, US, SG, MD simultaneously |
| **Full Audit** | All checks in parallel — complete domain health snapshot in one call |

### Domain Health Monitoring

Set up recurring scans in three steps:

1. **Domain Group** — a named list of domains (up to 20)
2. **Check Profile** — which checks to run per scan: dns / ssl / http / email / blacklist / geo
3. **Monitor** — link group + profile + interval (1h / 6h / 12h / 24h / 48h / 7d)

Run `run_scan` to trigger immediately. Results stored as snapshots — view per-domain per-check status in the panel, expand any row to see what specifically failed.

---

## Panel UI

Built on [Imperal Declarative UI](https://github.com/imperalcloud/imperal-sdk) — zero custom React.

```
┌──── Left Panel ────────────────────┐  ┌──── Right Panel ────────────────────────┐
│  [3 Monitors]  [1 Crit]  [1 Warn]  │  │  [3]  [1 Crit]  [1 Warn]  [1 OK]        │
│                                    │  │  ──────────────────────────────────────   │
│  Monitors  │  Quick Scan  │  Setup │  │  Email Stack  ·  CRITICAL  ·  today       │
│  ───────────────────────────────   │  │    webhostmost.com    CRITICAL  ▸          │
│  + New Monitor  ▼                  │  │      DNS: OK · SSL: 12d · Email: F grade   │
│  ───────────────────────────────   │  │    mail.whm.com       OK       ▸           │
│  Email Stack    CRITICAL  [▶]      │  │                                            │
│  Web Infra      WARNING   [▶]      │  │  Web Infra  ·  WARNING  ·  6h ago  [▶]    │
│  Client Sites   OK        [▶]      │  │  ──────────────────────────────────────   │
└────────────────────────────────────┘  │  Last Quick Check                          │
                                        │  google.com · full · 14:22                 │
                                        │  DNS: OK · SSL: OK · HTTP: A+              │
                                        └──────────────────────────────────────────┘
```

**Left panel:**
- Stats strip — total monitors / critical / warning
- **Monitors tab** — list with inline Scan Now `[▶]` and delete; click any row → detail view opens in right panel
- **Quick Scan tab** — domain + check type, result appears in right panel
- **Setup tab** — inline forms for creating domain groups, check profiles, and monitors

**Right panel:**
- Live stats from store (always accurate)
- Per-monitor sections with expandable domain rows — click to see per-check breakdown
- Single-monitor detail view with `← All Monitors` back button
- Last quick check result block

---

## File Structure

```
imperal-web-tools-extension/
├── main.py             # Entry point — sys.modules cleanup + imports
├── app.py              # Extension setup, ChatExtension, health check
├── handlers.py         # DNS, SSL, WHOIS, HTTP, Network, SEO
├── handlers_diag.py    # Email, Blacklist, Ports, SMTP, Geo, Full Audit
├── handlers_groups.py  # Domain Groups, Check Profiles, Monitors CRUD
├── handlers_scan.py    # Scan runner, results, quick check
├── panels.py           # @ext.panel handlers — sidebar + stats
├── panels_ui.py        # Panel UI helpers — options, labels, list builders
├── skeleton.py         # Background skeleton refresh
├── system_prompt.txt   # LLM system prompt
└── imperal.json        # Extension manifest
```

---

## Function Reference

### Diagnostics (12 functions)

| Function | Description |
|----------|-------------|
| `dns_lookup` | DNS records — A/AAAA/MX/NS/TXT/CNAME/SRV/DNSSEC/all, propagation, authoritative query |
| `ssl_check` | Certificate validity, issuer, expiry days, grade. Full mode adds chain + SANs + TLS |
| `whois_lookup` | Domain registrar, dates, nameservers, availability. IP ASN/org/country |
| `http_check` | Security headers grade A+–F, missing headers with fix tips, redirect chain |
| `seo_check` | Meta tags, robots.txt, sitemap.xml, Google indexing status |
| `email_check` | SPF/DMARC/DKIM/BIMI, full grade A–F, raw header trace, SPF/DMARC generator |
| `blacklist_check` | IP against 30 DNSBL or domain SURBL — clean / listed / critical |
| `port_scan` | Single TCP port or preset scan: web / mail / database / all |
| `smtp_test` | SMTP handshake via MX or direct host — EHLO, STARTTLS, AUTH, banner |
| `network_check` | ICMP ping, MTR traceroute, PTR reverse DNS, IP geolocation, ASN WHOIS |
| `geo_check` | Multi-region probe from EU/US/SG/MD — dns / ping / http / ssl / traceroute / full |
| `domain_full_check` | Full parallel audit — DNS + SSL + WHOIS + HTTP + email + blacklist + geo |

### Monitoring (14 functions)

| Function | Description |
|----------|-------------|
| `create_domain_group` | Create a named group of domains (max 5 groups, 20 domains each) |
| `update_domain_group` | Rename group, add or remove domains |
| `list_domain_groups` | List all domain groups |
| `delete_domain_group` | Delete group and associated monitors |
| `create_check_profile` | Define which checks to run per scan (max 5 profiles, 5 checks each) |
| `list_check_profiles` | List all check profiles |
| `delete_check_profile` | Delete profile and associated monitors |
| `create_monitor` | Link group + profile + interval (max 5 monitors) |
| `list_monitors` | List monitors with group, profile, interval, last scan time |
| `delete_monitor` | Delete a monitor |
| `run_scan` | Trigger immediate scan — stores snapshot, fires `scan.completed` event |
| `get_scan_results` | Get last snapshot — per-domain per-check status and overall verdict |
| `quick_check` | One-shot check from panel — result stored and shown in right panel |
| `get_panel_data` | Panel summary for LLM context — monitors, groups, profiles counts and statuses |

---

## Store Collections

| Collection | Contents |
|------------|----------|
| `wt_groups` | Domain groups — name, domain list |
| `wt_profiles` | Check profiles — name, check types |
| `wt_monitors` | Monitors — group_id, profile_id, interval_hours, last_run_at, last_snapshot_id |
| `wt_snapshots` | Scan results — per-domain per-check status, overall verdict, summary counts |
| `wt_quick_results` | Last quick check result per user |

---

## Events

| Event | Fired by | Effect |
|-------|----------|--------|
| `scan.completed` | `run_scan` | Both panels refresh |
| `quick.completed` | `quick_check` | Right panel refreshes |
| `monitor.created` | `create_monitor` | Both panels refresh |
| `monitor.deleted` | `delete_monitor` | Both panels refresh |
| `group.created` | `create_domain_group` | Left panel refreshes |
| `group.deleted` | `delete_domain_group` | Left panel refreshes |
| `profile.created` | `create_check_profile` | Left panel refreshes |
| `profile.deleted` | `delete_check_profile` | Left panel refreshes |

---

## Skeleton

`skeleton_refresh_web_tools` provides instant AI context without store queries:

```python
{
    "total": 3, "critical": 1, "warning": 1, "ok": 1,
    "monitors": {
        "monitor_id": {
            "name": "Email Stack",
            "status": "critical",
            "last_run_at": "2026-04-13T10:00:00",
            "interval_hours": 24,
            "summary": {"ok": 1, "warning": 0, "critical": 2}
        }
    }
}
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_TOOLS_API_URL` | `https://api.webhostmost.com/web-tools` | Backend API URL. Override for self-hosted deployments. |

---

## Built with

- [imperal-sdk](https://github.com/imperalcloud/imperal-sdk) 1.5.0
- [Imperal Cloud](https://panel.imperal.io)
