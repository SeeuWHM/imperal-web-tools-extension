"""web-tools · Skeleton — background monitor status refresh (SDK 5.2.0)."""
from __future__ import annotations

import asyncio

from app import ext
from imperal_sdk import ActionResult


@ext.skeleton(
    "web_tools",
    ttl=300,
    description="Web Tools monitor health summary — critical/warning/ok counts only. "
                "For DNS lookups, domain audits, geo checks and all diagnostic tools "
                "use dns_lookup / domain_full_check / geo_check — they do NOT require monitors.",
)
async def on_refresh(ctx) -> ActionResult:
    """Load aggregate monitor health — counts only, no names (names confuse LLM routing)."""
    try:
        page = await ctx.store.query("wt_monitors", where={"owner_id": ctx.user.imperal_id}, limit=10)
        if not page.data:
            return ActionResult.success(
                data={"total": 0, "critical": 0, "warning": 0, "ok": 0, "unknown": 0},
                summary="Web Tools: 0 monitors configured. Use dns_lookup or domain_full_check for instant domain checks.",
            )

        snap_ids = [m.data.get("last_snapshot_id") for m in page.data]

        async def _get_snap(snap_id):
            if snap_id:
                return await ctx.store.get("wt_snapshots", snap_id)
            return None

        snaps = await asyncio.gather(*[_get_snap(sid) for sid in snap_ids])

        critical = warning = ok = unknown = 0
        for snap in snaps:
            if not snap:
                unknown += 1
                continue
            status = snap.data.get("status", "unknown")
            if status == "critical":   critical += 1
            elif status == "warning":  warning  += 1
            elif status == "ok":       ok       += 1
            else:                      unknown  += 1

        total = len(page.data)
        return ActionResult.success(
            data={
                "total":    total,
                "critical": critical,
                "warning":  warning,
                "ok":       ok,
                "unknown":  unknown,
            },
            summary=(
                f"Web Tools: {total} recurring monitor(s) — "
                f"{critical} critical, {warning} warning, {ok} ok. "
                "For instant domain checks use dns_lookup or domain_full_check (no monitors needed)."
            ),
        )

    except Exception as exc:
        return ActionResult.success(
            data={"total": 0, "critical": 0, "warning": 0, "ok": 0, "unknown": 0},
            summary="Web Tools skeleton refresh failed.",
        )
