"""
Application metrics for the Spotify Personalized AI Memory System.

Privacy rule:
- Never expose memory text, subject IDs, tokens, API keys, or other
  sensitive content through metrics labels or metric values.
"""

from prometheus_client import Counter, Gauge, Histogram


# ------------------------------------------------------------
# API
# ------------------------------------------------------------

API_REQUESTS_TOTAL = Counter(
    "memory_api_requests_total",
    "Total API requests",
    ["method", "route", "status"],
)

API_REQUEST_LATENCY_SECONDS = Histogram(
    "memory_api_request_latency_seconds",
    "API request latency in seconds",
    ["method", "route"],
)

API_AUTH_FAILURES_TOTAL = Counter(
    "memory_api_authorization_failures_total",
    "Authorization failures",
    ["route", "reason"],
)


# ------------------------------------------------------------
# Memory processing
# ------------------------------------------------------------

MEMORY_PROCESSING_TOTAL = Counter(
    "memory_processing_total",
    "Memory processing attempts",
    ["status"],
)

MEMORY_PROCESSING_LATENCY_SECONDS = Histogram(
    "memory_processing_latency_seconds",
    "Memory processing latency in seconds",
)


# ------------------------------------------------------------
# Retrieval
# ------------------------------------------------------------

MEMORY_RETRIEVAL_TOTAL = Counter(
    "memory_retrieval_total",
    "Memory retrieval operations",
    ["status"],
)

MEMORY_RETRIEVAL_LATENCY_SECONDS = Histogram(
    "memory_retrieval_latency_seconds",
    "Memory retrieval latency in seconds",
)

MEMORY_RETRIEVAL_RESULTS = Histogram(
    "memory_retrieval_results",
    "Number of memories returned by retrieval",
    buckets=(0, 1, 2, 3, 5, 10, 20, 50),
)

MEMORY_RETRIEVAL_FALLBACK_TOTAL = Counter(
    "memory_retrieval_fallback_total",
    "Retrieval fallback operations",
    ["reason"],
)


# ------------------------------------------------------------
# Memory lifecycle
# ------------------------------------------------------------

MEMORY_CORRECTIONS_TOTAL = Counter(
    "memory_corrections_total",
    "Memory correction operations",
    ["status"],
)

MEMORY_DELETIONS_TOTAL = Counter(
    "memory_deletions_total",
    "Memory deletion operations",
    ["status"],
)


# ------------------------------------------------------------
# Context composition
# ------------------------------------------------------------

CONTEXT_COMPOSITIONS_TOTAL = Counter(
    "memory_context_compositions_total",
    "Context composition operations",
    ["status"],
)

CONTEXT_COMPOSITION_LATENCY_SECONDS = Histogram(
    "memory_context_composition_latency_seconds",
    "Context composition latency in seconds",
)

CONTEXT_MEMORIES_INCLUDED = Histogram(
    "memory_context_memories_included",
    "Number of memories included in composed context",
    buckets=(0, 1, 2, 3, 5, 10, 20),
)


# ------------------------------------------------------------
# Storage health
# ------------------------------------------------------------

STORAGE_HEALTH = Gauge(
    "memory_storage_health",
    "Storage health status: 1 healthy, 0 unhealthy",
    ["store"],
)


# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------

def set_storage_health(store: str, healthy: bool) -> None:
    """Set storage health without exposing sensitive information."""
    STORAGE_HEALTH.labels(store=store).set(1 if healthy else 0)


def observe_retrieval_results(count: int) -> None:
    """Record bounded retrieval result count."""
    MEMORY_RETRIEVAL_RESULTS.observe(max(0, count))


def observe_context_memories(count: int) -> None:
    """Record bounded context memory count."""
    CONTEXT_MEMORIES_INCLUDED.observe(max(0, count))