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
    ToolCall,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import ValidationError

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
    WebSearchToolArgs,
)
from app.services.appliance_service import ApplianceService
from app.services.dashboard_service import DashboardService
from app.services.web_search_service import WebSearchService
from app.services.tool_executor import ToolExecutor
from app.tools.agent_tools import (
    create_user_appliances_tool,
    create_user_energy_summary_tool,
    create_add_user_appliance_tool,
    create_update_user_appliance_tool,
    create_delete_user_appliance_tool,
    create_web_search_tool,
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
        web_search_service: WebSearchService,
    ):
        self.model = model
        self.appliance_service = appliance_service
        self.dashboard_service = dashboard_service
        self.web_search_service = web_search_service

    def _build_tools(self, user_id: str) -> list[BaseTool]:
        """Build LangChain tools bound to the specified user_id context."""
        return [
            create_user_appliances_tool(user_id, self.appliance_service),
            create_user_energy_summary_tool(user_id, self.dashboard_service),
            create_add_user_appliance_tool(user_id, self.appliance_service),
            create_update_user_appliance_tool(user_id, self.appliance_service),
            create_delete_user_appliance_tool(user_id, self.appliance_service),
            create_web_search_tool(self.web_search_service),
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
            sanitized_history = [h for h in history if h.content and h.content.strip()]
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
    def _parse_search_args(tool_call: ToolCall) -> WebSearchToolArgs | None:
        """Helper to validate WebSearchToolArgs if tool_call is web_search."""
        if tool_call.get("name") == "web_search" and tool_call.get("args"):
            try:
                return WebSearchToolArgs.model_validate(tool_call["args"])
            except ValidationError:
                pass
        return None

    @staticmethod
    def _create_tool_activity_event(
        tool_name: str,
        status: ActivityStatus,
        search_args: WebSearchToolArgs | None = None,
    ) -> StreamActivityEvent | None:
        """Create a typed StreamActivityEvent from declarative config."""
        config = TOOL_ACTIVITY_CONFIG.get(tool_name)
        if not config:
            return None

        if tool_name == "web_search" and search_args:
            message = (
                f'Searching: "{search_args.query}"'
                if status == "started"
                else f'Found search results for: "{search_args.query}"'
            )
        else:
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
        max_tool_turns = 5

        try:
            response: AIMessage | None = None

            has_finished_text_turn = False
            for _ in range(max_tool_turns):
                response = await ctx.model.ainvoke(ctx.messages)
                if not isinstance(response, AIMessage) or not response.tool_calls:
                    has_finished_text_turn = True
                    break
                ctx.messages.append(response)
                await tool_executor.execute(response.tool_calls, ctx.messages)

            if not has_finished_text_turn:
                logger.info(
                    "Max tool turns reached (%d); forcing final text completion turn.",
                    max_tool_turns,
                )
                response = await self.model.ainvoke(ctx.messages)

            if response is None or not isinstance(response, AIMessage):
                raise AgentServiceError("Failed to generate AI response.")

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
            max_tool_turns = 5
            has_finished_text_turn = False

            for turn in range(max_tool_turns):
                current_ai_message: AIMessage | None = None

                async for event in ctx.model.astream_events(ctx.messages, version="v2"):
                    if event["event"] == "on_chat_model_stream":
                        token_text = self._extract_chunk_text(event["data"]["chunk"])
                        if token_text:
                            yield StreamTokenEvent(token=token_text)
                    elif event["event"] == "on_chat_model_end":
                        output = event["data"]["output"]
                        if isinstance(output, AIMessage):
                            current_ai_message = output

                if turn == 0:
                    yield StreamActivityEvent(
                        id="act-understanding",
                        message="Understood your request",
                        status="completed",
                    )

                if not current_ai_message or not current_ai_message.tool_calls:
                    has_finished_text_turn = True
                    break

                # Phase 2: Sequential Tool Execution
                yield StreamStatusEvent(
                    status="executing_tools",
                    message="Executing requested action...",
                )
                ctx.messages.append(current_ai_message)

                for tool_call in current_ai_message.tool_calls:
                    name = tool_call["name"]
                    search_args = self._parse_search_args(tool_call)
                    activity = self._create_tool_activity_event(
                        name, "started", search_args=search_args
                    )
                    if activity:
                        yield activity

                for tool_call in current_ai_message.tool_calls:
                    yield StreamToolStartEvent(tool_name=tool_call["name"])

                await tool_executor.execute(current_ai_message.tool_calls, ctx.messages)

                for tool_call in current_ai_message.tool_calls:
                    yield StreamToolEndEvent(tool_name=tool_call["name"])

                for tool_call in current_ai_message.tool_calls:
                    name = tool_call["name"]
                    search_args = self._parse_search_args(tool_call)
                    activity = self._create_tool_activity_event(
                        name, "completed", search_args=search_args
                    )
                    if activity:
                        yield activity

            # If all max_tool_turns were spent executing tools without a final text output,
            # force text generation turn
            if not has_finished_text_turn:
                logger.info(
                    "Max tool turns reached (%d); forcing final text stream completion turn.",
                    max_tool_turns,
                )
                async for event in self.model.astream_events(
                    ctx.messages, version="v2"
                ):
                    if event["event"] == "on_chat_model_stream":
                        token_text = self._extract_chunk_text(event["data"]["chunk"])
                        if token_text:
                            yield StreamTokenEvent(token=token_text)

            # Final Phase: Stream Complete
            yield StreamCompleteEvent()

        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Error in stream_chat: %s", str(e))
            yield StreamErrorEvent(
                error="Failed to generate AI response. Please try again later."
            )
