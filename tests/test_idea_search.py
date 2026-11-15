"""Meaning search for talk-line alternatives: ideas, subjects, roots, scoring."""
import numpy as np

from src.core import idea_search as ids

LINE = "he understood the consequences of disobedience, yet he still chose to disobey Jehovah and rejected his love"


def test_ideas_are_clauses_without_their_lead_in():
    assert ids.ideas(LINE) == ["understood the consequences of disobedience", "disobey Jehovah", "rejected his love"]
    assert ids.ideas("Noah built the ark because he trusted Jehovah.") == ["Noah built the ark", "trusted Jehovah"]


def test_subjects_come_from_the_line_and_its_context():
    assert ids.subjects(LINE, "Adam and Eve in Eden (Genesis 3:6)") == ["Jehovah", "Adam", "Eve"]
    assert ids.subjects("", "Noah and his family entered the ark") == ["Noah"]


def test_roots_meet_across_word_forms():
    assert ids.root("disobedience") == ids.root("disobey") == ids.root("disobedient")
    assert ids.root("consequences") == ids.root("consequence")
    assert ids.roots("rejected his love") == {"reject", "love"}


class FakeCol:
    def __init__(self, rows):
        self.rows = rows

    def find(self, q=None, proj=None):
        return iter(self.rows)


class FakeDB:
    def __init__(self):
        self.phrases_collection = FakeCol([
            {"chuukese_phrase": "Atam a silei met epwe fis ika esap álleasochis", "english_translation": "Adam knew the result of disobedience", "source": "w20"},
            {"chuukese_phrase": "A tongei pwúnúwan", "english_translation": "He loved his wife", "source": "w20"},
            {"chuukese_phrase": "Ra álleasochis ngeni Jiowa", "english_translation": "They disobeyed Jehovah and turned away from his love", "source": "w21"},
            {"chuukese_phrase": "Ewe sakau a féér", "english_translation": "The boat was built", "source": "w21"},
        ])
        self.db = {"article_analysis_paragraphs": FakeCol([]), "conversation_phrases": FakeCol([])}


class FakeEmbedder:
    """Vectors from word roots, so 'meaning' is overlap of roots: enough to test the plumbing."""
    model = object()
    vocab = ["adam", "knew", "result", "disobe", "love", "wife", "jehovah", "turn", "boat", "built", "conseq", "reject", "underst"]

    def load(self):
        pass

    def encode(self, texts):
        out = []
        for t in texts:
            v = np.array([1.0 if r in ids.roots(t) else 0.0 for r in self.vocab], dtype="float32")
            out.append(v / (np.linalg.norm(v) or 1.0))
        return np.stack(out)


def test_search_ranks_by_meaning_phrases_and_subject(tmp_path):
    index = ids.IdeaIndex(FakeDB(), FakeEmbedder(), cache=tmp_path / "idx.npz")
    index._build()
    assert index.status == "ready" and len(index.rows) == 4 and (tmp_path / "idx.npz").exists()
    out = index.search(LINE, "", "Adam in Eden")
    assert out["index"] == "ready" and out["about"][:2] == ["Jehovah", "Adam"]
    top = [it["en"] for it in out["items"]]
    assert top[0] in ("They disobeyed Jehovah and turned away from his love", "Adam knew the result of disobedience")
    assert "The boat was built" not in top
    hit = next(it for it in out["items"] if it["en"].startswith("They disobeyed"))
    assert "disobey Jehovah" in hit["matched"] and hit["named"]


def test_search_before_the_index_is_ready_uses_roots_and_phrases():
    index = ids.IdeaIndex(FakeDB(), FakeEmbedder())
    index.rows = index._collect()
    index.row_roots = [ids.roots(r["en"]) for r in index.rows]
    out = index.search(LINE)
    assert out["index"] == "building"
    assert out["items"] and out["items"][0]["en"] != "The boat was built"
