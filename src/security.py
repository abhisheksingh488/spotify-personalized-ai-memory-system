"""
Security helpers for the Spotify Personalized AI Memory System.

Responsibilities:
- Resolve the authenticated subject.
- Enforce subject-level isolation.
- Prevent empty or malformed subject identities.
- Provide backend service identity for audit/policy use.

Current authentication modes:
- demo: subject is supplied through X-Subject-ID.
- disabled: anonymous access is allowed only when AUTH_REQUIRED=False.

Production authentication should be provided by the
API gateway / identity provider and mapped to this module.
"""

from fastapi import Header, HTTPException

from src.config import settings


# ============================================================
# SUBJECT VALIDATION
# ============================================================

def _validate_subject(subject: str) -> str:
    """
    Validate and normalize a subject identifier.
    """

    if not isinstance(subject, str):
        raise HTTPException(
            status_code=400,
            detail="Subject identity must be a string",
        )

    subject = subject.strip()

    if not subject:
        raise HTTPException(
            status_code=400,
            detail="Subject identity is required",
        )

    # Prevent accidentally accepting extremely large headers
    # as subject identifiers.
    if len(subject) > 256:
        raise HTTPException(
            status_code=400,
            detail="Subject identity is too long",
        )

    return subject


# ============================================================
# AUTHENTICATED SUBJECT
# ============================================================

def get_authenticated_subject(
    x_subject_id: str | None = Header(default=None),
) -> str:
    """
    Resolve the authenticated subject for the current request.

    Demo mode:
        X-Subject-ID header is required.

    Authentication disabled:
        The supplied subject is accepted when present;
        otherwise the request is treated as anonymous.

    Production authentication:
        The API gateway / identity provider should provide
        the verified identity before this application layer.
    """

    # --------------------------------------------------------
    # AUTHENTICATION DISABLED
    # --------------------------------------------------------

    if not settings.AUTH_REQUIRED:

        if x_subject_id:
            return _validate_subject(
                x_subject_id
            )

        return "anonymous"

    # --------------------------------------------------------
    # DEMO AUTHENTICATION
    # --------------------------------------------------------

    if settings.AUTH_MODE == "demo":

        if not x_subject_id:
            raise HTTPException(
                status_code=401,
                detail="Missing authentication subject",
                headers={
                    "WWW-Authenticate": "Subject"
                },
            )

        return _validate_subject(
            x_subject_id
        )

    # --------------------------------------------------------
    # UNSUPPORTED AUTH MODE
    # --------------------------------------------------------

    raise HTTPException(
        status_code=501,
        detail=(
            f"Authentication mode "
            f"'{settings.AUTH_MODE}' is not configured. "
            "Configure the API gateway or identity provider "
            "before enabling this mode."
        ),
    )


# ============================================================
# SUBJECT ISOLATION
# ============================================================

def require_same_subject(
    authenticated_subject: str,
    requested_subject: str,
) -> None:
    """
    Prevent one authenticated subject from accessing
    another subject's data.
    """

    authenticated_subject = _validate_subject(
        authenticated_subject
    )

    requested_subject = _validate_subject(
        requested_subject
    )

    if authenticated_subject != requested_subject:

        from src.metrics import API_AUTH_FAILURES_TOTAL

        API_AUTH_FAILURES_TOTAL.labels(
            route="memory_operation",
            reason="subject_mismatch",
        ).inc()

        raise HTTPException(
            status_code=403,
            detail="Subject access denied",
        )

# ============================================================
# SERVICE IDENTITY
# ============================================================

def get_service_identity() -> str:
    """
    Return the configured backend service identity
    for audit and policy purposes.
    """

    identity = str(
        settings.SERVICE_IDENTITY
    ).strip()

    if not identity:

        raise HTTPException(
            status_code=500,
            detail="Backend service identity is not configured",
        )

    return identity