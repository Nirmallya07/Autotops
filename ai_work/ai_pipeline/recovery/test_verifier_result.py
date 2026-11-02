from ai_work.ai_pipeline.recovery.verifier_result import RecoveryResult


def test_recovery_result():

    recovery = {
        "incident_id": "INC-TEST-001",
        "status": "RECOVERED",
        "details": {
            "pod_ready": True,
            "error_rate_normal": True,
            "restart_count_stable": True
        }
    }

    receiver = RecoveryResult()

    result = receiver.receive(recovery)

    assert result["incident_id"] == "INC-TEST-001"
    assert result["status"] == "RECOVERED"
    assert result["details"]["pod_ready"] is True
    assert result["details"]["error_rate_normal"] is True

    print("Recovery Result test passed!")
    print("Recovery status:", result["status"])


if __name__ == "__main__":
    test_recovery_result()
