"""
Agent business logic service using LangChain and Gemini
"""

import logging
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.prompts.agent import SYSTEM_PROMPT
from app.schemas.agent import ChatResponse

logger = logging.getLogger(__name__)


class AgentServiceError(Exception):
    """Application-level exception raised when AgentService encounters an execution error."""


class AgentService:
    """
    Agent business logic service using LangChain and Gemini
    """

    def __init__(self, model: BaseChatModel):
        self.model = model

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
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)

        return "".join(parts)

    async def chat(self, user_message: str) -> ChatResponse:
        """
        Process user message via LangChain and Gemini model, returning assistant response.
        """
        # NOTE / TODO: Remove logs soon
        logger.info("AgentService.chat: User Prompt: %r", user_message)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        try:
            response: AIMessage = await self.model.ainvoke(messages)
            text_content = self._extract_message_text(response)
            logger.info("AgentService.chat: Assistant Reply: %r", text_content)
            return ChatResponse(message=text_content)
        except Exception as e:
            logger.exception("Error invoking Gemini model in AgentService: %s", str(e))
            raise AgentServiceError("Failed to generate AI response.") from e
