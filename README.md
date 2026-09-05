# Chuuk Dictionary

A full-stack web application for digitizing, building, and using a Chuukese ↔ English
dictionary. It combines OCR ingestion of scanned publications, a structured bilingual
database, a fine-tunable neural translation stack, and a set of language-learning tools.

Chuukese is a low-resource Micronesian language with very little digitized material.
This project exists to build that corpus and turn it into usable translation models.

## What it does

**1. Digitize** — Upload scanned dictionary pages, PDFs, or DOCX files. Tesseract and
Google Cloud Vision run OCR, and a structure-aware parser turns raw lines into
dictionary entries with grammar types, examples, and confidence scores. Progress
streams to the browser over Server-Sent Events.

**2. Store** — Entries live in Azure Cosmos DB (MongoDB API) across five collections:
dictionary entries, pages, words, phrases, and paragraphs. Full CRUD, search,
import/export, and per-field statistics are exposed through the API.

**3. Translate** — Helsinki-NLP OPUS-MT models fine-tuned for Chuukese in both
directions, with an optional Ollama LLM backend. Every user correction is captured as a
training pair.

**4. Retrain** — A continuous trainer collects CHK↔EN pairs from every collection.
LoRA adapters apply a single corrected pair immediately; full fine-tune merges run on a
schedule. Fine-tuned weights persist to an Azure Files share so they survive redeploys.

**5. Learn** — Grammar reference, a verb-phrase builder, a sentence composer, sentence
analysis, a translation game, and article analysis that fetches a JW.org article and
highlights every word against the dictionary.

## Architecture

```
frontend/          React 19 + TypeScript + Vite + Mantine v8 (15 pages)
    │  axios, cookie sessions, permission-gated routes
    ▼
app.py             Flask monolith — 83 routes, role-gated, serves the built SPA
    │
    ├── src/ocr/          Tesseract + Google Vision, structure-aware parsing
    ├── src/pipeline/     200+ page document processing
    ├── src/database/     DictionaryDB, UserDB, PublicationManager, db_factory
    ├── src/translation/  Helsinki OPUS-MT (v1/v2), Ollama, hybrid fallback
    ├── src/training/     Continuous trainer, LoRA, AI training data generator
    ├── src/core/         JW.org lookup
    └── src/utils/        NWT EPUB parser, scripture parser, chunker
    ▼
Azure Cosmos DB (MongoDB API)

mcp_server/        MCP tools (translate, fix_translation, teach_pair, training)
```

`app.py` is deliberately a single file. Route groups are separated by banner comments.

## Prerequisites

- Python 3.11
- Node.js 22 (required by Vite 7 and React Router 7)
- Tesseract OCR
- A MongoDB instance, Cosmos DB Emulator, or Azure Cosmos DB account

Install Tesseract:

```bash
brew install tesseract                       # macOS
sudo apt-get install tesseract-ocr           # Debian/Ubuntu
```

