from types import SimpleNamespace as NS

import pytest

from ai_work.ai_pipeline.recovery.workload_verifier import DeploymentRecoveryVerifier


def owner(kind, name):
    return NS(kind=kind, name=name, controller=True)


def test_resolves_deployment_through_replicaset():
    pod = NS(metadata=NS(uid="pod-uid", owner_references=[owner("ReplicaSet", "web-rs")]))
    rs = NS(metadata=NS(owner_references=[owner("Deployment", "web")]))
    core = NS(read_namespaced_pod=lambda name, namespace: pod)
    apps = NS(read_namespaced_replica_set=lambda name, namespace: rs)
    verifier = DeploymentRecoveryVerifier(apps_api=apps, core_api=core)

    assert verifier.resolve_deployment_name("demo", "web-pod", "pod-uid") == "web"


def test_resolver_rejects_changed_pod_identity():
    pod = NS(metadata=NS(uid="new-uid", owner_references=[owner("ReplicaSet", "web-rs")]))
    core = NS(read_namespaced_pod=lambda name, namespace: pod)
    apps = NS()
    verifier = DeploymentRecoveryVerifier(apps_api=apps, core_api=core)

    with pytest.raises(ValueError, match="identity changed"):
        verifier.resolve_deployment_name("demo", "web-pod", "old-uid")


def test_resolver_rejects_pod_without_replicaset_owner():
    pod = NS(metadata=NS(uid="pod-uid", owner_references=[]))
    core = NS(read_namespaced_pod=lambda name, namespace: pod)
    verifier = DeploymentRecoveryVerifier(apps_api=NS(), core_api=core)

    with pytest.raises(ValueError, match="not controlled by a ReplicaSet"):
        verifier.resolve_deployment_name("demo", "web-pod", "pod-uid")


def test_resolver_rejects_replicaset_without_deployment_owner():
    pod = NS(metadata=NS(uid="pod-uid", owner_references=[owner("ReplicaSet", "web-rs")]))
    rs = NS(metadata=NS(owner_references=[]))
    core = NS(read_namespaced_pod=lambda name, namespace: pod)
    apps = NS(read_namespaced_replica_set=lambda name, namespace: rs)
    verifier = DeploymentRecoveryVerifier(apps_api=apps, core_api=core)

    with pytest.raises(ValueError, match="not controlled by a Deployment"):
        verifier.resolve_deployment_name("demo", "web-pod", "pod-uid")


def test_verifier_requires_owned_ready_replacement_and_stability():
    deployment = NS(
        spec=NS(replicas=1, selector=NS(match_labels={"app": "web"})),
        status=NS(observed_generation=2),
        metadata=NS(generation=2),
    )
    ready_pod = NS(
        status=NS(phase="Running", container_statuses=[NS(ready=True)]),
        metadata=NS(uid="replacement-uid", deletion_timestamp=None),
    )
    apps = NS(read_namespaced_deployment=lambda name, namespace: deployment)
    core = NS()
    verifier = DeploymentRecoveryVerifier(apps_api=apps, core_api=core, sleep_fn=lambda _: None)
    verifier._deployment_pods = lambda namespace, name, selector: [ready_pod]

    result = verifier.verify("demo", "web", "old-uid", timeout_seconds=1,
                             stability_samples=2, interval_seconds=0)

    assert result["status"] == "RECOVERED"
    assert result["sample_count"] == 2
    assert result["observations"][-1]["replacement_pod_uids"] == ["replacement-uid"]


def test_verifier_fails_if_replacement_is_not_ready():
    deployment = NS(
        spec=NS(replicas=1, selector=NS(match_labels={"app": "web"})),
        status=NS(observed_generation=1),
        metadata=NS(generation=1),
    )
    unready_pod = NS(
        status=NS(phase="Running", container_statuses=[NS(ready=False)]),
        metadata=NS(uid="replacement-uid", deletion_timestamp=None),
    )
    apps = NS(read_namespaced_deployment=lambda name, namespace: deployment)
    verifier = DeploymentRecoveryVerifier(
        apps_api=apps, core_api=NS(), sleep_fn=lambda _: None
    )
    verifier._deployment_pods = lambda namespace, name, selector: [unready_pod]

    result = verifier.verify("demo", "web", "old-uid", timeout_seconds=1,
                             stability_samples=1, interval_seconds=0)

    assert result["status"] == "FAILED"
