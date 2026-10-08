from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)


def test_explicit_preference_recall():
    subject_id = "demo-user-001"

    response = client.post(
        "/v1/memories/search",
        headers={
            "X-Subject-ID": subject_id,
        },
        json={
            "subject_id": subject_id,
            "intent": "Recommend music based on my preferences",
            "limit": 20,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["subject_id"] == subject_id
    assert "results" in body

    allowed_types = {
        "EXPLICIT_PREFERENCE",
        "CORRECTION",
        "explicit_preference",
        "correction",
    }

    for result in body["results"]:
        assert result["memory_type"] in allowed_types
        assert "memory_id" in result
        assert "fact_text" in result
        assert "confidence" in result
        assert "relevance_score" in result
        assert "retrieval_source" in result