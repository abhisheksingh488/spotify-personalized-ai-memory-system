"""
Spotify Personalized AI Memory System - MCP Server

Exposes the required MCP memory tools:

1. search_memory
2. add_explicit_preference
3. correct_memory
4. delete_memory
5. explain_memory_use

Security:
- Authenticated subject binding
- Subject-level authorization
- Rate limiting
- Minimal audit logging
- No memory text in audit logs
- Strict tool schemas
"""

import asyncio
import json
import os
import sys
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.graph_store import GraphStore
from src.vector_store import VectorStore
from src.retrieval import retrieve
from src.models import MemoryFact, MemoryType, PolicyClass


# ============================================================
# CONFIGURATION
# ============================================================

MCP_CONTRACT_VERSION = "1.0"

# Demo authentication identity.
#
# IMPORTANT:
# In production this should come from a verified
# MCP gateway / JWT / session instead of an environment variable.
MCP_AUTH_SUBJECT = os.getenv("MCP_AUTH_SUBJECT", "").strip()

RATE_LIMIT_MAX_CALLS = int(
    os.getenv("MCP_RATE_LIMIT_MAX_CALLS", "30")
)

RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("MCP_RATE_LIMIT_WINDOW_SECONDS", "60")
)


# ============================================================
# RATE LIMIT STATE
# ============================================================

_rate_lock = Lock()

_rate_history: dict[str, deque[float]] = defaultdict(deque)


# ============================================================
# STORES
# ============================================================

server = Server("spotify-memory-mcp")

graph = GraphStore()
vectors = VectorStore()


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticated_subject() -> str:
    """
    Return the trusted authenticated subject.

    The subject is NEVER taken directly from a tool request.
    """

    if not MCP_AUTH_SUBJECT:
        raise PermissionError(
            "MCP authentication subject is not configured"
        )

    return MCP_AUTH_SUBJECT


def require_subject(requested_subject: str) -> str:
    """
    Ensure the requested subject belongs to the authenticated user.
    """

    subject = authenticated_subject()

    if not requested_subject:
        raise PermissionError(
            "Subject is required"
        )

    if subject != requested_subject:
        raise PermissionError(
            "Subject access denied"
        )

    return subject


# ============================================================
# RATE LIMITING
# ============================================================

def check_rate_limit(subject: str) -> None:
    """
    Apply a per-subject sliding-window rate limit.
    """

    now = time.time()

    with _rate_lock:

        history = _rate_history[subject]

        while (
            history
            and now - history[0] > RATE_LIMIT_WINDOW_SECONDS
        ):
            history.popleft()

        if len(history) >= RATE_LIMIT_MAX_CALLS:
            raise PermissionError(
                "MCP rate limit exceeded"
            )

        history.append(now)


# ============================================================
# AUDIT LOGGING
# ============================================================

def audit_event(
    *,
    action: str,
    subject_id: str,
    status: str,
    memory_id: str | None = None,
    trace_id: str | None = None,
) -> None:
    """
    Emit a minimal audit event.

    IMPORTANT:
    Never log memory text or other sensitive user content.
    """

    event = {
        "event": "mcp_audit",
        "contract_version": MCP_CONTRACT_VERSION,
        "action": action,
        "subject_id": subject_id,
        "memory_id": memory_id,
        "status": status,
        "trace_id": trace_id,
        "timestamp": time.time(),
    }

    print(
        "AUDIT "
        + json.dumps(
            event,
            separators=(",", ":"),
        ),
        file=sys.stderr,
        flush=True,
    )


# ============================================================
# RESPONSE HELPERS
# ============================================================

def response(
    payload: dict[str, Any],
) -> list[TextContent]:
    """
    Return a structured MCP response.
    """

    return [
        TextContent(
            type="text",
            text=json.dumps(
                payload,
                indent=2,
                default=str,
            ),
        )
    ]


def error_response(
    *,
    error: str,
    status_code: int,
) -> list[TextContent]:

    return response(
        {
            "contract_version": MCP_CONTRACT_VERSION,
            "error": {
                "code": error,
                "status": status_code,
            },
        }
    )


# ============================================================
# MCP TOOL DEFINITIONS
# ============================================================

