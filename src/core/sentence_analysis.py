"""
Sentence analysis helpers: accent-variant matching and dictionary proposals.

The Sentence Analysis and Article Analysis pages look every word up in the
dictionary. This module holds the parts of that work that need no database:

- which unknown words are really known words spelled with different accents
  ("pwaselo" for the headword "pwáseló");
- a grammar guess for a word from its English gloss;
- assembling a proposed dictionary entry for a word we do not hold, from the
  evidence the app can gather (accent variants, related entries, the
  translation model's gloss, and how wol.jw.org renders the word in English).

Nothing here writes to the dictionary. Proposals are shown to the user, who
either adds the entry on the spot or sends it to the review queue.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from src.core.verb_verification import Baseline, renderings

# Letters and digits (no underscore): the same split the frontend uses.
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def norm_word(word: str) -> str:
    """Lowercase and strip diacritics, so 'pwáseló' and 'pwaselo' compare equal."""
    decomposed = unicodedata.normalize("NFD", (word or "").lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def words_in(text: str) -> list[str]:
    """The words of `text` in order, as they appear (case kept)."""
    return [m.group(0) for m in WORD_RE.finditer(text or "")]


def word_keys(text: str) -> set[str]:
    """Lowercase word keys of `text`, numbers left out (they are never headwords)."""
    return {w.lower() for w in words_in(text) if not w.isdigit()}


def accent_variants(keys: set[str], known: dict, by_norm: dict) -> dict[str, list[str]]:
    """Headwords that match each unknown key once accents are ignored.

    `by_norm` maps an accent-stripped form to the set of headwords spelled that
    way (as built by the similarity index). A headword equal to the key apart
    from case is not a variant — the bulk lookup would have found it.
    """
    out: dict[str, list[str]] = {}
    for key in keys:
        if key in known:
            continue
        heads = by_norm.get(norm_word(key)) or ()
        variants = sorted({h for h in heads if h.lower() != key})
        if variants:
            out[key] = variants
    return out


# ---------------------------------------------------------------------------
# Grammar guess from an English gloss
# ---------------------------------------------------------------------------

_PRONOUNS = {
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "mine", "yours", "ours", "theirs",
    "this", "that", "these", "those", "who", "whom", "what", "which",
}
_PREPOSITIONS = {
    "in", "on", "at", "to", "from", "with", "without", "for", "of", "by", "about",
    "into", "onto", "over", "under", "through", "between", "among", "toward", "towards",
    "before", "after", "during", "until", "against", "upon", "within",
}
_CONJUNCTIONS = {"and", "or", "but", "because", "if", "when", "while", "although", "though", "so", "nor", "whether"}
_INTERROGATIVES = {"why", "how", "where", "when", "who", "what", "which"}
_DEMONSTRATIVES = {"this", "that", "these", "those", "here", "there"}
_AUX = {"will", "would", "shall", "should", "can", "could", "may", "might", "must", "did", "do", "does", "have", "has", "had"}
_ADVERB_SUFFIX = ("ly",)
_ADJ_SUFFIX = ("ful", "less", "ous", "ive", "able", "ible", "al", "ish", "ic")
_NOUN_SUFFIX = ("tion", "sion", "ment", "ness", "ity", "ship", "hood", "er", "or", "ism")


def suggest_grammar(english: str) -> str:
    """A part-of-speech guess from an English gloss. Rough, but it gives the
    add-word form a sensible default instead of an empty field."""
    text = (english or "").strip().lower()
    if not text:
        return ""
    if text.startswith("to "):
        return "verb"
    first = re.sub(r"[^a-z']", "", text.split(",")[0].split()[0] if text.split() else "")
    if not first:
        return ""
    if first in _INTERROGATIVES:
        return "interrogative"
    if first in _DEMONSTRATIVES:
        return "demonstrative"
    if first in _PRONOUNS:
        return "pronoun"
    if first in _PREPOSITIONS:
        return "preposition"
    if first in _CONJUNCTIONS:
        return "conjunction"
    if first in _AUX:
        return "auxiliary"
    if first.endswith(_ADVERB_SUFFIX) and len(first) > 4:
        return "adverb"
    if first.endswith(_ADJ_SUFFIX) and len(first) > 5:
        return "adjective"
    if first.endswith(_NOUN_SUFFIX) and len(first) > 5:
        return "noun"
    if first.endswith("ing") or first.endswith("ed"):
        return "verb"
    return ""


# ---------------------------------------------------------------------------
# Evidence from wol.jw.org
# ---------------------------------------------------------------------------


def wol_pairs(results: list[dict], english: list[dict | None]) -> list[dict]:
    """Chuukese/English sentence pairs from WOL results and their English
    equivalents, keeping only the ones where an English sentence lined up."""
    pairs = []
    for result, en in zip(results, english):
        if not en or not en.get("text"):
            continue
        pairs.append(
            {
                "chk": result.get("text") or "",
                "en": en["text"],
                "scope": en.get("scope"),
                "link": result.get("link"),
                "english_link": en.get("link"),
                "citation": result.get("citation") or en.get("citation"),
                "title": result.get("title") or en.get("title"),
            }
        )
    return pairs


def wol_renderings(pairs: list[dict]) -> list[dict]:
    """How WOL renders the word in English, from its sentence pairs. With only
    a handful of pairs the baseline is the pairs themselves; `renderings`
    already excludes the word's own sentences from the background rate."""
    if len(pairs) < 2:
        return []
    baseline = Baseline()
    for p in pairs:
        baseline.add(p["en"])
    return renderings(pairs, baseline, min_count=2, min_lift=1.5)


