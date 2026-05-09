"""web-tools · Scheduled monitor runner — hourly cron, runs overdue monitors.

Architecture: @ext.schedule runs under __system__ context. Uses ctx.store.list_users()
to iterate all users that have monitors, then ctx.as_user(uid) to get a scoped Context
for per-user store operations. Pattern: SDK 1.5.23+ canonical fan-out (Rule 20).
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
            try:
                page = await user_ctx.store.query("wt_monitors",
                                                  where={"enabled": True}, limit=100)
                for mon in page.data:
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
                log.warning(f"wt_schedule: user {user_id} failed: {exc}")
    except Exception as exc:
        log.error(f"wt_schedule: runner failed: {exc}")

    if run_count:
        log.info(f"wt_schedule: ran {run_count} monitor(s)")


# ─── Internal helpers ─────────────────────────────────────────────────────── #

async def _maybe_run(ctx, mon, now: datetime.datetime) -> bool:
    """Run scan if monitor is overdue. ctx is already scoped to the monitor owner."""
    last_run = mon.data.get("last_run_at")
    interval_h = mon.data.get("interval_hours", 24)

    if last_run:
        try:
            last_run_dt = datetime.datetime.fromisoformat(last_run)
            if last_run_dt.tzinfo is None:
                last_run_dt = last_run_dt.replace(tzinfo=datetime.timezone.utc)
            elapsed_h = (now - last_run_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            elapsed_h = interval_h + 1  # malformed or incompatible timestamp → run it
        if elapsed_h < interval_h:
            return False

    grp = await ctx.store.get("wt_groups",   mon.data["group_id"])
    prf = await ctx.store.get("wt_profiles", mon.data["profile_id"])
    if not grp or not prf:
        log.debug(f"wt_schedule: monitor {mon.id} skipped — group/profile missing")
        return False

    domains: list[str] = grp.data["domains"]
    checks:  list[str] = prf.data["checks"]
    run_at   = now.isoformat()
    owner_id = mon.data.get("owner_id", "")

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

    old_snap_id = mon.data.get("last_snapshot_id")
    if old_snap_id and old_snap_id != snap.id:
        try:
            await ctx.store.delete("wt_snapshots", old_snap_id)
        except Exception:
            pass

    log.info(f"wt_schedule: '{mon.data.get('name')}' → {overall} ({len(domains)} domain(s))")
    return True
