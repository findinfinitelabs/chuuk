"""
Talk Builder API.

A talk is an outline (parsed from pasted text or an uploaded file, English
or Chuukese) with, under each point, an ordered list of bilingual lines the
speaker collected: from the Watchtower Library, Article and Sentence
Analysis, the Conversation Builder, or typed here. Scriptures cited by the
outline are looked up in both languages. Talks are per user through the
user library.

Routes
    POST   /api/talks/parse-outline        {text, language?} or multipart `file`
    POST   /api/talks/scriptures           {refs: [...]} → {ref: {chuukese, english, error}}
    GET    /api/talks                       the caller's talks (metadata)
    POST   /api/talks                       create {title, language, outline, lines}
    GET    /api/talks/<id>
    PUT    /api/talks/<id>                  replace title / outline / lines
    POST   /api/talks/<id>/lines           append one line under a point (from other pages)
    DELETE /api/talks/<id>
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Callable

from flask import Blueprint, jsonify, request

from src.api import user_library as _lib
from src.core.talk_outline import extract_text, parse_outline

COLLECTION = "talks"
META = {"title": 1, "language": 1, "outline.title": 1, "outline.total_minutes": 1, "line_count": 1, "created_at": 1, "updated_at": 1, "created_by": 1}


def _line(data: dict) -> dict:
    return {
        "id": data.get("id") or uuid.uuid4().hex[:10],
        "chk": (data.get("chk") or "").strip(),
        "en": (data.get("en") or "").strip(),
        "source": (data.get("source") or "typed")[:60],
        "ref": (data.get("ref") or "")[:300],
        "confirmed": bool(data.get("confirmed")),
        "note": (data.get("note") or "")[:500],
    }


def create_blueprint(get_db: Callable, login_required: Callable, cosmos_retry: Callable, scripture_lookup: Callable, glosser: Callable | None = None) -> Blueprint:
    bp = Blueprint("talks", __name__)

    def col():
        db = get_db()
        if db is None or getattr(db, "db", None) is None:
            return None
        return db.db[COLLECTION]

    def oid_of(value):
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            return None

    def serialize(doc: dict) -> dict:
        out = dict(doc)
        out["id"] = str(out.pop("_id"))
        for f in ("created_at", "updated_at"):
            if hasattr(out.get(f), "isoformat"):
                out[f] = out[f].isoformat()
        return out

    # ------------------------------------------------------------- outline

    @bp.route("/api/talks/parse-outline", methods=["POST"])
    @login_required
    def api_parse_outline():
        language = None
        if request.files.get("file"):
            f = request.files["file"]
            if not (f.filename or "").lower().endswith((".txt", ".docx", ".pdf", ".md")):
                return jsonify({"error": "Upload a .txt, .docx or .pdf file"}), 400
            try:
                text = extract_text(f.filename or "", f.read())
            except Exception as e:
                return jsonify({"error": f"Could not read the file: {e}"}), 400
            language = request.form.get("language") or None
        else:
            data = request.get_json(silent=True) or {}
            text = data.get("text") or ""
            language = data.get("language") or None
        if not text.strip():
            return jsonify({"error": "No outline text"}), 400
        outline = parse_outline(text, language)
        return jsonify({"outline": outline, "text": text})

    @bp.route("/api/talks/scriptures", methods=["POST"])
    @login_required
    def api_scriptures():
        data = request.get_json(silent=True) or {}
        refs = [str(r).strip() for r in (data.get("refs") or []) if str(r).strip()][:40]
        from src.core import wol_bible
        from src.core.scripture_refs import BOOKS, expand

        out = {}
        for ref in refs:
            verses = expand(ref)
            if not verses:
                out[ref] = {"chuukese": "", "english": "", "error": "Could not read this citation", "verses": []}
                continue
            rows, errors = [], []
            for label, query in verses[:12]:
                try:
                    r = scripture_lookup(query) or {}
                except Exception as e:  # pragma: no cover
                    r = {"error": str(e)}
                chk, eng = r.get("chuukese", "") or "", r.get("english", "") or ""
                # Fall back to wol.jw.org (cached per chapter) for whatever the local lookup lacks.
                m = re.match(r"^(.+?) (\d+):(\d+)$", query)
                if m and (not chk or not eng):
                    book = BOOKS.index(m.group(1)) + 1 if m.group(1) in BOOKS else None
                    db = getattr(get_db(), "db", None)
                    if book:
                        chk = chk or wol_bible.verse(db, "chk", book, int(m.group(2)), int(m.group(3)))
                        eng = eng or wol_bible.verse(db, "en", book, int(m.group(2)), int(m.group(3)))
                if not (chk or eng):
                    errors.append(f"{label}: {r.get('error') or 'not available'}")
                elif not chk:
                    errors.append(f"{label}: no Chuukese text (Hebrew Scriptures are not on WOL in Chuukese)")
                rows.append({"ref": label, "chuukese": chk, "english": eng})
            out[ref] = {
                "chuukese": " ".join(f"{v['ref'].rsplit(':', 1)[1]} {v['chuukese']}".strip() for v in rows if v["chuukese"]),
                "english": " ".join(f"{v['ref'].rsplit(':', 1)[1]} {v['english']}".strip() for v in rows if v["english"]),
                "error": "; ".join(errors) or None,
                "verses": rows,
            }
        return jsonify(out)

    # ---------------------------------------------------------- references

    @bp.route("/api/talks/references/resolve", methods=["POST"])
    @login_required
    def api_resolve_reference():
        """The article, paragraph(s) and Chuukese for one outline citation,
        key phrases of the outline point marked. Resolved results are cached
        in `outline_refs`; pages fetched from wol.jw.org are cached in
        `wol_pages`, so a reference costs the site at most once."""
        from src.core.outline_refs import Resolver, find_references
        from src.core.wol_pages import PageFetcher

        data = request.get_json(silent=True) or {}
        raw = (data.get("ref") or "").strip()
        context = (data.get("context") or "").strip()
        refs = find_references(raw)
        if not refs:
            return jsonify({"error": "Not a reference I can resolve"}), 400
        ref = refs[0]
        db = getattr(get_db(), "db", None)
        cache = db["outline_refs"] if db is not None else None
        key = {"ref": ref["raw"].lower(), "context": context.lower()[:300]}
        if cache is not None and not data.get("refresh"):
            hit = cosmos_retry(lambda: cache.find_one(key, {"_id": 0, "result": 1}))
            if hit:
                return jsonify({**hit["result"], "cached": True})
        resolver = Resolver(PageFetcher(db).get, glosser)
        try:
            result = resolver.resolve(ref, context)
        except Exception as e:
            return jsonify({"error": f"Could not resolve the reference: {e}"}), 502
        if cache is not None and (result["paragraphs"] or result["links"]["en"]):
            cosmos_retry(lambda: cache.update_one(key, {"$set": {**key, "result": result, "resolved_at": datetime.now(timezone.utc)}}, upsert=True))
        return jsonify(result)

    # --------------------------------------------------------------- talks

    @bp.route("/api/talks", methods=["GET"])
    @login_required
    def api_list():
        c = col()
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        docs = cosmos_retry(lambda: list(c.find(_lib.user_filter(get_db(), "talk"), META)))
        docs.sort(key=lambda d: d.get("updated_at") or d.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return jsonify([serialize(d) for d in docs])

    def body_to_doc(data: dict) -> dict:
        outline = data.get("outline") or {}
        lines = {}
        for pid, rows in (data.get("lines") or {}).items():
            if isinstance(rows, list):
                lines[str(pid)] = [_line(r) for r in rows if isinstance(r, dict)]
        return {
            "title": (data.get("title") or outline.get("title") or "Talk").strip()[:200],
            "language": data.get("language") or outline.get("language") or "en",
            "outline": outline,
            "outline_text": (data.get("outline_text") or "")[:20000],
            "lines": lines,
            "line_count": sum(len(v) for v in lines.values()),
            "updated_at": datetime.now(timezone.utc),
        }

    @bp.route("/api/talks", methods=["POST"])
    @login_required
    def api_create():
        c = col()
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        data = request.get_json(silent=True) or {}
        if not (data.get("outline") or {}).get("points") and not data.get("title"):
            return jsonify({"error": "An outline or a title is required"}), 400
        doc = body_to_doc(data)
        doc["created_at"] = doc["updated_at"]
        doc["created_by"] = _lib.current_email()
        oid = cosmos_retry(lambda: c.insert_one(doc)).inserted_id
        _lib.link(get_db(), "talk", oid)
        return jsonify({"success": True, "id": str(oid)})

    @bp.route("/api/talks/<talk_id>", methods=["GET"])
    @login_required
    def api_get(talk_id):
        c = col()
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        oid = oid_of(talk_id)
        if oid is None:
            return jsonify({"error": "Invalid ID"}), 400
        doc = cosmos_retry(lambda: c.find_one({"_id": oid}))
        if not doc:
            return jsonify({"error": "Not found"}), 404
        _lib.link(get_db(), "talk", oid)
        return jsonify(serialize(doc))

    @bp.route("/api/talks/<talk_id>", methods=["PUT"])
    @login_required
    def api_update(talk_id):
        c = col()
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        oid = oid_of(talk_id)
        if oid is None:
            return jsonify({"error": "Invalid ID"}), 400
        data = request.get_json(silent=True) or {}
        doc = body_to_doc(data)
        res = cosmos_retry(lambda: c.update_one({"_id": oid}, {"$set": doc}))
        if res.matched_count == 0:
            return jsonify({"error": "Not found"}), 404
        _lib.link(get_db(), "talk", oid)
        return jsonify({"success": True, "id": talk_id})

    @bp.route("/api/talks/<talk_id>/lines", methods=["POST"])
    @login_required
    def api_add_line(talk_id):
        """Append one line under a point: the "Add to talk" button on other pages."""
        c = col()
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        oid = oid_of(talk_id)
        if oid is None:
            return jsonify({"error": "Invalid ID"}), 400
        data = request.get_json(silent=True) or {}
        point_id = str(data.get("point_id") or "unsorted")
        line = _line(data)
        if not (line["chk"] or line["en"]):
            return jsonify({"error": "A line needs Chuukese or English text"}), 400
        doc = cosmos_retry(lambda: c.find_one({"_id": oid}, {"lines": 1}))
        if not doc:
            return jsonify({"error": "Not found"}), 404
        lines = doc.get("lines") or {}
        lines.setdefault(point_id, []).append(line)
        cosmos_retry(lambda: c.update_one({"_id": oid}, {"$set": {"lines": lines, "line_count": sum(len(v) for v in lines.values()), "updated_at": datetime.now(timezone.utc)}}))
        return jsonify({"success": True, "line": line, "point_id": point_id})

    @bp.route("/api/talks/<talk_id>", methods=["DELETE"])
    @login_required
    def api_delete(talk_id):
        c = col()
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        oid = oid_of(talk_id)
        if oid is None:
            return jsonify({"error": "Invalid ID"}), 400
        if _lib.unlink(get_db(), "talk", oid) == 0:
            cosmos_retry(lambda: c.delete_one({"_id": oid}))
        return jsonify({"success": True})

    return bp
