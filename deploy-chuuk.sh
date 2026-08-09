#!/bin/bash
set -euo pipefail

# Unified deployment for Chuuk dictionary (main app + Helsinki + Ollama)
# Prerequisites: Azure CLI logged in and permissions on the target subscription.

# Configuration (override with env vars if needed)
RESOURCE_GROUP=${RESOURCE_GROUP:-rg-chuuk-beta-eastus2}
LOCATION=${LOCATION:-eastus2}
CONTAINER_APP_ENV=${CONTAINER_APP_ENV:-chuuk-dictionary-env}
ACR_NAME=${ACR_NAME:-chuukdictregistry}
MAIN_APP_NAME=${MAIN_APP_NAME:-chuuk-dictionary}
MAIN_IMAGE=${MAIN_IMAGE:-chuuk-dictionary-app}
OLLAMA_APP_NAME=${OLLAMA_APP_NAME:-chuuk-ollama}
OLLAMA_IMAGE=${OLLAMA_IMAGE:-chuuk-ollama}
IMAGE_TAG=${IMAGE_TAG:-latest}
COSMOS_DB_NAME=${COSMOS_DB_NAME:-chuuk-dictionary-cosmos}
KEY_VAULT_NAME=${KEY_VAULT_NAME:-chuuk-kv-beta}
KV_FLASK_SECRET_NAME=${KV_FLASK_SECRET_NAME:-flask-secret-key}
KV_GOOGLE_API_KEY_NAME=${KV_GOOGLE_API_KEY_NAME:-google-cloud-api-key}
AZURE_SUBSCRIPTION=${AZURE_SUBSCRIPTION:-FindInfinite Labs - Beta}
# Storage account for persisting fine-tuned model weights across container restarts.
# The share is mounted at /app/models inside the main container so that any models
# trained or updated at runtime survive redeploys and scale-to-zero events.
MODEL_STORAGE_ACCOUNT=${MODEL_STORAGE_ACCOUNT:-chuukmodelstore}
MODEL_SHARE_NAME=${MODEL_SHARE_NAME:-chuuk-models}
# Mount at a SEPARATE directory so the baked-in /app/models/ in the image is
# never hidden.  Fine-tuned weights are written here and loaded preferentially.
MODEL_MOUNT_PATH=${MODEL_MOUNT_PATH:-/app/model_store}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { printf "${BLUE}%s${NC}\n" "$1"; }
success() { printf "${GREEN}%s${NC}\n" "$1"; }
warn() { printf "${YELLOW}%s${NC}\n" "$1"; }
die() { echo "$1" >&2; exit 1; }

require_az() {
  if ! command -v az >/dev/null 2>&1; then
    echo "Azure CLI not found. Install from https://learn.microsoft.com/cli/azure/install-azure-cli" >&2
    exit 1
  fi
}

ensure_login() {
  log "Checking Azure login..."
  if ! az account show >/dev/null 2>&1; then
    az login
  fi
  log "Setting subscription to ${AZURE_SUBSCRIPTION}..."
  az account set --subscription "$AZURE_SUBSCRIPTION"
  success "Using subscription: $(az account show --query name -o tsv)"
}

ensure_resource_group() {
  log "Ensuring resource group ${RESOURCE_GROUP}..."
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" >/dev/null
  success "Resource group ready"
}

register_providers() {
  log "Registering providers (Microsoft.App, Microsoft.OperationalInsights)..."
  az provider register --namespace Microsoft.App --wait >/dev/null 2>&1 || true
  az provider register --namespace Microsoft.OperationalInsights --wait >/dev/null 2>&1 || true
}

keyvault_available() {
  if [ -z "$KEY_VAULT_NAME" ]; then
    return 1
  fi
  az keyvault show --name "$KEY_VAULT_NAME" >/dev/null 2>&1
}

