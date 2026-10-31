"""Content-based pairing of article paragraphs and sentences across editions."""
from src.core.sentence_align import align_paragraphs, align_sentences, paragraph_label
from src.utils.scripture_parser import split_sentences


def test_paragraph_label():
    assert paragraph_label("2 Read Luke 1:67-73.") == "2"
    assert paragraph_label("3. From whom?") == "3"
    assert paragraph_label("10-11. What can we do?") == "10-11"
    assert paragraph_label("THE GIFT OF SALVATION") is None


def test_paragraphs_survive_extra_english_footnote():
    chk = [
        {"tag": "p", "pid": "7", "text": "ATUN Sekaraia me Elisapet ra fókkun chinnap, Jiowa a féri eú manaman."},
        {"tag": "h2", "pid": "8", "text": "EWE LIFFANG, ACH KÚNA AMANAW"},
        {"tag": "p", "pid": "37", "text": "2. (a) Me ren Luk 1:67-73, ifa ewe liffang Kot a pwonei?"},
        {"tag": "p", "pid": "9", "text": "2 Álleani Luk 1:67-73. Kot a fen pwonei ngeni néún kewe aramas."},
        {"tag": "p", "pid": "70", "text": "a ÁWEWEEN SASING: Ewe ewin sasing, sasingin rúúemén pwúpwúlú fefin ra afalafal lón eú leeni mi chómmóng aramas."},
    ]
    eng = [
        {"tag": "p", "pid": "7", "text": "“WHAT will this young child turn out to be?” The neighbors were curious."},
        {"tag": "h2", "pid": "8", "text": "THE GIFT OF SALVATION"},
        {"tag": "p", "pid": "39", "text": "2. (a) According to Luke 1:67-73, what gift is promised?"},
        {"tag": "p", "pid": "9", "text": "2 Read Luke 1:67-73. God had promised to give his people a gift."},
        {"tag": "p", "pid": "35", "text": "a See the excerpt containing Zechariah’s prophecy."},
        {"tag": "p", "pid": "72", "text": "b PICTURE DESCRIPTION: In the first photo, two sisters witness informally in a busy public place."},
    ]
    assert align_paragraphs(chk, eng) == [0, 1, 2, 3, 5]


def test_swapped_opening_pair_and_merged_tail():
    chk = split_sentences(
        "ATUN Sekaraia me Elisapet ra fókkun chinnap, Jiowa a féri eú manaman pwe repwe néúni emén át itan, Jon. "
        "Meinisin chókkewe mi rong ussun ena pwóróus, ra eis: “Epwe met ei kúkkún semirit epwe wiliiti?” (Luk 1:57-66) "
        "Jiowa a néúnéú Sekaraia le pélúweni ena kapas eis. "
        "Sipwe káé úlúngát mettóch a lamot ach sipwe aúcheani seni met Sekaraia a apasa. "
        "Ikkeei: (1) ewe liffang, ach kúna amanaw, (2) ach tufichin fel ngeni Jiowa, me (3) wisach le afalafala aramas."
    )
    eng = split_sentences(
        "“WHAT will this young child turn out to be?” (Luke 1:57-66) "
        "The neighbors and the relatives were curious about John, the son who was born miraculously to aged priest Zechariah and his elderly wife, Elizabeth, who had been barren. "
        "Jehovah used Zechariah to answer that question. "
        "From his message, we will learn about three things we should cherish: (1) the gift of salvation, (2) the privilege of sacred service, and (3) the responsibility to preach."
    )
    assert len(chk) == 5 and len(eng) == 4
    assert align_sentences(chk, eng) == [[1], [0], [2], [3], [3]]


def test_one_chuukese_to_two_english():
    chk = ["Atun a 30 ierin Jises, a papatais, me Jiowa a epiti ren ewe ngún mi fel me a wiliiti ewe Messaia mi pwonetiw. (Mat. 3:16, 17)",
           "A fókkun amwarar minne a fis!"]
    eng = ["The “powerful savior” was raised up when Jesus got baptized at age 30.",
           "At that time, Jehovah anointed him with holy spirit as the promised Messiah. (Matt. 3:16, 17)",
           "An exciting development indeed!"]
    assert align_sentences(chk, eng) == [[0, 1], [2]]


def test_gloss_breaks_ties():
    chk = ["Ewe mwán a tongei ewe tokter.", "Ewe nengngin a kkan ewe ik."]
    eng = ["The girl ate the fish.", "The man loved the doctor."]
    gloss = {"mwán": ["man"], "tongei": ["love"], "tokter": ["doctor"], "nengngin": ["girl"], "kkan": ["eat"], "ik": ["fish"]}.get
    assert align_sentences(chk, eng, lambda w: gloss(w, [])) == [[1], [0]]


def test_no_english():
    assert align_sentences(["A", "B"], []) == [[], []]
    assert align_sentences([], ["A"]) == []


def test_footnote_letter_splits_sentences():
    parts = split_sentences("But Zechariah did more than relate what his son, John, would do. a As we will see, it involves us today.")
    assert parts == ["But Zechariah did more than relate what his son, John, would do.", "As we will see, it involves us today."]


def test_question_markers_lead_their_question():
    assert split_sentences("2. (a) Me ren Luk 1:67-73, ifa ewe liffang? (b) Ié ewe chón amanaw?") == [
        "2. (a) Me ren Luk 1:67-73, ifa ewe liffang?",
        "(b) Ié ewe chón amanaw?",
    ]
