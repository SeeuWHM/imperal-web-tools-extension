"""web-tools · Scan runner, results, quick check."""
from __future__ import annotations

import asyncio
import datetime

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult


# ─── Helpers ──────────────────────────────────────────────────────────────── #

def _check_status(check: str, data: dict) -> str:
    """Derive ok/warning/critical/unknown from raw check result data."""
    if not data or data.get("error"):
        return "unknown"  # API/network error ≠ domain problem
    # ssl/http include "error": null on success — use .get(), not "in"
    if check == "blacklist":
        verdict = data.get("verdict", "clean")
        if not data.get("resolved_ip") and verdict == "clean":
            return "unknown"  # domain didn't resolve — blacklist result meaningless
        return "critical" if verdict == "critical" else ("warning" if verdict == "listed" else "ok")
    if check == "ssl":
        if not data.get("valid", True):
            return "critical"
        days = data.get("days_until_expiry") or data.get("days_remaining", 99)
        return "warning" if days < 14 else "ok"
    if check in ("http", "email"):
        grade = data.get("grade", "A")
        return "critical" if grade == "F" else ("warning" if grade in ("C", "D") else "ok")
    if check == "geo":
        regions = data.get("http", {}).get("regions", {})
        if not regions:
            regions = data.get("dns", {}).get("regions", {})
        total = len(regions)
        if total > 0:
            ok = sum(1 for r in regions.values()
                     if isinstance(r, dict) and not r.get("error") and r.get("ok", False))
            if ok / total < 0.6:
                return "warning"
        return "ok"
    if check == "smtp":
        return "ok" if data.get("reachable") else "warning"
    if check == "propagation":
        return "ok" if data.get("fully_propagated", True) else "warning"
    return "ok"


async def _run_domain_checks(ctx, domain: str, checks: list[str]) -> dict:
    """Run all profile checks for one domain in parallel (Semaphore(5))."""
    sem = asyncio.Semaphore(5)
    base = WEB_TOOLS_URL
    urls = {
        "dns":       f"{base}/v1/dns/all/{domain}",
        "ssl":       f"{base}/v1/ssl/{domain}",
        "whois":     f"{base}/v1/whois/{domain}/quick",
        "http":      f"{base}/v1/http/headers/{domain}/grade",
        "email":     f"{base}/v1/email/full/{domain}",
        "blacklist": f"{base}/v1/blacklist/domain/{domain}",
        "geo":         f"{base}/v1/geo/full/{domain}",
        "ports":       f"{base}/v1/ports/scan/{domain}",
        "smtp":        f"{base}/v1/smtp/test/{domain}",
        "propagation": f"{base}/v1/dns/propagation/{domain}",
    }

    async def _one(check: str) -> tuple[str, dict]:
        async with sem:
            try:
                resp = await ctx.http.get(urls[check])
                body = resp.json()
                d = body.get("data") if body.get("success") else None
                return check, {"status": _check_status(check, d or {}), "data": d}
            except Exception as exc:
                return check, {"status": "unknown", "error": str(exc)}

    return dict(await asyncio.gather(*[_one(c) for c in checks]))


# ─── Scan Runner ──────────────────────────────────────────────────────────── #

class RunScanParams(BaseModel):
    monitor_id: str = Field(description="Monitor ID to run scan for now")


@chat.function("run_scan", action_type="write", event="scan.completed",
               description="Trigger an immediate scan for a monitor — checks all domains in the group with the profile checks in parallel, stores a snapshot")
async def fn_run_scan(ctx, params: RunScanParams) -> ActionResult:
    try:
        return await _do_run_scan(ctx, params)
    except Exception as exc:
        return ActionResult.error(f"Scan failed: {exc}", retryable=True)


