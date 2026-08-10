"""
ToolExecutor service for executing and deduplicating LangChain tools.
"""

from dataclasses import dataclass
from typing import Any
from langchain_core.messages import BaseMessage, ToolCall, ToolMessage
from langchain_core.tools import BaseTool

from app.exceptions.agent import AgentServiceError
from app.schemas.agent import (
    AgentToolResult,
    ApplianceDeletePayload,
    SearchResultsResponse,
)
from app.schemas.energy import ApplianceResponse, EnergySummaryResponse

ToolResultPayload = (
    list[ApplianceResponse]
    | AgentToolResult[ApplianceResponse]
    | AgentToolResult[ApplianceDeletePayload]
    | AgentToolResult[SearchResultsResponse]
    | EnergySummaryResponse
)


@dataclass
class ExecutedToolResult:
    """
    Structured representation of an executed tool call.
    """

    tool_call_id: str
    tool_name: str
    tool_args: dict[str, Any]
    raw_result: ToolResultPayload | None
    success: bool
    error_message: str | None
    tool_message: ToolMessage


class ToolExecutor:
    """
    Lightweight executor for looking up, deduplicating, and executing LangChain tools.
    """

    def __init__(self, tools: list[BaseTool]):
        self.tools_by_name: dict[str, BaseTool] = {tool.name: tool for tool in tools}

    async def execute(
        self, tool_calls: list[ToolCall], messages: list[BaseMessage]
    ) -> list[ExecutedToolResult]:
        """
        Execute requested tools, append ToolMessages to messages, and return
        typed ExecutedToolResult list. Deduplicates identical tool calls within
        the same model response turn.
        """
        executed_results: dict[tuple[str, str], ExecutedToolResult] = {}
        results: list[ExecutedToolResult] = []

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})

            tool_id = tool_call.get("id")
            if tool_id is None:
                raise AgentServiceError("Tool call missing ID.")

            selected_tool = self.tools_by_name.get(tool_name)
            if selected_tool is None:
                continue

            cache_key = (tool_name, str(sorted(tool_args.items())))

            if cache_key in executed_results:
                cached = executed_results[cache_key]
                tool_message = ToolMessage(
                    content=cached.tool_message.content,
                    tool_call_id=tool_id,
                )
                messages.append(tool_message)
                results.append(
                    ExecutedToolResult(
                        tool_call_id=tool_id,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        raw_result=cached.raw_result,
                        success=cached.success,
                        error_message=cached.error_message,
                        tool_message=tool_message,
                    )
                )
                continue

            raw_result: ToolResultPayload | None = None
            success = False
            error_message: str | None = None

            try:
                raw_result = await selected_tool.ainvoke(tool_args)

                if isinstance(raw_result, AgentToolResult):
                    success = raw_result.success
                    error_message = raw_result.message if not success else None
                else:
                    success = True
                    error_message = None

                tool_msg_content = str(raw_result)
            except Exception as e:  # pylint: disable=broad-except
                raw_result = None
                success = False
                error_message = str(e)
                tool_msg_content = f"Error executing tool '{tool_name}': {e}"

            tool_message = ToolMessage(
                content=tool_msg_content,
                tool_call_id=tool_id,
            )

            messages.append(tool_message)

            exec_res = ExecutedToolResult(
                tool_call_id=tool_id,
                tool_name=tool_name,
                tool_args=tool_args,
                raw_result=raw_result,
                success=success,
                error_message=error_message,
                tool_message=tool_message,
            )
            executed_results[cache_key] = exec_res
            results.append(exec_res)

        return results
