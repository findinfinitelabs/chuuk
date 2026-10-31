"""
Scripture reference parsing utilities.

Loads book names from config/scripture_books.json and provides:

- a regex that matches a complete scripture citation, in any of the forms
  wol.jw.org uses in English and Chuukese articles, e.g.
      Féf. 5:42              1 Cor. 13:4, 7           Acts 19:8-10
      Fof. 27:37–28:2        Kölf. 3:13, 14           2Ki 21:4-7
      Rom 3:25; 14:24, 25; 1 Kor. 5:9-13              KÖLF. 32:5
- helpers to protect those citations with placeholders and restore them, and
- ``split_sentences()``, which breaks a paragraph into sentences without ever
  cutting through a citation, and keeps a trailing "(Mat. 6:9)" or
  "—Kölf. 23:4." with the sentence it belongs to.
"""

import json
import os
import re
from functools import lru_cache


def get_config_path():
    """Get the path to the scripture_books.json config file."""
    # Try multiple possible locations
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "scripture_books.json"),
        os.path.join(os.path.dirname(__file__), "..", "config", "scripture_books.json"),
        os.path.join(os.getcwd(), "config", "scripture_books.json"),
        "config/scripture_books.json",
    ]

    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path

    raise FileNotFoundError("scripture_books.json not found in any expected location")


@lru_cache(maxsize=1)
def load_scripture_books():
    """Load scripture book names from config file."""
    config_path = get_config_path()
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    return config["books"]


@lru_cache(maxsize=1)
def get_all_book_names():
    """Get a flat, de-duplicated list of all scripture book names (abbreviations and full names)."""
    books = load_scripture_books()
    seen = set()
    all_names = []
    for names in books.values():
        for name in names:
            if name not in seen:
                seen.add(name)
                all_names.append(name)
    return all_names


@lru_cache(maxsize=1)
def get_book_names_pattern():
    """Build regex pattern for matching any scripture book name (case-insensitive).

    Book names are matched whole: a leading word boundary is enforced and the
    name must be followed by an optional period and the chapter number, so "Is"
    only matches as Isaiah in "Is. 2:3", never inside "This".
    """
    all_names = get_all_book_names()
    # Sort by length descending so longer names match first (e.g., "Corinthians" before "Cor").
    all_names_sorted = sorted(all_names, key=len, reverse=True)
    alternatives = "|".join(re.escape(name).replace(r"\ ", r"\s+") for name in all_names_sorted)
    return r"(?i:" + alternatives + r")"


# "13:4", "13:4, 7", "19:8-10", "27:37–28:2", "3:13, 14", "4:3a"
_VERSES = r"\d+:\s?\d+[ab]?(?:\s?[-–—]\s?\d+(?::\d+)?[ab]?)?(?:\s?,\s?\d+[ab]?(?:\s?[-–—]\s?\d+(?::\d+)?)?)*"
# "14:24, 25; 15:2" — further chapter:verse groups of the same book
_CHAPTERS = rf"{_VERSES}(?:\s?;\s?{_VERSES})*"
_ORDINAL = r"(?:[1-3]\s?)?"


@lru_cache(maxsize=1)
def get_scripture_reference_pattern():
    """
    Build regex pattern for matching complete scripture references.

    One capturing group wraps the whole citation, so ``re.findall`` returns the
    citation text. Matched forms include:

    - 1 Cor. 13:4, 7 / Féf. 5:42 / Acts 19:8-10 / 1 Corinthians 15:33 / Mateus 5:3
    - 2Ki 21:4-7 (ordinal joined to the book), KÖLF. 32:5 (upper case)
    - Fof. 27:37–28:2 (range across chapters)
    - Rom 3:25; 14:24, 25; 1 Kor. 5:9-13 (several books / chapters joined by ";")
    """
    book_names = get_book_names_pattern()
    one_book = rf"{_ORDINAL}{book_names}\.?\s*{_CHAPTERS}"
    pattern = rf"((?<![\w.]){one_book}(?:\s?;\s?{one_book})*)"
    return pattern


_PLACEHOLDER = "<<<REF_{}>>>"
_PLACEHOLDER_RE = re.compile(r"<<<REF_(\d+)>>>")


