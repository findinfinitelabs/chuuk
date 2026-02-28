"""
Pytest fixtures for the Chuuk Dictionary test suite.

Provides:
- flask_app / client: test Flask client with in-memory mocks
- mock_db: mocked DictionaryDB so tests run without a real Cosmos DB connection
- auth_headers: pre-authenticated session headers for route tests
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path when tests are run from any directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Environment setup — must happen before app.py is imported
# ---------------------------------------------------------------------------

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("COSMOS_DB_CONNECTION_STRING", "")  # empty → app falls back gracefully


# ---------------------------------------------------------------------------
# Database mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mock_db() -> MagicMock:
    """Return a MagicMock that mimics DictionaryDB.

    Callers can configure return values per test, e.g.::

        mock_db.dictionary_collection.find_one.return_value = {...}
    """
    db = MagicMock()
    # Make the client truthy so auth/connection guards pass
    db.client = MagicMock()
    # Default collection query returns an empty list
    db.dictionary_collection.find.return_value = iter([])
    db.dictionary_collection.find_one.return_value = None
    db.dictionary_collection.count_documents.return_value = 0
    db.phrases_collection.find.return_value = iter([])
    db.phrases_collection.find_one.return_value = None
    db.users_collection.find_one.return_value = None
    return db


# ---------------------------------------------------------------------------
# Flask app / client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def flask_app(mock_db: MagicMock):
    """Return a Flask application instance configured for testing.

    The real database and Helsinki translator are replaced with mocks so that
    the test suite runs without any external services.
    """
    with (
        patch("src.database.dictionary_db.DictionaryDB", return_value=mock_db),
        patch("builtins.open", side_effect=_safe_open),
    ):
        import app as flask_module  # noqa: PLC0415

        flask_module.app.config.update(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
                "SECRET_KEY": "test-secret-key-not-for-production",
            }
        )
        yield flask_module.app


@pytest.fixture()
def client(flask_app):
    """Return a Flask test client."""
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Authentication helper
# ---------------------------------------------------------------------------

@pytest.fixture()
def auth_headers(client, flask_app) -> dict:
    """Return headers / cookies for a pre-authenticated test session.

    Uses the Flask test-session interface so no real magic link is needed.
    """
    with flask_app.test_request_context():
        with client.session_transaction() as sess:
            sess["user"] = "test@example.com"
            sess["authenticated"] = True
    return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_open(path, *args, **kwargs):
    """Allow opening config JSON files; block everything else during testing."""
    allowed_prefixes = (
        str(_PROJECT_ROOT / "config"),
        str(_PROJECT_ROOT / "models"),
    )
    path_str = str(path)
    if any(path_str.startswith(p) for p in allowed_prefixes):
        return open(path, *args, **kwargs)  # noqa: WPS515
    mock_fh = MagicMock()
    mock_fh.__enter__ = lambda s: s
    mock_fh.__exit__ = MagicMock(return_value=False)
    mock_fh.read.return_value = ""
    return mock_fh
