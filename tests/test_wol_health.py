"""The wol.jw.org circuit breaker: opens after a few failures, lets one probe
through after the cooling-off period, closes on success."""

from src.core import wol_health


def setup_function():
    wol_health.reset()


def teardown_function():
    wol_health.reset()


def test_opens_after_consecutive_failures_and_allows_one_probe(monkeypatch):
    assert wol_health.available()
    for _ in range(wol_health.FAILURES_TO_OPEN):
        wol_health.record_failure()
    assert wol_health.is_open()
    assert not wol_health.available()
    # Cooling-off over: exactly one probe gets through until it reports back.
    now = [1_000_000.0]
    monkeypatch.setattr(wol_health.time, "monotonic", lambda: now[0])
    wol_health.reset()
    for _ in range(wol_health.FAILURES_TO_OPEN):
        wol_health.record_failure()
    now[0] += wol_health.COOL_OFF_SECONDS + 1
    assert wol_health.available()
    assert not wol_health.available()
    wol_health.record_success()
    assert wol_health.available() and not wol_health.is_open()


def test_success_resets_the_failure_count():
    wol_health.record_failure()
    wol_health.record_failure()
    wol_health.record_success()
    wol_health.record_failure()
    assert not wol_health.is_open()


def test_chapter_fetch_skips_wol_while_breaker_open(monkeypatch):
    from src.core import wol_bible

    calls = []
    monkeypatch.setattr(wol_bible.requests, "get", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("should not be called")))
    for _ in range(wol_health.FAILURES_TO_OPEN):
        wol_health.record_failure()
    assert wol_bible._fetch("chk", 40, 5) is None
    assert calls == []


def test_verse_with_fetch_false_never_contacts_wol(monkeypatch):
    """A page opening reads stored verses only."""
    from src.core import wol_bible

    monkeypatch.setattr(wol_bible.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("wol.jw.org must not be contacted")))
    wol_bible._memory.clear()
    assert wol_bible.verse(None, "chk", 40, 5, 3, fetch=False) == ""
