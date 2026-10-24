"""
Cleaning rules for Chuukese ↔ English training pairs.

The DB holds text copied straight out of NWT / Watchtower pages, so sentence pairs
carry artefacts that a translation model should never learn:

* leading verse numbers      ``"13 Ina minne, …"``  /  ``"+ 14 And the prophecy …"``
* NWT footnote markers       ``"To the angel + of the congregation"``
* bare scripture-reference lists   ``"Mattu 10:1-10;; 10:35-40;;"``
* off-by-one verse alignment (chk verse 13 paired with eng verse 14)
* word-by-word gloss strings assembled from dictionary look-ups, presented as English

``clean_pair`` normalises what can be normalised and returns ``None`` for pairs
that should be dropped. It is applied by ``TrainingPairCollector.collect_all``
and by ``scripts/train_madlad.py`` so every trainer sees the same data.
"""

from __future__ import annotations

import re

_LEADING_VERSE = re.compile(r"^\s*\+?\s*(\d{1,3})\s+(?=\S)")
_SENSE_MARKER = re.compile(r"\s*\(\d{1,2}\)\s*$")  # homonym index on headwords: "war (2)"
_FOOTNOTE_PLUS = re.compile(r"(?:(?<=\s)|^)\+(?=\s|$)")  # a lone "+" token
_DOUBLE_SEMI = re.compile(r";\s*;+")
_WS = re.compile(r"\s+")
_ALPHA = re.compile(r"[^\W\d_]", re.UNICODE)
# Tell-tale signs of a dictionary gloss masquerading as a translation
_GLOSS_HINTS = (
    "(indicates",
    " / ",
    "he, she, it",
    "you are / you were",
    "(be) ",
    "(exclusive)",
    "(inclusive)",
)


def _strip_verse(text: str) -> tuple[str, str | None]:
    m = _LEADING_VERSE.match(text)
    if not m:
        return text, None
    return text[m.end():], m.group(1)


def _normalise(text: str, strip_footnotes: bool = True) -> str:
    if strip_footnotes:
        text = _FOOTNOTE_PLUS.sub(" ", text)
    text = _DOUBLE_SEMI.sub(";", text)
    return _WS.sub(" ", text).strip()


def _alpha_ratio(text: str) -> float:
    stripped = text.replace(" ", "")
    return len(_ALPHA.findall(stripped)) / max(1, len(stripped))


def is_sentence(chk: str, eng: str) -> bool:
    return " " in chk.strip() and " " in eng.strip()


def clean_pair(chuukese: str, english: str, source: str = "") -> tuple[str, str] | None:
    """Return a cleaned ``(chuukese, english)`` tuple or ``None`` to drop the pair."""
    chk = (chuukese or "").strip()
    eng = (english or "").strip()
    if not chk or not eng:
        return None

    # "war (2)" → "war": the sense index is lexicographer bookkeeping, not Chuukese
    chk = _SENSE_MARKER.sub("", chk)

    chk, v_chk = _strip_verse(chk)
    eng, v_eng = _strip_verse(eng)
    # Both sides numbered but with different verse numbers → misaligned copy
    if v_chk and v_eng and v_chk != v_eng:
        return None
    # Article-analysis rows where only the English carries a verse number are the
    # off-by-one cases we saw ("…end of v12" ↔ "+ 13 That is why …")
    if source == "article_analysis" and (v_chk is None) != (v_eng is None):
        return None

    # Dictionary glosses use "+" legitimately ("verb + kick"); NWT text uses a lone
    # "+" only as a footnote marker.
    strip_plus = source != "dictionary"
    chk, eng = _normalise(chk, strip_plus), _normalise(eng, strip_plus)
    if not chk or not eng:
        return None

    sentence = is_sentence(chk, eng)

    # Scripture reference lists / number-only rows: too little real language
    if sentence and (_alpha_ratio(chk) < 0.6 or _alpha_ratio(eng) < 0.6):
        return None

    # Assembled glosses (only ever seen from article analysis / game rows)
    if sentence and source in ("article_analysis", "translation_game"):
        low = eng.lower()
        if any(h in low for h in _GLOSS_HINTS):
            return None

    # Wildly different lengths on real sentences mean a bad alignment. Chuukese
    # runs longer than English, so the lower bound is generous.
    if sentence and len(chk) > 30:
        ratio = len(eng) / len(chk)
        if ratio > 2.5 or ratio < 0.33:
            return None

    return chk, eng


def clean_pairs(pairs: list[dict], stats: dict | None = None) -> list[dict]:
    """Apply ``clean_pair`` to a list of ``{chuukese, english, source?}`` dicts."""
    out = []
    dropped = 0
    changed = 0
    for p in pairs:
        res = clean_pair(p.get("chuukese", ""), p.get("english", ""), p.get("source", "") or "")
        if res is None:
            dropped += 1
            continue
        chk, eng = res
        if chk != (p.get("chuukese") or "").strip() or eng != (p.get("english") or "").strip():
            changed += 1
        q = dict(p)
        q["chuukese"], q["english"] = chk, eng
        out.append(q)
    if stats is not None:
        stats.update({"input": len(pairs), "kept": len(out), "dropped": dropped, "normalised": changed})
    return out
