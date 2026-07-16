"""
WattTipid API
"""

from fastapi import (
    FastAPI,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth
from app.database.redis import redis_client
from app.middleware.rate_limit import RateLimitMiddleware
from app.core.config import ENV

is_dev = ENV == "dev"

_docs_config = (
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
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://watt-tipid.vercel.app/",
    ],
    allow_methods=["*"],
    allow_headers=[
        "Authorization",
        "Content-Type",
    ],
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
