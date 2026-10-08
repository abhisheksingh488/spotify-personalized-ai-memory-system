from datetime import datetime, timezone

from src.memory_processor import _governance_allows_persistence
from src.models import InteractionEvent


def make_event(
    *,
    consent=True,
    age_group=None,
    geography=None,
):
    return InteractionEvent(
        subject_id="policy_test_user",
        surface="test",
        event_type="message",
        text="I prefer calm music",
        locale="en-IN",
        source="test",
        consent=consent,
        geography=geography,
        age_group=age_group,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def test_adult_normal_geography_allowed():
    event = make_event(
        age_group="adult",
        geography="india",
    )

    assert _governance_allows_persistence(event) is True


def test_minor_is_blocked():
    event = make_event(
        age_group="minor",
        geography="india",
    )

    assert _governance_allows_persistence(event) is False


def test_child_is_blocked():
    event = make_event(
        age_group="child",
        geography="india",
    )

    assert _governance_allows_persistence(event) is False


def test_unknown_age_is_allowed_without_inference():
    event = make_event(
        age_group="unknown",
        geography="india",
    )

    assert _governance_allows_persistence(event) is True


def test_blocked_geography_is_rejected():
    event = make_event(
        age_group="adult",
        geography="blocked",
    )

    assert _governance_allows_persistence(event) is False


def test_invalid_age_group_is_rejected():
    event = make_event(
        age_group="invalid_age_value",
        geography="india",
    )

    assert _governance_allows_persistence(event) is False


def test_consent_false_is_not_governance_approval():
    event = make_event(
        consent=False,
        age_group="adult",
        geography="india",
    )

    assert _governance_allows_persistence(event) is True
    assert event.consent is False