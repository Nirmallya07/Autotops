# V3 self-healing runbook

## Safe default
The standard incident runner remains proposal-only. V3 execution is a separate explicit command:

```bash
python -m ai_work.ai_pipeline.self_heal ai_work/examples/incident-CrashLoopBackOff.json --diagnoser mock
```

This stores reports under `artifacts/reports`, retrieval memory under `artifacts/incident_memory.sqlite3`, and a result JSON under `artifacts/self-heal-result.json`. Empty auto-actions means no automatic infrastructure operation.

## Opt-in restart
Only after reviewing the namespace RBAC, deployment name/service mapping, and test environment, an operator may opt in:

```bash
python -m ai_work.ai_pipeline.self_heal INCIDENT.json --diagnoser ollama --model qwen2.5:3b --auto-actions restart_pod
```

The current executor only supports deletion of the incident pod after checking its UID and confirming it is owned by a ReplicaSet or StatefulSet. The verifier then checks Deployment readiness and multiple stable samples. Rollback, scaling, and configuration changes remain human-approved.

## Least-privilege RBAC
The executor needs `get` and `delete` on pods in the target namespace. The recovery verifier needs `get` on deployments and `list` on pods. Do not grant cluster-admin. Restrict the service account to the namespace and resources actually used.

## Failure behavior
A failed API operation, missing identity, unmanaged pod, timeout, or failed post-action stability sample is escalated. There is no automatic retry loop. Historical memory records only verified recovered outcomes.

## Important limitations
The initial retrieval baseline is SQLite lexical matching, not embedding-based vector RAG. The executor supports one action only. A verified controller-level readiness result does not prove application-level correctness beyond Kubernetes readiness probes. Real-cluster behavior must be validated in a disposable test namespace before enabling automation in a workload.
