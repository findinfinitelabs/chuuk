"""
Word links for Scripture Lookup: which English word of a verse each Chuukese
word corresponds to, through the dictionary.

For every Chuukese word the dictionary holds, the English words of its gloss
are compared with the English verse. A spelling match wins (pregnant /
pregnancy, love / loved, by a light stem and a shared start); failing that
the gloss and the English word are compared by meaning with the sentence
embedder the meaning search already loads (difficulty / pain, child / son),
accepted above a threshold. Pairs are assigned greedily, best score first,
one partner per word on each side, nearer positions preferred on ties.

Word ordinals match the frontend's tokenisation (`[^\\W\\d_]+`-style split
on letters and digits), so each side is a list of pair ids by word ordinal.
"""

from __future__ import annotations

import re
import threading
import unicodedata

_WORD = re.compile(r"[\w]+", re.UNICODE)
_SEMANTIC_MIN = 0.42
_STOP = set(
    "the a an of to in on at by for with and or but as is are was were be been am do does did has have had he she it they them "
    "his her its their we us our you your i me my this that these those there here who which what when not no so if then than "
    "too very can could will would shall should may might must also just".split()
)


def words(text: str) -> list[str]:
    """Letters-and-digits runs, as GlossedWords and wordAlign count them."""
    return [w for w in re.split(r"([^\w]+)", text or "") if w and _WORD.fullmatch(w)]


def stem(word: str) -> str:
    w = unicodedata.normalize("NFD", word.lower())
    w = "".join(ch for ch in w if not unicodedata.combining(ch))
    w = re.sub(r"[’']s$", "", w)
    for end in ("ingly", "edly", "ness", "ing", "ed", "es", "ly", "s"):
        if len(w) > len(end) + 3 and w.endswith(end):
            w = w[: -len(end)]
            break
    return re.sub(r"ie$", "y", w)


def spelled_alike(a: str, b: str) -> bool:
    """Equal stems, or one the other's start within three letters, or a shared
    start that leaves at most two letters of the shorter (pregnant / pregnancy)."""
    if a == b:
        return True
    shorter = min(len(a), len(b))
    if shorter >= 4 and abs(len(a) - len(b)) <= 3 and (a.startswith(b) or b.startswith(a)):
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return shorter >= 6 and common >= shorter - 2


def gloss_alternatives(english: str) -> list[str]:
    """'after; afterwards (adv.); later or next' → ['after', 'afterwards', 'later', 'next']."""
    out: list[str] = []
    for alt in re.split(r"[;,/]|\bor\b", re.sub(r"\(.*?\)", "", english or "")):
        alt = " ".join(w for w in words(alt) if w.lower() not in _STOP)
        if alt and alt.lower() not in {o.lower() for o in out}:
            out.append(alt)
    return out[:6]


class Linker:
    """Scores and assigns the pairs; `embed(texts) -> vectors` may be None (spelling only)."""

    def __init__(self, embed=None):
        self.embed = embed
        self._cache: dict[str, object] = {}
        self._lock = threading.Lock()

    def _vectors(self, texts: list[str]):
        import numpy as np

        todo = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if todo and self.embed is not None:
            vecs = self.embed(todo)
            with self._lock:
                for t, v in zip(todo, vecs):
                    self._cache[t] = v
                if len(self._cache) > 60000:
                    self._cache.clear()
        return np.stack([self._cache[t] for t in texts]) if texts else np.zeros((0, 384), dtype="float32")

    def link(self, chk_text: str, en_text: str, dictionary: dict) -> dict:
        chk, en = words(chk_text), words(en_text)
        out = {"chk": [None] * len(chk), "en": [None] * len(en), "pairs": 0, "semantic": self.embed is not None}
        en_stems = [stem(w) for w in en]
        en_content = [i for i, w in enumerate(en) if w.lower() not in _STOP]
        candidates: list[tuple[float, float, int, int]] = []  # (-score, distance, ci, ei)
        semantic_jobs: list[tuple[int, int, str, str]] = []
        for ci, w in enumerate(chk):
            entry = dictionary.get(w.lower()) or {}
            alts = gloss_alternatives(entry.get("english") or "")
            if not alts:
                continue
            target = ci / max(1, len(chk)) * len(en)
            gloss_word_stems = [(alt, [stem(g) for g in words(alt)]) for alt in alts]
            for ei in en_content:
                spelled = any(spelled_alike(en_stems[ei], g) for _alt, gs in gloss_word_stems for g in gs)
                if spelled:
                    candidates.append((-1.0, abs(ei - target), ci, ei))
                elif self.embed is not None:
                    for alt, _gs in gloss_word_stems:
                        semantic_jobs.append((ci, ei, alt, en[ei]))
        if semantic_jobs:
            try:
                texts = [j[2] for j in semantic_jobs] + [j[3] for j in semantic_jobs]
                vecs = self._vectors(texts)
                n = len(semantic_jobs)
                sims = (vecs[:n] * vecs[n:]).sum(axis=1)
                for (ci, ei, _alt, _w), sim in zip(semantic_jobs, sims):
                    if float(sim) >= _SEMANTIC_MIN:
                        target = ci / max(1, len(chk)) * len(en)
                        # Meaning matches are rougher than spelling: a nearer word wins a close call.
                        candidates.append((-float(sim) + 0.004 * abs(ei - target), abs(ei - target), ci, ei))
            except Exception:
                out["semantic"] = False
        candidates.sort()
        for _s, _d, ci, ei in candidates:
            if out["chk"][ci] is not None or out["en"][ei] is not None:
                continue
            out["chk"][ci] = out["en"][ei] = out["pairs"]
            out["pairs"] += 1
        return out


_LINKER: Linker | None = None


def linker_for(dict_db) -> Linker:
    """The shared linker, using the meaning search's embedder when it is loaded
    (and asking for it to load otherwise, in the background)."""
    global _LINKER
    from src.core.idea_search import get_index

    index = get_index(dict_db)
    ready = index.embedder.model is not None
    if not ready:
        index.ensure()
    if _LINKER is None or (ready and _LINKER.embed is None):
        _LINKER = Linker(index.embedder.encode if ready else None)
    return _LINKER


__all__ = ["Linker", "linker_for", "words", "stem", "spelled_alike", "gloss_alternatives"]
