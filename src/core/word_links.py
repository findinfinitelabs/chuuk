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

A word the dictionary does not hold as it stands (ápilúkúni) is read through
the dictionary words it contains (ápilúkú "hope", lúkú "faith"): every such
base whose gloss is spelled like a word of the English verse is a candidate,
the longest match wins, and it is reported as the word's ``base`` so the page
can show it. No affixes are guessed and meaning is not consulted for bases: a
base is only ever a headword the dictionary holds, shown only when the English
of the same verse spells out its gloss (gave counts as give, saw as see).

Umlauts and acute accents are the same letters (ä/á, ö/ó, ü/ú), so every
comparison folds diacritics away.

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


def fold(word: str) -> str:
    """Lowercase without diacritics or hyphens: ápilúkú, apilükü and apiluku are one spelling."""
    w = unicodedata.normalize("NFD", (word or "").lower().replace("-", ""))
    return "".join(ch for ch in w if not unicodedata.combining(ch))


# Irregular English past forms, so "gave" is the spelling "give" (not a matter of meaning).
_IRREGULAR = {
    "gave": "give", "given": "give", "saw": "see", "seen": "see", "took": "take", "taken": "take", "went": "go", "gone": "go",
    "made": "make", "said": "say", "came": "come", "knew": "know", "known": "know", "found": "find", "told": "tell",
    "thought": "think", "brought": "bring", "bought": "buy", "sought": "seek", "taught": "teach", "caught": "catch",
    "spoke": "speak", "spoken": "speak", "wrote": "write", "written": "write", "ate": "eat", "eaten": "eat", "drank": "drink",
    "fell": "fall", "fallen": "fall", "held": "hold", "kept": "keep", "left": "leave", "lost": "lose", "met": "meet",
    "sent": "send", "sat": "sit", "stood": "stand", "understood": "understand", "began": "begin", "begun": "begin",
    "built": "build", "chose": "choose", "chosen": "choose", "died": "die", "forgave": "forgive", "forgiven": "forgive",
    "heard": "hear", "led": "lead", "lay": "lie", "paid": "pay", "ran": "run", "rose": "rise", "risen": "rise", "sang": "sing",
    "slept": "sleep", "struck": "strike", "swore": "swear", "sworn": "swear", "threw": "throw", "thrown": "throw", "wore": "wear",
    "won": "win", "children": "child", "men": "man", "women": "woman", "feet": "foot", "teeth": "tooth", "mice": "mouse", "sons": "son",
    "better": "good", "best": "good", "worse": "bad", "worst": "bad", "was": "be", "were": "be", "been": "be", "did": "do", "done": "do",
}


def stem(word: str) -> str:
    w = fold(word)
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    w = re.sub(r"[’']s$", "", w)
    for end in ("ingly", "edly", "ness", "ing", "ed", "es", "ly", "s"):
        if len(w) > len(end) + 3 and w.endswith(end):
            w = w[: -len(end)]
            break
    w = re.sub(r"ie$", "y", w)
    return _IRREGULAR.get(w, w)  # "thoughts" → "thought" → "think", like "thought" itself


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


_BASE_MIN_START = 3  # a base at the start of the word (ápilúkú in ápilúkúni)
_BASE_MIN_INSIDE = 4  # a base inside the word (lúkú in ápilúkúni) needs more letters


