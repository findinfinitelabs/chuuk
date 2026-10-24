"""Sentence extraction and English↔Chuukese paragraph pairing for the Translation Game."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.article_sentences import align_hints, clean_paragraph, parse_article
from src.utils.scripture_parser import split_sentences


def _doc(paragraphs, title="Title"):
    body = "".join(f'<p data-pid="{pid}" id="p{pid}">{html}</p>' for pid, html in paragraphs)
    return f"<html><body><h1>{title}</h1><article>{body}</article></body></html>"


CHK_PARA = (
    "Iwe nge, sia tongeni lúkú ei mettóch usun Jiowa pwe “esap wor an mwäl.” "
    '( <a class="b" href="/chk/wol/bc/r303/lp-te/1">Tut. 32:4</a> ) A alónga an kefil wóón '
    "meinisin ekkewe pwóróus mi enlet, nge esap wóón alon aramas. Ina popun, atun Jiowa a erá "
    "pwe “ese chúen chechchemeni” tipisin emén mi áier, a wewe ngeni pwe i esap chúen apwúngú."
)
EN_PARA = (
    "However, we can trust that Jehovah is “a God of faithfulness, with whom there is no injustice.” "
    '(<a class="b" href="/en/wol/bc/r1/lp-e/1">Deut. 32:4</a>) He bases his judgments on all the '
    "facts, not on hearsay or on prejudice. So when Jehovah says that he “will no longer remember” "
    "the sins of a repentant person, he means that he will not hold them against that person."
)


class TestSplitSentences:
    def test_closing_quote_then_citation_stays_with_sentence(self):
        parts = split_sentences(
            "Jiowa a erá: “Esap wor an mwäl.” ( Tut. 32:4 ) A alónga an kefil wóón meinisin ekkewe pwóróus."
        )
        assert parts == [
            "Jiowa a erá: “Esap wor an mwäl.” (Tut. 32:4)",
            "A alónga an kefil wóón meinisin ekkewe pwóróus.",
        ]

    def test_emdash_citation_with_two_books(self):
        parts = split_sentences(
            "Jerusalem a talo me Juta a pöönnülo.—Ais. 13:19; Jer. 52:12-14. Pwata ina a fis?"
        )
        assert parts[0].endswith("—Ais. 13:19; Jer. 52:12-14.")
        assert parts[1] == "Pwata ina a fis?"

    def test_multi_chapter_citation_kept_whole(self):
        text = (
            "Ewe imwenfel mi kaútá lón ena telinimw, ina leenien iten Jiowa. "
            "(Tut. 12:5; 14:24, 25; 1Kr 29:13-16; 1Ki 8:15-21, 41-43) Met mi éch aramas ra féri lón ena imwenfel."
        )
        parts = split_sentences(text)
        assert len(parts) == 2
        assert "(Tut. 12:5; 14:24, 25; 1Kr 29:13-16; 1Ki 8:15-21, 41-43)" in parts[0]

    def test_cross_chapter_range_and_psalms_abbreviation(self):
        parts = split_sentences(
            "Ewer, moni me pisek, ir ra nonnom lein ekkewe kot. ( Fof. 27:37–28:2 ) Jiowa a tongeni "
            "wiliiti emén soufiu mi pwora.—Kölf. 3:13, 14. Áwewe chék, i a tongeni wiliiti emén."
        )
        assert parts == [
            "Ewer, moni me pisek, ir ra nonnom lein ekkewe kot. (Fof. 27:37–28:2)",
            "Jiowa a tongeni wiliiti emén soufiu mi pwora.—Kölf. 3:13, 14.",
            "Áwewe chék, i a tongeni wiliiti emén.",
        ]

    def test_citation_in_running_text_and_read_parenthetical(self):
        parts = split_sentences(
            "Lon 2 Piter 1:21 , a erä: “Pun esap wor och kapasen osuni.” Ren ach sipwe pélúweni ena "
            "kapas eis, sipwe káé úlúngát mettóch. (Álleani Aisea 55:7.) A erá: “Repwe feiló.”—KÖLF. 32:5."
        )
        assert parts == [
            "Lon 2 Piter 1:21, a erä: “Pun esap wor och kapasen osuni.”",
            "Ren ach sipwe pélúweni ena kapas eis, sipwe káé úlúngát mettóch. (Álleani Aisea 55:7.)",
            "A erá: “Repwe feiló.”—KÖLF. 32:5.",
        ]

    def test_english_wol_forms(self):
        parts = split_sentences(
            "Do not quickly assume that a person who is rarely at home is not interested. (1 Cor. 13:4, 7) "
            "Instead, balance perseverance with wise use of your time.—1 Cor. 9:26. Read 1 Ki. 8:15-21 and "
            "Song of Sol. 2:1 with care."
        )
        assert len(parts) == 3
        assert parts[0].endswith("(1 Cor. 13:4, 7)")
        assert parts[1].endswith("—1 Cor. 9:26.")
        assert "1 Ki. 8:15-21" in parts[2] and "Song of Sol. 2:1" in parts[2]

    def test_short_abbreviation_needs_chapter_and_verse(self):
        # "Is" and "Am" are Isaiah/Amos only when followed by chapter:verse.
        parts = split_sentences("This is the way. Am I ready? Is 2:3 relevant? Yes it is.")
        assert parts == ["This is the way.", "Am I ready?", "Is 2:3 relevant?", "Yes it is."]


class TestParseArticle:
    def test_paragraph_numbers_and_bullets_stripped(self):
        assert clean_paragraph("8 Lón ei fansoun, Jiowa a emmweni.") == "Lón ei fansoun, Jiowa a emmweni."
        assert clean_paragraph("• Keep this line.") == "Keep this line."
        assert clean_paragraph("2 Piter 1:21 a erä.") == "2 Piter 1:21 a erä."

    def test_sentences_carry_paragraph_ids(self):
        parsed = parse_article(_doc([(3, CHK_PARA), (4, "Eú puk a áweweei ussun ena kapas, a erá pwe mi fókkun lamot.")]))
        assert parsed["title"] == "Title"
        assert parsed["has_pids"] is True
        texts = [s["text"] for s in parsed["sentences"]]
        assert texts[0].endswith("“esap wor an mwäl.” (Tut. 32:4)")
        assert len([s for s in parsed["sentences"] if s["pid"] == "3"]) == 3
        third = parsed["sentences"][2]
        assert (third["sentence_index"], third["sentence_count"]) == (2, 3)
        assert parsed["sentences"][3]["pid"] == "4"
        assert all(0.0 <= s["span"][0] < s["span"][1] <= 1.0 for s in parsed["sentences"])

    def test_footnote_markers_removed(self):
        html = _doc([(1, 'Jiowa a tongeni omusaaló tipisin Tafit<a class="fn">*</a> ren an nimanaw me lisowumwáál.')])
        assert parse_article(html)["sentences"][0]["text"] == (
            "Jiowa a tongeni omusaaló tipisin Tafit ren an nimanaw me lisowumwáál."
        )

    def test_pages_without_pids_fall_back_to_paragraph_elements(self):
        html = "<article><p>First paragraph with enough words here. Second sentence in it.</p><li>A list item long enough.</li></article>"
        parsed = parse_article(html)
        assert parsed["has_pids"] is False
        assert [s["text"] for s in parsed["sentences"]] == [
            "First paragraph with enough words here.",
            "Second sentence in it.",
            "A list item long enough.",
        ]
        assert all(s["pid"] is None for s in parsed["sentences"])


class TestAlignHints:
    def test_same_sentence_count_pairs_by_position(self):
        en = parse_article(_doc([(3, EN_PARA)]))["sentences"]
        chk = parse_article(_doc([(3, CHK_PARA)]))["sentences"]
        assert len(en) == len(chk) == 3
        hints = align_hints(en, chk)
        assert hints[en[0]["id"]] == {"paragraph": [1, 2, 3], "likely": [1]}
        assert hints[en[2]["id"]]["likely"] == [3]

    def test_different_counts_pair_by_position_in_paragraph(self):
        en = parse_article(_doc([(7, "One short English sentence here. Another English sentence follows it.")]))["sentences"]
        chk = parse_article(
            _doc([(7, "Eú kapas lón fósun Chuuk mi ffat ren ei. A pwal wor eú kapas. Pwal eú kapas sáingoon ikenai.")])
        )["sentences"]
        hints = align_hints(en, chk)
        assert hints[1]["paragraph"] == [1, 2, 3]
        assert hints[1]["likely"] and 3 not in hints[1]["likely"]
        assert hints[2]["likely"] and 1 not in hints[2]["likely"]

    def test_unpaired_paragraph_has_no_hint(self):
        en = parse_article(_doc([(1, "An English paragraph long enough to keep.")]))["sentences"]
        chk = parse_article(_doc([(2, "Eú kapas lón fósun Chuuk mi ffat ren ei.")]))["sentences"]
        assert align_hints(en, chk) == {}

    def test_no_pids_pairs_by_paragraph_order_only_when_counts_match(self):
        en = parse_article("<article><p>An English paragraph long enough to keep.</p><p>Second English paragraph here.</p></article>")["sentences"]
        chk = parse_article("<article><p>Eú kapas lón fósun Chuuk mi ffat ren ei.</p><p>Aruuen kapas lón fósun Chuuk.</p></article>")["sentences"]
        assert align_hints(en, chk) == {1: {"paragraph": [1], "likely": [1]}, 2: {"paragraph": [2], "likely": [2]}}
        chk_short = chk[:1]
        assert align_hints(en, chk_short) == {}
