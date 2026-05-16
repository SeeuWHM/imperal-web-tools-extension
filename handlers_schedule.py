"""web-tools · Scheduled monitor runner — hourly cron, runs overdue monitors.

Architecture: @ext.schedule runs under __system__ context. Uses ctx.store.list_users()
to iterate all users who have monitors, then ctx.as_user(uid) + ctx.store.query()
for per-user scoped operations (SDK 5.0.0 canonical fan-out pattern).
"""
from __future__ import annotations

import asyncio
import datetime
import logging

from app import ext

from handlers_scan import _run_domain_checks

log = logging.getLogger(__name__)

# ─── Schedule ─────────────────────────────────────────────────────────────── #

@ext.schedule("wt_monitor_runner", cron="0 * * * *")
async def run_scheduled_monitors(ctx) -> None:
    """Hourly: fan-out across all users, scan overdue monitors."""
    now = datetime.datetime.now(datetime.timezone.utc)
    run_count = 0

    try:
        async for user_id in ctx.store.list_users("wt_monitors"):
            user_ctx = ctx.as_user(user_id)
            page = await user_ctx.store.query("wt_monitors", limit=100)
            for mon in page.data:
                if not mon.data.get("enabled"):
                    continue
                try:
                    ran = await _maybe_run(user_ctx, mon, now)
                    if ran:
                        run_count += 1
                except Exception as exc:
                    log.warning(
                        f"wt_schedule: monitor {mon.id} "
                        f"({mon.data.get('name')}) failed: {exc}"
                    )
    except Exception as exc:
        log.error(f"wt_schedule: failed: {exc}")
        return

    if run_count:
        log.info(f"wt_schedule: ran {run_count} monitor(s)")


# ─── Internal helpers ─────────────────────────────────────────────────────── #

async def _maybe_run(ctx, mon, now: datetime.datetime) -> bool:
    """Run scan if monitor is overdue. ctx is already scoped to the monitor owner."""
    # Re-read from store — avoids the stale-data race where a manual scan ran
    # after run_scheduled_monitors queried all monitors at startup, causing a
    # duplicate scan because the in-memory last_run_at hadn't been updated yet.
    fresh = await ctx.store.get("wt_monitors", mon.id)
    if not fresh or not fresh.data.get("enabled"):
        return False

    last_run   = fresh.data.get("last_run_at")
    interval_h = fresh.data.get("interval_hours", 24)

    if last_run:
        try:
            last_run_dt = datetime.datetime.fromisoformat(last_run)
            if last_run_dt.tzinfo is None:
                last_run_dt = last_run_dt.replace(tzinfo=datetime.timezone.utc)
            elapsed_h = (now - last_run_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            elapsed_h = interval_h + 1
        if elapsed_h < interval_h:
            return False

    group_id   = fresh.data.get("group_id", "")
    profile_id = fresh.data.get("profile_id", "")
    if not group_id or not profile_id:
        log.warning(f"wt_schedule: monitor {mon.id} missing group_id or profile_id")
        return False

    grp = await ctx.store.get("wt_groups",   group_id)
    prf = await ctx.store.get("wt_profiles", profile_id)
    if not grp or not prf:
        log.debug(f"wt_schedule: monitor {mon.id} skipped — group/profile deleted")
        return False

    domains    = grp.data.get("domains", [])
    checks     = prf.data.get("checks",  [])
    old_snap_id = fresh.data.get("last_snapshot_id")
    run_at     = now.isoformat()
    owner_id   = fresh.data.get("owner_id", "")

    if not domains or not checks:
        log.debug(f"wt_schedule: monitor {mon.id} skipped — empty domains or checks")
        return False

    dom_sem = asyncio.Semaphore(3)

    async def _domain(d: str) -> tuple[str, dict]:
        async with dom_sem:
            return d, await _run_domain_checks(ctx, d, checks)

    domain_results = dict(await asyncio.gather(*[_domain(d) for d in domains]))

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

    snap = await ctx.store.create("wt_snapshots", {
        "owner_id":   owner_id,
        "monitor_id": mon.id,
        "status":     overall,
        "domains":    domain_results,
        "checks_run": checks,
        "summary": {
            "total_domains":    len(domains),
            "domains_ok":       dom_counts["ok"],
            "domains_warning":  dom_counts["warning"],
            "domains_critical": dom_counts["critical"],
            "domains_unknown":  dom_counts["unknown"],
        },
        "created_at": run_at,
    })
    await ctx.store.update("wt_monitors", mon.id, {
        "last_run_at":      run_at,
        "last_snapshot_id": snap.id,
    })
    if old_snap_id and old_snap_id != snap.id:
        try:
            await ctx.store.delete("wt_snapshots", old_snap_id)
        except Exception:
            pass

    log.info(f"wt_schedule: '{fresh.data.get('name')}' → {overall} ({len(domains)} domain(s))")
    return True
