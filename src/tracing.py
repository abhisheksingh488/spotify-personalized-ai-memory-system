"""
OpenTelemetry tracing setup for Spotify Memory System.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)


_INITIALIZED = False


def init_tracing() -> None:
    """
    Initialize OpenTelemetry tracing once.

    Tracing is disabled unless OTEL_ENABLED is set to true.
    """

    global _INITIALIZED

    if _INITIALIZED:
        return

    enabled = os.getenv(
        "OTEL_ENABLED",
        "false",
    ).lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if not enabled:
        _INITIALIZED = True
        return

    resource = Resource.create(
        {
            "service.name": os.getenv(
                "OTEL_SERVICE_NAME",
                "spotify-memory-api",
            ),
            "service.version": "1.0",
        }
    )

    provider = TracerProvider(
        resource=resource
    )

    otlp_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:4317",
    )

    exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )

    provider.add_span_processor(
        BatchSpanProcessor(exporter)
    )

    trace.set_tracer_provider(provider)

    _INITIALIZED = True


def get_tracer(
    name: str = "spotify-memory-system",
):
    """
    Return the application tracer.
    """

    init_tracing()

    return trace.get_tracer(name)