#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="autotops-demo:0.1"

echo "Building Docker image ${IMAGE_TAG}..."
docker build -t ${IMAGE_TAG} .

if command -v minikube >/dev/null 2>&1; then
  echo "Detected minikube. Loading image into minikube..."
  minikube image load ${IMAGE_TAG}
elif command -v kind >/dev/null 2>&1; then
  echo "Detected kind. Loading image into kind..."
  kind load docker-image ${IMAGE_TAG}
else
  echo "No local cluster loader found. Ensure image ${IMAGE_TAG} is available on cluster nodes."
fi

echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

echo "Waiting for rollout..."
kubectl rollout status deployment/autotops-demo --timeout=120s

echo "Port-forwarding service to localhost:5000 (background)..."
kubectl port-forward svc/autotops-demo 5000:80 >/dev/null 2>&1 &

echo "Demo running. Health: http://localhost:5000/health"
echo "Metrics: http://localhost:5000/metrics"
echo "Failure injection: /failure  Crash: /crash  Memory alloc: /alloc?mb=100"
