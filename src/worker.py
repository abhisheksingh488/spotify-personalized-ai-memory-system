"""
Standalone worker: consumes interaction events from Kafka and runs the
extraction -> policy filter -> graph write -> embed pipeline.

This is the asynchronous half of ingestion described in the spec;
the chat path only publishes events, it never waits on this.

Run with:
    python -m src.worker

Worker Prometheus metrics:
    http://localhost:8011/metrics
"""

import json
import logging

from kafka import KafkaConsumer
from prometheus_client import start_http_server

from src.config import settings
from src.models import InteractionEvent
from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.memory_processor import process_event


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
)

log = logging.getLogger(__name__)


# ============================================================
# WORKER METRICS
# ============================================================

WORKER_METRICS_PORT = 8011


# ============================================================
# IDEMPOTENCY
# ============================================================

# In-memory idempotency guard for this process's lifetime.
# Durable event idempotency is also handled by the memory pipeline.
_seen_keys: set[str] = set()


# ============================================================
# WORKER
# ============================================================

def run_worker():

    # --------------------------------------------------------
    # Start Prometheus metrics endpoint
    # --------------------------------------------------------

    start_http_server(WORKER_METRICS_PORT)

    log.info(
        "Worker Prometheus metrics available at http://localhost:%s/metrics",
        WORKER_METRICS_PORT,
    )

    # --------------------------------------------------------
    # Kafka consumer
    # --------------------------------------------------------

    consumer = KafkaConsumer(
        settings.KAFKA_EVENTS_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="memory-processor-workers",
        value_deserializer=lambda v: json.loads(
            v.decode("utf-8")
        ),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    # --------------------------------------------------------
    # Storage clients
    # --------------------------------------------------------

    graph = GraphStore()
    vectors = VectorStore()

    log.info("Worker started.")
    log.info(
        "Kafka topic: %s",
        settings.KAFKA_EVENTS_TOPIC,
    )
    log.info(
        "Consumer group: memory-processor-workers"
    )

    # --------------------------------------------------------
    # Consume events
    # --------------------------------------------------------

    for message in consumer:

        payload = message.value

        idem_key = payload.get(
            "idempotency_key"
        )

        # ----------------------------------------------------
        # Duplicate guard
        # ----------------------------------------------------

        if idem_key in _seen_keys:

            log.info(
                "Skipping duplicate event %s",
                idem_key,
            )

            continue

        # ----------------------------------------------------
        # Process event
        # ----------------------------------------------------

        try:

            event = InteractionEvent(
                **payload
            )

            written = process_event(
                event,
                graph,
                vectors,
            )

            _seen_keys.add(
                idem_key
            )

            log.info(
                "Processed event=%s subject=%s memories=%d",
                event.event_id,
                event.subject_id,
                len(written),
            )

        except Exception as exc:

            # Dead-letter handling can be added here for
            # production deployment. For local development,
            # keep the worker alive and log the failure.

            log.exception(
                "Failed to process event=%s: %s",
                idem_key,
                exc,
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run_worker()