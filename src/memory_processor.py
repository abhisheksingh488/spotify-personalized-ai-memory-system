"""
Memory extraction and persistence pipeline.

Pipeline:

interaction event
    -> consent gate
    -> event idempotency check
    -> LLM candidate extraction
    -> strict schema validation
    -> deterministic governance checks
    -> policy filtering
    -> correction/supersession handling
    -> graph persistence
    -> vector persistence

LLM-generated candidates are untrusted until they pass validation.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from src.llm import get_llm

from src.models import (
    CandidateDecision,
    InteractionEvent,
    MemoryCandidate,
    MemoryFact,
    MemoryType,
    PolicyClass,
)

from src.graph_store import GraphStore
from src.vector_store import VectorStore

from src.metrics import (
    MEMORY_PROCESSING_TOTAL,
    MEMORY_PROCESSING_LATENCY_SECONDS,
)

# ============================================================
# AGE / GEOGRAPHY GOVERNANCE
# ============================================================

ALLOWED_AGE_GROUPS = {
    "adult",
    "unknown",
}

BLOCKED_AGE_GROUPS = {
    "minor",
    "child",
}

BLOCKED_GEOGRAPHIES = {
    "blocked",
}


def _governance_allows_persistence(
    event: InteractionEvent,
) -> bool:
    """
    Deterministic age/geography governance gate.

    - Consent is handled separately.
    - Minor/child users are not allowed to create durable memory.
    - Explicitly blocked geography is not allowed.
    - Unknown age is allowed because the system must not infer age.
    """

    age_group = (
        str(event.age_group or "unknown")
        .strip()
        .lower()
    )

    geography = (
        str(event.geography or "")
        .strip()
        .lower()
    )

    if age_group in BLOCKED_AGE_GROUPS:
        return False

    if age_group not in ALLOWED_AGE_GROUPS:
        return False

    if geography in BLOCKED_GEOGRAPHIES:
        return False

    return True


log = logging.getLogger(__name__)


# ============================================================
# EXTRACTION PROMPT
# ============================================================

EXTRACTION_SYSTEM_PROMPT = """
You are a memory-extraction module for a music/podcast
app's AI memory system.

Given one user interaction, decide whether it contains
a durable fact worth remembering.

Allowed memory types:
- episode
- explicit_preference
- candidate_preference
- exclusion
- correction

Rules:

1. Only extract explicit_preference when the user directly
   states a lasting preference.

2. Use candidate_preference for something implied but
   not yet confirmed.

3. Use exclusion for:
   - "don't play X"
   - "don't recommend X"
   - "never suggest X"

4. Use correction whenever the user changes, reverses,
   updates, replaces, or contradicts a previous preference.

5. Strong correction signals include:
   - "I changed my mind"
   - "now I prefer"
   - "I don't want that anymore"
   - "I no longer want"
   - "instead"
   - "actually"
   - "but now"
   - "I prefer X now"
   - "I used to prefer X"

6. When the user explicitly changes a previous preference,
   ALWAYS use memory_type="correction".

7. Use episode for a one-off interaction that should not
   become a durable preference.

8. NEVER infer or store emotional or mental-health state
   as a durable fact.

9. Do not invent entities.

10. Do not invent facts that are not supported by the
    user interaction.

11. If nothing memorable is present, return an empty list.

Return ONLY valid JSON.

Required structure:

