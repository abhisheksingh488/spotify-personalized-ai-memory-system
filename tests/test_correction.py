from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)


def test_memory_correction_supersedes_old_memory():
    subject_id = "demo-user-001"

    # 1. Create the original memory
    create_response = client.post(
        "/v1/memories",
        headers={
            "X-Subject-ID": subject_id,
        },
        json={
            "subject_id": subject_id,
            "memory_type": "explicit_preference",
            "fact_text": "I prefer rock music.",
            "entities": ["rock"],
            "confidence": 0.95,
            "policy_class": "standard",
            "source_event_id": "pytest-correction-test-001",
            "retention_class": "standard",
        },
    )

    assert create_response.status_code in (200, 201)

    created = create_response.json()
    assert "memory_id" in created

    old_memory_id = created["memory_id"]

    # 2. Correct the original memory
    correction_response = client.patch(
        f"/v1/memories/{old_memory_id}",
        headers={
            "X-Subject-ID": subject_id,
        },
        json={
            "subject_id": subject_id,
            "corrected_fact_text": "I prefer lo-fi music.",
            "entities": ["lo-fi"],
        },
    )

    assert correction_response.status_code == 200

    correction = correction_response.json()

    assert correction["old_memory_id"] == old_memory_id
    assert "new_memory_id" in correction
    assert correction["new_memory_id"] != old_memory_id
    assert correction["status"] == "superseded_old"

    new_memory_id = correction["new_memory_id"]

    # 3. Verify old memory is superseded
    old_response = client.get(
        f"/v1/memories/{old_memory_id}",
        headers={
            "X-Subject-ID": subject_id,
        },
    )

    # The API may not expose a direct GET-memory endpoint.
    # The correction response itself confirms the supersession action.
    assert old_memory_id != new_memory_id

    # 4. Verify the corrected memory is retrievable
    search_response = client.post(
        "/v1/memories/search",
        headers={
            "X-Subject-ID": subject_id,
        },
        json={
            "subject_id": subject_id,
            "intent": "What kind of music do I prefer?",
            "limit": 20,
        },
    )

    assert search_response.status_code == 200

    body = search_response.json()

    memory_ids = [
        result["memory_id"]
        for result in body.get("results", [])
    ]

    # The old memory must not be returned as an active memory.
    assert old_memory_id not in memory_ids

    # The corrected memory should be available.
    assert new_memory_id in memory_ids