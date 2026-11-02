"""Regression tests for evidence-grounding safeguards in DiagnosisValidator."""

import pytest

from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator


def make_diagnosis(
    root_cause="The application encountered an error and terminated.",
    evidence=None,
    confidence=0.8,
):
    return {
        "incident_id": "INC-TEST",
        "root_cause": root_cause,
        "evidence": evidence if evidence is not None else ["last_exit_code: 1"],
        "confidence": confidence,
        "recommended_action": "Inspect the application logs.",
    }


def test_explicit_application_error_preserves_supported_diagnosis():
    marker = (
        "ERROR: Intentional process termination triggered through "
        "the /crash endpoint."
    )
    diagnosis = make_diagnosis(
        root_cause="The application was intentionally terminated through /crash.",
        evidence=[marker],
        confidence=0.95,
    )
    context = {"previous_logs": [marker], "current_logs": []}

    result = DiagnosisValidator().validate(diagnosis, context)

    assert result["root_cause"].endswith("/crash.")
    assert result["confidence"] == 0.95
    assert marker in result["evidence"]


def test_generic_flask_warning_does_not_count_as_failure_evidence():
    warning = (
        "WARNING: This is a development server. Do not use it in a "
        "production deployment."
    )
    diagnosis = make_diagnosis(
        evidence=[warning, "last_exit_code: 1"],
    )
    context = {"previous_logs": [warning], "current_logs": []}

    result = DiagnosisValidator().validate(diagnosis, context)

    assert "exact application-level root cause cannot be determined" in result["root_cause"]
    assert result["confidence"] == 0.35
    assert warning not in result["evidence"]


def test_empty_logs_downgrade_unsupported_error_claim():
    diagnosis = make_diagnosis(
        root_cause="The application encountered an error that caused termination.",
        evidence=["last_terminated_reason: Error", "last_exit_code: 1"],
    )

    result = DiagnosisValidator().validate(diagnosis, {
        "current_logs": [],
        "previous_logs": [],
    })

    assert "exact application-level root cause cannot be determined" in result["root_cause"]
    assert result["confidence"] == 0.35


def test_unrelated_generic_warning_is_removed_from_downgraded_evidence():
    warning = " * Serving Flask app 'app'"
    diagnosis = make_diagnosis(
        evidence=[warning, "last_exit_code: 1"],
    )

    result = DiagnosisValidator().validate(diagnosis, {
        "previous_logs": [warning],
    })

    assert warning not in result["evidence"]
    assert "last_exit_code: 1" in result["evidence"]


def test_structural_validation_rejects_invalid_confidence():
    diagnosis = make_diagnosis(confidence=1.5)

    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        DiagnosisValidator().validate(diagnosis, {"previous_logs": []})


def test_structural_validation_rejects_non_string_evidence():
    diagnosis = make_diagnosis(evidence=["exit code", 1])

    with pytest.raises(ValueError, match="each evidence item must be a string"):
        DiagnosisValidator().validate(diagnosis, {"previous_logs": []})
