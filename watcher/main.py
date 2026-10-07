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
    reported[key] = now
    name = pod.metadata.name
    evidence = {
        "pod_status": status,
        "kubernetes_events": k8s.get_events(NAMESPACE, name),
        "metrics": metrics,
        "logs": k8s.get_logs(NAMESPACE, name),
    }
    incident = create_incident(next_incident_id(OUT_DIR), SERVICE, NAMESPACE,
                               failure_type, severity, evidence)
    path = OUT_DIR / f"{incident['incident_id']}.json"
    path.write_text(json.dumps(incident, indent=2))
    print(f"[WATCHER] INCIDENT {incident['incident_id']} {failure_type} ({severity}) -> {path}", flush=True)


def run_once():
    pods = k8s.get_pods(NAMESPACE, SERVICE)
    if not pods:
        print("[WATCHER] no pods found", flush=True)
        return
    pod = pods[0]
    status = k8s.pod_status(pod)
    restarts = max([c["restart_count"] for c in status["containers"]] or [0])

    sev = rules.check_crashloop(status)
    if sev:
        emit(("CrashLoopBackOff",), "CrashLoopBackOff", sev, pod, status, {"restart_count": restarts})

    sev = rules.check_oom(status)
    if sev:
        emit(("OOMKilled", restarts), "OOMKilled", sev, pod, status, {"restart_count": restarts})

    sev, metrics = rules.check_5xx()
    if sev:
        emit(("HighHTTP5xxRate",), "HighHTTP5xxRate", sev, pod, status, metrics)
    else:
        reported.pop(("HighHTTP5xxRate",), None)


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    print(f"[WATCHER] started: service={SERVICE} namespace={NAMESPACE} interval={INTERVAL}s", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[WATCHER] error: {e}", flush=True)
        time.sleep(INTERVAL)
