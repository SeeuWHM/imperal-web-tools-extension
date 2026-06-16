"""web-tools · Bulk multi-domain audit — audit_domains (SDK 5.2.0 / SDL).

One-call audit of up to 25 domains. Delegates the fan-out to the backend
aggregate endpoint POST /v1/audit/batch (server-side bounded-parallel), then
reuses the existing status/summary machinery to build an EntityList.

Sibling imports are bound at MODULE LOAD time (kernel I-EXT-MODULE-ISOLATION:
a call-time `from handlers_scan import ...` would re-resolve bare `app` to the
wrong extension — see handlers_diag.py header).
"""
from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from handlers_scan import _check_status
from handlers_ui import _check_detail
from schemas_sdl_builders import DomainAuditPage, build_domain_audit_page

log = logging.getLogger(__name__)

MAX_DOMAINS = 25


class AuditDomainsParams(BaseModel):
    """Bulk multi-domain audit parameters."""
    domains: list[str] = Field(
        ...,
        description="Domains to audit in one call (1..25). Duplicates are removed.",
    )
    checks: list[Literal["dns", "ssl", "whois", "http", "email", "blacklist", "geo", "seo", "ports", "smtp"]] = Field(
        default=["dns", "ssl", "http", "email", "blacklist"],
        description="Checks to run per domain. Defaults to dns+ssl+http+email+blacklist. Add 'geo' for multi-region reachability (slowest), 'whois'/'seo'/'ports'/'smtp' as needed.",
    )
    include_raw: bool = Field(
        False,
        description="When false (default) each domain carries a compact per-check status + one-line summary. Set true to also include full raw check data (large).",
    )


@chat.function("audit_domains", action_type="read",
               data_model=DomainAuditPage,
               description="INSTANT bulk audit of MULTIPLE domains (up to 25) in ONE call — no monitors or setup required. Use when the user gives a LIST of domains to check/compare at once ('check these domains', 'audit all of these', 'compare these sites'). Runs the selected checks on every domain in parallel server-side and returns one result per domain. Default checks: dns + ssl + http + email + blacklist; add 'geo'/'whois'/'seo'/'ports'/'smtp'. For a SINGLE domain use domain_full_check instead. Do NOT use run_scan/list_monitors/get_scan_results — those are recurring-monitor tools.")
async def fn_audit_domains(ctx, params: AuditDomainsParams) -> ActionResult:
    """INSTANT bulk audit of multiple domains (up to 25) in one call."""
    domains = list(dict.fromkeys(
        d.strip() for d in (params.domains or []) if d and d.strip()
    ))[:MAX_DOMAINS]
    if not domains:
        return ActionResult.error("Provide at least one domain to audit.", retryable=False)

    checks = list(params.checks) or ["dns", "ssl", "http", "email", "blacklist"]

    try:
        resp = await ctx.http.post(
            f"{WEB_TOOLS_URL}/v1/audit/batch",
            json={"targets": domains, "checks": checks},
            timeout=150,
        )
        body = resp.json()
    except Exception as exc:
        log.error("audit_domains batch call failed: %s", exc)
        return ActionResult.error("Bulk audit failed — please try again.", retryable=True)

    if not isinstance(body, dict) or not body.get("success"):
        return ActionResult.error("Bulk audit failed — the diagnostics service returned an error.", retryable=True)

    data = body.get("data", {})
    results_map: dict = data.get("results", {}) or {}
    ordered = data.get("targets", domains)

    per_domain: list[tuple[str, dict]] = []
    issues = 0
    for domain in ordered:
        checks_out = results_map.get(domain, {}) or {}
        norm: dict = {}
        for check, outcome in checks_out.items():
            raw = outcome.get("data") if isinstance(outcome, dict) else None
            # Accept both "ok" and "success" as the per-check success flag from the backend.
            # Fall back to inferring success from data presence when neither flag exists.
            ok = bool(
                outcome.get("ok") or outcome.get("success") or (raw is not None)
            ) if isinstance(outcome, dict) else False
            status = _check_status(check, raw or {}) if ok else "unknown"
            if status in ("warning", "critical"):
                issues += 1
            wrapped = {"status": status, "data": raw,
                       "error": outcome.get("error") if isinstance(outcome, dict) else None}
            if params.include_raw:
                norm[check] = wrapped
            else:
                norm[check] = {"status": status, "summary": _check_detail(check, wrapped)}
        per_domain.append((domain, norm))

    await ctx.billing.track_usage("domain_audited", quantity=len(per_domain))
    return ActionResult.success(
        data=build_domain_audit_page(per_domain),
        summary=f"Audited {len(per_domain)} domain(s) × {len(checks)} check(s) — {issues} issue(s) found",
    )
