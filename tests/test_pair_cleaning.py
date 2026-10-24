"""Tests for the training-pair cleaning rules."""

from src.training.pair_cleaning import clean_pair, clean_pairs


def test_strips_matching_verse_numbers_and_footnote_markers():
    chk = "2 “Kopwe mak ngeni ewe chón kúné lón ewe mwichefel lón Efisus: Ikkeei met"
    eng = "2 “To the angel + of the congregation in Ephʹe·sus + write: These are the things"
    out = clean_pair(chk, eng, "translation_game")
    assert out == (
        "“Kopwe mak ngeni ewe chón kúné lón ewe mwichefel lón Efisus: Ikkeei met",
        "“To the angel of the congregation in Ephʹe·sus write: These are the things",
    )


def test_leading_plus_verse_number_is_stripped():
    out = clean_pair("11 Emén mi wor selingan, epwe aúseling", "+ 11 Let the one who has an ear hear", "translation_game")
    assert out == ("Emén mi wor selingan, epwe aúseling", "Let the one who has an ear hear")


def test_mismatched_verse_numbers_are_dropped():
    assert clean_pair("13 Ina minne, úa áeá kapas áwewe", "+ 14 And the prophecy of Isaiah", "article_analysis") is None


def test_article_analysis_one_sided_verse_number_is_dropped():
    assert clean_pair("Nge ié ese wor an, Kot epwe angei.", "+ 13 That is why I speak to them", "article_analysis") is None
    # other sources keep it (the number is just stripped)
    assert clean_pair("Nge ié ese wor an, Kot epwe angei.", "13 That is why I speak to them", "translation_game") == (
        "Nge ié ese wor an, Kot epwe angei.",
        "That is why I speak to them",
    )


def test_reference_lists_are_dropped():
    assert clean_pair("Mattu 10:1-10;; 10:35-40;; 20:24, 25;; 4:13;", "Matthew 10:1-10; Mark 3:13-19; 10:35-40", "article_analysis") is None
    assert clean_pair("119:2, 14.", "119 2 fourteen", "article_analysis") is None


def test_assembled_glosses_are_dropped():
    assert clean_pair("Pwata ka erá ena?", "why you are / you were erá so, like that", "article_analysis") is None
    assert clean_pair("2 Iwe a poputá le asukuler", "2 then, so, therefore he, she, it start (indicates", "article_analysis") is None


def test_homonym_sense_markers_are_stripped():
    assert clean_pair("war (2)", "root (of plant/tree)", "dictionary") == ("war", "root (of plant/tree)")
    assert clean_pair("i (1)", "he, she, it", "dictionary") == ("i", "he, she, it")


def test_longer_chuukese_sentence_is_kept():
    chk = "Ai Samol mi Lapalap, kopwe ümöümöch ngenikem, äm aipwe pwal tongeni manaw."
    assert clean_pair(chk, "O Jehovah, show us favor.", "dictionary") == (chk, "O Jehovah, show us favor.")


def test_dictionary_words_and_numbers_are_kept():
    assert clean_pair("meneekem", "satisfied with us (exclusive)", "dictionary") == ("meneekem", "satisfied with us (exclusive)")
    assert clean_pair("úlúpúkú inik me rúánú", "334", "dictionary") == ("úlúpúkú inik me rúánú", "334")
    assert clean_pair("ngenikich", "to give to us (verb + kick)", "dictionary") == ("ngenikich", "to give to us (verb + kick)")


def test_clean_bible_verse_is_untouched():
    chk = "Ei puk, puken uruwoon Jises Kraist, i mwirimwirin Tafit, mwirimwirin Eperiam we:"
    eng = "The book of the history of Jesus Christ, son of David, son of Abraham:"
    assert clean_pair(chk, eng, "nwt_bible") == (chk, eng)


def test_bad_length_ratio_sentence_is_dropped():
    chk = "A pwal tiinieiló ái úpwe ereniir ussun ewe fansoun Jiowa a tongeni efeiéchú aramas meinisin"
    assert clean_pair(chk, "to preach.", "nwt_bible") is None


def test_clean_pairs_reports_stats():
    pairs = [
        {"chuukese": "ran annim", "english": "good day", "source": "phrase"},
        {"chuukese": "13 Ina minne", "english": "+ 14 And the", "source": "article_analysis"},
        {"chuukese": "2 Kopwe mak", "english": "2 Write + now", "source": "translation_game"},
    ]
    stats = {}
    out = clean_pairs(pairs, stats)
    assert [p["english"] for p in out] == ["good day", "Write now"]
    assert stats == {"input": 3, "kept": 2, "dropped": 1, "normalised": 1}
