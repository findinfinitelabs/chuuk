#!/usr/bin/env python3
"""
Review the grammar type of every dictionary word and keep the labels simple.

Labels: verb, noun, adjective, adverb, pronoun, preposition, conjunction,
number, particle, phrase (and "unknown" when nothing supports a choice).

Evidence, in order of cost:
  1. the entry itself: its current label, the shape of the English, Chuukese
     affixes (object suffixes, directionals, possessive endings);
  2. how the word is used in the stored Chuukese text (phrases, analysed
     articles, conversations, Bible chapters, dictionary examples): a subject
     marker in front means verb, an article or possessive in front means noun,
     "mi" in front means adjective, and so on;
  3. wol.jw.org, only for words still uncertain after 1 and 2, capped, one
     slow request each through PoliteFetcher (cached on disk), stopping at
     once if the site declines.

Writes, per entry, a `grammar_review` record (label, confidence, evidence,
previous label, date). The `grammar` field itself is changed only when the
entry was not set by a person, the new label is confident, and the current
label is missing or not one of the simple set. Disagreements with an existing
simple label are reported, never applied. Report and CSV go to logs/.

Usage:
  python scripts/grammar_review.py [--dry-run] [--limit N] [--wol-cap 120]
         [--min-interval 4] [--no-wol]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from scripts.harvest_wol_pairs import PoliteFetcher  # noqa: E402
from src.core.wol_search import WOL_SEARCH, WOLSearch  # noqa: E402
from src.core.verb_forms import MARKER_INDEX  # noqa: E402

LOG_DIR = ROOT / "logs"
TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")
RUN_TAG = f"grammar_review {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

SIMPLE = ["verb", "noun", "adjective", "adverb", "pronoun", "preposition", "conjunction", "number", "particle", "phrase"]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── normalisation ───────────────────────────────────────────────────────────

def norm(s: str) -> str:
    d = unicodedata.normalize("NFD", (s or "").lower().replace("-", ""))
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


_TOKEN = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [norm(t) for t in _TOKEN.findall(text or "")]


def simple_of(grammar: str | None, modifier: str | None = None) -> str | None:
    """Map the many existing labels onto the simple set; None when unmappable."""
    g = (grammar or "").strip().lower()
    if not g:
        return None
    if g in SIMPLE:
        return g
    if g.startswith(("verb", "transitive", "intransitive", "stative verb", "v.", "vt", "vi")):
        return "verb"
    if g.startswith(("noun", "n.", "possessive", "possessed")):
        return "noun"
    if g.startswith(("adj", "stative")):
        return "adjective"
    if g.startswith(("adv",)):
        return "adverb"
    if g.startswith(("pron", "interrog")):
        return "pronoun"
    if g.startswith(("prep",)):
        return "preposition"
    if g.startswith(("conj",)):
        return "conjunction"
    if g.startswith(("num", "ordinal", "classifier", "cardinal")):
        return "number"
    if g.startswith(("particle", "interjection", "exclamation", "suffix", "prefix", "marker", "article", "demonstrative", "determiner")):
        return "particle"
    if g.startswith(("phrase", "sentence", "expression", "idiom")):
        return "phrase"
    return None


# ── context words ───────────────────────────────────────────────────────────

SUBJECT = {norm(m) for m in MARKER_INDEX}
BETWEEN = {"fen", "kan", "chek", "pwal", "mwo", "tongeni", "fokkun", "chuen", "kon"}
NOUN_BEFORE = {"ewe", "ekkewe", "eu", "emen", "ei", "ena", "ekkei", "ekkena", "neun", "an", "ach", "ai", "om", "am", "ar", "ami", "och", "ekkoch", "chommong", "ekis", "en", "ewe", "nouch", "noum", "noun", "nour"}
NOUN_AFTER = {"we", "kewe", "kei", "na", "nan", "ei", "ena", "kena"}
ADJ_BEFORE = {"mi", "fokkun", "kon", "pwal", "kkon"}
VERB_BEFORE = {"le", "pwe"}  # "le féri" = to do; "pwe epwe" is handled by markers

PRONOUN_EN = {"i", "me", "my", "mine", "you", "your", "yours", "he", "she", "it", "him", "her", "his", "hers", "its", "we", "us", "our", "ours", "they", "them", "their", "theirs", "this", "that", "these", "those", "who", "whom", "whose", "what", "which", "someone", "anyone", "everyone", "nobody", "myself", "yourself", "himself", "herself", "ourselves", "themselves"}
PREP_EN = {"of", "in", "on", "to", "from", "with", "at", "by", "for", "under", "over", "between", "through", "toward", "towards", "until", "into", "onto", "about", "above", "below", "behind", "beside", "near", "among", "across", "after", "before", "during", "without", "within", "against", "along", "around", "inside", "outside", "upon"}
CONJ_EN = {"and", "but", "because", "or", "if", "so", "then", "when", "while", "although", "though", "unless", "since", "whether", "nor", "yet", "therefore", "however", "until", "as"}
NUMBER_EN = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million", "first", "second", "third", "fourth", "fifth", "tenth", "half", "dozen"}
ADVERB_EN = {"very", "also", "only", "just", "already", "still", "again", "always", "never", "often", "sometimes", "now", "then", "soon", "later", "today", "tomorrow", "yesterday", "here", "there", "too", "almost", "really", "quickly", "slowly", "together", "away", "back", "far", "immediately", "usually", "perhaps", "maybe", "not", "yes", "no"}
PARTICLE_EN = {"yes", "no", "oh", "hey", "please", "indeed", "certainly", "okay", "ok"}

OBJECT_SUFFIX = re.compile(r"(ei|uk|ok|kich|kem|kemi|ir|er)$")
DIRECTIONAL = re.compile(r"(lo|ta|tiw|to|long|wou|sefal|sefan|etiw|eta|elo)$")
POSSESSIVE_EN = re.compile(r"^(my|your|his|her|its|our|their)\b|\bof$", re.IGNORECASE)
MARKER_RX = re.compile(r"^(u|ko|ke|e|si|au|ou|re|a|ka|ra|sia|aua|oua)(a|pwe|pwap|pwele|se|sap|saamwo|samwo|pwap)?$")


# ── corpus ──────────────────────────────────────────────────────────────────

class Corpus:
    """prev/next token counts for every word in the stored Chuukese text."""

    def __init__(self) -> None:
        self.prev: dict[str, Counter] = defaultdict(Counter)
        self.next: dict[str, Counter] = defaultdict(Counter)
        self.count: Counter = Counter()
        self.sentences = 0

    def add(self, text: str) -> None:
        toks = tokens(text)
        if not toks:
            return
        self.sentences += 1
        for i, t in enumerate(toks):
            self.count[t] += 1
            if i > 0:
                self.prev[t][toks[i - 1]] += 1
            if i + 1 < len(toks):
                self.next[t][toks[i + 1]] += 1

    def evidence(self, word: str, cap: float = 3.0) -> tuple[Counter, list[str]]:
        """Scores per label from the contexts the word appears in."""
        w = norm(word)
        score: Counter = Counter()
        notes: list[str] = []
        prev, nxt = self.prev.get(w, Counter()), self.next.get(w, Counter())
        if not prev and not nxt:
            return score, notes

        def add(label: str, n: int, per: float, why: str) -> None:
            if n:
                score[label] += min(cap, n * per)
                notes.append(f"{why}×{n}")

        add("verb", sum(c for p, c in prev.items() if p in SUBJECT), 0.6, "subject marker before")
        add("verb", sum(c for p, c in prev.items() if p in VERB_BEFORE), 0.4, "'le/pwe' before")
        add("noun", sum(c for p, c in prev.items() if p in NOUN_BEFORE), 0.6, "article/possessive before")
        add("noun", sum(c for n_, c in nxt.items() if n_ in NOUN_AFTER), 0.4, "demonstrative after")
        add("adjective", sum(c for p, c in prev.items() if p in ADJ_BEFORE), 0.5, "'mi/fókkun' before")
        return score, notes

    def wol_contexts(self, word: str, html: str, searcher: WOLSearch) -> int:
        """Feed the sentences found on a wol.jw.org results page into the corpus."""
        n = 0
        for item in searcher._parse(html, word):
            text = item.get("text") or "".join(seg.get("text", "") for seg in item.get("segments", []))
            if text:
                self.add(text)
                n += 1
        return n


# ── scoring ─────────────────────────────────────────────────────────────────

def entry_evidence(e: dict, with_prior: bool = True) -> tuple[Counter, list[str]]:
    score: Counter = Counter()
    notes: list[str] = []
    chk = (e.get("chuukese_word") or "").strip()
    if "→" in chk:
        chk = chk.split("→")[-1].strip()
    en = (e.get("english_translation") or "").strip()
    en_l = en.lower()
    en_first = en_l.split(";")[0].split(",")[0].strip()
    en_words = re.findall(r"[a-z']+", en_first)

    prior = simple_of(e.get("grammar"), e.get("grammar_modifier"))
    if prior and with_prior:
        score[prior] += 2.0
        notes.append(f"current label {e.get('grammar')!r}")

    chk_tokens = tokens(chk)
    # Subject pronoun + tense markers (ua, upwe, usaamwo, kepwap …) are one word class of their own.
    if len(chk_tokens) == 1 and (chk_tokens[0] in SUBJECT or MARKER_RX.match(chk_tokens[0])):
        score["pronoun"] += 3.0
        notes.append("subject pronoun / tense marker")
        return score, notes
    if len(chk_tokens) >= 3 or re.search(r"[.?!]$", chk):
        score["phrase"] += 3.0
        notes.append("several words")
        return score, notes

    if en_first.startswith("to ") and len(en_words) >= 2 and en_words[1] not in PRONOUN_EN | {"a", "an", "the"}:
        score["verb"] += 2.0
        notes.append("English 'to …'")
    if en_first.startswith(("to be ", "be ", "is ")) and len(en_words) >= 2:
        score["adjective"] += 1.0
        notes.append("English 'to be …'")
    if en_words and en_words[0] in ("a", "an", "the"):
        score["noun"] += 1.5
        notes.append("English 'a/the …'")
    if POSSESSIVE_EN.search(en_first):
        score["noun"] += 1.5
        notes.append("English possessive / '… of'")
    if len(en_words) == 1:
        w = en_words[0]
        if w in PRONOUN_EN:
            score["pronoun"] += 2.0; notes.append("English pronoun")
        elif w in PREP_EN:
            score["preposition"] += 2.0; notes.append("English preposition")
        elif w in CONJ_EN:
            score["conjunction"] += 2.0; notes.append("English conjunction")
        elif w in NUMBER_EN or w.isdigit():
            score["number"] += 2.0; notes.append("English number")
        elif w in PARTICLE_EN:
            score["particle"] += 1.5; notes.append("English particle")
        elif w in ADVERB_EN or w.endswith("ly"):
            score["adverb"] += 1.5; notes.append("English adverb")
        elif w.endswith(("ness", "tion", "ment", "ship", "hood", "ism", "ist", "ity")):
            score["noun"] += 1.0; notes.append("English noun ending")
        elif w.endswith(("ful", "less", "ous", "ive", "able", "ible", "al", "ish")):
            score["adjective"] += 0.8; notes.append("English adjective ending")
    if re.search(r"\d", en_first) or any(w in NUMBER_EN for w in en_words[:2]) and len(en_words) <= 3:
        score["number"] += 1.0
        notes.append("number word")
    if re.search(r"\b(me|you|us|them|him|her)\b", en_first) and OBJECT_SUFFIX.search(norm(chk)) and len(chk_tokens) == 1:
        score["verb"] += 2.0
        notes.append("object suffix + English object")
    if DIRECTIONAL.search(norm(chk)) and len(chk_tokens) == 1 and len(norm(chk)) > 5 and not prior == "noun":
        score["verb"] += 0.6
        notes.append("directional ending")
    if re.search(r"\b(my|your|his|her|our|their)\b", en_first) and len(chk_tokens) == 1:
        score["noun"] += 1.0
        notes.append("possessed form")
    mod = (e.get("grammar_modifier") or "").lower()
    if "transitive" in mod or "pronoun suffix" in mod or "directional" in mod or "causative" in mod:
        score["verb"] += 1.0; notes.append(f"modifier {mod!r}")
    if "possessive" in mod or "possessed" in mod or "locational" in mod:
        score["noun"] += 1.0; notes.append(f"modifier {mod!r}")
    if "stative" in mod:
        score["adjective"] += 1.0; notes.append(f"modifier {mod!r}")
    if len(chk_tokens) == 2 and not prior:
        score["phrase"] += 1.0
        notes.append("two words")
    return score, notes


def decide(score: Counter) -> tuple[str, float]:
    if not score:
        return "unknown", 0.0
    ranked = score.most_common(2)
    top, top_s = ranked[0]
    second_s = ranked[1][1] if len(ranked) > 1 else 0.0
    total = sum(score.values())
    # Confident when the top label carries most of the weight and clearly beats the runner-up.
    conf = (top_s / total) * min(1.0, (top_s - second_s + 1.0) / 3.0)
    return top, round(conf, 2)


def human_set(e: dict) -> bool:
    by = (e.get("edited_by") or "").strip()
    return bool(e.get("user_confirmed")) or (by and by.upper() not in ("AI", "SYSTEM", "GRAMMAR_REVIEW"))


# ── Cosmos helpers ──────────────────────────────────────────────────────────

def retry(fn, attempts: int = 8):
    delay = 1.0
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if i == attempts - 1 or not ("429" in str(e) or "RequestRateTooLarge" in str(e) or "16500" in str(e)):
                raise
            m = re.search(r"RetryAfterMs=(\d+)", str(e))
            time.sleep(max(delay, int(m.group(1)) / 1000 if m else 0))
            delay = min(delay * 2, 30)
    return None


def scan(col, proj: dict, batch: int = 200):
    """Iterate a collection in _id order, resuming after a throttle."""
    last = None
    while True:
        q = {"_id": {"$gt": last}} if last is not None else {}
        rows = retry(lambda: list(col.find(q, proj).sort("_id", 1).limit(batch)))
        if not rows:
            return
        for r in rows:
            yield r
        last = rows[-1]["_id"]
        time.sleep(0.05)


# ── main ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="score and report, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="only the first N entries (testing)")
    ap.add_argument("--wol-cap", type=int, default=120, help="max wol.jw.org searches (0 = none)")
    ap.add_argument("--min-interval", type=float, default=4.0, help="seconds between wol.jw.org requests")
    ap.add_argument("--no-wol", action="store_true")
    ap.add_argument("--apply-threshold", type=float, default=0.6, help="confidence needed to fill a missing/unmappable label")
    args = ap.parse_args()

    from src.database.dictionary_db import DictionaryDB  # noqa: PLC0415

    db = DictionaryDB()
    col = db.dictionary_collection
    LOG_DIR.mkdir(exist_ok=True)

    # 1. corpus
    log("Loading the stored Chuukese text…")
    corpus = Corpus()
    for r in scan(db.phrases_collection, {"chuukese_phrase": 1, "chuukese_sentence": 1, "chuukese": 1}):
        corpus.add(r.get("chuukese_phrase") or r.get("chuukese_sentence") or r.get("chuukese") or "")
    log(f"  phrases: {corpus.sentences} sentences")
    for r in scan(db.db["article_analysis_paragraphs"], {"paragraph.sentences.text_only": 1}):
        for s in (r.get("paragraph") or {}).get("sentences") or []:
            corpus.add(s.get("text_only") or "")
    log(f"  + articles: {corpus.sentences}")
    for r in scan(db.db["conversation_phrases"], {"chk": 1}):
        corpus.add(r.get("chk") or "")
    for r in scan(db.db["paragraphs"], {"chuukese_paragraph": 1}):
        corpus.add(r.get("chuukese_paragraph") or "")
    for r in scan(db.db["bible_chapters"], {"verses": 1, "lang": 1}):
        if r.get("lang") in ("chk", "chk_lm"):
            for v in (r.get("verses") or {}).values():
                corpus.add(v if isinstance(v, str) else "")
    log(f"  + conversations, paragraphs, Bible: {corpus.sentences} sentences, {len(corpus.count)} distinct words")

    # 2. entries
    proj = {"chuukese_word": 1, "english_translation": 1, "grammar": 1, "grammar_modifier": 1, "edited_by": 1, "user_confirmed": 1, "examples": 1}
    entries: list[dict] = []
    for e in scan(col, proj):
        entries.append(e)
        for ex in e.get("examples") or []:
            corpus.add(ex if isinstance(ex, str) else (ex or {}).get("chuukese") or "")
        if args.limit and len(entries) >= args.limit:
            break
    log(f"Loaded {len(entries)} dictionary entries")

    def score_entry(e: dict, with_prior: bool = True) -> tuple[str, float, list[str], Counter]:
        s, notes = entry_evidence(e, with_prior)
        chk = (e.get("chuukese_word") or "").split("→")[-1].strip()
        if len(tokens(chk)) == 1:
            cs, cnotes = corpus.evidence(chk)
            s.update(cs)
            notes += cnotes
        label, conf = decide(s)
        return label, conf, notes, s

    results: dict = {}
    for e in entries:
        results[e["_id"]] = score_entry(e)

    # 3. wol.jw.org for the uncertain single words
    uncertain = [e for e in entries if results[e["_id"]][1] < 0.55 and len(tokens((e.get("chuukese_word") or "").split("→")[-1])) == 1 and len(norm(e.get("chuukese_word") or "")) >= 3 and not human_set(e)]
    uncertain.sort(key=lambda e: (corpus.count.get(norm(e.get("chuukese_word") or ""), 0), -len(e.get("english_translation") or "")))
    log(f"Uncertain after local evidence: {len(uncertain)}")
    wol_done = 0
    if not args.no_wol and args.wol_cap > 0 and uncertain:
        fetcher = PoliteFetcher(min_interval=args.min_interval, jitter=2.0, max_requests=args.wol_cap)
        searcher = WOLSearch()
        seen_words: set[str] = set()
        for e in uncertain:
            if fetcher.requests_made >= args.wol_cap:
                break
            word = (e.get("chuukese_word") or "").split("→")[-1].strip()
            if norm(word) in seen_words:
                continue
            seen_words.add(norm(word))
            from urllib.parse import quote  # noqa: PLC0415
            url = WOL_SEARCH.format(lang="chk") + f"?q={quote(word)}"
            try:
                html = fetcher.get(url)
            except RuntimeError as ex:
                log(f"  wol.jw.org stopped: {ex}")
                break
            except Exception as ex:  # noqa: BLE001
                log(f"  wol.jw.org error for {word!r}: {ex}")
                break
            if not html or not html.strip():
                log("  wol.jw.org answered with an empty page (declining automated requests); stopping the WOL step")
                break
            n = corpus.wol_contexts(word, html, searcher)
            wol_done += 1
            results[e["_id"]] = score_entry(e)
            label, conf = results[e["_id"]][:2]
            log(f"  wol {wol_done}/{args.wol_cap}: {word!r} → {n} sentences → {label} ({conf})")
        log(f"wol.jw.org: {fetcher.requests_made} requests, {fetcher.cache_hits} from cache")
    # Any word whose contexts grew through another word's page benefits too.
    for e in entries:
        results[e["_id"]] = score_entry(e)

    # 4. decide writes
    now = datetime.now(timezone.utc)
    changes, disagreements, unknown, kept = [], [], [], 0
    rows_out = []
    for e in entries:
        label, conf, notes, s = results[e["_id"]]
        current = e.get("grammar")
        cur_simple = simple_of(current, e.get("grammar_modifier"))
        locked = human_set(e)
        action = "keep"
        if label == "unknown":
            action = "unknown"
            unknown.append(e)
        elif locked:
            action = "locked" if cur_simple != label else "keep"
        elif cur_simple is None and conf >= args.apply_threshold:
            action = "set"
            changes.append((e, label, conf))
        elif cur_simple is not None:
            # Would the evidence alone, without the current label's weight, pick something else?
            ev_label, ev_conf, ev_notes, _ = score_entry(e, with_prior=False)
            if ev_label not in ("unknown", cur_simple) and ev_conf >= 0.6 and len(ev_notes) >= 2:
                action = "disagree"
                disagreements.append((e, ev_label, ev_conf))
                notes = ev_notes
            else:
                kept += 1
        rows_out.append({"chuukese": e.get("chuukese_word", ""), "english": e.get("english_translation", ""), "current": current or "", "modifier": e.get("grammar_modifier") or "",
                         "label": label, "confidence": conf, "action": action, "evidence": "; ".join(notes)})
        if not args.dry_run:
            review = {"label": label, "confidence": conf, "evidence": notes[:12], "previous": current, "at": now, "run": RUN_TAG}
            update = {"$set": {"grammar_review": review}}
            if action == "set":
                update["$set"]["grammar"] = label
                update["$set"]["grammar_previous"] = current
                update["$set"]["grammar_set_by"] = RUN_TAG
            retry(lambda: col.update_one({"_id": e["_id"]}, update))
            time.sleep(0.03)

    # 5. report
    csv_path = LOG_DIR / f"grammar_review_{TODAY}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["chuukese", "english", "current", "modifier", "label", "confidence", "action", "evidence"])
        w.writeheader()
        w.writerows(rows_out)
    label_counts = Counter(r["label"] for r in rows_out)
    md = [f"# Grammar review {now:%Y-%m-%d}", "",
          f"Entries: {len(entries)} · corpus sentences: {corpus.sentences} · wol.jw.org pages: {wol_done} · {'DRY RUN' if args.dry_run else 'written'}", "",
          "## Labels", ""] + [f"- {k}: {v}" for k, v in label_counts.most_common()] + ["",
          f"## Set (label was missing or not simple): {len(changes)}", ""] + [f"- {e.get('chuukese_word')} = {e.get('english_translation')} → **{l}** ({c}); was {e.get('grammar')!r}" for e, l, c in changes[:400]] + ["",
          f"## Disagreements (not applied, please check): {len(disagreements)}", ""] + [f"- {e.get('chuukese_word')} = {e.get('english_translation')}: has {e.get('grammar')!r}, evidence says **{l}** ({c})" for e, l, c in disagreements[:400]] + ["",
          f"## No evidence: {len(unknown)}", ""] + [f"- {e.get('chuukese_word')} = {e.get('english_translation')}" for e in unknown[:200]] + ["",
          f"Kept as is: {kept}. Full detail: {csv_path.name}"]
    md_path = LOG_DIR / f"grammar_review_{TODAY}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    log(f"Done. Set {len(changes)}, disagreements {len(disagreements)}, unknown {len(unknown)}, kept {kept}. Report: {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
