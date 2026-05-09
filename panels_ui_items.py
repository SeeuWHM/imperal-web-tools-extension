"""web-tools · Domain/scan component builders — scan_tool_items, domain_items, ip_scan_items."""
from __future__ import annotations

from imperal_sdk import ui

from panels_ui_base import status_badge, _fmt_check_value


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


def build_check_toggles(enabled_checks: list[str]) -> ui.UINode:
    """Toggle group for check profile editor — one Toggle per check in PROFILE_CHECK_OPTS."""
    return ui.Stack([
        ui.Toggle(
            label=opt["label"],
            param_name=opt["value"],
            value=opt["value"] in enabled_checks,
        )
        for opt in PROFILE_CHECK_OPTS
    ], direction="v", gap=2)


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


def domain_items(domains_data: dict) -> list:
    """Expandable ListItem per domain — status badge on row, per-check KV detail on expand."""
    items = []
    for domain, checks in sorted(domains_data.items()):
        statuses    = [c.get("status", "unknown") for c in checks.values()]
        has_unknown = "unknown" in statuses
        overall     = (
            "critical" if "critical" in statuses else
            "warning"  if "warning"  in statuses else
            "ok"       if "ok" in statuses and not has_unknown else
            "unknown"
        )
        kv = [
            {"key": chk.upper(), "value": _fmt_check_value(chk, res.get("data") or {})}
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


# ─── IP Scan result helpers ───────────────────────────────────────────────── #

def _fmt_ip_val(chk: str, data: dict) -> str:
    """One-line summary for a single IP check result."""
    if not data:
        return ""
    if chk == "ip_lookup":
        country = data.get("country", "")
        org     = (data.get("org") or "")[:22]
        return f"{country} · {org}".strip(" ·") or "—"
    if chk == "blacklist":
        verdict = data.get("verdict", "clean")
        if verdict == "clean":
            return "BL Clean"
        total = data.get("listed_count", 0)
        names = [r["name"] for r in (data.get("results") or []) if r.get("listed")][:2]
        more  = f" +{total - len(names)}" if total > len(names) else ""
        return (f"BL: {', '.join(names)}{more}" if names else f"BL Listed ({total})")
    if chk == "reverse":
        hn = data.get("hostname") or data.get("ptr")
        return f"PTR: {hn}" if hn else "No PTR"
    if chk == "ports":
        open_p = [str(p["port"]) for p in (data.get("ports") or [])
                  if p.get("status") == "open"]
        return f"Open: {', '.join(open_p[:4])}" if open_p else "All closed"
    if chk == "geo_ping":
        regions = data.get("regions", {})
        reach   = sum(1 for r in regions.values()
                      if isinstance(r, dict) and r.get("reachable"))
        return f"Ping {reach}/{len(regions)}"
    return chk.upper()


def ip_scan_items(results: dict) -> list:
    """Compact non-expandable ListItems for IP Scan Tool."""
    items = []
    for ip, checks in sorted(results.items()):
        statuses = [c.get("status", "ok") for c in checks.values()]
        overall  = (
            "critical" if "critical" in statuses else
            "warning"  if "warning"  in statuses else "ok"
        )
        parts    = [_fmt_ip_val(chk, (res.get("data") or {}))
                    for chk, res in checks.items()]
        subtitle = " · ".join(p for p in parts if p)
        items.append(ui.ListItem(
            id=ip, title=ip,
            subtitle=subtitle or "—",
            badge=status_badge(overall),
        ))
    return items

