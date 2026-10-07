#!/usr/bin/env bash
set -euo pipefail

# Demo runner for Member2 watcher using the real cluster
# Usage: ./scripts/member2_demo.sh crash|oom

HERE=$(cd "$(dirname "$0")" && pwd)
INCIDENT_DIR="$HERE/member2_incidents"
mkdir -p "$INCIDENT_DIR"

SERVICE=${SERVICE:-autotops-demo}
NAMESPACE=${NAMESPACE:-default}
PF_PID=""

port_forward_pod() {
  POD=$1
  PORT=$2
  kubectl -n "$NAMESPACE" port-forward "pod/$POD" ${PORT}:${PORT} >/dev/null 2>&1 &
  PF_PID=$!
  # give it a moment
  sleep 1
}

stop_pf() {
  if [[ -n "$PF_PID" ]]; then
    kill "$PF_PID" >/dev/null 2>&1 || true
    wait "$PF_PID" 2>/dev/null || true
    PF_PID=""
  fi
}

pod_name() {
  kubectl -n "$NAMESPACE" get pods -l app="$SERVICE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

wait_for_crashloop() {
  echo "[3] Waiting for CrashLoopBackOff..."
  for i in {1..60}; do
    P=$(pod_name)
    if [[ -z "$P" ]]; then
      sleep 1
      continue
    fi
    REASON=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
    if [[ "$REASON" == "CrashLoopBackOff" ]]; then
      echo "[3] Kubernetes reports CrashLoopBackOff"
      return 0
    fi
    sleep 1
  done
  echo "[3] Timeout waiting for CrashLoopBackOff" >&2
  return 1
}

wait_for_oom() {
  echo "[3] Waiting for OOMKilled (exitCode=137)..."
  for i in {1..60}; do
    P=$(pod_name)
    if [[ -z "$P" ]]; then
      sleep 1
      continue
    fi
    # check last terminated reason or exit code
    REASON=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null || true)
    EXIT=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null || true)
    if [[ "$REASON" == "OOMKilled" ]] || [[ "$EXIT" == "137" ]]; then
      echo "[3] Kubernetes reports OOMKilled (reason=${REASON:-<none>} exit=${EXIT:-<none>})"
      return 0
    fi
    sleep 1
  done
  echo "[3] Timeout waiting for OOMKilled" >&2
  return 1
}

run_watcher_once() {
  echo "[4] Running watcher once (will import watcher.main.run_once)"
  PYDIR="$(cd "$(dirname "$0")/.." && pwd)/watcher"
  python - <<PY
import os,sys
sys.path.insert(0, '$PYDIR')
os.environ['SERVICE']='${SERVICE}'
os.environ['NAMESPACE']='${NAMESPACE}'
os.environ['INCIDENT_DIR']='${INCIDENT_DIR}'
import main
main.run_once()
PY
}

validate_and_show() {
  echo "[6] Looking for generated incident files in $INCIDENT_DIR"
  ls -1 "$INCIDENT_DIR" || true
  for f in "$INCIDENT_DIR"/INC-*.json; do
    [[ -f "$f" ]] || continue
    echo "[6] Incident file: $f"
    cat "$f"
    echo
    echo "[7] Validating against schema..."
    python - <<PY
import json,sys,pathlib
from jsonschema import validate
schema= json.loads(open('schemas/incident.json').read())
inc=json.loads(open('$f').read())
validate(inc,schema)
print('Schema validation PASSED')
PY
  done
}

demo_crash() {
  echo "[1] Application status"
  kubectl -n "$NAMESPACE" get pods -l app="$SERVICE" -o wide

  P=$(pod_name)
  if [[ -z "$P" ]]; then
    echo "no pod found for $SERVICE" >&2
    exit 1
  fi

  echo "[2] Triggering /crash on pod $P"
  echo "[2] Triggering /crash on pod $P (in-cluster exec)"
  kubectl -n "$NAMESPACE" exec --stdin --tty "$P" -- /bin/sh -c "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/crash')\" || true" >/dev/null 2>&1 || true
  # give Kubernetes a moment to observe the failure
  sleep 2

  wait_for_crashloop

  echo "[4] Watcher started"
  run_watcher_once

  echo "[5] Incident detection + file generation"
  validate_and_show

  stop_pf
  trap - EXIT
}

demo_oom() {
  echo "[1] Recovering application (rollout restart)"
  kubectl -n "$NAMESPACE" rollout restart deployment/$SERVICE
  echo "Waiting for pod ready..."
  kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app=$SERVICE --timeout=120s

  P=$(pod_name)
  if [[ -z "$P" ]]; then
    echo "no pod found for $SERVICE" >&2
    exit 1
  fi

  ALLOC_MB=${ALLOC_MB:-600}
  echo "[2] Triggering /alloc?mb=${ALLOC_MB} on pod $P (in-cluster exec)"
  # Run the alloc request inside the container so the request does not depend on a
  # port-forward surviving the container termination. The exec may fail if the
  # container OOMs immediately, which is expected; that's fine — Kubernetes will
  # record the OOMKilled state.
  kubectl -n "$NAMESPACE" exec --stdin --tty "$P" -- /bin/sh -c "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/alloc?mb=${ALLOC_MB}')\" || true" >/dev/null 2>&1 || true
  # give Kubernetes a moment to record termination
  sleep 2

  wait_for_oom

  echo "[4] Watcher started"
  run_watcher_once

  echo "[5] Incident detection + file generation"
  validate_and_show

  stop_pf
  trap - EXIT
}

if [[ "${1:-}" == "crash" ]]; then
  demo_crash
elif [[ "${1:-}" == "oom" ]]; then
  demo_oom
else
  echo "Usage: $0 crash|oom" >&2
  exit 2
fi
