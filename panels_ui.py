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

# Check type labels and tooltip descriptions (used in setup panel)
CHECKS_INFO: dict[str, tuple[str, str]] = {
    "ssl":       ("SSL Certificate",      "Grade A-F · days until expiry · issuer & chain"),
    "http":      ("HTTP Headers",         "Security grade A-F · HSTS, CSP, X-Frame-Options, XCTO"),
    "email":     ("Email Deliverability", "SPF · DMARC · DKIM grade A-F · catches delivery issues"),
    "blacklist": ("Blacklist",            "IP vs 30 DNSBL lists (Spamhaus, SpamCop, Barracuda) · clean / listed"),
    "geo":       ("Geo Probe",            "Availability from 4 regions: EU · US · SG · MD"),
    "whois":     ("WHOIS",               "Domain registrar · expiry date · nameservers"),
    "dns":       ("DNS Records",          "A · MX · NS · TXT record lookup · basic DNS health"),
}


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
    _label = {"ok": "OK",    "warning": "Warning", "critical": "Critical"}
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
        verdict = data.get("verdict", "clean")
        listed  = data.get("listed_on") or []
        if verdict == "clean":
            return "Clean"
        n = len(listed)
        if n == 0:
            return "Listed"
        return f"Listed on {n} {'list' if n == 1 else 'lists'}"

    if chk == "geo":
        # Geo data is {dns: {regions: {...}}, http: {regions: {...}}, ssl: {...}}
        # Use http regions as availability signal; fall back to dns regions
        regions = (data.get("http", {}).get("regions") or
                   data.get("dns", {}).get("regions") or {})
        if not regions and isinstance(data, dict):
            # Quick-check single-probe: data IS the flat regions dict
            flat_ok = all(
                v.get("available", True) for v in data.values()
                if isinstance(v, dict) and "region" in v
            )
            region_items = [v for v in data.values()
                            if isinstance(v, dict) and "region" in v]
            if region_items:
                ok = sum(1 for r in region_items if not r.get("error") and r.get("available", True))
                return f"{ok}/{len(region_items)} regions reachable"
        ok = sum(1 for r in regions.values()
                 if isinstance(r, dict) and not r.get("error") and r.get("available", True))
        total = len(regions)
        return f"{ok}/{total} regions reachable" if total else "OK"

    if chk == "whois":
        registrar = data.get("registrar", "")
        exp = (data.get("expiry_date") or "")[:10]
        if registrar:
            return f"{registrar}" + (f" · exp {exp}" if exp else "")
        return "Found"

    return "OK"


# ─── Domain / scan component builders ────────────────────────────────────── #

def _check_subtitle(checks: dict) -> str:
    """One-line check summary: "DNS ✓ · SSL 45d · HTTP B · Email C · BL Clean"."""
    parts: list[str] = []
    for chk, res in checks.items():
        st    = res.get("status", "unknown")
        data  = res.get("data") or {}
        short = chk.upper()
        lbl   = "HTTP" if chk == "http" else "Email" if chk == "email" else short
        if st == "ok":
            if chk == "dns":                parts.append("DNS ✓")
            elif chk == "ssl":
                d = data.get("days_until_expiry") or data.get("days_remaining")
                parts.append(f"SSL {d}d" if d is not None else "SSL ✓")
            elif chk in ("http", "email"):  parts.append(f"{lbl} {data.get('grade', '?')}")
            elif chk == "blacklist":        parts.append("BL Clean")
            elif chk == "geo":
                geo_r = (data.get("http", {}).get("regions") or
                         data.get("dns", {}).get("regions") or {})
                ok_r  = sum(1 for r in geo_r.values()
                            if isinstance(r, dict) and not r.get("error") and r.get("available", True))
                tot_r = len(geo_r)
                parts.append(f"GEO {ok_r}/{tot_r}" if tot_r else "GEO ✓")
            else:                           parts.append(f"{short} ✓")
        elif st == "warning":
            if chk == "ssl":
                d = data.get("days_until_expiry") or data.get("days_remaining")
                parts.append(f"SSL {d}d!" if d is not None else "SSL !")
            elif chk in ("http", "email"):  parts.append(f"{lbl} {data.get('grade', '?')}")
            elif chk == "blacklist":
                n_bl = len(data.get("listed_on") or [])
                parts.append(f"BL({n_bl})" if n_bl else "BL Listed")
            elif chk == "geo":
                geo_r = (data.get("http", {}).get("regions") or
                         data.get("dns", {}).get("regions") or {})
                ok_r  = sum(1 for r in geo_r.values()
                            if isinstance(r, dict) and not r.get("error") and r.get("available", True))
                tot_r = len(geo_r)
                parts.append(f"GEO {ok_r}/{tot_r}!" if tot_r else "GEO !")
            else:                           parts.append(f"{short} !")
        elif st == "critical":  parts.append(f"{short} ✗")
        else:                   parts.append(f"{short} —")
    return " · ".join(parts)


