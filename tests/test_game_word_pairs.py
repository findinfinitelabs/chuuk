"""
Word pairs saved from the Translation Game feed the dictionary that glosses the
next article. These tests cover the round trip: a pair linked as "Jeremaia,"
is stored as "Jeremaia", the article it came from is recorded on the entry,
and a later lookup of the word finds it with its translation and appearances.
"""
from __future__ import annotations

import re

import pytest


class FakeCollection:
    def __init__(self, field, rows=None):
        self.field = field
        self.rows = list(rows or [])
        self.updates: list[tuple] = []

    def _matches(self, row, query):
        for key, cond in (query or {}).items():
            value = row.get(key)
            if isinstance(cond, dict) and "$in" in cond:
                if value not in cond["$in"]:
                    return False
            elif isinstance(cond, dict) and "$regex" in cond:
                if not re.match(cond["$regex"], str(value or ""), re.I):
                    return False
            elif value != cond:
                return False
        return True

    def find(self, query=None, projection=None):
        return iter([dict(r) for r in self.rows if self._matches(r, query)])

    def find_one(self, query=None, projection=None):
        for r in self.rows:
            if self._matches(r, query):
                return dict(r)
        return None

    def insert_one(self, doc):
        doc = dict(doc)
        doc.setdefault("_id", f"id{len(self.rows)}")
        self.rows.append(doc)

    def update_one(self, query, update):
        for r in self.rows:
            if self._matches(r, query):
                r.update(update.get("$set", {}))
                self.updates.append((query, update))
                return


class FakeDB:
    def __init__(self):
        self.dictionary_collection = FakeCollection(
            "chuukese_word",
            [
                {"_id": "d1", "chuukese_word": "tongei", "english_translation": "to love", "grammar": "verb"},
                {"_id": "d2", "chuukese_word": "Jiowa", "english_translation": "Jehovah", "grammar": "noun",
                 "game_appearances": [{"article_id": "a1", "title": "Old article", "url": "", "english": "Jehovah is love."}]},
            ],
        )
        self.phrases_collection = FakeCollection(
            "chuukese_phrase", [{"_id": "p1", "chuukese_phrase": "kilisou", "english_translation": "thank you"}]
        )
        self.words_collection = FakeCollection("chuukese", [])


@pytest.fixture()
def fake_db(monkeypatch, flask_app):
    import app

    db = FakeDB()
    monkeypatch.setattr(app, "dict_db", db)
    # The similarity index is cached for five minutes; rebuild it from the fake.
    monkeypatch.setattr(app, "_similar_index_cache", {"index": None, "timestamp": None})
    return db


class TestCleanHeadword:
    def test_strips_surrounding_punctuation(self):
        from app import _clean_headword

        assert _clean_headword("Jeremaia,") == "Jeremaia"
        assert _clean_headword('“ewe') == "ewe"
        assert _clean_headword("(aramas)") == "aramas"
        assert _clean_headword("  Jiowa   Kot. ") == "Jiowa Kot"

    def test_keeps_accents_and_inner_apostrophes(self):
        from app import _clean_headword

        assert _clean_headword("pwáseló!") == "pwáseló"
        assert _clean_headword("1914") == "1914"


class TestAppearanceUpdate:
    def test_adds_newest_first_and_skips_repeat(self):
        from app import _appearance_update

        old = [{"article_id": "a1", "english": "one"}]
        new = {"article_id": "a2", "english": "two"}
        assert _appearance_update(old, new) == [new, old[0]]
        assert _appearance_update(old, {"article_id": "a1", "english": "one"}) is None
        assert _appearance_update(old, None) is None


class TestLookupCarriesAppearances:
    def test_entry_reports_where_it_was_matched(self, fake_db):
        from app import _lookup_words_bulk

        got = _lookup_words_bulk({"jiowa"})
        assert got["jiowa"]["english"] == "Jehovah"
        assert got["jiowa"]["appearances"][0]["title"] == "Old article"

    def test_confirmed_row_beats_imported_row(self):
        from app import _wol_entry_rank

        imported = {"english_translation": "love", "confidence_score": 100}
        confirmed = {"english_translation": "to love", "confidence_score": 100, "user_confirmed": True}
        assert _wol_entry_rank(confirmed) > _wol_entry_rank(imported)


