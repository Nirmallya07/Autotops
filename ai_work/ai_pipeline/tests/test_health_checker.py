from types import SimpleNamespace
from unittest.mock import patch

from kubernetes.client.exceptions import ApiException

from ai_work.ai_pipeline.recovery.health_checker import (
    HEALTHY_NOW,
    IDENTITY_CHANGED,
    POD_NOT_FOUND,
    UNHEALTHY,
    UNKNOWN,
    KubernetesHealthChecker,
)


def make_pod(name="api-abc", uid="pod-uid-1", phase="Running",
             ready=True, restart_count=2, waiting_reason=None):
    waiting = (
        SimpleNamespace(reason=waiting_reason)
        if waiting_reason else None
    )
    container_status = SimpleNamespace(
        name="api",
        ready=ready,
        restart_count=restart_count,
        state=SimpleNamespace(waiting=waiting),
        last_state=None,
    )
    return SimpleNamespace(
        metadata=SimpleNamespace(name=name, uid=uid),
        status=SimpleNamespace(
            phase=phase,
            container_statuses=[container_status],
        ),
    )


def make_incident(uid="pod-uid-1", restart_count=2):
    pod_status = {
        "name": "api-abc",
        "uid": uid,
        "phase": "Running",
        "containers": [{"name": "api", "ready": False,
                        "restart_count": restart_count,
                        "waiting_reason": "CrashLoopBackOff"}],
    }
    return {
        "incident_id": "INC-TEST-001",
        "namespace": "default",
        "evidence": {"pod_status": pod_status},
    }


class FakeApi:
    def __init__(self, pod=None, error=None):
        self.pod = pod
        self.error = error

    def read_namespaced_pod(self, name, namespace):
        if self.error:
            raise self.error
        return self.pod


def test_reports_healthy_when_pod_and_all_containers_are_ready():
    api = FakeApi(make_pod(ready=True, restart_count=3))

    result = KubernetesHealthChecker(api=api).assess(make_incident())

    assert result["status"] == HEALTHY_NOW
    assert result["restart_count_before"] == 2
    assert result["restart_count_now"] == 3
    assert result["restart_count_increased"] is True
    assert result["identity_verified"] is True


def test_reports_unhealthy_when_container_is_not_ready():
    api = FakeApi(make_pod(ready=False, waiting_reason="CrashLoopBackOff"))

    result = KubernetesHealthChecker(api=api).assess(make_incident())

    assert result["status"] == UNHEALTHY
    assert "not ready" in result["reason"]
    assert "CrashLoopBackOff" in result["reason"]


def test_does_not_compare_restart_counts_for_a_replacement_pod():
    api = FakeApi(make_pod(uid="new-pod-uid", ready=True))

    result = KubernetesHealthChecker(api=api).assess(make_incident())

    assert result["status"] == IDENTITY_CHANGED
    assert result["identity_verified"] is False


def test_reports_pod_not_found():
    api = FakeApi(error=ApiException(status=404, reason="Not Found"))

    result = KubernetesHealthChecker(api=api).assess(make_incident())

    assert result["status"] == POD_NOT_FOUND


def test_reports_unknown_when_api_is_unavailable():
    api = FakeApi(error=ApiException(status=503, reason="Unavailable"))

    result = KubernetesHealthChecker(api=api).assess(make_incident())

    assert result["status"] == UNKNOWN


def test_reports_unknown_when_incident_has_no_pod_identity():
    incident = {
        "incident_id": "INC-TEST-002",
        "namespace": "default",
        "evidence": {"pod_status": {}},
    }

    with patch(
        "ai_work.ai_pipeline.recovery.health_checker.get_kubernetes_client"
    ) as get_client:
        result = KubernetesHealthChecker().assess(incident)

    assert result["status"] == UNKNOWN
    get_client.assert_not_called()

def test_does_not_claim_recovery_when_incident_pod_uid_is_missing():
    api = FakeApi(make_pod(ready=True))

    result = KubernetesHealthChecker(api=api).assess(
        make_incident(uid=None)
    )

    assert result["status"] == UNKNOWN
    assert result["identity_verified"] is False

