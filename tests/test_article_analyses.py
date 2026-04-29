import importlib
import os
from datetime import datetime, timezone
from bson import ObjectId
from unittest.mock import MagicMock
from unittest.mock import patch


COSMOS_EXCLUDED_ORDER_BY_ERROR = (
    "Error=2, Details='Response status code does not indicate success: BadRequest (400); "
    "Reason: (Message: {\"Errors\":[\"The index path corresponding to the specified "
    "order-by item is excluded.\"]})'"
)


class FakeUpdateResult:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


class FakeDeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class FakeCollection:
    def __init__(self):
        self.docs = []

    def find(self, query=None, projection=None):
        query = query or {}
        matched = [doc.copy() for doc in self.docs if all(doc.get(key) == value for key, value in query.items())]
        if projection:
            projected = []
            for doc in matched:
                item = {}
                for key, enabled in projection.items():
                    if enabled and key in doc:
                        item[key] = doc[key]
                projected.append(item)
            return projected
        return matched

    def find_one(self, query=None, projection=None):
        results = self.find(query, projection)
        return results[0] if results else None

    def update_one(self, query, update, upsert=False):
        existing = None
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                existing = doc
                break

        if existing is not None:
            existing.update(update.get("$set", {}))
            return FakeUpdateResult()

        if not upsert:
            return FakeUpdateResult()

        new_doc = {"_id": ObjectId()}
        new_doc.update(query)
        new_doc.update(update.get("$setOnInsert", {}))
        new_doc.update(update.get("$set", {}))
        self.docs.append(new_doc)
        return FakeUpdateResult(new_doc["_id"])

    def insert_many(self, docs):
        self.docs.extend(doc.copy() for doc in docs)

    def delete_many(self, query):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not all(doc.get(key) == value for key, value in query.items())]
        return FakeDeleteResult(before - len(self.docs))

    def delete_one(self, query):
        deleted = self.delete_many(query).deleted_count
        return FakeDeleteResult(1 if deleted else 0)


def test_article_analysis_list_falls_back_when_cosmos_rejects_sort():
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault("COSMOS_DB_CONNECTION_STRING", "")

    with patch("src.database.dictionary_db.DictionaryDB", return_value=MagicMock(db=None)):
        import app as flask_module  # noqa: PLC0415

        flask_module = importlib.reload(flask_module)

        sort_cursor = MagicMock()
        sort_cursor.sort.side_effect = Exception(COSMOS_EXCLUDED_ORDER_BY_ERROR)

        docs = [
            {
                "_id": "older",
                "chuukese_title": "Older",
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            },
            {
                "_id": "newer",
                "chuukese_title": "Newer",
                "created_at": "2026-02-01T00:00:00+00:00",
            },
        ]
        unsorted_cursor = MagicMock()
        unsorted_cursor.limit.return_value = docs

        collection = MagicMock()
        collection.find.side_effect = [sort_cursor, unsorted_cursor]
        flask_module.dict_db.db = {"article_analyses": collection}

        client = flask_module.app.test_client()
        with client.session_transaction() as session:
            session["logged_in"] = True
            session["user_email"] = "test@example.com"
            session["user_role"] = "admin"

        response = client.get("/api/article-analyses")

        assert response.status_code == 200
        payload = response.get_json()
        assert [item["_id"] for item in payload] == ["newer", "older"]
        assert payload[0]["created_at"] == "2026-02-01T00:00:00+00:00"


def test_article_analysis_save_and_get_use_split_paragraph_storage():
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault("COSMOS_DB_CONNECTION_STRING", "")

    with patch("src.database.dictionary_db.DictionaryDB", return_value=MagicMock(db=None)):
        import app as flask_module  # noqa: PLC0415

        flask_module = importlib.reload(flask_module)

        metadata = FakeCollection()
        paragraphs = FakeCollection()
        flask_module.dict_db.db = {
            "article_analyses": metadata,
            "article_analysis_paragraphs": paragraphs,
        }

        client = flask_module.app.test_client()
        with client.session_transaction() as session:
            session["logged_in"] = True
            session["user_email"] = "test@example.com"
            session["user_role"] = "admin"

        save_response = client.post(
            "/api/article-analyses",
            json={
                "url": "https://example.com/article",
                "chuukese_title": "Saved title",
                "paragraph_count": 2,
                "sentence_count": 3,
                "paragraphs": [
                    {"index": 0, "raw_text": "one", "sentences": [], "sentence_count": 0},
                    {"index": 1, "raw_text": "two", "sentences": [], "sentence_count": 0},
                ],
            },
        )

        assert save_response.status_code == 200
        saved_id = ObjectId(save_response.get_json()["id"])

        assert metadata.docs[0]["url"] == "https://example.com/article"
        assert "paragraphs" not in metadata.docs[0]
        assert len(paragraphs.docs) == 2
        assert all(doc["analysis_id"] == saved_id for doc in paragraphs.docs)

        get_response = client.get(f"/api/article-analyses/{saved_id}")

        assert get_response.status_code == 200
        payload = get_response.get_json()
        assert payload["_id"] == str(saved_id)
        assert [paragraph["raw_text"] for paragraph in payload["paragraphs"]] == ["one", "two"]