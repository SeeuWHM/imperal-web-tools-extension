# Changelog

## [1.10.0] — 2026-06-25 — Token economy: read `mode`, content_hash/outline/tables, search recency

Brings the extension 1:1 with the web-search↔Webbee integration spec
(`extensions/web-search-webbee-integration.md`, backend ≥ web-search-v0.7.0).

### Added — readers
- **`mode`** on all readers (`full` | `main` | `outline` | `tables` | `metadata`) — the token-economy lever.
  Triage with `metadata` (~0 tok) / `outline` (~100 tok) before pulling `full`; `tables` for price/data pages.
- **`PageContent`** now surfaces the full read contract: `content_hash` (sha256[:32] — DEDUP key),
  `word_count`, `outline` (heading tree), `tables` (structured) + enriched metadata.
- Descriptions teach the reading ladder (snippet → metadata/outline triage → full/tables on the 2–3 winners)
  and tell Webby to dedup on `content_hash` (don't re-ingest identical content).

### Added — search
- **`recency_days`** (required for 'today'/'latest' — Exa isn't recency-sorted), **`type`**, **`category`**.

### Notes
- Dedup is exposed as a FACT (`content_hash`), not enforced in the extension: the SDK Context has no
  conversation id and `ctx.cache` is per-user+TTL, so per-conversation `seen_hashes` belongs to Webby/kernel
  (which the integration spec targets). The extension's job is to surface the hash.
- Manifest rebuilt (SDK 5.7.3): tools unchanged at 38; params/return contracts enriched.

## [1.9.0] — 2026-06-25 — Heavy readers (Chromium + Office docs) + per-user read policy

### Added
- **`read_url_rendered`** ⚠️ TOKEN-HEAVY — headless-Chromium reader (`/v1/read_rendered`) for JS / bot-protected
  pages that the cheap `read_url` can't open. On-demand only.
- **`read_document`** ⚠️ TOKEN-HEAVY — Office document reader (`/v1/read_document`, `.docx/.xlsx/.pptx` → Markdown).
- **`set_web_read_policy(ask|always|never_heavy)`** — persists a per-user heavy-read preference in `wt_prefs`.
- `query` param added to all three readers (focus extraction/truncation on a question — backend supports it).

### Behaviour — cost-aware escalation (deterministic)
- When `read_url` fails on a page a heavy reader could open, it branches on the per-user policy:
  - **ask** (default): returns an escalation FACT (which heavy tool + that it costs tokens) so Webby surfaces
    what it already found and asks the user before spending tokens.
  - **always**: `read_url` escalates to the right heavy reader itself (Chromium for CHALLENGE_BLOCKED/403/empty,
    document for Office) — deterministic, no re-ask.
  - **never_heavy**: reports unreadable; Webby uses what search/`read_url` already returned.
- Escalation target derived from the backend error code (`CHALLENGE_BLOCKED`/`UPSTREAM_HTTP_ERROR`/`EXTRACTION_EMPTY`
  → rendered; `UNSUPPORTED_CONTENT_TYPE` + Office URL → document). `ROBOTS_DISALLOWED`/`FETCH_TIMEOUT`/`TOO_LARGE`
  never escalate (a heavy reader won't help).
- `backend.py`: added `unwrap_full()` / `error_code()` so handlers can branch on WHY a read failed.

### Build
- Manifest rebuilt (SDK 5.7.3): 35 → 38 tools (37 functions), +event `web_read_policy.changed`.

## [1.8.0] — 2026-06-25 — Web research (web_search + read_url) + envelope hardening

### Added
- **Web research tools** backed by the `web-tools-api` microservice (Exa search + SSRF-guarded reader):
  - `web_search` — find pages for a query; returns candidate cards (`url`/`title`/`snippet`/`score`) as a real
    SDL `EntityList[SearchResultItem]`. Does NOT read content — the LLM picks which url(s) to read next.
  - `read_url` — read ONE page into clean Markdown (`PageContent` entity: source, lang, token_count, metadata).
  - Two-layer design: the backend is a dumb fetcher, the LLM is the orchestrator. The resilience loop
    ("a page errored → read the next candidate") lives in the LLM — `read_url` returns a retryable error FACT
    on a dead page instead of raising, so one bad page never aborts the research.
  - New module `handlers_search.py`; SDL entities `SearchResultItem` / `SearchResultList` / `PageContent`.

### Changed (envelope hardening — old endpoints, 1:1 with the new backend error contract)
- New shared `backend.py`: `unwrap(resp, fallback)` / `error_message(body, fallback)` normalize the
  `{success, data|error}` envelope — handles HTTP 4xx/5xx with a typed envelope AND `error` arriving as
  either a string (legacy) or `{code, message}` (current backend), and never raises on HTTP status.
- Retrofitted all diagnostic handlers (`handlers.py`, `handlers_diag.py`, `handlers_quick.py`) off
  `resp.raise_for_status()` + ad-hoc `body.get("error")` onto `unwrap()` — a backend hiccup is now a clean
  `ActionResult.error` instead of an unhandled exception that crashes the chat turn.
- `handlers_scan.py` / `handlers_bulk.py`: failed sub-checks now carry the backend's error reason
  (via `error_message`) instead of a bare `unknown` with no explanation.

### Build
- Manifest rebuilt with `imperal build` (SDK 5.7.3): `sdk_version` 5.3.0 → 5.7.3; 33 → 35 tools.

## [1.7.0] — 2026-06-16 — SDK 5.3.0, Per Action pricing

### Changed
- SDK pin bumped: `5.2.1` → `5.3.0`
- Pricing model: Per Action via Developer Portal
  — `run_scan_tool` 8 tokens, `run_ip_scan` 6 tokens, `audit_domains` 15 tokens

## [1.6.0] — 2026-06-09 + post-release fixes 2026-06-14

### Bugfixes (2026-06-14, commits `69b402b`→`c365092`)

- **`handlers_bulk.py`** — `run_scan_tool` and `run_ip_scan` were collecting full per-target results but **not passing them to `build_scan_op`** (`results=` keyword missing). LLM received only aggregate counters (`scanned=N, issues=0`) with no per-IP / per-domain breakdown. Fixed: `results=results` added to both `build_scan_op` calls.
- **`handlers_diag.py`** — `geo_check` description claimed `check_type=full` runs "dns+ping+http+ssl+traceroute". The backend `geo/full` endpoint only runs dns+http+ssl (no ping, no traceroute). Description corrected to "dns+http+ssl from all 4 regions simultaneously".
- **`handlers_profiles.py`** — `_VALID_CHECKS` only included `{"dns","ssl","whois","http","email","blacklist","geo"}`. Backend supports 10 checks; `seo`, `ports`, `smtp` were silently rejected when creating or updating a profile. Fixed: all 10 check types now accepted.
- **`handlers_diag.py`** — `geo_check` LLM routing bug: "loading speed from region X" triggered `check_type=full` (slowest — dns+http+ssl) instead of `check_type=http`. Explicit routing rules added to description with natural-language triggers per check_type.
- **`handlers_bulk.py`** — `IpScanParams.domains` renamed to `ips` (semantic mismatch: field name implied domains, not IPs). Backward-compat `model_validator` keeps old `domains` key working.
- **`handlers_monitors.py`, `handlers_groups.py`, `handlers_profiles.py`** — `id_projection` missing on 6 update/delete handlers (`update_monitor`, `delete_monitor`, `update_domain_group`, `delete_domain_group`, `update_check_profile`, `delete_check_profile`). Added `id_projection="<id_field>"` on all 6.
- **`handlers_audit.py`** — `audit_domains` only checked `outcome.get("ok")`. Backend `audit_service.py` confirms `ok` is the correct field, but added resilient fallback: also accepts `outcome.get("success")` and data presence.
- **`handlers_quick.py`** — `quick_check` full preset issues count used a plain `not r.get("error")` check instead of `_check_status()`, underreporting real issues. Fixed to use `_check_status(name, r) in ("warning","critical")`.
- **Version sync** — `main.py` docstring and `imperal.json` showed `1.5.0` while `app.py` had `1.6.0`. All three synced to `1.6.0`.

## [1.6.0] — 2026-06-09

### Feature — bulk multi-domain audit `audit_domains` (plan P2)
- **`handlers_audit.py`** (new) — `audit_domains(domains, checks, include_raw=False)` audits up to **25 domains in ONE call**. It POSTs once to the backend aggregate endpoint `POST /v1/audit/batch` (server-side bounded-parallel) instead of doing N×M client HTTP calls, then reuses the existing `_check_status` + `_check_detail` machinery to build an `EntityList` (`DomainAuditPage`). `action_type="read"`. Sibling imports bound at module load (I-EXT-MODULE-ISOLATION).
- **`schemas_sdl.py`** — new `DomainAuditPage(sdl.EntityList[DomainAuditResult])`; **`schemas_sdl_builders.py`** — `build_domain_audit_page(per_domain)`.
- **`app.py`** — ChatExtension description now disambiguates `domain_full_check` (ONE domain) vs `audit_domains` (MANY domains, up to 25).
- **Backend `whm-web-tools-api` v1.0.0 → v1.1.0** (deployed + verified on api-server, additive — existing endpoints untouched):
  - `POST /v1/audit/batch` (P2) — targets × checks aggregator, loopback fan-out (httpx, semaphore=12), de-dups targets, caps at 25, filters unknown checks, normalized `{success, data:{results[target][check]={ok,data,error}}}`.
  - `GET /v1/audit/full/{domain}` (P4) — single-domain convenience wrapper (repeatable `?checks=`).
  - `GET /v1/stats/usage` (P5) — per-tool usage (count/errors/avg_ms/max_ms) aggregated read-only from the structured request log; no hot-path change, no new dependency. (Redis/SigNoz counter is the future-proof upgrade — open infra decision.)
  - `docs/openapi.yaml` regenerated from the live app (69 paths, v1.1.0).
  - **P4 rate-limit + SSRF guards were already implemented** (`SecurityMiddleware`: internal unlimited / external 10 req/min / 429; `is_safe_target` blocks private IPs) — nothing to add.
  - All 69 endpoints smoke-tested post-deploy: 68 pass; the one 400 (`/v1/dns/srv/<bare-domain>`) is correct SRV-format validation, not a regression.

### Feature — `domain_full_check` hardening (plan P1) + intent clarity (P3)
- **`handlers_diag.py` / `handlers_scan.py`** — `domain_full_check` now accepts three additional checks in `checks`: **`seo`** (meta/title issues via `/v1/seo/meta?url=`), **`ports`** (open-port scan), **`smtp`** (mail-server connectivity). `ports`/`smtp` endpoints already existed in `_run_domain_checks`; `seo` was added (query-param target, unlike the path-style endpoints). `_check_status` gained an `seo` branch (any reported issue → `warning`).
- **`handlers_diag.py`** — new `include_raw: bool = False` param. By default the **`data` payload** carries only a compact `{check: {status, summary}}` map (one-line summary per check, reusing the existing `_check_detail` builder) instead of the full ~10–15 KB raw blob — aligns with the performance guidance (don't return large payloads). The full audit table (`full_audit_ui`) is still always rendered from the complete results. Set `include_raw=true` only when the user explicitly wants raw data.
- **`handlers_diag.py`** — error path no longer leaks `str(exc)` to the user (docs: "never put raw exception strings in user-facing text"). The raw exception is logged via `logging.getLogger(__name__)` (same pattern as `handlers_schedule.py`); the user sees a stable `"Domain audit failed — please try again."` with `retryable=True`.
- **`handlers_ui.py`** — `_check_detail` gained `seo` / `smtp` one-line renderers (using only fields already referenced by `_check_status`). `ports` falls back to the generic truncated renderer (backend field shape not part of `docs.imperal.io` — left honest, not invented).
- **Description rewrite (P3)** — `domain_full_check` description now enumerates all optional checks and the `include_raw` behaviour, keeping the `Do NOT use run_scan/list_monitors/get_scan_results` routing guard.
- **`action_type` audit (P3)** — verified all 31 functions: diagnostics = `read`, monitor/group/profile create/update = `write`, all deletes = `destructive` (→ KAV confirmation per docs). No changes needed.
- Manifest is regenerated by `imperal build` / Dev Portal on deploy (docs: never hand-edit `imperal.json`).

## [1.5.1] — 2026-06-09

### Bugfix (critical) — `domain_full_check` cross-extension module collision
- **`handlers_diag.py`** — `domain_full_check` failed with `cannot import name 'WEB_TOOLS_URL' from 'app' (/opt/extensions/microsoft-ads/app.py)` (prod log 2026-06-08 13:43Z). Root cause: a **call-time lazy import** `from handlers_scan import _run_domain_checks` inside the handler. The kernel loader (`I-EXT-MODULE-ISOLATION`) rebinds bare sibling module names to an ext-unique namespace after load; re-importing a sibling at dispatch re-resolved bare `app` to whichever extension last owned it. Fix: **hoist the import to module load time** + wrap the handler body in try/except → `ActionResult.error(retryable=True)`. Individual checks were unaffected (they bind `WEB_TOOLS_URL` at load). NOT a packaging change — the kernel loads flat modules, not Python packages.

## [1.5.0] — 2026-06-03 (actualized)

### Routing fixes (critical)
- **`skeleton.py`** — aggregate health counts only (`total/critical/warning/ok/unknown`), NO monitor names. Previously monitor names like "Монитор DNS-записей" leaked into the classifier envelope causing `list_monitors` to fire on plain DNS queries.
- **`domain_full_check`** — now wired to `full_audit_ui` (was built but never called → empty table). Now uses `_run_domain_checks` for consistent `ok/warning/critical` status per check.
- **`propagation_type`** — `Literal[...] | None`, `None`-safe. Was crashing with `VALIDATION_MISSING_FIELD` when LLM passed `null`.
- **`ChatExtension` description** — split into two labelled sections: INSTANT DIAGNOSTICS vs RECURRING MONITORS. Previously LLM routed "check this domain" to monitors.
- **Function descriptions** — all geo/ssl/http/dns/network descriptions now clearly separate: `geo_check` = reachability from 4 regions; `ssl_check`/`http_check` = quality grade.
- **`handlers_bulk.py`** — `run_scan_tool` + `run_ip_scan` split from `handlers_quick.py` (300-line rule).
- **`.bak/` dirs** — removed from git tracking (37 files); added to `.gitignore`.
- **`@ext.on_install`** — added (fixes V12 validator warning).
- **`return_schema`** — populated via `imperal build` (all 31 tools now carry `x-sdl: "entity"` + `x-sdl-role` per field in manifest).
- **`sdk_version`** — `5.2.0` → `5.2.1` (PyPI published version used by `imperal build`).

## [1.5.0] — 2026-06-01

### SDL migration (SDK 5.2.0 — Structured Data Layer)
- **New `schemas_sdl.py`** — 18 SDL entity classes (`sdl.Entity` + facets). Domain checks compose `NetAsset`/`ServiceHealth`/`Certificated`/`RiskScored`; monitors compose `Schedulable`; lists use `sdl.EntityList[T]`. Custom fields use the `wt.*` namespace via `sdl.field(role=...)`.
- **New `schemas_sdl_builders.py`** — 18 builder functions converting raw API/store dicts → SDL entities. Handlers import entities + builders only from this module.
- **`data_model=` added to ALL 31 `@chat.function` handlers** (was: NONE — V23/V24 were unsatisfied across the whole extension). Each handler now declares its SDL return type and passes `data=build_*(...)` instead of a raw dict.
- **`imperal.json`** — `sdk_version` `5.0.0` → `5.2.0`. NOTE: per-tool `return_schema` in the manifest stays `{}` — it is generated by `imperal build` (needs py3.11 venv); the manifest is hand-maintained, so `data_model=` lives in code only for now.

### Fixed — LLM routing (root cause: skeleton leaked monitor names)
- **`skeleton.py`** — classifier envelope no longer emits monitor **names**. Previously it returned `{name: "Монитор DNS-записей группы доменов", ...}` per monitor; the LLM saw "DNS"/domain names in context and routed plain domain/DNS requests to `list_monitors` instead of `dns_lookup`/`domain_full_check`. Now returns aggregate health counts only (`total/critical/warning/ok/unknown`) + a summary line steering ad-hoc checks to `dns_lookup`/`domain_full_check`.
- **`propagation_type` crash** — `dns_lookup` raised `VALIDATION_MISSING_FIELD` when the LLM passed `propagation_type: null`. Type widened to `Literal[...] | None`, handler uses `params.propagation_type or "A"`.
- **`domain_full_check` had no result table** — `full_audit_ui` was imported but never called, and the handler returned raw API data without per-check status. Now uses `_run_domain_checks` (adds ok/warning/critical) and renders `full_audit_ui`.
- **`handlers_ui._check_detail`** — unwraps the `{status, data}` shape from `_run_domain_checks`; added `geo` and `whois` detail rows.

### Changed — description disambiguation (reduce LLM mis-routing)
- **`geo_check`** — reframed as geographic **reachability/speed** from EU/US/SG/MD (triggers: "loading speed from America/Asia", "скорость загрузки"), explicitly NOT certificate/header quality.
- **`ssl_check` / `http_check`** — marked as **quality** checks; cross-reference `geo_check` for per-region reachability.
- **`whois_lookup`** — clarified ownership data vs `network_check ip_lookup` (geolocation).
- **`network_check`** — `ip_lookup`/`reverse_dns`/`asn` are IP-only (with example); `ping`/`traceroute` work on domains.
- **`dns_lookup`** — `record_type='all'` for "all records/все записи"; `propagation` + `propagation_type='NS'` for "did my NS update propagate?"; states it needs no monitors.
- **`domain_full_check`** — positioned as the INSTANT one-shot master audit (no monitors); explicitly "do NOT call dns/ssl/http individually after".
- **`run_scan` / `get_scan_results` / `list_monitors`** — scoped to existing monitors only; explicitly NOT for ad-hoc domain checks; note that monitor NAMES are irrelevant to routing.
- **`ChatExtension` description** — rewritten into two labelled sections: INSTANT DIAGNOSTICS vs RECURRING MONITORS.

### SDK Compliance
- **`app.py`** — removed `system_prompt=_SYSTEM_PROMPT` kwarg + the `system_prompt.txt` file read (no-op in SDK 5.0.0, LLM router removed).
- **`app.py`** — removed the `ext._panels["secrets"]["slot"]` hack (dead since SDK 5.0.1; the authoritative `@ext.panel("secrets", slot="overlay")` in `panels.py` remains).

### Refactor
- **`handlers_bulk.py`** (new) — `run_scan_tool` + `run_ip_scan` extracted from `handlers_quick.py` (was 298L, near the 300-line limit). `main.py` updated: new module in `sys.modules` purge list + import.

### Notes / legacy
- **`system_prompt.txt`** is now orphaned (no code reads it). Kept on disk pending decision — safe to delete.
- Version bumped `1.4.4` → `1.5.0` (`app.py`, `imperal.json`, `main.py` docstring).

---

## [1.4.3] — 2026-05-17

### Fixed
- **`panels.py`** — Added `@ext.panel("secrets", slot="overlay")` explicitly. The previous fix in `app.py` (set `ext._panels["secrets"]["slot"]`) was a no-op: `_panels` is empty at `Extension.__init__` time, `@ext.panel()` decorators run later. Explicit registration is the authoritative fix — Kernel reads `ext.panels` after all decorators and sees `secrets → overlay`.
- **`panels_ui_items.py:6`** — `_REGION_DISPLAY` and `PROFILE_CHECK_OPTS` were used but not imported from `panels_ui_base`. `_REGION_DISPLAY` caused a live `NameError` whenever a user expanded a geo-check row in the Scan Tool results panel.

### Changed
- **`imperal.json`** — version corrected to `1.4.3` (was stuck at `1.4.1` since patch2 → manifest was never re-synced with code version).

---

## [1.4.2] — 2026-05-17

### Fixed
- **`app.py`** — SDK 5.0.0 автоматически регистрирует панель "secrets" на `slot="right"`, из-за чего правая колонка показывала секреты вместо мониторов. Добавлен тот же обходной путь что в mail-client: `ext._panels["secrets"]["slot"] = "overlay"` в try/except — secrets скрывается, правый слот достаётся "overview".

---

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