# ---------------------------------------------------------------------------
# The proposal
# ---------------------------------------------------------------------------


def _clean_gloss(text: str, word: str) -> str:
    """A model gloss is only useful when it is actual English, not the word
    echoed back or a whole sentence."""
    gloss = (text or "").strip().strip(".").strip()
    if not gloss or norm_word(gloss) == norm_word(word):
        return ""
    if len(gloss.split()) > 6:
        return ""
    return gloss


def build_proposal(
    word: str,
    variants: list[dict],
    similar: list[dict],
    rend: list[dict],
    model_word: str,
    context_english: str | None = None,
) -> dict:
    """Pick the best-supported English, grammar and definition for `word`.

    Order of trust: the same word under different accents (it *is* the entry),
    then what WOL renders it as across several sentences, then the translation
    model's gloss. Grammar follows the same source, falling back to the most
    common grammar among related entries, then a guess from the English.
    """
    english = ""
    grammar = ""
    definition = ""
    source = ""
    model_gloss = _clean_gloss(model_word, word)

    with_english = [v for v in variants if v.get("english")]
    if with_english:
        v = with_english[0]
        english, grammar, definition, source = v["english"], v.get("grammar", ""), v.get("definition", ""), "accent_variant"
    elif rend:
        top = rend[0]
        # Prefer a rendering the model agrees with, when there is one.
        agreeing = [r for r in rend if model_gloss and r["stem"] in {s for s in _stems(model_gloss)}]
        chosen = agreeing[0] if agreeing else top
        english, source = chosen["word"], "wol"
    elif model_gloss:
        english, source = model_gloss, "model"

    if not grammar:
        counts = Counter(s.get("grammar") for s in similar if s.get("grammar"))
        if counts:
            grammar = counts.most_common(1)[0][0]
    if not grammar and english:
        grammar = suggest_grammar(english)

    confirmed_in_context = bool(
        english and context_english and _stems(english) & _stems(context_english)
    )

    return {
        "english": english,
        "grammar": grammar or "",
        "definition": definition or "",
        "source": source,
        "model_gloss": model_gloss,
        "confirmed_in_context": confirmed_in_context,
    }


def _stems(text: str) -> set[str]:
    from src.core.verb_verification import english_content_words  # noqa: PLC0415

    return {s for _, s in english_content_words(text or "")}


