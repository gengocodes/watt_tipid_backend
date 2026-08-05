"""
Web search integration service using DuckDuckGo Search.
"""

import asyncio
import logging
from ddgs import DDGS

from app.schemas.agent import (
    AgentToolResult,
    SearchResultItem,
    SearchResultsResponse,
)

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Service for executing external web searches via DuckDuckGo Search.
    """

    @staticmethod
    def _perform_ddg_search(query: str, max_results: int) -> list[SearchResultItem]:
        """
        Synchronous search invocation using DDGS.
        """
        items: list[SearchResultItem] = []
        with DDGS() as ddgs:
            raw_results = ddgs.text(query, max_results=max_results)
            for raw in raw_results:
                title = str(raw.get("title", "")).strip()
                url = str(raw.get("href", "")).strip()
                raw_snippet = str(raw.get("body", "")).strip()

                # Prune snippet length to 180 characters max to optimize LLM context & token cost
                snippet = (
                    raw_snippet[:180].strip() + "..."
                    if len(raw_snippet) > 180
                    else raw_snippet
                )

                if title or url or snippet:
                    items.append(
                        SearchResultItem(
                            title=title,
                            url=url,
                            snippet=snippet,
                        )
                    )
        return items

    async def search(
        self, query: str, max_results: int = 3
    ) -> AgentToolResult[SearchResultsResponse]:
        """
        Search the web for information using DuckDuckGo with query fallback.

        Args:
            query: Non-empty search query string.
            max_results: Maximum number of search results to return (1-4).

        Returns:
            AgentToolResult containing SearchResultsResponse on success or failure message.
        """
        sanitized_query = query.strip() if query else ""
        if not sanitized_query:
            return AgentToolResult[SearchResultsResponse](
                success=False,
                message="Search query cannot be empty.",
                data=None,
            )

        clamped_max_results = max(1, min(max_results, 4))

        logger.info(
            "Executing web search for query: %r (max_results=%d)",
            sanitized_query,
            clamped_max_results,
        )

        try:
            # Primary search attempt
            items = await asyncio.to_thread(
                self._perform_ddg_search, sanitized_query, clamped_max_results
            )

            # Fallback search attempt if primary returned empty results and query has > 5 words
            words = sanitized_query.split()
            if not items and len(words) > 5:
                simplified_query = " ".join(words[:5])
                logger.info(
                    "Primary search returned empty results; trying simplified fallback query: %r",
                    simplified_query,
                )
                items = await asyncio.to_thread(
                    self._perform_ddg_search, simplified_query, clamped_max_results
                )

            payload = SearchResultsResponse(query=sanitized_query, results=items)

            if not items:
                logger.info(
                    "Web search returned no results for query: %r", sanitized_query
                )
                return AgentToolResult[SearchResultsResponse](
                    success=True,
                    message=f"No web search results found for query '{sanitized_query}'.",
                    data=payload,
                )

            logger.info(
                "Web search returned %d items for query: %r",
                len(items),
                sanitized_query,
            )
            return AgentToolResult[SearchResultsResponse](
                success=True,
                message=f"Successfully retrieved {len(items)} web search "
                "results for query '{sanitized_query}'.",
                data=payload,
            )

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Web search failed for query %r: %s", sanitized_query, str(e)
            )
            return AgentToolResult[SearchResultsResponse](
                success=False,
                message=f"Web search failed: {str(e)}",
                data=None,
            )
