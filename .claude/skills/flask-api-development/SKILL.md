---
name: flask-api-development
description: Patterns for the Chuuk Dictionary Flask backend — single-file `app.py` monolith, role-permission gated routes, Cosmos DB / `DictionaryDB` integration, SSE processing streams, and the translate/correction loop. Use when adding/altering API endpoints, wiring auth into new routes, or modifying request/response shapes.
---

# Flask API Development

The backend is a **single-file monolith**: [app.py](../../../app.py) (~5,300 lines as of this writing). There are no Blueprints. New routes go directly into `app.py` and follow the conventions below.

## Layout snapshot

```
app.py                         # All routes, auth, translation orchestration, OCR glue
src/
  database/
    db_factory.py              # Cosmos / managed-identity / local-Mongo client
    dictionary_db.py           # DictionaryDB — search_word, add_word, search_phrases…
    user_db.py                 # UserDB — sessions, page-tracking, role/permissions
    publication_manager.py     # File metadata + uploads/<pub_id>/ filesystem
  translation/
    helsinki_translator_v2.py  # Marian fine-tuned models, BLEU eval
    llm_trainer.py             # Ollama wrapper + custom modelfile build
    hybrid_translator.py       # Programmatic three-engine wrapper (HTTP layer skips it)
  ocr/                         # OCRProcessor, EnhancedOCRProcessor, AdvancedDocumentParser
  pipeline/large_document_processor.py
  utils/                       # NWT EPUB parser, scripture parser, intelligent chunker
  core/jworg_lookup.py
frontend/                      # Vite + React 19 + Mantine v8, served from frontend/dist in prod
```

## Auth gate (the single most-confused thing)

The session keys you must set/read are:

