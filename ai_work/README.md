# AI Work — Incident Response Pipeline

This component consumes normalized incident JSON from the observability Watcher and runs it through diagnosis, validation, remediation proposal, approval handoff, recovery-result handling, and reporting.

## Modules
- `ai_pipeline/` — diagnosis, validation, remediation proposals, approval handoff, recovery results, and reporting.
- `examples/` — sample incidents shared with the Watcher.
- `schemas/` — shared JSON contracts.

## Run tests from the repository root

```powershell
python -m pytest .\ai_work\ai_pipeline -v
```

Ollama-backed tests require Ollama at `http://localhost:11434` with `llama3.2:3b`. Other tests use mocks where appropriate.

## Execution boundary
The pipeline prepares and validates proposals and an approval-gated handoff. Tests simulate execution/recovery; they do not prove that real cluster changes occurred.