ensure_keyvault_and_secrets() {
  if [ -z "$KEY_VAULT_NAME" ]; then
    die "KEY_VAULT_NAME is required. Set KEY_VAULT_NAME to your Azure Key Vault name."
  fi
  log "Checking Key Vault ${KEY_VAULT_NAME} and required secrets..."
  az keyvault show --name "$KEY_VAULT_NAME" >/dev/null || die "Key Vault ${KEY_VAULT_NAME} not found or inaccessible."
  local kv_flask kv_google
  kv_flask=$(fetch_kv_secret "$KV_FLASK_SECRET_NAME")
  [ -n "$kv_flask" ] || die "Secret ${KV_FLASK_SECRET_NAME} not found in vault ${KEY_VAULT_NAME}."
  kv_google=$(fetch_kv_secret "$KV_GOOGLE_API_KEY_NAME")
  [ -n "$kv_google" ] || die "Secret ${KV_GOOGLE_API_KEY_NAME} not found in vault ${KEY_VAULT_NAME}."
  success "Key Vault and secrets available"
}

fetch_kv_secret() {
  local secret_name="$1"
  if keyvault_available; then
    az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$secret_name" --query value -o tsv 2>/dev/null || true
  else
    echo ""
  fi
}

ensure_acr() {
  log "Ensuring ACR ${ACR_NAME}..."
  if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --sku Basic --admin-enabled true >/dev/null
    success "ACR created"
  else
    success "ACR exists"
  fi
  ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)
  ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query username -o tsv)
  ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query passwords[0].value -o tsv)
}

ensure_env() {
  log "Ensuring Container Apps environment ${CONTAINER_APP_ENV}..."
  if ! az containerapp env show --name "$CONTAINER_APP_ENV" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    az containerapp env create --name "$CONTAINER_APP_ENV" --resource-group "$RESOURCE_GROUP" --location "$LOCATION"
    success "Container Apps environment created"
  else
    success "Container Apps environment exists"
  fi
}

ensure_model_storage() {
  # Provision an Azure Storage account + File Share and attach it to the
  # Container Apps environment so that fine-tuned Helsinki model weights
  # survive container restarts, scale-to-zero events, and redeploys.
  #
  # The share is mounted at MODEL_MOUNT_PATH (/app/models) inside the main
  # container; this directory shadows the baked-in models in the image while
  # preserving them as the initial fallback (the storage is populated from the
  # image layer the very first time the container writes there).
  log "Ensuring model storage account ${MODEL_STORAGE_ACCOUNT}..."

  # Storage account names must be globally unique, 3-24 lower-case alphanumeric
  if ! az storage account show --name "$MODEL_STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    az storage account create \
      --name "$MODEL_STORAGE_ACCOUNT" \
      --resource-group "$RESOURCE_GROUP" \
      --location "$LOCATION" \
      --sku Standard_LRS \
      --kind StorageV2 \
      --allow-blob-public-access false \
      --min-tls-version TLS1_2 >/dev/null
    success "Storage account created: ${MODEL_STORAGE_ACCOUNT}"
  else
    success "Storage account exists: ${MODEL_STORAGE_ACCOUNT}"
  fi

  MODEL_STORAGE_KEY=$(az storage account keys list \
    --account-name "$MODEL_STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[0].value" -o tsv)

  # Create the file share if missing
  if ! az storage share show \
      --name "$MODEL_SHARE_NAME" \
      --account-name "$MODEL_STORAGE_ACCOUNT" \
      --account-key "$MODEL_STORAGE_KEY" >/dev/null 2>&1; then
    az storage share create \
      --name "$MODEL_SHARE_NAME" \
      --account-name "$MODEL_STORAGE_ACCOUNT" \
      --account-key "$MODEL_STORAGE_KEY" \
      --quota 32 >/dev/null   # 32 GiB — plenty for Helsinki Marian weights
    success "File share created: ${MODEL_SHARE_NAME}"
  else
    success "File share exists: ${MODEL_SHARE_NAME}"
  fi

  # Register the storage with the Container Apps environment (idempotent)
  az containerapp env storage set \
    --name "$CONTAINER_APP_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --storage-name "chuuk-models" \
    --azure-file-account-name "$MODEL_STORAGE_ACCOUNT" \
    --azure-file-account-key "$MODEL_STORAGE_KEY" \
    --azure-file-share-name "$MODEL_SHARE_NAME" \
    --access-mode ReadWrite >/dev/null
  success "Model storage registered with Container Apps environment"
}

