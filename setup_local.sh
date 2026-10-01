#!/usr/bin/env bash
# Spins up a local kind cluster via Terraform, then deploys the sample app.
set -euo pipefail

cd "$(dirname "$0")/../infra/terraform"
echo "==> Provisioning local kind cluster..."
terraform init -input=false
terraform apply -auto-approve

echo "==> Switching kubectl context..."
kubectl config use-context kind-autoops

cd - > /dev/null
echo "==> Deploying sample app..."
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/sample-app-deployment.yaml
kubectl apply -f k8s/sample-app-service.yaml

echo "==> Done. Check pods with: kubectl get pods -n autoops"
