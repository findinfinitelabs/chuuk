---
name: database-management-operations
description: Conventions for the Chuuk Dictionary persistence layer — Azure Cosmos DB (MongoDB API) via `db_factory`, `DictionaryDB`, `UserDB`, and `PublicationManager`. Covers connection-resolution order, the actual collection/method names in use, and the managed-identity path. Use when adding queries, debugging connection issues, or extending the schema.
---

# Database Management Operations

All persistence is **Azure Cosmos DB with MongoDB API** via `pymongo`. There is no SQLAlchemy, no SQLite, no relational layer. Three Python classes wrap it; nothing instantiates `MongoClient` directly.

## Layout

| File | Class / role |
|---|---|
| [`src/database/db_factory.py`](../../../src/database/db_factory.py) | Connection helpers (`get_cosmos_client`, `get_database_client`, `get_database_config`) |
| [`src/database/dictionary_db.py`](../../../src/database/dictionary_db.py) | `DictionaryDB` — entries, words, phrases, paragraphs, pages |
| [`src/database/user_db.py`](../../../src/database/user_db.py) | `UserDB` — users, role/permissions, sessions, page-tracking |
| [`src/database/publication_manager.py`](../../../src/database/publication_manager.py) | `PublicationManager` — publication metadata + uploads/ filesystem |

## Connection resolution order

[`db_factory.get_cosmos_client()`](../../../src/database/db_factory.py#L62) tries, in order:

1. `COSMOS_MONGO_CONNECTION_STRING` — direct MongoDB connection string. **Preferred** in production. (Older docs reference `COSMOS_DB_CONNECTION_STRING`; that name is **not** read.)
2. **Managed Identity** if `USE_MANAGED_IDENTITY=true` + `COSMOS_ACCOUNT_NAME` are set ([db_factory.py](../../../src/database/db_factory.py#L20)).
3. `COSMOS_DB_URI` + `COSMOS_DB_KEY` — builds the connection string locally with URL-encoded key.
4. Local MongoDB at `mongodb://localhost:27017/` as fallback.

Environment variables actually consulted:

| Var | Used by |
|---|---|
| `COSMOS_MONGO_CONNECTION_STRING` | preferred path |
| `USE_MANAGED_IDENTITY` (`true`/`false`) | managed-identity gate |
| `COSMOS_ACCOUNT_NAME` (default `chuuk-dictionary-cosmos`) | both managed identity + URI build |
| `COSMOS_DB_URI`, `COSMOS_DB_KEY` | key-based auth |

`retryWrites=False` and `appName=@<account>@` are required by Cosmos's MongoDB API and are baked into the generated connection string.

## Database & collection names

From [`get_database_config()`](../../../src/database/db_factory.py#L130):

```python
{
  "database_name":     "chuuk_dictionary",
  "container_name":    "dictionary_entries",   # → DictionaryDB.dictionary_collection
  "pages_container":   "dictionary_pages",     # → pages_collection
  "words_container":   "words",                # → words_collection
  "phrases_container": "phrases",              # → phrases_collection
  "paragraphs_container": "paragraphs",        # → paragraphs_collection
  "users_container":   "users",                # → UserDB.users_collection
}
```

## DictionaryDB — actual API

The methods that actually exist (see [dictionary_db.py](../../../src/database/dictionary_db.py#L972)):

- `search_word(word: str) -> dict | None`
- `search_words(query: str, limit: int = 50) -> list[dict]`
- `add_word(word: str, translation: str, **meta) -> str`
- `search_phrases(query: str, limit: int = 50) -> list[dict]`
- `add_phrase(chuukese: str, english: str, **meta) -> str`
- Plus direct collection access (`dict_db.dictionary_collection.find(...)`) for ad-hoc queries.

There is **no** `search_entries`, `bulk_insert_entries`, `get_all_entries`, etc. Older skill docs invented those.

## UserDB

[`UserDB`](../../../src/database/user_db.py#L11) handles auth-adjacent state:

- `get_user(email)`, `upsert_user(email, role)`
- `start_session(email)` — issues a `session_id`, invalidates prior active session for that email
- `is_session_valid(email, session_id)` — single-active-session enforcement
- `track_page(email, page)` — appends to `pages_accessed`, updates `last_activity_at` ([user_db.py](../../../src/database/user_db.py#L164))
- Schema fields: `email`, `role`, `session_id`, `session_start_at`, `last_activity_at`, `pages_accessed`, `accepted_terms_at`

## PublicationManager

[`PublicationManager`](../../../src/database/publication_manager.py#L10) coordinates DB metadata + the filesystem under `uploads/`:

- `create_publication(title, author, ...)` — writes Cosmos doc + creates `uploads/<id>/` dir
- `add_page(pub_id, file)` — saves file, adds page metadata
- `get_publication(pub_id)`, `list_publications()`
- Page metadata is persisted both in Cosmos and in a per-publication JSON sidecar ([publication_manager.py](../../../src/database/publication_manager.py#L18)) — keep them in sync if you mutate either directly.

## Common patterns

```python
from src.database.dictionary_db import DictionaryDB
from src.database.user_db import UserDB

dict_db = DictionaryDB()  # Singleton-ish — instantiate once per worker
user_db = UserDB()

# Search (escape user input!)
results = dict_db.search_words(user_query, limit=50)

# Direct collection query when method doesn't fit
import re
pattern = re.escape(user_input)
rows = dict_db.dictionary_collection.find(
    {"chuukese_word": {"$regex": pattern, "$options": "i"}},
    limit=50,
)

# Insert with audit fields
from datetime import datetime, timezone
dict_db.dictionary_collection.insert_one({
    "chuukese_word": word,
    "english_translation": meaning,
    "grammar_type": pos,
    "confidence_score": 0.9,
    "edited_by": user_email,
    "created_at": datetime.now(timezone.utc),
})
```

## Cosmos DB constraints

- `pymongo` version is pinned in [requirements.txt](../../../requirements.txt) for Cosmos wire-protocol compatibility — don't bump unilaterally.
- `retryWrites=False` is mandatory (already in connection string).
- RU budget matters: avoid full collection scans; prefer indexed `chuukese_word` / `english_translation` queries.
- Cosmos's MongoDB API ignores some `$regex` flags silently — case-insensitive search via `$options: "i"` is fine; lookahead/lookbehind are not.
- The factory's local-MongoDB fallback is for tests/dev only — production must have Cosmos credentials.

## Pitfalls

- The 2-worker gunicorn setup means `DictionaryDB()` is instantiated twice. Don't add per-instance caches and expect them to be coherent across requests.
- When adding a new collection, plumb it into `get_database_config()` AND the `DictionaryDB.__init__` block so `_collection` attributes stay consistent.
- Managed-identity path requires the workload identity to have a Cosmos RBAC role assigned — see [docs/AZURE_DEPLOYMENT.md](../../../docs/AZURE_DEPLOYMENT.md).
- Renaming a collection in `get_database_config()` does **not** rename the underlying Cosmos container — you must run an Azure-side migration.
