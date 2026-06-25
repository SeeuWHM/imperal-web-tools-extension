"""web-tools · Web research handlers — search + 3 readers + read policy (SDK 5.x / SDL).

Two-layer design: the backend is a dumb fetcher, the LLM is the orchestrator. Three readers,
cheapest first:
  • read_url          — fast, no-JS reader (always try this first).
  • read_url_rendered — headless-Chromium render for JS / bot-protected pages.  ⚠️ TOKEN-HEAVY
  • read_document     — Office docs (.docx/.xlsx/.pptx) → Markdown.               ⚠️ TOKEN-HEAVY

When read_url fails on a page the heavy readers COULD open, the user's standing read policy decides:
  • ask (default) — read_url returns an escalation FACT; Webby surfaces what it found and asks first.
  • always        — read_url escalates to the right heavy reader itself (deterministic, no re-ask).
  • never_heavy   — read_url reports unreadable; Webby uses what search already gave it.
The policy is stored per-user in `wt_prefs` and set via set_web_read_policy.

Sibling imports are bound at MODULE LOAD time (kernel I-EXT-MODULE-ISOLATION — see handlers_diag.py).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from backend import unwrap, unwrap_full
from schemas_sdl_builders import (
    SearchResultList, PageContent, WtOpResult,
    build_search_result_list, build_page_content, build_wt_op,
)

# Cheap-read failure codes that a heavier reader could still open.
_RENDER_CODES = {"CHALLENGE_BLOCKED", "UPSTREAM_HTTP_ERROR", "EXTRACTION_EMPTY"}
_OFFICE_EXT = (".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt")

_READ_POLICIES = ("ask", "always", "never_heavy")
_DEFAULT_POLICY = "ask"

_RENDER_PATH = "/v1/read_rendered"
_DOCUMENT_PATH = "/v1/read_document"


# ─── Helpers ──────────────────────────────────────────────────────────────── #

def _is_office_url(url: str) -> bool:
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    return path.endswith(_OFFICE_EXT)


def _escalation_target(code: str | None, url: str) -> str | None:
    """Map a cheap-read failure to a heavy reader: 'rendered' | 'document' | None."""
    if code == "UNSUPPORTED_CONTENT_TYPE" and _is_office_url(url):
        return "document"
    if code in _RENDER_CODES:
        return "rendered"
    return None


async def _post_read(ctx, path: str, url: str, max_tokens: int,
                     query: str | None, mode: str, timeout: int):
    resp = await ctx.http.post(
        f"{WEB_TOOLS_URL}{path}",
        json={"url": url, "max_tokens": max_tokens, "query": query, "mode": mode},
        timeout=timeout,
    )
    return unwrap_full(resp, f"Could not read {url}")


def _ok(data: dict, url: str, note: str | None = None) -> ActionResult:
    title = data.get("title") or url
    summary = f"Read “{title}” ({data.get('token_count', 0)} tokens)"
    if note:
        summary += f" {note}"
    return ActionResult.success(data=build_page_content(data), summary=summary)


async def _get_read_policy(ctx) -> str:
    try:
        page = await ctx.store.query("wt_prefs", where={"owner_id": ctx.user.imperal_id}, limit=1)
    except Exception:
        return _DEFAULT_POLICY
    if page.data:
        pol = page.data[0].data.get("web_read_policy")
        if pol in _READ_POLICIES:
            return pol
    return _DEFAULT_POLICY


async def _heavy_read(ctx, path: str, params: "ReadUrlParams") -> ActionResult:
    try:
        data, _code, err = await _post_read(
            ctx, path, params.url, params.max_tokens, params.query, params.mode, 60)
    except Exception as exc:
        return ActionResult.error(
            f"The heavy reader could not reach {params.url} ({exc}). Try the next result.", retryable=True)
    if err:
        return ActionResult.error(f"{err}. Try the next result.", retryable=True)
    return _ok(data, params.url)


# ─── Web search ───────────────────────────────────────────────────────────── #

class WebSearchParams(BaseModel):
    """Web search parameters."""
    query: str = Field(..., min_length=1, description="Search query in natural language.")
    num_results: int = Field(default=10, ge=1, le=50, description="How many candidate results to return.")
    include_domains: list[str] | None = Field(
        default=None, description="Restrict results to these domains (e.g. ['docs.python.org']).")
    recency_days: int | None = Field(
        default=None, ge=1, le=3650,
        description="Only results published within the last N days. REQUIRED for 'today'/'latest'/'recent' "
                    "queries — Exa ranking alone is NOT recency-sorted.")
    type: Literal["auto", "fast", "instant", "deep-lite"] = Field(
        default="auto", description="Exa search type — leave 'auto' unless you need speed (fast/instant).")
    category: Literal["news", "research paper", "company", "pdf", "github", "tweet",
                      "personal site", "linkedin profile", "financial report"] | None = Field(
        default=None, description="Bias results toward a content category when the query clearly targets one.")


@chat.function("web_search", action_type="read",
               data_model=SearchResultList,
               description="WEB SEARCH — find pages for a query. FIRST step of any web research: returns "
                           "candidate cards (url, title, snippet, score) but does NOT read page content. The "
                           "`snippet` is an LLM-ready excerpt and is OFTEN ENOUGH to answer — read pages only "
                           "when you need more. Then read just the 2–3 BEST urls (not all results). For "
                           "'today'/'latest'/'recent' queries you MUST pass recency_days (ranking isn't "
                           "recency-sorted). Use include_domains to focus a site, category to bias content type. "
                           "Re-run with new wording if results are thin. NOT for diagnosing a domain you own "
                           "— that's domain_full_check / dns_lookup / etc.")
async def fn_web_search(ctx, params: WebSearchParams) -> ActionResult:
    """Web search — returns candidate cards for the LLM to choose from."""
    resp = await ctx.http.post(
        f"{WEB_TOOLS_URL}/v1/search",
        json={"query": params.query, "num_results": params.num_results,
              "include_domains": params.include_domains, "recency_days": params.recency_days,
              "type": params.type, "category": params.category},
        timeout=30,
    )
    data, err = unwrap(resp, "Web search failed")
    if err:
        return ActionResult.error(err, retryable=True)
    return ActionResult.success(
        data=build_search_result_list(data),
        summary=f"{data.get('count', 0)} result(s) for “{params.query}”",
    )


# ─── Readers ──────────────────────────────────────────────────────────────── #

class ReadUrlParams(BaseModel):
    """Read-one-page parameters."""
    url: str = Field(..., min_length=1, description="URL to read (http/https).")
    max_tokens: int = Field(default=8000, ge=200, le=32000,
                            description="Token budget for the extracted content.")
    query: str | None = Field(default=None,
                              description="Optional: focus extraction/truncation on this question.")
    mode: Literal["full", "main", "outline", "tables", "metadata"] = Field(
        default="full",
        description="TOKEN ECONOMY — what to return. full=whole page (expensive); main=prose only; "
                    "outline=heading tree (~100 tok, 'which section?'); tables=only tables (price/data pages); "
                    "metadata=no body (~0 tok, 'is it worth reading?'). Triage with metadata/outline FIRST, "
                    "then full/tables on the winner.")


@chat.function("read_url", action_type="read",
               data_model=PageContent,
               description="READ ONE web page into clean Markdown — the cheap, default reader; ALWAYS try this "
                           "before the heavy readers. TOKEN ECONOMY via `mode`: triage with mode='metadata' "
                           "(~0 tok: worth reading?) or mode='outline' (~100 tok: which section?) BEFORE pulling "
                           "mode='full'; use mode='tables' for price/data pages. Each result includes "
                           "`content_hash` — if you already read identical content this conversation, DON'T "
                           "re-read it, refer to what you have (two urls can share a hash). Also returns `outline` "
                           "and structured `tables` — use those, don't parse tables out of the text. If it errors, "
                           "read the NEXT candidate — one dead page must not end the task. If a page is blocked "
                           "(JS/bot-protection) or is an Office doc, this returns a note pointing to the "
                           "TOKEN-HEAVY read_url_rendered / read_document tools: tell the user what you already "
                           "found and ask before spending tokens (unless the read policy is 'always' — then it "
                           "auto-reads).")
async def fn_read_url(ctx, params: ReadUrlParams) -> ActionResult:
    """Cheap reader; a blocked/heavy page becomes an escalation FACT (or auto-reads under 'always')."""
    try:
        data, code, err = await _post_read(
            ctx, "/v1/read", params.url, params.max_tokens, params.query, params.mode, 40)
    except Exception as exc:
        return ActionResult.error(
            f"Could not reach the reader for {params.url} ({exc}). Try the next result.", retryable=True)
    if not err:
        return _ok(data, params.url)

    target = _escalation_target(code, params.url)
    if not target:                                   # rendering won't help (robots/timeout/too-large/…)
        return ActionResult.error(f"{err}. Try the next result.", retryable=True)

    policy = await _get_read_policy(ctx)
    if policy == "never_heavy":
        return ActionResult.error(
            f"{err}. A heavy reader could open this, but your read policy is 'never_heavy' — "
            f"use what search already returned.", retryable=True)

    if policy == "always":                           # deterministic auto-escalation — no re-ask
        path = _RENDER_PATH if target == "rendered" else _DOCUMENT_PATH
        try:
            hdata, _hc, herr = await _post_read(
                ctx, path, params.url, params.max_tokens, params.query, params.mode, 60)
        except Exception as exc:
            return ActionResult.error(
                f"The heavy reader could not reach {params.url} ({exc}). Try the next result.", retryable=True)
        if herr:
            return ActionResult.error(
                f"Even the heavy reader could not read {params.url}: {herr}. Try the next result.", retryable=True)
        note = "(auto-rendered via headless Chromium" if target == "rendered" \
            else "(auto-read as an Office document"
        return _ok(hdata, params.url, note=f"{note} per your always-read policy)")

    # policy == 'ask' (default): emit an escalation FACT; Webby surfaces findings and asks first.
    tool = "read_url_rendered" if target == "rendered" else "read_document"
    what = "is behind JavaScript / bot-protection" if target == "rendered" else "is an Office document"
    return ActionResult.error(
        f"{params.url} {what} — the basic reader can't open it. The TOKEN-HEAVY `{tool}` tool can, but it "
        f"costs extra tokens. Tell the user what you already found and ask whether to spend tokens reading "
        f"this page (they can say “always read” to skip this question from now on).", retryable=True)


@chat.function("read_url_rendered", action_type="read",
               data_model=PageContent,
               description="⚠️ TOKEN-HEAVY, on-demand. Read a page in a real headless Chromium browser — for "
                           "pages the normal read_url could NOT open because they need JavaScript or are behind "
                           "bot-protection (read_url returned CHALLENGE_BLOCKED / 403 / empty). Slow and consumes "
                           "many tokens. Use ONLY for an IMPORTANT page AFTER read_url failed, and prefer to ask "
                           "the user first unless they set the read policy to 'always'. Never use as the first "
                           "reader — always try read_url first.")
async def fn_read_url_rendered(ctx, params: ReadUrlParams) -> ActionResult:
    """Headless-Chromium render of a JS / bot-protected page (heavy)."""
    return await _heavy_read(ctx, _RENDER_PATH, params)


@chat.function("read_document", action_type="read",
               data_model=PageContent,
               description="⚠️ TOKEN-HEAVY, on-demand. Read an Office document (.docx / .xlsx / .pptx) at a URL "
                           "into Markdown. Use ONLY when the url points to such a document (read_url returns "
                           "UNSUPPORTED_CONTENT_TYPE for these). Large spreadsheets/decks consume many tokens — "
                           "prefer to ask the user first unless the read policy is 'always'. Not for normal web "
                           "pages (use read_url) or PDFs (read_url already handles PDF).")
async def fn_read_document(ctx, params: ReadUrlParams) -> ActionResult:
    """Office document (.docx/.xlsx/.pptx) → Markdown (heavy)."""
    return await _heavy_read(ctx, _DOCUMENT_PATH, params)


# ─── Read policy ──────────────────────────────────────────────────────────── #

class ReadPolicyParams(BaseModel):
    """Web read policy parameters."""
    policy: Literal["ask", "always", "never_heavy"] = Field(
        ..., description="ask=warn+ask before heavy reads (default); always=auto-read blocked/Office pages; "
                         "never_heavy=never use the heavy readers.")


@chat.function("set_web_read_policy", action_type="write", event="web_read_policy.changed",
               effects=["update:web_read_policy"],
               data_model=WtOpResult,
               description="Set the user's standing policy for the TOKEN-HEAVY web readers (read_url_rendered / "
                           "read_document). Call when the user expresses a preference: 'читай всегда' / 'always "
                           "read' / 'don't ask just read' → 'always'; 'не читай тяжёлое' / 'stop reading heavy "
                           "pages' → 'never_heavy'; 'ask me first' → 'ask'. Persists per-user across sessions.")
async def fn_set_web_read_policy(ctx, params: ReadPolicyParams) -> ActionResult:
    """Persist the per-user web read policy in wt_prefs."""
    page = await ctx.store.query("wt_prefs", where={"owner_id": ctx.user.imperal_id}, limit=1)
    doc = {"owner_id": ctx.user.imperal_id, "web_read_policy": params.policy}
    if page.data:
        await ctx.store.update("wt_prefs", page.data[0].id, doc)
    else:
        await ctx.store.create("wt_prefs", doc)
    label = {"ask": "ask before heavy reads",
             "always": "always read (auto-escalate to heavy readers)",
             "never_heavy": "never use heavy readers"}[params.policy]
    return ActionResult.success(
        data=build_wt_op("web_read_policy", f"Web read policy: {label}"),
        summary=f"Web read policy set to “{params.policy}”.",
    )
