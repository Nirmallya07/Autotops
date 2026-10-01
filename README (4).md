# infra/terraform

Provisions a local `kind` (Kubernetes-in-Docker) cluster so you have
something real for the agent to act on, without needing a cloud account
yet.

```bash
terraform init
terraform apply
```

Then point kubectl at it:
```bash
kubectl config use-context kind-autoops
```

When you're ready to target a real cloud cluster, this is the file to
replace — everything downstream (k8s manifests, agent tools.py) talks to
whatever context `KUBE_CONTEXT` in `.env` points at, so the rest of the
project doesn't need to change.
