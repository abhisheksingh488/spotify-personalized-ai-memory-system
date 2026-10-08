import pytest

from src.security import require_same_subject


def test_same_subject_is_allowed():
    result = require_same_subject(
        "demo-user-001",
        "demo-user-001",
    )

    assert result is None


def test_cross_subject_is_blocked():
    with pytest.raises(Exception):
        require_same_subject(
            "demo-user-001",
            "demo-user-002",
        )

from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)


def test_cross_subject_memory_is_not_returned():
    response = client.post(
        "/v1/memories/search",
        headers={
            "X-Subject-ID": "demo-user-001",
        },
        json={
            "subject_id": "demo-user-001",
            "intent": "What does the user prefer about Korean music?",
            "limit": 50,
        },
    )

    assert response.status_code == 200

    body = response.json()

    for result in body["results"]:
        assert result["memory_id"] != "56956315-133a-48e1-8aeb-36191b168dbb"

def test_cross_subject_memory_deletion_is_blocked():
    memory_id = "56956315-133a-48e1-8aeb-36191b168dbb"

    response = client.delete(
        f"/v1/memories/{memory_id}",
        headers={
            "X-Subject-ID": "demo-user-001",
        },
    )

    assert response.status_code == 403

def test_policy_flagged_memory_candidate_is_not_accepted():
    from src.memory_processor import _policy_allows_persistence
    from src.models import MemoryCandidate

    candidate = MemoryCandidate(
        decision="accept",
        memory_type="explicit_preference",
        fact_text="Sensitive information that should not become durable memory.",
        normalized_fact="Sensitive information that should not become durable memory.",
        entities=[],
        relevance_score=0.95,
        confidence=0.95,
        temporal_scope=None,
        policy_flags=["privacy_risk"],
        reason="Test privacy risk.",
    )

    assert _policy_allows_persistence(candidate) is False