"""A checked Talk Builder line is stored as a verified word, phrase or sentence."""

from unittest.mock import MagicMock

import app as app_module


def _db():
    db = MagicMock()
    db.phrases_collection.find_one.return_value = None
    db.dictionary_collection.insert_one.return_value = MagicMock(inserted_id="x")
    return db


def test_sentence_and_phrase_go_to_the_phrase_library(monkeypatch):
    db = _db()
    monkeypatch.setattr(app_module, "dict_db", db)
    out = app_module._store_verified_pair("Ewe lúkúlúk mi enlet esap wewemang.", "True faith is not gullibility.", "talk_builder", "w12 11/1 23", "CL")
    assert out == {"stored": True, "kind": "sentence", "updated": False}
    doc = db.phrases_collection.insert_one.call_args.args[0]
    assert doc["verified"] and doc["confidence_score"] == 100 and doc["type"] == "sentence" and doc["reference"] == "w12 11/1 23"
    out = app_module._store_verified_pair("kapas eis", "question", "talk_builder")
    assert out["kind"] == "phrase"


def test_rechecking_the_same_chuukese_updates_instead_of_duplicating(monkeypatch):
    db = _db()
    db.phrases_collection.find_one.return_value = {"_id": "phrase_1", "chuukese_phrase": "kapas eis", "english_translation": "a question"}
    monkeypatch.setattr(app_module, "dict_db", db)
    out = app_module._store_verified_pair("Kapas eis", "question", "talk_builder")
    assert out == {"stored": True, "kind": "phrase", "updated": True}
    db.phrases_collection.insert_one.assert_not_called()
    update = db.phrases_collection.update_one.call_args.args[1]["$set"]
    assert update["english_translation"] == "question" and update["verified"]


def test_single_word_marks_the_dictionary_headword_verified(monkeypatch):
    db = _db()
    monkeypatch.setattr(app_module, "dict_db", db)
    coll = MagicMock()
    monkeypatch.setattr(app_module, "_find_headword", lambda w: (coll, "chuukese_word", {"_id": "d1", "english_translation": "faith"}))
    out = app_module._store_verified_pair("lúkúlúk", "faith, trust", "talk_builder")
    assert out == {"stored": True, "kind": "word", "updated": True}
    update = coll.update_one.call_args.args[1]["$set"]
    assert update["english_translation"] == "faith; faith, trust" and update["confidence_score"] == 100
