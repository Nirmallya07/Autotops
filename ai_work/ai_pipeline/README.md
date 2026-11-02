# AI Work — Incident Response Pipeline

This component consumes normalized incident JSON from the observability Watcher and runs diagnosis, validation, remediation proposal, approval handoff, recovery-result handling, and reporting.

## Modules

- `incident_loader.py` — loads and validates the shared incident JSON contract.
- `diagnoser/` — diagnostic context, mock/Ollama diagnosis, and output validation.
- `fixer/` — remediation proposals, approval manager, and execution handoff.
- `recovery/` — read-only Kubernetes health assessment, sampled recovery stability monitoring, and recovery-result validation.
- `reporter/` — incident report generation.
- `runner.py` — CLI entry point that processes a Watcher incident into a validated diagnosis and proposed remediation.
- `tests/` — end-to-end, loader, schema, runner, and pipeline tests.

## Install and test from repository root

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest .\observability\watcher\tests -v
python -m pytest .\ai_work\ai_pipeline -v --ignore=ai_work/ai_pipeline/diagnoser/test_ollama.py --ignore=ai_work/ai_pipeline/tests/test_ai_pipeline.py --ignore=ai_work/ai_pipeline/tests/test_all_incidents.py
```

The ignored tests require Ollama at `http://localhost:11434` with `llama3.2:3b`. To run those tests, start Ollama, pull the model, and run the full AI pipeline test command. Sample incidents are in `ai_work/examples/`; schemas are in `ai_work/schemas/`.

## Run the integrated incident runner

Deterministic local smoke test:

```powershell
python -m ai_work.ai_pipeline.runner .\ai_work\examples\incident-CrashLoopBackOff.json --diagnoser mock --output .\artifacts\incident-analysis.json
```

Use the local LLM:

```powershell
ollama pull llama3.2:3b
python -m ai_work.ai_pipeline.runner .\ai_work\examples\incident-CrashLoopBackOff.json --diagnoser ollama --output .\artifacts\incident-analysis.json
```

The runner first checks the current state of the incident's pod. If the same pod is currently Running and all its containers are ready, it starts a 60-second recovery stability window and samples health every 10 seconds. If all sampled observations remain healthy and the pod UID stays the same, the result is `RECOVERED` and no remediation proposal is generated. This is sampled verification, not a guarantee that no brief failure occurred between checks. If the pod becomes unhealthy during the window, the runner creates a proposal with status `AWAITING_HUMAN_APPROVAL`. If the pod is missing or its identity changes, the result is `NEEDS_HEALTH_REVIEW`. If observations become inconclusive, the proposal remains approval-gated and the uncertainty is included in the result. The monitor is read-only and does not close the incident.

**Execution boundary:** the health checker is read-only. The runner does not approve or execute remediation and does not mark an incident RESOLVED. Tests simulate Kubernetes responses, execution, and recovery; they do not prove real Kubernetes resources were changed.
