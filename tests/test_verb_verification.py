"""Verb verification against WOL evidence: renderings, support and proposals."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.verb_verification import (
    Baseline,
    detect_inflection,
    grammar_proposal,
    normalize_modifier,
    renderings,
    stem,
    translation_proposal,
)

PAIRS = [
    {"chk": "Jiowa a apworai Taniel.", "en": "Daniel’s unwavering faith in Jehovah sustained him.", "form": "apworai"},
    {"chk": "A apworai le pennúkú manawan.", "en": "It gave him the courage to risk his life.", "form": "apworai"},
    {"chk": "Ei pwóróus a apworai ekkewe chón mwich.", "en": "This account encouraged the brothers greatly.", "form": "apworai"},
    {"chk": "Repwe apworai fengen.", "en": "They should encourage one another.", "form": "apworai"},
    {"chk": "Met a apworai Paul?", "en": "What encouraged Paul to keep preaching?", "form": "apworai"},
]


def _baseline(extra=()):
    b = Baseline()
    for p in PAIRS:
        b.add(p["en"])
    for s in extra:
        b.add(s)
    return b


def test_stem_groups_inflections():
    assert stem("encouraged") == stem("encouraging") == stem("encourage")
    assert stem("courage") != stem("encourage")


def test_renderings_find_the_recurring_english_word():
    rend = renderings(PAIRS, _baseline(["We help people.", "We help them again."]))
    assert rend[0]["word"] in ("encouraged", "encourage")
    assert rend[0]["count"] == 3


def test_common_corpus_words_are_not_renderings():
    extra = [f"They encourage the brothers {i}" for i in range(40)]
    rend = renderings(PAIRS, _baseline(extra))
    assert all(r["stem"] != stem("encourage") for r in rend)


def test_needs_review_when_current_english_never_appears():
    prop = translation_proposal({"english_translation": "make brave"}, PAIRS, _baseline())
    assert prop["outcome"] == "needs_review"
    assert prop["tier"] == "review"
    # 3 of 5 sentences agree: offered as a suggestion, but the prefilled wording
    # stays the current one until agreement is strong.
    assert prop["evidence"]["suggestions"][0] in ("encouraged", "encourage")
    assert prop["proposed"]["english_translation"] == "make brave"
    assert prop["evidence"]["forms"] == ["apworai"]


def test_confirmed_when_current_english_is_supported():
    prop = translation_proposal({"english_translation": "to encourage"}, PAIRS, _baseline())
    assert prop["outcome"] == "confirmed"
    assert prop["tier"] == "auto"
    assert prop["proposed"] == {"wol_verified": True}


def test_add_senses_when_wol_also_uses_other_words():
    pairs = PAIRS + [
        {"chk": "x", "en": "Her words sustained him through the trial."},
        {"chk": "y", "en": "Prayer sustained the family."},
    ]
    prop = translation_proposal({"english_translation": "encourage"}, pairs, _baseline())
    assert prop["outcome"] == "add_senses"
    assert "sustain" in prop["proposed"]["english_translation"]


def test_insufficient_and_no_evidence():
    assert translation_proposal({"english_translation": "x"}, PAIRS[:2], _baseline())["outcome"] == "insufficient"
    assert translation_proposal({"english_translation": "x"}, [], _baseline())["outcome"] == "no_evidence"


def test_normalize_modifier():
    assert normalize_modifier("pronoun suffix") == "object suffix"
    assert normalize_modifier("transitive + pronoun") == "transitive, object suffix"
    assert normalize_modifier("Transitive") == "transitive"
    assert normalize_modifier(None) is None


def test_detect_inflection_from_definition_and_headword():
    known = {"chchúngú", "echipwanga", "attauwei"}
    assert detect_inflection("echipwangakem", "echipwanga + suffix -kem (1pl excl object)", known) == {
        "base_word": "echipwanga", "suffix": "kem", "kind": "object suffix"}
    assert detect_inflection("attauwei → attauweiei", "attauwei → attauwei + suffix -ei (1sg object (me))", known)["base_word"] == "attauwei"
    assert detect_inflection("chchúngúei", "—", known) == {"base_word": "chchúngú", "suffix": "ei", "kind": "object suffix"}
    assert detect_inflection("faas", "Cause of a fall.", known) is None


def test_grammar_proposal_retags_suffixed_adjective_as_verb():
    entry = {"chuukese_word": "chchúngúei", "grammar": "adjective", "grammar_modifier": None, "definition": "chchúngú + suffix -ei (1sg object (me))"}
    prop = grammar_proposal(entry, {"chchúngú"})
    assert prop["tier"] == "auto"
    assert prop["proposed"]["grammar"] == "verb"
    assert prop["proposed"]["base_word"] == "chchúngú"
    assert prop["proposed"]["grammar_modifier"] == "object suffix"


def test_grammar_proposal_none_when_clean():
    assert grammar_proposal({"chuukese_word": "faas", "grammar": "verb", "grammar_modifier": "transitive", "definition": "x"}, set()) is None


def test_proper_nouns_and_acronyms_are_not_renderings():
    pairs = [
        {"chk": "a", "en": "Satan tried to tempt Jesus, as the LMD shows."},
        {"chk": "b", "en": "We should resist Satan and his tempting offers."},
        {"chk": "c", "en": "Miriam resisted Satan; Satan tempts everyone."},
    ]
    b = Baseline()
    for p in pairs:
        b.add(p["en"])
    words = {r["stem"] for r in renderings(pairs, b, min_count=2)}
    assert "satan" not in words and "miriam" not in words and "lmd" not in words
    assert stem("tempt") in words


def test_strong_agreement_prefills_new_wording():
    pairs = [{"chk": str(i), "en": f"They encouraged the brothers {i}."} for i in range(5)]
    b = Baseline()
    for p in pairs:
        b.add(p["en"])
    b.add("Something else entirely."); b.add("Another unrelated line.")
    prop = translation_proposal({"english_translation": "make brave"}, pairs, b)
    assert prop["outcome"] == "needs_review"
    assert prop["proposed"]["english_translation"] == "encouraged"
