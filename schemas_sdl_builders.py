"""web-tools — SDL builder helpers (imperal-sdk 5.2.0).

Each function converts raw API data or store document dicts into the
corresponding SDL entity for ActionResult.data.

Handlers import ONLY from this module — it re-exports SDL entity classes too.
"""
from __future__ import annotations

from schemas_sdl import (
    DomainCheckResult, SslResult, EmailAuthResult, BlacklistResult,
    PortScanResult, SmtpResult, GeoCheckResult, DomainAuditResult, DomainAuditPage,
    ScanOpResult, PanelDataResult, MonitorScanResult,
    MonitorEntity, MonitorPage,
    DomainGroupEntity, DomainGroupPage,
    CheckProfileEntity, CheckProfilePage,
    WtOpResult,
    SearchResultItem, SearchResultList, PageContent,
)

__all__ = [
    "DomainCheckResult", "SslResult", "EmailAuthResult", "BlacklistResult",
    "PortScanResult", "SmtpResult", "GeoCheckResult", "DomainAuditResult", "DomainAuditPage",
    "ScanOpResult", "PanelDataResult", "MonitorScanResult",
    "MonitorEntity", "MonitorPage",
    "DomainGroupEntity", "DomainGroupPage",
    "CheckProfileEntity", "CheckProfilePage",
    "WtOpResult",
    "build_domain_check", "build_ssl", "build_email_auth", "build_blacklist",
    "build_port_scan", "build_smtp", "build_geo", "build_domain_audit",
    "build_domain_audit_page",
    "build_scan_op", "build_panel_data", "build_monitor_scan",
    "build_monitor", "build_monitor_page",
    "build_domain_group", "build_domain_group_page",
    "build_check_profile", "build_check_profile_page",
    "build_wt_op",
    "SearchResultItem", "SearchResultList", "PageContent",
    "build_search_result", "build_search_result_list", "build_page_content",
]


def build_domain_check(target: str, check_type: str, raw_data) -> DomainCheckResult:
    return DomainCheckResult(
        id=target,
        title=f"{check_type.upper()} for {target}",
        kind="domain_check",
        domain=target,
        check_type=check_type,
        raw_data=raw_data if isinstance(raw_data, dict) else None,
    )


def build_ssl(domain: str, port: int, raw_data) -> SslResult:
    d = raw_data if isinstance(raw_data, dict) else {}
    grade = d.get("grade")
    days = d.get("days_until_expiry") or d.get("days_remaining")
    valid = d.get("valid", True)
    return SslResult(
        id=domain,
        title=f"SSL for {domain}",
        kind="ssl_result",
        domain=domain,
        port=port,
        grade=grade,
        days_remaining=days,
        cert_is_valid=valid,
        status="ok" if valid else "warning",
        raw_data=d or None,
    )


def build_email_auth(domain: str, check_type: str, raw_data) -> EmailAuthResult:
    return EmailAuthResult(
        id=domain,
        title=f"Email {check_type} for {domain}",
        kind="email_auth_result",
        domain=domain,
        check_type=check_type,
        raw_data=raw_data if isinstance(raw_data, dict) else None,
    )


def build_blacklist(target: str, target_type: str, raw_data) -> BlacklistResult:
    d = raw_data if isinstance(raw_data, dict) else {}
    verdict = d.get("verdict", "clean")
    risk_level = "high" if verdict == "critical" else "medium" if verdict == "listed" else "low"
    return BlacklistResult(
        id=target,
        title=f"Blacklist: {target}",
        kind="blacklist_result",
        domain=target if target_type == "domain" else None,
        ip=target if target_type == "ip" else None,
        target_type=target_type,
        verdict=verdict,
        risk_level=risk_level,
        raw_data=d or None,
    )


def build_port_scan(host: str, raw_data) -> PortScanResult:
    return PortScanResult(
        id=host,
        title=f"Port scan: {host}",
        kind="port_scan_result",
        domain=host,
        raw_data=raw_data if isinstance(raw_data, dict) else None,
    )


def build_smtp(target: str, raw_data) -> SmtpResult:
    d = raw_data if isinstance(raw_data, dict) else {}
    reachable = d.get("reachable", True)
    return SmtpResult(
        id=target,
        title=f"SMTP: {target}",
        kind="smtp_result",
        domain=target,
        health="ok" if reachable else "degraded",
        raw_data=d or None,
    )


def build_geo(target: str, check_type: str, raw_data) -> GeoCheckResult:
    return GeoCheckResult(
        id=target,
        title=f"Geo {check_type}: {target}",
        kind="geo_result",
        domain=target,
        check_type=check_type,
        regions=raw_data if isinstance(raw_data, dict) else None,
    )


def build_domain_audit(domain: str, results: dict) -> DomainAuditResult:
    return DomainAuditResult(
        id=domain,
        title=f"Full audit: {domain}",
        kind="domain_audit",
        domain=domain,
        check_results=results,
    )


def build_domain_audit_page(per_domain: list[tuple[str, dict]]) -> DomainAuditPage:
    """Wrap a list of (domain, check_results) into a DomainAuditPage EntityList."""
    items = [build_domain_audit(domain, results) for domain, results in per_domain]
    return DomainAuditPage(items=items, total=len(items))


def build_scan_op(target: str, preset: str, scanned: int,
                  issues: int, checks: list, results=None) -> ScanOpResult:
    return ScanOpResult(
        id=target or "scan",
        title=f"Scan: {scanned} domain(s), {issues} issue(s)",
        kind="scan_op",
        scanned=scanned,
        issues=issues,
        checks=checks or None,
        preset=preset or None,
        results=results if isinstance(results, dict) else None,
    )


