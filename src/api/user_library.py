"""
Per-user library over shared saved content.

Saved WOL searches, article analyses and sentence analyses are expensive to
produce (each one is a trip to wol.jw.org plus the dictionary pass), so the
content documents stay shared: one per URL, query or sentence, whoever
produced it. What is per user is the *library*: which of those documents show
in each person's sidebar. This collection holds that link.

    user_library: { user_email, kind, item_id, saved_at }
    kind: "article" | "wol_search" | "sentence"

When a second person asks for an article that is already analysed, the lookup
endpoints hand them the stored document and add it to their library; nothing
is fetched again. Removing an item from a library deletes the content only
when no other library still points at it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import session

COLLECTION = "user_library"
KINDS = ("article", "wol_search", "sentence")
_index_done = False


def collection(db):
    if db is None or getattr(db, "db", None) is None:
        return None
    col = db.db[COLLECTION]
    global _index_done
    if not _index_done:
        try:
            col.create_index([("user_email", 1), ("kind", 1), ("item_id", 1)], unique=True)
            col.create_index([("kind", 1), ("item_id", 1)])
        except Exception:
            pass
        _index_done = True
    return col


def current_email() -> str:
    return (session.get("user_email") or "").strip().lower()


def link(db, kind: str, item_id, email: str | None = None) -> None:
    """Put `item_id` in the user's library (idempotent)."""
    col = collection(db)
    if col is None or item_id is None:
        return
    email = (email or current_email())
    if not email:
        return
    col.update_one(
        {"user_email": email, "kind": kind, "item_id": item_id},
        {"$set": {"saved_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def unlink(db, kind: str, item_id) -> int:
    """Remove the item from the user's library; returns how many other
    libraries still hold it (0 means the content may be deleted)."""
    col = collection(db)
    if col is None:
        return 0
    col.delete_one({"user_email": current_email(), "kind": kind, "item_id": item_id})
    return col.count_documents({"kind": kind, "item_id": item_id})


def item_ids(db, kind: str) -> list:
    col = collection(db)
    if col is None:
        return []
    email = current_email()
    if not email:
        return []
    return [d["item_id"] for d in col.find({"user_email": email, "kind": kind}, {"item_id": 1})]


def user_filter(db, kind: str) -> dict:
    """Mongo filter selecting only the content in the current user's library."""
    return {"_id": {"$in": item_ids(db, kind)}}
