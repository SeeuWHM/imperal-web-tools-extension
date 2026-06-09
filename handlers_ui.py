"""web-tools · Inline UI builders for ActionResult.ui chat responses."""
from __future__ import annotations

from imperal_sdk import ui


def _kv(items: list[tuple[str, str]]) -> ui.UINode:
    return ui.KeyValue(items=[{"key": k, "value": v} for k, v in items], columns=1)


def ssl_ui(domain: str, data: dict) -> ui.UINode:
    grade   = data.get("grade", "?")
    valid   = data.get("valid", False)
    days    = data.get("days_until_expiry")
    issuer  = data.get("issuer", "?")
    color   = "green" if grade in ("A", "A+") else "yellow" if grade == "B" else "red"
    items   = [
        ("Domain",  domain),
        ("Grade",   grade),
        ("Valid",   "Yes" if valid else "No"),
        ("Issuer",  str(issuer)[:60]),
    ]
    if days is not None:
        items.append(("Expires in", f"{days} days"))
    return ui.Stack([
        ui.Badge(f"SSL {grade}", color=color),
        _kv(items),
    ], gap=2)


def dns_ui(domain: str, record_type: str, records: list | dict) -> ui.UINode:
    if isinstance(records, list):
        rows = [{"type": record_type, "value": str(r)[:80]} for r in records[:20]]
    elif isinstance(records, dict):
        rows = [{"type": k, "value": str(v)[:80]} for k, v in list(records.items())[:20]]
    else:
        rows = [{"type": record_type, "value": str(records)[:80]}]
    return ui.Stack([
        ui.Text(f"DNS {record_type} — {domain}", variant="body"),
        ui.DataTable(
            columns=[
                ui.DataColumn("type",  "Type",  sortable=False, width="15%"),
                ui.DataColumn("value", "Value", sortable=False, width="85%"),
            ],
            rows=rows,
        ),
    ], gap=2)


def blacklist_ui(target: str, data: dict) -> ui.UINode:
    verdict = data.get("verdict", "unknown")
    listed  = data.get("listed_on", []) or []
    color   = "red" if verdict == "critical" else "yellow" if verdict == "listed" else "green"
    items   = [
        ("Target",  target),
        ("Verdict", verdict.upper()),
        ("Listed",  str(len(listed))),
    ]
    children: list = [ui.Badge(verdict.upper(), color=color), _kv(items)]
    if listed:
        children.append(ui.Alert(message=f"Listed on: {', '.join(listed[:5])}", type="error"))
    return ui.Stack(children, gap=2)


def http_ui(domain: str, data: dict) -> ui.UINode:
    grade    = data.get("grade", "?")
    score    = data.get("score", 0)
    missing  = data.get("missing", []) or []
    color    = "green" if grade in ("A+", "A") else "yellow" if grade == "B" else "red"
    items    = [
        ("Domain", domain),
        ("Grade",  grade),
        ("Score",  f"{score}/100"),
        ("Missing headers", str(len(missing))),
    ]
    children: list = [ui.Badge(f"HTTP {grade}", color=color), _kv(items)]
    if missing:
        children.append(ui.Alert(
            message="Missing: " + ", ".join(missing[:5]),
            type="warn",
        ))
    return ui.Stack(children, gap=2)


def full_audit_ui(domain: str, results: dict) -> ui.UINode:
    rows = []
    for check, data in results.items():
        if not data or isinstance(data, str):
            continue
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        color  = "green" if status == "ok" else "yellow" if status == "warning" else "red"
        rows.append({
            "check":  check.upper(),
            "status": status,
            "detail": _check_detail(check, data),
        })
    return ui.Stack([
        ui.Text(f"Domain audit: {domain}", variant="body"),
        ui.DataTable(
            columns=[
                ui.DataColumn("check",  "Check",  sortable=False, width="20%"),
                ui.DataColumn("status", "Status", sortable=False, width="20%"),
                ui.DataColumn("detail", "Detail", sortable=False, width="60%"),
            ],
            rows=rows,
        ),
    ], gap=2)


def _check_detail(check: str, data: dict) -> str:
    if not isinstance(data, dict):
        return str(data)[:60]
    # _run_domain_checks wraps results as {status, data} — unwrap inner data for details
    inner = data.get("data") if "data" in data else data
    if data.get("error"):
        return f"Error: {str(data.get('error'))[:50]}"
    if not isinstance(inner, dict):
        return str(inner)[:60] if inner else "—"
    if check == "ssl":
        return f"Grade {inner.get('grade','?')}, expires in {inner.get('days_until_expiry','?')}d"
    if check == "http":
        return f"Grade {inner.get('grade','?')}, score {inner.get('score','?')}/100"
    if check == "blacklist":
        return f"Verdict: {inner.get('verdict','unknown')}"
    if check == "dns":
        records = inner.get("records", {})
        return f"{len(records) if isinstance(records, (dict,list)) else '?'} records"
    if check == "email":
        spf  = "SPF "  + ("✓" if inner.get("spf")   else "✗")
        dkim = "DKIM " + ("✓" if inner.get("dkim")  else "✗")
        dmarc= "DMARC "+ ("✓" if inner.get("dmarc") else "✗")
        return f"{spf} · {dkim} · {dmarc}"
    if check == "geo":
        http = inner.get("http", {})
        regions = http.get("regions", {}) if isinstance(http, dict) else {}
        return f"{len(regions)} region(s) probed"
    if check == "whois":
        registrar = inner.get("registrar", inner.get("org", "?"))
        return f"Registrar: {str(registrar)[:40]}"
    if check == "seo":
        issues = inner.get("issues") or []
        n = len(issues) if isinstance(issues, (list, dict)) else issues
        return "No meta issues" if not n else f"{n} meta issue(s)"
    if check == "smtp":
        return "Reachable" if inner.get("reachable") else "Not reachable"
    return str(inner)[:60]