{
  "memories": [
    {
      "decision": "accept|reject|review",
      "memory_type": "episode|explicit_preference|candidate_preference|exclusion|correction",
      "fact_text": "...",
      "normalized_fact": "...",
      "entities": [],
      "relevance_score": 0.0,
      "confidence": 0.0,
      "temporal_scope": "...",
      "policy_class": "standard|sensitive|blocked",
      "policy_flags": [],
      "reason": "..."
    }
  ]
}
"""


# ============================================================
# CONSTANTS
# ============================================================

MAX_FACT_LENGTH = 2000
MAX_ENTITY_LENGTH = 200
MAX_ENTITIES = 20


# ============================================================
# TEXT / ENTITY NORMALIZATION
# ============================================================

def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def _entity_to_text(entity: Any) -> str:
    """
    Normalize an LLM entity into a safe string.

    Supports:
    - "Hindi music"
    - {"text": "Hindi music"}
    - {"value": "Hindi music"}
    - {"name": "Hindi music"}
    - {"entity": "Hindi music"}
    """

    if isinstance(entity, str):
        return entity.strip()

    if isinstance(entity, dict):
        for key in (
            "text",
            "value",
            "name",
            "entity",
        ):
            value = entity.get(key)

            if isinstance(value, str):
                return value.strip()

    return ""


def _clean_entities(
    entities: Any,
) -> list[str]:
    if not isinstance(entities, list):
        return []

    cleaned: list[str] = []

    for entity in entities[:MAX_ENTITIES]:

        entity_text = _entity_to_text(entity)

        if not entity_text:
            continue

        cleaned.append(
            entity_text[:MAX_ENTITY_LENGTH]
        )

    return list(
        dict.fromkeys(cleaned)
    )


def _clean_policy_flags(
    flags: Any,
) -> list[str]:
    if not isinstance(flags, list):
        return []

    cleaned: list[str] = []

    for flag in flags:
        if not isinstance(flag, str):
            continue

        flag = flag.strip().lower()

        if flag:
            cleaned.append(flag)

    return list(
        dict.fromkeys(cleaned)
    )


# ============================================================
# RAW LLM NORMALIZATION
# ============================================================

def _normalize_raw_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize untrusted LLM output BEFORE Pydantic validation.
    """

    normalized = dict(item)

    normalized["fact_text"] = _clean_text(
        normalized.get("fact_text")
    )

    normalized["normalized_fact"] = (
        _clean_text(
            normalized.get("normalized_fact")
        )
        or normalized["fact_text"]
    )

    normalized["entities"] = _clean_entities(
        normalized.get("entities")
    )

    normalized["policy_flags"] = (
        _clean_policy_flags(
            normalized.get("policy_flags")
        )
    )

    normalized["temporal_scope"] = (
        _clean_text(
            normalized.get("temporal_scope")
        )
        or None
    )

    normalized["reason"] = (
        _clean_text(
            normalized.get("reason")
        )
        or None
    )

    return normalized


# ============================================================
# JSON PARSING
# ============================================================

def _extract_json(
    raw: str,
) -> dict[str, Any] | None:

    if not raw:
        return None

    raw = raw.strip()

    if raw.startswith("```json"):
        raw = raw[len("```json"):]

    elif raw.startswith("```"):
        raw = raw[len("```"):]

    if raw.endswith("```"):
        raw = raw[:-3]

    raw = raw.strip()

    try:
        value = json.loads(raw)

    except json.JSONDecodeError:
        return None

    if not isinstance(value, dict):
        return None

    return value


# ============================================================
# CANDIDATE VALIDATION
# ============================================================

def _candidate_is_valid(
    candidate: MemoryCandidate,
) -> bool:

    fact_text = _clean_text(
        candidate.fact_text
    )

    if not fact_text:
        return False

    if len(fact_text) > MAX_FACT_LENGTH:
        return False

    if not 0.0 <= candidate.confidence <= 1.0:
        return False

    if not 0.0 <= candidate.relevance_score <= 1.0:
        return False

    return True


def _normalize_candidate(
    candidate: MemoryCandidate,
) -> MemoryCandidate:

    fact_text = _clean_text(
        candidate.fact_text
    )

    normalized_fact = (
        _clean_text(
            candidate.normalized_fact
        )
        or fact_text
    )

    temporal_scope = (
        _clean_text(
            candidate.temporal_scope
        )
        or None
    )

    reason = (
        _clean_text(
            candidate.reason
        )
        or None
    )

    return candidate.model_copy(
        update={
            "fact_text": fact_text,
            "normalized_fact": normalized_fact,
            "entities": _clean_entities(
                candidate.entities
            ),
            "policy_flags": _clean_policy_flags(
                candidate.policy_flags
            ),
            "temporal_scope": temporal_scope,
            "reason": reason,
        }
    )


