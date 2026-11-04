"""Verify controller-level recovery after a pod is replaced."""
import time
from datetime import datetime, timezone
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


class DeploymentRecoveryVerifier:
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

    def verify(self, namespace, deployment_name, old_pod_uid, timeout_seconds=120,
               stability_samples=3, interval_seconds=5):
        apps, core = self._apis()
        deadline = time.monotonic() + timeout_seconds
        observations = []
        while time.monotonic() < deadline:
            try:
                deployment = apps.read_namespaced_deployment(deployment_name, namespace)
                selector = deployment.spec.selector.match_labels or {}
                if not selector:
                    return self._result("UNKNOWN", "Deployment selector is empty.", observations)
                selector_text = ",".join(f"{k}={v}" for k, v in selector.items())
                pods = core.list_namespaced_pod(namespace, label_selector=selector_text).items
                desired = deployment.spec.replicas or 0
                ready = [p for p in pods if p.status.phase == "Running"
                         and bool(p.status.container_statuses)
                         and all(c.ready for c in p.status.container_statuses)
                         and not p.metadata.deletion_timestamp]
                replacement = [p for p in ready if p.metadata.uid != old_pod_uid]
                observed = getattr(deployment.status, "observed_generation", 0) or 0
                generation = getattr(deployment.metadata, "generation", 0) or 0
                good = (observed >= generation and bool(ready)
                        and len(ready) >= desired and bool(replacement))
                observations.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "desired_replicas": desired, "ready_replicas": len(ready),
                    "replacement_pod_uids": [p.metadata.uid for p in replacement],
                    "observed_generation": deployment.status.observed_generation,
                    "generation": deployment.metadata.generation, "healthy": good,
                })
                if good:
                    break
            except ApiException as exc:
                return self._result("UNKNOWN", f"Kubernetes API returned HTTP {exc.status}.", observations)
            self.sleep(2)
        if not observations or not observations[-1].get("healthy"):
            return self._result("FAILED", "Deployment did not become ready with a replacement pod before timeout.", observations)
        for _ in range(max(0, stability_samples - 1)):
            self.sleep(interval_seconds)
            deployment = apps.read_namespaced_deployment(deployment_name, namespace)
            selector_text = ",".join(f"{k}={v}" for k,v in deployment.spec.selector.match_labels.items())
            pods = core.list_namespaced_pod(namespace, label_selector=selector_text).items
            desired = deployment.spec.replicas or 0
            healthy = [p for p in pods if p.status.phase == "Running"
                       and bool(p.status.container_statuses)
                       and all(c.ready for c in p.status.container_statuses)
                       and not p.metadata.deletion_timestamp]
            good = len(healthy) >= desired and all(p.metadata.uid != old_pod_uid for p in healthy)
            observations.append({"timestamp": datetime.now(timezone.utc).isoformat(),
                                 "desired_replicas": desired, "ready_replicas": len(healthy),
                                 "healthy": good})
            if not good:
                return self._result("FAILED", "Replacement workload failed a stability observation.", observations)
        return self._result("RECOVERED", "Replacement workload passed controller readiness and stability checks.", observations)

    @staticmethod
    def _result(status, reason, observations):
        return {"status": status, "reason": reason, "sample_count": len(observations),
                "observations": observations}
