# Changelog

## [1.4.0-patch3] — 2026-05-10

### Fixed
- **`main.py:27`** — literal `\n` embedded in Python comment caused `handlers_quick` to never import; `quick_check`, `run_scan_tool`, `run_ip_scan`, `get_panel_data` were unregistered — Scan Tool left panel was completely broken (all form actions returned "tool not found"). Split into two separate import lines.

### Changed
- **`effects=`** added to all write/destructive `@chat.function` handlers (V20 compliance — becomes ERROR in SDK v5.0.0):
  - `handlers_groups.py`: `create_domain_group` → `["create:domain_group"]`, `update_domain_group` → `["update:domain_group"]`, `delete_domain_group` → `["delete:domain_group"]`
  - `handlers_monitors.py`: `create_monitor` → `["create:monitor"]`, `update_monitor` → `["update:monitor"]`, `delete_monitor` → `["delete:monitor"]`, `create_monitor_full` → `["create:monitor","create:domain_group","create:check_profile"]`
  - `handlers_profiles.py`: `create_check_profile` → `["create:check_profile"]`, `update_check_profile` → `["update:check_profile"]`, `delete_check_profile` → `["delete:check_profile"]`
  - `handlers_scan.py`: `run_scan` → `["create:scan_result"]`
  - `handlers_quick.py`: `quick_check`, `run_scan_tool`, `run_ip_scan` → `["create:scan_result"]`
- **`imperal.json`** — upgraded to manifest_schema_version=3; all 31 `@chat.function` handlers emitted as typed tool entries with `action_type`, `chain_callable`, `effects`, `event`; resolves "Manifest matches code" portal warning
- **`handlers_quick.py`** — compacted `get_panel_data` return dict (302L → 298L)

---

## [1.4.0-patch2] — 2026-05-09

### Fixed
- **`page.items` → `page.data`** everywhere — `Page` class has `.data`, not `.items`; all store query paths were silently failing (empty results on update/list operations)
- **`refresh_panels` format** — removed `__panel__` prefix; correct format is bare panel IDs `["sidebar","overview"]`, not `["__panel__sidebar",...]`; panels were not refreshing after any write operation

### Added
- **`handlers_ui.py`** — inline UI builders: `ssl_ui`, `dns_ui`, `blacklist_ui`, `http_ui`, `full_audit_ui` used in `ActionResult.ui` for rich inline chat display
- **`ActionResult.ui`** — DNS, SSL, HTTP, Blacklist chat functions now return formatted inline UI in chat alongside the plain summary
- **`ctx.progress`** in `fn_run_scan_tool` — progress updates at each domain + 0%/90%/100% milestones

### Changed
- **`panels_ui.py`** (384L) split into `panels_ui_base.py` (143L) + `panels_ui_items.py` (248L); `panels_ui.py` is now a thin re-export shim (9L)

---

## [1.4.0-patch1] — 2026-05-09

### Added
- **V14**: `Extension(description=...)` — domain health monitoring description ≥40 chars
- **V15**: `Extension(display_name='Web Tools')` added
- **V17**: `EmptyParams` class added to `handlers_groups.py`, `handlers_profiles.py`, `handlers_monitors.py`, `handlers_quick.py` — all parameterless `@chat.function` handlers now comply
- **V21**: `icon.svg` created (globe icon, valid SVG with viewBox); `Extension(icon='icon.svg')` set
- **`actions_explicit=True`** added to `Extension` per federal contract

### Changed
- All 26 `@chat.function` descriptions rewritten — unambiguous, distinguishes similar functions (run_scan vs run_scan_tool vs quick_check, create_monitor vs create_monitor_full), cross-references list_* functions for ID lookup, warns about cascade deletes

---

## [1.4.0] — 2026-04-30 (first git push)

### Fixed (SDK 3.x migration)
- **`ctx.user.id` → `ctx.user.imperal_id`** across all 12 files (`AttributeError` on SDK 3.0+ without this)
- **`app.py`** — removed deprecated `model=` parameter from `ChatExtension` (removed in SDK v1.6.0)
- **`skeleton.py`** — `@ext.tool("skeleton_refresh_web_tools", **kwargs)` → `@ext.skeleton("web_tools", ttl=300)` (canonical SDK decorator)
- **`handlers_quick.py`** `get_panel_data` — skeleton key corrected: `"skeleton_refresh_web_tools"` → `"web_tools"`
- **`imperal.json`** — removed `kwargs` from skeleton tool parameters entry (`{}` is correct for skeleton tools)
- **`GeoCheckParams`** — `model_validator(mode="before")` accepting `domains`/`domain`/`host` → `target` alias (LLM compat)
- **`NetworkCheckParams`** — same alias validator

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
