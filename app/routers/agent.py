"""
AI Agent endpoint routers
"""

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_agent_service
from app.schemas.agent import ChatRequest, ChatResponse, StreamErrorEvent
from app.schemas.auth import User
from app.services.agent_service import AgentService, AgentServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["AI Agent"])


@router.post(
    "/chat",
    status_code=status.HTTP_200_OK,
)
async def chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ChatResponse:
    """
    Process chat interaction with WattTipid AI assistant
    """
    # NOTE / TODO: Remove logs soon
    logger.info(
        "POST /agents/chat request from user_id=%s | Prompt: %r",
        current_user.id,
        request.message,
    )
    try:
        response = await agent_service.chat(
            user_id=current_user.id,
            user_name=current_user.first_name,
            user_message=request.message,
        )
        logger.info(
            "POST /agents/chat response for user_id=%s | Reply: %r",
            current_user.id,
            response.message,
        )
        return response
    except AgentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI response. Please try again later.",
        ) from e


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
)
async def chat_stream(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> StreamingResponse:
    """
    Stream chat interaction with WattTipid AI assistant via Server-Sent Events (SSE)
    """
    logger.info(
        "POST /agents/chat/stream request from user_id=%s | Prompt: %r",
        current_user.id,
        request.message,
    )

    async def event_generator():
        try:
            async for event in agent_service.stream_chat(
                user_id=current_user.id,
                user_name=current_user.first_name,
                user_message=request.message,
            ):
                yield f"data: {event.model_dump_json()}\n\n"
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Error generating stream in chat_stream endpoint: %s", str(e)
            )
            err_event = StreamErrorEvent(
                error="Failed to generate AI response. Please try again later."
            )
            yield f"data: {err_event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
