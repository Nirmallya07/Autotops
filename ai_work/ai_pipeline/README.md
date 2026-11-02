# AI Work — Incident Response Pipeline

This component consumes normalized incident JSON from the observability Watcher and runs diagnosis, validation, remediation proposal, approval handoff, recovery-result handling, and reporting.

## Modules

- `incident_loader.py` — loads and validates the shared incident JSON contract.
- `diagnoser/` — diagnostic context, mock/Ollama diagnosis, and output validation.
- `fixer/` — remediation proposals, approval manager, and execution handoff.
- `recovery/` — recovery-result validation.
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

The result includes the incident, validated diagnosis, and remediation proposal. Its status is `AWAITING_HUMAN_APPROVAL`. The runner does not approve, execute, or claim recovery. An authorized human must review the proposal before the approval and execution-handoff components are used.

**Execution boundary:** the pipeline validates diagnoses and prepares approval-gated remediation handoffs. Tests simulate execution and recovery; they do not prove real Kubernetes resources were changed.
