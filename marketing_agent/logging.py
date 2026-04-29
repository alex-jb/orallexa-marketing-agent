"""Structured logging — JSON-formatted stdlib logging, opt-in.

Why stdlib logging instead of structlog/loguru? No extra deps; the JSON
formatter is 30 lines. Output is compatible with Langfuse / Datadog /
Vector / any log shipper that parses JSON.

Why JSON? When you eventually pipe `marketing-agent` runs into Langfuse
or a self-hosted observability stack, structured fields beat regex-parsing
free-form text by 10x.

Default: WARNING+ on stderr, plain text. Set MARKETING_AGENT_LOG=json to
switch to structured JSON; MARKETING_AGENT_LOG_LEVEL=debug to verbose.
"""
from __future__ import annotations
import json
import logging
import os
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """One-line JSON per log record. Adds ts, level, name, msg + any extras."""

    BUILTIN_FIELDS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach any extra fields the caller passed via logger.info("x", extra={"k": "v"})
        for k, v in record.__dict__.items():
            if k in self.BUILTIN_FIELDS or k.startswith("_"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except (TypeError, ValueError):
                payload[k] = repr(v)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_CONFIGURED = False


def get_logger(name: str = "marketing_agent") -> logging.Logger:
    """Return a configured logger. Idempotent — safe to call repeatedly."""
    global _CONFIGURED
    logger = logging.getLogger(name)
    if _CONFIGURED:
        return logger

    level_name = os.getenv("MARKETING_AGENT_LOG_LEVEL", "warning").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stderr)
    if os.getenv("MARKETING_AGENT_LOG", "").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        ))
    logger.handlers.clear()
    logger.addHandler(handler)
    _CONFIGURED = True
    return logger
