import json

import pytest

from ai_work.ai_pipeline.recovery.incident_lifecycle import (
    AWAITING_HUMAN_APPROVAL,
    INVESTIGATING,
    NEEDS_HEALTH_REVIEW,
    OPEN,
    RECOVERED,
    RESOLVED,
    IncidentLifecycle,
)


def test_lifecycle_records_processing_outcome_without_touching_source(tmp_path):
    source = tmp_path / "INC-1.json"
    original = {"incident_id": "INC-1", "status": "OPEN", "evidence": {"raw": True}}
    source.write_text(json.dumps(original), encoding="utf-8")
    lifecycle = IncidentLifecycle(tmp_path / "lifecycle" / "INC-1.json")

    lifecycle.start_processing("INC-1")
    record = lifecycle.record_outcome(
        "INC-1", RECOVERED, {"message": "Same pod stayed healthy."}
    )

    assert record["current_status"] == RECOVERED
    assert [event["status"] for event in record["events"]] == [
        OPEN, INVESTIGATING, RECOVERED
    ]
    assert json.loads(source.read_text(encoding="utf-8")) == original


def test_lifecycle_records_approval_and_review_outcomes(tmp_path):
    for outcome in (AWAITING_HUMAN_APPROVAL, NEEDS_HEALTH_REVIEW):
        lifecycle = IncidentLifecycle(tmp_path / f"{outcome}.json")
        lifecycle.start_processing("INC-2")
        record = lifecycle.record_outcome("INC-2", outcome)
        assert record["current_status"] == outcome


def test_only_recovered_incident_can_be_resolved_by_human(tmp_path):
    lifecycle = IncidentLifecycle(tmp_path / "INC-3.json")
    lifecycle.start_processing("INC-3")

    with pytest.raises(ValueError, match="Only a RECOVERED"):
        lifecycle.resolve("INC-3", actor="operator", note="Looks fine.")

    lifecycle.record_outcome("INC-3", RECOVERED)
    record = lifecycle.resolve("INC-3", actor="operator", note="Verified and closed.")

    assert record["current_status"] == RESOLVED
    assert record["events"][-1]["actor"] == "operator"


def test_resolved_incident_is_terminal(tmp_path):
    lifecycle = IncidentLifecycle(tmp_path / "INC-4.json")
    lifecycle.start_processing("INC-4")
    lifecycle.record_outcome("INC-4", RECOVERED)
    lifecycle.resolve("INC-4", actor="operator", note="Closed.")

    with pytest.raises(ValueError, match="already RESOLVED"):
        lifecycle.start_processing("INC-4")
    with pytest.raises(ValueError, match="already RESOLVED"):
        lifecycle.record_outcome("INC-4", RECOVERED)


@pytest.mark.parametrize(
    ("actor", "note"),
    [("", "done"), ("operator", ""), (" ", "done"), ("operator", " ")],
)
def test_resolution_requires_actor_and_note(tmp_path, actor, note):
    lifecycle = IncidentLifecycle(tmp_path / "INC-5.json")
    lifecycle.start_processing("INC-5")
    lifecycle.record_outcome("INC-5", RECOVERED)

    with pytest.raises(ValueError):
        lifecycle.resolve("INC-5", actor=actor, note=note)


def test_lifecycle_rejects_unknown_outcome(tmp_path):
    lifecycle = IncidentLifecycle(tmp_path / "INC-6.json")
    with pytest.raises(ValueError, match="Unsupported processing outcome"):
        lifecycle.record_outcome("INC-6", "MAGIC")
