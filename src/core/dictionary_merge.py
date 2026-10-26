"""
Merging dictionary entries that share a headword.

Used in two places: the CSV import, so a re-imported or overlapping file adds
to the existing entry instead of creating a copy; and scripts/dedupe_dictionary.py,
which collapses the duplicates already in the collection.

Merging is conservative: distinct English wordings become separate senses
("ghost of; color of"), the longest definition wins and the others are kept in
``other_definitions``, and a grammar tag is only changed when the copies agree.
Disagreements are reported so they can go to the review queue.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

SENSE_SEPARATOR = "; "
_SURROUNDING_PUNCT_RE = re.compile(r"^[^\w]+|[^\w]+$", re.UNICODE)


def clean_headword(text) -> str:
    """A headword as it should be stored: punctuation and quotes gone from its
    outer edges, whitespace collapsed. 'Jeremaia,' -> 'Jeremaia'; '"ewe Kot.'
    -> 'ewe Kot'. Inner punctuation stays: '(Jer 48:27, 29;' -> 'Jer 48:27, 29'."""
    collapsed = " ".join(str(text or "").split())
    return _SURROUNDING_PUNCT_RE.sub("", collapsed)


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _key(text) -> str:
    """Comparison key: lowercase, no leading 'to', no brackets, singular-ish.
    'to force (by threats)' and 'force by threat' compare equal."""
    k = _norm(text).lower().rstrip(".")
    k = re.sub(r"[()\[\],\"“”‘’']", " ", k)
    k = re.sub(r"^to\s+", "", k)
    k = re.sub(r"\s+", " ", k).strip()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in k.split())


def split_senses(english: str) -> list[str]:
    """'ghost of; color of' → ['ghost of', 'color of'] (commas stay inside a sense:
    'keep, own, possess' is one sense with synonyms)."""
    return [s for s in (_norm(p) for p in (english or "").split(";")) if s]


def merge_senses(*wordings: str) -> str:
    """Combine English wordings into one sense list, dropping repeats and
    wordings wholly contained in another ('keep, possess' inside 'keep, possess, have')."""
    senses: list[str] = []
    for wording in wordings:
        for sense in split_senses(wording):
            k = _key(sense)
            words = set(k.replace(",", " ").split())
            # Already covered by an existing sense?
            if any(k == _key(s) or words <= set(_key(s).replace(",", " ").split()) for s in senses):
                continue
            # Does this sense cover an existing shorter one? Replace it.
            senses = [s for s in senses if not set(_key(s).replace(",", " ").split()) <= words or _key(s) == k]
            senses.append(sense)
    return SENSE_SEPARATOR.join(senses)


def clean_senses(english) -> str:
    """An English wording with stray punctuation gone from each sense and
    repeats collapsed: '(Jer 48:27 29 42' -> 'Jer 48:27 29 42';
    'Moab; “Moab”' -> 'Moab'."""
    return merge_senses(*(clean_headword(sense) for sense in split_senses(english)))


def _filled(entry: dict) -> int:
    return sum(1 for k in ("english_translation", "grammar", "grammar_modifier", "definition", "references") if _norm(entry.get(k)) not in ("", "—", "none"))


def choose_survivor(entries: list[dict]) -> dict:
    """The copy to keep: the best-populated one, and among equals the oldest."""
    return sorted(entries, key=lambda e: (-_filled(e), str(e.get("_id"))))[0]


def merge_group(entries: list[dict]) -> dict:
    """Merge copies of one headword.

    Returns ``{"survivor": entry, "update": {$set fields}, "absorbed": [ids],
    "grammar_conflict": {...} | None, "identical": bool}``.
    """
    survivor = choose_survivor(entries)
    others = [e for e in entries if e is not survivor]

    def distinct(field):
        seen, out = set(), []
        for e in [survivor] + others:
            v = _norm(e.get(field))
            if v and v not in ("—", "None", "none") and _key(v) not in seen:
                seen.add(_key(v))
                out.append(v)
        return out

    englishes = distinct("english_translation")
    definitions = sorted(distinct("definition"), key=len, reverse=True)
    grammars = Counter(g.lower() for g in distinct("grammar") for _ in [0])
    grammar_votes = Counter(_norm(e.get("grammar")).lower() for e in entries if _norm(e.get("grammar")))
    modifiers = distinct("grammar_modifier")

    update: dict = {}
    merged_english = merge_senses(*englishes)
    if merged_english and merged_english != _norm(survivor.get("english_translation")):
        update["english_translation"] = merged_english
    if definitions:
        if definitions[0] != _norm(survivor.get("definition")):
            update["definition"] = definitions[0]
        if len(definitions) > 1:
            update["other_definitions"] = definitions[1:]
    if not _norm(survivor.get("grammar_modifier")) and modifiers:
        update["grammar_modifier"] = modifiers[0]

    grammar_conflict = None
    if len(grammar_votes) > 1:
        majority, votes = grammar_votes.most_common(1)[0]
        tied = [g for g, n in grammar_votes.items() if n == votes]
        grammar_conflict = {
            "votes": dict(grammar_votes),
            "majority": None if len(tied) > 1 else majority,
            "survivor_grammar": _norm(survivor.get("grammar")) or None,
        }
        if grammar_conflict["majority"] and grammar_conflict["majority"] != (_norm(survivor.get("grammar")).lower()):
            update["grammar"] = grammar_conflict["majority"]
    elif grammar_votes and not _norm(survivor.get("grammar")):
        update["grammar"] = next(iter(grammar_votes))

    identical = len(englishes) <= 1 and len(definitions) <= 1 and len(grammar_votes) <= 1 and len(grammars) <= 1
    return {
        "survivor": survivor,
        "update": update,
        "absorbed": [e["_id"] for e in others],
        "grammar_conflict": grammar_conflict,
        "identical": identical,
    }


def merge_new_into_existing(existing: dict, new: dict) -> dict:
    """$set fields to bring what a freshly imported row adds into the existing
    entry (used by the CSV import). Empty when the row adds nothing."""
    result = merge_group([existing, {**new, "_id": "zzz-new"}])
    update = dict(result["update"])
    update.pop("grammar", None)  # an import never flips an existing tag
    if update:
        update["date_modified"] = datetime.now(timezone.utc)
    return update


__all__ = ["clean_headword", "clean_senses", "merge_group", "merge_senses", "split_senses", "choose_survivor", "merge_new_into_existing"]
