variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = "c8928261-3c0c-4e98-bbc6-9ba70d318285"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "uksouth"
}

variable "project" {
  description = "Project name used as a prefix for all resources"
  type        = string
  default     = "mediflow"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "aks_node_count" {
  description = "Number of nodes in the default AKS node pool"
  type        = number
  default     = 2
}

variable "aks_node_vm_size" {
  description = "VM size for AKS nodes"
  type        = string
  default     = "Standard_B2s"
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    project     = "mediflow"
    environment = "dev"
    managed_by  = "terraform"
    owner       = "gbadedata"
  }
}
