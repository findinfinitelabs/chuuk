"""
Pair the paragraphs and sentences of a Chuukese article with its English
edition by content, not by position.

The two editions of a wol.jw.org article do not line up one-for-one:

* the English may carry a footnote paragraph the Chuukese lacks, which shifts
  every later paragraph id;
* within a paragraph the translator may put two sentences in the other order,
  split one into two, or merge two into one.

Counting sentences per language and pairing the n-th with the n-th therefore
drifts as soon as either happens. Instead, ``align_paragraphs`` pairs the
paragraph lists by a monotone dynamic programme over shared paragraph ids,
leading labels ("2", "3.", "10-11."), element kind and length, and
``align_sentences`` pairs the sentences of one paragraph pair by a similar
programme over scripture citations, numbers, list markers, terminal
punctuation, dictionary glosses and length, allowing 1-1, 1-2, 2-1, 2-2 and
unmatched beads. A 2-2 bead is then resolved crosswise when the sentences are
swapped.

Both functions are pure and cheap (paragraphs ≤ ~100, sentences ≤ ~20).
"""

from __future__ import annotations

import math
import re
from typing import Callable, Iterable

from src.utils.scripture_parser import get_scripture_reference_pattern

_REF_RE = re.compile(get_scripture_reference_pattern())
_CHAPTER_VERSE_RE = re.compile(r"\d+:\d+(?:[-–]\d+)?(?:,\s*\d+)*")
_NUMBER_RE = re.compile(r"(?<![\d:])\d+(?![\d:])")
_LIST_MARK_RE = re.compile(r"\((\d{1,2}|[a-z])\)")
_LABEL_RE = re.compile(r"^\s*(\d{1,3}(?:[-–]\d{1,3})?)\.?(?=\s|$)")
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_QUOTE_RE = re.compile(r"[“”\"]")

# Bead shapes: (chuukese sentences consumed, english sentences consumed).
_BEADS = ((1, 1), (1, 2), (2, 1), (2, 2), (1, 0), (0, 1))
_BEAD_PENALTY = {(1, 1): 0.0, (1, 2): 0.6, (2, 1): 0.6, (2, 2): 2.0, (1, 0): 1.6, (0, 1): 1.6}
# Two sentences rendered in the other order: cheaper than a 2-2 merge.
_SWAP_PENALTY = 0.5

Gloss = Callable[[str], Iterable[str]]


# ---------------------------------------------------------------------------
# Paragraphs
# ---------------------------------------------------------------------------


def paragraph_label(text: str) -> str | None:
    """The study-article label a paragraph opens with: "2", "3.", "10-11."
    all give "2", "3", "10-11"."""
    m = _LABEL_RE.match(text or "")
    return m.group(1).replace("–", "-") if m else None


def _para_score(a: dict, b: dict, ratio: float) -> float:
    score = 0.0
    if a.get("pid") and a.get("pid") == b.get("pid"):
        score += 3.0
    la, lb = paragraph_label(a.get("text", "")), paragraph_label(b.get("text", ""))
    if la and lb:
        score += 2.0 if la == lb else -2.0
    elif la or lb:
        score -= 0.5
    if a.get("tag") == b.get("tag"):
        score += 0.5
    else:
        score -= 1.0
    score -= 0.8 * _length_cost(a.get("text", ""), b.get("text", ""), ratio)
    return score


