"""Read-only Kubernetes health assessment for a previously reported incident."""

from datetime import datetime, timezone

from kubernetes.client.exceptions import ApiException

from watcher.collectors.k8s import get_kubernetes_client, pod_status


HEALTHY_NOW = "HEALTHY_NOW"
UNHEALTHY = "UNHEALTHY"
POD_NOT_FOUND = "POD_NOT_FOUND"
IDENTITY_CHANGED = "IDENTITY_CHANGED"
UNKNOWN = "UNKNOWN"


class KubernetesHealthChecker:
    """Check the current state of the incident's pod without changing resources.

    A healthy result describes one observation only. Callers must not treat it
    as proof of sustained recovery without a separate stability window.
    """

    def __init__(self, api=None):
        # Dependency injection keeps the checker easy to test without a cluster.
        self.api = api

    def assess(self, incident):
        evidence = incident.get("evidence") or {}
        previous = evidence.get("pod_status") or {}
        pod_name = previous.get("name")
        namespace = incident.get("namespace")

        if not pod_name or not namespace:
            return self._result(
                incident, UNKNOWN,
                "Incident evidence does not contain a pod name and namespace.",
                pod_name=pod_name,
            )

        try:
            # Client setup can fail when kubeconfig or cluster access is absent.
            # Treat that as UNKNOWN rather than crashing incident processing.
            api = self.api if self.api is not None else get_kubernetes_client()
            pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)
        except ApiException as exc:
            if exc.status == 404:
                return self._result(
                    incident, POD_NOT_FOUND,
                    f"Pod '{pod_name}' no longer exists in namespace '{namespace}'.",
                    pod_name=pod_name,
                )
            return self._result(
                incident, UNKNOWN,
                f"Kubernetes API returned HTTP {exc.status}.",
                pod_name=pod_name,
            )
        except Exception as exc:
            return self._result(
                incident, UNKNOWN,
                f"Could not read the pod: {type(exc).__name__}.",
                pod_name=pod_name,
            )

        current = pod_status(pod)
        previous_uid = previous.get("uid")
        current_uid = current.get("uid")

        # A pod name can be reused. Never compare restart counts across UIDs.
        if previous_uid and current_uid and previous_uid != current_uid:
            return self._result(
                incident, IDENTITY_CHANGED,
                "A different pod now has this name; the original pod cannot be verified.",
                pod_name=pod_name,
                pod_uid=current_uid,
                phase=current.get("phase"),
                containers=current.get("containers", []),
                identity_verified=False,
            )

        if not previous_uid or not current_uid:
            return self._result(
                incident, UNKNOWN,
                "Pod identity is missing from the incident or live snapshot; recovery cannot be verified safely.",
                pod_name=pod_name,
                pod_uid=current_uid,
                phase=current.get("phase"),
                identity_verified=False,
            )

        containers = current.get("containers") or []
        if not containers:
            return self._result(
                incident, UNKNOWN,
                "Kubernetes returned no container status; readiness cannot be confirmed.",
                pod_name=pod_name,
                pod_uid=current_uid,
                phase=current.get("phase"),
                containers=[],
                identity_verified=bool(previous_uid and current_uid),
            )

        not_ready = [item["name"] for item in containers if not item.get("ready")]
        waiting = [
            f"{item['name']} ({item['waiting_reason']})"
            for item in containers if item.get("waiting_reason")
        ]
        phase = current.get("phase")

        if phase != "Running" or not_ready or waiting:
            reasons = []
            if phase != "Running":
                reasons.append(f"pod phase is {phase or 'unknown'}")
            if not_ready:
                reasons.append("containers not ready: " + ", ".join(not_ready))
            if waiting:
                reasons.append("containers waiting: " + ", ".join(waiting))

            return self._result(
                incident, UNHEALTHY, "; ".join(reasons),
                pod_name=pod_name,
                pod_uid=current_uid,
                phase=phase,
                containers=containers,
                identity_verified=bool(previous_uid and current_uid),
            )

        previous_restarts = self._max_restarts(previous.get("containers") or [])
        current_restarts = self._max_restarts(containers)

        return self._result(
            incident, HEALTHY_NOW,
            "The pod is Running and all reported containers are ready in this observation.",
            pod_name=pod_name,
            pod_uid=current_uid,
            phase=phase,
            containers=containers,
            restart_count_before=previous_restarts,
            restart_count_now=current_restarts,
            restart_count_increased=(
                previous_restarts is not None
                and current_restarts is not None
                and current_restarts > previous_restarts
            ),
            identity_verified=bool(previous_uid and current_uid),
        )

    @staticmethod
    def _max_restarts(containers):
        counts = [
            item.get("restart_count")
            for item in containers
            if isinstance(item.get("restart_count"), int)
        ]
        return max(counts) if counts else None

    @staticmethod
    def _result(incident, status, reason, **details):
        return {
            "incident_id": incident.get("incident_id"),
            "status": status,
            "reason": reason,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
