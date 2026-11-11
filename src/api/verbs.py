"""
Verb lookup route: a verb with its subject pronouns, object suffixes and
stored examples. See src/core/verb_forms.py. No wol.jw.org access here; the
page uses the existing /api/wol/verb-examples behind a button for that.
"""

from __future__ import annotations

from typing import Callable

from flask import Blueprint, jsonify, request

from src.core import verb_forms


def create_blueprint(get_db: Callable, login_required: Callable) -> Blueprint:
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

    return bp
