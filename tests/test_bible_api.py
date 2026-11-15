"""Scripture Lookup: citations as jw.org accepts them, verses from the uploaded Bibles only."""
import flask
import pytest

from src.api import bible


def test_parse_query_reads_jworg_style_citations():
    assert bible.parse_query("John 3:16, 17") == [(43, 3, [16, 17])]
    assert bible.parse_query("1Pe 3:1, 2, 15") == [(60, 3, [1, 2, 15])]
    assert bible.parse_query("Isa. 33:24; 35:5, 6") == [(23, 33, [24]), (23, 35, [5, 6])]
    assert bible.parse_query("Ps 23") == [(19, 23, None)]
    assert bible.parse_query("Jude") == [(65, 1, None)]
    assert bible.parse_query("Kölf. 37:29") == [(19, 37, [29])]
    assert bible.parse_query("Luke 1:67-73")[0][2] == list(range(67, 74))
    assert bible.parse_query("nonsense 3:1") == []


def test_spec_collapses_runs():
    assert bible._spec([1, 2, 3, 7]) == "1-3, 7"


@pytest.fixture
def client():
    app = flask.Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(bible.create_blueprint(lambda: None, lambda f: f, lambda text: {"dictionary": {"kot": {"english": "God"}}, "similar": {}, "phrases": {}}))
    return app.test_client()


def test_lookup_returns_both_languages_from_the_local_bibles(client):
    r = client.get("/api/bible/lookup?q=1Ti 2:14")
    assert r.status_code == 200
    p = r.get_json()["passages"][0]
    assert p["name"] == "1 Timothy" and p["chk_name"] == "1 Timoty" and p["chapter"] == 2
    assert p["verses"][0]["n"] == 14 and "Adam" in p["verses"][0]["en"] and p["verses"][0]["chk"].startswith("Pwal och, Atam")
    assert p["highlight"] == [14] and p["whole"] is False and p["source_chk"] == "nwt"
    assert p["maps"]["dictionary"]["kot"]["english"] == "God"


def test_hebrew_scriptures_use_liebenzell_for_chuukese(client):
    p = client.get("/api/bible/lookup?q=Isa 55:8, 9").get_json()["passages"][0]
    assert p["source_chk"] == "liebenzell" and [v["n"] for v in p["verses"]] == [8, 9]
    assert all(v["en"] for v in p["verses"])


def test_whole_chapter_with_neighbours(client):
    p = client.get("/api/bible/chapter?book=65&chapter=1&highlight=3").get_json()
    assert p["whole"] and p["prev"] == {"book": 64, "chapter": 1} and p["next"] == {"book": 66, "chapter": 1}
    assert p["highlight"] == [3] and len(p["verses"]) == 25
    assert client.get("/api/bible/chapter?book=66&chapter=23").status_code == 404


def test_unreadable_citation_is_said_plainly(client):
    r = client.get("/api/bible/lookup?q=xyz")
    assert r.status_code == 400 and "Could not read" in r.get_json()["error"]
    assert client.get("/api/bible/books").get_json()[18] == {"number": 19, "name": "Psalms", "chk_name": "Kölfel", "chapters": 150}
