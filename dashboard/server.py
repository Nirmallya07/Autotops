#!/usr/bin/env python3
import json, os, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
INCIDENT_DIR = ROOT / "scripts" / "member2_incidents"
RUNTIME_DIR = ROOT / "dashboard" / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
STATUS_FILE = RUNTIME_DIR / "demo_status.json"
LOG_FILE = RUNTIME_DIR / "demo.log"
SERVICE = os.environ.get("SERVICE", "autotops-demo")
NAMESPACE = os.environ.get("NAMESPACE", "default")

def run_cmd(args, timeout=10):
    try:
        p = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {"ok": p.returncode == 0, "stdout": p.stdout.strip(), "stderr": p.stderr.strip(), "code": p.returncode}
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e), "code": -1}

def set_status(state, demo="", message=""):
    STATUS_FILE.write_text(json.dumps({"state": state, "demo": demo, "message": message,
                                       "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2))

def get_status():
    if STATUS_FILE.exists():
        try: return json.loads(STATUS_FILE.read_text())
        except Exception: pass
    return {"state": "idle", "demo": "", "message": "Ready"}

def run_demo(kind):
    if get_status().get("state") == "running": return
    set_status("running", kind, "Running " + kind + " failure demo...")
    def worker():
        with LOG_FILE.open("w") as log:
            try:
                p = subprocess.Popen(["bash", "scripts/member2_demo.sh", kind], cwd=ROOT,
                                     stdout=log, stderr=subprocess.STDOUT, text=True)
                code = p.wait()
                set_status("success" if code == 0 else "error", kind,
                           "Demo completed successfully." if code == 0 else "Demo exited with code " + str(code) + ".")
            except Exception as e:
                log.write("\nDashboard error: " + str(e) + "\n")
                set_status("error", kind, str(e))
    threading.Thread(target=worker, daemon=True).start()

def kubectl_json(args):
    r = run_cmd(["kubectl", "-n", NAMESPACE] + args)
    if not r["ok"]: return None, r["stderr"] or "kubectl failed"
    try: return json.loads(r["stdout"]), ""
    except Exception as e: return None, str(e)

def cluster_status():
    pods, err = kubectl_json(["get", "pods", "-l", "app=" + SERVICE, "-o", "json"])
    if pods is None: return {"available": False, "error": err, "pods": []}
    result = []
    for p in pods.get("items", []):
        cs = (p.get("status", {}).get("containerStatuses") or [{}])[0]
        waiting = cs.get("state", {}).get("waiting") or {}
        terminated = cs.get("state", {}).get("terminated") or {}
        last = cs.get("lastState", {}).get("terminated") or {}
        result.append({"name": p.get("metadata", {}).get("name", ""), "phase": p.get("status", {}).get("phase", "Unknown"),
                       "ready": cs.get("ready", False), "restarts": cs.get("restartCount", 0),
                       "waiting_reason": waiting.get("reason", ""), "terminated_reason": terminated.get("reason", ""),
                       "last_reason": last.get("reason", ""), "last_exit": last.get("exitCode")})
    dep, _ = kubectl_json(["get", "deployment", SERVICE, "-o", "json"])
    return {"available": True, "pods": result,
            "deployment": {"ready": (dep or {}).get("status", {}).get("readyReplicas", 0),
                           "desired": (dep or {}).get("spec", {}).get("replicas", 0)}}

def incidents():
    items = []
    INCIDENT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INCIDENT_DIR.glob("INC-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        try:
            x = json.loads(path.read_text()); e = x.get("evidence", {}); pod = e.get("pod_status", {})
            ctr = (pod.get("containers") or [{}])[0]
            items.append({"incident_id": x.get("incident_id"), "failure_type": x.get("failure_type"),
                          "severity": x.get("severity"), "status": x.get("status"), "detected_at": x.get("detected_at"),
                          "pod": pod.get("name"), "restarts": ctr.get("restart_count"),
                          "reason": ctr.get("waiting_reason") or ctr.get("last_terminated_reason"),
                          "exit_code": ctr.get("last_exit_code")})
        except Exception: pass
    return items

def log_tail():
    if not LOG_FILE.exists(): return ""
    return "\n".join(LOG_FILE.read_text(errors="replace").splitlines()[-80:])

class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def serve_file(self, path, content_type):
        if not path.exists(): self.send_error(404); return
        body = path.read_bytes(); self.send_response(200); self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/": return self.serve_file(ROOT/"dashboard"/"index.html", "text/html; charset=utf-8")
        if path == "/dashboard.css": return self.serve_file(ROOT/"dashboard"/"dashboard.css", "text/css; charset=utf-8")
        if path == "/dashboard.js": return self.serve_file(ROOT/"dashboard"/"dashboard.js", "application/javascript; charset=utf-8")
        if path == "/api/status":
            return self.send_json({"service": SERVICE, "namespace": NAMESPACE, "cluster": cluster_status(),
                                   "incidents": incidents(), "demo": get_status(), "log": log_tail()})
        if path == "/api/health": return self.send_json({"ok": True, "service": SERVICE})
        self.send_error(404)
    def do_POST(self):
        path = urlparse(self.path).path
        if path in ("/api/demo/crash", "/api/demo/oom"):
            kind = "crash" if path.endswith("crash") else "oom"
            if get_status().get("state") == "running":
                return self.send_json({"ok": False, "message": "A demo is already running."}, 409)
            run_demo(kind); return self.send_json({"ok": True, "message": kind.upper() + " demo started."})
        self.send_error(404)
    def log_message(self, fmt, *args): return

if __name__ == "__main__":
    set_status("idle", "", "Ready")
    print("AutoTops dashboard: http://127.0.0.1:8000")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
