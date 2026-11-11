"""Verb lookup: object suffix rules, attestation, clause detection, route."""
from __future__ import annotations

from unittest.mock import MagicMock

import app as app_module  # noqa: F401  (imported before conftest patches `open`, like the other route tests)
from src.core import verb_forms as vf


def test_candidates_for_ei_stem():
    c = vf.candidates("tongei")
    assert c["me"][0] == "tongeei"
    assert c["you"][0] == "tongeek"
    assert c["us_incl"] == ["tongeikich"]
    assert c["them"][0] == "tongeir"


def test_candidates_for_i_stem():
    c = vf.candidates("álisi")
    assert c["me"][0] == "álisiei"
    assert "álisuk" in c["you"]
    assert c["them"][0] == "álisiir"
    assert c["him"] == ["álisi"]


def test_object_series_prefers_attested_forms():
    related = [
        {"chuukese_word": "álisuk", "english_translation": "help you", "grammar": "verb"},
        {"chuukese_word": "álisikich", "english_translation": "helps us", "grammar": "verb"},
        {"chuukese_word": "attauwei → attauweiei", "english_translation": "caught fish for me"},
    ]
    rows = {r["object"]: r for r in vf.object_series("álisi", related)}
    assert rows["you"]["form"] == "álisuk" and rows["you"]["attested"] and rows["you"]["gloss"] == "help you"
    assert rows["us_incl"]["form"] == "álisikich" and rows["us_incl"]["attested"]
    assert rows["me"]["form"] == "álisiei" and not rows["me"]["attested"]
    assert rows["him"]["form"] == "álisi"


def test_arrow_entries_name_the_derived_form():
    rows = {r["object"]: r for r in vf.object_series("attauwei", [{"chuukese_word": "attauwei → attauweiei", "english_translation": "caught fish for me"}])}
    assert rows["me"]["form"] == "attauweiei" and rows["me"]["attested"]


def test_subject_table_has_seven_persons_and_seven_tenses():
    t = vf.subject_table("álisi")
    assert len(t) == 7 and all(len(r["cells"]) == 7 for r in t)
    assert t[0]["cells"][0]["chuukese"] == "ua álisi"
    assert t[2]["cells"][1]["chuukese"] == "epwe álisi"
    assert t[6]["cells"][3]["chuukese"] == "rese álisi"


def test_find_clause_detects_marker_aspect_and_form():
    pat = vf.clause_pattern(["álisikich", "álisi"])
    hit = vf.find_clause("Áwewe chék, eli sia fen tingorei Jiowa an epwe álisikich.", pat)
    assert hit["marker"] == "epwe" and hit["person"] == "3s" and hit["tense"] == "future" and hit["form"] == "álisikich"
    hit = vf.find_clause("Jiowa a fen álisi ekkewe aramas", pat)
    assert hit["marker"] == "a" and hit["aspect"] == "fen"
    # "ach álisi" is a possessive, not a subject marker
    assert vf.find_clause("ach álisi", pat) is None
    # The marker must be a whole word: "ra" inside "Jiowa" does not count.
    assert vf.find_clause("Jiowaálisi", pat) is None


def test_examples_from_db_keeps_only_marker_plus_verb():
    db = MagicMock()
    db.phrases_collection.find.return_value.limit.return_value = [
        {"chuukese_phrase": "Ua álisi ewe mwán.", "english_translation": "I helped the man."},
        {"chuukese_phrase": "Án álisi a múrinné.", "english_translation": "His help is good."},
    ]
    db.db.__getitem__.return_value.find.return_value.limit.return_value = []
    db.dictionary_collection.find.return_value.limit.return_value = []
    ex = vf.examples_from_db(db, ["álisi"])
    assert [e["chk"] for e in ex] == ["Ua álisi ewe mwán."]
    assert ex[0]["person"] == "1s" and ex[0]["source"] == "library"


def test_lookup_without_db_still_forms_the_series():
    r = vf.lookup(None, "tongei")
    assert r["found"] is False and r["verb"] == "tongei"
    assert len(r["subjects"]) == 7 and len(r["objects"]) == 7 and r["examples"] == []


def _client(monkeypatch, db):
    monkeypatch.setattr(app_module, "dict_db", db)
    app_module.app.config["TESTING"] = True
    c = app_module.app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["user_email"] = "test@example.com"
    return c


def test_lookup_route_requires_query(monkeypatch):
    c = _client(monkeypatch, MagicMock())
    assert c.get("/api/verbs/lookup").status_code == 400


def test_lookup_route_returns_series(monkeypatch):
    db = MagicMock()
    db.dictionary_collection.find.return_value.limit.return_value = [
        {"chuukese_word": "tongei", "english_translation": "to love", "grammar": "verb", "grammar_modifier": "transitive"},
        {"chuukese_word": "tongeek", "english_translation": "love you", "grammar": "verb"},
    ]
    db.phrases_collection.find.return_value.limit.return_value = []
    db.db.__getitem__.return_value.find.return_value.limit.return_value = []
    c = _client(monkeypatch, db)
    r = c.get("/api/verbs/lookup?q=tongei")
    assert r.status_code == 200
    d = r.get_json()
    assert d["found"] and d["english"] == "to love"
    you = next(o for o in d["objects"] if o["object"] == "you")
    assert you["form"] == "tongeek" and you["attested"]


def test_english_query_offers_chuukese_words():
    db = MagicMock()
    rows = [
        {"chuukese_word": "lamot", "english_translation": "important, need", "grammar": "adjective"},
        {"chuukese_word": "osun", "english_translation": "in need of, require, lack", "grammar": "verb", "grammar_modifier": "or adjective"},
        {"chuukese_word": "tikek", "english_translation": "needle (sewing)", "grammar": "noun"},
        {"chuukese_word": "Ren ach sipwe lúkúlúk", "english_translation": "we need to be balanced", "grammar": ""},
    ]
    db.dictionary_collection.find.return_value.limit.return_value = rows
    m = vf.english_matches(db.dictionary_collection, "need")
    assert [x["chuukese"] for x in m] == ["osun", "lamot"]  # verb first; 'needle' and the sentence are left out
    db.phrases_collection.find.return_value.limit.return_value = []
    db.db.__getitem__.return_value.find.return_value.limit.return_value = []
    r = vf.lookup(db, "need")
    assert r["matches"][0]["chuukese"] == "osun" and r["verb"] in ("osun", "lamot")
