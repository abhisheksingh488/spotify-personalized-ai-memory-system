from datetime import datetime, timezone

from src.operational_store import operational_store
from src.models import TraceRecord


TRACE_ID = "operational-store-test-001"
SUBJECT_ID = "demo-user-001"

trace = TraceRecord(
    trace_id=TRACE_ID,
    subject_id=SUBJECT_ID,
    event_id=None,
    memory_ids=["test-memory-001"],
    stages=["retrieve", "compose_context", "complete"],
    fallback=False,
    created_at=datetime.now(timezone.utc).isoformat(),
    metadata={
        "test": True,
        "source": "operational_store_test"
    },
)

print("HEALTH:")
print(operational_store.health())

print("\nSAVING TRACE...")
operational_store.save_trace(trace)
print("TRACE SAVED")

print("\nREADING TRACE FROM STORE...")
loaded = operational_store.get_trace(TRACE_ID)

if loaded:
    print("TRACE READ OK")
    print(loaded.model_dump(mode="json"))
else:
    print("TRACE READ FAILED")

print("\nREDIS CACHE CHECK...")
redis_client = operational_store._get_redis()
cached = redis_client.get(f"trace:{TRACE_ID}")

if cached:
    print("REDIS CACHE OK")
else:
    print("REDIS CACHE FAILED")