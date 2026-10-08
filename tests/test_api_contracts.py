from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)


def test_events_requires_authentication():
    response = client.post(
        "/v1/events",
        json={
            "subject_id": "demo-user-001",
            "event_type": "message",
            "message": "I prefer calm Hindi music while studying.",
            "surface": "chat",
            "locale": "en-IN",
            "consent": True,
            "idempotency_key": "pytest-auth-test-001",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authentication subject"


def test_events_rejects_cross_subject_request():
    response = client.post(
        "/v1/events",
        headers={"X-Subject-ID": "demo-user-001"},
        json={
            "subject_id": "demo-user-002",
            "event_type": "message",
            "message": "Cross subject test.",
            "surface": "chat",
            "locale": "en-IN",
            "consent": True,
            "idempotency_key": "pytest-cross-subject-001",
        },
    )

    assert response.status_code == 403


def test_memory_extraction_contract():
    response = client.post(
        "/v1/memories/extract",
        headers={"X-Subject-ID": "demo-user-001"},
        json={
            "subject_id": "demo-user-001",
            "surface": "chat",
            "event_type": "message",
            "text": "I prefer calm Hindi songs when I study.",
            "locale": "en-IN",
            "consent": True,
            "source": "api",
            "idempotency_key": "pytest-extract-001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "event_id" in body
    assert "candidates" in body
    assert "count" in body
    assert body["count"] == len(body["candidates"])

    if body["candidates"]:
        candidate = body["candidates"][0]

        assert "decision" in candidate
        assert "normalized_fact" in candidate
        assert "confidence" in candidate
        assert "relevance_score" in candidate
        assert "temporal_scope" in candidate
        assert "policy_flags" in candidate
        assert "reason" in candidate


def test_memory_search_contract():
    response = client.post(
        "/v1/memories/search",
        headers={"X-Subject-ID": "demo-user-001"},
        json={
            "subject_id": "demo-user-001",
            "intent": "What Hindi music does the user prefer when studying?",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "trace_id" in body
    assert "subject_id" in body
    assert body["subject_id"] == "demo-user-001"
    assert "results" in body
    assert isinstance(body["results"], list)

    for result in body["results"]:
        assert "memory_id" in result
        assert "fact_text" in result
        assert "confidence" in result
        assert "policy_class" in result
        assert "relevance_score" in result
        assert "retrieval_source" in result


def test_context_compose_contract():
    response = client.post(
        "/v1/context/compose",
        headers={
            "X-Subject-ID": "demo-user-001",
        },
        json={
            "subject_id": "demo-user-001",
            "intent": "What Hindi music does the user prefer when studying?",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["schema_version"] == "1.0"
    assert body["subject_id"] == "demo-user-001"
    assert body["intent"] == (
        "What Hindi music does the user prefer when studying?"
    )

    assert "memories" in body
    assert isinstance(body["memories"], list)

    assert "fallback" in body
    assert isinstance(body["fallback"], bool)

    assert "trace_id" in body
    assert isinstance(body["trace_id"], str)

    assert "influencing_memory_ids" in body
    assert isinstance(body["influencing_memory_ids"], list)

    for item in body["memories"]:
        assert "memory" in item
        assert "relevance_score" in item
        assert "relevance_reason" in item
        assert "retrieval_source" in item

        memory = item["memory"]

        assert "memory_id" in memory
        assert "subject_id" in memory
        assert memory["subject_id"] == "demo-user-001"
        assert "fact_text" in memory
        assert "memory_type" in memory
        assert "confidence" in memory
        assert "policy_class" in memory

def test_feedback_contract():
    response = client.post(
        "/v1/feedback",
        headers={"X-Subject-ID": "demo-user-001"},
        json={
            "subject_id": "demo-user-001",
            "feedback_type": "memory",
            "memory_id": "5f1e4337-0d93-4a68-bcad-bc88ac021acd",
            "value": "relevant",
            "comment": "This memory is useful.",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["schema_version"] == "1.0"
    assert "feedback_id" in body
    assert body["subject_id"] == "demo-user-001"
    assert body["status"] == "recorded"


def test_trace_contract():
    # First create a request that generates a trace.
    response = client.post(
        "/v1/memories/search",
        headers={"X-Subject-ID": "demo-user-001"},
        json={
            "subject_id": "demo-user-001",
            "intent": "What Hindi music does the user prefer when studying?",
            "limit": 10,
        },
    )

    assert response.status_code == 200

    trace_id = response.json()["trace_id"]

    # Fetch the trace.
    trace_response = client.get(
        f"/v1/traces/{trace_id}",
        headers={"X-Subject-ID": "demo-user-001"},
    )

    assert trace_response.status_code == 200

    body = trace_response.json()

    assert body["trace_id"] == trace_id
    assert body["subject_id"] == "demo-user-001"
    assert "memory_ids" in body
    assert isinstance(body["memory_ids"], list)
    assert "stages" in body
    assert isinstance(body["stages"], list)
    assert "fallback" in body
    assert isinstance(body["fallback"], bool)