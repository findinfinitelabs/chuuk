"""Tests for the sentence / article analysis rebuild.

Pure helpers in src.core.sentence_analysis, then the Flask routes with the
dictionary layer patched: no database, model or network access.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.core import sentence_analysis as sa

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_norm_word_strips_accents_and_case():
    assert sa.norm_word("Pwáseló") == "pwaselo"
    assert sa.norm_word("ÁÉÚ") == "aeu"


def test_word_keys_drops_numbers_and_lowercases():
    assert sa.word_keys("Jiowa a tongei 12 aramas.") == {"jiowa", "a", "tongei", "aramas"}


def test_accent_variants_only_for_unknown_words_with_different_accents():
    by_norm = {"pwaselo": {"pwáseló", "pwaselo"}, "tongei": {"tongei"}}
    known = {"tongei": {"english": "love"}}
    out = sa.accent_variants({"pwaselo", "tongei", "foo"}, known, by_norm)
    # 'pwaselo' itself is not a variant of 'pwaselo'; only the accented headword is.
    assert out == {"pwaselo": ["pwáseló"]}


@pytest.mark.parametrize(
    "english, grammar",
    [
        ("to love", "verb"),
        ("he, him", "pronoun"),
        ("quickly", "adverb"),
        ("in, at", "preposition"),
        ("happiness", "noun"),
        ("", ""),
    ],
)
def test_suggest_grammar(english, grammar):
    assert sa.suggest_grammar(english) == grammar


def test_wol_pairs_keeps_only_results_with_english():
    results = [{"text": "a", "link": "l1"}, {"text": "b", "link": "l2"}]
    english = [{"text": "A", "scope": "sentence", "link": "e1"}, None]
    pairs = sa.wol_pairs(results, english)
    assert len(pairs) == 1
    assert pairs[0]["chk"] == "a" and pairs[0]["en"] == "A" and pairs[0]["english_link"] == "e1"


def test_build_proposal_prefers_accent_variant():
    p = sa.build_proposal(
        "pwaselo",
        variants=[{"headword": "pwáseló", "english": "to be lost", "grammar": "verb", "definition": "d"}],
        similar=[],
        rend=[{"stem": "forgiv", "word": "forgive", "count": 3}],
        model_word="forgive",
    )
    assert p["english"] == "to be lost"
    assert p["grammar"] == "verb"
    assert p["source"] == "accent_variant"


def test_build_proposal_falls_back_to_wol_then_model():
    rend = [{"stem": "forgiv", "word": "forgive", "count": 3}]
    p = sa.build_proposal("omusalo", [], [{"word": "omus", "english": "forgive", "grammar": "verb"}], rend, "pardon")
    assert p["english"] == "forgive"
    assert p["source"] == "wol"
    assert p["grammar"] == "verb"  # from the related entry

    p = sa.build_proposal("omusalo", [], [], [], "to pardon", context_english="He will pardon them.")
    assert p["english"] == "to pardon"
    assert p["source"] == "model"
    assert p["confirmed_in_context"] is True


def test_build_proposal_ignores_echoed_or_sentence_length_gloss():
    p = sa.build_proposal("foo", [], [], [], "Foo")
    assert p["english"] == "" and p["model_gloss"] == ""
    p = sa.build_proposal("foo", [], [], [], "this is a very long sentence that is not a gloss at all")
    assert p["english"] == ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@pytest.fixture()
def mod():
    """The app module, imported once with the database mocked. Importing
    app.py is slow and other test files share the module, so the database
    attributes these tests set are restored afterwards."""
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault("COSMOS_DB_CONNECTION_STRING", "")
    if "app" in sys.modules:
        flask_module = sys.modules["app"]
    else:
        with patch("src.database.dictionary_db.DictionaryDB", return_value=MagicMock(db=None)):
            import app as flask_module  # noqa: PLC0415
    if flask_module.dict_db is None:
        flask_module.dict_db = MagicMock(db=None)
    db = flask_module.dict_db
    saved = {name: getattr(db, name, None) for name in ("db", "dictionary_collection", "phrases_collection", "_normalize_grammar")}
    yield flask_module
    for name, value in saved.items():
        setattr(db, name, value)


def _login(client, role="admin"):
    with client.session_transaction() as session:
        session["logged_in"] = True
        session["user_email"] = "test@example.com"
        session["user_role"] = role


INDEX = {
    "by_norm": {"pwaselo": {"pwáseló"}, "tongei": {"tongei"}, "jiowa": {"Jiowa"}},
    "by_prefix": {"ton": [("tongei", "tongei")]},
    "english": {"tongei": "to love", "tongen": "love (n.)", "pwáseló": "to be lost"},
    "grammar": {"tongei": "verb"},
    "phrases": {},
}


def _bulk(words):
    """Stand-in for the Cosmos bulk lookup."""
    table = {
        "jiowa": {"entry_id": "1", "source": "dictionary", "english": "Jehovah", "grammar": "noun", "grammar_modifier": None, "definition": "", "status": "translated", "verified": True, "appearances": []},
        "tongei": {"entry_id": "2", "source": "dictionary", "english": "to love", "grammar": "verb", "grammar_modifier": None, "definition": "", "status": "translated", "verified": False, "appearances": []},
        "pwáseló": {"entry_id": "3", "source": "dictionary", "english": "to be lost", "grammar": "verb", "grammar_modifier": None, "definition": "", "status": "translated", "verified": False, "appearances": []},
    }
    return {w.lower(): table[w.lower()] for w in words if w.lower() in table}


def test_analyze_sentence_reports_accent_variants_and_similar(mod):
    client = mod.app.test_client()
    _login(client)
    with patch.object(mod, "_lookup_words_bulk", side_effect=_bulk), patch.object(mod, "_get_similarity_index", return_value=INDEX):
        res = client.post("/api/sentences/analyze", json={"sentence": "Jiowa a tongei pwaselo tongen."})
    assert res.status_code == 200
    body = res.get_json()
    assert [w["word"] for w in body["words"]] == ["Jiowa", "a", "tongei", "pwaselo", "tongen"]
    # Known as-is.
    assert body["dictionary"]["tongei"]["english"] == "to love"
    # Known under a different accent spelling: returned as that entry, flagged.
    assert body["dictionary"]["pwaselo"]["variant_of"] == "pwáseló"
    assert body["dictionary"]["pwaselo"]["english"] == "to be lost"
    # Unknown, with related entries by stem.
    assert "tongen" not in body["dictionary"]
    assert [s["word"] for s in body["similar"]["tongen"]] == ["tongei"]
    # Truly unknown with nothing similar: absent from both.
    assert "a" not in body["dictionary"] and "a" not in body["similar"]


def test_analyze_sentence_requires_login_and_text(mod):
    client = mod.app.test_client()
    assert client.post("/api/sentences/analyze", json={"sentence": "x"}).status_code == 401
    _login(client)
    assert client.post("/api/sentences/analyze", json={"sentence": "   "}).status_code == 400


def test_suggest_queue_files_a_new_word_review(mod):
    client = mod.app.test_client()
    _login(client, role="user")
    col = MagicMock()
    mod.dict_db.db = {"translation_reviews": col}
    res = client.post(
        "/api/sentences/suggest/queue",
        json={"word": "omusalo", "english": "forgive", "grammar": "verb", "sentence": "A omusalo.", "evidence": {"source": "wol", "pairs": [{"chk": "A omusalo.", "en": "He forgave."}]}},
    )
    assert res.status_code == 200
    flt, update = col.update_one.call_args.args
    assert flt == {"kind": "new_word", "headword": "omusalo", "status": "pending"}
    doc = update["$set"]
    assert doc["proposed"]["english_translation"] == "forgive"
    assert doc["proposed"]["grammar"] == "verb"
    assert doc["evidence"]["pair_count"] == 1
    assert doc["proposed_by"] == "test@example.com"
    assert col.update_one.call_args.kwargs == {"upsert": True}


def test_suggest_queue_requires_english(mod):
    client = mod.app.test_client()
    _login(client)
    mod.dict_db.db = {"translation_reviews": MagicMock()}
    assert client.post("/api/sentences/suggest/queue", json={"word": "x"}).status_code == 400


def test_apply_new_word_review_inserts_entry(mod):
    collection = MagicMock()
    collection.find_one.return_value = None
    collection.insert_one.return_value = MagicMock(inserted_id="new-id")
    mod.dict_db.dictionary_collection = collection
    mod.dict_db._normalize_grammar = lambda g: g
    review = {"_id": "r1", "kind": "new_word", "headword": "omusalo", "proposed_by": "someone@example.com"}
    applied = mod._apply_review(review, {"english_translation": "forgive", "grammar": "verb", "example": "A omusalo."}, "admin@example.com")
    assert applied["entry_id"] == "new-id"
    entry = collection.insert_one.call_args.args[0]
    assert entry["chuukese_word"] == "omusalo"
    assert entry["english_translation"] == "forgive"
    assert entry["examples"] == ["A omusalo."]
    assert entry["added_by"] == "someone@example.com"
    assert entry["history"][0]["review_id"] == "r1"


def test_apply_new_word_review_updates_existing_headword(mod):
    collection = MagicMock()
    collection.find_one.return_value = {"_id": "old", "english_translation": "", "grammar": "", "definition": ""}
    mod.dict_db.dictionary_collection = collection
    mod.dict_db._normalize_grammar = lambda g: g
    review = {"_id": "r2", "kind": "new_word", "headword": "omusalo"}
    applied = mod._apply_review(review, {"english_translation": "forgive"}, "admin@example.com")
    assert applied["entry_id"] == "old"
    collection.insert_one.assert_not_called()
    flt, update = collection.update_one.call_args.args
    assert flt == {"_id": "old"}
    assert update["$set"]["english_translation"] == "forgive"
    assert update["$push"]["history"]["before"] == {"english_translation": "", "grammar": "", "definition": ""}


# ---------------------------------------------------------------------------
# Exact source on wol.jw.org
# ---------------------------------------------------------------------------


def test_clean_for_search_drops_citations_and_edge_punctuation():
    assert sa.clean_for_search("“Iwe, Jiowa esap pwapwa. (Jer. 48:31-36)”") == "Iwe Jiowa esap pwapwa"


def test_source_queries_whole_sentence_then_windows():
    short = sa.source_queries("Jiowa a tongei aramas.")
    assert short == ['"Jiowa a tongei aramas"']
    long = sa.source_queries("one two three four five six seven eight nine ten eleven", window=8)
    assert long[0] == '"one two three four five six seven eight nine ten eleven"'
    assert '"one two three four five six seven eight"' in long
    assert '"four five six seven eight nine ten eleven"' in long
    assert len(long) == len(set(long))


def test_source_score_is_accent_insensitive_and_rewards_contiguous_match():
    assert sa.source_score("Jiowa a tongei aramas", "Me met a pwáári pwe Jiowa a tongei aramas meinisin?") == 1.0
    assert sa.source_score("Jiowa a tóngei aramas", "jiowa a tongei aramas") == 1.0
    assert sa.source_score("Jiowa a tongei aramas", "Jises a pwáári ngeni aramas.") < 0.6


def test_pick_source_prefers_exact_text_with_aligned_english():
    results = [
        {"text": "Jiowa a tongei aramas meinisin.", "link": "l1", "citation": "w26"},
        {"text": "A tongei aramas, Jiowa.", "link": "l2", "citation": "w20"},
    ]
    english = [
        {"text": "Jehovah loves all people.", "scope": "sentence", "link": "e1"},
        {"text": "Whole paragraph…", "scope": "paragraph", "link": "e2"},
    ]
    picked = sa.pick_source("Jiowa a tongei aramas meinisin", results, english)
    assert picked["link"] == "l1" and picked["exact"] is True
    assert picked["english"]["text"] == "Jehovah loves all people."
    assert sa.pick_source("Something else entirely here", results, english) is None


def test_source_route_returns_match(mod):
    client = mod.app.test_client()
    _login(client)
    searcher = MagicMock()
    searcher.search.side_effect = [
        {"results": []},
        {"results": [{"text": "Iwe, Jiowa esap pwapwa ren an epwe nieló Moap.", "link": "l", "citation": "w26 7/1"}]},
    ]
    searcher.english_for_many.return_value = [{"text": "Jehovah would not take pleasure in destroying Moab.", "scope": "sentence", "link": "e"}]
    with patch.object(mod, "_get_wol_search", return_value=searcher):
        res = client.post("/api/sentences/source", json={"sentence": "Iwe, Jiowa esap pwapwa ren an epwe nieló Moap. (Jer. 48:31-36)"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["match"]["exact"] is True
    assert body["match"]["english"]["text"].startswith("Jehovah would not")
    assert len(body["queries"]) == 2  # whole sentence missed, first window hit


def test_source_route_no_match(mod):
    client = mod.app.test_client()
    _login(client)
    searcher = MagicMock()
    searcher.search.return_value = {"results": []}
    with patch.object(mod, "_get_wol_search", return_value=searcher):
        res = client.post("/api/sentences/source", json={"sentence": "Ese wor."})
    assert res.status_code == 200 and res.get_json()["match"] is None
    searcher.english_for_many.assert_not_called()


def test_save_pair_writes_confirmed_sentence(mod):
    client = mod.app.test_client()
    _login(client, role="user")
    phrases = MagicMock()
    mod.dict_db.phrases_collection = phrases
    res = client.post(
        "/api/sentences/pairs",
        json={"chuukese": "Jiowa a tongei aramas.", "english": "Jehovah loves people.", "source": "wol.jw.org", "citation": "w26 7/1", "link": "https://wol.jw.org/x"},
    )
    assert res.status_code == 201
    doc = phrases.insert_one.call_args.args[0]
    assert doc["type"] == "sentence" and doc["user_confirmed"] is True and doc["confidence_score"] == 100
    assert doc["chuukese_sentence"] == "Jiowa a tongei aramas." and doc["english_translation"] == "Jehovah loves people."
    assert doc["source"] == "wol.jw.org" and doc["citation"] == "w26 7/1"
    assert doc["_id"].startswith("sentence_")


def test_save_pair_rejects_unknown_source_and_empty_text(mod):
    client = mod.app.test_client()
    _login(client)
    phrases = MagicMock()
    mod.dict_db.phrases_collection = phrases
    assert client.post("/api/sentences/pairs", json={"chuukese": "x"}).status_code == 400
    res = client.post("/api/sentences/pairs", json={"chuukese": "a b", "english": "c d", "source": "evil"})
    assert res.status_code == 201
    assert phrases.insert_one.call_args.args[0]["source"] == "user"
