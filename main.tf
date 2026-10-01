terraform {
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.4"
    }
  }
}

provider "kind" {}

resource "kind_cluster" "autoops" {
  name           = "autoops"
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"
    }
    node {
      role = "worker"
    }
  }
}

# TODO: once you move off `kind` to a real cloud cluster, swap this file
# for an AWS EKS / GCP GKE module instead — the k8s/ manifests and the
# agent's tools.py shouldn't need to change, just KUBE_CONTEXT.
