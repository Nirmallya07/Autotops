# AutoOps — a self-healing CI/CD platform

AutoOps watches your services, figures out when something's wrong, and fixes it
without you getting paged at 2am — a human only steps in when the agent isn't
confident enough to act alone.

## The mental model

Think of it like a hospital:

| Component     | Role                        | What it actually is             |
|----------------|------------------------------|----------------------------------|
| Prometheus     | Vitals monitor               | Scrapes metrics continuously     |
| Alertmanager   | Nurse who notices a spike    | Fires alerts on rule breach      |
| LangGraph agent| The doctor's decision loop   | Observe → Diagnose → Decide → Act → Verify |
| Claude API     | The diagnostic brain         | Reasons about *what's* wrong and *what to do* |
| kubectl/Terraform | The treatment              | Executes the fix (rollback, restart, scale, provision) |
| Grafana        | The chart at the foot of the bed | Humans watch it, agent doesn't need to |

The core loop lives in `agents/graph.py`. Everything else exists to feed that
loop data or give it hands to act with.

## Architecture

```
                 ┌──────────────┐
                 │  Prometheus  │◄────── scrapes ──── sample app / cluster
                 └──────┬───────┘
                        │ metrics query
                        ▼
                 ┌──────────────┐        ┌──────────────┐
                 │ LangGraph    │──────► │  Claude API  │
                 │ agent loop   │ ◄──────│ (reasoning)  │
                 └──────┬───────┘        └──────────────┘
                        │ tool calls (kubectl, terraform, notify)
                        ▼
                 ┌──────────────┐
                 │  Kubernetes  │
                 │   cluster    │
                 └──────────────┘
```

`api/main.py` is a thin FastAPI wrapper: it exposes `/webhook/alert` so
Alertmanager can trigger the agent, and `/healthz` for its own liveness.

## Repo layout

```
autoops/
├── agents/             LangGraph agent: state, graph, tools, Claude client
├── api/                FastAPI service — entrypoint & alert webhook
├── monitoring/         Prometheus + Grafana config
├── k8s/                Kubernetes manifests (sample target app)
├── infra/terraform/    IaC for a local kind cluster (swap for cloud later)
├── tests/              Unit tests for the agent graph
└── scripts/            One-shot setup scripts
```

## Local setup (kind + docker-compose)

1. **Prereqs**: Docker Desktop, `kind`, `kubectl`, `terraform`, Python 3.11+.

2. **Clone & install**
   ```bash
   cd autoops
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # then paste in your ANTHROPIC_API_KEY
   ```

3. **Bring up monitoring stack locally**
   ```bash
   docker compose up -d
   ```
   Prometheus → http://localhost:9090, Grafana → http://localhost:3000 (admin/admin)

4. **Spin up a local cluster + sample app**
   ```bash
   bash scripts/setup_local.sh
   ```

5. **Run the agent API**
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```

6. **Trigger it manually** (before wiring real alerts) to sanity-check the loop:
   ```bash
   curl -X POST localhost:8000/webhook/alert \
     -H "Content-Type: application/json" \
     -d '{"alert_name": "HighErrorRate", "service": "sample-app", "severity": "warning"}'
   ```

## Status

This is the scaffold — the graph nodes in `agents/graph.py` are stubbed with
TODOs. Next step: fill in `diagnose_node` and `decide_node` with real
Prometheus queries + Claude reasoning.

## AI assistance disclosure

Scaffold generated with Claude's help (repo structure, boilerplate, skeleton
code). Logic inside each node still needs to be written and understood before
it's "yours" — don't submit/demo code you can't explain.
