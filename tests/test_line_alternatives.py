"""Alternatives for a talk line: key terms, overlap scoring, and merging WOL
hits with stored pairs."""

from src.core.line_alternatives import Finder, key_terms, overlap


def test_key_terms_are_longest_content_words():
    terms = key_terms("Ewe lükülük mi enlet esap wewen mi wewemang are tipis ngeni Kot")
    assert terms[0] == "wewemang"
    assert "ewe" not in terms and "ngeni" not in terms
    assert len(terms) == 3


def test_overlap_counts_shared_content_words():
    assert overlap("Ewe lükülük mi enlet esap wewemang", "Lükülük mi enlet esap wewemang ngeni Kot") == 1.0
    assert overlap("Ewe lükülük mi enlet", "Pworausen Noa me ewe noter") == 0.0


class FakeCol:
    def __init__(self, rows):
        self.rows = rows

    def find(self, q, proj=None):
        return self

    def limit(self, n):
        return iter(self.rows)


class FakeDictDB:
    def __init__(self):
        self.phrases_collection = FakeCol([{"chuukese_phrase": "Lükülük mi enlet esap wewemang", "english_translation": "True faith is not gullibility", "source": "w12"}])
        self.db = {"article_analysis_paragraphs": FakeCol([]), "conversation_phrases": FakeCol([])}


class FakeWOL:
    def search(self, query, pages=1, limit=20):
        return {"results": [{"text": "Ewe lükülük mi enlet esap wewemang.", "citation": "w12 11/1 23", "link": "https://wol.jw.org/chk/wol/d/r303/lp-te/2012810", "docId": "2012810"}]}

    def english_for_many(self, items):
        return [{"text": "True faith is not gullibility."} for _ in items]


def test_find_merges_wol_and_library_hits_sorted_by_overlap():
    out = Finder(FakeDictDB(), FakeWOL()).find("Ewe lükülük mi enlet esap wewemang are tipis")
    assert out["wol_reachable"] and out["wol_count"] == 1
    sources = [it["source"] for it in out["items"]]
    assert "wol" in sources and "library" in sources
    assert out["items"][0]["en"]
    assert all(it["score"] > 0 for it in out["items"])
    assert out["items"][0]["source"] == "wol"  # ties go to wol.jw.org first


def test_find_without_wol_uses_library_only():
    out = Finder(FakeDictDB(), None).find("Ewe lükülük mi enlet esap wewemang")
    assert out["wol_reachable"] is False and out["wol_count"] == 0
    assert [it["source"] for it in out["items"]] == ["library"]
