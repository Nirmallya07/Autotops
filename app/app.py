from flask import Flask, jsonify, Response, request
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import os
import threading

app = Flask(__name__)

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

_allocations = []
_alloc_lock = threading.Lock()


@app.after_request
def after_request(response):
    endpoint = request.path
    method = request.method
    status = str(response.status_code)
    HTTP_REQUESTS.labels(method=method, endpoint=endpoint, status=status).inc()
    return response


@app.route("/")
def home():
    return jsonify({
        "project": "AutoTops",
        "message": "Autonomous Troubleshooting and Operations Platform",
        "status": "running"
    })


@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/failure")
def failure():
    return jsonify({
        "status": "failure",
        "message": "Intentional test failure for AutoTops"
    }), 500


@app.route("/crash")
def crash():
    # Crash the process immediately to allow Kubernetes to detect CrashLoopBackOff on restart.
    os._exit(1)


@app.route("/alloc")
def alloc():
    """
    Allocate specified MB of memory and retain it in process memory.
    Query parameter: mb (int) — number of megabytes to allocate.
    Safety: capped at 1024 MB to avoid accidental host OOM in dev.
    Example: /alloc?mb=200
    """
    mb = request.args.get("mb", "10")
    try:
        mb = int(mb)
    except ValueError:
        return jsonify({"error": "invalid mb parameter"}), 400

    if mb <= 0:
        return jsonify({"error": "mb must be > 0"}), 400

    if mb > 1024:
        return jsonify({"error": "mb too large; max 1024"}), 400

    size = mb * 1024 * 1024
    with _alloc_lock:
        _allocations.append(bytearray(size))

    return jsonify({"allocated_mb": mb, "total_allocations": len(_allocations)}), 200


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)