def align_paragraphs(chuukese: list[dict], english: list[dict]) -> list[int | None]:
    """For each Chuukese paragraph, the index of its English paragraph or
    ``None``. Paragraph dicts carry ``text`` and optionally ``tag`` and ``pid``.

    >>> align_paragraphs([{"text": "1. Why?"}, {"text": "1 Because."}],
    ...                  [{"text": "a Footnote."}, {"text": "1. Why?"}, {"text": "1 Because."}])
    [1, 2]
    """
    n, m = len(chuukese), len(english)
    if not n or not m:
        return [None] * n
    ratio = _corpus_ratio([p.get("text", "") for p in chuukese], [p.get("text", "") for p in english])
    skip = -1.2
    best = [[-math.inf] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = best[i][j]
            if cur == -math.inf:
                continue
            if i < n and j < m:
                s = cur + _para_score(chuukese[i], english[j], ratio)
                if s > best[i + 1][j + 1]:
                    best[i + 1][j + 1], back[i + 1][j + 1] = s, (1, 1)
            if i < n and cur + skip > best[i + 1][j]:
                best[i + 1][j], back[i + 1][j] = cur + skip, (1, 0)
            if j < m and cur + skip > best[i][j + 1]:
                best[i][j + 1], back[i][j + 1] = cur + skip, (0, 1)
    out: list[int | None] = [None] * n
    i, j = n, m
    while i > 0 or j > 0:
        di, dj = back[i][j]  # type: ignore[misc]
        if di and dj:
            out[i - 1] = j - 1
        i, j = i - di, j - dj
    return out


# ---------------------------------------------------------------------------
# Sentences
# ---------------------------------------------------------------------------


def _anchors(text: str) -> set[str]:
    """Language-independent tokens a translation preserves: chapter:verse
    citations, bare numbers, list markers, terminal punctuation."""
    out: set[str] = set()
    refs = _REF_RE.findall(text)
    for ref in refs:
        for cv in _CHAPTER_VERSE_RE.findall(ref):
            out.add("ref:" + re.sub(r"\s+", "", cv.replace("–", "-")))
    stripped = _REF_RE.sub(" ", text)
    for num in _NUMBER_RE.findall(stripped):
        out.add("num:" + num)
    for mark in _LIST_MARK_RE.findall(stripped):
        out.add("mark:" + mark)
    body = re.sub(r"\s*\([^)]*\)\s*$", "", stripped.strip())
    body = body.rstrip("”’\"') ")
    if body.endswith("?"):
        out.add("end:?")
    elif body.endswith("!"):
        out.add("end:!")
    if _QUOTE_RE.search(text):
        out.add("quote")
    return out


def _anchor_score(a: str, b: str) -> float:
    sa, sb = _anchors(a), _anchors(b)
    if not sa and not sb:
        return 0.0
    shared = sa & sb
    only = (sa ^ sb)
    weight = lambda t: 1.5 if t.startswith("ref:") else 0.8 if t.startswith(("num:", "mark:")) else 0.4
    return sum(weight(t) for t in shared) - 0.6 * sum(weight(t) for t in only)


def _length_cost(a: str, b: str, ratio: float) -> float:
    la, lb = max(len(a), 1), max(len(b), 1)
    return abs(math.log((la / lb) / ratio))


def _corpus_ratio(a: list[str], b: list[str]) -> float:
    la, lb = sum(len(s) for s in a), sum(len(s) for s in b)
    if not la or not lb:
        return 1.0
    return min(max(la / lb, 0.5), 2.0)


def _gloss_score(chk: str, eng: str, gloss: Gloss | None) -> float:
    """Share of Chuukese content words whose dictionary gloss shows up in
    the English sentence (0..1)."""
    if gloss is None:
        return 0.0
    eng_words = {w.lower() for w in _WORD_RE.findall(eng)}
    if not eng_words:
        return 0.0
    hits = total = 0
    for w in _WORD_RE.findall(chk):
        if len(w) < 3:
            continue
        total += 1
        glosses = {g.lower() for g in (gloss(w.lower()) or []) if len(g) >= 3}
        if glosses & eng_words:
            hits += 1
    return hits / total if total else 0.0


def _bead_score(chk: list[str], eng: list[str], ratio: float, gloss: Gloss | None) -> float:
    a, b = " ".join(chk), " ".join(eng)
    return (
        _anchor_score(a, b)
        - 1.2 * _length_cost(a, b, ratio)
        + 2.0 * _gloss_score(a, b, gloss)
    )


def _pair_score(chk: str, eng: str, ratio: float, gloss: Gloss | None) -> float:
    return _bead_score([chk], [eng], ratio, gloss)


def align_sentences(
    chuukese: list[str],
    english: list[str],
    gloss: Gloss | None = None,
) -> list[list[int]]:
    """For each Chuukese sentence, the indices of the English sentence(s) that
    translate it (possibly empty, possibly two).

    ``gloss(word)`` may return the English gloss words of a Chuukese word; it
    sharpens the choice when two sentences look alike structurally.

    >>> align_sentences(["Setup. ", "He asked: “Who?” (Luke 1:57-66)"],
    ...                 ["“Who?” (Luke 1:57-66)", "The setup sentence."])
    [[1], [0]]
    """
    n, m = len(chuukese), len(english)
    if not n:
        return []
    if not m:
        return [[] for _ in range(n)]
    ratio = _corpus_ratio(chuukese, english)

    best = [[-math.inf] * (m + 1) for _ in range(n + 1)]
    # back[i][j] = (chk consumed, eng consumed, swapped) of the bead ending at (i, j).
    back: list[list[tuple[int, int, bool] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = best[i][j]
            if cur == -math.inf:
                continue
            for di, dj in _BEADS:
                ni, nj = i + di, j + dj
                if ni > n or nj > m:
                    continue
                swapped = False
                if di and dj:
                    s = cur + _bead_score(chuukese[i:ni], english[j:nj], ratio, gloss) - _BEAD_PENALTY[(di, dj)]
                    if di == 2 and dj == 2:
                        crossed = (
                            cur
                            + _pair_score(chuukese[i], english[j + 1], ratio, gloss)
                            + _pair_score(chuukese[i + 1], english[j], ratio, gloss)
                            - _SWAP_PENALTY
                        )
                        if crossed > s:
                            s, swapped = crossed, True
                else:
                    s = cur - _BEAD_PENALTY[(di, dj)]
                if s > best[ni][nj]:
                    best[ni][nj], back[ni][nj] = s, (di, dj, swapped)

    beads: list[tuple[int, int, int, int, bool]] = []  # (chk start, chk end, eng start, eng end, swapped)
    i, j = n, m
    while i > 0 or j > 0:
        di, dj, swapped = back[i][j]  # type: ignore[misc]
        beads.append((i - di, i, j - dj, j, swapped))
        i, j = i - di, j - dj
    beads.reverse()

    out: list[list[int]] = [[] for _ in range(n)]
    for ci, ce, ei, ee, swapped in beads:
        if ce == ci or ee == ei:
            continue
        if swapped:
            out[ci], out[ci + 1] = [ei + 1], [ei]
        else:
            for k in range(ci, ce):
                out[k] = list(range(ei, ee))
    return out


__all__ = ["align_paragraphs", "align_sentences", "paragraph_label"]
