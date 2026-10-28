"""Tests for the saved sentence analyses blueprint, on a bare Flask app."""

from functools import wraps
from unittest.mock import MagicMock

import pytest
from bson import ObjectId
from flask import Flask, jsonify, session

from src.api.sentence_analyses import create_blueprint, query_key

pytestmark = pytest.mark.unit


def _login_required(f):
    @wraps(f)
    def inner(*a, **kw):
        if not session.get("logged_in"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*a, **kw)

    return inner


class FakeCursor(list):
    """A list that also answers pymongo's sort/limit chaining."""

    def sort(self, key, direction=1):
        return FakeCursor(sorted(self, key=lambda d: d.get(key) or 0, reverse=direction == -1))

    def limit(self, n):
        return FakeCursor(self[:n])


class FakeCollection:
    def __init__(self):
        self.docs = []

    def _match(self, q):
        return [d for d in self.docs if all(d.get(k) == v for k, v in q.items())]

    def find(self, q=None, projection=None):
        rows = [dict(d) for d in self._match(q or {})]
        if projection:
            rows = [{k: v for k, v in d.items() if projection.get(k)} for d in rows]
        return FakeCursor(rows)

    def find_one(self, q, projection=None):
        m = self._match(q)
        return dict(m[0]) if m else None

    def update_one(self, q, update, upsert=False):
        m = self._match(q)
        if m:
            m[0].update(update.get("$set", {}))
            return MagicMock(upserted_id=None)
        doc = {"_id": ObjectId(), **q, **update.get("$setOnInsert", {}), **update.get("$set", {})}
        self.docs.append(doc)
        return MagicMock(upserted_id=doc["_id"])

    def delete_one(self, q):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in q.items())]
        return MagicMock(deleted_count=before - len(self.docs))


@pytest.fixture()
def harness():
    col = FakeCollection()
    db = MagicMock()
    db.db = {"sentence_analyses": col}
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="t")
    app.register_blueprint(create_blueprint(lambda: db, _login_required, lambda fn: fn()))
    client = app.test_client()
    return app, client, col


def _login(client, email="me@example.com", role="user"):
    with client.session_transaction() as s:
        s["logged_in"] = True
        s["user_email"] = email
        s["user_role"] = role


def test_query_key_folds_case_and_whitespace():
    assert query_key("  Jiowa   a tongei ") == "jiowa a tongei"


def test_requires_login(harness):
    _, client, _ = harness
    assert client.get("/api/sentence-analyses").status_code == 401


def test_save_list_get_roundtrip_and_upsert(harness):
    _, client, col = harness
    _login(client)
    body = {
        "sentence": "Jiowa a tongei aramas.",
        "words": [{"word": "Jiowa", "key": "jiowa"}, {"word": "a", "key": "a"}, {"word": "tongei", "key": "tongei"}, {"word": "aramas", "key": "aramas"}],
        "dictionary": {"jiowa": {"english": "Jehovah"}, "tongei": {"english": "love"}},
        "translation": {"text": "Jehovah loves people.", "engine": "MADLAD-400"},
        "source": None,
        "user_translation": None,
    }
    res = client.post("/api/sentence-analyses", json=body)
    assert res.status_code == 200
    saved_id = res.get_json()["id"]
    assert len(col.docs) == 1
    doc = col.docs[0]
    assert doc["word_count"] == 4 and doc["known_count"] == 2
    assert doc["has_user_translation"] is False and doc["created_by"] == "me@example.com"

    # Same sentence again, now with a user translation: one record, updated.
    body["user_translation"] = {"english": "Jehovah loves people.", "source": "wol.jw.org", "citation": "w26"}
    res = client.post("/api/sentence-analyses", json={**body, "sentence": "Jiowa  a tongei aramas."})
    assert res.get_json()["id"] == saved_id
    assert len(col.docs) == 1
    assert col.docs[0]["has_user_translation"] is True
    assert col.docs[0]["user_translation"]["saved_by"] == "me@example.com"

    listed = client.get("/api/sentence-analyses").get_json()
    assert [d["id"] for d in listed] == [saved_id]
    assert listed[0]["has_user_translation"] is True and listed[0]["word_count"] == 4
    assert "dictionary" not in listed[0]

    full = client.get(f"/api/sentence-analyses/{saved_id}").get_json()
    assert full["dictionary"]["jiowa"]["english"] == "Jehovah"
    assert full["user_translation"]["english"] == "Jehovah loves people."
    assert isinstance(full["updated_at"], str)


def test_delete_only_owner_or_admin(harness):
    _, client, col = harness
    _login(client, email="owner@example.com")
    saved_id = client.post("/api/sentence-analyses", json={"sentence": "Ese wor.", "words": []}).get_json()["id"]

    _login(client, email="other@example.com")
    assert client.delete(f"/api/sentence-analyses/{saved_id}").status_code == 403
    _login(client, email="admin@example.com", role="admin")
    assert client.delete(f"/api/sentence-analyses/{saved_id}").status_code == 200
    assert col.docs == []


def test_bad_ids_and_empty_sentence(harness):
    _, client, _ = harness
    _login(client)
    assert client.get("/api/sentence-analyses/not-an-id").status_code == 400
    assert client.post("/api/sentence-analyses", json={"sentence": "  "}).status_code == 400
    assert client.get(f"/api/sentence-analyses/{ObjectId()}").status_code == 404
