from ai_work.ai_pipeline.recovery.stability_monitor import (
    NEEDS_REVIEW,
    RECOVERED,
    RecoveryStabilityMonitor,
)


POD_UID = "pod-uid-1"


class SequenceChecker:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def assess(self, incident):
        self.calls += 1
        return next(self.results)


def healthy(uid=POD_UID, identity_verified=True):
    return {
        "status": "HEALTHY_NOW",
        "pod_uid": uid,
        "identity_verified": identity_verified,
    }


def test_returns_recovered_after_same_pod_stays_healthy_for_window():
    checker = SequenceChecker([healthy(), healthy(), healthy()])
    sleeps = []

    monitor = RecoveryStabilityMonitor(
        checker,
        window_seconds=20,
        interval_seconds=10,
        sleep_fn=sleeps.append,
    )

    result = monitor.monitor({"incident_id": "INC-1"})

    assert result["status"] == RECOVERED
    assert result["sample_count"] == 3
    assert result["window_seconds"] == 20
    assert sleeps == [10, 10]


def test_stops_when_pod_becomes_unhealthy():
    checker = SequenceChecker([
        healthy(),
        {"status": "UNHEALTHY", "reason": "container not ready"},
    ])
    monitor = RecoveryStabilityMonitor(
        checker, window_seconds=60, interval_seconds=10, sleep_fn=lambda _: None
    )

    result = monitor.monitor({"incident_id": "INC-2"})

    assert result["status"] == "UNHEALTHY"
    assert result["sample_count"] == 2


def test_requires_review_when_pod_identity_changes_mid_window():
    checker = SequenceChecker([
        healthy(),
        healthy(uid="replacement-pod"),
    ])
    monitor = RecoveryStabilityMonitor(
        checker, window_seconds=30, interval_seconds=10, sleep_fn=lambda _: None
    )

    result = monitor.monitor({"incident_id": "INC-3"})

    assert result["status"] == NEEDS_REVIEW
    assert result["sample_count"] == 2


def test_unknown_observation_does_not_count_as_recovery():
    checker = SequenceChecker([
        healthy(),
        {"status": "UNKNOWN", "reason": "API unavailable"},
    ])
    monitor = RecoveryStabilityMonitor(
        checker, window_seconds=30, interval_seconds=10, sleep_fn=lambda _: None
    )

    result = monitor.monitor({"incident_id": "INC-4"})

    assert result["status"] == "UNKNOWN"
    assert result["sample_count"] == 2


def test_non_healthy_initial_observation_does_not_start_window():
    checker = SequenceChecker([
        {"status": "UNHEALTHY", "reason": "not ready"},
    ])
    sleeps = []
    monitor = RecoveryStabilityMonitor(
        checker,
        window_seconds=30,
        interval_seconds=10,
        sleep_fn=sleeps.append,
    )

    result = monitor.monitor({"incident_id": "INC-5"})

    assert result["status"] == "UNHEALTHY"
    assert result["sample_count"] == 1
    assert sleeps == []


def test_rejects_invalid_window_or_interval():
    checker = SequenceChecker([])

    for kwargs in (
        {"window_seconds": 0},
        {"window_seconds": float("inf")},
        {"interval_seconds": -1},
        {"interval_seconds": True},
    ):
        try:
            RecoveryStabilityMonitor(checker, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid duration should raise ValueError")
