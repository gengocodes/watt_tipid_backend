"""
Unit tests for WebSearchService and create_web_search_tool
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.schemas.agent import (
    AgentToolResult,
    SearchResultItem,
    SearchResultsResponse,
)
from app.services.web_search_service import WebSearchService
from app.tools.agent_tools import create_web_search_tool


@pytest.mark.anyio
async def test_web_search_service_success():
    """
    Test WebSearchService returning structured SearchResultsResponse on success.
    """
    service = WebSearchService()
    mock_raw_results = [
        SearchResultItem(
            title="Inverter Air Conditioner Power Consumption",
            url="https://example.com/inverter-ac",
            snippet="Inverter ACs save up to 50% energy compared to non-inverters.",
        )
    ]

    with patch.object(
        service, "_perform_ddg_search", return_value=mock_raw_results
    ) as mock_ddg:
        result = await service.search("inverter air conditioner wattage", max_results=3)

        assert isinstance(result, AgentToolResult)
        assert result.success is True
        assert "Successfully retrieved 1 web search results" in result.message
        assert isinstance(result.data, SearchResultsResponse)
        assert result.data.query == "inverter air conditioner wattage"
        assert len(result.data.results) == 1
        assert (
            result.data.results[0].title == "Inverter Air Conditioner Power Consumption"
        )
        assert result.data.results[0].url == "https://example.com/inverter-ac"
        assert "save up to 50% energy" in result.data.results[0].snippet
        mock_ddg.assert_called_once_with("inverter air conditioner wattage", 3)


@pytest.mark.anyio
async def test_web_search_service_empty_query():
    """
    Test WebSearchService handling empty or whitespace queries cleanly.
    """
    service = WebSearchService()

    result = await service.search("   ")

    assert isinstance(result, AgentToolResult)
    assert result.success is False
    assert result.message == "Search query cannot be empty."
    assert result.data is None


@pytest.mark.anyio
async def test_web_search_service_no_results():
    """
    Test WebSearchService handling empty search result lists.
    """
    service = WebSearchService()

    with patch.object(service, "_perform_ddg_search", return_value=[]):
        result = await service.search("nonexistent query xyz123")

        assert isinstance(result, AgentToolResult)
        assert result.success is True
        assert "No web search results found" in result.message
        assert isinstance(result.data, SearchResultsResponse)
        assert len(result.data.results) == 0


@pytest.mark.anyio
async def test_web_search_service_exception_handling():
    """
    Test WebSearchService handling DuckDuckGo search exceptions gracefully.
    """
    service = WebSearchService()

    with patch.object(
        service, "_perform_ddg_search", side_effect=Exception("DDG rate limit exceeded")
    ):
        result = await service.search("refrigerator power efficiency")

        assert isinstance(result, AgentToolResult)
        assert result.success is False
        assert "Web search failed: DDG rate limit exceeded" in result.message
        assert result.data is None


@pytest.mark.anyio
async def test_create_web_search_tool_invocation():
    """
    Test invoking the tool created by create_web_search_tool factory.
    """
    mock_service = MagicMock()
    expected_response = AgentToolResult[SearchResultsResponse](
        success=True,
        message="Found 1 result",
        data=SearchResultsResponse(query="solar panel", results=[]),
    )
    mock_service.search = AsyncMock(return_value=expected_response)

    tool = create_web_search_tool(mock_service)
    assert tool.name == "web_search"

    result = await tool.ainvoke({"query": "solar panel"})

    assert isinstance(result, AgentToolResult)
    assert result.success is True
    mock_service.search.assert_called_once_with("solar panel")