def base_candidates(word: str, lexicon: dict | None) -> list[tuple[str, str]]:
    """Dictionary headwords with a gloss that the word contains, longest first:
    (headword, english). `lexicon` is the similarity index ({"by_norm": folded →
    headwords, "english": headword → gloss}); a base is never the whole word."""
    if not lexicon:
        return []
    by_norm, english = lexicon.get("by_norm") or {}, lexicon.get("english") or {}
    norm = fold(word)
    out: list[tuple[str, str]] = []
    for length in range(len(norm) - 1, _BASE_MIN_START - 1, -1):
        for start in range(0, len(norm) - length + 1):
            if start and length < _BASE_MIN_INSIDE:
                continue
            for head in sorted(by_norm.get(norm[start:start + length], ())):
                gloss = english.get(head) or ""
                if gloss and gloss_alternatives(gloss):
                    out.append((head, gloss))
    return out


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

    def link(self, chk_text: str, en_text: str, dictionary: dict, lexicon: dict | None = None) -> dict:
        chk, en = words(chk_text), words(en_text)
        out = {"chk": [None] * len(chk), "en": [None] * len(en), "pairs": 0, "semantic": self.embed is not None, "bases": [None] * len(chk)}
        en_stems = [stem(w) for w in en]
        en_content = [i for i, w in enumerate(en) if w.lower() not in _STOP]
        candidates: list[tuple[float, float, int, int]] = []  # (-score, distance, ci, ei)
        semantic_jobs: list[tuple[int, int, str, str, tuple | None]] = []
        # Best base per (chk word, English word): (rank, headword, gloss alternative); longer bases first.
        bases: dict[tuple[int, int], tuple[float, str, str]] = {}

        def note_base(ci: int, ei: int, base: tuple | None, strength: float) -> None:
            if base is None:
                return
            head, alt = base
            rank = strength + len(fold(head)) / 100
            if rank > bases.get((ci, ei), (-1,))[0]:
                bases[(ci, ei)] = (rank, head, alt)

        for ci, w in enumerate(chk):
            entry = dictionary.get(w.lower()) or dictionary.get(fold(w)) or {}
            # The word's own gloss first (base None), then the glosses of the dictionary words it contains.
            sources: list[tuple[tuple | None, list[str]]] = [(None, gloss_alternatives(entry.get("english") or ""))]
            for head, gloss in base_candidates(w, lexicon):
                sources.append(((head, gloss), gloss_alternatives(gloss)))
            if not any(alts for _b, alts in sources):
                continue
            target = ci / max(1, len(chk)) * len(en)
            for base, alts in sources:
                # A whole-word match outranks a base; a longer base outranks a shorter one.
                base_penalty = 0.0 if base is None else 0.1 - len(fold(base[0])) / 1000
                gloss_word_stems = [(alt, [stem(g) for g in words(alt)]) for alt in alts]
                for ei in en_content:
                    hit = next((alt for alt, gs in gloss_word_stems if any(spelled_alike(en_stems[ei], g) for g in gs)), None)
                    if hit is not None:
                        candidates.append((-1.0 + base_penalty, abs(ei - target), ci, ei))
                        note_base(ci, ei, (base[0], hit) if base else None, 1.0)
                    elif self.embed is not None and base is None:
                        # Meaning is only consulted for the word's own gloss: a base word that
                        # merely means something like an English word would be a guess.
                        for alt, _gs in gloss_word_stems:
                            semantic_jobs.append((ci, ei, alt, en[ei], base))
        if semantic_jobs:
            try:
                texts = [j[2] for j in semantic_jobs] + [j[3] for j in semantic_jobs]
                vecs = self._vectors(texts)
                n = len(semantic_jobs)
                sims = (vecs[:n] * vecs[n:]).sum(axis=1)
                for (ci, ei, alt, _w, base), sim in zip(semantic_jobs, sims):
                    if float(sim) >= _SEMANTIC_MIN:
                        target = ci / max(1, len(chk)) * len(en)
                        base_penalty = 0.0 if base is None else 0.1 - len(fold(base[0])) / 1000
                        # Meaning matches are rougher than spelling: a nearer word wins a close call.
                        candidates.append((-float(sim) + base_penalty + 0.004 * abs(ei - target), abs(ei - target), ci, ei))
                        note_base(ci, ei, (base[0], alt) if base else None, float(sim))
            except Exception:
                out["semantic"] = False
        candidates.sort()
        for _s, _d, ci, ei in candidates:
            if out["chk"][ci] is not None or out["en"][ei] is not None:
                continue
            out["chk"][ci] = out["en"][ei] = out["pairs"]
            out["pairs"] += 1
            found = bases.get((ci, ei))
            if found:
                out["bases"][ci] = {"word": found[1], "english": found[2]}
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


__all__ = ["Linker", "linker_for", "words", "fold", "stem", "spelled_alike", "gloss_alternatives", "base_candidates"]
