"""Outline citations: finding them, key phrases, paragraph highlighting."""
from src.core.outline_refs import find_references, highlight_paragraph, key_words, page_range, paragraphs_by_number, parse_document


def test_find_references():
    refs = find_references("Train each child (Ps 127:4; w19.12 26 ¶20) lff lesson 16 points 4-5, bt chap. 20 ¶13-15, it-1 543, lmd lesson 5 point 4")
    assert [r["kind"] for r in refs] == ["w", "lesson", "chapter", "it", "lesson"]
    assert refs[0] == {"raw": "w19.12 26 ¶20", "kind": "w", "pub": "w", "year": 2019, "month": 12, "day": None, "page": 26, "paragraphs": [20]}
    assert refs[1]["pub"] == "lff" and refs[1]["lesson"] == 16 and refs[1]["paragraphs"] == [4, 5]
    assert refs[2]["chapter"] == 20 and refs[2]["paragraphs"] == [13, 14, 15]
    assert refs[3]["pub"] == "it-1" and refs[3]["page"] == 543
    assert refs[4]["pub"] == "lmd" and refs[4]["paragraphs"] == [4]


def test_older_citation_forms():
    refs = find_references("See (w12 11/1 23) and (w10 3/15 12-13 ¶4-5), g 11/12 8, wp16 2/1 5, km 5/09 3")
    assert refs[0] == {"raw": "w12 11/1 23", "kind": "w", "pub": "w", "year": 2012, "month": 11, "day": 1, "page": 23, "paragraphs": []}
    assert refs[1]["year"] == 2010 and refs[1]["day"] == 15 and refs[1]["page"] == 12 and refs[1]["paragraphs"] == [4, 5]
    assert refs[2]["pub"] == "g" and refs[2]["year"] == 2012 and refs[2]["month"] == 11 and refs[2]["day"] is None and refs[2]["page"] == 8
    assert refs[3]["pub"] == "wp" and refs[3]["year"] == 2016
    assert refs[4]["pub"] == "km" and refs[4]["year"] == 2009 and refs[4]["month"] == 5 and refs[4]["day"] is None


def test_key_words_skip_stopwords_and_citations():
    assert key_words("Jehovah appreciates it when parents rely on him (w21.08 5 ¶9)") == ["appreciates", "parents", "rely"]


def test_page_range_and_numbering():
    assert page_range("w25 January pp. 2-7") == (2, 7)
    assert page_range("w25 January p. 32") == (32, 32)
    html = ("<article><p data-pid='38'>2. How did Jehovah reveal his glory?</p>"
            "<p data-pid='9'><span class='parNum' data-pnum='2'><sup>2</sup></span> What is glory? It is impressive and it covers more than forty characters.</p>"
            "<p data-pid='10'>9 Older format paragraph with a printed number that is long enough to count here.</p></article>")
    doc = parse_document(html)
    assert [(pid, n) for pid, _, n in doc["paragraphs"]] == [("38", None), ("9", 2), ("10", 9)]
    assert [(n, pid) for n, pid, _ in paragraphs_by_number(doc["paragraphs"], [2, 9])] == [(2, "9"), (9, "10")]


def test_highlight_marks_english_and_aligned_chuukese():
    en = "What is glory? Jehovah revealed his glory at Mount Sinai in a powerful display."
    chk = "Met weween ling? Jiowa a pwáraaló lingan me ren ewe Chuuk Sinai lón eú pwáratá mi manaman."
    hl = highlight_paragraph(en, chk, key_words("Jehovah revealed his glory at Mount Sinai"), {"lingan": "glory", "sinai": "Sinai"})
    assert [r["hit"] for r in hl["english"]] == [False, True]
    assert [w["text"] for w in hl["english"][1]["words"] if w["hit"]] == ["revealed", "glory", "Mount", "Sinai"]
    assert [r["hit"] for r in hl["chuukese"]] == [False, True]
    assert [w["text"] for w in hl["chuukese"][1]["words"] if w["hit"]] == ["lingan", "Sinai"]
    assert highlight_paragraph(en, None, [])["chuukese"] is None


def test_lookup_resolves_citation_through_wol_lookup_page():
    """"w12 11/1 23" is answered by WOL's citation lookup page, which links the
    document; the resolver uses that before crawling the library index."""
    from src.core.outline_refs import Resolver, find_references

    pages = {
        "https://wol.jw.org/en/wol/l/r1/lp-e?q=w12%2011/1%2023": (
            '<html><body><ul><li><a href="/en/wol/h/r1/lp-e">Home</a></li></ul>'
            '<div class="results"><a href="/en/wol/d/r1/lp-e/2012810#h=1:0-9:0">Is Religious Faith an Emotional Crutch?</a>'
            '<a href="/en/wol/bc/r1/lp-e/2012810/0/0">Proverbs 14:15</a></div></body></html>'
        ),
        "https://wol.jw.org/en/wol/d/r1/lp-e/2012810": (
            '<html><body><h1>Is Religious Faith an Emotional Crutch?</h1><li class="documentLocation">w12 11/1 pp. 23-24</li>'
            '<article><p data-pid="1">Some equate faith with gullibility, as if believers simply ignore reality.</p>'
            '<p data-pid="2">Religious faith that is not built on sound evidence can become a crutch, but true faith is not mental laziness.</p></article></body></html>'
        ),
    }
    fetched = []

    def fetch(url):
        fetched.append(url)
        return pages.get(url)

    ref = find_references("True faith is not mental laziness or an emotional crutch (w12 11/1 23)")[0]
    out = Resolver(fetch).resolve(ref, "True faith is not mental laziness or an emotional crutch")
    assert out["links"]["en"] == "https://wol.jw.org/en/wol/d/r1/lp-e/2012810#h=1:0-9:0"
    assert out["title"]["en"] == "Is Religious Faith an Emotional Crutch?"
    assert out["chuukese_available"] is False and "not available in Chuukese" in out["note"]
    assert [p["number"] for p in out["paragraphs"]] == [1, 2]
    assert any(w["hit"] for w in out["paragraphs"][1]["en_sentences"][0]["words"])
    assert not any("/library/" in u for u in fetched), "the library index was crawled although the lookup answered"
