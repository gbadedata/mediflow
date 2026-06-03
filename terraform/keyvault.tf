# ── Current client context ────────────────────────────────────────────────────
data "azurerm_client_config" "current" {}

# ── Key Vault ─────────────────────────────────────────────────────────────────
resource "azurerm_key_vault" "main" {
  name                        = "kv-${var.project}-${var.environment}"
  location                    = azurerm_resource_group.main.location
  resource_group_name         = azurerm_resource_group.main.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false
  rbac_authorization_enabled   = true
  tags                        = var.tags
}

# ── Grant your own identity admin access to the vault ────────────────────────
resource "azurerm_role_assignment" "kv_admin_self" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ── Grant AKS identity access to read secrets ─────────────────────────────────
resource "azurerm_role_assignment" "kv_secrets_aks" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_kubernetes_cluster.main.key_vault_secrets_provider[0].secret_identity[0].object_id
}

# ── Example secret: API key placeholder ──────────────────────────────────────
resource "azurerm_key_vault_secret" "app_api_key" {
  name         = "mediflow-api-key"
  value        = "placeholder-rotate-before-production"
  key_vault_id = azurerm_key_vault.main.id
  tags         = var.tags

  depends_on = [azurerm_role_assignment.kv_admin_self]
}
