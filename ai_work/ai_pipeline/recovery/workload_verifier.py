"""Verify controller-level recovery after a pod is replaced."""
import time
from datetime import datetime, timezone

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


class DeploymentRecoveryVerifier:
    """Resolve pod ownership and verify a Deployment's replacement replicas."""

    def __init__(self, apps_api=None, core_api=None, sleep_fn=time.sleep):
        self.apps = apps_api
        self.core = core_api
        self.sleep = sleep_fn

    def _apis(self):
        if self.apps is None or self.core is None:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            self.apps = self.apps or client.AppsV1Api()
            self.core = self.core or client.CoreV1Api()
        return self.apps, self.core

    def resolve_deployment_name(self, namespace, pod_name, expected_uid=None):
        """Resolve Pod -> ReplicaSet -> Deployment; fail closed otherwise."""
        apps, core = self._apis()
        pod = core.read_namespaced_pod(pod_name, namespace)
        if expected_uid and pod.metadata.uid != expected_uid:
            raise ValueError("Pod identity changed; refusing to infer its Deployment.")
        owners = pod.metadata.owner_references or []
        rs_owner = next((owner for owner in owners
                         if owner.kind == "ReplicaSet" and owner.controller), None)
        if rs_owner is None:
            raise ValueError("Pod is not controlled by a ReplicaSet.")
        replica_set = apps.read_namespaced_replica_set(rs_owner.name, namespace)
        deployment_owner = next(
            (owner for owner in (replica_set.metadata.owner_references or [])
             if owner.kind == "Deployment" and owner.controller), None
        )
        if deployment_owner is None:
            raise ValueError("ReplicaSet is not controlled by a Deployment.")
        return deployment_owner.name

    @staticmethod
    def _ready(pod):
        statuses = getattr(pod.status, "container_statuses", None) or []
        return (pod.status.phase == "Running" and bool(statuses)
                and all(item.ready for item in statuses)
                and not pod.metadata.deletion_timestamp)

    def _deployment_pods(self, namespace, deployment, selector_text):
        apps, core = self._apis()
        pods = core.list_namespaced_pod(
            namespace, label_selector=selector_text
        ).items
        owned = []
        for pod in pods:
            owners = pod.metadata.owner_references or []
            rs_owner = next((owner for owner in owners
                             if owner.kind == "ReplicaSet" and owner.controller), None)
            if rs_owner is None:
                continue
            try:
                replica_set = apps.read_namespaced_replica_set(rs_owner.name, namespace)
            except ApiException:
                continue
            if any(owner.kind == "Deployment" and owner.controller
                   and owner.name == deployment
                   for owner in (replica_set.metadata.owner_references or [])):
                owned.append(pod)
        return owned

    def verify(self, namespace, deployment_name, old_pod_uid, timeout_seconds=120,
               stability_samples=3, interval_seconds=5):
        apps, core = self._apis()
        deadline = time.monotonic() + timeout_seconds
        observations = []
        while time.monotonic() < deadline:
            try:
                deployment = apps.read_namespaced_deployment(deployment_name, namespace)
                selector = deployment.spec.selector.match_labels or {}
                desired = deployment.spec.replicas or 0
                if not selector or desired < 1:
                    return self._result(
                        "UNKNOWN", "Deployment selector is empty or replicas are zero.", observations
                    )
                selector_text = ",".join(f"{key}={value}" for key, value in selector.items())
                pods = self._deployment_pods(namespace, deployment_name, selector_text)
                ready = [pod for pod in pods if self._ready(pod)]
                replacements = [pod for pod in ready if pod.metadata.uid != old_pod_uid]
                observed = getattr(deployment.status, "observed_generation", 0) or 0
                generation = getattr(deployment.metadata, "generation", 0) or 0
                healthy = (observed >= generation and len(ready) >= desired
                           and bool(replacements))
                observations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "desired_replicas": desired,
                    "ready_replicas": len(ready),
                    "replacement_pod_uids": [pod.metadata.uid for pod in replacements],
                    "observed_generation": observed,
                    "generation": generation,
                    "healthy": healthy,
                })
                if healthy:
                    break
            except ApiException as exc:
                return self._result(
                    "UNKNOWN", f"Kubernetes API returned HTTP {exc.status}.", observations
                )
            self.sleep(2)

        if not observations or not observations[-1].get("healthy"):
            return self._result(
                "FAILED", "Deployment did not become ready with an owned replacement pod before timeout.",
                observations,
            )

        for _ in range(max(0, stability_samples - 1)):
            self.sleep(interval_seconds)
            try:
                deployment = apps.read_namespaced_deployment(deployment_name, namespace)
                selector = deployment.spec.selector.match_labels or {}
                selector_text = ",".join(f"{key}={value}" for key, value in selector.items())
                pods = self._deployment_pods(namespace, deployment_name, selector_text)
                desired = deployment.spec.replicas or 0
                ready = [pod for pod in pods if self._ready(pod)]
                replacements = [pod for pod in ready if pod.metadata.uid != old_pod_uid]
                observed = getattr(deployment.status, "observed_generation", 0) or 0
                generation = getattr(deployment.metadata, "generation", 0) or 0
                healthy = (bool(selector) and desired > 0 and observed >= generation
                           and len(ready) >= desired and bool(replacements))
                observations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "desired_replicas": desired, "ready_replicas": len(ready),
                    "replacement_pod_uids": [pod.metadata.uid for pod in replacements],
                    "healthy": healthy,
                })
                if not healthy:
                    return self._result(
                        "FAILED", "Replacement workload failed an ownership/readiness stability observation.",
                        observations,
                    )
            except ApiException as exc:
                return self._result(
                    "UNKNOWN", f"Kubernetes API returned HTTP {exc.status} during stability checks.",
                    observations,
                )
        return self._result(
            "RECOVERED",
            "Deployment-owned replacement pods passed readiness and stability checks.",
            observations,
        )

    @staticmethod
    def _result(status, reason, observations):
        return {"status": status, "reason": reason, "sample_count": len(observations),
                "observations": observations}
