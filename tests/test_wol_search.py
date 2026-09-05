"""Tests for the WOL search parser.

Covers reference parsing, highlight segmentation and subject detection against
markup captured from wol.jw.org. No network access — the sample HTML below is a
trimmed copy of a real result group.
"""

import pytest
from bs4 import BeautifulSoup

from src.core.wol_search import WOLSearch, detect_subject, parse_reference

pytestmark = pytest.mark.unit


# Trimmed from a live search for "chapur".
SAMPLE_HTML = """
<ul class="results resultContentDocument">
  <li class="caption">
    <a class="lnk" href="/chk/wol/d/r303/lp-te/2000884?q=chapur&amp;p=par">
      Ka Fokkun Aucheani An Jiowa Kkewe Kapasen Achechem?
    </a>
    <span class="count">(Fán 6)</span>
  </li>
  <li class="result">
    <ul class="resultItems">
      <li class="searchResult pub-w docId-2000884 pub-w01">
        <article>
          <div class="document">
            <p>Ua fokkun aucheani ir <span class="mk">chapur</span>.</p>
            <p>Ewe sou kol a eani ewe kol: ua tongei ir <span class="mk"><em>chapur</em></span>.</p>
          </div>
        </article>
      </li>
      <li class="ref">w01 4/1 p. 26-31 - Ewe Leenien Mas—2001</li>
    </ul>
  </li>
</ul>
"""


class TestParseReference:
    @pytest.mark.parametrize(
        "raw,pub,year,month,day,pages",
        [
            ("w01 4/1 p. 26-31 - Ewe Leenien Mas—2001", "w01", 2001, 4, 1, "26-31"),
            ("w97 7/1 p. 26-31 - Ewe Leenien Mas—1997", "w97", 1997, 7, 1, "26-31"),
            ("mwb17 February p. 6 - Manawach—2017", "mwb17", 2017, 2, None, "6"),
            ("nwt Föför 1:1-28:31 - Paipelin Ótót Séfé (nwt)", "nwt", None, None, None, None),
        ],
    )
    def test_shapes(self, raw, pub, year, month, day, pages):
        ref = parse_reference(raw)
        assert ref["pub"] == pub
        assert ref["year"] == year
        assert ref["month"] == month
        assert ref["day"] == day
        assert ref["pages"] == pages

    def test_two_digit_years_span_the_century(self):
        # WOL's Chuukese corpus starts in the 1980s, so 90+ means 19xx.
        assert parse_reference("w97 1/1 - x")["year"] == 1997
        assert parse_reference("w08 1/1 - x")["year"] == 2008

    def test_empty(self):
        assert parse_reference("")["year"] is None


class TestSegments:
    def test_parse_extracts_sentences_and_marks_hits(self):
        results = WOLSearch()._parse(SAMPLE_HTML, "chapur")
        assert len(results) == 2

        first = results[0]
        assert first["text"] == "Ua fokkun aucheani ir chapur."
        assert [s["text"] for s in first["segments"] if s["match"]] == ["chapur"]
        assert first["title"].startswith("Ka Fokkun Aucheani")
        assert first["link"] == (
            "https://wol.jw.org/chk/wol/d/r303/lp-te/2000884?q=chapur&p=par"
        )
        assert first["reference"]["year"] == 2001

    def test_hit_nested_in_other_markup_is_still_marked(self):
        # The second snippet wraps the hit in <span class="mk"><em>…</em></span>.
        second = WOLSearch()._parse(SAMPLE_HTML, "chapur")[1]
        assert [s["text"] for s in second["segments"] if s["match"]] == ["chapur"]

    def test_segments_reassemble_into_the_full_sentence(self):
        for result in WOLSearch()._parse(SAMPLE_HTML, "chapur"):
            assert "".join(s["text"] for s in result["segments"]) == result["text"]


class TestDetectSubject:
    @pytest.mark.parametrize(
        "before,subject,tense,kind",
        [
            ("Iwe ua", "I", "Past/Present", "pronoun"),
            ("ekkewe chon ra", "they", "Past/Present", "pronoun"),
            ("Nge epwe", "he/she/it", "Future", "pronoun"),
            ("kich sipwe", "we (incl.)", "Future", "pronoun"),
        ],
    )
    def test_subject_markers(self, before, subject, tense, kind):
        got = detect_subject(before)
        assert got["subject"] == subject
        assert got["tense"] == tense
        assert got["kind"] == kind

    def test_standalone_pronoun_is_reported_alongside_the_marker(self):
        got = detect_subject("i a")
        assert got["subject"] == "he/she/it"
        assert got["standalone"] == "i"

    def test_named_subject_wins_over_the_marker(self):
        got = detect_subject("Tafit a")
        assert got["subject"] == "Tafit"
        assert got["kind"] == "name"
        # The marker still carries the tense.
        assert got["tense"] == "Past/Present"

    @pytest.mark.parametrize("before,gloss", [("ach", "our (incl.)"), ("óm", "your"), ("nei", "my")])
    def test_possessive_is_not_a_subject(self, before, gloss):
        # "ach tongei" is "our love", not "we love".
        got = detect_subject(before)
        assert got["kind"] == "possessive"
        assert got["subject"] == gloss

    @pytest.mark.parametrize("before", ["Chok", "Fókkun", "Iwe", "Nge"])
    def test_capitalised_function_words_are_not_names(self, before):
        assert detect_subject(before) is None

    def test_no_context(self):
        assert detect_subject("") is None
        assert detect_subject("   ") is None