class TestSaveWordPairs:
    def test_new_word_is_stored_clean_with_its_article(self, client, fake_db):
        res = client.post(
            "/api/brochures/match/words",
            json={
                "word_pairs": [{"chuukese": "Jeremaia,", "english": "Jeremiah", "grammar": "noun"}],
                "article_id": "abc",
                "article_title": "Lessons from Jeremiah",
                "article_url": "https://wol.jw.org/chk/x",
                "english_text": "Jeremiah was faithful.",
            },
        )
        assert res.status_code == 201
        body = res.get_json()
        assert body["saved"] == ["Jeremaia"]
        row = fake_db.dictionary_collection.find_one({"chuukese_word": "Jeremaia"})
        assert row["english_translation"] == "Jeremiah"
        assert row["user_confirmed"] is True
        assert row["game_appearances"][0]["title"] == "Lessons from Jeremiah"
        # The response carries the gloss entry the client merges into its maps.
        assert body["dictionary"]["jeremaia"]["english"] == "Jeremiah"
        assert body["dictionary"]["jeremaia"]["appearances"][0]["article_id"] == "abc"

    def test_known_word_gains_a_sense_and_an_appearance(self, client, fake_db):
        res = client.post(
            "/api/brochures/match/words",
            json={
                "word_pairs": [{"chuukese": "tongei", "english": "cherish", "grammar": "verb"}],
                "article_id": "a9",
                "article_title": "New article",
                "english_text": "They cherish them.",
            },
        )
        assert res.status_code == 201
        assert res.get_json()["updated"] == ["tongei"]
        row = fake_db.dictionary_collection.find_one({"chuukese_word": "tongei"})
        assert row["english_translation"] == "to love; cherish"
        assert [a["article_id"] for a in row["game_appearances"]] == ["a9"]

    def test_same_sentence_is_not_recorded_twice(self, client, fake_db):
        payload = {
            "word_pairs": [{"chuukese": "Jiowa", "english": "Jehovah"}],
            "article_id": "a1",
            "article_title": "Old article",
            "english_text": "Jehovah is love.",
        }
        client.post("/api/brochures/match/words", json=payload)
        row = fake_db.dictionary_collection.find_one({"chuukese_word": "Jiowa"})
        assert len(row["game_appearances"]) == 1

    def test_word_held_in_phrases_is_updated_there_not_duplicated(self, client, fake_db):
        client.post("/api/brochures/match/words", json={"word_pairs": [{"chuukese": "Kilisou!", "english": "grateful"}]})
        assert fake_db.dictionary_collection.find_one({"chuukese_word": "Kilisou"}) is None
        row = fake_db.phrases_collection.find_one({"chuukese_phrase": "kilisou"})
        assert row["english_translation"] == "thank you; grateful"

    def test_same_meaning_in_other_words_does_not_add_a_sense(self, client, fake_db):
        client.post("/api/brochures/match/words", json={"word_pairs": [{"chuukese": "tongei", "english": "loves"}]})
        row = fake_db.dictionary_collection.find_one({"chuukese_word": "tongei"})
        assert row["english_translation"] == "to love"

    def test_numbers_pair_but_are_not_headwords(self, client, fake_db):
        res = client.post("/api/brochures/match/words", json={"word_pairs": [{"chuukese": "1914", "english": "1914"}]})
        assert res.get_json()["skipped"] == ["1914"]
        assert fake_db.dictionary_collection.find_one({"chuukese_word": "1914"}) is None


class TestLookupWordPairs:
    def test_returns_gloss_maps_for_the_modal(self, client, fake_db):
        res = client.get("/api/brochures/match/words", query_string={"chuukese_tokens": "Jeremaia,,tongei,tongeni,13"})
        assert res.status_code == 200
        body = res.get_json()
        assert body["dictionary"]["tongei"]["english"] == "to love"
        assert [p["chuukese"] for p in body["pairs"]] == ["tongei"]
        # Unknown inflection points at the base entry we hold, with its grammar.
        assert any(h["word"] == "tongei" and h["grammar"] == "verb" for h in body["similar"]["tongeni"])
        assert "13" not in body["dictionary"]


