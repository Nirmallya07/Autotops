import re
from kubernetes import client, config

_v1 = None


def get_kubernetes_client():
    """Load Kubernetes configuration only when an API call is needed."""
    global _v1

    if _v1 is None:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        _v1 = client.CoreV1Api()

    return _v1


def get_pods(namespace, app_label):
    v1 = get_kubernetes_client()
    pods = v1.list_namespaced_pod(
        namespace, label_selector=f"app={app_label}"
    ).items
    # Ignore pods being deleted and inspect the newest active pod first.
    pods = [p for p in pods if not p.metadata.deletion_timestamp]
    return sorted(
        pods,
        key=lambda p: p.metadata.creation_timestamp.timestamp()
        if p.metadata.creation_timestamp else 0,
        reverse=True,
    )


def pod_status(pod):
    containers = []
    for cs in (pod.status.container_statuses or []):
        waiting = cs.state.waiting if cs.state else None
        last = cs.last_state.terminated if cs.last_state else None
        containers.append({
            "name": cs.name,
            "ready": cs.ready,
            "restart_count": cs.restart_count,
            "waiting_reason": waiting.reason if waiting else None,
            "last_terminated_reason": last.reason if last else None,
            "last_exit_code": last.exit_code if last else None,
            "last_terminated_at": last.finished_at.isoformat() if last and last.finished_at else None,
        })
    return {
        "name": pod.metadata.name,
        "uid": pod.metadata.uid,
        "phase": pod.status.phase,
        "containers": containers,
    }


def get_events(namespace, pod_name, limit=10):
    v1 = get_kubernetes_client()
    events = v1.list_namespaced_event(
        namespace, field_selector=f"involvedObject.name={pod_name}"
    ).items

    def when(e):
        return e.last_timestamp or e.event_time or e.metadata.creation_timestamp

    events.sort(key=when, reverse=True)
    return [
        {
            "type": e.type,
            "reason": e.reason,
            "message": e.message,
            "count": e.count,
            "last_timestamp": when(e).isoformat() if when(e) else None,
        }
        for e in events[:limit]
    ]


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _read_log_stream(v1, namespace, pod_name, previous, lines):
    """Read one container log stream without hiding errors from the caller."""
    resp = v1.read_namespaced_pod_log(
        pod_name,
        namespace,
        tail_lines=300,
        previous=previous,
        _preload_content=False,
    )
    text = ANSI.sub("", resp.data.decode("utf-8", errors="replace"))
    noise = ("GET /health", "GET /metrics")
    useful = [
        line for line in text.splitlines()
        if line.strip() and not any(item in line for item in noise)
    ]
    return useful[-lines:]


def get_log_evidence(namespace, pod_name, lines=30):
    """Collect current and previous container logs as separate evidence."""
    v1 = get_kubernetes_client()
    result = {"current_logs": [], "previous_logs": []}

    for previous, key in (
        (False, "current_logs"),
        (True, "previous_logs"),
    ):
        try:
            result[key] = _read_log_stream(
                v1, namespace, pod_name, previous, lines
            )
        except Exception:
            # A previous stream may not exist before the first restart.
            # Keep the other stream even if one request fails.
            result[key] = []

    # Keep the original logs array for compatibility with existing consumers.
    result["logs"] = result["current_logs"] + result["previous_logs"]
    if not result["logs"]:
        result["logs"] = ["no logs available"]
    return result


def get_logs(namespace, pod_name, lines=30):
    """Backward-compatible combined log collector."""
    return get_log_evidence(namespace, pod_name, lines)["logs"]
