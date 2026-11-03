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


def test_printed_outline_headings_become_sections():
    """A pasted S-34 outline has no indentation: capitalised headings with
    times are the sections, the lines after each are its points, the note
    and the footer are set aside, and the number leaves the title."""
    from src.core.talk_outline import parse_outline

    text = """No. 166True Faith—What Is It, and How Is It Shown?
PLEASE NOTE: Warmly encourage newly interested ones to cultivate faith.
TRUE FAITH IS BUILT ON EVIDENCE (6 min.)
Many claim that faith and reason are incompatible (g 1/11 28 ¶1-2)
True faith is not mental laziness or an emotional crutch (w12 11/1 23)
TRUE FAITH IS SHOWN BY ACTIONS (13 min.)
If our faith is genuine, it will be evident in our actions [Read James 2:17, 26]
YOU CAN CULTIVATE TRUE FAITH (4 min.)
Ask Jehovah God to help you to grow strong in faith (Jas 2:23)
[Adhere closely to the outlined material, and observe the indicated timing of each section]
TO BE COVERED IN 30 MINUTES
© 2024 Watch Tower Bible and Tract Society of Pennsylvania
S-34-E No. 166 10/24"""
    o = parse_outline(text, "en")
    assert o["title"] == "True Faith—What Is It, and How Is It Shown?" and o["number"] == "No. 166"
    assert o["note"].startswith("Warmly encourage")
    assert [p["text"] for p in o["points"]] == ["TRUE FAITH IS BUILT ON EVIDENCE", "TRUE FAITH IS SHOWN BY ACTIONS", "YOU CAN CULTIVATE TRUE FAITH"]
    assert [p["minutes"] for p in o["points"]] == [6, 13, 4]
    assert o["total_minutes"] == 30
    assert [c["text"][:20] for c in o["points"][0]["children"]] == ["Many claim that fait", "True faith is not me"]
    assert o["points"][0]["children"][1]["references"][0]["raw"] == "w12 11/1 23"
    assert o["points"][2]["children"][0]["scriptures"] == ["Jas 2:23"]
    assert len(o["dropped"]) == 5


def test_restructure_keeps_point_ids_for_existing_talks():
    from src.core.talk_outline import restructure

    outline = {"title": "T", "points": [{"id": "p1", "text": "PLEASE NOTE: x", "minutes": None, "children": [
        {"id": "p2", "text": "FIRST SECTION", "minutes": 6}, {"id": "p3", "text": "a point", "minutes": None},
        {"id": "p4", "text": "SECOND SECTION", "minutes": 4}, {"id": "p5", "text": "another point", "minutes": None}]}], "total_minutes": None}
    o = restructure(outline)
    assert [p["id"] for p in o["points"]] == ["p2", "p4"]
    assert [c["id"] for c in o["points"][0]["children"]] == ["p3"]
    assert o["dropped"] == ["p1"] and o["total_minutes"] == 10
