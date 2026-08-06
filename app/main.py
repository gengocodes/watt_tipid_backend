"""
WattTipid API
"""

import logging
from typing import Any, Dict
from fastapi import (
    FastAPI,
    Response,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, energy, dashboard, user_settings, agent, saving_tips
from app.database.redis import redis_client
from app.middleware.rate_limit import RateLimitMiddleware
from app.core.config import ENV
from app.core.logging_config import setup_logging
from app.middleware.logging_middleware import LoggingContextMiddleware

setup_logging()
logger = logging.getLogger(__name__)

is_dev = ENV == "dev"

_docs_config: Dict[str, Any] = (
    {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }
    if is_dev
    else {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
)

app = FastAPI(
    title="WattTipid API",
    description="WattTipid Agentic AI API",
    **_docs_config,
)

app.include_router(auth.router)
app.include_router(energy.router)
app.include_router(dashboard.router)
app.include_router(user_settings.router)
app.include_router(agent.router)
app.include_router(saving_tips.router)


# LoggingContextMiddleware wraps RateLimitMiddleware
# to ensure logging context is set during its execution
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://watt-tipid.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global handler for unexpected server exceptions.
    """
    logger.exception(
        "Unhandled server error occurred during %s %s %s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )


@app.get("/health")
async def health_check(response: Response):
    """Check the health of the API"""
    try:
        await redis_client.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:  # pylint: disable=broad-except
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "error": str(e)}
