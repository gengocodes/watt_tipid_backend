"""
Unit and integration tests for logging configuration, contextvars,
middleware isolation, and log formatting.
"""

# pylint: disable=wrong-import-position, disable=no-member

from unittest.mock import MagicMock, AsyncMock

import logging
import io
import anyio
import pytest

# Mock Redis / PyMongo before importing app to prevent CI network calls
import pymongo
import app.database.redis

pymongo.MongoClient = MagicMock()
if not isinstance(app.database.redis.redis_client, AsyncMock):
    app.database.redis.redis_client = AsyncMock()
app.database.redis.redis_client.incr.return_value = 1
app.database.redis.redis_client.expire.return_value = True

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.logging_config import (
    user_id_ctx,
    request_id_ctx,
    setup_logging,
    ContextFilter,
)
from app.middleware.logging_middleware import LoggingContextMiddleware


def test_context_filter_injection():
    """Verify ContextFilter injects request_id and user_id into log records."""
    t_rid = request_id_ctx.set("test-request-123")
    t_uid = user_id_ctx.set("test-user-456")

    try:
        record = logging.LogRecord(
            name="app.test",
            level=logging.INFO,
            pathname="test_logging.py",
            lineno=10,
            msg="Hello, world!",
            args=(),
            exc_info=None,
        )

        filt = ContextFilter()
        assert filt.filter(record) is True
        assert record.request_id == "test-request-123"
        assert record.user_id == "test-user-456"
    finally:
        request_id_ctx.reset(t_rid)
        user_id_ctx.reset(t_uid)


def test_logging_formatter_output():
    """Verify that logging output formatter includes request and user IDs."""

    setup_logging()
    logger = logging.getLogger("app.test")

    # Add a custom stream handler writing to a StringIO stream
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [req_id: %(request_id)s] "
        "[user: %(user_id)s] %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())
    logger.addHandler(handler)

    t_rid = request_id_ctx.set("formatter-req")
    t_uid = user_id_ctx.set("formatter-user")

    try:
        logger.info("Test formatter message")
        output = stream.getvalue()
        assert "[req_id: formatter-req]" in output
        assert "[user: formatter-user]" in output
        assert "app.test - Test formatter message" in output
    finally:
        request_id_ctx.reset(t_rid)
        user_id_ctx.reset(t_uid)
        logger.removeHandler(handler)


def test_middleware_initialization_and_cleanup():
    """Verify LoggingContextMiddleware binds variables during request and resets them after."""
    test_app = FastAPI()
    test_app.add_middleware(LoggingContextMiddleware)

    captured_rid = None
    captured_uid = None

    @test_app.get("/test")
    def test_endpoint():
        nonlocal captured_rid, captured_uid
        captured_rid = request_id_ctx.get()
        captured_uid = user_id_ctx.get()
        return {"status": "ok"}

    client = TestClient(test_app)

    # Before request, variables should be default ("N/A")
    assert request_id_ctx.get() == "N/A"
    assert user_id_ctx.get() == "N/A"

    response = client.get("/test")
    assert response.status_code == 200

    # Context variables inside request should have been populated
    assert captured_rid != "N/A"
    assert len(captured_rid) == 36  # Valid UUID
    assert captured_uid == "N/A"  # Default since unauthenticated

    # After request, they should be cleaned up / reset back to default
    assert request_id_ctx.get() == "N/A"
    assert user_id_ctx.get() == "N/A"


@pytest.mark.anyio
async def test_concurrent_request_isolation():
    """Verify concurrent requests have isolated logging contexts (no leakage)."""

    async def request_worker(task_id: str, delay: float):
        # Manually emulate middleware context binding
        token_rid = request_id_ctx.set(f"req-{task_id}")
        token_uid = user_id_ctx.set(f"user-{task_id}")
        try:
            await anyio.sleep(delay)
            # Verify values remain isolated
            assert request_id_ctx.get() == f"req-{task_id}"
            assert user_id_ctx.get() == f"user-{task_id}"
        finally:
            request_id_ctx.reset(token_rid)
            user_id_ctx.reset(token_uid)

    # Run multiple tasks concurrently with different values and delays
    async with anyio.create_task_group() as tg:
        tg.start_soon(request_worker, "A", 0.05)
        tg.start_soon(request_worker, "B", 0.02)
        tg.start_soon(request_worker, "C", 0.08)