@server.list_tools()
async def list_tools() -> list[Tool]:

    return [

        # ----------------------------------------------------
        # SEARCH MEMORY
        # ----------------------------------------------------

        Tool(
            name="search_memory",
            description=(
                "Retrieve relevant Spotify listening memories "
                "for the authenticated subject."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "intent": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
                "required": [
                    "subject_id",
                    "intent",
                ],
                "additionalProperties": False,
            },
        ),

        # ----------------------------------------------------
        # ADD EXPLICIT PREFERENCE
        # ----------------------------------------------------

        Tool(
            name="add_explicit_preference",
            description=(
                "Store a Spotify listening preference that "
                "the user directly and explicitly stated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "fact_text": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                    },
                },
                "required": [
                    "subject_id",
                    "fact_text",
                ],
                "additionalProperties": False,
            },
        ),

        # ----------------------------------------------------
        # CORRECT MEMORY
        # ----------------------------------------------------

        Tool(
            name="correct_memory",
            description=(
                "Supersede an existing Spotify memory with "
                "a corrected fact belonging to the authenticated subject."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "old_memory_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "subject_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "corrected_fact_text": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "entities": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                    },
                },
                "required": [
                    "old_memory_id",
                    "subject_id",
                    "corrected_fact_text",
                ],
                "additionalProperties": False,
            },
        ),

        # ----------------------------------------------------
        # DELETE MEMORY
        # ----------------------------------------------------

        Tool(
            name="delete_memory",
            description=(
                "Delete a Spotify memory belonging to "
                "the authenticated subject."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "subject_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
                "required": [
                    "memory_id",
                    "subject_id",
                ],
                "additionalProperties": False,
            },
        ),

        # ----------------------------------------------------
        # EXPLAIN MEMORY USE
        # ----------------------------------------------------

        Tool(
            name="explain_memory_use",
            description=(
                "Explain why a stored Spotify memory was used, "
                "including provenance, relevance, confidence, "
                "and policy metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "subject_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "intent": {
                        "type": "string",
                        "minLength": 1,
                    },
                },
                "required": [
                    "memory_id",
                    "subject_id",
                    "intent",
                ],
                "additionalProperties": False,
            },
        ),
    ]


# ============================================================
# MCP TOOL EXECUTION
# ============================================================

