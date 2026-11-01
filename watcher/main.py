import json
import os
import pathlib
import time

import rules
from collectors import k8s
from incident import create_incident, next_incident_id

NAMESPACE = os.getenv("NAMESPACE", "default")
SERVICE = os.getenv("SERVICE", "autotops-demo")
INTERVAL = int(os.getenv("INTERVAL", "10"))
OUT_DIR = pathlib.Path(os.getenv("INCIDENT_DIR", str(pathlib.Path.home() / "autotops" / "incidents")))
ACTIVE_STATE = pathlib.Path(os.getenv("INCIDENT_STATE_FILE", str(OUT_DIR / ".active_incidents.json")))


def _key_id(key):
    """Stable JSON representation so deduplication survives process restarts."""
    return json.dumps(key, separators=(",", ":"), sort_keys=True)


def load_active_incidents(path=ACTIVE_STATE):
    try:
        data = json.loads(path.read_text())
        return set(data.get("active", []))
    except FileNotFoundError:
        return set()
    except (OSError, ValueError, AttributeError):
        print(f"[WATCHER] could not read active incident state: {path}", flush=True)
        return set()


def save_active_incidents(active, path=ACTIVE_STATE):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"active": sorted(active)}, indent=2))
    tmp.replace(path)


def emit(key, failure_type, severity, pod, status, metrics, active):
    key_id = _key_id(key)
    if key_id in active:
        print(f"[WATCHER] existing active incident suppresses duplicate: {failure_type} pod={status.get('name')}", flush=True)
        return False

    name = pod.metadata.name
    evidence = {
        "pod_status": status,
        "kubernetes_events": k8s.get_events(NAMESPACE, name),
        "metrics": metrics,
        "logs": k8s.get_logs(NAMESPACE, name),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    incident = create_incident(next_incident_id(OUT_DIR), SERVICE, NAMESPACE,
                               failure_type, severity, evidence)
    path = OUT_DIR / f"{incident['incident_id']}.json"
    try:
        with path.open("x") as f:
            json.dump(incident, f, indent=2)
    except FileExistsError:
        print(f"[WATCHER] incident path already exists: {path}", flush=True)
        return False

    active.add(key_id)
    print(f"[WATCHER] INCIDENT {incident['incident_id']} {failure_type} ({severity}) -> {path}", flush=True)
    return True


def run_once():
    pods = k8s.get_pods(NAMESPACE, SERVICE)
    if not pods:
        print("[WATCHER] no pods found; retaining active incident state", flush=True)
        return

    active = load_active_incidents()
    detected = set()

    for pod in pods:
        status = k8s.pod_status(pod)
        containers = status["containers"]
        restarts = max([c["restart_count"] for c in containers] or [0])
        pod_uid = status.get("uid") or status.get("name")

        events = k8s.get_events(NAMESPACE, status["name"])
        sev = rules.check_crashloop(status, events)
        if sev:
            key = ("CrashLoopBackOff", pod_uid)
            key_id = _key_id(key)
            detected.add(key_id)
            emit(key, "CrashLoopBackOff", sev, pod, status,
                 {"restart_count": restarts}, active)

        sev = rules.check_oom(status)
        if sev:
            oom_times = [c.get("last_terminated_at") for c in containers
                         if c.get("last_terminated_reason") == "OOMKilled"]
            key = ("OOMKilled", pod_uid, tuple(oom_times))
            detected.add(_key_id(key))
            emit(key, "OOMKilled", sev, pod, status,
                 {"restart_count": restarts}, active)

    # Service-level metric alert is evaluated once, independently of pod count.
    sev, metrics = rules.check_5xx()
    if sev:
        key = ("HighHTTP5xxRate",)
        detected.add(_key_id(key))
        emit(key, "HighHTTP5xxRate", sev, pods[0], k8s.pod_status(pods[0]),
             metrics, active)

    # Persist only currently detected failures. Once a failure is no longer
    # observed, its key is cleared so a later recurrence can create a new incident.
    save_active_incidents(detected)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[WATCHER] started: service={SERVICE} namespace={NAMESPACE} interval={INTERVAL}s", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[WATCHER] error: {e}", flush=True)
        time.sleep(INTERVAL)
