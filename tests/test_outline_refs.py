"""Outline citations: finding them, key phrases, paragraph highlighting."""
from src.core.outline_refs import find_references, highlight_paragraph, key_words, page_range, paragraphs_by_number, parse_document


def test_find_references():
    refs = find_references("Train each child (Ps 127:4; w19.12 26 ¶20) lff lesson 16 points 4-5, bt chap. 20 ¶13-15, it-1 543, lmd lesson 5 point 4")
    assert [r["kind"] for r in refs] == ["w", "lesson", "chapter", "it", "lesson"]
    assert refs[0] == {"raw": "w19.12 26 ¶20", "kind": "w", "year": 2019, "month": 12, "page": 26, "paragraphs": [20]}
    assert refs[1]["pub"] == "lff" and refs[1]["lesson"] == 16 and refs[1]["paragraphs"] == [4, 5]
    assert refs[2]["chapter"] == 20 and refs[2]["paragraphs"] == [13, 14, 15]
    assert refs[3]["pub"] == "it-1" and refs[3]["page"] == 543
    assert refs[4]["pub"] == "lmd" and refs[4]["paragraphs"] == [4]


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