Windows builds: <https://github.com/UB-Mannheim/tesseract/wiki>

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt              # full stack, including torch/transformers
cd frontend && npm ci && cd ..
cp .env.example .env                         # then edit — see Configuration
```

`requirements.runtime.txt` is a slimmer set (no ML packages) for running the web app
without the translation and training features.

### Create the first user

Authentication is access-code based — there are no passwords. Users are read from
Cosmos DB, falling back to the `APP_USERS_JSON` environment variable, falling back to
`config/users.json`.

```bash
python scripts/manage_users.py add you@example.com --name "Your Name" --role admin
```

Other subcommands: `list`, `remove`, `regenerate`, `generate`. The generated access code
is what you enter at the login screen. Users created locally are auto-synced to Cosmos DB
on first app start.

**Note:** `manage_users.py` reads and writes `config/users.json` only — it has no Cosmos
DB code path. Once users live in Cosmos (which is where the running app looks first), the
script's `regenerate` and `remove` subcommands will report "user not found" and change
nothing. To modify a user that exists in Cosmos, go through `UserDB` in
`src/database/user_db.py`, or the admin UI at `/admin/users`.

## Running

The one-command path starts the database, Flask, and Vite together:

```bash
./run.sh start      # also: stop | restart | status | logs
```

Or run the pieces yourself:

```bash
python app.py                    # Flask on :5002
cd frontend && npm run dev       # Vite on :5173, proxies /api to :5002
```

In development, use <http://localhost:5173>. In production Flask serves the built
frontend from `frontend/dist` and everything runs on one port.

## Configuration

All settings come from environment variables, loaded from `.env` locally.

### Database

Connection is resolved in order by `src/database/db_factory.py`:

| Variable | Purpose |
|---|---|
| `COSMOS_MONGO_CONNECTION_STRING` / `COSMOS_CONNECTION_STRING` | Full Cosmos DB MongoDB connection string |
| `COSMOS_ACCOUNT_NAME` + `USE_MANAGED_IDENTITY` | Azure managed identity auth (preferred in production) |
| `COSMOS_DB_URI`, `COSMOS_DB_KEY` | Cosmos endpoint and key |
| `MONGODB_URI` | Local MongoDB, e.g. `mongodb://localhost:27017/` |

### Application

| Variable | Default | Purpose |
|---|---|---|
| `FLASK_SECRET_KEY` | random | Session signing. **Required** when `FLASK_ENV=production` |
| `FLASK_ENV` | — | `development` enables debug mode and relaxes cookie security |
| `PORT` | `5002` | Flask listen port |
| `UPLOAD_FOLDER` | `uploads` | Where uploaded pages are written |
| `MAX_CONTENT_LENGTH` | `16777216` | Upload size cap in bytes |
| `APP_USERS_JSON` | — | Inline users JSON, for containers without Cosmos DB |

### OCR

| Variable | Purpose |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to a Google Cloud service account JSON key |
| `GOOGLE_CLOUD_API_KEY` / `GOOGLE_VISION_API_KEY` | Vision API key alternative |

Tesseract alone is enough; Google Vision improves accuracy on difficult scans.

