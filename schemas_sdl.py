"""web-tools — SDL entity classes (imperal-sdk 5.2.0).

Namespace: wt.* — not a reserved SDL namespace, safe for custom roles.
"""
from __future__ import annotations

from pydantic import Field
from imperal_sdk import sdl
from imperal_sdk.sdl import field as sdl_field


# ── Domain diagnostic results ─────────────────────────────────────────────────

class DomainCheckResult(sdl.Entity, sdl.NetAsset, sdl.ServiceHealth):
    """Generic domain diagnostic — DNS, WHOIS, HTTP, SEO, Network."""

    kind: str = "domain_check"
    check_type: str | None = sdl_field(role="wt.check_type")
    raw_data: dict | None = sdl_field(role="wt.raw_data")


class SslResult(sdl.Entity, sdl.NetAsset, sdl.Certificated, sdl.ServiceHealth):
    """SSL/TLS certificate check result."""

    kind: str = "ssl_result"
    grade: str | None = sdl_field(role="wt.grade")
    days_remaining: int | None = sdl_field(role="wt.days_remaining")
    raw_data: dict | None = sdl_field(role="wt.raw_data")


class EmailAuthResult(sdl.Entity, sdl.NetAsset):
    """Email authentication check — SPF, DMARC, DKIM, BIMI, full grade."""

    kind: str = "email_auth_result"
    check_type: str | None = sdl_field(role="wt.check_type")
    raw_data: dict | None = sdl_field(role="wt.raw_data")


class BlacklistResult(sdl.Entity, sdl.NetAsset, sdl.RiskScored):
    """Spam blacklist check — DNSBL/SURBL verdict."""

    kind: str = "blacklist_result"
    target_type: str | None = sdl_field(role="wt.target_type")
    verdict: str | None = sdl_field(role="wt.verdict")
    raw_data: dict | None = sdl_field(role="wt.raw_data")


class PortScanResult(sdl.Entity, sdl.NetAsset):
    """TCP port scan result."""

    kind: str = "port_scan_result"
    raw_data: dict | None = sdl_field(role="wt.raw_data")


class SmtpResult(sdl.Entity, sdl.NetAsset, sdl.ServiceHealth):
    """SMTP server connectivity test result."""

    kind: str = "smtp_result"
    raw_data: dict | None = sdl_field(role="wt.raw_data")


class GeoCheckResult(sdl.Entity, sdl.NetAsset):
    """Multi-region geo probe result (EU/US/SG/MD)."""

    kind: str = "geo_result"
    check_type: str | None = sdl_field(role="wt.check_type")
    regions: dict | None = sdl_field(role="wt.regions")


class DomainAuditResult(sdl.Entity, sdl.NetAsset):
    """Full parallel domain audit — all check results combined."""

    kind: str = "domain_audit"
    check_results: dict | None = sdl_field(role="wt.check_results")


# ── Scan operation results ─────────────────────────────────────────────────────

class ScanOpResult(sdl.Entity, sdl.Timestamped):
    """Bulk / quick scan operation result."""

    kind: str = "scan_op"
    scanned: int | None = sdl_field(role="wt.scanned")
    issues: int | None = sdl_field(role="wt.issues")
    checks: list[str] | None = sdl_field(role="wt.checks")
    preset: str | None = sdl_field(role="wt.preset")
    results: dict | None = sdl_field(role="wt.results")


class PanelDataResult(sdl.Entity):
    """Panel summary — monitor/group/profile counts and health totals."""

    kind: str = "panel_data"
    monitor_count: int | None = sdl_field(role="wt.monitor_count")
    group_count: int | None = sdl_field(role="wt.group_count")
    profile_count: int | None = sdl_field(role="wt.profile_count")
    critical_count: int | None = sdl_field(role="wt.critical_count")
    warning_count: int | None = sdl_field(role="wt.warning_count")
    ok_count: int | None = sdl_field(role="wt.ok_count")


class MonitorScanResult(sdl.Entity, sdl.Timestamped):
    """Domain monitor scan snapshot result."""

    kind: str = "monitor_scan"
    monitor_id: str | None = sdl_field(role="wt.monitor_id")
    snapshot_id: str | None = sdl_field(role="wt.snapshot_id")
    domains_checked: int | None = sdl_field(role="wt.domains_checked")
    summary: dict | None = sdl_field(role="wt.summary")
    domains: dict | None = sdl_field(role="wt.domains")
    checks_run: list[str] | None = sdl_field(role="wt.checks")


# ── Monitor / group / profile entities ───────────────────────────────────────

class MonitorEntity(sdl.Entity, sdl.Schedulable, sdl.ServiceHealth):
    """Domain health monitor — recurring scan configuration."""

    kind: str = "monitor"
    monitor_id: str | None = sdl_field(role="wt.monitor_id")
    group_id: str | None = sdl_field(role="wt.group_id")
    profile_id: str | None = sdl_field(role="wt.profile_id")
    interval_hours: int | None = sdl_field(role="wt.interval_hours")
    enabled: bool | None = sdl_field(role="wt.enabled")
    last_run_at: str | None = sdl_field(role="wt.last_run_at")
    snapshot_id: str | None = sdl_field(role="wt.snapshot_id")
    domains_count: int | None = sdl_field(role="wt.domains_count")
    checks: list[str] | None = sdl_field(role="wt.checks")


class MonitorPage(sdl.EntityList[MonitorEntity]):
    """Paginated monitor list — returned by list_monitors()."""

    pass


class DomainGroupEntity(sdl.Entity):
    """Named group of domains for monitoring."""

    kind: str = "domain_group"
    group_id: str | None = sdl_field(role="wt.group_id")
    domains: list[str] | None = sdl_field(role="wt.domains")
    domain_count: int | None = sdl_field(role="wt.domain_count")


class DomainGroupPage(sdl.EntityList[DomainGroupEntity]):
    """Paginated domain group list — returned by list_domain_groups()."""

    pass


class CheckProfileEntity(sdl.Entity):
    """Check profile — defines which checks run per domain in a monitor."""

    kind: str = "check_profile"
    profile_id: str | None = sdl_field(role="wt.profile_id")
    checks: list[str] | None = sdl_field(role="wt.checks")


class CheckProfilePage(sdl.EntityList[CheckProfileEntity]):
    """Paginated check profile list — returned by list_check_profiles()."""

    pass


class WtOpResult(sdl.Entity):
    """Generic CRUD confirmation — create/update/delete operations."""

    kind: str = "wt_op"
    monitors_removed: int | None = sdl_field(role="wt.monitors_removed")
