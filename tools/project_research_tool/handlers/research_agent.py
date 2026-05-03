"""Web research agent using the Anthropic API with the web_search tool."""
import logging
from typing import Any, Dict, List

import anthropic

from config import config
from prompts.research_templates import build_research_prompt

logger = logging.getLogger(__name__)

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 4096


def run(
    project_name: str,
    project_id: str,
    municipality: str,
    state: str,
) -> Dict[str, Any]:
    """Run web research for the project using Claude with the web_search tool.

    Args:
        project_name: Human-readable project name.
        project_id: Project UUID.
        municipality: Resolved municipality name (from municipalities_new).
        state: Resolved state name.

    Returns:
        {
            "status": "success" | "error",
            "summary": str,
            "sources": [{"url": str, "title": str, "relevance_note": str}],
            "full_response": str,
            "source_count": int
        }
    """
    if not config.ANTHROPIC_API_KEY:
        logger.warning("[Research] ANTHROPIC_API_KEY not set — skipping")
        return {"status": "not_implemented", "summary": "", "sources": [], "full_response": "", "source_count": 0}

    logger.info(f"[Research] Web research: {project_name} ({project_id})")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = build_research_prompt(project_name, project_id, municipality or "", state or "")

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )

        full_text = _extract_text(response)
        sources = _extract_sources(response)
        summary = _make_summary(full_text)

        logger.info(f"[Research] Found {len(sources)} sources")
        return {
            "status": "success",
            "summary": summary,
            "sources": sources,
            "full_response": full_text,
            "source_count": len(sources),
        }

    except anthropic.APIError as e:
        logger.error(f"[Research] ERROR: {e}")
        return {
            "status": "error",
            "message": str(e),
            "summary": "",
            "sources": [],
            "full_response": "",
            "source_count": 0,
        }


def _extract_text(response) -> str:
    """Concatenate all text content blocks from the response."""
    return "\n\n".join(
        block.text for block in response.content if hasattr(block, "text")
    )


def _extract_sources(response) -> List[Dict[str, str]]:
    """Extract URLs from tool_result blocks (web_search results) and text citations."""
    sources: List[Dict[str, str]] = []

    for block in response.content:
        # Citations attached to text blocks (Anthropic citations API)
        if hasattr(block, "citations"):
            for citation in block.citations:
                sources.append({
                    "url": getattr(citation, "url", ""),
                    "title": getattr(citation, "title", ""),
                    "relevance_note": "",
                })
        # Tool result blocks contain raw search results
        if getattr(block, "type", None) == "tool_result":
            content = getattr(block, "content", [])
            if isinstance(content, list):
                for item in content:
                    url = getattr(item, "url", "") or (item.get("url", "") if isinstance(item, dict) else "")
                    title = getattr(item, "title", "") or (item.get("title", "") if isinstance(item, dict) else "")
                    if url:
                        sources.append({"url": url, "title": title, "relevance_note": ""})

    # Deduplicate by URL
    seen: set = set()
    unique: List[Dict[str, str]] = []
    for s in sources:
        if s["url"] and s["url"] not in seen:
            seen.add(s["url"])
            unique.append(s)
    return unique


def _make_summary(full_text: str, max_chars: int = 600) -> str:
    """Return the first ~600 chars of the response as a summary paragraph."""
    if len(full_text) <= max_chars:
        return full_text
    cutoff = full_text.rfind(" ", 0, max_chars)
    return (full_text[:cutoff] if cutoff > 0 else full_text[:max_chars]) + "…"