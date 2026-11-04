# AutoTops V2/V3 implementation notes

## Four agents
- WatcherAgent: deterministic Kubernetes/Prometheus detection and incident creation.
- DiagnoserAgent: structured evidence diagnosis; optional SQLite historical incident retrieval.
- FixerAgent: deterministic proposal, fail-closed policy, bounded orchestrator and Kubernetes adapter.
- ReporterAgent: JSON and text incident reports.

## V2 incident memory
SQLite is used to avoid an external vector database service for the initial milestone. Retrieval uses transparent lexical overlap plus service/failure-type boosts. Only verified successful outcomes can be stored. Historical matches are advisory context, never proof of a current root cause. This is a lightweight retrieval baseline, not embedding-based semantic RAG.

## V3 execution safety
The default policy allowlist is empty. Automatic actions require explicit configuration. Rollback, scale and configuration changes always require human approval. The initial executor exposes only a fixed pod-delete operation for a controller-managed pod after re-reading and matching its UID. No shell commands are accepted. Failed operations are escalated; there is no retry loop.

The default runner remains non-executing. Real execution is opt-in and must be configured by an operator with least-privilege Kubernetes RBAC. A pod restart is not guaranteed recovery; the existing health checker and stability monitor must verify the replacement workload.

## Operational limitations
- SQLite lexical retrieval is not a vector embedding system.
- Automatic pod restart is disabled by default.
- Real cluster execution cannot be proven by unit tests or GitHub Actions.
- Human approval and policy-auto authorization are distinct paths.
