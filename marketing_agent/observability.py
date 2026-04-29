"""Observability — opt-in OpenTelemetry / Phoenix instrumentation.

Why opt-in? Tracing dependencies (opentelemetry-sdk, openinference-instrumentation-anthropic)
add ~50MB to the install. Most users running the agent locally just want
the JSON logs from `logging.py`. Production / debugging users want full
distributed traces in Phoenix or Langfuse.

To enable:
    pip install "orallexa-marketing-agent[observability]"
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:6006/v1/traces  # local Phoenix
    # or set OTEL_EXPORTER_OTLP_ENDPOINT to a Langfuse / Honeycomb / Datadog endpoint
    export OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental

Then import init_tracing() once at the top of your script (e.g. CLI main):

    from marketing_agent.observability import init_tracing
    init_tracing()

After init, every Anthropic call from `content/generator.py` and `critic.py`
emits an OTel span with token counts + latency. Supervisor iterations are
parented under a single root span per supervise() call, so a Phoenix view
of a single request shows the whole Drafter → Critic → Rewriter tree.

Falls back to a no-op span when OTel isn't installed — code instrumented
with @traced is safe to call regardless.
"""
from __future__ import annotations
import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, TypeVar

from marketing_agent.logging import get_logger

log = get_logger(__name__)
T = TypeVar("T")

_TRACER = None
_TRACING_ENABLED = False


def is_enabled() -> bool:
    """True iff init_tracing() has succeeded in this process."""
    return _TRACING_ENABLED


def init_tracing(*, service_name: str = "orallexa-marketing-agent",
                   endpoint: str | None = None) -> bool:
    """Initialize OTel tracing. Returns True on success, False if deps missing.

    Reads endpoint from arg → OTEL_EXPORTER_OTLP_ENDPOINT env → defaults to
    local Phoenix at http://localhost:6006/v1/traces.
    """
    global _TRACER, _TRACING_ENABLED
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.debug("OTel deps not installed; tracing disabled. "
                   "Install 'orallexa-marketing-agent[observability]'")
        return False

    endpoint = (endpoint
                 or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
                 or "http://localhost:6006/v1/traces")
    resource = Resource.create({"service.name": service_name,
                                  "service.version": _version()})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer(service_name)
    _TRACING_ENABLED = True

    # Auto-instrument Anthropic SDK if openinference is installed
    try:
        from openinference.instrumentation.anthropic import (
            AnthropicInstrumentor,
        )
        AnthropicInstrumentor().instrument()
        log.info("OTel + Anthropic auto-instrumentation enabled",
                  extra={"endpoint": endpoint})
    except ImportError:
        log.info("OTel enabled (Anthropic auto-instrumentation skipped — "
                  "install openinference-instrumentation-anthropic for it)",
                  extra={"endpoint": endpoint})
    return True


def _version() -> str:
    from marketing_agent import __version__
    return __version__


@contextmanager
def span(name: str, **attrs: Any):
    """Context manager that emits an OTel span if tracing enabled, else no-op.

    Usage:
        with span("supervisor.iteration", attempt=2, platform="x"):
            ...
    """
    if not _TRACING_ENABLED or _TRACER is None:
        yield None
        return
    with _TRACER.start_as_current_span(name) as s:
        for k, v in attrs.items():
            try:
                s.set_attribute(k, v)
            except Exception:
                s.set_attribute(k, str(v))
        yield s


def traced(name: str | None = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: wrap a function in a span. Span name defaults to fn name."""
    def deco(fn: Callable[..., T]) -> Callable[..., T]:
        span_name = name or fn.__name__

        @wraps(fn)
        def wrapped(*args, **kwargs) -> T:
            with span(span_name):
                return fn(*args, **kwargs)
        return wrapped
    return deco
