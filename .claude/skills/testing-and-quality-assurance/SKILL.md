---
name: testing-and-quality-assurance
description: Pytest patterns for the Chuuk Dictionary backend — running the suite, the shared `mock_db` / `client` / `auth_headers` fixtures, the right places to patch (`DictionaryDB` class, not `app.dict_db`), and how to mark unit vs integration vs translation tests. Use when adding tests, fixing fixture failures, or wiring CI.
---

# Testing & Quality Assurance

## Running the suite

From repo root with `.venv` active:

```bash
.venv/bin/python -m pytest                    # full suite
.venv/bin/python -m pytest -m unit            # unit only
.venv/bin/python -m pytest -m "not slow"      # skip slow ML tests
.venv/bin/python -m pytest tests/test_basic.py -v
```

`pytest.ini` config:
- `testpaths = tests`
- `--strict-markers` — unknown markers fail.
- Filters out `transformers`/`torch` deprecation noise.

## Markers (enforced)

| Marker | Use for |
|---|---|
| `unit` | Pure logic, no I/O, no network, no model load. |
| `integration` | Hits real DB or external services. Skipped in CI by default. |
| `translation` | Loads Helsinki / Ollama models. Slow + heavy. |
| `slow` | Anything > 5s. |

Always mark a test. Unmarked tests run in every job and slow CI down.

## Fixtures (from [tests/conftest.py](../../../tests/conftest.py))

| Fixture | Scope | What you get |
|---|---|---|
| `mock_db` | session | `MagicMock` shaped like `DictionaryDB` (collections respond to `.find/.find_one/.count_documents`) |
| `flask_app` | session | The real Flask `app` with `DictionaryDB` patched to `mock_db` and a guarded `open()` |
| `client` | function | `flask_app.test_client()` |
| `auth_headers` | function | Currently sets the wrong session keys — see warning below |

The mock is wired by `patch("src.database.dictionary_db.DictionaryDB", return_value=mock_db)` — i.e. patching the **class** before `app` is imported. **Do not** later try `patch("app.dict_db", ...)`; the singleton is already the mock and re-patching at the module level fights the class-level patch.

## ⚠️ The `auth_headers` fixture is broken

It sets `sess["authenticated"]` and `sess["user"]`, but the production gate checks `sess["logged_in"]` + `sess["user_email"]` + `sess["session_id"]` ([app.py](../../../app.py#L442)). Until the fixture is fixed, build the session inline in your test:

```python
def test_authenticated_route(client, flask_app):
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["user_email"] = "test@example.com"
        sess["user_role"] = "admin"
        sess["session_id"] = "test-session"
    # Also bypass the single-session DB check
    with patch("app.get_user_db") as gud:
        gud.return_value.is_session_valid.return_value = True
        resp = client.get("/api/dictionary/search?q=ran")
    assert resp.status_code == 200
```

If you fix `auth_headers`, also patch `is_session_valid` inside it.

## Configuring `mock_db` per test

```python
def test_search(client, mock_db):
    mock_db.search_words.return_value = [
        {"chuukese_word": "ran", "english_translation": "water"}
    ]
    # OR via raw collection:
    mock_db.dictionary_collection.find.return_value = iter([
        {"chuukese_word": "ran", "english_translation": "water"}
    ])
```

The methods that exist on the real `DictionaryDB` (and that you should mock):
- `search_word`, `search_words`, `add_word`
- `search_phrases`, `add_phrase`

There is **no** `search_entries`, `bulk_insert_entries`, etc. Don't mock methods that don't exist — the real code will never call them.

## Translation tests

```python
@pytest.mark.translation
@pytest.mark.slow
def test_helsinki_chk_to_en():
    from src.translation.helsinki_translator_v2 import HelsinkiTranslator
    t = HelsinkiTranslator()
    t.setup_models()  # no direction arg
    assert t.translate("ran", "chk_to_en") == "water"
```

Use BLEU only when you control the reference set — small samples are noisy.

## Test file inventory

The `tests/` directory mixes real pytest tests and exploratory scripts. Files prefixed `test_` are collected:

- `test_basic.py` — publication manager, jworg lookup. *Some assertions hit the network — mark `integration`.*
- `test_collections.py` — DB collection ops.
- `test_helsinki_trainer.py` — fine-tuner helpers (mark `slow`).
- `test_translation.py` — end-to-end translate (mark `translation`/`slow`).
- `test_scripture_parsing.py` — pure unit (regex, book lookup).
- `test_word_families.py` — pure unit.

Scripts without the `test_` prefix (e.g. `find_complex_words.py`, `debug_models.py`) are **not** test runners — they exist for one-off investigation.

## CI guidance

The default CI invocation should be `pytest -m "not slow and not translation and not integration"` to keep runs fast. Translation/integration jobs run on a separate, slower lane.

## Pitfalls

- Importing `app` triggers DB init — that's why fixtures patch `DictionaryDB` before the import. Don't `import app` at module top of a test file; let the fixture do it.
- The `_safe_open` in conftest blocks file opens outside `config/` and `models/` — if your test needs to read a file, point it under `config/` or extend the allowlist.
- Two gunicorn workers in prod ≠ test fixture state. Don't write tests that assume cross-request in-memory state.
- `WTF_CSRF_ENABLED=False` is set in the fixture, but the app does not actually use Flask-WTF — the flag is a no-op kept for legacy reasons.
