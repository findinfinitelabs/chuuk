"""
Verify dictionary verbs against real usage on wol.jw.org.

Given a verb and the Chuukese/English sentence pairs WOL yields for it, this
module works out how the verb is actually rendered in English (the
"renderings"), how well the dictionary's current translation is supported,
and what, if anything, should change. Nothing here writes to the dictionary:
it produces review proposals, and the review page applies them.

Two kinds of proposal come out:

- ``translation``: the current English is confirmed, needs review (WOL renders
  the word differently), or WOL also uses senses the entry lacks.
- ``grammar``: mechanical fixes — a normalised grammar modifier, and for
  suffixed/directional forms, which base word they inflect. These are
  deterministic and marked ``tier="auto"``.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# English side
# ---------------------------------------------------------------------------

STOPWORDS = set(
    """
a an the and or but if then than so as of to in on at by for from with without into onto
over under about above below between among through during before after until while because
although though whether is are was were be been being am do does did done doing have has had
having will would shall should can could may might must ought not no nor never ever also too
very just only even still yet already again more most much many few little less least some any
all each every either neither both other another such same own this that these those there here
where when why how what which who whom whose it its he him his she her hers they them their
theirs we us our ours you your yours i me my mine one ones someone anyone everyone nothing
something anything everything self himself herself themselves ourselves yourself itself up down
out off away back forth around along across toward towards upon within against per via
let lets make makes made making get gets got getting go goes went going come comes came coming
take takes took taking give gives gave given giving put say says said saying tell told
thing things way ways time times day days year years people person man men woman women
jehovah god jesus christ lord bible kingdom israel paul david moses jerusalem jews christian
christians brother brothers sister sisters congregation elders elder witnesses verse chapter
""".split()
)

_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_SUFFIXES = ("ingly", "ing", "edly", "ed", "ies", "es", "s", "ly", "ness", "ment", "tion", "sion", "ful")


def stem(word: str) -> str:
    """A crude stemmer: enough to let 'encourage', 'encouraged' and 'encouraging'
    land on the same key. Not for display — keep the surface form for that."""
    w = word.lower().replace("’", "'").rstrip("'")
    if w.endswith("'s"):
        w = w[:-2]
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            if suf == "ies":
                w += "y"
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def english_content_words(sentence: str) -> list[tuple[str, str]]:
    """(surface, stem) for each content word in an English sentence.

    Proper nouns (capitalised anywhere but sentence-initially), acronyms and
    possessives are skipped: "Satan", "LMD" and "God’s" are never how a verb is
    rendered, and with only a handful of sentences they otherwise float up."""
    out = []
    text = sentence or ""
    for m in _WORD.finditer(text):
        surface = m.group(0)
        low = surface.lower().replace("’", "'")
        if low in STOPWORDS or len(low) < 3 or "'" in low:
            continue
        if surface.isupper():
            continue
        if surface[0].isupper():
            before = text[: m.start()].rstrip()
            sentence_initial = not before or before[-1] in ".!?:;“\"‘'—-"
            if not sentence_initial:
                continue
        out.append((surface, stem(low)))
    return out


def sense_stems(english: str) -> list[set[str]]:
    """The dictionary's English, split into its senses, each as a set of stems.
    'to purify, to clean' → [{'purify'}, {'clean'}]."""
    senses = []
    for part in re.split(r"[,;/]|\bor\b", english or ""):
        part = re.sub(r"^\s*to\s+", "", part.strip(), flags=re.I)
        stems = {s for _, s in english_content_words(part)}
        if stems:
            senses.append(stems)
    return senses


# ---------------------------------------------------------------------------
# Renderings
# ---------------------------------------------------------------------------


class Baseline:
    """Document frequency of English stems across every sentence in a run, so
    a word that is simply common everywhere ('help', 'know') is not mistaken
    for the rendering of one particular verb."""

    def __init__(self):
        self.df: Counter = Counter()
        self.n = 0

    def add(self, sentence: str) -> None:
        self.n += 1
        self.df.update({s for _, s in english_content_words(sentence)})

    def rate(self, stem_: str, exclude_df: int = 0, exclude_n: int = 0) -> float:
        """Background rate of a stem, leaving out the sentences of the verb under
        study (they would otherwise dominate a small run). A mild prior keeps
        the rate sensible when the background is tiny."""
        df = max(self.df.get(stem_, 0) - exclude_df, 0)
        n = max(self.n - exclude_n, 0)
        return (df + 0.5) / (n + 10)


def renderings(pairs: list[dict], baseline: Baseline, min_count: int = 2, min_lift: float = 2.0) -> list[dict]:
    """Candidate English renderings of the verb across its sentence pairs.

    Each pair is ``{"chk": ..., "en": ...}``. A rendering is an English stem that
    occurs in several of the pairs and far more often there than in the corpus
    at large. Returns dicts sorted by score:
    ``{"stem", "word", "count", "share", "lift", "score", "examples": [pair indexes]}``.
    """
    n = len(pairs)
    if n == 0:
        return []
    per_stem_pairs: dict[str, set[int]] = defaultdict(set)
    surfaces: dict[str, Counter] = defaultdict(Counter)
    capitalised: Counter = Counter()
    occurrences: Counter = Counter()
    for i, p in enumerate(pairs):
        for surface, s in english_content_words(p.get("en", "")):
            per_stem_pairs[s].add(i)
            surfaces[s][surface.lower()] += 1
            occurrences[s] += 1
            if surface[0].isupper():
                capitalised[s] += 1

    out = []
    for s, idxs in per_stem_pairs.items():
        count = len(idxs)
        if count < min_count:
            continue
        # A name that only survived the sentence-initial exception still shows
        # as capitalised in most of its occurrences; a verb does not.
        if capitalised[s] / occurrences[s] >= 0.6:
            continue
        share = count / n
        lift = share / baseline.rate(s, exclude_df=count, exclude_n=n)
        if lift < min_lift:
            continue
        score = share * math.log(1 + lift)
        out.append(
            {
                "stem": s,
                "word": surfaces[s].most_common(1)[0][0],
                "count": count,
                "share": round(share, 3),
                "lift": round(lift, 1),
                "score": round(score, 3),
                "examples": sorted(idxs)[:5],
            }
        )
    out.sort(key=lambda r: (-r["score"], -r["count"], r["word"]))
    return out[:8]


def sense_support(english: str, pairs: list[dict]) -> list[dict]:
    """How many pairs contain each sense of the current translation."""
    out = []
    pair_stems = [{s for _, s in english_content_words(p.get("en", ""))} for p in pairs]
    for sense in sense_stems(english):
        hits = [i for i, stems in enumerate(pair_stems) if sense & stems]
        out.append({"sense": " ".join(sorted(sense)), "count": len(hits), "examples": hits[:5]})
    return out


# ---------------------------------------------------------------------------
# Translation proposals
# ---------------------------------------------------------------------------

MIN_PAIRS = 3
CONFIRM_SHARE = 0.4
STRONG_SHARE = 0.4
STRONG_COUNT = 3


def translation_proposal(entry: dict, pairs: list[dict], baseline: Baseline) -> dict:
    """Judge one verb's translation against its WOL evidence.

    Outcomes:
      no_evidence          WOL has no usable sentence pairs
      insufficient         fewer than MIN_PAIRS pairs
      confirmed            the current English appears in enough pairs (auto: mark verified)
      add_senses           confirmed, but WOL also renders it other ways worth adding (review)
      needs_review         the current English does not appear in the pairs (review)
    """
    english = (entry.get("english_translation") or "").strip()
    n = len(pairs)
    rend = renderings(pairs, baseline) if n else []
    support = sense_support(english, pairs) if n else []
    supported = max((s["count"] for s in support), default=0)
    support_share = supported / n if n else 0.0
    covered = {st for s in sense_stems(english) for st in s}
    extra = [r for r in rend if r["stem"] not in covered and r["count"] >= STRONG_COUNT and r["share"] >= STRONG_SHARE]

    if n == 0:
        outcome, tier = "no_evidence", None
    elif n < MIN_PAIRS:
        outcome, tier = "insufficient", None
    elif support_share >= CONFIRM_SHARE:
        outcome, tier = ("add_senses", "review") if extra else ("confirmed", "auto")
    else:
        outcome, tier = "needs_review", "review"

    # Suggestions are the renderings strong enough to be worth the reviewer's
    # attention; the proposed wording is only prefilled with them when the
    # agreement is high, otherwise it starts from the current wording and the
    # reviewer builds the new one from the suggestion chips.
    suggestions = [r for r in rend if r["count"] >= STRONG_COUNT and r["share"] >= STRONG_SHARE]
    proposed = None
    if outcome == "add_senses":
        proposed = {"english_translation": english + ", " + ", ".join(r["word"] for r in extra[:3])}
    elif outcome == "needs_review":
        strong = [r for r in suggestions if r["share"] >= 0.7]
        proposed = {"english_translation": ", ".join(r["word"] for r in strong[:2]) if strong else english}
    elif outcome == "confirmed":
        proposed = {"wol_verified": True}

    return {
        "kind": "translation",
        "outcome": outcome,
        "tier": tier,
        "status": "pending" if tier else "info",
        "current": {"english_translation": english, "grammar": entry.get("grammar"), "definition": entry.get("definition")},
        "proposed": proposed,
        "evidence": {
            "pair_count": n,
            "support_share": round(support_share, 3),
            "senses": support,
            "renderings": rend,
            "suggestions": [r["word"] for r in suggestions],
            "forms": sorted({p.get("form") for p in pairs if p.get("form")}),
            "pairs": pairs[:12],
        },
    }


# ---------------------------------------------------------------------------
# Grammar proposals
# ---------------------------------------------------------------------------

# The free-text modifiers in the data, mapped onto a fixed vocabulary.
MODIFIER_CANON = {
    "transitive": "transitive",
    "intransitive": "intransitive",
    "stative": "stative",
    "causative": "causative",
    "reduplicated": "reduplicated",
    "directional": "directional",
    "pronoun suffix": "object suffix",
    "pronoun": "object suffix",
    "pronoun form": "object suffix",
    "suffix": "object suffix",
    "transitive + suffix": "transitive, object suffix",
    "transitive + pronoun suffix": "transitive, object suffix",
    "transitive + pronoun": "transitive, object suffix",
    "transitive + directional": "transitive, directional",
    "or adjective": "also adjective",
    "or noun": "also noun",
}

OBJECT_SUFFIXES = {
    "ei": "1sg object (me)",
    "uk": "2sg object (you)",
    "úk": "2sg object (you)",
    "kem": "1pl excl object (us, excl.)",
    "kemi": "2pl object (you pl.)",
    "kich": "1pl incl object (us, incl.)",
    "ir": "3pl object (them)",
    "r": "3pl object (them)",
}
DIRECTIONALS = {
    "ló": "away / completive",
    "lo": "away / completive",
    "tá": "upward",
    "ta": "upward",
    "tiw": "downward",
    "to": "toward speaker",
    "wu": "outward",
    "feil": "around / about",
    "fetál": "around / about",
}
_DEF_INFLECTION = re.compile(r"^\s*([^\s+→]+)\s*(?:→\s*\S+\s*)?\+\s*suffix\s+-?(\S+?)\s*(?:\(|$)", re.I)


def normalize_modifier(modifier: str | None) -> str | None:
    if not modifier:
        return None
    key = re.sub(r"\s+", " ", modifier.strip().lower())
    return MODIFIER_CANON.get(key, key)


def detect_inflection(headword: str, definition: str | None, known_words: set[str]) -> dict | None:
    """Work out whether a headword is an inflected form of a base word.

    Trusts the definition's own "base + suffix -x" note first, then falls back
    to peeling a known object suffix or directional off the headword when what
    is left is itself a dictionary word."""
    head = (headword or "").strip()
    m = _DEF_INFLECTION.match(definition or "")
    if m:
        base, suffix = m.group(1).strip(), m.group(2).strip("-")
        kind = "object suffix" if suffix in OBJECT_SUFFIXES else "directional" if suffix in DIRECTIONALS else "suffix"
        return {"base_word": base, "suffix": suffix, "kind": kind}
    for table, kind in ((OBJECT_SUFFIXES, "object suffix"), (DIRECTIONALS, "directional")):
        for suffix in sorted(table, key=len, reverse=True):
            if head.endswith(suffix) and len(head) - len(suffix) >= 3:
                base = head[: -len(suffix)]
                if base in known_words:
                    return {"base_word": base, "suffix": suffix, "kind": kind}
    return None


def grammar_proposal(entry: dict, known_words: set[str]) -> dict | None:
    """Mechanical fixes for one entry, or None when nothing needs changing."""
    changes: dict = {}
    notes = []
    modifier = entry.get("grammar_modifier")
    canon = normalize_modifier(modifier)
    if modifier and canon != modifier:
        changes["grammar_modifier"] = canon
        notes.append(f"modifier “{modifier}” → “{canon}”")

    inflection = detect_inflection(entry.get("chuukese_word", ""), entry.get("definition"), known_words)
    if inflection and not entry.get("base_word"):
        changes["base_word"] = inflection["base_word"]
        changes["inflection"] = {"suffix": inflection["suffix"], "kind": inflection["kind"]}
        notes.append(f"inflected form of “{inflection['base_word']}” ({inflection['kind']} -{inflection['suffix']})")
        if inflection["kind"] == "object suffix" and (entry.get("grammar") or "").lower() != "verb":
            changes["grammar"] = "verb"
            notes.append(f"takes an object suffix, so “{entry.get('grammar')}” → “verb”")
        if inflection["kind"] == "object suffix" and "object suffix" not in (canon or ""):
            changes["grammar_modifier"] = ", ".join(x for x in [canon, "object suffix"] if x)

    if not changes:
        return None
    return {
        "kind": "grammar",
        "outcome": "normalize",
        "tier": "auto",
        "status": "pending",
        "current": {
            "grammar": entry.get("grammar"),
            "grammar_modifier": modifier,
            "base_word": entry.get("base_word"),
            "definition": entry.get("definition"),
        },
        "proposed": changes,
        "evidence": {"notes": notes},
    }


# ---------------------------------------------------------------------------
# Choosing which verbs to check first
# ---------------------------------------------------------------------------


def rank_verbs(verbs: list[dict], corpus_counts: Counter) -> list[dict]:
    """Base forms with many derived entries, and words common in the local
    corpus, come first — that is where a wrong translation costs the most."""
    heads = [v["chuukese_word"].strip() for v in verbs]
    derived = Counter()
    for v in verbs:
        m = _DEF_INFLECTION.match(v.get("definition") or "")
        if m:
            derived[m.group(1).strip()] += 1
    prefix_children = Counter()
    sorted_heads = sorted(set(heads))
    for h in sorted_heads:
        if len(h) < 4:
            continue
        for other in sorted_heads:
            if other != h and other.startswith(h) and len(other) <= len(h) + 5:
                prefix_children[h] += 1

    def score(v):
        h = v["chuukese_word"].strip()
        return derived[h] * 3 + prefix_children[h] + corpus_counts.get(h.lower(), 0) * 2

    return sorted(verbs, key=lambda v: (-score(v), v["chuukese_word"]))


__all__ = [
    "Baseline",
    "renderings",
    "sense_support",
    "translation_proposal",
    "grammar_proposal",
    "detect_inflection",
    "normalize_modifier",
    "rank_verbs",
    "stem",
]
