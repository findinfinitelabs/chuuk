"""The version endpoint the update toast polls, and active sessions that
survive a restart because they are read back from the user record."""

from unittest.mock import MagicMock

import app as app_module


def test_api_version_reports_first_release(client):
    data = client.get("/api/version").get_json()
    assert data["version"].count(".") == 3
    assert data["title"]


def test_active_session_is_read_from_user_record_after_restart(monkeypatch):
    """A new container starts with an empty cache; the session id stored on
    the user record keeps the person signed in."""
    user_db = MagicMock()
    user_db.is_connected.return_value = True
    user_db.get_active_session.return_value = "abc123"
    monkeypatch.setattr(app_module, "get_user_db", lambda: user_db)
    app_module._active_sessions.clear()
    assert app_module._get_active_session("Chris@Example.com") == "abc123"
    user_db.get_active_session.assert_called_once_with("chris@example.com")
    # Cached afterwards: no second read.
    assert app_module._get_active_session("chris@example.com") == "abc123"
    user_db.get_active_session.assert_called_once()
    app_module._set_active_session("chris@example.com", "def456")
    user_db.set_active_session.assert_called_once_with("chris@example.com", "def456")
    app_module._clear_active_session("chris@example.com")
    user_db.clear_active_session.assert_called_once_with("chris@example.com")
    assert "chris@example.com" not in app_module._active_sessions