def protect_scripture_references(text):
    """
    Protect scripture references in text from being split by sentence boundaries.

    Returns:
        tuple: (protected_text, list of protected references)
    """
    pattern = get_scripture_reference_pattern()
    protected_refs = []

    def protect_ref(match):
        placeholder = _PLACEHOLDER.format(len(protected_refs))
        protected_refs.append(match.group(0))
        return placeholder

    protected_text = re.sub(pattern, protect_ref, text)
    return protected_text, protected_refs


def restore_scripture_references(text, protected_refs):
    """Restore protected scripture references in text."""
    return _PLACEHOLDER_RE.sub(lambda m: protected_refs[int(m.group(1))], text)


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_INVISIBLE = re.compile(r"[​‌‍­﻿⁠]")

# A sentence ends at . ! or ?, plus any closing quotes/brackets, plus an optional
# trailing parenthesised citation such as "(Kölf. 137:1, 3)" or "(Álleani Aisea
# 55:7.)". The next sentence starts with an opening quote/bracket, a capital
# (including Chuukese Á É Ó Ú Ä Ö Ü), a digit (paragraph numbers) or a
# protected citation.
_SENTENCE_END = re.compile(
    r"[.!?][”’\"')\]]*(?:\s*\((?:[^()<]|<<<REF_\d+>>>){1,160}\))?"
    r"(?:\s[a-z](?=\s))?"  # a footnote letter stuck to the sentence end: "do. a As we"
    r"(?=\s+[“‘\"'(\[]?(?:[A-ZÀ-Þ]|\d|<<<REF_))"
)
# A lone footnote letter left on a sentence end, e.g. "would do. a".
_TRAILING_FOOTNOTE = re.compile(r"(?<=[.!?”’\"')\]])\s[a-z]$")


def normalize_text(text):
    """Collapse whitespace and undo the stray spaces HTML extraction leaves
    around punctuation: "Mattu 24:14 , ewe" → "Mattu 24:14, ewe", "( Mat. 6:9 )"
    → "(Mat. 6:9)"."""
    text = _INVISIBLE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?’”)\]])", r"\1", text)
    text = re.sub(r"([(\[“‘])\s+", r"\1", text)
    # "wa.— Luk 15:7 ." → "wa.—Luk 15:7."
    text = re.sub(r"\s*(—|–)\s*", r"\1", text)
    return text


def split_sentences(text):
    """Split a paragraph into sentences, keeping every scripture citation whole
    and attached to the sentence it cites.

    >>> split_sentences('A erá: “Esap wor an mwäl.” (Tut. 32:4) A alónga an kefil.')
    ['A erá: “Esap wor an mwäl.” (Tut. 32:4)', 'A alónga an kefil.']
    """
    text = normalize_text(text)
    if not text:
        return []
    protected, refs = protect_scripture_references(text)

    out, start = [], 0
    for m in _SENTENCE_END.finditer(protected):
        out.append(protected[start : m.end()].strip())
        start = m.end()
    out.append(protected[start:].strip())
    out = [_TRAILING_FOOTNOTE.sub("", s) for s in out]
    out = _rebalance_markers([s for s in out if s])
    return [restore_scripture_references(s, refs) for s in out if s]


_LABEL_ONLY = re.compile(r"^\d{1,3}(?:[-–]\d{1,3})?\.?(?:\s*\([a-z]\))?$")
_TRAILING_MARKER = re.compile(r"\s*\([a-z]\)$")


def _rebalance_markers(parts):
    """Study-question pieces come out as "2. (a)", "…? (b)", "…?": the label
    and the (a)/(b) markers belong at the start of the question they
    introduce, so move them there."""
    out = []
    carry = ""
    for part in parts:
        if carry:
            part = f"{carry} {part}"
            carry = ""
        if _LABEL_ONLY.match(part):
            carry = part
            continue
        m = _TRAILING_MARKER.search(part)
        if m and part[: m.start()].rstrip()[-1:] in ".!?”’\"')]":
            carry = m.group(0).strip()
            part = part[: m.start()]
        out.append(part)
    if carry:
        if out:
            out[-1] = f"{out[-1]} {carry}"
        else:
            out.append(carry)
    return out


# For backwards compatibility and direct import
def get_pattern():
    """Alias for get_scripture_reference_pattern()."""
    return get_scripture_reference_pattern()