async def _do_run_scan(ctx, params: RunScanParams) -> ActionResult:
    mon = await ctx.store.get("wt_monitors", params.monitor_id)
    if not mon or mon.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Monitor not found.", retryable=False)

    grp = await ctx.store.get("wt_groups", mon.data["group_id"])
    prf = await ctx.store.get("wt_profiles", mon.data["profile_id"])
    if not grp or not prf:
        return ActionResult.error("Domain group or check profile was deleted.", retryable=False)

    domains: list[str] = grp.data["domains"]
    checks:  list[str] = prf.data["checks"]
    now = datetime.datetime.utcnow().isoformat()

    dom_sem = asyncio.Semaphore(3)

    async def _domain(d: str) -> tuple[str, dict]:
        async with dom_sem:
            return d, await _run_domain_checks(ctx, d, checks)

    domain_results = dict(await asyncio.gather(*[_domain(d) for d in domains]))

    # Check-level counts (for pie chart)
    all_statuses = [r["status"] for dr in domain_results.values() for r in dr.values()]
    counts: dict[str, int] = {"ok": 0, "warning": 0, "critical": 0, "unknown": 0}
    for s in all_statuses:
        counts[s] = counts.get(s, 0) + 1

    # Domain-level counts (for "N/20 OK" display) — same logic as domain_items in UI
    dom_lvl: list[str] = []
    for dr in domain_results.values():
        d_st = [r["status"] for r in dr.values()]
        d_has_unk = "unknown" in d_st
        dom_lvl.append(
            "critical" if "critical" in d_st else
            "warning"  if "warning"  in d_st else
            "ok"       if "ok" in d_st and not d_has_unk else
            "unknown"
        )
    dom_counts = {s: dom_lvl.count(s) for s in ("ok", "warning", "critical", "unknown")}

    overall = ("critical" if dom_counts["critical"] else
               "warning"  if dom_counts["warning"]  else
               "ok"       if dom_counts["ok"]        else "unknown")

    old_snap_id = mon.data.get("last_snapshot_id")
    snap = await ctx.store.create("wt_snapshots", {
        "owner_id":   ctx.user.id,
        "monitor_id": params.monitor_id,
        "status":     overall,
        "domains":    domain_results,
        "checks_run": checks,
        "summary": {
            "total_domains":   len(domains),
            "domains_ok":      dom_counts["ok"],
            "domains_warning": dom_counts["warning"],
            "domains_critical":dom_counts["critical"],
            "domains_unknown": dom_counts["unknown"],
        },
        "created_at": now,
    })
    await ctx.store.update("wt_monitors", params.monitor_id, {
        "last_run_at":      now,
        "last_snapshot_id": snap.id,
    })
    if old_snap_id:
        try:
            await ctx.store.delete("wt_snapshots", old_snap_id)
        except Exception:
            pass

    issues = counts["warning"] + counts["critical"]
    return ActionResult.success(
        data={"snapshot_id": snap.id, "monitor_id": params.monitor_id,
              "status": overall, "summary": counts, "domains_checked": len(domains)},
        summary=f"Scan complete: {overall.upper()} — {len(domains)} domain(s), {issues} issue(s)",
        refresh_panels=["__panel__sidebar", "__panel__overview", "__panel__detail"],
    )


# ─── Scan Results ─────────────────────────────────────────────────────────── #

class GetScanResultsParams(BaseModel):
    monitor_id: str = Field(description="Monitor ID to retrieve last scan results for")


@chat.function("get_scan_results", action_type="read",
               description="Get the last scan snapshot for a monitor — per-domain per-check status, overall verdict and summary counts")
async def fn_get_scan_results(ctx, params: GetScanResultsParams) -> ActionResult:
    mon = await ctx.store.get("wt_monitors", params.monitor_id)
    if not mon or mon.data.get("owner_id") != ctx.user.id:
        return ActionResult.error("Monitor not found.", retryable=False)

    snap_id = mon.data.get("last_snapshot_id")
    if not snap_id:
        return ActionResult.error("No scan results yet — run a scan first.", retryable=False)

    snap = await ctx.store.get("wt_snapshots", snap_id)
    if not snap:
        return ActionResult.error("Snapshot not found.", retryable=False)

    return ActionResult.success(
        data={
            "monitor_id":  params.monitor_id,
            "snapshot_id": snap.id,
            "status":      snap.data["status"],
            "domains":     snap.data["domains"],
            "checks_run":  snap.data["checks_run"],
            "summary":     snap.data["summary"],
            "scanned_at":  snap.data["created_at"],
        },
        summary=f"Last scan: {snap.data['status'].upper()} on {snap.data['created_at'][:10]}",
    )

