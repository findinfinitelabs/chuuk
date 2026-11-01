"""Talk Builder: outline parsing."""
from src.core.talk_outline import detect_language, parse_outline

SAMPLE = """Why Trust the Bible? (Ps. 119:105)
1. The Bible claims to be from God (5 min.)
   a. 2 Tim. 3:16, 17 — inspired of God
   b. Written by about 40 men over 1,600 years
2. The Bible is accurate (8 min.)
   • Historically: Luke 3:1, 2
   • Scientifically: Job 26:7; Isa. 40:22
3. Conclusion (2 min.)
   Read Ps. 37:29 and invite them to the meeting
"""


def test_outline_structure():
    o = parse_outline(SAMPLE)
    assert o["title"] == "Why Trust the Bible?" and o["theme_scripture"] == "Ps. 119:105"
    assert o["language"] == "en" and o["total_minutes"] == 15
    assert [p["text"] for p in o["points"]] == ["The Bible claims to be from God", "The Bible is accurate", "Conclusion"]
    assert [p["minutes"] for p in o["points"]] == [5, 8, 2]
    assert o["points"][0]["children"][0]["scriptures"] == ["2 Tim. 3:16, 17"]
    assert o["points"][1]["children"][1]["scriptures"] == ["Job 26:7", "Isa. 40:22"]
    assert o["points"][2]["children"][0]["scriptures"] == ["Ps. 37:29"]
    ids = [p["id"] for p in o["points"]] + [c["id"] for p in o["points"] for c in p["children"]]
    assert len(ids) == len(set(ids))


def test_plain_lines_and_language():
    o = parse_outline("Pwata Sipwe Lúkúlúk wóón ewe Paipel?\nEwe Paipel a feito seni Kot me a álisikich.\nA pwal enlet.")
    assert o["language"] == "chk" and o["title"].startswith("Pwata")
    assert len(o["points"]) == 1 and len(o["points"][0]["children"]) == 1
    assert detect_language("The Bible claims to be from God and is accurate.") == "en"
    assert parse_outline("") == {"title": "", "theme_scripture": "", "language": "en", "points": [], "total_minutes": None}