# ============================================================
# EXTRACTION
# ============================================================

def extract_candidates(
    event: InteractionEvent,
) -> list[MemoryCandidate]:

    if not event.text:
        return []

    text = event.text.strip()

    if not text:
        return []

    llm = get_llm(
        temperature=0.0
    )

    try:
        response = llm.invoke(
            [
                {
                    "role": "system",
                    "content": EXTRACTION_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        "User interaction:\n"
                        f"{text}"
                    ),
                },
            ]
        )

    except Exception as exc:
        log.exception(
            "LLM memory extraction failed: %s",
            exc,
        )

        return []

    raw = getattr(
        response,
        "content",
        "",
    )

    if not isinstance(raw, str):
        return []

    data = _extract_json(raw)

    if data is None:
        log.warning(
            "Memory extraction returned invalid JSON"
        )

        return []

    memories = data.get(
        "memories",
        [],
    )

    if not isinstance(
        memories,
        list,
    ):
        return []

    validated: list[
        MemoryCandidate
    ] = []

    for item in memories:

        if not isinstance(
            item,
            dict,
        ):
            continue

        item = _normalize_raw_item(item)

        try:
            candidate = (
                MemoryCandidate.model_validate(
                    item
                )
            )

        except Exception as exc:
            log.warning(
                "Rejected invalid memory candidate: %s",
                exc,
            )

            continue

        candidate = _normalize_candidate(
            candidate
        )

        if not _candidate_is_valid(
            candidate
        ):
            continue

        validated.append(
            candidate
        )

    return validated


# ============================================================
# POLICY / GOVERNANCE
# ============================================================

def _policy_allows_persistence(
    candidate: MemoryCandidate,
) -> bool:

    if (
        candidate.policy_class
        == PolicyClass.BLOCKED
    ):
        return False

    if (
        candidate.policy_class
        == PolicyClass.SENSITIVE
    ):
        return False

    if (
        candidate.decision
        != CandidateDecision.ACCEPT
    ):
        return False

    if candidate.policy_flags:

        flags = {
            str(flag).strip().lower()
            for flag in candidate.policy_flags
            if str(flag).strip()
        }

        blocked_flags = {
            "blocked",
            "sensitive",
            "privacy_risk",
            "security_risk",
            "pii",
            "mental_health",
            "health",
        }

        if flags.intersection(
            blocked_flags
        ):
            return False

    return True


# ============================================================
# MEMORY FACT CREATION
# ============================================================

def _candidate_to_fact(
    candidate: MemoryCandidate,
    event: InteractionEvent,
) -> MemoryFact:

    fact_text = (
        candidate.normalized_fact
        or candidate.fact_text
    )

    return MemoryFact(
        subject_id=event.subject_id,
        memory_type=candidate.memory_type,
        fact_text=fact_text,
        entities=candidate.entities,
        confidence=candidate.confidence,
        policy_class=candidate.policy_class,
        source_event_id=event.event_id,
        source=event.source,
        valid_from=event.timestamp,
        retention_class="standard",
    )


# ============================================================
# CORRECTION HANDLING
# ============================================================

def _supersede_prior_preferences(
    event: InteractionEvent,
    new_fact: MemoryFact,
    graph: GraphStore,
) -> None:

    prior_memories = (
        graph.get_active_memories(
            event.subject_id
        )
    )

    preference_types = {
        MemoryType.EXPLICIT_PREFERENCE.value,
        MemoryType.CANDIDATE_PREFERENCE.value,
        MemoryType.EXCLUSION.value,
        MemoryType.CORRECTION.value,
    }

    for prior in prior_memories:

        prior_memory_id = prior.get(
            "memory_id"
        )

        prior_subject_id = prior.get(
            "subject_id"
        )

        prior_type = prior.get(
            "memory_type"
        )

        if not prior_memory_id:
            continue

        if (
            prior_subject_id
            != event.subject_id
        ):
            continue

        if (
            prior_memory_id
            == new_fact.memory_id
        ):
            continue

        if (
            prior_type
            not in preference_types
        ):
            continue

        try:
            graph.supersede_memory(
                prior_memory_id,
                new_fact.memory_id,
            )

        except Exception as exc:
            log.exception(
                "Failed to supersede memory %s: %s",
                prior_memory_id,
                exc,
            )


