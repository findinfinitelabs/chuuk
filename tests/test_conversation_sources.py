"""Parsing of the Conversation Builder's wol.jw.org sources (bilingual, by pid)."""
from src.api.conversation import fill_slots
from src.core.conversation_sources import parse_lesson, parse_truths, parse_workbook_week, split_statement, week_dates


def _doc(title, body):
    return f"<html><body><article><h1 data-pid='0'>{title}</h1>{body}</article></body></html>"


def test_split_statement():
    assert split_statement("2. The earth will never be destroyed.—Ps. 104:5; Eccl. 1:4.") == ("The earth will never be destroyed.", "Ps. 104:5; Eccl. 1:4")
    assert split_statement("10. Mi wor iten Kot.— Rom 10:13; Féf. 2:21 .") == ("Mi wor iten Kot.", "Rom 10:13; Féf. 2:21")
    assert split_statement("No reference here.") == ("No reference here.", "")


def test_parse_truths_pairs_statements_by_pid():
    en = _doc("Truths We Love to Teach", "<h2 data-pid='13'>THE FUTURE</h2><p data-pid='14'>1. The earth will never be destroyed.—Ps. 104:5.</p>"
              "<h2 data-pid='19'>GOD</h2><p data-pid='20'>2. God has a name.—Ps. 83:18.</p>")
    chk = _doc("Pwóróus mi Enlet", "<h2 data-pid='13'>LÓN MWACH</h2><p data-pid='14'>1. Fénúfan esap fókkun taló.—Kölf. 104:5.</p>"
               "<h2 data-pid='19'>KOT</h2><p data-pid='20'>2. Mi wor iten Kot.—Kölf. 83:18.</p>")
    t = parse_truths(chk, en)
    assert [s["id"] for s in t["subjects"]] == ["the-future", "god"]
    assert t["subjects"][0]["title"] == {"chk": "Lón Mwach", "en": "The Future"}
    st = t["subjects"][1]["statements"][0]
    assert st["n"] == 2 and st["chk"] == "Mi wor iten Kot." and st["en"] == "God has a name."
    assert st["scriptures"] == {"chk": "Kölf. 83:18", "en": "Ps. 83:18"}


def test_parse_lesson_points_items_and_quotes():
    en = _doc("Interest in Others", "<p data-pid='1'>STARTING A CONVERSATION</p><p data-pid='4'>Principle: “Love . . . does not look for its own interests.”—1 Cor. 13:4, 5.</p>"
              "<h2 data-pid='12'>Imitate Jesus</h2><p data-pid='13'>3. Be flexible. Ask yourself:</p><p data-pid='14'>‘What is in the news?’</p>"
              "<p data-pid='20'>5. Listen.</p><p data-pid='21'>Don’t talk too much.</p><h3 data-pid='23'>SEE ALSO</h3><p data-pid='24'>Matt. 7:12</p>")
    chk = _doc("Fós Ussun Met ewe Emén A Sani", "<p data-pid='1'>POPUTÁÁNI EÚ PWÓRÓUSFENGEN</p><p data-pid='4'>Kapasen Emmwen: “Tong . . .”—1 Kor. 13:4, 5.</p>"
               "<h2 data-pid='12'>Áppirú Jises</h2><p data-pid='13'>3. Tipemecheres. Pwisin eisinuk:</p><p data-pid='14'>‘Met sókkun pwóróus a nóm lón news?’</p>"
               "<p data-pid='20'>5. Aúseling.</p><p data-pid='21'>Kosap kon fós chómmóng.</p><h3 data-pid='23'>PWAL PPII</h3><p data-pid='24'>Mat. 7:12</p>")
    l = parse_lesson(chk, en, 1)
    assert l["stage"] == {"chk": "Poputááni Eú Pwóróusfengen", "en": "Starting A Conversation"}
    assert l["principle"]["chk"].startswith("Kapasen Emmwen")
    pts = l["sections"][0]["points"]
    assert pts[0]["n"] == 3 and pts[0]["chk"].startswith("Tipemecheres")
    assert pts[0]["items"] == [{"pid": "14", "chk": "‘Met sókkun pwóróus a nóm lón news?’", "en": "‘What is in the news?’", "quoted": True}]
    assert pts[1]["items"][0]["quoted"] is False
    assert l["see_also"] == {"chk": "Mat. 7:12", "en": "Matt. 7:12"}


