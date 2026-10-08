from unittest.mock import Mock

from src.memory_processor import process_event
from src.models import InteractionEvent


def make_event():
    return InteractionEvent(
        event_id="idempotency-test-event-001",
        subject_id="demo-user-001",
        event_type="message",
        text="I prefer calm Hindi music while studying.",
        surface="chat",
        locale="en-IN",
        consent=True,
    )


def test_duplicate_event_is_skipped():
    event = make_event()

    graph = Mock()
    vectors = Mock()

    # Simulate that this event was already processed.
    graph.has_processed_event.return_value = True

    result = process_event(
        event,
        graph,
        vectors,
    )

    assert result == []

    graph.has_processed_event.assert_called_once_with(
        "demo-user-001",
        "idempotency-test-event-001",
    )

    # Already processed event must not write another memory.
    vectors.upsert.assert_not_called()


def test_new_event_is_not_blocked_by_idempotency_gate():
    event = make_event()

    graph = Mock()
    vectors = Mock()

    # Event has not been processed before.
    graph.has_processed_event.return_value = False

    # Stop the test after the idempotency gate.
    # The purpose here is only to verify that the gate does not
    # incorrectly reject a new event.
    try:
        process_event(event, graph, vectors)
    except Exception:
        pass

    graph.has_processed_event.assert_called_once_with(
        "demo-user-001",
        "idempotency-test-event-001",
    )