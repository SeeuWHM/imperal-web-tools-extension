# Changelog

## [1.2.0] — 2026-04-16

### Added
- **`@ext.schedule`** — `wt_monitor_runner`, cron `0 * * * *` (SDK v1.5.4 pattern). Global hourly check: queries all enabled monitors, runs those where `last_run_at + interval_hours ≤ now`. Previous snapshot deleted on each run to prevent store bloat.
- **Setup as SlideOver** — `__panel__setup` now renders as `ui.SlideOver(width="lg")`. Opens as a slide-over popup, closes back to overview.
- **TagInput for domains** — `ui.TagInput` (fixed in SDK v1.5.4) replaces plain CSV input. Type domain + Enter or Space to add as a tag; × to remove. Works in both create and edit forms.
- **Toggle+Tooltip check selection** — `ui.Toggle` + `ui.Tooltip` per check type in profile create form. Hover ℹ icon to see what each check returns (grade, days, regions, etc.). Defaults: SSL/HTTP/Email/Blacklist ON.
- **Monitors list in Setup** — existing monitors now shown in Setup panel with delete actions (was missing).
- **Group edit in Setup** — existing groups expand to show TagInput edit form.

### Changed
- Sidebar: removed "+ New Monitor" button — single "Setup" entry point.
- `update_domain_group`: accepts `domains: list[str]` for full replacement from TagInput.
- `create_check_profile`: accepts individual bool params (`ssl`, `http`, `email`, etc.) from toggles.
- `delete_monitor`: now cascade-deletes snapshots (was orphaning them).
- `skeleton.py`: default status fixed from `"ok"` → `"unknown"` for missing field.
- Interval display: `every 168h` → `every week`, `every 48h` → `every 2 days`, etc.
- Bar chart in overview: now includes Unknown column; monitor names show ellipsis on truncation.

## [1.0.0] — 2026-04-13

### Added
- 26 chat functions across 6 diagnostic categories: DNS, SSL, WHOIS, HTTP, email, blacklist, ports, SMTP, network, SEO, geo probe, full audit
- Domain health monitoring system: domain groups + check profiles + monitors + scan snapshots
- Enterprise panel UI: left sidebar with monitors list, quick scan form, setup accordions; right panel with live scan results and expandable domain rows
- Click-through navigation: clicking a monitor in the left panel opens detailed results in the right panel
- Quick check form with instant result display in right panel
- Skeleton refresh for instant AI context (monitor status summary, critical/warning/ok counts)
- Health check endpoint
- `WEB_TOOLS_API_URL` environment variable for self-hosted backend configuration
