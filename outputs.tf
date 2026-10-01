output "kubeconfig_context" {
  value       = "kind-${var.cluster_name}"
  description = "Set KUBE_CONTEXT in .env to this value"
}
