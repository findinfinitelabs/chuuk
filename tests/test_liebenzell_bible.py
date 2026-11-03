"""The Liebenzell Paipel PDF parser: page headers, chapter numbers, section
headings with verse ranges, footnotes and single-chapter books."""

from src.core.liebenzell_bible import _Parser, book_number


PAGE_1 = """KENESES 1:1 1 KENESES 1:2
Keneses
Kapas akom
I. Iten ei puk: Keneses, wewen lepopun.
1. Sopun 1-11, usun än Kot föri läng
Kot a föri läng me fanüfan me aramas
1.1–2.7
1 Lepopun Kot a föri läng me fanüfan.
2 Nge fanüfan a kotongau o pön, nge Ngünün
Kot a tümwünü ewe lölö."""

PAGE_2 = """KENESES 1:3 2 KENESES 2:2
3 Mürin, Kot a apasa, “Epwe saram.” Iwe, a saramala. ✡
✡
2
Ewe afisin rän
2.1-3
1 Iei usun läng me fanüfan ra wes.
2 Iwe, Kot a wes seni an angang. †
† 2:2: Ipr 4.4,10 ✡ 1:3: Eks 20.11
ei wokisin esap wokisin"""

PAGE_OBADIAH = """OPATAIA1 1255 OPATAIA7
Opataia
Kapas akom
Kot a atekisonätiu chon Etom
1-16
1 Iei osuni Opataia.
2 Üpwe akükünalo om mwü."""


def test_parse_pages():
    p = _Parser()
    p.page(PAGE_1)
    p.page(PAGE_2)
    p.page(PAGE_OBADIAH)
    gen = p.bible[1]
    assert gen[1][1] == "Lepopun Kot a föri läng me fanüfan."
    assert gen[1][2] == "Nge fanüfan a kotongau o pön, nge Ngünün Kot a tümwünü ewe lölö."
    assert gen[1][3] == "Mürin, Kot a apasa, “Epwe saram.” Iwe, a saramala."
    assert gen[2] == {1: "Iei usun läng me fanüfan ra wes.", 2: "Iwe, Kot a wes seni an angang."}
    assert p.bible[31][1] == {1: "Iei osuni Opataia.", 2: "Üpwe akükünalo om mwü."}


def test_book_labels():
    assert book_number("1.SAMUEL") == 9
    assert book_number("ÄN SALOMON AFALAFAL") == 21
    assert book_number("OPATAIA") == 31
    assert book_number("MALAKAI") == 39
    assert book_number("PWÄRÄTÄ") == 66
    assert book_number("Contents") is None