# ---------------------------------------------------------------------------
# Finding the sentence itself on wol.jw.org
# ---------------------------------------------------------------------------
# The model's translation of a sentence is a guess. When the sentence comes
# from a publication, wol.jw.org holds the real English, so the analysis
# page looks the sentence up there first. WOL honours quoted exact-phrase
# queries, but long queries with punctuation or scripture citations miss, so
# the sentence is cleaned and, failing a whole-sentence hit, searched by
# shorter windows of consecutive words.

_PAREN_REF_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*")
# Punctuation inside a quoted phrase breaks WOL's exact-phrase matching, so
# the query keeps only the words.
_INNER_PUNCT_RE = re.compile(r"[,;:!?\"\u201c\u201d\u2018\u2019\(\)\[\]\u2014\u2013]+")
_TRAIL_RE = re.compile(r"[\s\.\!\?\:;,—–\-\"'“”‘’]+$")
_LEAD_RE = re.compile(r"^[\s\"'“”‘’—–\-]+")
SOURCE_WINDOW = 8


def clean_for_search(sentence: str) -> str:
    """The sentence as WOL would index it: no bracketed citations, no
    surrounding quotes or dashes, single spaces."""
    text = _PAREN_REF_RE.sub(" ", sentence or "")
    text = _INNER_PUNCT_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    text = _LEAD_RE.sub("", _TRAIL_RE.sub("", text.strip()))
    return text.strip()


def source_queries(sentence: str, window: int = SOURCE_WINDOW) -> list[str]:
    """Quoted exact-phrase queries to try in order: the whole sentence, then
    (for long sentences) windows of `window` words from the start, the
    middle and the end. Duplicates are dropped."""
    text = clean_for_search(sentence)
    if not text:
        return []
    words = text.split(" ")
    queries = [f'"{text}"']
    if len(words) > window:
        starts = {0, max(0, (len(words) - window) // 2), len(words) - window}
        for s in sorted(starts):
            chunk = " ".join(words[s : s + window])
            q = f'"{chunk}"'
            if q not in queries:
                queries.append(q)
    return queries


def _norm_tokens(text: str) -> list[str]:
    return [norm_word(w) for w in words_in(text)]


def source_score(sentence: str, candidate: str) -> float:
    """How much of the sentence the candidate text contains, 0..1, comparing
    accent-stripped words. 1.0 means every word of the sentence appears in
    order in the candidate."""
    want = _norm_tokens(clean_for_search(sentence))
    have = _norm_tokens(candidate)
    if not want or not have:
        return 0.0
    # Longest run of the sentence found contiguously in the candidate.
    best = 0
    for i in range(len(have)):
        k = 0
        while i + k < len(have) and k < len(want) and have[i + k] == want[k]:
            k += 1
        best = max(best, k)
    if best == len(want):
        return 1.0
    # Otherwise, the share of sentence words present at all.
    present = sum(1 for w in want if w in set(have))
    return round(max(best, present * 0.9) / len(want), 3)


def pick_source(sentence: str, results: list[dict], english: list[dict | None], min_score: float = 0.6) -> dict | None:
    """The best WOL result for the sentence, with its English attached.

    Prefers a result whose English lined up at sentence level, then the
    closest text match. Returns None when nothing scores above `min_score`.
    """
    best = None
    for result, en in zip(results, english):
        score = source_score(sentence, result.get("text") or "")
        if score < min_score:
            continue
        aligned = 1 if en and en.get("scope") == "sentence" else 0
        has_en = 1 if en and en.get("text") else 0
        key = (score >= 1.0, has_en, aligned, score)
        if best is None or key > best[0]:
            best = (key, result, en)
    if best is None:
        return None
    _, result, en = best
    return {
        "chuukese": result.get("text") or "",
        "segments": result.get("segments") or [],
        "title": result.get("title"),
        "link": result.get("link"),
        "citation": result.get("citation"),
        "reference": result.get("reference") or {},
        "english": en,
        "score": source_score(sentence, result.get("text") or ""),
        "exact": source_score(sentence, result.get("text") or "") >= 1.0,
    }
