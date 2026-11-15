"""
Search the stored library by meaning, for the Talk Builder's "Similar in the
library" feature.

A collected line such as "he understood the consequences of disobedience, yet
he still chose to disobey Jehovah and rejected his love" is about ideas, not
words: *consequences of disobedience*, *disobey Jehovah*, *reject his love*,
and, from the outline point around it, *Adam*. This module

* pulls those **ideas** out of the English (clauses with their leading
  pronouns and light verbs stripped) and the **subjects** out of the line and
  its outline context (names such as Adam, Jehovah, Jesus);
* keeps an in-memory **index** of every stored pair that has English
  (dictionary phrases, analysed-article sentences, corrected conversation
  lines), with a sentence embedding for each, so a search compares meaning
  (all-MiniLM-L6-v2 through `transformers`, which the app already ships) and
  not just spelling;
* **scores** each stored sentence by how close its English is in meaning to
  the line and to each idea, with a bonus when the idea's words occur
  together as a phrase (word roots, so "disobey" meets "disobedience") and
  when it names the subject.

The embedding model is loaded once, in a background thread, the first time a
search runs; until it is ready, and if it cannot be loaded, the search still
answers from phrase and root matches alone and says so (`index` in the
result). The vectors are cached in data/cache so a restart only re-encodes
new sentences. Nothing here touches the network except that one model
download.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
import warnings
from pathlib import Path

log = logging.getLogger(__name__)

MODEL = os.getenv("IDEA_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CACHE = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "idea_index.npz"
REFRESH_SECONDS = 3600
MAX_ROWS = 60000

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_CLAUSE_SPLIT = re.compile(
    r"\s*(?:[,;:.!?()—–\"“”]+|\s(?:yet|but|and|or|because|so that|so|while|when|although|though|since|then|whereas|however|therefore|which|who|that)\s)\s*",
    re.IGNORECASE,
)
# What a clause often starts with before its idea: subjects, auxiliaries,
# adverbs and the light verbs that only introduce the real verb.
_LEAD = set(
    "i you he she it we they who that this these those there here still then also just even yet already always never "
    "ever often really truly indeed only too very so not no "
    "am is are was were be been being have has had do does did will would shall should can could may might must "
    "chose chooses choose decided decides decide began begins begin started starts start continued continues continue "
    "wanted wants want tried tries try went goes go came comes come seemed seems seem able to kept keeps keep "
    "needs need needed let lets his her their our your my its the a an of in on at by for with".split()
)
_STOP = set(
    "the a an of in on at by for with to from and or but yet so as is are was were be been being am do does did has have had "
    "he she it they them their his her its we us our you your i me my this that these those there here who whom which what "
    "when where why how not no nor if then than too very can could will would shall should may might must also just still "
    "even ever never always often into onto over under about after before while during because though although since "
    "one ones all any some such each every both either neither more most much many own same other another".split()
)
from src.core.scripture_refs import BOOKS as _BOOKS

_NAME_SKIP = _STOP | {"god", "bible", "jehovah's", "chapter", "verse", "paragraph", "par", "see", "read"} | {b.lower() for b in _BOOKS} | {b.split()[-1].lower() for b in _BOOKS}
_NAMES = set(
    "jehovah jesus christ adam eve noah abraham sarah isaac jacob joseph moses aaron joshua david solomon elijah elisha "
    "job daniel jonah paul peter john james mary martha lazarus satan devil cain abel lot esau rahab ruth naomi samuel saul "
    "hezekiah josiah jeremiah isaiah ezekiel nehemiah esther mordecai timothy barnabas stephen pilate herod israel judah".split()
)

try:
    from nltk.stem import PorterStemmer

    _STEM = PorterStemmer().stem
except Exception:  # pragma: no cover
    _STEM = lambda w: w  # noqa: E731


def root(word: str) -> str:
    """A spelling-insensitive root: the Porter stem cut to six letters, so
    disobey / disobedience / disobedient and consequence / consequences meet."""
    s = _STEM(word.lower())
    return s[:6] if len(s) > 6 else s


def roots(text: str) -> set[str]:
    return {root(w) for w in _WORD.findall(text or "") if w.lower() not in _STOP and len(w) > 2}


def ideas(english: str, limit: int = 6) -> list[str]:
    """The ideas of an English line: each clause with its leading pronoun,
    auxiliaries and light verbs stripped, 2–8 words long, in order."""
    out: list[str] = []
    for clause in _CLAUSE_SPLIT.split(english or ""):
        words = _WORD.findall(clause)
        while words and words[0].lower() in _LEAD:
            words.pop(0)
        while words and words[-1].lower() in _STOP:
            words.pop()
        phrase = " ".join(words)
        content = [w for w in words if w.lower() not in _STOP]
        if 1 <= len(content) and 2 <= len(words) <= 8 and phrase.lower() not in {o.lower() for o in out}:
            out.append(phrase)
    return out[:limit]


def subjects(*texts: str) -> list[str]:
    """Names the line and its outline context are about (Adam, Jehovah…)."""
    found: list[str] = []
    for text in texts:
        words = _WORD.findall(text or "")
        # A heading in Title Case ("True Faith—What Is It?") capitalises every
        # word: take only known names from it.
        caps = sum(1 for w in words if w[0].isupper())
        title_case = len(words) >= 2 and caps / len(words) > 0.5
        for i, w in enumerate(words):
            lw = w.lower()
            if lw in _NAME_SKIP or len(w) < 3:
                continue
            if lw in _NAMES or (not title_case and w[0].isupper() and i > 0 and lw not in _LEAD):
                name = w.capitalize() if lw in _NAMES else w
                if name not in found:
                    found.append(name)
    return found[:6]


def _norm(text: str) -> str:
    return " ".join(_WORD.findall((text or "").lower()))


class Embedder:
    """all-MiniLM-L6-v2 mean-pooled, normalised. Loaded lazily."""

    def __init__(self, name: str = MODEL):
        self.name = name
        self.tok = self.model = None

    def load(self) -> None:
        import torch  # noqa: F401  (already a dependency)
        from transformers import AutoModel, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(self.name)
        self.model = AutoModel.from_pretrained(self.name).eval()

    def encode(self, texts: list[str]):
        import numpy as np
        import torch

        if not texts:
            return np.zeros((0, 384), dtype="float32")
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), 64):
                b = self.tok(texts[i : i + 64], padding=True, truncation=True, max_length=128, return_tensors="pt")
                h = self.model(**b).last_hidden_state
                mask = b["attention_mask"].unsqueeze(-1)
                e = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
                e = e / e.norm(dim=1, keepdim=True).clamp(min=1e-6)
                out.append(e.numpy().astype("float32"))
        return np.concatenate(out)


class IdeaIndex:
    """Every stored pair with English, its roots and (once ready) its vector."""

    def __init__(self, dict_db, embedder: Embedder | None = None, cache: Path = CACHE):
        self.dict_db = dict_db
        self.embedder = embedder or Embedder()
        self.cache = cache
        self.rows: list[dict] = []
        self.row_roots: list[set[str]] = []
        self.vectors = None  # numpy (n, 384) aligned with rows, or None
        self.status = "building"  # building | ready | unavailable
        self.error = ""
        self.loaded_at = 0.0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    # -- rows ------------------------------------------------------------

    def _collect(self) -> list[dict]:
        rows: list[dict] = []
        seen: set[str] = set()

        def add(c, e, source, reference="", link=None):
            c, e = (c or "").strip(), (e or "").strip()
            key = _norm(c)
            if c and e and key and key not in seen and len(rows) < MAX_ROWS:
                seen.add(key)
                rows.append({"chk": c, "en": e, "source": source, "reference": reference or "", "link": link})

        db = getattr(self.dict_db, "db", None)
        try:
            col = getattr(self.dict_db, "phrases_collection", None)
            if col is not None:
                for r in col.find({}, {"chuukese_phrase": 1, "chuukese_sentence": 1, "chuukese": 1, "english_translation": 1, "english": 1, "source": 1, "reference": 1}):
                    add(r.get("chuukese_phrase") or r.get("chuukese_sentence") or r.get("chuukese"), r.get("english_translation") or r.get("english"), "library", r.get("reference") or r.get("source") or "")
        except Exception as e:
            log.warning("idea index phrases: %s", e)
        try:
            if db is not None:
                for doc in db["article_analysis_paragraphs"].find({}, {"paragraph.sentences.text_only": 1, "paragraph.sentences.english_text": 1, "article_title": 1, "title": 1, "url": 1}):
                    title = doc.get("article_title") or doc.get("title") or "analysed article"
                    para = doc.get("paragraph") or {}
                    sentences = para.get("sentences") if isinstance(para, dict) else None
                    if sentences is None and isinstance(para, list):
                        sentences = para
                    for s in sentences or []:
                        add(s.get("text_only"), s.get("english_text"), "article", title, doc.get("url"))
        except Exception as e:
            log.warning("idea index articles: %s", e)
        try:
            if db is not None:
                for doc in db["conversation_phrases"].find({"mt": False}, {"chk": 1, "en": 1}):
                    add(doc.get("chk"), doc.get("en"), "conversation")
        except Exception as e:
            log.warning("idea index conversations: %s", e)
        return rows

    # -- build -----------------------------------------------------------

    def _build(self) -> None:
        import numpy as np

        try:
            rows = self._collect()
            row_roots = [roots(r["en"]) for r in rows]
            with self._lock:
                self.rows, self.row_roots, self.loaded_at = rows, row_roots, time.time()
            if self.embedder.model is None:
                self.embedder.load()
            cached: dict[str, "np.ndarray"] = {}
            if self.cache.exists():
                try:
                    z = np.load(self.cache, allow_pickle=False)
                    cached = dict(zip(z["keys"].tolist(), z["vectors"]))
                except Exception as e:
                    log.warning("idea index cache unreadable: %s", e)
            keys = [hashlib.sha1(r["en"].encode("utf-8")).hexdigest() for r in rows]
            todo = [i for i, k in enumerate(keys) if k not in cached]
            if todo:
                fresh = self.embedder.encode([rows[i]["en"] for i in todo])
                for i, v in zip(todo, fresh):
                    cached[keys[i]] = v
            vectors = np.stack([cached[k] for k in keys]) if rows else np.zeros((0, 384), dtype="float32")
            try:
                self.cache.parent.mkdir(parents=True, exist_ok=True)
                np.savez(self.cache, keys=np.array(keys), vectors=vectors)
            except Exception as e:
                log.warning("idea index cache not written: %s", e)
            with self._lock:
                self.vectors, self.status, self.error = vectors, "ready", ""
            log.info("idea index ready: %d sentences", len(rows))
        except Exception as e:
            log.warning("idea index unavailable: %s", e)
            with self._lock:
                self.status, self.error = "unavailable", str(e)[:200]

    def ensure(self) -> None:
        """Start (or refresh) the build in the background; never blocks."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            if self.status == "ready" and time.time() - self.loaded_at < REFRESH_SECONDS:
                return
            if self.status == "unavailable" and time.time() - self.loaded_at < 300:
                return
            self.status = "building" if self.vectors is None else self.status
            self._thread = threading.Thread(target=self._build, name="idea-index", daemon=True)
            self._thread.start()

    def wait(self, seconds: float) -> None:
        if self._thread:
            self._thread.join(seconds)

    # -- search ----------------------------------------------------------

    def search(self, english: str, chuukese: str = "", context: str = "", limit: int = 10) -> dict:
        """Stored sentences closest in meaning to `english` (the line), with the
        ideas and subjects searched for and, per hit, which ideas it carries."""
        import numpy as np

        idea_list = ideas(english)
        about = subjects(english, context)
        idea_roots = [roots(p) for p in idea_list]
        about_roots = {root(a) for a in about}
        with self._lock:
            rows, row_roots, vectors, status = self.rows, self.row_roots, self.vectors, self.status
        line_roots = roots(english)
        n = len(rows)
        if n == 0:
            return {"ideas": idea_list, "about": about, "items": [], "index": status, "indexed": 0}

        sem = np.zeros(n, dtype="float32")
        idea_sem = np.zeros((max(len(idea_list), 1), n), dtype="float32")
        if vectors is not None and status == "ready" and len(vectors) == n:
            q = self.embedder.encode([english] + idea_list)
            # numpy 2 on Apple's BLAS raises spurious RuntimeWarnings on float32
            # matmul (the values are correct and match float64); keep them out of the log.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                sem = np.nan_to_num(vectors @ q[0])
                if idea_list:
                    idea_sem = np.nan_to_num(q[1:] @ vectors.T)

        line_norm = _norm(chuukese)
        scored = []
        for i, r in enumerate(rows):
            if _norm(r["chk"]) == line_norm:
                continue
            rr = row_roots[i]
            # An idea counts as present when all its roots occur (one may be missing in a long idea).
            matched = [idea_list[k] for k, ir in enumerate(idea_roots) if ir and len(ir & rr) >= len(ir) - (1 if len(ir) >= 4 else 0)]
            shared = len(line_roots & rr) / max(1, min(len(line_roots), len(rr))) if line_roots and rr else 0.0
            named = bool(about_roots & rr)
            if status == "ready":
                meaning = max(float(sem[i]), 0.9 * float(idea_sem[:, i].max()) if idea_list else 0.0)
                score = 0.75 * meaning + min(0.3, 0.15 * len(matched)) + (0.08 if named else 0.0) + 0.1 * shared
                floor = 0.42
            else:
                meaning = 0.0
                score = min(0.6, 0.3 * len(matched)) + 0.4 * shared + (0.1 if named else 0.0)
                floor = 0.25
            if score >= floor:
                scored.append((score, meaning, matched, named, i))
        scored.sort(key=lambda t: -t[0])
        items, seen_en = [], set()
        for score, meaning, matched, named, i in scored:
            if len(items) >= limit:
                break
            if _norm(rows[i]["en"]) in seen_en:  # the same English under variant Chuukese spellings
                continue
            seen_en.add(_norm(rows[i]["en"]))
            items.append({**rows[i], "score": round(min(score, 0.99), 2), "meaning": round(meaning, 2), "matched": matched, "named": named})
        return {"ideas": idea_list, "about": about, "items": items, "index": status, "indexed": n, "error": self.error}


_INDEX: IdeaIndex | None = None
_INDEX_LOCK = threading.Lock()


def get_index(dict_db) -> IdeaIndex:
    global _INDEX
    with _INDEX_LOCK:
        if _INDEX is None:
            _INDEX = IdeaIndex(dict_db)
        return _INDEX


__all__ = ["ideas", "subjects", "roots", "root", "Embedder", "IdeaIndex", "get_index"]