def domain_items(domains_data: dict) -> list:
    """Expandable ListItem per domain — status badge on row, per-check detail on expand."""
    items = []
    for domain, checks in sorted(domains_data.items()):
        statuses = [c.get("status", "unknown") for c in checks.values()]
        has_unknown = "unknown" in statuses
        overall  = (
            "critical" if "critical" in statuses else
            "warning"  if "warning"  in statuses else
            "ok"       if "ok" in statuses and not has_unknown else
            "unknown"
        )
        # "ok" only when ALL checks ran cleanly — if any check failed to run
        # (unknown/unavailable), badge shows "—" so user knows it's incomplete
        kv = [
            {"key":   chk.upper(),
             "value": _fmt_check_value(chk, res.get("data") or {})}
            for chk, res in checks.items()
        ]
        expanded = (
            [ui.KeyValue(items=kv, columns=2)] if kv
            else [ui.Text(content="No check data available", variant="caption")]
        )
        items.append(ui.ListItem(
            id=domain,
            title=domain,
            subtitle=_check_subtitle(checks),
            badge=status_badge(overall),
            expandable=True,
            expanded_content=expanded,
        ))
    return items


def quick_kv(q: dict) -> list:
    """KeyValue rows for the last quick check result block."""
    results = q.get("results")   # full audit: {check: raw_data}
    result  = q.get("result")    # single check: raw_data dict
    preset  = q.get("preset", "")

    if results and isinstance(results, dict):
        return [
            {"key": chk.upper(), "value": _fmt_check_value(chk, data)}
            for chk, data in results.items()
            if isinstance(data, dict)
        ]

    if result and isinstance(result, dict):
        # Single-check result — format based on preset
        val = _fmt_check_value(preset, result) if preset else "OK"
        if val == "OK":
            # Fall back: show top-level scalar fields
            skip = {"raw", "error", "success", "checked_at", "timestamp"}
            return [
                {"key": k.replace("_", " ").title(), "value": str(v)}
                for k, v in result.items()
                if k not in skip and not isinstance(v, (dict, list))
            ][:8]
        return [{"key": preset.upper(), "value": val}]

    return []

# ─── Setup list builders ─────────────────────────────────────────────────── #

def group_items(grp_page_data: list) -> list:
    """ListItem per domain group — shows domain count, offers delete action."""
    return [
        ui.ListItem(
            id=g.id,
            title=g.data["name"],
            subtitle=f"{len(g.data.get('domains', []))} domain(s)",
            icon="Globe",
            actions=[
                {"icon": "Trash2", "label": "Delete",
                 "on_click": ui.Call("delete_domain_group", group_id=g.id),
                 "confirm": f"Delete group '{g.data['name']}' and all its monitors?"},
            ],
        )
        for g in grp_page_data
    ]


def profile_items(prf_page_data: list) -> list:
    """ListItem per check profile — shows check types, offers delete action."""
    return [
        ui.ListItem(
            id=p.id,
            title=p.data["name"],
            subtitle=", ".join(p.data.get("checks", [])),
            icon="CheckSquare",
            actions=[
                {"icon": "Trash2", "label": "Delete",
                 "on_click": ui.Call("delete_check_profile", profile_id=p.id),
                 "confirm": f"Delete profile '{p.data['name']}' and all its monitors?"},
            ],
        )
        for p in prf_page_data
    ]