build_images() {
  log "Building main image ${MAIN_IMAGE}:${IMAGE_TAG} (linux/amd64)..."
  az acr build --registry "$ACR_NAME" --image "${MAIN_IMAGE}:${IMAGE_TAG}" --file Dockerfile --platform linux/amd64 .
  success "Main image built and pushed"

  log "Building Ollama image ${OLLAMA_IMAGE}:${IMAGE_TAG} (linux/amd64)..."
  az acr build --registry "$ACR_NAME" --image "${OLLAMA_IMAGE}:${IMAGE_TAG}" --file Dockerfile.ollama --platform linux/amd64 .
  success "Ollama image built and pushed"
}

load_or_generate_secret() {
  local key_name="$1"
  local current_value="${!key_name:-}"
  if [ -n "$current_value" ]; then
    printf '%s' "$current_value"
    return
  fi
  local kv_value
  kv_value=$(fetch_kv_secret "$KV_FLASK_SECRET_NAME")
  if [ -n "$kv_value" ]; then
    printf '%s' "$kv_value"
    return
  fi
  if [ -f .env ] && grep -q "^${key_name}=" .env; then
    grep "^${key_name}=" .env | head -1 | cut -d'=' -f2-
    return
  fi
  # Generate once and persist to .env
  local generated
  generated=$(openssl rand -hex 32)
  printf '\n%s=%s\n' "$key_name" "$generated" >> .env
  warn "Generated ${key_name} and saved to .env"
  printf '%s' "$generated"
}

load_optional_env() {
  local key_name="$1"
  local current_value="${!key_name:-}"
  if [ -n "$current_value" ]; then
    printf '%s' "$current_value"
    return
  fi
  if [ -f .env ] && grep -q "^${key_name}=" .env; then
    grep "^${key_name}=" .env | head -1 | cut -d'=' -f2-
  fi
}

load_required_google_key() {
  local kv_value
  kv_value=$(fetch_kv_secret "$KV_GOOGLE_API_KEY_NAME")
  if [ -n "$kv_value" ]; then
    printf '%s' "$kv_value"
    return
  fi
  local from_env
  from_env=$(load_optional_env GOOGLE_CLOUD_API_KEY)
  if [ -n "$from_env" ]; then
    printf '%s' "$from_env"
    return
  fi
  die "GOOGLE_CLOUD_API_KEY not found in Key Vault ${KEY_VAULT_NAME:-<unset>} or environment/.env."
}

fetch_cosmos() {
  log "Fetching Cosmos DB credentials..."
  COSMOS_DB_KEY=$(az cosmosdb keys list --name "$COSMOS_DB_NAME" --resource-group "$RESOURCE_GROUP" --type keys --query primaryMasterKey -o tsv)
  COSMOS_DB_URI="https://${COSMOS_DB_NAME}.documents.azure.com:443/"
  if [ -z "$COSMOS_DB_KEY" ]; then
    echo "Failed to retrieve Cosmos DB key; check permissions and database name." >&2
    exit 1
  fi
  success "Cosmos DB credentials retrieved"
}

