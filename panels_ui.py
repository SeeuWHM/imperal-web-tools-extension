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
    if not data or "error" in data:
        return "Unavailable"

    if chk == "dns":
        records = data.get("records", {})
        if isinstance(records, dict):
            types = [t for t, v in records.items() if v]
            return f"Found ({', '.join(types[:5])})" if types else "Resolves"
        return "Resolves"

    if chk == "ssl":
        if not data.get("valid", True):
            return "Invalid certificate"
        days  = data.get("days_until_expiry")
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
        return f"Listed on {n} {'list' if n == 1 else 'lists'}"

    if chk == "geo":
        regions = data if isinstance(data, dict) else {}
        ok = sum(1 for r in regions.values()
                 if isinstance(r, dict) and not r.get("error"))
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
                d = data.get("days_until_expiry")
                parts.append(f"SSL {d}d" if d is not None else "SSL ✓")
            elif chk in ("http", "email"):  parts.append(f"{lbl} {data.get('grade', '?')}")
            elif chk == "blacklist":        parts.append("BL Clean")
            else:                           parts.append(f"{short} ✓")
        elif st == "warning":
            if chk == "ssl":
                d = data.get("days_until_expiry")
                parts.append(f"SSL {d}d!" if d is not None else "SSL !")
            elif chk in ("http", "email"):  parts.append(f"{lbl} {data.get('grade', '?')}")
            elif chk == "blacklist":        parts.append(f"BL({len(data.get('listed_on') or [])})")
            else:                           parts.append(f"{short} !")
        elif st == "critical":  parts.append(f"{short} ✗")
        else:                   parts.append(f"{short} —")
    return " · ".join(parts)


def domain_items(domains_data: dict) -> list:
    """Expandable ListItem per domain — status badge on row, per-check detail on expand."""
    items = []
    for domain, checks in sorted(domains_data.items()):
        statuses = [c.get("status", "unknown") for c in checks.values()]
        overall  = (
            "critical" if "critical" in statuses else
            "warning"  if "warning"  in statuses else
            "ok"       if "ok"       in statuses else "unknown"
        )
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


# ─── Detail view builder ─────────────────────────────────────────────────── #

def build_detail_view(mon, grp_name: str, snap) -> ui.Stack:
    """Right panel detail view for a specific monitor — toolbar + domain list."""
    status  = snap.data.get("status", "unknown") if snap else "unknown"
    domains = snap.data.get("domains", {}) if snap else {}
    last    = (mon.data.get("last_run_at") or "Never")[:10]

    toolbar = ui.Stack([
        ui.Button("All Monitors", icon="ArrowLeft", variant="ghost", size="sm",
                  on_click=ui.Call("__panel__stats", selected_monitor_id="")),
        ui.Stack([
            ui.Text(content=mon.data["name"], variant="subheading"),
            status_badge(status),
        ], direction="horizontal", gap=2),
        ui.Button("Scan Now", icon="Play", variant="secondary", size="sm",
                  on_click=ui.Call("run_scan", monitor_id=mon.id)),
    ], direction="horizontal", gap=2, justify="between", sticky=True)

    subtitle = ui.Text(
        content=f"{grp_name} · Last scan: {last} · every {mon.data['interval_hours']}h",
        variant="caption",
    )

    settings_accordion = ui.Accordion(sections=[
        {"id": "mon_settings", "title": "Monitor Settings", "children": [
            ui.Form(
                action="update_monitor",
                submit_label="Save",
                defaults={"monitor_id": mon.id},
                children=[
                    ui.Input(placeholder="Monitor name", param_name="name",
                             value=mon.data["name"]),
                    ui.Select(options=INTERVAL_OPTS,
                              value=str(mon.data["interval_hours"]),
                              param_name="interval_hours"),
                ],
            ),
        ]},
    ])

    if not domains:
        return ui.Stack([
            toolbar, subtitle,
            ui.Empty(message="No scan results yet — press Scan Now", icon="Activity"),
            settings_accordion,
        ])

    all_chks = [c for d in domains.values() for c in d.values()]
    n_ok   = sum(1 for c in all_chks if c.get("status") == "ok")
    n_warn = sum(1 for c in all_chks if c.get("status") == "warning")
    n_crit = sum(1 for c in all_chks if c.get("status") == "critical")
    n_unk  = sum(1 for c in all_chks if c.get("status") == "unknown")
    summary = ui.Text(
        content=(f"{len(domains)} domains · {n_ok} OK"
                 + (f" · {n_warn} warning" if n_warn else "")
                 + (f" · {n_crit} critical" if n_crit else "")
                 + (f" · {n_unk} unavailable" if n_unk else "")),
        variant="caption",
    )

    critical_alert = (
        ui.Alert(type="error", message=f"{n_crit} check(s) are critical — review domains below")
        if n_crit else None
    )
    content: list = [toolbar, subtitle]
    if critical_alert:
        content.append(critical_alert)
    content += [summary, ui.List(items=domain_items(domains), searchable=True),
                settings_accordion]
    return ui.Stack(content)


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
