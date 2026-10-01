"""
Tools = the doctor's hands. Every function here does something real
(query Prometheus, talk to Kubernetes). Nodes in graph.py call these;
they should never touch kubernetes/prometheus clients directly.

Each function is deliberately synchronous and narrow-scoped. Easier to unit
test, easier to reason about what the agent is *allowed* to do.
"""

import os
from datetime import datetime, timedelta

from prometheus_api_client import PrometheusConnect
from kubernetes import client as k8s_client, config as k8s_config


# ---------- Observability ----------

def get_prometheus_client() -> PrometheusConnect:
    url = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    return PrometheusConnect(url=url, disable_ssl=True)


def query_service_metrics(service: str, minutes: int = 5) -> dict:
    """Pull a small, fixed set of vitals for a service over the last N minutes.

    TODO: replace these placeholder PromQL queries with ones that match
    your actual exporter's metric names once the sample app is instrumented.
    """
    prom = get_prometheus_client()
    end = datetime.utcnow()
    start = end - timedelta(minutes=minutes)

    queries = {
        "error_rate": f'rate(http_requests_total{{service="{service}", status=~"5.."}}[5m])',
        "latency_p99": f'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m]))',
        "restart_count": f'kube_pod_container_status_restarts_total{{pod=~"{service}.*"}}',
    }

    results = {}
    for name, query in queries.items():
        try:
            results[name] = prom.custom_query_range(
                query=query, start_time=start, end_time=end, step="30s"
            )
        except Exception as e:  # pragma: no cover - network dependent
            results[name] = {"error": str(e)}
    return results


# ---------- Kubernetes actions ----------

def _get_k8s_apps_client() -> k8s_client.AppsV1Api:
    context = os.environ.get("KUBE_CONTEXT") or None
    k8s_config.load_kube_config(context=context)
    return k8s_client.AppsV1Api()


def rollback_deployment(service: str, namespace: str | None = None) -> str:
    """Roll back a Deployment to its previous ReplicaSet revision."""
    namespace = namespace or os.environ.get("KUBE_NAMESPACE", "default")
    apps = _get_k8s_apps_client()

    # TODO: real rollback needs the revision history; k8s python client
    # doesn't have a one-line "undo" like `kubectl rollout undo`.
    # Simplest correct approach: shell out to kubectl, or walk
    # ReplicaSet history via apps.list_namespaced_replica_set().
    return f"[stub] would roll back deployment/{service} in ns/{namespace}"


def restart_deployment(service: str, namespace: str | None = None) -> str:
    """Trigger a rolling restart by patching a restart annotation."""
    namespace = namespace or os.environ.get("KUBE_NAMESPACE", "default")
    apps = _get_k8s_apps_client()

    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "autoops/restartedAt": datetime.utcnow().isoformat()
                    }
                }
            }
        }
    }
    apps.patch_namespaced_deployment(name=service, namespace=namespace, body=patch)
    return f"restarted deployment/{service} in ns/{namespace}"


def scale_deployment(service: str, replicas: int, namespace: str | None = None) -> str:
    namespace = namespace or os.environ.get("KUBE_NAMESPACE", "default")
    apps = _get_k8s_apps_client()
    apps.patch_namespaced_deployment_scale(
        name=service, namespace=namespace, body={"spec": {"replicas": replicas}}
    )
    return f"scaled deployment/{service} to {replicas} replicas"


# ---------- Human escalation ----------

def notify_human(message: str) -> str:
    """Send an alert to a human. TODO: wire up SLACK_WEBHOOK_URL with an
    actual HTTP POST once you're ready to test end-to-end."""
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print(f"[notify_human - no webhook configured] {message}")
        return "logged locally (no webhook configured)"
    # TODO: requests.post(webhook, json={"text": message})
    return "sent to slack (stub)"
