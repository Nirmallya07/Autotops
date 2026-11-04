"""Least-privilege Kubernetes remediation adapter.

Only fixed, allowlisted API operations are exposed. No shell or kubectl command
is constructed from model output.
"""
from typing import Any, Dict
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


class KubernetesRemediationExecutor:
    def __init__(self, core_api=None):
        self.core = core_api

    def _api(self):
        if self.core is None:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            self.core = client.CoreV1Api()
        return self.core

    def execute(self, handoff: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(handoff, dict) or handoff.get("status") != "READY_FOR_EXECUTION":
            raise ValueError("A READY_FOR_EXECUTION handoff is required.")
        if handoff.get("action") != "restart_pod":
            raise ValueError("Only restart_pod is supported by this executor.")
        if handoff.get("approved_by") != "policy:auto":
            raise ValueError("A policy authorization or explicit human approval is required.")
        namespace, pod_name, expected_uid = (
            handoff.get("namespace"), handoff.get("pod_name"), handoff.get("pod_uid"))
        if not all(isinstance(x, str) and x.strip() for x in (namespace, pod_name, expected_uid)):
            raise ValueError("Namespace, pod name, and expected UID are required.")
        api = self._api()
        try:
            pod = api.read_namespaced_pod(pod_name, namespace)
            if pod.metadata.uid != expected_uid:
                return {"status": "FAILED", "execution_performed": False,
                        "reason": "Pod identity changed; refusing deletion."}
            owners = pod.metadata.owner_references or []
            if not any(owner.kind in {"ReplicaSet", "StatefulSet"} for owner in owners):
                raise ValueError("Refusing to restart an unmanaged pod.")
            api.delete_namespaced_pod(
                pod_name, namespace,
                body=client.V1DeleteOptions(grace_period_seconds=30),
                propagation_policy="Foreground",
            )
            return {"status": "SUCCESS", "execution_performed": True,
                    "action": "restart_pod", "target": pod_name,
                    "namespace": namespace, "expected_pod_uid": expected_uid,
                    "message": "Pod deletion requested; controller is expected to recreate it."}
        except ApiException as exc:
            return {"status": "FAILED", "execution_performed": False,
                    "reason": f"Kubernetes API returned HTTP {exc.status}."}