@server.call_tool()
async def call_tool(
    name: str,
    arguments: dict,
) -> list[TextContent]:

    try:

        # ----------------------------------------------------
        # BASIC ARGUMENT VALIDATION
        # ----------------------------------------------------

        if not isinstance(arguments, dict):

            return error_response(
                error="invalid_arguments",
                status_code=400,
            )

        # ----------------------------------------------------
        # AUTHENTICATION
        # ----------------------------------------------------

        subject = authenticated_subject()

        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        check_rate_limit(subject)

        # ----------------------------------------------------
        # SUBJECT BINDING
        # ----------------------------------------------------

        requested_subject = arguments.get(
            "subject_id"
        )

        if requested_subject:
            require_subject(
                requested_subject
            )
        else:
            raise PermissionError(
                "Subject is required"
            )

        # ====================================================
        # SEARCH MEMORY
        # ====================================================

        if name == "search_memory":

            intent = str(
                arguments.get(
                    "intent",
                    ""
                )
            ).strip()

            if not intent:

                return error_response(
                    error="invalid_intent",
                    status_code=400,
                )

            results = retrieve(
                subject,
                intent,
                graph,
                vectors,
            )

            payload = {
                "contract_version":
                    MCP_CONTRACT_VERSION,

                "subject_id":
                    subject,

                "tool":
                    name,

                "results": [
                    {
                        "memory_id":
                            r.memory.memory_id,

                        "fact":
                            r.memory.fact_text,

                        "type":
                            r.memory.memory_type.value,

                        "confidence":
                            r.memory.confidence,

                        "relevance_score":
                            r.relevance_score,

                        "reason":
                            r.relevance_reason,

                        "provenance": {
                            "source_event_id":
                                r.memory.source_event_id,

                            "valid_from":
                                r.memory.valid_from,

                            "valid_to":
                                r.memory.valid_to,

                            "status":
                                r.memory.status,
                        },

                        "policy": {
                            "policy_class":
                                r.memory.policy_class.value,
                        },
                    }

                    for r in results
                ],
            }

            audit_event(
                action=name,
                subject_id=subject,
                status="success",
            )

            return response(
                payload
            )

        # ====================================================
        # ADD EXPLICIT PREFERENCE
        # ====================================================

        if name == "add_explicit_preference":

            fact_text = str(
                arguments.get(
                    "fact_text",
                    ""
                )
            ).strip()

            if not fact_text:

                return error_response(
                    error="invalid_fact_text",
                    status_code=400,
                )

            entities = arguments.get(
                "entities",
                [],
            )

            if not isinstance(
                entities,
                list,
            ):
                return error_response(
                    error="invalid_entities",
                    status_code=400,
                )

            fact = MemoryFact(

                subject_id=subject,

                memory_type=
                    MemoryType.EXPLICIT_PREFERENCE,

                fact_text=fact_text,

                entities=entities,

                confidence=0.95,

                policy_class=
                    PolicyClass.STANDARD,
            )

            graph.upsert_memory(
                fact
            )

            vectors.upsert(
                fact.memory_id,
                fact.subject_id,
                fact.fact_text,
            )

            audit_event(
                action=name,
                subject_id=subject,
                memory_id=fact.memory_id,
                status="success",
            )

            return response(
                {
                    "contract_version":
                        MCP_CONTRACT_VERSION,

                    "status":
                        "created",

                    "memory_id":
                        fact.memory_id,

                    "subject_id":
                        subject,

                    "provenance": {
                        "source":
                            "explicit_user_statement",

                        "source_event_id":
                            fact.source_event_id,

                        "valid_from":
                            fact.valid_from,
                    },

                    "policy": {
                        "policy_class":
                            fact.policy_class.value,
                    },
                }
            )

        # ====================================================
        # CORRECT MEMORY
        # ====================================================

        if name == "correct_memory":

            old_memory_id = str(
                arguments.get(
                    "old_memory_id",
                    ""
                )
            ).strip()

            corrected_fact_text = str(
                arguments.get(
                    "corrected_fact_text",
                    ""
                )
            ).strip()

            if (
                not old_memory_id
                or not corrected_fact_text
            ):

                return error_response(
                    error="invalid_correction",
                    status_code=400,
                )

            old_memory = graph.get_memory(
                old_memory_id
            )

            if not old_memory:

                return error_response(
                    error="memory_not_found",
                    status_code=404,
                )

            if old_memory.get(
                "subject_id"
            ) != subject:

                audit_event(
                    action=name,
                    subject_id=subject,
                    memory_id=old_memory_id,
                    status="denied",
                )

                return error_response(
                    error="subject_access_denied",
                    status_code=403,
                )

            entities = arguments.get(
                "entities",
                [],
            )

            if not isinstance(
                entities,
                list,
            ):
                return error_response(
                    error="invalid_entities",
                    status_code=400,
                )

            new_fact = MemoryFact(

                subject_id=subject,

                memory_type=
                    MemoryType.CORRECTION,

                fact_text=
                    corrected_fact_text,

                entities=entities,

                confidence=0.95,

                policy_class=
                    PolicyClass.STANDARD,
            )

            graph.upsert_memory(
                new_fact
            )

            graph.supersede_memory(
                old_memory_id,
                new_fact.memory_id,
            )

            vectors.upsert(
                new_fact.memory_id,
                new_fact.subject_id,
                new_fact.fact_text,
            )

            audit_event(
                action=name,
                subject_id=subject,
                memory_id=old_memory_id,
                status="success",
            )

            return response(
                {
                    "contract_version":
                        MCP_CONTRACT_VERSION,

                    "status":
                        "superseded_old",

                    "old_memory_id":
                        old_memory_id,

                    "new_memory_id":
                        new_fact.memory_id,

                    "subject_id":
                        subject,

                    "provenance": {
                        "source":
                            "user_correction",

                        "supersedes":
                            old_memory_id,

                        "valid_from":
                            new_fact.valid_from,
                    },

                    "policy": {
                        "policy_class":
                            new_fact.policy_class.value,
                    },
                }
            )

        # ====================================================
        # DELETE MEMORY
        # ====================================================

        if name == "delete_memory":

            memory_id = str(
                arguments.get(
                    "memory_id",
                    ""
                )
            ).strip()

            if not memory_id:

                return error_response(
                    error="invalid_memory_id",
                    status_code=400,
                )

            memory = graph.get_memory(
                memory_id
            )

            if not memory:

                return error_response(
                    error="memory_not_found",
                    status_code=404,
                )

            if memory.get(
                "subject_id"
            ) != subject:

                audit_event(
                    action=name,
                    subject_id=subject,
                    memory_id=memory_id,
                    status="denied",
                )

                return error_response(
                    error="subject_access_denied",
                    status_code=403,
                )

            # Delete from graph
            graph.delete_memory(
                memory_id
            )

            # Delete from vector store
            vectors.delete(
                memory_id
            )

            audit_event(
                action=name,
                subject_id=subject,
                memory_id=memory_id,
                status="success",
            )

            return response(
                {
                    "contract_version":
                        MCP_CONTRACT_VERSION,

                    "status":
                        "deleted",

                    "memory_id":
                        memory_id,

                    "subject_id":
                        subject,
                }
            )

        # ====================================================
        # EXPLAIN MEMORY USE
        # ====================================================

        if name == "explain_memory_use":

            memory_id = str(
                arguments.get(
                    "memory_id",
                    ""
                )
            ).strip()

            intent = str(
                arguments.get(
                    "intent",
                    ""
                )
            ).strip()

            if (
                not memory_id
                or not intent
            ):

                return error_response(
                    error="invalid_explanation_request",
                    status_code=400,
                )

            memory = graph.get_memory(
                memory_id
            )

            if not memory:

                return error_response(
                    error="memory_not_found",
                    status_code=404,
                )

            if memory.get(
                "subject_id"
            ) != subject:

                audit_event(
                    action=name,
                    subject_id=subject,
                    memory_id=memory_id,
                    status="denied",
                )

                return error_response(
                    error="subject_access_denied",
                    status_code=403,
                )

            results = retrieve(
                subject,
                intent,
                graph,
                vectors,
            )

            matched = next(
                (
                    item
                    for item in results
                    if item.memory.memory_id
                    == memory_id
                ),
                None,
            )

            audit_event(
                action=name,
                subject_id=subject,
                memory_id=memory_id,
                status="success",
            )

            return response(
                {
                    "contract_version":
                        MCP_CONTRACT_VERSION,

                    "memory_id":
                        memory_id,

                    "subject_id":
                        subject,

                    "used_for_intent":
                        intent,

                    "was_retrieved":
                        matched is not None,

                    "explanation": {
                        "relevance_reason": (
                            matched.relevance_reason
                            if matched
                            else
                            "Memory was not among "
                            "the retrieved memories "
                            "for this intent."
                        ),

                        "relevance_score": (
                            matched.relevance_score
                            if matched
                            else None
                        ),
                    },

                    "provenance": {
                        "source_event_id":
                            memory.get(
                                "source_event_id"
                            ),

                        "valid_from":
                            memory.get(
                                "valid_from"
                            ),

                        "valid_to":
                            memory.get(
                                "valid_to"
                            ),

                        "status":
                            memory.get(
                                "status"
                            ),
                    },

                    "policy": {
                        "policy_class":
                            memory.get(
                                "policy_class",
                                PolicyClass.STANDARD.value,
                            ),
                    },
                }
            )

        # ====================================================
        # UNKNOWN TOOL
        # ====================================================

        return error_response(
            error="unknown_tool",
            status_code=404,
        )

    # ========================================================
    # PERMISSION ERROR
    # ========================================================

    except PermissionError as exc:

        audit_event(
            action=name,
            subject_id=(
                MCP_AUTH_SUBJECT
                or "unknown"
            ),
            status="denied",
        )

        message = str(exc).lower()

        if "rate limit" in message:

            return error_response(
                error="rate_limit_exceeded",
                status_code=429,
            )

        return error_response(
            error="subject_access_denied",
            status_code=403,
        )

    # ========================================================
    # GENERAL ERROR
    # ========================================================

    except Exception as exc:

        print(
            f"MCP ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )

        audit_event(
            action=name,
            subject_id=(
                MCP_AUTH_SUBJECT
                or "unknown"
            ),
            status="error",
        )

        return error_response(
            error="internal_error",
            status_code=500,
        )


# ============================================================
# SERVER ENTRYPOINT
# ============================================================

async def main():

    async with stdio_server() as (
        read,
        write,
    ):

        await server.run(
            read,
            write,
            server.create_initialization_options(),
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )