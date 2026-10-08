"""
Vector memory store.

Responsibilities:
- Create/manage the Qdrant collection.
- Generate embeddings for memory facts and search queries.
- Keep the same memory_id as the Neo4j graph.
- Store subject/policy/status/provenance metadata.
- Enforce subject-level filtering during semantic search.
- Support deletion propagation.

The graph remains the authoritative source for memory ownership
and lifecycle. Qdrant is a semantic retrieval index.
"""

from __future__ import annotations

from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer

from src.config import settings


# ============================================================
# EMBEDDING MODEL
# ============================================================

_embedder: Optional[
    SentenceTransformer
] = None


def get_embedder() -> SentenceTransformer:
    """
    Lazily initialize the embedding model.

    Lazy loading prevents model initialization during module import.
    """

    global _embedder

    if _embedder is None:
        _embedder = SentenceTransformer(
            settings.EMBEDDING_MODEL
        )

    return _embedder


# ============================================================
# VECTOR STORE
# ============================================================

class VectorStore:
    """
    Qdrant-backed semantic memory index.
    """

    def __init__(self):
        self.client = QdrantClient(
            url=settings.QDRANT_URL
        )

        self._ensure_collection()

    # ========================================================
    # COLLECTION
    # ========================================================

    def _ensure_collection(self) -> None:
        """
        Create the configured collection when it does not exist.
        """

        collections = (
            self.client
            .get_collections()
            .collections
        )

        collection_names = {
            collection.name
            for collection in collections
        }

        if (
            settings.QDRANT_COLLECTION
            not in collection_names
        ):
            self.client.create_collection(
                collection_name=(
                    settings.QDRANT_COLLECTION
                ),
                vectors_config=(
                    qmodels.VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=qmodels.Distance.COSINE,
                    )
                ),
            )

    # ========================================================
    # EMBEDDING
    # ========================================================

    def _embed(
        self,
        text: str,
    ) -> list[float]:
        """
        Generate one embedding vector.
        """

        if not text or not text.strip():
            raise ValueError(
                "Cannot create an embedding from empty text."
            )

        vector = get_embedder().encode(
            text.strip()
        )

        return vector.tolist()

    # ========================================================
    # UPSERT
    # ========================================================

    def upsert(
        self,
        memory_id: str,
        subject_id: str,
        text: str,
        *,
        policy_class: str = "standard",
        status: str = "active",
        memory_type: str | None = None,
        confidence: float | None = None,
        source_event_id: str | None = None,
    ) -> None:
        """
        Insert or update one memory vector.

        memory_id must remain identical to the graph memory ID.
        """

        if not memory_id:
            raise ValueError(
                "memory_id is required."
            )

        if not subject_id:
            raise ValueError(
                "subject_id is required."
            )

        if not text or not text.strip():
            raise ValueError(
                "Memory text is required."
            )

        vector = self._embed(text)

        payload = {
            "memory_id": memory_id,
            "subject_id": subject_id,
            "fact_text": text.strip(),
            "policy_class": policy_class,
            "status": status,
        }

        if memory_type is not None:
            payload["memory_type"] = (
                memory_type
            )

        if confidence is not None:
            payload["confidence"] = float(
                confidence
            )

        if source_event_id is not None:
            payload["source_event_id"] = (
                source_event_id
            )

        self.client.upsert(
            collection_name=(
                settings.QDRANT_COLLECTION
            ),
            points=[
                qmodels.PointStruct(
                    id=memory_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        subject_id: str,
        query: str,
        top_k: int = 10,
    ) -> List[dict]:
        """
        Semantic search scoped strictly to one subject.

        Qdrant-level filtering prevents vectors belonging to another
        subject from entering the retrieval pipeline.
        """

        if not subject_id:
            return []

        if not query or not query.strip():
            return []

        safe_top_k = max(
            1,
            min(
                int(top_k),
                100,
            ),
        )

        vector = self._embed(
            query
        )

        query_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="subject_id",
                    match=qmodels.MatchValue(
                        value=subject_id
                    ),
                ),
                qmodels.FieldCondition(
                    key="status",
                    match=qmodels.MatchValue(
                        value="active"
                    ),
                ),
                qmodels.FieldCondition(
                    key="policy_class",
                    match=qmodels.MatchValue(
                        value="standard"
                    ),
                ),
            ]
        )

        results = self.client.search(
            collection_name=(
                settings.QDRANT_COLLECTION
            ),
            query_vector=vector,
            query_filter=query_filter,
            limit=safe_top_k,
        )

        output: List[dict] = []

        for result in results:

            payload = (
                result.payload
                or {}
            )

            # Defensive subject check even though Qdrant
            # already applies the subject filter.
            if (
                payload.get(
                    "subject_id"
                )
                != subject_id
            ):
                continue

            memory_id = (
                payload.get(
                    "memory_id"
                )
                or result.id
            )

            if not memory_id:
                continue

            output.append(
                {
                    "memory_id": memory_id,
                    "score": float(
                        result.score
                    ),
                    **payload,
                }
            )

        return output

    # ========================================================
    # DELETE
    # ========================================================

    def delete(
        self,
        memory_id: str,
    ) -> None:
        """
        Permanently remove a vector by memory ID.

        This must be called as part of the memory deletion
        propagation workflow.
        """

        if not memory_id:
            return

        self.client.delete(
            collection_name=(
                settings.QDRANT_COLLECTION
            ),
            points_selector=(
                qmodels.PointIdsList(
                    points=[memory_id]
                )
            ),
        )

    # ========================================================
    # COLLECTION HEALTH
    # ========================================================

    def collection_exists(self) -> bool:
        """
        Return whether the configured collection exists.
        """

        collections = (
            self.client
            .get_collections()
            .collections
        )

        return (
            settings.QDRANT_COLLECTION
            in {
                collection.name
                for collection in collections
            }
        )

    # ========================================================
    # HEALTH
    # ========================================================

    def health_check(self) -> bool:
        """
        Check whether Qdrant is reachable and the configured
        collection exists.
        """

        try:
            collections = (
                self.client
                .get_collections()
                .collections
            )

            collection_names = {
                collection.name
                for collection in collections
            }

            return (
                settings.QDRANT_COLLECTION
                in collection_names
            )

        except Exception:
            return False
    # ========================================================
    # COUNT
    # ========================================================

    def count(self) -> int:
        """
        Return the approximate number of indexed vectors.
        """

        result = self.client.count(
            collection_name=(
                settings.QDRANT_COLLECTION
            ),
            exact=True,
        )

        return int(
            result.count
        )