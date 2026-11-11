"""
Verb lookup route: a verb with its subject pronouns, object suffixes and
stored examples. See src/core/verb_forms.py. No wol.jw.org access here; the
page uses the existing /api/wol/verb-examples behind a button for that.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from typing import Callable

import requests
from flask import Blueprint, jsonify, request

from src.core import verb_forms

log = logging.getLogger(__name__)

COUNTS_COLLECTION = "wol_counts"
COUNT_TTL_DAYS = 30
MAX_COUNT_WORDS = 6
SPACING_SECONDS = 1.5


def create_blueprint(get_db: Callable, login_required: Callable, wol_search: Callable | None = None) -> Blueprint:
    """`wol_search()` returns the shared WOLSearch client; used only by the
    counts route, which runs on an explicit click and caches its answers."""
    bp = Blueprint("verb_lookup", __name__)

    @bp.route("/api/verbs/lookup", methods=["GET"])
    @login_required
    def verb_lookup():
        q = (request.args.get("q") or "").strip()
        if not q:
            return jsonify({"error": "A verb is required"}), 400
        if len(q) > 60:
            return jsonify({"error": "Too long (60 characters max)"}), 400
        try:
            limit = max(5, min(int(request.args.get("limit", 30) or 30), 100))
        except ValueError:
            limit = 30
        return jsonify(verb_forms.lookup(get_db(), q, example_limit=limit)), 200

    @bp.route("/api/verbs/wol-counts", methods=["POST"])
    @login_required
    def wol_counts():
        """Occurrence counts on wol.jw.org for a few words, from the cache when
        fresh, else one spaced request per word. Never called automatically."""
        data = request.get_json(silent=True) or {}
        words = [str(w).strip() for w in (data.get("words") or []) if str(w).strip()][:MAX_COUNT_WORDS]
        if not words:
            return jsonify({"error": "words are required"}), 400
        db = get_db()
        col = db.db[COUNTS_COLLECTION] if db is not None and getattr(db, "db", None) is not None else None
        now = dt.datetime.utcnow()
        out, fetched = [], 0
        for w in words:
            cached = None
            if col is not None:
                try:
                    cached = col.find_one({"query": w.lower(), "lang": "chk"}, {"_id": 0})
                except Exception as e:  # pragma: no cover
                    log.warning("wol_counts cache read: %s", e)
            if cached and (now - (cached.get("fetched_at") or dt.datetime.min)).days < COUNT_TTL_DAYS:
                out.append({**cached, "cached": True})
                continue
            if wol_search is None:
                out.append({"query": w, "error": "wol.jw.org search is not available"})
                continue
            try:
                if fetched:
                    time.sleep(SPACING_SECONDS)
                c = wol_search().count(w)
                fetched += 1
                row = {**c, "query": w.lower(), "lang": "chk", "fetched_at": now}
                if col is not None:
                    try:
                        col.update_one({"query": w.lower(), "lang": "chk"}, {"$set": row}, upsert=True)
                    except Exception as e:  # pragma: no cover
                        log.warning("wol_counts cache write: %s", e)
                out.append({**row, "cached": False})
            except requests.RequestException as e:
                out.append({"query": w, "error": f"wol.jw.org: {e}"})
        return jsonify({"counts": out, "fetched": fetched}), 200

    return bp
