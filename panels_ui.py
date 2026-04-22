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


# ─── Domain / scan component builders ────────────────────────────────────── #

def _check_subtitle(checks: dict) -> str:
    """One-line check summary: "DNS ✓ · SSL 45d · HTTP B · Email C · BL Clean"."""
    parts: list[str] = []
    for chk, res in checks.items():
        st    = res.get("status", "unknown")
        data  = res.get("data") or {}
        short = chk.upper()
        lbl   = {"http": "HTTP", "email": "Email", "propagation": "PROP",
                  "smtp": "SMTP"}.get(chk, short)
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
                            if isinstance(r, dict) and not r.get("error") and r.get("ok", False))
                tot_r = len(geo_r)
                parts.append(f"GEO {ok_r}/{tot_r}" if tot_r else "GEO ✓")
            else:                           parts.append(f"{short} ✓")
        elif st == "warning":
            if chk == "ssl":
                d = data.get("days_until_expiry") or data.get("days_remaining")
                parts.append(f"SSL {d}d!" if d is not None else "SSL !")
            elif chk in ("http", "email"):  parts.append(f"{lbl} {data.get('grade', '?')}")
            elif chk == "blacklist":
                n_bl = data.get("ip_listed_count", 0) + data.get("domain_listed_count", 0)
                parts.append(f"BL({n_bl})" if n_bl else "BL Listed")
            elif chk == "geo":
                geo_r = (data.get("http", {}).get("regions") or
                         data.get("dns", {}).get("regions") or {})
                ok_r  = sum(1 for r in geo_r.values()
                            if isinstance(r, dict) and not r.get("error") and r.get("ok", False))
                tot_r = len(geo_r)
                parts.append(f"GEO {ok_r}/{tot_r}!" if tot_r else "GEO !")
            else:                           parts.append(f"{short} !")
        elif st == "critical":  parts.append(f"{short} ✗")
        else:                   parts.append(f"{short} —")
    return " · ".join(parts)


def _fmt_check_expanded(chk: str, data: dict) -> str:
    """Verbose single-line per check for expanded scan results view."""
    if not data or data.get("error"):
        return "Unavailable"
    if chk == "ssl":
        days  = data.get("days_until_expiry") or data.get("days_remaining")
        grade = data.get("grade", "?")
        issuer = (data.get("issuer") or "")[:25]
        return " · ".join(p for p in
            [f"Grade {grade}", f"{days}d left" if days is not None else None, issuer] if p)
    if chk == "http":
        grade   = data.get("grade", "?")
        score   = data.get("score")
        missing = [h.get("name", "") for h in data.get("headers", [])
                   if h.get("status") in ("missing", "invalid")][:3]
        parts   = [f"Grade {grade}"]
        if score:   parts.append(f"{score}/100")
        if missing: parts.append("Missing: " + ", ".join(missing))
        return " · ".join(parts)
    if chk == "email":
        grade  = data.get("grade", "?")
        spf_ok = "✓" if (data.get("spf") or {}).get("valid") else "✗"
        dm     = data.get("dmarc") or {}
        dm_ok  = "✓" if dm.get("valid") else "✗"
        dp     = dm.get("policy", "")
        dk_ok  = "✓" if (data.get("dkim") or {}).get("valid") else "✗"
        return (f"Grade {grade} · SPF{spf_ok} · "
                f"DMARC{dm_ok}{f' p={dp}' if dp and dp != 'reject' else ''} · DKIM{dk_ok}")
    if chk == "geo":
        regions = (data.get("http", {}).get("regions") or
                   data.get("dns", {}).get("regions") or {})
        parts = []
        for name, r in regions.items():
            if not isinstance(r, dict): continue
            disp = _REGION_DISPLAY.get(name, name)
            ok = r.get("ok", False)
            ms = r.get("latency_ms") or r.get("probe_ms")
            parts.append(f"{disp} {'✓' if ok else '✗'}"
                         + (f" {int(ms)}ms" if ms and ok else ""))
        return " · ".join(parts) or "—"
    if chk == "propagation":
        srvs = data.get("servers", [])
        parts = []
        for s in srvs:
            raw  = s.get("name") or s.get("location") or "?"
            name = raw.split("(")[0].strip()
            ok   = s.get("status") == "success"
            parts.append(f"{name} {'✓' if ok else '✗'}")
        return " · ".join(parts[:6]) or "—"
    if chk == "smtp":
        if not data.get("reachable"): return "Not reachable"
        port = data.get("best_port", "")
        tls  = "✓" if data.get("starttls_available") else "✗"
        sw   = (data.get("server_software") or "")[:15]
        mx   = (data.get("mx_host") or "")[:20]
        return (f"Port {port} · TLS {tls}"
                + (f" · {sw}" if sw else "") + (f" · MX: {mx}" if mx else ""))
    if chk == "ports":
        ports_list = data.get("results", [])
        if not ports_list:
            return "—"
        parts = []
        for p in ports_list:
            sym = "✓" if p.get("status") == "open" else "✗"
            svc = p.get("service", "")
            parts.append(f"{p.get('port')} {sym}" + (f" {svc}" if svc else ""))
        return " · ".join(parts[:8]) or "—"
    return _fmt_check_value(chk, data)


def scan_tool_items(results: dict) -> list:
    """Expandable ListItems for Domain Scan Tool — subtitle + KV detail per check."""
    items = []
    for domain, checks in sorted(results.items()):
        statuses = [c.get("status", "unknown") for c in checks.values()]
        has_unk  = "unknown" in statuses
        overall  = (
            "critical" if "critical" in statuses else
            "warning"  if "warning"  in statuses else
            "ok"       if "ok" in statuses and not has_unk else
            "unknown"
        )
        kv = [{"key": chk.upper(),
               "value": _fmt_check_expanded(chk, res.get("data") or {})}
              for chk, res in checks.items()]
        items.append(ui.ListItem(
            id=domain, title=domain,
            subtitle=_check_subtitle(checks),
            badge=status_badge(overall),
            expandable=True,
            expanded_content=[
                ui.Stack([ui.KeyValue(items=kv, columns=1)], className="select-text"),
            ] if kv else [],
            actions=[],
        ))
    return items

