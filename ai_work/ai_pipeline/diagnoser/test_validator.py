from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator


def test_valid_diagnosis():

    diagnosis = {
        "incident_id": "INC-TEST-004",
        "root_cause": "Application pod is repeatedly crashing.",
        "evidence": [
            "CrashLoopBackOff detected",
            "Container exited with code 1"
        ],
        "confidence": 0.90,
        "recommended_action": (
            "Inspect the application configuration."
        )
    }

    validator = DiagnosisValidator()

    result = validator.validate(diagnosis)

    assert result["incident_id"] == "INC-TEST-004"
    assert result["confidence"] == 0.90

    print("Valid diagnosis test passed!")


def test_invalid_confidence():

    diagnosis = {
        "incident_id": "INC-TEST-005",
        "root_cause": "Test failure.",
        "evidence": [],
        "confidence": 1.5,
        "recommended_action": "Investigate."
    }

    validator = DiagnosisValidator()

    try:
        validator.validate(diagnosis)
        assert False, "Invalid confidence should be rejected"

    except ValueError as error:
        assert "confidence" in str(error)

    print("Invalid confidence test passed!")


if __name__ == "__main__":
    test_valid_diagnosis()
    test_invalid_confidence()
