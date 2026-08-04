"""
Agent business logic service using LangChain and Gemini
"""

import logging
from dataclasses import dataclass
from typing import AsyncGenerator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from app.constants.agent import TOOL_ACTIVITY_CONFIG
from app.prompts.agent import get_system_prompt
from app.schemas.agent import (
    ActivityStatus,
    AgentStreamEvent,
    ChatHistoryMessage,
    ChatResponse,
    GeminiContentBlock,
    StreamActivityEvent,
    StreamCompleteEvent,
    StreamErrorEvent,
    StreamStatusEvent,
    StreamTokenEvent,
    StreamToolEndEvent,
    StreamToolStartEvent,
)
from app.services.appliance_service import ApplianceService
from app.services.dashboard_service import DashboardService
from app.services.tool_executor import ToolExecutor
from app.tools.agent_tools import (
    create_user_appliances_tool,
    create_user_energy_summary_tool,
    create_add_user_appliance_tool,
    create_update_user_appliance_tool,
    create_delete_user_appliance_tool,
)
from app.exceptions.agent import AgentServiceError

logger = logging.getLogger(__name__)


@dataclass
class AgentChatContext:
    """Encapsulates the state and bound model required for an agent chat session."""

    tools: list[BaseTool]
    messages: list[BaseMessage]
    model: Runnable


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

    def _build_tools(self, user_id: str) -> list[BaseTool]:
        """Build LangChain tools bound to the specified user_id context."""
        return [
            create_user_appliances_tool(user_id, self.appliance_service),
            create_user_energy_summary_tool(user_id, self.dashboard_service),
            create_add_user_appliance_tool(user_id, self.appliance_service),
            create_update_user_appliance_tool(user_id, self.appliance_service),
            create_delete_user_appliance_tool(user_id, self.appliance_service),
        ]

    @staticmethod
    def _build_initial_messages(
        user_name: str,
        user_message: str,
        history: list[ChatHistoryMessage] | None = None,
    ) -> list[BaseMessage]:
        """
        Build system prompt (always at index=0), sanitized client-provided history,
        and current user message.
        """
        system_prompt = get_system_prompt(user_name)
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

        if history:
            # 1. Sanitize first: filter out empty or whitespace-only items
            sanitized_history = [
                h for h in history if h.content and h.content.strip()
            ]
            # 2. Truncate second: keep at most the last 10 messages
            truncated_history = sanitized_history[-10:]

            for item in truncated_history:
                cleaned_text = item.content.strip()
                if item.role == "user":
                    messages.append(HumanMessage(content=cleaned_text))
                elif item.role == "assistant":
                    messages.append(AIMessage(content=cleaned_text))

        messages.append(HumanMessage(content=user_message))
        return messages

    def _prepare_context(
        self,
        user_id: str,
        user_name: str,
        user_message: str,
        history: list[ChatHistoryMessage] | None = None,
    ) -> AgentChatContext:
        """Prepare tools, messages, and tool-bound model for a chat session."""
        tools = self._build_tools(user_id)
        messages = self._build_initial_messages(user_name, user_message, history)
        bound_model = self.model.bind_tools(tools)
        return AgentChatContext(tools=tools, messages=messages, model=bound_model)

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

    @classmethod
    def _extract_chunk_text(cls, chunk: BaseMessage) -> str:
        """Extract text from a streamed LangChain message chunk."""
        if not isinstance(chunk, AIMessage):
            return ""
        return cls._extract_message_text(chunk)

    @staticmethod
    def _create_tool_activity_event(
        tool_name: str, status: ActivityStatus
    ) -> StreamActivityEvent | None:
        """Create a typed StreamActivityEvent from declarative config."""
        config = TOOL_ACTIVITY_CONFIG.get(tool_name)
        if not config:
            return None

        message = config["started"] if status == "started" else config["completed"]

        return StreamActivityEvent(
            id=config["id"],
            message=message,
            status=status,
        )

    async def chat(
        self,
        user_id: str,
        user_name: str,
        user_message: str,
        history: list[ChatHistoryMessage] | None = None,
    ) -> ChatResponse:
        """
        Process user message via LangChain and Gemini model with tools
        """
        logger.info("AgentService.chat: User Prompt: %r", user_message)

        ctx = self._prepare_context(user_id, user_name, user_message, history)
        tool_executor = ToolExecutor(ctx.tools)

        try:
            response: AIMessage = await ctx.model.ainvoke(ctx.messages)

            if response.tool_calls:
                ctx.messages.append(response)
                await tool_executor.execute(response.tool_calls, ctx.messages)
                response = await ctx.model.ainvoke(ctx.messages)

            text_content = self._extract_message_text(response)
            logger.info("AgentService.chat: Assistant Reply: %r", text_content)
            return ChatResponse(message=text_content)
        except Exception as e:
            logger.exception("Error invoking Gemini model in AgentService: %s", str(e))
            raise AgentServiceError("Failed to generate AI response.") from e

    async def stream_chat(
        self,
        user_id: str,
        user_name: str,
        user_message: str,
        history: list[ChatHistoryMessage] | None = None,
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        """
        Process user message via LangChain and Gemini model with tools, streaming typed SSE events.
        """
        logger.info("AgentService.stream_chat: User Prompt: %r", user_message)

        try:
            # Phase 1: Context Preparation & Initial UX Events
            yield StreamStatusEvent(
                status="analyzing", message="Analyzing your request..."
            )
            yield StreamActivityEvent(
                id="act-understanding",
                message="Understanding your request",
                status="started",
            )

            ctx = self._prepare_context(user_id, user_name, user_message, history)
            tool_executor = ToolExecutor(ctx.tools)
            initial_ai_message: AIMessage | None = None

            # Phase 2: First Model Turn - Stream Tokens & Capture Message Output
            async for event in ctx.model.astream_events(ctx.messages):
                if event["event"] == "on_chat_model_stream":
                    token_text = self._extract_chunk_text(event["data"]["chunk"])
                    if token_text:
                        yield StreamTokenEvent(token=token_text)
                elif event["event"] == "on_chat_model_end":
                    output = event["data"]["output"]
                    if isinstance(output, AIMessage):
                        initial_ai_message = output

            yield StreamActivityEvent(
                id="act-understanding",
                message="Understood your request",
                status="completed",
            )

            # Phase 3: Tool Execution (If Tool Calls Requested)
            has_tools = bool(initial_ai_message and initial_ai_message.tool_calls)

            if has_tools and initial_ai_message:
                yield StreamStatusEvent(
                    status="executing_tools",
                    message="Retrieving requested energy data...",
                )
                ctx.messages.append(initial_ai_message)

                tool_names = [tc["name"] for tc in initial_ai_message.tool_calls]

                for name in tool_names:
                    activity = self._create_tool_activity_event(name, "started")
                    if activity:
                        yield activity

                for tool_call in initial_ai_message.tool_calls:
                    yield StreamToolStartEvent(tool_name=tool_call["name"])

                await tool_executor.execute(initial_ai_message.tool_calls, ctx.messages)

                for tool_call in initial_ai_message.tool_calls:
                    yield StreamToolEndEvent(tool_name=tool_call["name"])

                for name in tool_names:
                    activity = self._create_tool_activity_event(name, "completed")
                    if activity:
                        yield activity

            # Phase 4: Final Model Turn & Stream Generation
            if has_tools:
                async for event in ctx.model.astream_events(ctx.messages, version="v2"):
                    if event["event"] == "on_chat_model_stream":
                        token_text = self._extract_chunk_text(event["data"]["chunk"])
                        if token_text:
                            yield StreamTokenEvent(token=token_text)

            # Phase 5: Stream Complete
            yield StreamCompleteEvent()

        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Error in stream_chat: %s", str(e))
            yield StreamErrorEvent(
                error="Failed to generate AI response. Please try again later."
            )
