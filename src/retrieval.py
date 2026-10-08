"""
Hybrid memory retrieval.

Retrieval pipeline:

1. Fetch active memories for the authenticated subject.
2. Search the vector store using the user's intent.
3. Intersect vector results with graph-owned memories.
4. Apply deterministic policy and status filters.
5. Calculate a deterministic hybrid relevance score.
6. Always preserve important high-confidence explicit preferences
   and exclusions.
7. Return only the bounded number of memories allowed by configuration.

Memory text is treated as data, not instructions.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models import (
    MemoryFact,
    MemoryType,
    PolicyClass,
    RetrievedMemory,
)

from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.config import settings


# ============================================================
# MEMORY TYPE WEIGHTS
# ============================================================

TYPE_WEIGHT = {
    MemoryType.EXPLICIT_PREFERENCE: 1.00,
    MemoryType.CORRECTION: 1.00,
    MemoryType.EXCLUSION: 0.90,
    MemoryType.CANDIDATE_PREFERENCE: 0.60,
    MemoryType.EPISODE: 0.30,
}


# ============================================================
# RECENCY
# ============================================================

def _recency_score(
    valid_from: str | None,
) -> float:
    """
    Recency score between 0 and 1.

    A memory starts at 1.0 and decays to 0 over roughly
    90 days.

    Invalid timestamps receive a neutral score rather than
    crashing retrieval.
    """

    if not valid_from:
        return 0.5

    try:
        ts = datetime.fromisoformat(
            valid_from
        )

        if ts.tzinfo is None:
            ts = ts.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        age_seconds = (
            now - ts
        ).total_seconds()

        # Future timestamps should not receive a penalty.
        age_days = max(
            0.0,
            age_seconds / 86400.0,
        )

        return max(
            0.0,
            1.0 - age_days / 90.0,
        )

    except Exception:
        return 0.5


# ============================================================
# POLICY
# ============================================================

def _memory_is_retrievable(
    memory: dict,
    subject_id: str,
) -> bool:
    """
    Deterministic retrieval policy.

    A memory is retrievable only when:
    - it belongs to the requested subject
    - it is active
    - it is not blocked
    - it is not sensitive
    """

    if memory.get(
        "subject_id"
    ) != subject_id:
        return False

    if memory.get(
        "status"
    ) != "active":
        return False

    policy_class = memory.get(
        "policy_class",
        PolicyClass.STANDARD.value,
    )

    if policy_class in {
        PolicyClass.BLOCKED.value,
        PolicyClass.SENSITIVE.value,
    }:
        return False

    return True


# ============================================================
# TYPE
# ============================================================

def _memory_type(
    memory: dict,
) -> MemoryType | None:
    """
    Safely convert stored memory type into MemoryType.
    """

    try:
        return MemoryType(
            memory["memory_type"]
        )

    except (
        KeyError,
        ValueError,
        TypeError,
    ):
        return None


# ============================================================
# SCORING
# ============================================================

def _hybrid_score(
    semantic_score: float,
    memory: dict,
    memory_type: MemoryType,
) -> float:
    """
    Deterministic hybrid relevance score.

    Weighting:
        50% semantic similarity
        25% confidence
        15% memory type importance
        10% recency
    """

    semantic = max(
        0.0,
        min(
            1.0,
            float(
                semantic_score
            ),
        ),
    )

    confidence = max(
        0.0,
        min(
            1.0,
            float(
                memory.get(
                    "confidence",
                    0.5,
                )
            ),
        ),
    )

    type_score = TYPE_WEIGHT.get(
        memory_type,
        0.3,
    )

    recency = _recency_score(
        memory.get(
            "valid_from"
        )
    )

    score = (
        0.50 * semantic
        + 0.25 * confidence
        + 0.15 * type_score
        + 0.10 * recency
    )

    return round(
        score,
        4,
    )


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve(
    subject_id: str,
    intent: str,
    graph: GraphStore,
    vectors: VectorStore,
) -> list[RetrievedMemory]:
    """
    Retrieve relevant memories for exactly one subject.

    The graph acts as the authoritative ownership/status layer.
    The vector store provides semantic candidate ranking.

    Cross-subject vector results are rejected before they can
    reach the context composer.
    """

    if not subject_id:
        return []

    if not intent or not intent.strip():
        return []

    # --------------------------------------------------------
    # Graph candidates
    # --------------------------------------------------------

    graph_memories = (
        graph.get_active_memories(
            subject_id
        )
    )

    graph_candidates: dict[
        str,
        dict,
    ] = {}

    for memory in graph_memories:

        if not isinstance(
            memory,
            dict,
        ):
            continue

        memory_id = memory.get(
            "memory_id"
        )

        if not memory_id:
            continue

        if not _memory_is_retrievable(
            memory,
            subject_id,
        ):
            continue

        graph_candidates[
            memory_id
        ] = memory

    if not graph_candidates:
        return []

    # --------------------------------------------------------
    # Vector candidates
    # --------------------------------------------------------

    vector_hits = vectors.search(
        subject_id,
        intent.strip(),
        top_k=15,
    )

    scored: dict[
        str,
        RetrievedMemory,
    ] = {}

    # --------------------------------------------------------
    # Semantic + graph hybrid scoring
    # --------------------------------------------------------

    for hit in vector_hits:

        if not isinstance(
            hit,
            dict,
        ):
            continue

        memory_id = hit.get(
            "memory_id"
        )

        if not memory_id:
            continue

        # The graph is authoritative. A vector hit alone
        # must never create a retrievable memory.
        memory = graph_candidates.get(
            memory_id
        )

        if memory is None:
            continue

        memory_type = _memory_type(
            memory
        )

        if memory_type is None:
            continue

        semantic_score = hit.get(
            "score",
            0.0,
        )

        try:
            semantic_score = float(
                semantic_score
            )

        except (
            TypeError,
            ValueError,
        ):
            semantic_score = 0.0

        score = _hybrid_score(
            semantic_score,
            memory,
            memory_type,
        )

        try:
            memory_fact = MemoryFact(
                **memory
            )

        except Exception:
            # Invalid stored records must never reach the
            # context composer.
            continue

        scored[
            memory_id
        ] = RetrievedMemory(
            memory=memory_fact,
            relevance_score=score,
            relevance_reason=(
                "hybrid match: "
                f"semantic={semantic_score:.2f}, "
                f"type={memory_type.value}, "
                f"confidence="
                f"{memory.get('confidence', 0.5):.2f}, "
                f"recency="
                f"{_recency_score(memory.get('valid_from')):.2f}"
            ),
        )

    # --------------------------------------------------------
    # Relational recall
    # --------------------------------------------------------
    #
    # Important explicit preferences and exclusions should
    # remain available even when their wording does not rank
    # inside the vector search top-k.
    # --------------------------------------------------------

    for memory_id, memory in (
        graph_candidates.items()
    ):

        if memory_id in scored:
            continue

        memory_type = _memory_type(
            memory
        )

        if memory_type is None:
            continue

        confidence = memory.get(
            "confidence",
            0.0,
        )

        try:
            confidence = float(
                confidence
            )

        except (
            TypeError,
            ValueError,
        ):
            confidence = 0.0

        if (
            memory_type
            in (
                MemoryType.EXPLICIT_PREFERENCE,
                MemoryType.EXCLUSION,
                MemoryType.CORRECTION,
            )
            and confidence >= 0.80
        ):
            try:
                memory_fact = MemoryFact(
                    **memory
                )

            except Exception:
                continue

            # Base relational score is deliberately below
            # a strong semantic match, but above weak episodes.
            score = round(
                0.65
                + 0.15 * min(
                    confidence,
                    1.0,
                ),
                4,
            )

            scored[
                memory_id
            ] = RetrievedMemory(
                memory=memory_fact,
                relevance_score=score,
                relevance_reason=(
                    "high-confidence "
                    "relational recall"
                ),
            )

    # --------------------------------------------------------
    # Final deterministic ranking
    # --------------------------------------------------------

    ranked = sorted(
        scored.values(),
        key=lambda item: (
            item.relevance_score,
            item.memory.confidence,
            item.memory.recorded_at,
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Bounded context
    # --------------------------------------------------------

    max_memories = max(
        0,
        int(
            settings.MAX_CONTEXT_MEMORIES
        ),
    )

    return ranked[
        :max_memories
    ]