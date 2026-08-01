"""
Agent business logic service using LangChain and Gemini
"""

import logging
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    ToolCall,
)
from langchain_core.tools import BaseTool

from app.prompts.agent import get_system_prompt
from app.schemas.agent import ChatResponse, GeminiContentBlock
from app.services.appliance_service import ApplianceService
from app.services.dashboard_service import DashboardService
from app.tools.agent_tools import (
    create_user_appliances_tool,
    create_user_energy_summary_tool,
)

logger = logging.getLogger(__name__)


class AgentServiceError(Exception):
    """Application-level exception raised when AgentService encounters an execution error."""


class AgentService:
    """
    Agent business logic service using LangChain and Gemini
    """

    def __init__(
        self,
        model: BaseChatModel,
        appliance_service: ApplianceService,
        dashboard_service: DashboardService,
    ):
        self.model = model
        self.appliance_service = appliance_service
        self.dashboard_service = dashboard_service

    @staticmethod
    def _extract_message_text(message: AIMessage) -> str:
        """
        Extract text content from LangChain AIMessage.
        """
        content = message.content

        if isinstance(content, str):
            return content

        parts: list[str] = []

        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue

            block = GeminiContentBlock.model_validate(part)

            parts.append(block.text)

        return "".join(parts)

    @staticmethod
    async def _execute_tool_calls(
        tool_calls: list[ToolCall],
        tools: list[BaseTool],
        messages: list[BaseMessage],
    ) -> None:
        """
        Execute requested LangChain tools and append their results as ToolMessages.

        Deduplicates identical tool calls within the same model response so that
        the same tool is only executed once while still returning a ToolMessage
        for every original tool_call_id required by the model.
        """
        tools_by_name: dict[str, BaseTool] = {tool.name: tool for tool in tools}

        executed_results: dict[tuple[str, str], str] = {}

        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            tool_id = tool_call.get("id")
            if tool_id is None:
                raise AgentServiceError("Tool call missing ID.")

            selected_tool = tools_by_name.get(tool_name)

            if selected_tool is None:
                continue

            cache_key = (
                tool_name,
                str(sorted(tool_args.items())),
            )

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

    async def chat(
        self, user_id: str, user_name: str, user_message: str
    ) -> ChatResponse:
        """
        Process user message via LangChain and Gemini model with tools
        """
        # NOTE / TODO: Remove logs soon
        logger.info("AgentService.chat: User Prompt: %r", user_message)

        system_prompt = get_system_prompt(user_name)
        tools = [
            create_user_appliances_tool(user_id, self.appliance_service),
            create_user_energy_summary_tool(user_id, self.dashboard_service),
        ]

        model_with_tools = self.model.bind_tools(tools)
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        try:
            response: AIMessage = await model_with_tools.ainvoke(messages)

            # Handle LLM-requested tool calls: execute requested tools, reuse duplicate
            # results within the same turn, then send tool outputs back to the model
            # so it can generate a final response using the retrieved user data.
            if response.tool_calls:
                messages.append(response)

                await self._execute_tool_calls(response.tool_calls, tools, messages)

                response = await model_with_tools.ainvoke(messages)

            text_content = self._extract_message_text(response)
            logger.info("AgentService.chat: Assistant Reply: %r", text_content)
            return ChatResponse(message=text_content)
        except Exception as e:
            logger.exception("Error invoking Gemini model in AgentService: %s", str(e))
            raise AgentServiceError("Failed to generate AI response.") from e
