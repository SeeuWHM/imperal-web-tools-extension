# Changelog

## [Unreleased] — 2026-04-30

### Fixed
- **SDK 3.x migration** — `ctx.user.id` → `ctx.user.imperal_id` across all 12 files (`AttributeError` on SDK 3.0+ without this)
- **`app.py`** — removed deprecated `model=` parameter from `ChatExtension` (removed in SDK v1.6.0)
- **`skeleton.py`** — `@ext.tool("skeleton_refresh_web_tools", **kwargs)` → `@ext.skeleton("web_tools", ttl=300)` (canonical SDK decorator)
- **`handlers_quick.py`** `get_panel_data` — skeleton data key corrected: `"skeleton_refresh_web_tools"` → `"web_tools"` (matches `@ext.skeleton("web_tools", ...)`)
- **`imperal.json`** — removed `kwargs` from skeleton tool parameters entry (`{}` is correct for skeleton tools)
- **`GeoCheckParams`** — added `model_validator(mode="before")` accepting `domains`/`domain`/`host` → `target` alias (LLM compat: prevents `VALIDATION_MISSING_FIELD` when LLM passes `domains=['...']` instead of `target='...'`)
- **`NetworkCheckParams`** — same alias validator as `GeoCheckParams`

### Other
- Git repository initialized and connected to `github-web-tools:SeeuWHM/imperal-web-tools-extension.git`

---

## [1.4.0] — 2026-04-21

### Added
- **LEFT panel** — Domain Scan + IP Scan with tab-button switching
- **`run_scan_tool`** — multi-domain on-demand scan (1-10 domains, 9 check toggles)
- **`run_ip_scan`** — IP scan (1-5 IPs, 5 check toggles: Info/BL/PTR/Geo Ping/Ports)
- **`quick_check`** — single domain preset (full/dns/ssl/http/email/blacklist/geo/ports)
- **`create_monitor_full`** — one-step atomic monitor creation from panel (group + profile + monitor)
- **`handlers_quick.py`** split out from `handlers_scan.py`
- **System prompt** fully rewritten — 31 functions, result interpretation guide, common workflows

### Changed
- RIGHT panel redesigned: stats bar + bar chart + sorted monitor cards
- New Monitor form moved to `view=new` within `__panel__overview`
- `panels_setup.py` superseded (no longer imported — legacy reference only)

---

## [1.3.0-fixes] — 2026-04-22 / 2026-04-23

### Fixed
- **Scheduler fan-out** — `ctx.store.list_users()` + `ctx.as_user()` pattern: system context was returning 0 monitors (user-owned records invisible to system user_id)
- **Port scan** — was reading `data["ports"]`, API returns `data["results"]`; always showed "All closed"
- **WHOIS expiry** — was reading `expiry_date`, API returns `expires` + `days_until_expiry`
- **IP scan empty** — `ip_lookup`/`reverse`/`geo_ping` Pydantic defaults were `False`; raised to `True`
- **`asyncio.CancelledError`** — not re-raised in bare `except Exception`; added `return_exceptions=True`
- **TagInput regex** — old `^[a-zA-Z0-9][a-zA-Z0-9.\-]+$` accepted `notadomain`; new requires at least one dot
- **Quick check error handling** — `resp.raise_for_status()` wrapped in try/except, returns `ActionResult.error(retryable=True)`
- **Detail panel summary** — was using check-level counts instead of domain-level `summary` dict from snapshot
- **IP scan status default** — `"ok"` → `"unknown"` for items with no data

### Changed
- Space added as TagInput delimiter in all 3 forms
- Regions display: EU→WEU, MD→EEU, SG→AS
- DNSBL count: 30 → 29 (Invaluement ivmSIP removed — SIP/VoIP list, false positives on hosting IPs)

### Removed
- `_domain_explain_msg` from `panels_ui.py` (orphaned after `actions=[]` GAP-B workaround)

---

## [1.2.0] — 2026-04-16

### Added
- **`@ext.schedule`** — `wt_monitor_runner`, cron `0 * * * *`. Hourly check: runs overdue monitors
- **`ui.TagInput`** for domains in all group/monitor forms
- **`ui.Toggle`** per check type in check profile create/edit forms (defaults: SSL/HTTP/Email/Blacklist ON)
- Domain Groups + Check Profiles as separate entities with full CRUD

### Changed
- `delete_monitor` now cascade-deletes snapshots
- `update_domain_group` accepts `domains: list[str]` for full replacement from TagInput
- Interval display: `every 168h` → `every week`, `every 48h` → `every 2 days`
- Bar chart: Unknown column added; monitor names show ellipsis on truncation

---

## [1.0.0] — 2026-04-13

### Added
- 26 chat functions: DNS, SSL, WHOIS, HTTP, email, blacklist, ports, SMTP, network, SEO, geo probe, full audit
- Domain health monitoring: groups + profiles + monitors + snapshots
- LEFT sidebar + RIGHT panel + monitor detail view
- Skeleton refresh for instant AI context (monitor status summary)
- `WEB_TOOLS_API_URL` env var for self-hosted backend
- `@ext.health_check` → `/v1/health`
