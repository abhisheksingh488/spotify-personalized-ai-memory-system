"""
Temporal graph memory layer.

Stores durable memories in Neo4j with:
- subject isolation
- provenance via source_event_id
- valid-time fields
- policy/status metadata
- entity relationships
- correction/supersession relationships
- event-level idempotency checks
"""

from __future__ import annotations

from typing import List, Optional

from neo4j import GraphDatabase

from src.config import settings
from src.models import MemoryFact, now_iso


class GraphStore:
    """Neo4j persistence layer for governed user memories."""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(
                settings.NEO4J_USER,
                settings.NEO4J_PASSWORD,
            ),
        )

        self._ensure_constraints()

    # ========================================================
    # CONNECTION
    # ========================================================
    def close(self) -> None:
        self.driver.close()

    def health_check(self) -> bool:
        """
        Check whether Neo4j is reachable and responding.
        Returns True when the database is healthy.
        """
        try:
            with self.driver.session() as session:
                result = session.run(
                    "RETURN 1 AS health"
                )
                record = result.single()

                return bool(
                    record
                    and record["health"] == 1
                )

        except Exception:
            return False

    # ========================================================
    # SCHEMA
    # ========================================================

    def _ensure_constraints(self) -> None:
        with self.driver.session() as session:

            session.run(
                """
                CREATE CONSTRAINT memory_id_unique IF NOT EXISTS
                FOR (m:Memory)
                REQUIRE m.memory_id IS UNIQUE
                """
            )

            session.run(
                """
                CREATE CONSTRAINT subject_id_unique IF NOT EXISTS
                FOR (s:Subject)
                REQUIRE s.subject_id IS UNIQUE
                """
            )

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    def has_processed_event(
        self,
        subject_id: str,
        source_event_id: str,
    ) -> bool:
        """
        Check whether this subject/event already produced
        at least one persisted memory.

        IMPORTANT:
        The check is scoped to subject_id so one subject can
        never affect another subject's processing.
        """

        if not subject_id or not source_event_id:
            return False

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (m:Memory)
                WHERE m.subject_id = $subject_id
                  AND m.source_event_id = $source_event_id
                  AND m.status <> 'deleted'
                RETURN count(m) AS memory_count
                """,
                subject_id=subject_id,
                source_event_id=source_event_id,
            )

            record = result.single()

            if not record:
                return False

            return int(record["memory_count"]) > 0

    # ========================================================
    # MEMORY WRITE
    # ========================================================

    def upsert_memory(
        self,
        fact: MemoryFact,
    ) -> None:
        """
        Idempotent write of a canonical memory fact.

        memory_id is the primary memory identity.
        source_event_id provides event provenance.
        """

        with self.driver.session() as session:

            session.run(
                """
                MERGE (subj:Subject {
                    subject_id: $subject_id
                })

                MERGE (m:Memory {
                    memory_id: $memory_id
                })

                SET
                    m.subject_id = $subject_id,
                    m.memory_type = $memory_type,
                    m.fact_text = $fact_text,
                    m.entities = $entities,
                    m.confidence = $confidence,
                    m.policy_class = $policy_class,
                    m.source_event_id = $source_event_id,
                    m.source = $source,
                    m.valid_from = $valid_from,
                    m.valid_to = $valid_to,
                    m.recorded_at = $recorded_at,
                    m.status = $status,
                    m.superseded_by = $superseded_by,
                    m.retention_class = $retention_class,
                    m.geography = $geography,
                    m.age_group = $age_group

                MERGE (subj)-[:HAS_MEMORY]->(m)

                WITH m

                UNWIND $entities AS entity_name

                MERGE (e:Entity {
                    name: entity_name
                })

                MERGE (m)-[:ABOUT]->(e)
                """,
                subject_id=fact.subject_id,
                memory_id=fact.memory_id,
                memory_type=fact.memory_type.value,
                fact_text=fact.fact_text,
                entities=fact.entities,
                confidence=fact.confidence,
                policy_class=fact.policy_class.value,
                source_event_id=fact.source_event_id,
                source=fact.source,
                valid_from=fact.valid_from,
                valid_to=fact.valid_to,
                recorded_at=fact.recorded_at,
                status=fact.status.value
                if hasattr(fact.status, "value")
                else str(fact.status),
                superseded_by=fact.superseded_by,
                retention_class=fact.retention_class,
                geography=fact.geography,
                age_group=fact.age_group,
            )

    # ========================================================
    # CORRECTION / SUPERSESSION
    # ========================================================

    def supersede_memory(
        self,
        old_memory_id: str,
        new_memory_id: str,
    ) -> None:
        """
        Mark an old memory as superseded and connect it to
        the replacement memory.
        """

        if not old_memory_id or not new_memory_id:
            return

        with self.driver.session() as session:

            session.run(
                """
                MATCH (old:Memory {
                    memory_id: $old_id
                })

                MATCH (new:Memory {
                    memory_id: $new_id
                })

                SET
                    old.status = 'superseded',
                    old.valid_to = $now,
                    old.superseded_by = $new_id

                MERGE (old)-[:SUPERSEDES]->(new)
                """,
                old_id=old_memory_id,
                new_id=new_memory_id,
                now=now_iso(),
            )

    # ========================================================
    # READ MEMORY
    # ========================================================

    def get_memory(
        self,
        memory_id: str,
    ) -> Optional[dict]:
        """
        Return one memory by ID.
        """

        if not memory_id:
            return None

        with self.driver.session() as session:

            result = session.run(
                """
                MATCH (m:Memory {
                    memory_id: $id
                })

                RETURN m
                """,
                id=memory_id,
            )

            record = result.single()

            if not record:
                return None

            return dict(record["m"])

    # ========================================================
    # DELETE
    # ========================================================

    def delete_memory(
        self,
        memory_id: str,
    ) -> None:
        """
        Soft-delete a memory.

        Retrieval excludes deleted memories.
        """

        if not memory_id:
            return

        with self.driver.session() as session:

            session.run(
                """
                MATCH (m:Memory {
                    memory_id: $id
                })

                SET
                    m.status = 'deleted'
                """,
                id=memory_id,
            )

    def hard_delete_memory(
        self,
        memory_id: str,
    ) -> None:
        """
        Permanently remove a memory node and its
        relationships.
        """

        if not memory_id:
            return

        with self.driver.session() as session:

            session.run(
                """
                MATCH (m:Memory {
                    memory_id: $id
                })

                DETACH DELETE m
                """,
                id=memory_id,
            )

    # ========================================================
    # ACTIVE MEMORIES
    # ========================================================

    def get_active_memories(
        self,
        subject_id: str,
        limit: int = 50,
    ) -> List[dict]:
        """
        Return active, standard-policy memories for one subject.
        """

        if not subject_id:
            return []

        limit = max(
            1,
            min(int(limit), 100),
        )

        with self.driver.session() as session:

            result = session.run(
                """
                MATCH
                    (:Subject {
                        subject_id: $subject_id
                    })
                    -[:HAS_MEMORY]->
                    (m:Memory)

                WHERE
                    m.status = 'active'
                    AND m.policy_class = 'standard'

                RETURN m

                ORDER BY
                    m.confidence DESC,
                    m.recorded_at DESC

                LIMIT $limit
                """,
                subject_id=subject_id,
                limit=limit,
            )

            return [
                dict(record["m"])
                for record in result
            ]

    # ========================================================
    # ENTITY SIMILARITY
    # ========================================================

    def find_similar_fact_by_entities(
        self,
        subject_id: str,
        entities: List[str],
    ) -> Optional[dict]:
        """
        Find an active memory for the same subject sharing
        one of the supplied entities.
        """

        if not subject_id or not entities:
            return None

        clean_entities = [
            str(entity).strip()
            for entity in entities
            if str(entity).strip()
        ]

        if not clean_entities:
            return None

        with self.driver.session() as session:

            result = session.run(
                """
                MATCH
                    (:Subject {
                        subject_id: $subject_id
                    })
                    -[:HAS_MEMORY]->
                    (m:Memory)
                    -[:ABOUT]->
                    (e:Entity)

                WHERE
                    m.status = 'active'
                    AND m.policy_class = 'standard'
                    AND e.name IN $entities

                RETURN m

                ORDER BY
                    m.confidence DESC

                LIMIT 1
                """,
                subject_id=subject_id,
                entities=clean_entities,
            )

            record = result.single()

            if not record:
                return None

            return dict(record["m"])

    # ========================================================
    # MEMORY HISTORY
    # ========================================================

    def get_memory_history(
        self,
        subject_id: str,
        memory_id: str,
    ) -> List[dict]:
        """
        Return the supersession history for a memory,
        scoped to the same subject.
        """

        if not subject_id or not memory_id:
            return []

        with self.driver.session() as session:

            result = session.run(
                """
                MATCH
                    (:Subject {
                        subject_id: $subject_id
                    })
                    -[:HAS_MEMORY]->
                    (m:Memory {
                        memory_id: $memory_id
                    })

                OPTIONAL MATCH path =
                    (m)-[:SUPERSEDES*0..10]->(next:Memory)

                WHERE
                    next IS NULL
                    OR next.subject_id = $subject_id

                RETURN DISTINCT
                    nodes(path) AS memories
                """,
                subject_id=subject_id,
                memory_id=memory_id,
            )

            memories: list[dict] = []

            for record in result:

                nodes = record.get(
                    "memories"
                ) or []

                for node in nodes:

                    data = dict(node)

                    if data not in memories:
                        memories.append(data)

            return memories