class TestEntryRanking:
    """The dictionary holds several rows for common words; the best must win."""

    def test_translated_entry_beats_untranslated(self):
        from app import _wol_entry_rank

        translated = {"english_translation": "the", "confidence_score": 10}
        empty = {"english_translation": "", "confidence_score": 99}
        assert _wol_entry_rank(translated) > _wol_entry_rank(empty)

    def test_higher_confidence_wins_among_translated(self):
        from app import _wol_entry_rank

        low = {"english_translation": "the", "confidence_score": 10}
        high = {"english_translation": "the", "confidence_score": 90}
        assert _wol_entry_rank(high) > _wol_entry_rank(low)

    def test_non_numeric_confidence_does_not_raise(self):
        from app import _wol_entry_rank

        assert _wol_entry_rank({"english_translation": "x", "confidence_score": "n/a"})


class TestWordTokenisation:
    """The backend split must match the one the frontend renders with, or words
    silently lose their tint."""

    def test_splits_letters_only(self):
        from app import _WOL_WORD_RE

        text = '"Ewe kapas allim epwe akkomw."—MARK 13:10.'
        assert _WOL_WORD_RE.findall(text) == [
            "Ewe", "kapas", "allim", "epwe", "akkomw", "MARK",
        ]

    def test_keeps_accented_characters_whole(self):
        from app import _WOL_WORD_RE

        assert _WOL_WORD_RE.findall("eáni nónnóm chá") == ["eáni", "nónnóm", "chá"]


class TestDictionarySources:
    """Chuukese headwords live in three collections; a lookup that reads only
    `dictionary_entries` reports known words as missing — "kilisou" is a real
    example, stored as a single-word row in `phrases`."""

    def test_all_three_collections_are_consulted(self, monkeypatch):
        import app

        class FakeCollection:
            def __init__(self, field, rows):
                self.field = field
                self.rows = rows

            def find(self, query, projection=None):
                wanted = query.get(self.field, {}).get("$in", []) if query else []
                if not query:
                    return iter(self.rows)
                return iter([r for r in self.rows if r.get(self.field) in wanted])

        class FakeDB:
            dictionary_collection = FakeCollection(
                "chuukese_word", [{"chuukese_word": "tongei", "english_translation": "to love"}]
            )
            phrases_collection = FakeCollection(
                "chuukese_phrase", [{"chuukese_phrase": "kilisou", "english_translation": "thank you"}]
            )
            words_collection = FakeCollection(
                "chuukese", [{"chuukese": "aramas", "english_translation": "person"}]
            )

        monkeypatch.setattr(app, "dict_db", FakeDB())
        got = app._lookup_words_bulk({"tongei", "kilisou", "aramas"})

        assert got["tongei"]["english"] == "to love"
        assert got["kilisou"]["english"] == "thank you"   # from `phrases`
        assert got["aramas"]["english"] == "person"       # from `words`
        assert all(v["status"] == "translated" for v in got.values())


class TestSimilarWords:
    def test_within_one_edit(self):
        from app import _within_one_edit

        assert _within_one_edit("kkot", "kot")        # deletion
        assert _within_one_edit("tongei", "tongen")   # substitution
        assert _within_one_edit("tongei", "tongei")   # identical
        assert not _within_one_edit("tong", "tongei")  # two edits apart
        assert not _within_one_edit("abc", "xyz")

    def test_norm_word_strips_accents(self):
        from app import _norm_word

        assert _norm_word("pwáseló") == _norm_word("pwaselo")
        assert _norm_word("Kilisou") == "kilisou"

    def test_matches_stems_accents_and_near_misses(self):
        from app import _norm_word, _similar_words

        index = {"by_norm": {}, "by_prefix": {}, "english": {}}
        for word, gloss in [
            ("tong", "love"), ("tongei", "to love"), ("tongen", "love of"),
            ("állea", "read"), ("kot", "god"), ("zzz", ""),
        ]:
            norm = _norm_word(word)
            index["by_norm"].setdefault(norm, set()).add(word)
            index["by_prefix"].setdefault(norm[:3], []).append((norm, word))
            index["by_prefix"].setdefault(norm[:2], []).append((norm, word))
            index["english"][word] = gloss

        # Shared stem, in both directions.
        found = [h["word"] for h in _similar_words("tongeni", index)]
        assert "tongei" in found and "tong" in found

        # Accent-insensitive.
        assert "állea" in [h["word"] for h in _similar_words("alleani", index)]

        # Alphabetical, and glosses come along.
        hits = _similar_words("tongeni", index)
        assert [h["word"] for h in hits] == sorted(h["word"] for h in hits)
        assert all("english" in h for h in hits)

    def test_no_match_returns_empty(self):
        from app import _similar_words

        empty = {"by_norm": {}, "by_prefix": {}, "english": {}}
        assert _similar_words("qqqqq", empty) == []
        assert _similar_words("ab", empty) == []  # too short to be meaningful