def test_week_dates():
    assert week_dates("JANUARY 6-12", 2025) == ("2025-01-06", "2025-01-12")
    assert week_dates("JANUARY 27–FEBRUARY 2", 2025) == ("2025-01-27", "2025-02-02")
    assert week_dates("DECEMBER 29–JANUARY 4", 2025) == ("2025-12-29", "2026-01-04")
    assert week_dates("Not a week", 2025) is None


def test_parse_workbook_week_field_ministry_parts():
    en = _doc("JANUARY 6-12", "<h2 data-pid='4'>TREASURES FROM GOD’S WORD</h2><h3 data-pid='5'>1. Parents</h3><p data-pid='6'>(10 min.)</p>"
              "<h2 data-pid='18'>APPLY YOURSELF TO THE FIELD MINISTRY</h2>"
              "<h3 data-pid='21'>5. Starting a Conversation</h3><p data-pid='22'>(4 min.) INFORMAL WITNESSING. The person expresses a belief that conflicts with a Bible teaching. ( lmd lesson 5 point 4 )</p>"
              "<h3 data-pid='23'>6. Making Disciples</h3><p data-pid='24'>(5 min.) lff lesson 16 points 4-5 . Discuss the arrangements. ( lmd lesson 10 point 4 )</p>"
              "<h2 data-pid='25'>LIVING AS CHRISTIANS</h2><h3 data-pid='27'>7. Parents</h3><p data-pid='28'>(15 min.)</p>")
    chk = _doc("JANUARY 6-12", "<h2 data-pid='4'>PWÓRÓUS AÚCHEA</h2><h3 data-pid='5'>1. Sam me In</h3><p data-pid='6'>(10 min.)</p>"
               "<h2 data-pid='18'>ELIPWÁKÉCHUK LÓN ANGANGEN AFALAFAL</h2>"
               "<h3 data-pid='21'>5. Poputááni eú Pwóróusfengen</h3><p data-pid='22'>(4 min.) AFALAFAL SERESERÉCH. Ewe emén a apwóróusa an lúkú. ( lmd lesen 5 nampa 4 )</p>"
               "<h3 data-pid='23'>6. Álisi Aramas</h3><p data-pid='24'>(5 min.) lff lesen 16 nampa 4-5 . Pwóróusfengen. ( lmd lesen 10 nampa 4 )</p>"
               "<h2 data-pid='25'>MANAWEN CHÓN KRAIST</h2><h3 data-pid='27'>7. Sam</h3><p data-pid='28'>(15 min.)</p>")
    w = parse_workbook_week(chk, en, "202025001", 2025)
    assert (w["start"], w["end"]) == ("2025-01-06", "2025-01-12")
    assert [p["n"] for p in w["parts"]] == [5, 6]
    p5, p6 = w["parts"]
    assert p5["minutes"] == 4 and p5["refs"] == {"lmd": {"lesson": 5, "points": "4"}}
    assert p5["setting"]["en"] == "INFORMAL WITNESSING. The person expresses a belief that conflicts with a Bible teaching."
    assert p5["setting"]["chk"] == "AFALAFAL SERESERÉCH. Ewe emén a apwóróusa an lúkú."
    assert p6["refs"] == {"lmd": {"lesson": 10, "points": "4"}, "lff": {"lesson": 16, "points": "4-5"}}
    assert p6["setting"]["en"] == "Discuss the arrangements."


def test_fill_slots():
    assert fill_slots("Let us read {{scripture}}.", {"scripture": "Kölf. 37:29"}) == "Let us read Kölf. 37:29."
    assert fill_slots("See you on {{day}}.", {}) == "See you on [day]."
