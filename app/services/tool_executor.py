"""
ToolExecutor service for executing and deduplicating LangChain tools.
"""

from langchain_core.messages import BaseMessage, ToolCall, ToolMessage
from langchain_core.tools import BaseTool

from app.exceptions.agent import AgentServiceError


class ToolExecutor:
    """
    Lightweight executor for looking up, deduplicating, and executing LangChain tools.
    """

    def __init__(self, tools: list[BaseTool]):
        self.tools_by_name: dict[str, BaseTool] = {tool.name: tool for tool in tools}

    async def execute(
        self, tool_calls: list[ToolCall], messages: list[BaseMessage]
    ) -> None:
        """
        Execute requested tools and append ToolMessages to messages.

        Deduplicates identical tool calls within the same model response turn.
        """
        executed_results: dict[tuple[str, str], str] = {}

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            tool_id = tool_call.get("id")
            if tool_id is None:
                raise AgentServiceError("Tool call missing ID.")

            selected_tool = self.tools_by_name.get(tool_name)
            if selected_tool is None:
                continue

            cache_key = (tool_name, str(sorted(tool_args.items())))

            if cache_key not in executed_results:
                executed_results[cache_key] = str(
                    await selected_tool.ainvoke(tool_args)
                )

            messages.append(
                ToolMessage(
                    content=executed_results[cache_key],
                    tool_call_id=tool_id,
                )
            )