### Translation and training

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_ENABLED` | `false` | Enable the Ollama LLM backend (resource-heavy) |
| `OLLAMA_BASE_URL` | — | Ollama sidecar endpoint |
| `MODEL_STORE_PATH` | — | Writable path for fine-tuned weights, preferred over baked-in `models/` |
| `FORCE_CPU` | — | Skip CUDA/MPS detection during training |
| `TRAINING_INTERVAL_MINUTES` | `30` | Scheduled fine-tune interval |
| `TRAINING_MIN_NEW_PAIRS` | `10` | Minimum new pairs before a scheduled run fires |
| `LORA_MERGE_THRESHOLD` | `50` | LoRA updates before merging into the base model |

### Magic-link email

Optional — login also works with the access code alone.

`SMTP_HOST` (default `smtp.gmail.com`), `SMTP_PORT` (default `587`), `SMTP_USER`,
`SMTP_PASSWORD`, `SMTP_FROM`. Links expire after 15 minutes.

## Authentication and roles

Login accepts either an access code or an emailed magic link. Only one session per user
is active at a time — logging in elsewhere invalidates the previous session.

Three roles gate both API routes and frontend navigation, defined in `ROLE_PERMISSIONS`
in `app.py`:

| Role | Access |
|---|---|
| `user` | Home, Lookup, Sentences, Translate, Grammar |
| `translator` | The above, plus Database, Translation Game, AI Training |
| `admin` | Everything, plus Publications and User Management |

The frontend reads its permission list from `GET /api/auth/status` and hides routes it
lacks; the server enforces the same rules with `@role_required`.

## API

83 routes. Most sit under `/api`; a handful of older unprefixed ones remain
(`/translate_helsinki`, `/train_helsinki`, `/evaluate_helsinki`, `/train_ollama`,
`/model_status`, `/database`), and the upload and OCR routes are registered at both
their `/api` and legacy paths. The main groups:

| Group | Examples |
|---|---|
| Auth | `POST /api/auth/login`, `POST /api/auth/request-magic-link`, `GET /api/auth/status`, `POST /api/auth/logout` |
| Admin | `GET/POST /api/admin/users`, `DELETE /api/admin/users/<email>` |
| Publications | `GET/POST /api/publications`, `POST /api/publications/<id>/upload`, `POST /api/publications/<id>/upload_csv` |
| OCR | `POST /api/ocr/process`, `POST /api/ocr/reprocess`, `GET /api/processing/stream/<session_id>` (SSE) |
| Dictionary | `GET/POST/PUT/DELETE /api/database/entries`, `/api/database/stats`, `/api/database/export`, `/api/database/import` |
| Translation | `POST /api/translate`, `POST /api/translate/correction`, `GET /api/translate/training-status` |
| AI training | `POST /api/ai-training/start`, `POST /api/ai-training/lora-teach`, `GET /api/ai-training/stream` (SSE) |
| Scripture | `POST /api/scripture/preview`, `GET /api/database/bible-coverage` |
| Corpus | `POST /api/articles/fetch`, `POST /api/sentences/analyze`, `GET/POST /api/brochures/match/words` |

## Testing

```bash
pytest                      # collects tests/ per pytest.ini
pytest -m unit              # markers: unit, integration, translation, slow
```

`tests/` holds the pytest suite and nothing else. Run-by-hand debug and inspection
scripts live in `scripts/debug/` — they have no assertions and several connect to a live
database, so they are deliberately kept where pytest will not import them. See
`scripts/debug/README.md`.

Note that the test suite needs Python 3.10+; parts of `src/` use `X | None` annotations
at runtime, which raise `TypeError` on 3.9.

## Deployment

Deploys to Azure Container Apps.

```bash
./deploy-chuuk.sh
```

The script builds the image remotely with `az acr build`, pulls secrets from Key Vault,
injects Cosmos DB credentials, and mounts an Azure Files share at `/app/model_store` so
fine-tuned weights survive restarts and scale-to-zero. Override any of `RESOURCE_GROUP`,
`ACR_NAME`, `KEY_VAULT_NAME`, `AZURE_SUBSCRIPTION`, and friends via environment
variables.

`Dockerfile` is a multi-stage build: Node 22 builds the frontend, Python 3.11-slim runs
Gunicorn on port 8000 with Tesseract installed. `Dockerfile.ollama` builds the optional
LLM sidecar. There is no docker-compose.

`.github/workflows/deploy-main-app.yml` runs the same script from CI; it is
manual-trigger only. See `.github/SETUP_SECRETS.md` for the service principal setup.

Further detail lives in `docs/AZURE_DEPLOYMENT.md` and
`docs/COSMOS_DB_CONTAINER_SETUP.md`.

## MCP server

Translation and training are also exposed as MCP tools — `translate`,
`fix_translation`, `start_training`, `get_training_status`, `teach_pair`:

```bash
python -m mcp_server.run_stdio      # stdio transport
python -m mcp_server.run_http       # HTTP, port from MCP_HTTP_PORT
```

The MCP SDK is not in `requirements.txt`; install it separately if you need this.

## Repository layout

```
app.py                  Flask application (all routes)
src/                    Backend modules — see Architecture above
frontend/               React SPA
mcp_server/             MCP tool server
config/                 Grammar data, scripture book names, NWT EPUBs, brochures
models/                 Fine-tuned Helsinki OPUS-MT checkpoints
scripts/                Data loading, migrations, corpus extraction, user management
scripts/debug/          Ad-hoc inspection scripts — not tests, not collected by pytest
tests/                  Pytest suite
docs/                   Deployment and subsystem guides
.claude/skills/         Task-specific guides for each subsystem
```

## License

MIT — see `LICENSE`.