| key | source | purpose |
|---|---|---|
| `session["logged_in"]` | login route | the boolean every route checks ([app.py](../../../app.py#L442)) |
| `session["user_email"]` | login route | identity |
| `session["user_role"]` | login route | role string |
| `session["session_id"]` | login route | single-active-session token |

There is **no** `session["authenticated"]` and **no** `session["user"]` — older code/tests use those names and silently fail. New decorators must check `logged_in` and validate `session_id` against `UserDB.is_session_valid(...)` ([app.py](../../../app.py#L696)).

Permission checks use `g.permissions` populated by the before-request handler at [app.py](../../../app.py#L481). The map is `ROLE_PERMISSIONS` at [app.py](../../../app.py#L462). When you add a new permission, add it both there and in the frontend's `hasPermission(...)` gates ([frontend/src/App.tsx](../../../frontend/src/App.tsx#L163)).

For the full auth story see the [auth-session-and-permissions-flow](../auth-session-and-permissions-flow/SKILL.md) skill.

## Active endpoint surface (selected)

Auth & users:
- `POST /api/auth/login` — access-code login ([app.py](../../../app.py#L505))
- `POST /api/auth/magic-link` ([app.py](../../../app.py#L577))
- `GET /api/auth/magic/<token>`
- `GET /api/auth/status`, `POST /api/auth/logout`, `POST /api/auth/track-page`, `POST /api/auth/accept-terms`
- `GET/POST/PATCH/DELETE /api/admin/users`

Dictionary CRUD:
- `POST /api/dictionary/entries` ([app.py](../../../app.py#L4973))
- `POST /api/dictionary/entries/bulk` ([app.py](../../../app.py#L5045))
- `GET /api/dictionary/search?q=...` (use `DictionaryDB.search_word` / `search_words`)

Publications & OCR (see [publication-ocr-processing-workflow](../publication-ocr-processing-workflow/SKILL.md)):
- `POST /api/publications`, `GET /api/publications`, `GET /api/publications/<id>` ([app.py](../../../app.py#L890))
- `POST /api/publications/<id>/upload` ([app.py](../../../app.py#L1180))
- `GET /api/processing/stream` — Server-Sent Events ([app.py](../../../app.py#L1129))

Translation (see [translation-orchestration-and-feedback](../translation-orchestration-and-feedback/SKILL.md)):
- `POST /api/translate` ([app.py](../../../app.py#L1538))
- `POST /api/translate/correction` ([app.py](../../../app.py#L1627))
- `GET /api/translate/training-status` ([app.py](../../../app.py#L1802))

Article & sentence analysis:
- Article fetch + analysis: [app.py](../../../app.py#L4398), [app.py](../../../app.py#L4492)
- Saved sentence analyses CRUD: [app.py](../../../app.py#L4806)

Scripture (see [scripture-reference-parsing](../scripture-reference-parsing/SKILL.md)):
- `GET /api/scripture/preview` ([app.py](../../../app.py#L3541))
- `GET /api/bible/coverage` ([app.py](../../../app.py#L2881))

JW.org lookup: [app.py](../../../app.py#L1982), article fetch [app.py](../../../app.py#L3668).

## Database access pattern

Use the singleton DBs that `app.py` imports lazily:

```python
from src.database.dictionary_db import DictionaryDB
from src.database.user_db import UserDB
from src.database.publication_manager import PublicationManager

dict_db = DictionaryDB()         # internally calls db_factory.get_cosmos_client()
user_db = UserDB()
pub_mgr = PublicationManager()
```

Do **not** instantiate a `MongoClient` directly. `db_factory` resolves auth in this order ([src/database/db_factory.py](../../../src/database/db_factory.py#L62)):

1. `COSMOS_MONGO_CONNECTION_STRING` (preferred)
2. Managed identity if `USE_MANAGED_IDENTITY=true` + `COSMOS_ACCOUNT_NAME`
3. `COSMOS_DB_URI` + `COSMOS_DB_KEY`
4. Fallback to local MongoDB

`COSMOS_DB_CONNECTION_STRING` (used in some old docs) is **not** read.

The collection attributes on `DictionaryDB` are `dictionary_collection`, `phrases_collection`, `users_collection`, `paragraphs_collection`, `pages_collection`, `words_collection`. Methods are `search_word`, `search_words`, `add_word`, `search_phrases`, `add_phrase` ([src/database/dictionary_db.py](../../../src/database/dictionary_db.py#L972)) — there is no `search_entries` / `bulk_insert_entries`.

## Conventions for new endpoints

1. Place the route alphabetically near its peers in `app.py` — there's no formal grouping but clusters exist.
2. Wrap with `@login_required` (uses the `logged_in` gate) and where applicable `@requires_permission("foo")`.
3. Return JSON with explicit shape `{ ok: bool, ...payload }` for write endpoints, raw payload for reads.
4. Failures should return `{ error: "..." }` + the appropriate 4xx/5xx, not raise.
5. SSE endpoints must use `Response(stream_with_context(gen()), mimetype="text/event-stream")` and ping every 15s — gunicorn's 300s timeout (set in [Dockerfile](../../../Dockerfile)) is the upper bound.
6. File uploads: use `secure_filename(...)`, validate against `ALLOWED_EXTENSIONS` ([app.py](../../../app.py#L248)), and write under `uploads/<pub_id>/`.
7. Heavy work (OCR, training) goes to background threads keyed by a stream ID so progress can be pushed via `/api/processing/stream`.

## Production runtime

Gunicorn from [Dockerfile](../../../Dockerfile#L40):
```
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 300 \
  --access-logfile - --error-logfile - app:app
```
Two workers means singletons (`DictionaryDB`, etc.) live per-worker. Anything you cache in process memory needs cache-bust strategy — there's no shared in-memory store.

## Testing

See the [testing-and-quality-assurance](../testing-and-quality-assurance/SKILL.md) skill. The shared mock DB lives in [tests/conftest.py](../../../tests/conftest.py) and is patched via `patch("src.database.dictionary_db.DictionaryDB", return_value=mock_db)`. The `auth_headers` fixture currently sets the wrong session keys — update it before relying on it.

## Pitfalls

- Don't reach into `session["user"]` — use `session["user_email"]`.
- Magic link tokens are single-use; in tests build the session directly rather than going through the email flow.
- Gunicorn 2 workers + Cosmos + SSE: do not assume a stream you started in worker A will be picked up in worker B. Stream IDs are local.
- If you add a new env var, also add it to `.env.example`, `dev-start.sh`, [`deploy-chuuk.sh`](../../../deploy-chuuk.sh) (`ENV_ARGS`), and document it in [docs/AZURE_DEPLOYMENT.md](../../../docs/AZURE_DEPLOYMENT.md).
