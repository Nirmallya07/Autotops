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
COOLDOWN = int(os.getenv("COOLDOWN", "30"))


def _key_id(key):
    return json.dumps(key, separators=(",", ":"), sort_keys=True)


def load_active_incidents(path=ACTIVE_STATE):
    try:
        data = json.loads(path.read_text())
        # The previous implementation stored a list with no timestamps. Those
        # entries could remain stale forever, so discard that legacy format.
        if not isinstance(data.get("active"), dict):
            return {}
        return {key: float(ts) for key, ts in data["active"].items()}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, AttributeError, TypeError):
        print(f"[WATCHER] could not read active incident state: {path}", flush=True)
        return {}


def save_active_incidents(active, path=ACTIVE_STATE):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"active": active}, indent=2))
    tmp.replace(path)


def emit(key, failure_type, severity, pod, status, metrics, active):
    now = time.time()
    key_id = _key_id(key)
    last_emitted = active.get(key_id)
    if last_emitted is not None and now - last_emitted < COOLDOWN:
        print(f"[WATCHER] duplicate suppressed ({int(COOLDOWN - (now - last_emitted))}s cooldown): {failure_type} pod={status.get('name')}", flush=True)
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

    active[key_id] = now
    print(f"[WATCHER] INCIDENT {incident['incident_id']} {failure_type} ({severity}) -> {path}", flush=True)
    return True


def run_once():
    pods = k8s.get_pods(NAMESPACE, SERVICE)
    if not pods:
        print("[WATCHER] no pods found; retaining incident cooldown state", flush=True)
        return

    active = load_active_incidents()
    now = time.time()
    # Expire old suppression records so a later recurrence is not blocked forever.
    active = {key: ts for key, ts in active.items() if now - ts < COOLDOWN}

    for pod in pods:
        status = k8s.pod_status(pod)
        containers = status["containers"]
        restarts = max([c["restart_count"] for c in containers] or [0])
        pod_uid = status.get("uid") or status.get("name")

        events = k8s.get_events(NAMESPACE, status["name"])
        sev = rules.check_crashloop(status, events)
        if sev:
            emit(("CrashLoopBackOff", pod_uid), "CrashLoopBackOff", sev,
                 pod, status, {"restart_count": restarts}, active)

        sev = rules.check_oom(status)
        if sev:
            oom_times = [c.get("last_terminated_at") for c in containers
                         if c.get("last_terminated_reason") == "OOMKilled"]
            emit(("OOMKilled", pod_uid, tuple(oom_times)), "OOMKilled", sev,
                 pod, status, {"restart_count": restarts}, active)

    sev, metrics = rules.check_5xx()
    if sev:
        emit(("HighHTTP5xxRate",), "HighHTTP5xxRate", sev,
             pods[0], k8s.pod_status(pods[0]), metrics, active)

    save_active_incidents(active)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[WATCHER] started: service={SERVICE} namespace={NAMESPACE} interval={INTERVAL}s", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[WATCHER] error: {e}", flush=True)
        time.sleep(INTERVAL)