class TestCleanHeadwordInMergeModule:
    def test_shared_with_scripts(self):
        from src.core.dictionary_merge import clean_headword

        assert clean_headword('"ewe Kot.') == "ewe Kot"
        assert clean_headword("(Jer 48:27, 29, 42;") == "Jer 48:27, 29, 42"
        assert clean_headword(None) == ""

    def test_english_senses_are_cleaned_and_collapsed(self):
        from src.core.dictionary_merge import clean_senses, merge_senses

        assert clean_senses("(1 min.)") == "1 min"
        assert clean_senses("Moab; “Moab”") == "Moab"
        assert clean_senses("to love; cherish") == "to love; cherish"
        # Quotes never make a new sense when saving either.
        assert merge_senses("Moab", "“Moab”") == "Moab"


class TestPhrases:
    def _index(self):
        from app import _index_phrase

        phrases: dict = {}
        _index_phrase(phrases, "ewe Kot", {"english_translation": "the God", "grammar": "phrase"})
        _index_phrase(phrases, "ewe Kot mi tong", {"english_translation": "the God is love"})
        _index_phrase(phrases, "Ewe aramas mi chok tongei ekkewe aramas meinisin", {"english_translation": "x"})  # too long
        _index_phrase(phrases, "ewe Kot", {"english_translation": "", "type": "sentence"})  # sentences never
        return phrases

    def test_index_keeps_short_phrases_only(self):
        phrases = self._index()
        assert set(phrases) == {"ewe kot", "ewe kot mi tong"}
        assert phrases["ewe kot"]["words"] == ["ewe", "kot"]
        assert phrases["ewe kot"]["text"] == "ewe Kot"

    def test_found_as_consecutive_words_not_across_a_boundary(self):
        from app import _find_phrases

        phrases = self._index()
        assert set(_find_phrases("A sipwe tongei ewe Kot, pun i mi tong.", phrases)) == {"ewe kot"}
        assert set(_find_phrases("Ewe Kot mi tong ngenikich.", phrases)) == {"ewe kot", "ewe kot mi tong"}
        assert _find_phrases("ra chok ewe. Kot a tong.", phrases) == {}
        assert _find_phrases("", phrases) == {}

    def test_attach_dictionary_reports_phrases_in_the_text(self, fake_db):
        import app

        fake_db.dictionary_collection.rows.append(
            {"_id": "d3", "chuukese_word": "ewe Kot", "english_translation": "the God", "grammar": "phrase"}
        )
        payload = app._attach_dictionary({"results": [{"text": "A tongei ewe Kot."}]})
        assert payload["phrases"]["ewe kot"]["english"] == "the God"

    def test_saving_a_phrase_pair_returns_it_and_refreshes_the_index(self, client, fake_db):
        import app

        app._get_similarity_index()  # warm the cache
        res = client.post("/api/brochures/match/words", json={"word_pairs": [{"chuukese": "ewe Kot,", "english": "the God"}]})
        body = res.get_json()
        assert body["saved"] == ["ewe Kot"]
        assert body["phrases"]["ewe kot"]["english"] == "the God"
        assert app._similar_index_cache["index"] is None  # rebuilt on the next article


class TestSavedMatchesComeBackOnFetch:
    def test_matches_of_an_article_in_restore_shape(self, fake_db):
        import app

        class Cursor:
            def __init__(self, rows):
                self.rows = rows

            def sort(self, *_a):
                return iter(self.rows)

        class Matches:
            def find(self, query, projection=None):
                assert query == {"article_id": "art1"}
                return Cursor([{"english_id": 3, "chuukese_ids": [4, 5], "english_text": "Hi", "was_edited": False, "word_pairs": []}])

        fake_db.db = {"brochure_matches": Matches()}
        got = app._game_article_matches("art1")
        assert got == [{"english_id": 3, "chuukese_ids": [4, 5], "english_text": "Hi", "was_edited": False, "word_pairs": []}]
        assert app._game_article_matches("") == []
