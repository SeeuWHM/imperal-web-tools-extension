"""web-tools · Panel UI helpers — options, labels, component builders."""
from __future__ import annotations

from imperal_sdk import ui

# ─── Select options ───────────────────────────────────────────────────────── #

CHECKS_OPTS = [
    {"value": "dns",       "label": "DNS"},
    {"value": "ssl",       "label": "SSL"},
    {"value": "http",      "label": "HTTP Headers"},
    {"value": "email",     "label": "Email Deliverability"},
    {"value": "blacklist", "label": "Blacklist"},
    {"value": "geo",       "label": "Geo Probe"},
    {"value": "whois",     "label": "WHOIS"},
]

PRESET_OPTS = [
    {"value": "full",      "label": "Full Audit — DNS · SSL · HTTP · Email · BL"},
    {"value": "dns",       "label": "DNS Records"},
    {"value": "ssl",       "label": "SSL Certificate"},
    {"value": "http",      "label": "HTTP Headers"},
    {"value": "email",     "label": "Email Deliverability"},
    {"value": "blacklist", "label": "Blacklist"},
    {"value": "geo",       "label": "Geo Probe — EU / US / SG / MD"},
    {"value": "ports",     "label": "Port Scan"},
]

INTERVAL_OPTS = [
    {"value": "1",   "label": "Every hour"},
    {"value": "6",   "label": "Every 6 hours"},
    {"value": "12",  "label": "Every 12 hours"},
    {"value": "24",  "label": "Every day"},
    {"value": "48",  "label": "Every 2 days"},
    {"value": "168", "label": "Every week"},
]

# ─── Status helpers ───────────────────────────────────────────────────────── #

def status_label(status: str) -> str:
    """Human-readable status label."""
    return {"ok": "OK", "warning": "WARNING", "critical": "CRITICAL"}.get(status, "—")


def check_detail(check: str, data: dict) -> str:
    """Short context string appended to status — e.g. '· 12d left', '· grade F'."""
    if not data:
        return ""
    if check == "ssl":
        days = data.get("days_until_expiry")
        if days is not None:
            return f" · {days}d left"
    if check in ("http", "email"):
        grade = data.get("grade")
        if grade:
            return f" · grade {grade}"
    if check == "blacklist":
        verdict = data.get("verdict", "")
        if verdict and verdict != "clean":
            return f" · {verdict}"
    return ""


# ─── Component builders ───────────────────────────────────────────────────── #

def domain_items(domains_data: dict) -> list:
    """Expandable ListItem per domain — status on row, per-check KeyValue on expand."""
    items = []
    for domain, checks in sorted(domains_data.items()):
        statuses = [c.get("status", "ok") for c in checks.values()]
        overall  = (
            "CRITICAL" if "critical" in statuses else
            "WARNING"  if "warning"  in statuses else "OK"
        )
        kv = [
            {"key":   chk.upper(),
             "value": status_label(res.get("status", "ok"))
                      + check_detail(chk, res.get("data") or {})}
            for chk, res in checks.items()
        ]
        items.append(ui.ListItem(
            id=domain,
            title=domain,
            meta=overall,
            expandable=True,
            expanded_content=[ui.KeyValue(items=kv, columns=2)],
        ))
    return items


def quick_kv(q: dict) -> list:
    """KeyValue rows for the last quick check result block."""
    results = q.get("results")   # full audit: {check: raw_data}
    result  = q.get("result")    # single check: raw_data dict

    if results and isinstance(results, dict):
        rows = []
        for chk, data in results.items():
            if not isinstance(data, dict):
                continue
            val = "ERROR" if "error" in data else ("OK" + check_detail(chk, data))
            rows.append({"key": chk.upper(), "value": val})
        return rows

    if result and isinstance(result, dict):
        skip = {"raw", "error", "success", "checked_at", "timestamp"}
        return [
            {"key": k.replace("_", " ").title(), "value": str(v)}
            for k, v in result.items()
            if k not in skip and not isinstance(v, (dict, list))
        ][:8]

    return []
