"""Scripture word links: spelling matches first, then meaning, one partner each."""
import numpy as np

from src.core import word_links as wl


def test_spelling_rules():
    assert wl.spelled_alike(wl.stem("pregnancy"), wl.stem("pregnant"))
    assert wl.spelled_alike(wl.stem("loved"), wl.stem("love"))
    assert wl.spelled_alike(wl.stem("thoughts"), wl.stem("thought"))
    assert not wl.spelled_alike(wl.stem("world"), wl.stem("word"))
    assert wl.gloss_alternatives("after; afterwards (adv.); later or next") == ["after", "afterwards", "later", "next"]
    assert wl.stem("gave") == wl.stem("give") == "give" and wl.stem("Children") == "child"


DICT = {"kot": {"english": "god"}, "tongei": {"english": "to love; love"}, "fénúfan": {"english": "world; earth"}, "néún": {"english": "his child"}, "weiresin": {"english": "difficulty of"}, "pwopwo": {"english": "pregnant"}}


def test_spelling_links_without_an_embedder():
    out = wl.Linker(None).link("Pokiten Kot a tongei fénúfan, a fangoló Néún", "For God loved the world so much that he gave his Son", DICT)
    chk, en = wl.words("Pokiten Kot a tongei fénúfan, a fangoló Néún"), wl.words("For God loved the world so much that he gave his Son")
    pairs = {chk[i]: en[out["en"].index(p)] for i, p in enumerate(out["chk"]) if p is not None}
    assert pairs == {"Kot": "God", "tongei": "loved", "fénúfan": "world"} and out["semantic"] is False


def fake_embed(texts):
    sim = {"difficulty": "pain", "pain": "difficulty", "child": "son", "son": "child"}
    vocab = sorted({t.lower() for t in texts} | set(sim))
    out = []
    for t in texts:
        v = np.zeros(len(vocab), dtype="float32")
        v[vocab.index(t.lower())] = 1.0
        if t.lower() in sim:
            v[vocab.index(sim[t.lower()])] = 0.6
        out.append(v / np.linalg.norm(v))
    return np.stack(out)


def test_meaning_links_what_spelling_misses():
    out = wl.Linker(fake_embed).link("weiresin om pwopwo, Néún", "the pain of your pregnancy, his Son", DICT)
    chk, en = wl.words("weiresin om pwopwo, Néún"), wl.words("the pain of your pregnancy, his Son")
    pairs = {chk[i]: en[out["en"].index(p)] for i, p in enumerate(out["chk"]) if p is not None}
    assert pairs == {"weiresin": "pain", "pwopwo": "pregnancy", "Néún": "Son"} and out["semantic"]


LEXICON = {
    "by_norm": {"apiluku": {"ápilúkú"}, "luku": {"lúkú"}, "api": {"ápi"}, "kuni": {"kúni"}},
    "english": {"ápilúkú": "hope; to hope", "lúkú": "faith; to believe", "ápi": "", "kúni": "to see"},
}


def test_base_words_come_from_the_dictionary_and_the_english_of_the_verse():
    assert [h for h, _g in wl.base_candidates("ápilúkúni", LEXICON)] == ["ápilúkú", "lúkú", "kúni"]
    assert wl.base_candidates("apilükü", LEXICON) == [("lúkú", "faith; to believe")]  # umlauts are accents
    out = wl.Linker(None).link("ra ápilúkúni Kot", "they hoped in God", {"kot": {"english": "God"}}, LEXICON)
    chk, en = wl.words("ra ápilúkúni Kot"), wl.words("they hoped in God")
    pairs = {chk[i]: en[out["en"].index(p)] for i, p in enumerate(out["chk"]) if p is not None}
    assert pairs == {"ápilúkúni": "hoped", "Kot": "God"}
    assert out["bases"] == [None, {"word": "ápilúkú", "english": "hope"}, None]
    # Without English support no base is shown: the dictionary is read, never interpreted.
    out = wl.Linker(None).link("ra ápilúkúni", "they ran", {}, LEXICON)
    assert out["bases"] == [None, None] and out["pairs"] == 0


def test_bases_are_never_justified_by_meaning_alone():
    lexicon = {"by_norm": {"iten": {"iten"}}, "english": {"iten": "name"}}
    out = wl.Linker(fake_embed).link("pokiten", "for him", {}, lexicon)
    assert out["pairs"] == 0 and out["bases"] == [None]
