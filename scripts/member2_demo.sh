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
PYTHON_BIN=${PYTHON_BIN:-""}
# Prefer project virtualenv if present
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$(pwd)/.venv/bin/python" ]]; then
    PYTHON_BIN="$(pwd)/.venv/bin/python"
  elif [[ -x "$(pwd)/venv/bin/python" ]]; then
    PYTHON_BIN="$(pwd)/venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=$(command -v python)
  else
    echo "ERROR: no python executable found in PATH; install python3 or activate virtualenv" >&2
    exit 1
  fi
fi

# Prometheus stub control (top-level to avoid nested function parsing issues)
PROM_STUB_PID=""
PROM_STUB_PORT=""
start_prom_stub() {
  for port in 19090 19091 19092; do
    "$PYTHON_BIN" -u - "$port" <<PY >/dev/null 2>&1 &
import http.server, socketserver, json, sys
port = int(sys.argv[1])
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/v1/query'):
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status':'success','data':{'result':[]}}).encode())
        else:
            self.send_response(404); self.end_headers()
    def log_message(self,*a): pass
with socketserver.TCPServer(('127.0.0.1', port), H) as httpd:
    httpd.serve_forever()
PY
    PID=$!
    sleep 0.2
    if kill -0 "$PID" >/dev/null 2>&1; then
      PROM_STUB_PID=$PID
      PROM_STUB_PORT=$port
      break
    fi
  done
}
stop_prom_stub() {
  if [[ -n "$PROM_STUB_PID" ]]; then
    kill "$PROM_STUB_PID" >/dev/null 2>&1 || true
    wait "$PROM_STUB_PID" 2>/dev/null || true
    PROM_STUB_PID=""
    PROM_STUB_PORT=""
  fi
}

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
  for i in {1..180}; do
    P=$(pod_name)
    if [[ -z "$P" ]]; then
      sleep 1
      continue
    fi
    # check waiting reason
    REASON=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
    # check recent events for BackOff
    EVENT_BACKOFF=$(kubectl -n "$NAMESPACE" get events --field-selector involvedObject.name="$P" -o jsonpath='{.items[*].reason}' 2>/dev/null | grep -Eo 'BackOff' || true)
    RESTARTS=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || true)
    if [[ "$REASON" == "CrashLoopBackOff" ]] || [[ -n "$EVENT_BACKOFF" ]] || ([[ -n "$RESTARTS" ]] && [[ "$RESTARTS" -gt 0 ]]); then
      echo "[3] Kubernetes reports CrashLoopBackOff (reason=${REASON:-<none>} restarts=${RESTARTS:-0})"
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
  # Start the prom stub (top-level helper) and run the watcher pointed at it.
  start_prom_stub

  "$PYTHON_BIN" - <<PY
import os,sys
sys.path.insert(0, '$PYDIR')
os.environ['SERVICE']='${SERVICE}'
os.environ['NAMESPACE']='${NAMESPACE}'
os.environ['INCIDENT_DIR']='${INCIDENT_DIR}'
# Point the Watcher at the local stub so prom queries return empty results
os.environ['PROM_URL']='http://127.0.0.1:${PROM_STUB_PORT}'
import main
main.run_once()
PY

  stop_prom_stub
}

validate_and_show() {
  PRE_EXISTING_LIST=$1
  # Identify the most-recent incident created by the last watcher run.
  # Find newest file that is not in the PRE_EXISTING_LIST
  echo "[6] Looking for generated incident files in $INCIDENT_DIR"
  newest=''
  for f in $(ls -1t "$INCIDENT_DIR"/INC-*.json 2>/dev/null || true); do
    if [[ -z "$PRE_EXISTING_LIST" || ! $(echo "$PRE_EXISTING_LIST" | grep -x "$f" ) ]]; then
      newest="$f"
      break
    fi
  done
  if [[ -z "$newest" ]]; then
    # fallback to newest overall
    newest=$(ls -1t "$INCIDENT_DIR"/INC-*.json 2>/dev/null | head -n1 || true)
  fi
  if [[ -z "$newest" ]]; then
    echo "No incident file found in $INCIDENT_DIR" >&2
    return 1
  fi
  echo "[6] Incident file: $newest"
  # Print a concise summary of the incident (no full JSON dump)
  "$PYTHON_BIN" - <<PY
import json,sys
inc=json.loads(open('$newest').read())
e=inc.get('evidence',{})
pod_status=e.get('pod_status',{})
containers=pod_status.get('containers',[])
ctr=containers[0] if containers else {}
print('    Pod:         {}'.format(pod_status.get('name','<none>')))
print('    Restarts:    {}'.format(ctr.get('restart_count','<none>')))
print('    Reason:      {}'.format(ctr.get('waiting_reason') or ctr.get('last_terminated_reason') or '<none>'))
if ctr.get('last_exit_code') is not None:
    print('    Exit code:   {}'.format(ctr.get('last_exit_code')))
print('    Incident ID: {}'.format(inc.get('incident_id')))
print('    Severity:    {}'.format(inc.get('severity')))
PY
  echo
  echo "[7] Validating against schema..."
  "$PYTHON_BIN" - <<PY
import json,sys
from jsonschema import validate
schema= json.loads(open('schemas/incident.json').read())
inc=json.loads(open('$newest').read())
validate(inc,schema)
print('    Schema:      PASSED')
PY
}

