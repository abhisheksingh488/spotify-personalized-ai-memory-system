from fastapi.testclient import TestClient

from src.api import app


client = TestClient(app)


def test_memory_deletion_contract():
    subject_id = "demo-user-001"

    # 1. Create a temporary memory
    create_response = client.post(
        "/v1/memories",
        headers={
            "X-Subject-ID": subject_id,
        },
        json={
           "subject_id": subject_id,
           "memory_type": "explicit_preference",
           "fact_text": "Temporary test memory for deletion.",
           "entities": ["deletion-test"],
           "confidence": 0.95,
           "policy_class": "standard",
           "source_event_id": "pytest-deletion-test-001",
           "retention_class": "standard",
        },
    )

    assert create_response.status_code in (200, 201)

    created = create_response.json()

    assert "memory_id" in created

    memory_id = created["memory_id"]

    # 2. Delete the temporary memory
    delete_response = client.delete(
        f"/v1/memories/{memory_id}",
        headers={
            "X-Subject-ID": subject_id,
        },
    )

    assert delete_response.status_code == 200

    deletion = delete_response.json()

    assert "job_id" in deletion
    assert deletion["memory_id"] == memory_id

    job_id = deletion["job_id"]

    # 3. Check deletion job status
    status_response = client.get(
        f"/v1/deletions/{job_id}",
        headers={
            "X-Subject-ID": subject_id,
        },
    )

    assert status_response.status_code == 200

    status = status_response.json()

    assert status["job_id"] == job_id
    assert status["memory_id"] == memory_id
    assert status["status"] == "completed"

    # 4. Verify deletion propagated to all required stores
    assert status["graph_deleted"] is True
    assert status["vector_deleted"] is True
    assert status["cache_deleted"] is True
    assert status["operational_metadata_deleted"] is True