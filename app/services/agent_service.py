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
from app.services.tool_executor import ToolExecutor, ExecutedToolResult
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

    @classmethod
    def _get_activity_id(cls, tool_name: str, turn: int) -> str:
        """Get canonical activity ID matching TOOL_ACTIVITY_CONFIG."""
        config = TOOL_ACTIVITY_CONFIG.get(tool_name)
        base_id = config["id"] if config else f"act-{tool_name}"
        return base_id if turn == 0 else f"{base_id}-turn-{turn}"

    @classmethod
    def _build_started_activity_message(
        cls, tool_name: str, tool_calls: list[ToolCall]
    ) -> str:
        """Construct a dynamic started activity message based on tool_name and call count."""
        count = len(tool_calls)

        if tool_name == "web_search":
            if count == 1:
                search_args = cls._parse_search_args(tool_calls[0])
                if search_args:
                    return f'Searching: "{search_args.query}"'
            return f"Searching web for {count} queries..."

        if tool_name == "get_user_appliances":
            return "Reviewing your appliances..."
        if tool_name == "get_user_energy_summary":
            return "Analyzing your energy usage..."
        if tool_name == "add_user_appliance":
            return (
                "Adding 1 appliance..."
                if count == 1
                else f"Adding {count} appliances..."
            )
        if tool_name == "update_user_appliance":
            return (
                "Updating 1 appliance..."
                if count == 1
                else f"Updating {count} appliances..."
            )
        if tool_name == "delete_user_appliance":
            return (
                "Deleting 1 appliance..."
                if count == 1
                else f"Deleting {count} appliances..."
            )

        config = TOOL_ACTIVITY_CONFIG.get(tool_name)
        return config["started"] if config else f"Executing {tool_name}..."

    @classmethod
    def _build_completed_activity_message(
        cls, tool_name: str, results: list[ExecutedToolResult]
    ) -> str:
        """Construct a dynamic completed activity message inspecting typed execution results."""
        total = len(results)
        succeeded = sum(1 for r in results if r.success)
        failed = total - succeeded

        if tool_name == "web_search":
            if total == 1 and results[0].tool_args.get("query"):
                q = results[0].tool_args["query"]
                return f'Found search results for: "{q}"'
            return f"Found search results for {total} queries"

        if tool_name == "get_user_appliances":
            if (
                total > 0
                and results[0].success
                and isinstance(results[0].raw_result, list)
            ):
                app_count = len(results[0].raw_result)
                if app_count == 0:
                    return "No appliances found"
                if app_count == 1:
                    return "Found 1 appliance"
                return f"Found {app_count} appliances"
            return "Reviewed appliances"

        if tool_name == "get_user_energy_summary":
            return "Analyzed energy usage"

        action_verbs = {
            "add_user_appliance": ("Added", "add"),
            "update_user_appliance": ("Updated", "update"),
            "delete_user_appliance": ("Deleted", "delete"),
        }

        if tool_name in action_verbs:
            past_verb, base_verb = action_verbs[tool_name]
            noun = "appliance" if total == 1 else "appliances"

            if succeeded > 0 and failed == 0:
                return f"{past_verb} {succeeded} {noun}"
            if succeeded > 0 and failed > 0:
                return f"{past_verb} {succeeded} of {total} {noun} ({failed} failed)"
            return f"Failed to {base_verb} {noun}"

        config = TOOL_ACTIVITY_CONFIG.get(tool_name)
        return config["completed"] if config else f"Completed {tool_name}"

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

                # Group tool calls by tool_name in current turn
                grouped_tool_calls: dict[str, list[ToolCall]] = {}
                for tc in current_ai_message.tool_calls:
                    grouped_tool_calls.setdefault(tc["name"], []).append(tc)

                # Sequentially process each tool group: emit started, execute, emit completed
                for tool_name, calls in grouped_tool_calls.items():
                    activity_id = self._get_activity_id(tool_name, turn)
                    started_message = self._build_started_activity_message(
                        tool_name, calls
                    )

                    # 1. Emit started activity event for active group right before execution
                    yield StreamActivityEvent(
                        id=activity_id,
                        message=started_message,
                        status="started",
                    )

                    # 2. Emit tool start events for calls in active group
                    for tc in calls:
                        yield StreamToolStartEvent(tool_name=tc["name"])

                    # 3. Execute calls for active tool group
                    executed_results = await tool_executor.execute(
                        calls, ctx.messages
                    )

                    # 4. Emit tool end events for calls in active group
                    for tc in calls:
                        yield StreamToolEndEvent(tool_name=tc["name"])

                    # 5. Emit completed activity event for active group upon completion
                    completed_message = self._build_completed_activity_message(
                        tool_name, executed_results
                    )
                    yield StreamActivityEvent(
                        id=activity_id,
                        message=completed_message,
                        status="completed",
                    )

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
