---
name: security-environment-standards
description: Security model and environment-variable conventions for the Chuuk Dictionary app — hybrid access-code + magic-link auth, role/permission gating, single-active-session enforcement, file-upload allow-list, scripture endpoint anti-scrape, and the env vars actually read. Use when adding secrets, configuring environments, or hardening a route.
---

# Security & Environment Standards

## Auth model (the actual one)

The app uses **two complementary auth flows**, not magic-link only:

1. **Access-code login** — primary path. `POST /api/auth/login` with `{ email, access_code }` ([app.py](../../../app.py#L505)). Codes are managed via the admin UI / `UserDB`.
2. **Magic-link login** — secondary. `POST /api/auth/magic-link` ([app.py](../../../app.py#L577)) emails a token. `GET /api/auth/magic/<token>` consumes it.

Both flows produce the same session shape. The session keys actually checked:

| key | meaning |
|---|---|
| `session["logged_in"]` | the gate (NOT `authenticated`) |
| `session["user_email"]` | identity (NOT `user`) |
| `session["user_role"]` | role string |
| `session["session_id"]` | single-active-session token |

Single-active-session enforcement: every protected request validates `session["session_id"]` against `UserDB.is_session_valid` ([app.py](../../../app.py#L696), [app.py](../../../app.py#L704)). Logging in elsewhere invalidates the old session and the next request returns `error: "session_invalidated"`.

Permissions: derived from role via `ROLE_PERMISSIONS` ([app.py](../../../app.py#L462)) and exposed on `g.permissions` ([app.py](../../../app.py#L481)). Required `accepted_terms_at` first-login gate enforces Terms of Use. Admin endpoints require `role == "admin"` *and* `"admin"` permission — gate on both.

For the full auth picture see the [auth-session-and-permissions-flow](../auth-session-and-permissions-flow/SKILL.md) skill.

## Environment variables actually consulted

```bash
# Flask
FLASK_SECRET_KEY=<64-hex-chars>            # Required in prod; .env auto-generated for dev
FLASK_ENV=production                       # Enables secure cookies
FLASK_DEBUG=0

# Database (see database-management-operations skill)
COSMOS_MONGO_CONNECTION_STRING=...         # Preferred
# OR
USE_MANAGED_IDENTITY=true
COSMOS_ACCOUNT_NAME=chuuk-dictionary-cosmos
# OR
COSMOS_DB_URI=https://<acct>.documents.azure.com:443/
COSMOS_DB_KEY=<primary-key>

# Translation
GOOGLE_CLOUD_API_KEY=...                   # REST key (preferred)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json   # service-account fallback
OLLAMA_BASE_URL=http://chuuk-ollama:11434  # private FQDN in prod

# Uploads
MAX_CONTENT_LENGTH=16777216
UPLOAD_FOLDER=uploads
```

`COSMOS_DB_CONNECTION_STRING` is **not** read anywhere — older docs lie about this. Don't add it to deploy scripts.

## File upload allow-list

From [app.py](../../../app.py#L248):

```python
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "pdf", "docx"}
```

`txt`, `csv`, and `epub` are **not** in the upload allow-list — they're handled by separate import endpoints (CSV import, EPUB lookup). When adding an extension, also confirm OCR can handle it; if not, add a parallel import path.

Uploads always go through `werkzeug.utils.secure_filename` and land under `uploads/<publication_id>/`.

## Session cookie config

```python
app.config['SESSION_COOKIE_SECURE']   = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
```

`SameSite=Lax` is fine because the SPA is same-origin in prod (Flask serves `frontend/dist`). If you ever split frontend and backend onto different hosts, raise to `None` and enforce HTTPS (and add CORS).

## Regex / injection safety

User input that flows into MongoDB `$regex`, into Tesseract command flags, or into shell commands must be escaped:

```python
import re
pattern = re.escape(user_input)
collection.find({"chuukese_word": {"$regex": pattern, "$options": "i"}})
```

`DictionaryDB.search_word/search_words/search_phrases` already escape internally — only handle escaping yourself when you bypass them with raw collection access.

## Scripture endpoint robots policy

Bible/scripture endpoints respect a tighter robots policy ([app.py](../../../app.py#L3574)) — they're NoIndex/NoFollow with rate-limit hints, to discourage bulk scraping of NWT content. New endpoints under `/api/scripture/...` or `/api/bible/...` should reuse the same gate.

## Secrets management

- Never hardcode secrets. `.env.example` is committed; `.env` is gitignored.
- Production secrets live in **Azure Key Vault**. The deploy script reads `flask-secret-key` and `google-cloud-api-key` ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L17)) and fails fast if either is missing ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L66)).
- Cosmos credentials are fetched at deploy time via `az cosmosdb keys list` and passed into Container Apps as env vars ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L242)).
- `FLASK_SECRET_KEY` is auto-generated and persisted to `.env` if missing locally, but **must** exist in Key Vault for prod.

## Production checklist

- [ ] `FLASK_ENV=production`, `FLASK_DEBUG=0`
- [ ] `FLASK_SECRET_KEY` from Key Vault
- [ ] Cosmos credentials present (one of the three auth paths)
- [ ] `GOOGLE_CLOUD_API_KEY` from Key Vault if Google Vision/Translate is needed
- [ ] `OLLAMA_BASE_URL` set to internal Container App FQDN
- [ ] HTTPS enforced at Container App ingress (default for external ingress)
- [ ] Admin user provisioned via `scripts/manage_users.py` or AdminUsers UI
- [ ] Terms of Use text current — first-login users will be prompted

## Pitfalls

- Don't write a new decorator that reads `session["authenticated"]` or `session["user"]`. Those keys do not exist; the gate is `logged_in` + `user_email`.
- The single-session check rejects requests silently — if a route mysteriously 401s in tests, mock `UserDB.is_session_valid` to return `True`.
- Magic-link tokens are stored in process memory in the current implementation (`magic_links` dict). They do not survive worker restarts. Don't rely on them for long-lived flows.
- Adding a new env var? Update `.env.example`, `dev-start.sh`, [`deploy-chuuk.sh`](../../../deploy-chuuk.sh) (`ENV_ARGS`), and Key Vault if it's a secret.
