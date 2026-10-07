# AutoTops — Member 1 (DevOps & Infrastructure)

Overview
- Demo Flask app, containerized, deployable to local Kubernetes.
- Instrumented with Prometheus-compatible metrics (`http_requests_total`).
- Controlled failure endpoints for demo: `/failure` (500), `/crash` (process exit), `/alloc?mb=N` (memory allocation).

Prerequisites (local)
- `docker`
- `kubectl`
- `minikube` (or `kind`)
- `python 3.12` (for tests)

Quick local verification
1) Run tests:
	`pytest`

2) Build image:
	`docker build -t autotops-demo:0.1 .`

3) Deploy to minikube:
	`minikube start`
	`./demo/run_demo.sh`

4) Verify endpoints:
	`curl http://localhost:5000/health`
	`curl http://localhost:5000/metrics`
	`curl http://localhost:5000/failure`

Member 2 (Watcher) integration contract
- Service name: `autotops-demo`
- Deployment name: `autotops-demo`
- Pod label: `app=autotops-demo`
- Namespace: `default`
- Metrics endpoint: `/metrics` (on port 5000)
- Key metric: `http_requests_total` with labels `method`, `endpoint`, `status`
- Watcher Prometheus query expected to work: `http_requests_total{status=~"5.."}`
- Logs: available via `kubectl logs <pod>`
- Evidence available: pod status, restartCount, container termination reason, events, metrics, logs

CI
- GitHub Actions workflow runs tests, builds Docker image (tagged by commit SHA), and runs Trivy scan (no push).

Failure injection endpoints
- `/failure` → returns HTTP 500 (does not kill container)
- `/crash` → exits process (Kubernetes will restart; repeated crashes can produce CrashLoopBackOff)
- `/alloc?mb=N` → allocate N MB retained in process memory (used to demonstrate OOMKilled when N > container memory limit). Use with caution.

For detailed commands, see `demo/run_demo.sh` and `.github/workflows/ci.yml`
