# AutoTops Operations Dashboard

Local faculty-demo dashboard for the V1 prototype. It reads live Kubernetes state through local kubectl, displays incident JSON files from the existing Member 2 workflow, and starts the existing CrashLoopBackOff/OOMKilled demos.

## Start

Ensure Minikube/Kubernetes and the application are running, then from the repository root:

    chmod +x scripts/start_dashboard.sh
    ./scripts/start_dashboard.sh

Open http://127.0.0.1:8000

## Faculty demo

1. Show Application, Kubernetes and Watcher cards.
2. Click Trigger CrashLoopBackOff.
3. Explain that the dashboard starts scripts/member2_demo.sh crash.
4. Watch the pod restart state change.
5. Show the incident ID and severity after the watcher runs.
6. Select **View AI Analysis** on the incident card to inspect diagnosis, live health,
   remediation proposal, approval requirement, and lifecycle status.
7. Repeat with OOMKilled if time permits.

The dashboard intentionally reuses the tested demo workflow instead of creating a second failure-detection implementation. The demo script runs the AI pipeline after Watcher incident validation and stores its result under
`scripts/member2_incidents/analysis/` and lifecycle history under
`scripts/member2_incidents/lifecycle/`. The dashboard reads these files through
`/api/incidents/<incident-id>`; it does not run the AI pipeline itself.
