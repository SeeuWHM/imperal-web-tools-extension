"""web-tools · shared web-tools-api envelope handling (SDK 5.x).

Every web-tools-api response is `{success: bool, data | error}`. Failures can arrive
two ways and `error` has two shapes — this module normalizes all of it so a backend
hiccup never crashes a chat turn (it becomes a clean ActionResult.error instead):

  • transport  — HTTP 4xx/5xx with the typed envelope `{success:false, error:{code,message}}`
  • logical    — HTTP 200 with `success:false`
  • error body — `{code, message}` (current backend) OR a bare string (legacy endpoints)

Handlers call `unwrap(resp, "…")` and branch on the returned (data, error) pair.
"""
from __future__ import annotations

from typing import Any


def error_message(body: Any, fallback: str) -> str:
    """Coerce any backend error shape (str | {code,message} | None) into one clean string."""
    err = body.get("error") if isinstance(body, dict) else body
    if isinstance(err, dict):
        msg = err.get("message") or err.get("detail")
        code = err.get("code")
        if msg and code and str(code) not in str(msg):
            return f"{msg} [{code}]"
        return str(msg or code or fallback)
    if isinstance(err, str) and err.strip():
        return err.strip()
    return fallback


def error_code(body: Any) -> str | None:
    """Extract the backend error code ({code,message} shape only), else None."""
    err = body.get("error") if isinstance(body, dict) else None
    return err.get("code") if isinstance(err, dict) else None


def unwrap_full(resp, fallback: str) -> tuple[dict | None, str | None, str | None]:
    """Return (data, error_code, error_msg). data on success; code+msg on failure.

    Never raises on HTTP status. The code lets callers branch on WHY a read failed
    (e.g. escalate a CHALLENGE_BLOCKED page to the heavy reader).
    """
    try:
        body = resp.json()
    except Exception:
        status = getattr(resp, "status_code", "?")
        return None, None, f"{fallback} (HTTP {status}, non-JSON response)"
    if isinstance(body, dict) and body.get("success"):
        data = body.get("data")
        return (data if isinstance(data, dict) else {}), None, None
    return None, error_code(body), error_message(body, fallback)


def unwrap(resp, fallback: str) -> tuple[dict | None, str | None]:
    """Return (data, None) on success, (None, error_msg) on any failure.

    Never raises on HTTP status — a 4xx/5xx envelope is parsed, not thrown, so the
    LLM receives a fact ('this call failed: …') and can decide what to do next.
    """
    data, _code, err = unwrap_full(resp, fallback)
    return data, err