deploy_ollama() {
  log "Deploying Ollama Container App (${OLLAMA_APP_NAME})..."
  local image_ref="${ACR_LOGIN_SERVER}/${OLLAMA_IMAGE}:${IMAGE_TAG}"
  if az containerapp show --name "$OLLAMA_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    # Refresh registry credentials before pulling new image
    az containerapp registry set \
      --name "$OLLAMA_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --server "$ACR_LOGIN_SERVER" \
      --username "$ACR_USERNAME" \
      --password "$ACR_PASSWORD" >/dev/null

    az containerapp update \
      --name "$OLLAMA_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --image "$image_ref" \
      --cpu 2.0 \
      --memory 4Gi
    success "Ollama app updated"
  else
    az containerapp create \
      --name "$OLLAMA_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --environment "$CONTAINER_APP_ENV" \
      --image "$image_ref" \
      --target-port 11434 \
      --ingress internal \
      --cpu 2.0 \
      --memory 4Gi \
      --min-replicas 1 \
      --max-replicas 1 \
      --registry-server "$ACR_LOGIN_SERVER" \
      --registry-username "$ACR_USERNAME" \
      --registry-password "$ACR_PASSWORD"
    success "Ollama app created"
  fi
  OLLAMA_FQDN=$(az containerapp show --name "$OLLAMA_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)
  OLLAMA_BASE_URL="https://${OLLAMA_FQDN}"
  success "Ollama URL: ${OLLAMA_BASE_URL}"
}

deploy_main() {
  log "Deploying main Container App (${MAIN_APP_NAME})..."
  local image_ref="${ACR_LOGIN_SERVER}/${MAIN_IMAGE}:${IMAGE_TAG}"
  local flask_secret
  flask_secret=$(load_or_generate_secret FLASK_SECRET_KEY)
  local google_key
  google_key=$(load_required_google_key)

  # Build env var list
  ENV_ARGS=(
    "DB_TYPE=cosmos"
    "COSMOS_DB_URI=${COSMOS_DB_URI}"
    "COSMOS_DB_KEY=${COSMOS_DB_KEY}"
    "FLASK_ENV=production"
    "FLASK_DEBUG=0"
    "FLASK_SECRET_KEY=${flask_secret}"
    # Fine-tuned model weights are written here (Azure File Share mount).
    # Baked-in base weights remain in /app/models/ as fallback.
    "MODEL_STORE_PATH=${MODEL_MOUNT_PATH}"
  )
  if [ -n "$google_key" ]; then
    ENV_ARGS+=("GOOGLE_CLOUD_API_KEY=${google_key}")
  fi
  if [ -n "${OLLAMA_BASE_URL:-}" ]; then
    ENV_ARGS+=("OLLAMA_BASE_URL=${OLLAMA_BASE_URL}")
  fi

  if az containerapp show --name "$MAIN_APP_NAME" --resource-group "$RESOURCE_GROUP" >/dev/null 2>&1; then
    # Refresh registry credentials before pulling new image
    az containerapp registry set \
      --name "$MAIN_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --server "$ACR_LOGIN_SERVER" \
      --username "$ACR_USERNAME" \
      --password "$ACR_PASSWORD" >/dev/null

    az containerapp update \
      --name "$MAIN_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --image "$image_ref" \
      --set-env-vars "${ENV_ARGS[@]}"

    # Ensure the model volume is mounted (idempotent via az containerapp update --volume)
    az containerapp update \
      --name "$MAIN_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --volume "name=models-vol,storage-type=AzureFile,storage-name=chuuk-models" \
      --mount "name=models-vol,mount-path=${MODEL_MOUNT_PATH}" 2>/dev/null || \
        warn "Volume mount update skipped (may require revision; check portal if models do not persist)"
    success "Main app updated"
  else
    az containerapp create \
      --name "$MAIN_APP_NAME" \
      --resource-group "$RESOURCE_GROUP" \
      --environment "$CONTAINER_APP_ENV" \
      --image "$image_ref" \
      --registry-server "$ACR_LOGIN_SERVER" \
      --registry-username "$ACR_USERNAME" \
      --registry-password "$ACR_PASSWORD" \
      --target-port 8000 \
      --ingress external \
      --cpu 2.0 \
      --memory 4.0Gi \
      --min-replicas 0 \
      --max-replicas 2 \
      --env-vars "${ENV_ARGS[@]}" \
      --volume "name=models-vol,storage-type=AzureFile,storage-name=chuuk-models" \
      --mount "name=models-vol,mount-path=${MODEL_MOUNT_PATH}"
    success "Main app created"
  fi
  APP_FQDN=$(az containerapp show --name "$MAIN_APP_NAME" --resource-group "$RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)
  success "Main app URL: https://${APP_FQDN}"
}

main() {
  log "🚀 Starting Chuuk deployment (main + Ollama)"
  require_az
  ensure_login
  ensure_resource_group
  ensure_keyvault_and_secrets
  register_providers
  ensure_acr
  ensure_env
  ensure_model_storage
  build_images
  fetch_cosmos
  deploy_ollama
  deploy_main
  echo ""
  success "Deployment complete"
  echo "Main app: https://${APP_FQDN}"
  echo "Ollama:   ${OLLAMA_BASE_URL} (internal)"
  echo "Logs: az containerapp logs show --name ${MAIN_APP_NAME} --resource-group ${RESOURCE_GROUP} --follow"
}

main "$@"
