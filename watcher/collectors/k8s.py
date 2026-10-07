import re
from kubernetes import client, config

try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

v1 = client.CoreV1Api()


def get_pods(namespace, app_label):
    return v1.list_namespaced_pod(namespace, label_selector=f"app={app_label}").items


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
        })
    return {
        "name": pod.metadata.name,
        "phase": pod.status.phase,
        "containers": containers,
    }


def get_events(namespace, pod_name, limit=10):
    events = v1.list_namespaced_event(
        namespace, field_selector=f"involvedObject.name={pod_name}"
    ).items

    def when(e):
        return e.last_timestamp or e.event_time or e.metadata.creation_timestamp

    events.sort(key=when, reverse=True)
    return [
        {"type": e.type, "reason": e.reason, "message": e.message, "count": e.count}
        for e in events[:limit]
    ]


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def get_logs(namespace, pod_name, lines=30):
    noise = ("GET /health", "GET /metrics")
    for previous in (False, True):
        try:
            resp = v1.read_namespaced_pod_log(
                pod_name, namespace, tail_lines=300, previous=previous,
                _preload_content=False,
            )
            text = ANSI.sub("", resp.data.decode("utf-8", errors="replace"))
            useful = [l for l in text.splitlines() if l.strip() and not any(n in l for n in noise)]
            if useful:
                return useful[-lines:]
        except Exception:
            continue
    return ["no logs available"]
