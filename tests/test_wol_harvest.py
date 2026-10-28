"""Tests for the wol.jw.org publication harvester logic (no network)."""

import pytest

from src.core import wol_harvest as wh

pytestmark = pytest.mark.unit

INDEX_HTML = """
<ul>
 <li><a href="/chk/wol/library/r303/lp-te/meinisin-mi-peres/minen-k%C3%A1%C3%A9-f%C3%A1n-iten-mwiich/manawach-me-ach-angangen-afalafal-minen-k%C3%A1%C3%A9-f%C3%A1n-iten-mwiich-2026">2026</a></li>
 <li><a href="/chk/wol/library/r303/lp-te/meinisin-mi-peres/minen-káé-fán-iten-mwiich/manawach-me-ach-angangen-afalafal-minen-káé-fán-iten-mwich-2025">2025</a></li>
 <li><a href="/chk/wol/library/r303/lp-te/meinisin-mi-peres/minen-káé-fán-iten-mwiich/manawach-me-ach-angangen-afalafal-minen-káé-fán-iten-mwich-2025/january">deeper</a></li>
 <li><a href="/chk/wol/pref/r303/lp-te?url=x">Preferences</a></li>
</ul>
"""

ISSUE_HTML = """
<a href="/chk/wol/d/r303/lp-te/202025000?q=x">Cover</a>
<a href="/chk/wol/d/r303/lp-te/202025001">January 6-12</a>
<a href="/chk/wol/d/r303/lp-te/202025001">January 6-12 again</a>
<a href="/chk/wol/d/r303/lp-te/202025002">January 13-19</a>
<a href="/en/wol/d/r1/lp-e/999">not chuukese</a>
"""


def test_year_link_matches_on_year_suffix_despite_slug_spelling():
    assert wh.year_link(INDEX_HTML, "mwb", 2025).endswith("mwich-2025")
    assert wh.year_link(INDEX_HTML, "mwb", 2026).endswith("mwiich-2026")
    assert wh.year_link(INDEX_HTML, "mwb", 2019) is None


def test_child_links_only_one_level_down():
    parent = wh.CHK_LIBRARY + "/minen-káé-fán-iten-mwiich"
    hrefs = [h for h, _ in wh.child_links(INDEX_HTML, parent)]
    assert len(hrefs) == 2
    assert all(h.count("/") == parent.count("/") + 1 for h in hrefs)


def test_doc_links_unique_in_order():
    assert wh.doc_links(ISSUE_HTML) == [("202025000", "Cover"), ("202025001", "January 6-12"), ("202025002", "January 13-19")]


def test_parse_document_reads_paragraph_ids_once():
    html = """
    <html><body><h1>Title Here</h1><li class="documentLocation">mwb25 January pp. 2-3</li>
    <article>
      <p data-pid="1">First sentence. Second one.</p>
      <div data-pid="2"><p data-pid="2">Nested same pid.</p></div>
      <p>No pid, ignored.</p>
    </article></body></html>"""
    doc = wh.parse_document(html)
    assert doc["title"] == "Title Here"
    assert doc["citation"] == "mwb25 January pp. 2-3"
    assert doc["paragraphs"] == [("1", "First sentence. Second one."), ("2", "Nested same pid.")]


def test_pair_paragraph_positional_when_counts_match():
    chk = "Jiowa a tongei aramas meinisin. A mochen sipwe áppirú i."
    eng = "Jehovah loves all people. He wants us to imitate him."
    pairs = wh.pair_paragraph("7", chk, eng)
    assert [(p["chuukese"], p["english"]) for p in pairs] == [
        ("Jiowa a tongei aramas meinisin.", "Jehovah loves all people."),
        ("A mochen sipwe áppirú i.", "He wants us to imitate him."),
    ]
    assert all(p["alignment"] == "positional" and p["confidence_score"] == 90 for p in pairs)


def test_pair_paragraph_single_sentence_is_exact():
    pairs = wh.pair_paragraph("3", "Jiowa a tongei aramas meinisin.", "Jehovah loves all people.")
    assert len(pairs) == 1 and pairs[0]["alignment"] == "exact" and pairs[0]["confidence_score"] == 95


def test_pair_paragraph_falls_back_to_whole_paragraph_when_counts_differ():
    chk = "Jiowa a tongei aramas meinisin, iwe a mochen sipwe áppirú i."
    eng = "Jehovah loves all people. He wants us to imitate him."
    pairs = wh.pair_paragraph("4", chk, eng)
    assert len(pairs) == 1 and pairs[0]["type"] == "paragraph" and pairs[0]["confidence_score"] == 85


def test_pair_paragraph_skips_identical_headings_and_fragments():
    assert wh.pair_paragraph("1", "JANUARY 6-12", "JANUARY 6-12") == []
    assert wh.pair_paragraph("2", "Kél 134", "Song 134") == []
    # Two long sentences against one: no positional pairing, and the whole
    # paragraph is too long to keep as one example.
    long_chk = " ".join(["Kapas"] * 80)
    long_eng = " ".join(["word"] * 80) + "."
    assert wh.pair_paragraph("5", long_chk + ". " + long_chk + ".", long_eng) == []


def test_pair_paragraph_drops_lines_whose_citations_disagree():
    chk = "Kf 131:1, 2—Met ekkewe sam me in ra tongeni káé seni ekkeei wokisin? (w21.07 21 ¶6)"
    eng = "Ps 128:3 —Why does the psalmist compare sons to the shoots of an olive tree? (it-2 555)"
    assert wh.pair_paragraph("8", chk, eng) == []
    # Page numbers differing between editions must not count as a mismatch.
    chk_ok = "Asukula emén me emén naw alóngólóng wóón minne mi lamot ngeni (Kf 127:4; w19.12 26 ¶20)"
    eng_ok = "Train each child according to his individual needs (Ps 127:4; w19.12 27 ¶20)"
    assert len(wh.pair_paragraph("9", chk_ok, eng_ok)) == 1


def test_pair_documents_matches_by_pid_and_record_shape():
    chk = {"title": "Tettelin", "citation": "mwb25 January p. 2", "paragraphs": [("1", "Jiowa a tongei aramas meinisin."), ("9", "Ese wor lon English.")]}
    eng = {"title": "Headline", "citation": "mwb25 January p. 2", "paragraphs": [("1", "Jehovah loves all people.")]}
    pairs = wh.pair_documents("202025001", chk, eng)
    assert len(pairs) == 1 and pairs[0]["doc_id"] == "202025001"
    rec = wh.pair_record(pairs[0], "mwb", 2025, chk, eng)
    assert rec["_id"] == "wol_202025001_1_0"
    assert rec["chuukese_sentence"] == "Jiowa a tongei aramas meinisin." and rec["english_translation"] == "Jehovah loves all people."
    assert rec["type"] == "sentence" and rec["confidence_score"] == 95 and rec["source"] == "wol.jw.org"
    assert rec["publication"] == "mwb" and rec["year"] == 2025 and rec["user_confirmed"] is False
    assert rec["link"].endswith("/202025001#p1") and rec["link_en"].endswith("/202025001#p1")
