"""
Saved sentence analyses (/api/sentence-analyses).

The Sentence Analysis page keeps every analysis it completes — the words
with their dictionary maps, the model translation, the source text found on
wol.jw.org and any translation the user added — so it can be reopened from
the page's sidebar without re-running the lookups. One document per
sentence: analyzing the same sentence again overwrites the earlier record.

Registered from app.py with the app's own database handle and auth
decorator, so this module has no dependency on the monolith::

    from src.api.sentence_analyses import create_blueprint
    app.register_blueprint(create_blueprint(lambda: dict_db, login_required, _cosmos_retry))
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable

from flask import Blueprint, jsonify, request, session

from src.api import user_library as _lib

COLLECTION = "sentence_analyses"
MAX_SENTENCE = 2000

_META_FIELDS = {
    "_id": 1,
    "sentence": 1,
    "word_count": 1,
    "known_count": 1,
    "has_source": 1,
    "has_user_translation": 1,
    "created_by": 1,
    "created_at": 1,
    "updated_at": 1,
}


def query_key(sentence: str) -> str:
    """Whitespace-folded, lowercase sentence: the upsert key."""
    return re.sub(r"\s+", " ", (sentence or "")).strip().lower()


def serialize(doc: dict) -> dict:
    out = dict(doc)
    out["id"] = str(out.pop("_id", ""))
    for field in ("created_at", "updated_at"):
        value = out.get(field)
        if hasattr(value, "isoformat"):
            out[field] = value.isoformat()
    ut = out.get("user_translation")
    if isinstance(ut, dict) and hasattr(ut.get("saved_at"), "isoformat"):
        ut["saved_at"] = ut["saved_at"].isoformat()
    return out


def create_blueprint(get_db: Callable, login_required: Callable, cosmos_retry: Callable) -> Blueprint:
    bp = Blueprint("sentence_analyses", __name__)

    def collection():
        db = get_db()
        if db is None or getattr(db, "db", None) is None:
            return None
        return db.db[COLLECTION]

    @bp.route("/api/sentence-analyses", methods=["GET"])
    @login_required
    def list_analyses():
        """Newest first, metadata only."""
        col = collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503
        mine = _lib.user_filter(get_db(), "sentence")
        try:
            try:
                docs = list(col.find(mine, _META_FIELDS).sort("updated_at", -1).limit(200))
            except Exception as exc:  # Cosmos refuses to sort on an unindexed field
                if "order-by" not in str(exc).lower():
                    raise
                docs = sorted(col.find(mine, _META_FIELDS), key=lambda d: d.get("updated_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:200]
            return jsonify([serialize(d) for d in docs])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/api/sentence-analyses/<analysis_id>", methods=["GET"])
    @login_required
    def get_analysis(analysis_id):
        from bson import ObjectId
        from bson.errors import InvalidId

        col = collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503
        try:
            oid = ObjectId(analysis_id)
        except InvalidId:
            return jsonify({"error": "Invalid ID"}), 400
        doc = col.find_one({"_id": oid})
        if not doc:
            return jsonify({"error": "Not found"}), 404
        return jsonify(serialize(doc))

    @bp.route("/api/sentence-analyses", methods=["POST"])
    @login_required
    def save_analysis():
        """Upsert one analysis, keyed on the sentence."""
        data = request.get_json(silent=True) or {}
        sentence = (data.get("sentence") or "").strip()
        if not sentence:
            return jsonify({"error": "sentence is required"}), 400
        if len(sentence) > MAX_SENTENCE:
            return jsonify({"error": f"Sentence is too long ({MAX_SENTENCE} characters max)"}), 400
        col = collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503

        words = data.get("words") if isinstance(data.get("words"), list) else []
        dictionary = data.get("dictionary") if isinstance(data.get("dictionary"), dict) else {}
        user_translation = data.get("user_translation") if isinstance(data.get("user_translation"), dict) else None
        if user_translation:
            user_translation = {
                "english": (user_translation.get("english") or "").strip(),
                "source": user_translation.get("source") or "user",
                "citation": user_translation.get("citation") or None,
                "link": user_translation.get("link") or None,
                "title": user_translation.get("title") or None,
                "saved_by": user_translation.get("saved_by") or session.get("user_email", ""),
                "saved_at": user_translation.get("saved_at") or datetime.now(timezone.utc),
            }
            if not user_translation["english"]:
                user_translation = None

        now = datetime.now(timezone.utc)
        keys = {w.get("key") for w in words if isinstance(w, dict)}
        payload = {
            "sentence": sentence,
            "words": words,
            "dictionary": dictionary,
            "similar": data.get("similar") if isinstance(data.get("similar"), dict) else {},
            "phrases": data.get("phrases") if isinstance(data.get("phrases"), dict) else {},
            "translation": data.get("translation") if isinstance(data.get("translation"), dict) else None,
            "source": data.get("source") if isinstance(data.get("source"), dict) else None,
            "user_translation": user_translation,
            "word_count": len([k for k in keys if k and not k.isdigit()]),
            "known_count": len([k for k in keys if k and k in dictionary]),
            "has_source": bool(data.get("source")),
            "has_user_translation": bool(user_translation),
            "updated_at": now,
        }
        key = query_key(sentence)
        try:
            result = cosmos_retry(
                lambda: col.update_one(
                    {"query_key": key},
                    {"$set": payload, "$setOnInsert": {"query_key": key, "created_at": now, "created_by": session.get("user_email", "")}},
                    upsert=True,
                )
            )
            saved_id = result.upserted_id
            if saved_id is None:
                existing = col.find_one({"query_key": key}, {"_id": 1})
                saved_id = existing["_id"] if existing else None
            _lib.link(get_db(), "sentence", saved_id)
            return jsonify({"success": True, "id": str(saved_id) if saved_id else None})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/api/sentence-analyses/lookup", methods=["GET"])
    @login_required
    def lookup_analysis():
        """An analysis of this sentence that anyone already ran, returned in
        full and added to the caller's library, so no lookups run again."""
        col = collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503
        sentence = (request.args.get("sentence") or "").strip()
        if not sentence:
            return jsonify({"error": "sentence is required"}), 400
        doc = col.find_one({"query_key": query_key(sentence)})
        if not doc:
            return jsonify({"found": False}), 404
        _lib.link(get_db(), "sentence", doc["_id"])
        out = serialize(doc)
        out["found"] = True
        return jsonify(out)

    @bp.route("/api/sentence-analyses/<analysis_id>", methods=["DELETE"])
    @login_required
    def delete_analysis(analysis_id):
        """Remove from my library; the content goes only when no one else has it."""
        from bson import ObjectId
        from bson.errors import InvalidId

        col = collection()
        if col is None:
            return jsonify({"error": "Database unavailable"}), 503
        try:
            oid = ObjectId(analysis_id)
        except InvalidId:
            return jsonify({"error": "Invalid ID"}), 400
        if _lib.unlink(get_db(), "sentence", oid) == 0:
            col.delete_one({"_id": oid})
        return jsonify({"success": True})

    return bp