def build_panel_data(monitors: int, domain_groups: int, profiles: int,
                     critical: int, warning: int, ok: int) -> PanelDataResult:
    return PanelDataResult(
        id="panel_data",
        title="Web Tools",
        kind="panel_data",
        status="critical" if critical else "warning" if warning else "ok",
        monitor_count=monitors,
        group_count=domain_groups,
        profile_count=profiles,
        critical_count=critical,
        warning_count=warning,
        ok_count=ok,
    )


def build_monitor_scan(snap_id: str, monitor_id: str, status: str,
                       summary: dict | None, domains_checked: int,
                       domains: dict | None = None,
                       checks_run: list | None = None) -> MonitorScanResult:
    return MonitorScanResult(
        id=snap_id,
        title=f"Scan: {status.upper()}",
        kind="monitor_scan",
        status=status,
        monitor_id=monitor_id,
        snapshot_id=snap_id,
        domains_checked=domains_checked,
        summary=summary,
        domains=domains,
        checks_run=checks_run or None,
    )


def build_monitor(monitor_id: str, name: str, group_id: str = "",
                  profile_id: str = "", interval_hours: int = 24,
                  enabled: bool = True, last_run_at: str | None = None,
                  snapshot_id: str | None = None, health: str | None = None,
                  domains_count: int | None = None,
                  checks: list | None = None) -> MonitorEntity:
    return MonitorEntity(
        id=monitor_id,
        title=name,
        kind="monitor",
        monitor_id=monitor_id,
        group_id=group_id or None,
        profile_id=profile_id or None,
        interval_hours=interval_hours,
        enabled=enabled,
        last_run_at=last_run_at,
        snapshot_id=snapshot_id,
        health=health,
        domains_count=domains_count,
        checks=checks or None,
    )


def build_monitor_page(monitors: list[dict]) -> MonitorPage:
    items = [
        build_monitor(
            monitor_id=m["monitor_id"],
            name=m["name"],
            group_id=m.get("group_id", ""),
            profile_id=m.get("profile_id", ""),
            interval_hours=m.get("interval_hours", 24),
            enabled=m.get("enabled", True),
            last_run_at=m.get("last_run_at"),
            snapshot_id=m.get("last_snapshot_id"),
        )
        for m in monitors
    ]
    return MonitorPage(items=items, total=len(items))


def build_domain_group(group_id: str, name: str, domains: list[str]) -> DomainGroupEntity:
    return DomainGroupEntity(
        id=group_id,
        title=name,
        kind="domain_group",
        group_id=group_id,
        domains=domains or None,
        domain_count=len(domains) if domains else 0,
    )


def build_domain_group_page(groups: list[dict]) -> DomainGroupPage:
    items = [
        build_domain_group(g["group_id"], g["name"], g.get("domains", []))
        for g in groups
    ]
    return DomainGroupPage(items=items, total=len(items))


def build_check_profile(profile_id: str, name: str, checks: list[str]) -> CheckProfileEntity:
    return CheckProfileEntity(
        id=profile_id,
        title=name,
        kind="check_profile",
        profile_id=profile_id,
        checks=checks or None,
    )


def build_check_profile_page(profiles: list[dict]) -> CheckProfilePage:
    items = [
        build_check_profile(p["profile_id"], p["name"], p.get("checks", []))
        for p in profiles
    ]
    return CheckProfilePage(items=items, total=len(items))


def build_wt_op(entity_id: str, title: str, monitors_removed: int = 0) -> WtOpResult:
    return WtOpResult(
        id=entity_id,
        title=title,
        kind="wt_op",
        monitors_removed=monitors_removed or None,
    )


# ── Web research ───────────────────────────────────────────────────────────────

def build_search_result(r: dict) -> SearchResultItem:
    url = r.get("url") or ""
    return SearchResultItem(
        id=url,
        title=(r.get("title") or url or "result")[:300],
        kind="search_result",
        url=url or None,
        snippet=r.get("snippet"),
        published_date=r.get("published_date"),
        author=r.get("author"),
        score=r.get("score"),
        engine=r.get("engine") or "exa",
    )


def build_search_result_list(data: dict) -> SearchResultList:
    """Wrap backend SearchData into a SearchResultList EntityList."""
    raw = data.get("results") or []
    items = [build_search_result(r) for r in raw if isinstance(r, dict) and r.get("url")]
    return SearchResultList(items=items, total=data.get("count", len(items)))


def build_page_content(d: dict) -> PageContent:
    """Wrap backend ReadData into a PageContent entity."""
    url = d.get("url") or ""
    final_url = d.get("final_url") or url
    meta = d.get("metadata")
    outline = d.get("outline")
    tables = d.get("tables")
    return PageContent(
        id=final_url or url or "page",
        title=(d.get("title") or final_url or url or "page")[:300],
        kind="page_content",
        url=url or None,
        final_url=final_url or None,
        content=d.get("content") or "",
        source=d.get("source"),
        content_type=d.get("content_type"),
        lang=d.get("lang"),
        token_count=d.get("token_count") or 0,
        word_count=d.get("word_count"),
        truncated=bool(d.get("truncated", False)),
        content_hash=d.get("content_hash"),
        outline=outline if isinstance(outline, list) and outline else None,
        tables=tables if isinstance(tables, list) and tables else None,
        page_metadata=meta if isinstance(meta, dict) and meta else None,
    )
