"""web-tools · Panel UI helpers — options, labels, component builders."""
from __future__ import annotations

from imperal_sdk import ui

# Region display names: raw API key → short label shown in UI
_REGION_DISPLAY = {"EU": "WEU", "MD": "EEU", "SG": "AS", "US": "US"}

# ─── Select options ───────────────────────────────────────────────────────── #

INTERVAL_OPTS = [
    {"value": "1",   "label": "Every hour"},
    {"value": "6",   "label": "Every 6 hours"},
    {"value": "12",  "label": "Every 12 hours"},
    {"value": "24",  "label": "Every day"},
    {"value": "48",  "label": "Every 2 days"},
    {"value": "168", "label": "Every week"},
]

# MultiSelect options for check profile forms (label includes brief description)
PROFILE_CHECK_OPTS = [
    {"value": "ssl",       "label": "SSL Certificate — grade A-F, expiry days"},
    {"value": "http",      "label": "HTTP Headers — security grade A-F"},
    {"value": "email",     "label": "Email Delivery — SPF · DMARC · DKIM"},
    {"value": "blacklist", "label": "Blacklist — 29 DNSBL lists"},
    {"value": "geo",       "label": "Geo Probe — WEU · US · AS · EEU"},
    {"value": "whois",     "label": "WHOIS — registrar, expiry date"},
]
PROFILE_CHECK_DEFAULTS = ["ssl", "http", "email", "blacklist"]


def fmt_interval(hours: int) -> str:
    """Human-readable interval: 168 → 'every week', 48 → 'every 2 days'."""
    _map = {1: "every hour", 6: "every 6h", 12: "every 12h",
            24: "every day", 48: "every 2 days", 168: "every week"}
    if hours in _map:
        return _map[hours]
    return f"every {hours}h" if hours < 24 else f"every {hours // 24}d"


# ─── Status helpers ───────────────────────────────────────────────────────── #

def status_badge(status: str) -> ui.Badge:
    """Colored Badge for monitor/domain status. Expects: ok/warning/critical/unknown."""
    _color = {"ok": "green", "warning": "yellow", "critical": "red"}
    _label = {"ok": "OK",   "warning": "Warning",  "critical": "Critical"}
    return ui.Badge(label=_label.get(status, "—"), color=_color.get(status, "gray"))


def _fmt_check_value(chk: str, data: dict | None) -> str:
    """User-friendly value string for a single check result.

    Used by both quick_kv (right-panel card) and domain_items (expandable detail).
    Returns a plain string — no status prefix needed, the value speaks for itself.
    """
    if not data or data.get("error"):
        return "Unavailable"

    if chk == "dns":
        records = data.get("records", {})
        if isinstance(records, dict):
            types = [t for t, v in records.items() if v]
            if not types:
                return "No records"
            if types == ["NS"] or (len(types) == 1 and types[0] == "NS"):
                return "Found (NS only)"
            return f"Found ({', '.join(types[:5])})"
        return "No records"

    if chk == "ssl":
        if not data.get("valid", True):
            return "Invalid certificate"
        days  = data.get("days_until_expiry") or data.get("days_remaining")
        grade = data.get("grade", "?")
        if days is not None:
            return f"Grade {grade} · {days}d left"
        return f"Grade {grade}"

    if chk in ("http", "email"):
        grade = data.get("grade", "?")
        return f"Grade {grade}"

    if chk == "blacklist":
        verdict     = data.get("verdict", "clean")
        resolved_ip = data.get("resolved_ip")
        if not resolved_ip and verdict == "clean":
            return "Unresolvable"
        if verdict == "clean":
            return "Clean"
        total = data.get("ip_listed_count", 0) + data.get("domain_listed_count", 0)
        names = ([r["name"] for r in data.get("ip_results",    []) if r.get("listed")]
               + [r["name"] for r in data.get("surbl_results", []) if r.get("listed")])[:3]
        more  = f" +{total - len(names)}" if total > len(names) else ""
        prefix = "Critical" if verdict == "critical" else "Listed"
        return (f"{prefix}: {', '.join(names)}{more}" if names else f"{prefix} on {total} DNSBL(s)")

    if chk == "geo":
        regions = (data.get("http", {}).get("regions") or
                   data.get("dns", {}).get("regions") or {})
        if not regions and isinstance(data, dict):
            region_items = [v for v in data.values()
                            if isinstance(v, dict) and "region" in v]
            if region_items:
                ok = sum(1 for r in region_items if not r.get("error") and r.get("available", True))
                return f"{ok}/{len(region_items)} regions reachable"
        ok = sum(1 for r in regions.values()
                 if isinstance(r, dict) and not r.get("error") and r.get("ok", False))
        total = len(regions)
        return f"{ok}/{total} regions reachable" if total else "OK"

    if chk == "whois":
        registrar = data.get("registrar") or ""
        exp = (data.get("expires") or data.get("expiry_date") or "")[:10]
        days = data.get("days_until_expiry")
        if registrar:
            return f"{registrar}" + (f" · {days}d" if days else (f" · {exp}" if exp else ""))
        return (f"Exp {exp} · {days}d" if exp and days else f"Exp {exp}" if exp else "—")

    if chk == "smtp":
        if not data.get("reachable"):
            return "Not reachable"
        port    = data.get("best_port", "")
        tls     = data.get("starttls_available", False)
        sw      = data.get("server_software") or ""
        return (f"Port {port} · {'STARTTLS ✓' if tls else 'No STARTTLS'}"
                + (f" · {sw}" if sw else ""))

    if chk == "propagation":
        propagated = data.get("fully_propagated", True)
        servers    = data.get("servers", [])
        ok_count   = sum(1 for s in servers if s.get("status") == "success")
        total      = len(servers)
        if not total:
            return "—"
        return (f"Consistent · {ok_count}/{total} servers" if propagated
                else f"Inconsistent! · {ok_count}/{total} agree")

    if chk == "ports":
        open_p = [str(p.get("port", "")) for p in data.get("results", []) if p.get("status") == "open"]
        return f"Open: {', '.join(open_p[:5])}" if open_p else "All closed"

    return "OK"

