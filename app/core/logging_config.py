"""
Logging configuration and context utilities
"""

import contextvars
import logging

# Context variables for request-scoped values
user_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id", default="N/A"
)
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="N/A"
)


def bind_user_context(user_id: str) -> None:
    """Bind user_id to the request-scoped context variable"""
    user_id_ctx.set(user_id)


class ContextFilter(logging.Filter):
    """
    Filter to inject request_id and user_id into standard LogRecords
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_id = user_id_ctx.get()
        record.request_id = request_id_ctx.get()
        return True


def setup_logging() -> None:
    """
    Initialize the structured logging setup for the 'app' parent logger.
    """
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on reload
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [request: %(request_id)s] [user: %(user_id)s] "
        "%(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())

    logger.addHandler(handler)
    logger.propagate = False
