"""
Conversation Builder API.

A branching conversation flow (src/data/conversation_flow.json) whose lines
are filled from the harvested publications (``conversation_sources``: Love
People—Make Disciples lessons, Truths We Love to Teach, workbook weeks) and
from ``conversation_phrases`` (Chuukese for the authored lines: machine
translated by scripts/fill_conversation_phrases.py until someone corrects
them here). Saved conversations are per user through the user library.

Routes
    GET  /api/conversation/sources                subjects, lessons, workbook weeks
    GET  /api/conversation/flow?subject=&statement=&lesson=
    PUT  /api/conversation/phrases/<phrase_id>    {chk} correct a line
    GET  /api/conversations                       the caller's saved conversations
    POST /api/conversations                       save one
    GET  /api/conversations/<id>
    DELETE /api/conversations/<id>
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from flask import Blueprint, jsonify, request, session

from src.api import user_library as _lib

SOURCES = "conversation_sources"
PHRASES = "conversation_phrases"
SAVED = "conversations"
FLOW_PATH = Path(__file__).resolve().parent.parent / "data" / "conversation_flow.json"
_SLOT = re.compile(r"\{\{(\w+)\}\}")
_flow_cache: dict | None = None


def load_flow() -> dict:
    global _flow_cache
    if _flow_cache is None:
        with open(FLOW_PATH, encoding="utf-8") as f:
            _flow_cache = json.load(f)
    return _flow_cache


def fill_slots(text: str, ctx: dict) -> str:
    """Replace {{statement}}, {{scripture}} … from ctx; unknown slots become
    a visible blank the speaker fills in."""
    return _SLOT.sub(lambda m: str(ctx.get(m.group(1)) or f"[{m.group(1)}]"), text or "")


def create_blueprint(get_db: Callable, login_required: Callable, cosmos_retry: Callable) -> Blueprint:
    bp = Blueprint("conversation", __name__)

    def col(name):
        db = get_db()
        if db is None or getattr(db, "db", None) is None:
            return None
        return db.db[name]

    # ------------------------------------------------------------------ sources

    def sources() -> dict:
        """Everything harvested, keyed by kind (one Cosmos query)."""
        c = col(SOURCES)
        out = {"truths": None, "end": None, "lessons": {}, "workbook": []}
        if c is None:
            return out
        for doc in cosmos_retry(lambda: list(c.find({}, {"_id": 0}))):
            kind = doc.get("kind")
            if kind == "truths":
                out["truths"] = doc["data"]
            elif kind == "end":
                out["end"] = doc["data"]
            elif kind == "lesson":
                out["lessons"][int(doc["number"])] = doc["data"]
            elif kind == "workbook":
                out["workbook"].append(doc["data"])
        out["workbook"].sort(key=lambda w: w.get("start") or "")
        return out

    def phrase_overrides() -> dict:
        c = col(PHRASES)
        if c is None:
            return {}
        return {d["phrase_id"]: d for d in cosmos_retry(lambda: list(c.find({}, {"_id": 0})))}

    def current_week(weeks: list[dict]) -> dict | None:
        today = date.today().isoformat()
        for w in weeks:
            if w.get("start") and w.get("end") and w["start"] <= today <= w["end"]:
                return w
        upcoming = [w for w in weeks if (w.get("start") or "") > today]
        return upcoming[0] if upcoming else (weeks[-1] if weeks else None)

    @bp.route("/api/conversation/sources", methods=["GET"])
    @login_required
    def api_sources():
        src = sources()
        truths = src["truths"] or {"subjects": []}
        lessons = [
            {"number": n, "title": d["title"], "stage": d["stage"], "principle": d["principle"]}
            for n, d in sorted(src["lessons"].items())
        ]
        week = current_week(src["workbook"])
        return jsonify(
            {
                "has_sources": bool(src["truths"]),
                "truths_title": truths.get("title"),
                "subjects": truths.get("subjects", []),
                "lessons": lessons,
                "weeks": src["workbook"],
                "current_week": week,
            }
        )

    # --------------------------------------------------------------------- flow

    def resolve_phrase(p: dict, ctx: dict, overrides: dict, src: dict) -> dict:
        """One line, bilingual, with its provenance."""
        pid = p.get("id")
        ov = overrides.get(pid) or {}
        out = {"id": pid, "en": fill_slots(p.get("en", ""), ctx), "chk": "", "mt": False, "source": "authored"}
        ref = p.get("from")
        if ref:
            m = re.match(r"lesson:(\d+):pid:(\w+)", ref)
            lesson = src["lessons"].get(int(m.group(1))) if m else None
            if lesson:
                for sec in lesson["sections"]:
                    for pt in sec["points"]:
                        for it in [pt] + pt["items"]:
                            if it.get("pid") == m.group(2):
                                out.update({"chk": it["chk"], "en": it["en"], "source": f"Love People, lesson {m.group(1)}"})
        if ov.get("chk"):
            out["chk"] = fill_slots(ov["chk"], ctx)
            out["mt"] = bool(ov.get("mt"))
            out["engine"] = ov.get("engine")
        elif p.get("chk"):
            out["chk"] = fill_slots(p["chk"], ctx)
        return out

    def statement_phrase(stmt: dict | None, subject: dict | None, pid: str) -> dict | None:
        if not stmt:
            return None
        return {
            "id": pid,
            "en": stmt["en"],
            "chk": stmt["chk"],
            "mt": False,
            "source": f"Truths We Love to Teach, {subject['title']['en']} {stmt['n']}" if subject else "Truths We Love to Teach",
            "scriptures": stmt.get("scriptures"),
        }

    def lesson_phrases(numbers: list[int], src: dict, ctx: dict) -> list[dict]:
        """Quoted lines from the named lessons: authentic Chuukese to say or ask."""
        out = []
        for n in numbers or []:
            lesson = src["lessons"].get(n)
            if not lesson:
                continue
            for sec in lesson["sections"]:
                for pt in sec["points"]:
                    for it in pt["items"]:
                        if it.get("quoted") and it.get("chk"):
                            out.append(
                                {
                                    "id": f"lesson:{n}:pid:{it['pid']}",
                                    "en": it["en"],
                                    "chk": it["chk"],
                                    "mt": False,
                                    "source": f"Love People, lesson {n} point {pt['n']}",
                                    "point": pt["en"],
                                }
                            )
        return out

    @bp.route("/api/conversation/flow", methods=["GET"])
    @login_required
    def api_flow():
        flow = load_flow()
        src = sources()
        overrides = phrase_overrides()
        subject_id = (request.args.get("subject") or "").strip()
        stmt_n = request.args.get("statement", type=int)
        lesson_n = request.args.get("lesson", type=int)

        subjects = (src["truths"] or {}).get("subjects", [])
        subject = next((s for s in subjects if s["id"] == subject_id), None)
        statements = subject["statements"] if subject else []
        stmt = next((s for s in statements if s["n"] == stmt_n), None) or (statements[0] if statements else None)
        following = None
        if stmt and statements:
            i = [s["n"] for s in statements].index(stmt["n"])
            following = statements[i + 1] if i + 1 < len(statements) else None
        openers = flow["subject_openers"].get(subject_id, [])

        me = (session.get("user_name") or "").split(" ")[0] or "[your name]"
        ctx = {
            "statement": stmt["chk"] if stmt else "[statement]",
            "scripture": stmt["scriptures"]["chk"] if stmt else "[scripture]",
            "me": me,
            "next_question": openers[1]["en"] if len(openers) > 1 else "[question]",
        }
        ctx_en = {**ctx, "statement": stmt["en"] if stmt else "[statement]", "scripture": stmt["scriptures"]["en"] if stmt else "[scripture]"}

        def corrected(pid: str) -> str:
            """Chuukese for a UI label only once a person has corrected it;
            a machine translation of a label is more confusing than English."""
            ov = overrides.get(pid) or {}
            return ov.get("chk", "") if ov and not ov.get("mt") else ""

        def resolve(p):
            # English slots take English values, Chuukese slots Chuukese ones.
            r_en = resolve_phrase(p, ctx_en, overrides, src)
            r_chk = resolve_phrase(p, ctx, overrides, src)
            return {**r_en, "chk": r_chk["chk"]}

        nodes = {}
        for nid, node in flow["nodes"].items():
            say = []
            for p in node.get("say", []):
                slot = p.get("slot")
                if slot == "statement":
                    sp = statement_phrase(stmt, subject, p["id"])
                    if sp:
                        say.append(sp)
                elif slot == "next_statement":
                    sp = statement_phrase(following, subject, p["id"])
                    if sp:
                        say.append(sp)
                elif slot == "subject_opener":
                    say.extend(resolve(o) for o in openers)
                else:
                    say.append(resolve(p))
            nodes[nid] = {
                "id": nid,
                "title": {"en": node["title"]["en"], "chk": corrected(f"node:{nid}:title")},
                "stage": node.get("stage"),
                "guidance": node.get("guidance", {}).get("en", ""),
                "lessons": node.get("lessons", []),
                "think": [resolve(p) for p in node.get("think", [])],
                "say": say,
                "lesson_phrases": lesson_phrases(node.get("lessons", []), src, ctx),
                "responses": [
                    {
                        "kind": r["kind"],
                        "label": {"en": r["label"]["en"], "chk": corrected(f"node:{nid}:resp:{r['kind']}:label")},
                        "they": [resolve(t) for t in r.get("they", [])],
                        "next": r["next"],
                    }
                    for r in node.get("responses", [])
                ],
            }

        lesson = src["lessons"].get(lesson_n) if lesson_n else None
        return jsonify(
            {
                "start": flow["start"],
                "nodes": nodes,
                "subject": {"id": subject["id"], "title": subject["title"]} if subject else None,
                "statement": stmt,
                "next_statement": following,
                "lesson": lesson,
                "end_article": src["end"],
            }
        )

    # ------------------------------------------------------------------ phrases

    @bp.route("/api/conversation/phrases/<path:phrase_id>", methods=["PUT"])
    @login_required
    def api_correct_phrase(phrase_id):
        c = col(PHRASES)
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        data = request.get_json(silent=True) or {}
        chk = (data.get("chk") or "").strip()
        if not chk:
            return jsonify({"error": "chk is required"}), 400
        now = datetime.now(timezone.utc)
        doc = {
            "phrase_id": phrase_id,
            "en": (data.get("en") or "").strip(),
            "chk": chk,
            "mt": False,
            "edited_by": _lib.current_email(),
            "edited_at": now,
        }
        cosmos_retry(lambda: c.update_one({"phrase_id": phrase_id}, {"$set": doc, "$unset": {"engine": "", "filled_at": ""}}, upsert=True))
        return jsonify({"success": True, "phrase": {k: v for k, v in doc.items() if k != "edited_at"}})

    # -------------------------------------------------------------------- saved

    def serialize(doc: dict) -> dict:
        out = dict(doc)
        out["id"] = str(out.pop("_id"))
        for f in ("created_at", "updated_at"):
            if hasattr(out.get(f), "isoformat"):
                out[f] = out[f].isoformat()
        return out

    @bp.route("/api/conversations", methods=["GET"])
    @login_required
    def api_list():
        c = col(SAVED)
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        mine = _lib.user_filter(get_db(), "conversation")
        docs = cosmos_retry(lambda: list(c.find(mine, {"path": 0})))
        docs.sort(key=lambda d: d.get("updated_at") or d.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return jsonify([serialize(d) for d in docs])

    @bp.route("/api/conversations", methods=["POST"])
    @login_required
    def api_save():
        from bson import ObjectId
        from bson.errors import InvalidId

        c = col(SAVED)
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        data = request.get_json(silent=True) or {}
        path = data.get("path") or []
        if not isinstance(path, list) or not path:
            return jsonify({"error": "path is required"}), 400
        now = datetime.now(timezone.utc)
        doc = {
            "title": (data.get("title") or "").strip()[:200] or "Conversation",
            "subject": data.get("subject"),
            "statement": data.get("statement"),
            "lesson": data.get("lesson"),
            "week": data.get("week"),
            "path": path,
            "step_count": len(path),
            "updated_at": now,
            "created_by": _lib.current_email(),
        }
        oid = None
        if data.get("id"):
            try:
                oid = ObjectId(data["id"])
            except InvalidId:
                return jsonify({"error": "Invalid ID"}), 400
            cosmos_retry(lambda: c.update_one({"_id": oid}, {"$set": doc}))
        else:
            doc["created_at"] = now
            oid = cosmos_retry(lambda: c.insert_one(doc)).inserted_id
        _lib.link(get_db(), "conversation", oid)
        return jsonify({"success": True, "id": str(oid)})

    @bp.route("/api/conversations/<conversation_id>", methods=["GET"])
    @login_required
    def api_get(conversation_id):
        from bson import ObjectId
        from bson.errors import InvalidId

        c = col(SAVED)
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        try:
            oid = ObjectId(conversation_id)
        except InvalidId:
            return jsonify({"error": "Invalid ID"}), 400
        doc = cosmos_retry(lambda: c.find_one({"_id": oid}))
        if not doc:
            return jsonify({"error": "Not found"}), 404
        return jsonify(serialize(doc))

    @bp.route("/api/conversations/<conversation_id>", methods=["DELETE"])
    @login_required
    def api_delete(conversation_id):
        from bson import ObjectId
        from bson.errors import InvalidId

        c = col(SAVED)
        if c is None:
            return jsonify({"error": "Database unavailable"}), 503
        try:
            oid = ObjectId(conversation_id)
        except InvalidId:
            return jsonify({"error": "Invalid ID"}), 400
        if _lib.unlink(get_db(), "conversation", oid) == 0:
            cosmos_retry(lambda: c.delete_one({"_id": oid}))
        return jsonify({"success": True})

    return bp
