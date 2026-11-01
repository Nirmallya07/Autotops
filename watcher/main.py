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

reported = {}
COOLDOWN = int(os.getenv("COOLDOWN", "300"))


def emit(key, failure_type, severity, pod, status, metrics):
    now = time.time()
    if key in reported and now - reported[key] < COOLDOWN:
        return
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
    # Exclusive creation prevents silently overwriting an existing incident.
    try:
        with path.open("x") as f:
            json.dump(incident, f, indent=2)
    except FileExistsError:
        print(f"[WATCHER] incident path already exists: {path}", flush=True)
        return
    reported[key] = now
    print(f"[WATCHER] INCIDENT {incident['incident_id']} {failure_type} ({severity}) -> {path}", flush=True)


def run_once():
    pods = k8s.get_pods(NAMESPACE, SERVICE)
    if not pods:
        print("[WATCHER] no pods found", flush=True)
        return

    for pod in pods:
        status = k8s.pod_status(pod)
        containers = status["containers"]
        restarts = max([c["restart_count"] for c in containers] or [0])
        pod_uid = status.get("uid") or status.get("name")

        events = k8s.get_events(NAMESPACE, status["name"])
        sev = rules.check_crashloop(status, events)
        if sev:
            emit(("CrashLoopBackOff", pod_uid), "CrashLoopBackOff", sev,
                 pod, status, {"restart_count": restarts})

        sev = rules.check_oom(status)
        if sev:
            oom_times = [c.get("last_terminated_at") for c in containers
                         if c.get("last_terminated_reason") == "OOMKilled"]
            emit(("OOMKilled", pod_uid, tuple(oom_times)), "OOMKilled", sev,
                 pod, status, {"restart_count": restarts})

    # Service-level metric alert is evaluated once, independently of pod count.
    sev, metrics = rules.check_5xx()
    if sev:
        emit(("HighHTTP5xxRate",), "HighHTTP5xxRate", sev,
             pods[0], k8s.pod_status(pods[0]), metrics)
    else:
        reported.pop(("HighHTTP5xxRate",), None)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[WATCHER] started: service={SERVICE} namespace={NAMESPACE} interval={INTERVAL}s", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[WATCHER] error: {e}", flush=True)
        time.sleep(INTERVAL)
