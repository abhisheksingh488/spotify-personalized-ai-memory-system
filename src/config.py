"""
Central application configuration.

All environment-specific values are loaded from environment variables
or the local .env file.

Secrets must never be committed to source control.
Use .env.example only as a template with placeholder values.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


def _get_bool(
    name: str,
    default: bool,
) -> bool:
    """
    Safely parse a boolean environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def _get_int(
    name: str,
    default: int,
) -> int:
    """
    Safely parse an integer environment variable.
    """

    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be an integer."
        ) from exc


def _get_float(
    name: str,
    default: float,
) -> float:
    """
    Safely parse a floating-point environment variable.
    """

    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a number."
        ) from exc


def _get_csv(
    name: str,
    default: str,
) -> list[str]:
    """
    Read a comma-separated environment variable.
    """

    value = os.getenv(
        name,
        default,
    )

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


# ============================================================
# SETTINGS
# ============================================================


class Settings:
    """
    Application configuration.

    Keep secrets in environment variables.
    """

    # --------------------------------------------------------
    # Application
    # --------------------------------------------------------

    APP_NAME = os.getenv(
        "APP_NAME",
        "spotify-personalized-ai-memory-system",
    )

    APP_ENV = os.getenv(
        "APP_ENV",
        "development",
    )

    DEBUG = _get_bool(
        "DEBUG",
        False,
    )

    SERVICE_IDENTITY = os.getenv(
        "SERVICE_IDENTITY",
        "spotify-memory-api",
    )

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------

    GROQ_API_KEY = os.getenv(
        "GROQ_API_KEY",
        "",
    )

    GROQ_MODEL = os.getenv(
        "GROQ_MODEL",
        "llama-3.3-70b-versatile",
    )

    GROQ_TEMPERATURE = _get_float(
        "GROQ_TEMPERATURE",
        0.0,
    )

    # Optional web-search integration.
    TAVILY_API_KEY = os.getenv(
        "TAVILY_API_KEY",
        "",
    )

    # --------------------------------------------------------
    # Neo4j
    # --------------------------------------------------------

    NEO4J_URI = os.getenv(
        "NEO4J_URI",
        "bolt://neo4j-service:7687",
    )

    NEO4J_USER = os.getenv(
        "NEO4J_USER",
        "neo4j",
    )

    # Do NOT keep a real production password here.
    # Local .env should provide this value.
    NEO4J_PASSWORD = os.getenv(
        "NEO4J_PASSWORD",
        "",
    )

    NEO4J_DATABASE = os.getenv(
        "NEO4J_DATABASE",
        "neo4j",
    )

    # --------------------------------------------------------
    # Kafka
    # --------------------------------------------------------

    KAFKA_BOOTSTRAP_SERVERS = os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "localhost:9092",
    )

    KAFKA_EVENTS_TOPIC = os.getenv(
        "KAFKA_EVENTS_TOPIC",
        "interaction-events",
    )

    KAFKA_CONSUMER_GROUP = os.getenv(
        "KAFKA_CONSUMER_GROUP",
        "memory-processor-workers",
    )

    KAFKA_AUTO_OFFSET_RESET = os.getenv(
        "KAFKA_AUTO_OFFSET_RESET",
        "earliest",
    )

    KAFKA_ENABLE_AUTO_COMMIT = _get_bool(
        "KAFKA_ENABLE_AUTO_COMMIT",
        False,
    )

    # --------------------------------------------------------
    # Qdrant
    # --------------------------------------------------------

    QDRANT_URL = os.getenv(
        "QDRANT_URL",
        "http://localhost:6333",
    )

    QDRANT_API_KEY = os.getenv(
        "QDRANT_API_KEY",
        "",
    )

    QDRANT_COLLECTION = os.getenv(
        "QDRANT_COLLECTION",
        "spotify_memory",
    )

    # --------------------------------------------------------
    # Embeddings
    # --------------------------------------------------------

    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "all-MiniLM-L6-v2",
    )

    # all-MiniLM-L6-v2 produces 384-dimensional vectors.
    EMBEDDING_DIM = _get_int(
        "EMBEDDING_DIM",
        384,
    )

    EMBEDDING_MODEL_VERSION = os.getenv(
        "EMBEDDING_MODEL_VERSION",
        "all-MiniLM-L6-v2",
    )

    EMBEDDING_DISTANCE = os.getenv(
        "EMBEDDING_DISTANCE",
        "cosine",
    )

    # --------------------------------------------------------
    # Retrieval
    # --------------------------------------------------------

    MAX_CONTEXT_MEMORIES = _get_int(
        "MAX_CONTEXT_MEMORIES",
        8,
    )

    MAX_RETRIEVAL_CANDIDATES = _get_int(
        "MAX_RETRIEVAL_CANDIDATES",
        15,
    )

    RETRIEVAL_LATENCY_BUDGET_MS = _get_int(
        "RETRIEVAL_LATENCY_BUDGET_MS",
        250,
    )

    MIN_MEMORY_CONFIDENCE = _get_float(
        "MIN_MEMORY_CONFIDENCE",
        0.50,
    )

    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    MAX_CONTEXT_CHARS = _get_int(
        "MAX_CONTEXT_CHARS",
        8000,
    )

    MAX_CONTEXT_TOKENS = _get_int(
        "MAX_CONTEXT_TOKENS",
        2000,
    )

    # --------------------------------------------------------
    # Authentication / Authorization
    # --------------------------------------------------------

    AUTH_REQUIRED = _get_bool(
        "AUTH_REQUIRED",
        True,
    )

    AUTH_MODE = os.getenv(
        "AUTH_MODE",
        "demo",
    )

    # --------------------------------------------------------
    # Rate limiting
    # --------------------------------------------------------

    RATE_LIMIT_REQUESTS = _get_int(
        "RATE_LIMIT_REQUESTS",
        60,
    )

    RATE_LIMIT_WINDOW_SECONDS = _get_int(
        "RATE_LIMIT_WINDOW_SECONDS",
        60,
    )

    # --------------------------------------------------------
    # CORS
    # --------------------------------------------------------

    CORS_ALLOW_ORIGINS = _get_csv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:3000",
    )

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    API_PREFIX = os.getenv(
        "API_PREFIX",
        "/v1",
    )

    API_REQUEST_TIMEOUT_SECONDS = _get_int(
        "API_REQUEST_TIMEOUT_SECONDS",
        30,
    )

    # --------------------------------------------------------
    # Memory / Privacy
    # --------------------------------------------------------

    DEFAULT_RETENTION_CLASS = os.getenv(
        "DEFAULT_RETENTION_CLASS",
        "standard",
    )

    ALLOW_SENSITIVE_MEMORY = _get_bool(
        "ALLOW_SENSITIVE_MEMORY",
        False,
    )

    ALLOW_BLOCKED_MEMORY = _get_bool(
        "ALLOW_BLOCKED_MEMORY",
        False,
    )

    # --------------------------------------------------------
    # Deletion
    # --------------------------------------------------------

    DELETION_JOB_RETENTION_SECONDS = _get_int(
        "DELETION_JOB_RETENTION_SECONDS",
        86400,
    )

    DELETION_VERIFY_ENABLED = _get_bool(
        "DELETION_VERIFY_ENABLED",
        True,
    )

    # --------------------------------------------------------
    # Observability
    # --------------------------------------------------------

    OTEL_ENABLED = _get_bool(
        "OTEL_ENABLED",
        False,
    )

    OTEL_SERVICE_NAME = os.getenv(
        "OTEL_SERVICE_NAME",
        "spotify-memory-api",
    )

    OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "",
    )

    PROMETHEUS_ENABLED = _get_bool(
        "PROMETHEUS_ENABLED",
        False,
    )

    # --------------------------------------------------------
    # Operational storage
    # --------------------------------------------------------

    POSTGRES_URL = os.getenv(
        "POSTGRES_URL",
        "",
    )

    REDIS_URL = os.getenv(
        "REDIS_URL",
        "",
    )

    # --------------------------------------------------------
    # Feature flags
    # --------------------------------------------------------

    ENABLE_KAFKA = _get_bool(
        "ENABLE_KAFKA",
        True,
    )

    ENABLE_LLM_EXTRACTION = _get_bool(
        "ENABLE_LLM_EXTRACTION",
        True,
    )

    ENABLE_WEB_SEARCH = _get_bool(
        "ENABLE_WEB_SEARCH",
        False,
    )

    ENABLE_TELEMETRY = _get_bool(
        "ENABLE_TELEMETRY",
        False,
    )


# ============================================================
# SINGLETON SETTINGS OBJECT
# ============================================================

settings = Settings()