# ============================================================
# FULL EVENT PROCESSOR
# ============================================================

def process_event(
    event: InteractionEvent,
    graph: GraphStore,
    vectors: VectorStore,
) -> list[MemoryFact]:

    processing_start = time.perf_counter()

    try:

        # ----------------------------------------------------
        # Consent gate
        # ----------------------------------------------------

        if not event.consent:
            log.info(
                "Skipping memory processing because consent is false"
            )

            MEMORY_PROCESSING_TOTAL.labels(
                status="blocked_consent"
            ).inc()

            return []

        # ----------------------------------------------------
        # Age / geography governance gate
        # ----------------------------------------------------

        if not _governance_allows_persistence(event):
            log.info(
                "Skipping memory processing because age/geography "
                "governance does not allow durable memory"
            )

            MEMORY_PROCESSING_TOTAL.labels(
                status="blocked_governance"
            ).inc()

            return []

        # ----------------------------------------------------
        # EVENT IDEMPOTENCY GATE
        # ----------------------------------------------------

        if graph.has_processed_event(
            event.subject_id,
            event.event_id,
        ):
            log.info(
                "Skipping already processed event=%s subject=%s",
                event.event_id,
                event.subject_id,
            )

            MEMORY_PROCESSING_TOTAL.labels(
                status="duplicate"
            ).inc()

            return []

        # ----------------------------------------------------
        # Extract
        # ----------------------------------------------------

        candidates = extract_candidates(
            event
        )

        if not candidates:

            MEMORY_PROCESSING_TOTAL.labels(
                status="no_candidates"
            ).inc()

            return []

        written: list[
            MemoryFact
        ] = []

        # ----------------------------------------------------
        # Candidate processing
        # ----------------------------------------------------

        for candidate in candidates:

            if not _policy_allows_persistence(
                candidate
            ):
                continue

            try:

                fact = _candidate_to_fact(
                    candidate,
                    event,
                )

                # --------------------------------------------
                # Correction handling
                # --------------------------------------------

                if (
                    fact.memory_type
                    == MemoryType.CORRECTION
                ):
                    _supersede_prior_preferences(
                        event,
                        fact,
                        graph,
                    )

                # --------------------------------------------
                # Graph persistence
                # --------------------------------------------

                graph.upsert_memory(
                    fact
                )

                # --------------------------------------------
                # Vector persistence
                # --------------------------------------------

                vectors.upsert(
                    fact.memory_id,
                    fact.subject_id,
                    fact.fact_text,
                    policy_class=fact.policy_class.value,
                    status=(
                        fact.status.value
                        if hasattr(
                            fact.status,
                            "value",
                        )
                        else str(fact.status)
                    ),
                    memory_type=fact.memory_type.value,
                    confidence=fact.confidence,
                    source_event_id=fact.source_event_id,
                )

                written.append(
                    fact
                )

            except Exception as exc:

                log.exception(
                    "Failed to persist memory candidate: %s",
                    exc,
                )

                continue

        # ----------------------------------------------------
        # Processing metric
        # ----------------------------------------------------

        MEMORY_PROCESSING_TOTAL.labels(
            status=(
                "success"
                if written
                else "no_memory_written"
            )
        ).inc()

        return written

    except Exception:
        MEMORY_PROCESSING_TOTAL.labels(
            status="error"
        ).inc()

        raise

    finally:
        MEMORY_PROCESSING_LATENCY_SECONDS.observe(
            time.perf_counter() - processing_start
        )