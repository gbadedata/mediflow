subscription_id  = "c8928261-3c0c-4e98-bbc6-9ba70d318285"
location         = "uksouth"
project          = "mediflow"
environment      = "dev"
aks_node_count   = 2
aks_node_vm_size = "Standard_D2ps_v6"

tags = {
  project     = "mediflow"
  environment = "dev"
  managed_by  = "terraform"
  owner       = "gbadedata"
}