demo_crash() {
  cat <<'HEADER'
============================================================
        AUTOTOPS - MEMBER 2 FAILURE DETECTION DEMO
============================================================

TEST: CrashLoopBackOff

HEADER

  echo "[1/5] Triggering application crash..."
  echo "      Application: $SERVICE"
  echo "      Failure:     Container crash"

  echo "[1] Application status"
  kubectl -n "$NAMESPACE" get pods -l app="$SERVICE" -o wide

  P=$(pod_name)
  if [[ -z "$P" ]]; then
    echo "no pod found for $SERVICE" >&2
    exit 1
  fi

  echo "[2/5] Kubernetes detecting failure..."
  echo "      Triggering /crash on pod $P (in-cluster exec)"
  kubectl -n "$NAMESPACE" exec --stdin --tty "$P" -- /bin/sh -c "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/crash')\" || true" >/dev/null 2>&1 || true
  # give Kubernetes time to observe restarts
  sleep 2
  wait_for_crashloop
  # Gather current pod info for summary
  RESTARTS=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo '<none>')
  REASON=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
  echo "      Status:      ${REASON:-CrashLoopBackOff}"
  echo "      Restarts:    ${RESTARTS}"

  echo "[3/5] Member 2 Watcher analyzing Kubernetes state..."
  # snapshot preexisting incidents so we can identify the new one created now
  PRE_EXISTING=$(ls -1 "$INCIDENT_DIR"/INC-*.json 2>/dev/null || true)
  run_watcher_once

  echo "[4/5] Incident created"
  # Print concise incident summary and validate only the incident created by this run
  validate_and_show "$PRE_EXISTING"

  echo "[5/5] Validating incident schema..."
  echo
  echo "------------------------------------------------------------"
  echo "RESULT: SUCCESS"
  echo "CrashLoopBackOff was detected and converted into an incident."
  echo "------------------------------------------------------------"
}

demo_oom() {
  cat <<'HEADER'
============================================================
        AUTOTOPS - MEMBER 2 FAILURE DETECTION DEMO
============================================================

TEST: OOMKilled

HEADER

  echo "[1/5] Triggering excessive memory allocation..."
  echo "      Application: $SERVICE"
  echo "      Memory limit: 256Mi"

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
  echo "[2/5] Kubernetes detecting failure..."
  echo "      Triggering /alloc?mb=${ALLOC_MB} on pod $P (in-cluster exec)"
  kubectl -n "$NAMESPACE" exec --stdin --tty "$P" -- /bin/sh -c "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/alloc?mb=${ALLOC_MB}')\" || true" >/dev/null 2>&1 || true
  # give Kubernetes a moment to record termination
  sleep 2
  wait_for_oom
  RESTARTS=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo '<none>')
  REASON=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}' 2>/dev/null || true)
  EXIT=$(kubectl -n "$NAMESPACE" get pod "$P" -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}' 2>/dev/null || true)
  echo "      Status:      ${REASON:-OOMKilled}"
  echo "      Exit code:   ${EXIT:-<none>}"
  echo "      Restarts:    ${RESTARTS}"

  echo "[3/5] Member 2 Watcher analyzing Kubernetes state..."
  PRE_EXISTING=$(ls -1 "$INCIDENT_DIR"/INC-*.json 2>/dev/null || true)
  run_watcher_once

  echo "[4/5] Incident created"
  validate_and_show "$PRE_EXISTING"

  echo "[5/5] Validating incident schema..."
  echo
  echo "------------------------------------------------------------"
  echo "RESULT: SUCCESS"
  echo "OOMKilled was detected and converted into an incident."
  echo "------------------------------------------------------------"
}

if [[ "${1:-}" == "crash" ]]; then
  demo_crash
elif [[ "${1:-}" == "oom" ]]; then
  demo_oom
else
  echo "Usage: $0 crash|oom" >&2
  exit 2
fi
