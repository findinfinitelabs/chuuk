"""The uploaded New World Translation: header parsing and local-only lookups."""
from src.core import nwt_bible as nb


def _w(text, x=26.0, y=23.0, h=7.2):
    return (x, y, x + 10, y + h, text)


def test_header_reads_book_and_the_book_that_begins_on_the_page():
    assert nb._header([_w("GENESIS"), _w("1:20–2:5", x=59), _w("44", x=278)])[:2] == (1, None)
    assert nb._header([_w("1"), _w("SAMUEL", x=32), _w("17:1–18:4", x=70)])[:2] == (9, None)
    assert nb._header([_w("AMOS"), _w("9:11–OBADIAH", x=50), _w("3", x=120)])[:2] == (30, 31)
    assert nb._header([_w("NUMBERS"), _w("36:1", x=50), _w("–", x=70), _w("DEUTERONOMY", x=80), _w("Contents", x=140)])[:2] == (4, 5)
    assert nb._header([_w("OBADIAH"), _w("4-17", x=60)])[:2] == (31, None)
    assert nb._header([_w("THE"), _w("FIRST", x=40), _w("OF", x=60)])[0] is None


def test_lookup_never_touches_the_network(monkeypatch):
    nb._memory.clear()
    monkeypatch.setattr(nb, "EN_FILE", nb.EN_FILE)
    text = nb.verse(None, "en", 54, 2, 14)
    assert "Adam" in text and "deceived" in text
    assert nb.verse(None, "chk", 54, 2, 14).startswith("Pwal och, Atam")
    assert nb.verse(None, "chk", 1, 1, 1) == ""   # Chuukese NWT covers Matthew–Revelation only


def test_database_copy_is_preferred():
    class Col:
        def find_one(self, q, proj):
            return {"verses": {"14": "from the database"}}

    db = {nb.COLLECTION: Col()}
    assert nb.verse(db, "en", 54, 2, 14) == "from the database"
