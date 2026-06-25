"""web-tools · Web research handlers — web_search + read_url (SDK 5.x / SDL).

Two-layer design: the backend is a dumb fetcher (search returns candidate cards,
read returns ONE clean page or a typed error), the LLM is the orchestrator. The
resilience loop ('a page errored → read the next one') lives in the LLM, driven by
retryable error FACTS — never by backend-side fallback. read_url therefore NEVER
raises on a dead page: it returns ActionResult.error(retryable=True) so the turn
survives and the model can pick the next result.

Sibling imports are bound at MODULE LOAD time (kernel I-EXT-MODULE-ISOLATION — see
handlers_diag.py header for why a call-time `from app import …` would mis-resolve).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app import chat, WEB_TOOLS_URL
from imperal_sdk import ActionResult
from backend import unwrap
from schemas_sdl_builders import (
    SearchResultList, PageContent,
    build_search_result_list, build_page_content,
)


# ─── Web search ───────────────────────────────────────────────────────────── #

class WebSearchParams(BaseModel):
    """Web search parameters."""
    query: str = Field(..., min_length=1, description="Search query in natural language.")
    num_results: int = Field(default=10, ge=1, le=50, description="How many candidate results to return.")
    include_domains: list[str] | None = Field(
        default=None, description="Restrict results to these domains (e.g. ['docs.python.org']).")


@chat.function("web_search", action_type="read",
               data_model=SearchResultList,
               description="WEB SEARCH — find pages for a query. FIRST step of any web research: returns "
                           "candidate cards (url, title, snippet, score) but does NOT read page content. "
                           "Inspect the cards, pick the relevant url(s), then call read_url on them. Run "
                           "web_search again with a different phrasing if the first results are thin. Use "
                           "include_domains to focus on a specific site. NOT for diagnosing a domain you own "
                           "— that's domain_full_check / dns_lookup / etc.")
async def fn_web_search(ctx, params: WebSearchParams) -> ActionResult:
    """Web search — returns candidate cards for the LLM to choose from."""
    resp = await ctx.http.post(
        f"{WEB_TOOLS_URL}/v1/search",
        json={"query": params.query, "num_results": params.num_results,
              "include_domains": params.include_domains},
        timeout=30,
    )
    data, err = unwrap(resp, "Web search failed")
    if err:
        return ActionResult.error(err, retryable=True)
    count = data.get("count", 0)
    return ActionResult.success(
        data=build_search_result_list(data),
        summary=f"{count} result(s) for “{params.query}”",
    )


# ─── Read URL ─────────────────────────────────────────────────────────────── #

class ReadUrlParams(BaseModel):
    """Read-one-page parameters."""
    url: str = Field(..., min_length=1, description="URL to read (http/https).")
    max_tokens: int = Field(default=8000, ge=200, le=32000,
                            description="Token budget for the extracted content.")


@chat.function("read_url", action_type="read",
               data_model=PageContent,
               description="READ ONE web page into clean Markdown — the second step of web research, after "
                           "web_search. Returns extracted text + metadata (title, source, lang, token_count). "
                           "CRITICAL: if this returns an error for a url, DO NOT abandon the research — call "
                           "read_url again on the NEXT candidate from web_search. One dead or blocked page "
                           "must never end the task. Read several pages when one source is not enough.")
async def fn_read_url(ctx, params: ReadUrlParams) -> ActionResult:
    """Read one page → clean Markdown; a failed page is a retryable fact, not a crash."""
    try:
        resp = await ctx.http.post(
            f"{WEB_TOOLS_URL}/v1/read",
            json={"url": params.url, "max_tokens": params.max_tokens},
            timeout=40,
        )
    except Exception as exc:
        return ActionResult.error(
            f"Could not reach the reader for {params.url} ({exc}). Try the next result.",
            retryable=True,
        )
    data, err = unwrap(resp, f"Could not read {params.url}")
    if err:
        return ActionResult.error(f"{err}. Try the next result.", retryable=True)
    title = data.get("title") or params.url
    return ActionResult.success(
        data=build_page_content(data),
        summary=f"Read “{title}” ({data.get('token_count', 0)} tokens)",
    )
