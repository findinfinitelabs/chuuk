---
name: azure-container-deployment
description: Deploy the Chuuk Dictionary stack (main app + Ollama sidecar) to Azure Container Apps. Covers ACR remote builds via `az acr build`, Key Vault prerequisites, Cosmos DB credential injection, and the env-var contract. Use when running a deploy, debugging a failed deploy, or modifying Azure infrastructure.
---

# Azure Container Deployment

The deploy is one script: [`deploy-chuuk.sh`](../../../deploy-chuuk.sh). It deploys two Container Apps to a single Container Apps environment, sourcing secrets from Key Vault and Cosmos credentials at deploy time. **No** `docker build` is run locally — images are built remotely in ACR.

## Resources (defaults; override via env)

| Var | Default |
|---|---|
| `RESOURCE_GROUP` | `rg-chuuk-beta-eastus2` |
| `LOCATION` | `eastus2` |
| `CONTAINER_APP_ENV` | `chuuk-dictionary-env` |
| `ACR_NAME` | `chuukdictregistry` |
| `MAIN_APP_NAME` / `MAIN_IMAGE` | `chuuk-dictionary` / `chuuk-dictionary-app` |
| `OLLAMA_APP_NAME` / `OLLAMA_IMAGE` | `chuuk-ollama` / `chuuk-ollama` |
| `COSMOS_DB_NAME` | `chuuk-dictionary-cosmos` |
| `KEY_VAULT_NAME` | `chuuk-kv-beta` |
| `KV_FLASK_SECRET_NAME` | `flask-secret-key` |
| `KV_GOOGLE_API_KEY_NAME` | `google-cloud-api-key` |
| `AZURE_SUBSCRIPTION` | `FindInfinite Labs - Beta` |

The script `set`s the subscription explicitly ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L47)), so accidentally being on the wrong subscription is not a failure mode.

## Prerequisites (failure-fast)

`ensure_keyvault_and_secrets` ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L66)) requires:

- The Key Vault exists and you have read access.
- Both `flask-secret-key` and `google-cloud-api-key` secrets exist in it.

If either is missing the script aborts before doing any work. Provision them once via:

```bash
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name flask-secret-key --value "$(openssl rand -hex 32)"
az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name google-cloud-api-key --value "<your-key>"
```

Cosmos DB credentials are fetched at deploy time via `az cosmosdb keys list` and passed in directly — no Key Vault entry needed for them.

## Build flow (no local docker)

`build_images` ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L116)) runs:

```bash
az acr build --registry chuukdictregistry --image chuuk-dictionary-app:latest \
  --file Dockerfile --platform linux/amd64 .
az acr build --registry chuukdictregistry --image chuuk-ollama:latest \
  --file Dockerfile.ollama --platform linux/amd64 .
```

This pushes the build context up to ACR and builds inside Azure — works on M-series Macs where local `linux/amd64` builds would otherwise be cross-arch.

`PREPULL_LLM` is **not** set by default — the Ollama image starts lean and pulls `llama3.2:3b` on first boot (~30s warm-up). Add `--build-arg PREPULL_LLM=true` (and a much larger image) if cold starts are a problem.

## Container Apps configuration (current)

Main app ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L282)):
- `--cpu 2.0 --memory 4.0Gi`
- `--min-replicas 0 --max-replicas 2`
- `--target-port 8000 --ingress external` (public HTTPS)

Ollama sidecar ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L220)):
- `--cpu 2.0 --memory 4Gi`
- `--min-replicas 1 --max-replicas 1` (always on; keeps the model loaded)
- `--target-port 11434 --ingress internal` (private FQDN, reachable only inside the env)

The internal Ollama FQDN is captured into `OLLAMA_BASE_URL` and injected into the main app's env ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L227)).

## Env vars passed to the main app

From [deploy-chuuk.sh](../../../deploy-chuuk.sh#L242):

```
DB_TYPE=cosmos
COSMOS_DB_URI=<from az cosmosdb>
COSMOS_DB_KEY=<from az cosmosdb keys list>
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=<from KV>
GOOGLE_CLOUD_API_KEY=<from KV>             # if present
OLLAMA_BASE_URL=https://<internal-fqdn>    # if Ollama deployed
```

Important: secrets are passed as **plain env values** in the current script, **not** via `secretRef`. If you want to switch to secretRef, update `deploy_main` to first `az containerapp secret set` and then reference `secretref:<name>` in `--env-vars` — and remember to refresh secrets on every key rotation.

## Architecture facts (don't forget)

- The frontend is **bundled into the Flask image** (`COPY --from=frontend-builder /app/frontend/dist ./frontend/dist` in [Dockerfile](../../../Dockerfile#L33)). There is **no** Static Web App, no separate CDN, no Cloudflare. Same-origin everything.
- One Container Apps environment hosts both apps. Splitting them across environments breaks the internal FQDN-based connectivity to Ollama.
- Models are baked into the image (`COPY models/ ./models/` in [Dockerfile](../../../Dockerfile#L25)) — image size is ~2 GiB. Retraining requires a new image build + deploy. See [production-retraining-orchestration](../production-retraining-orchestration/SKILL.md).

## Operational commands

```bash
# Tail logs
az containerapp logs show -n chuuk-dictionary -g rg-chuuk-beta-eastus2 --follow

# Open a shell in the running container
az containerapp exec -n chuuk-dictionary -g rg-chuuk-beta-eastus2 --command /bin/bash

# Force a restart by bumping the revision
az containerapp update -n chuuk-dictionary -g rg-chuuk-beta-eastus2 --image <same-tag>
```

## Pitfalls

- The script auto-generates `FLASK_SECRET_KEY` and writes it to `.env` if missing — that's a *local-only* fallback. In CI/CD, ensure the Key Vault secret exists; otherwise users get logged out on every redeploy because the cookie signature changes.
- `min-replicas=0` on the main app means cold starts. The first request after idle takes 5–15s. Don't set this to 1 without budget consideration.
- `min-replicas=1` on Ollama is required — at 0, the model unloads and every translate request pays the model-load cost.
- If you change `MAIN_APP_NAME`/`OLLAMA_APP_NAME`, the deploy will create new resources rather than update existing ones. Always check `az containerapp list -g $RESOURCE_GROUP -o table` before re-running.
- Key Vault access: the deploy runs as the user invoking it, not as a managed identity — that user needs `Key Vault Secrets User` (or higher) on the vault.
