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
    status_groups = (
        ("application", getattr(pod.status, "container_statuses", None)),
        ("init", getattr(pod.status, "init_container_statuses", None)),
        ("ephemeral", getattr(pod.status, "ephemeral_container_statuses", None)),
    )
    for container_type, statuses in status_groups:
        for cs in statuses or []:
            waiting = cs.state.waiting if cs.state else None
            last = cs.last_state.terminated if cs.last_state else None
            containers.append({
                "name": cs.name,
                "container_type": container_type,
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


def _read_log_stream(v1, namespace, pod_name, previous, lines, container=None):
    """Read one container log stream without hiding errors from the caller."""
    options = {
        "tail_lines": 300,
        "previous": previous,
        "_preload_content": False,
    }
    if container:
        options["container"] = container
    resp = v1.read_namespaced_pod_log(pod_name, namespace, **options)
    text = ANSI.sub("", resp.data.decode("utf-8", errors="replace"))
    noise = ("GET /health", "GET /metrics")
    useful = [
        line for line in text.splitlines()
        if line.strip() and not any(item in line for item in noise)
    ]
    return useful[-lines:]


def _log_error_details(error):
    """Return a compact, serializable description of a Kubernetes log API error."""
    status = getattr(error, "status", None)
    message = str(getattr(error, "reason", "") or error).strip()
    return {
        "type": type(error).__name__,
        "http_status": status,
        "message": message[:500],
    }


def get_log_evidence(namespace, pod_name, lines=30, container_names=None):
    """Collect logs per container and report the outcome of every API request.

    current_logs and previous_logs remain flat string arrays for existing
    diagnostic consumers. log_collection adds per-container observability
    metadata without turning collection errors into application evidence.
    """
    v1 = get_kubernetes_client()
    names = list(dict.fromkeys(
        name for name in (container_names or []) if isinstance(name, str) and name
    ))
    # Preserve the old default-container behavior for callers that do not
    # provide container names.
    targets = names or [None]
    result = {
        "current_logs": [],
        "previous_logs": [],
        "log_collection": {"containers": {}},
    }

    for container in targets:
        label = container or "default"
        details = {}
        for previous, key in ((False, "current_logs"), (True, "previous_logs")):
            try:
                collected = _read_log_stream(
                    v1, namespace, pod_name, previous, lines, container=container
                )
                result[key].extend(collected)
                details["previous" if previous else "current"] = {
                    "status": "collected" if collected else "empty",
                    "line_count": len(collected),
                }
            except Exception as error:
                error_details = _log_error_details(error)
                # Kubernetes commonly returns 400/404 when no previous
                # container instance exists. Record this as unavailable,
                # not as an application failure or an API outage.
                unavailable = previous and error_details["http_status"] in (400, 404)
                details["previous" if previous else "current"] = {
                    "status": "unavailable" if unavailable else "error",
                    "error": error_details,
                }
        result["log_collection"]["containers"][label] = details

    # Keep the original combined field for consumers using the v1 schema.
    # An empty list accurately means no log lines were collected; unlike a
    # placeholder string, it cannot be mistaken for application evidence.
    result["logs"] = result["current_logs"] + result["previous_logs"]
    return result

def get_logs(namespace, pod_name, lines=30):
    """Backward-compatible combined log collector."""
    return get_log_evidence(namespace, pod_name, lines)["logs"]
