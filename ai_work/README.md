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


## Incident lifecycle history

The source incident JSON remains Watcher-owned and is not rewritten by the AI
pipeline. To persist AI processing state separately, pass a lifecycle directory:

```bash
python -m ai_work.ai_pipeline.runner scripts/member2_incidents/INC-054.json \
  --diagnoser mock \
  --stability-window-seconds 20 \
  --stability-interval-seconds 5 \
  --lifecycle-dir scripts/member2_incidents/lifecycle
```

This creates one lifecycle JSON file per incident under the supplied directory.
It records an append-only event history beginning with `OPEN`, followed by
`INVESTIGATING` and the pipeline outcome (`RECOVERED`,
`AWAITING_HUMAN_APPROVAL`, or `NEEDS_HEALTH_REVIEW`). Each event includes a
timestamp, actor, and message; outcome events may also include health evidence.

A recovered incident is not automatically resolved. Resolution is a separate
human action and requires an actor and a note:

```python
from ai_work.ai_pipeline.recovery.incident_lifecycle import IncidentLifecycle

lifecycle = IncidentLifecycle(
    "scripts/member2_incidents/lifecycle/INC-054.json"
)
lifecycle.resolve(
    "INC-054",
    actor="operator",
    note="Reviewed the recovery evidence and confirmed closure.",
)
```

Only a `RECOVERED` incident can be resolved in this lifecycle version.
`RESOLVED` is terminal. Lifecycle persistence is opt-in; omitting
`--lifecycle-dir` preserves the runner's previous behavior.


## Using a specific local Ollama model

Select the Ollama model explicitly with `--ollama-model`. The default remains
`llama3.2:3b` for compatibility. For example, if `qwen2.5:3b` is installed
locally:

```bash
python -m ai_work.ai_pipeline.runner scripts/member2_incidents/INC-054.json \\
  --diagnoser ollama \\
  --ollama-model qwen2.5:3b \\
  --stability-window-seconds 10 \\
  --stability-interval-seconds 5 \\
  --output /tmp/INC-054-qwen-analysis.json
```

The model supplies the diagnosis only. Kubernetes health checks, recovery
verification, approval requirements, and the no-automatic-execution boundary
remain enforced by the pipeline.


## Ollama diagnosis quality

The Ollama prompt requires the model to separate observed evidence from
hypotheses. In particular, `CrashLoopBackOff` is treated as a symptom rather
than an explanation of the underlying application failure. When logs do not
show the actual error, the model must state that the exact cause is unknown and
recommend collecting more useful evidence, such as current and previous
container logs. Generic runtime warnings must not be presented as the cause
without supporting evidence. The model must not recommend arbitrary retry
increases or restart-policy changes as a substitute for diagnosis.
