"""
Parse the wol.jw.org publications the Conversation Builder draws on, in
Chuukese and English, into structured bilingual records.

Sources (document ids are shared by the two language editions):

* ``Love People—Make Disciples`` (lmd): twelve lessons (1102023301–1102023312),
  appendix A "Truths We Love to Teach" (1102023316) and "Should You End the
  Conversation?" (1102023317).
* Meeting workbook weeks (2020YYNNN): the "Apply Yourself to the Field
  Ministry" parts, each naming a setting and the lmd lesson point to apply.

Paragraphs pair by ``data-pid``; the English of a paragraph is the paragraph
with the same pid. Everything here is pure parsing; fetching lives in
``scripts/harvest_conversation_sources.py`` behind the polite fetcher.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from src.core.wol_search import _clean, _plain

LMD = {
    "lessons": [str(1102023300 + n) for n in range(1, 13)],
    "truths": "1102023316",
    "end": "1102023317",
}
LMD_LESSON_RE = re.compile(r"lmd\s+(?:lesson|lesen)\s+(\d+)\s+(?:points?|nampa)\s+([\d]+(?:\s*[-–]\s*\d+)?)", re.I)
LFF_RE = re.compile(r"lff\s+(?:lesson|lesen)\s+(\d+)(?:\s+(?:points?|nampa)\s+([\d]+(?:\s*[-–]\s*\d+)?))?", re.I)
_NUMBERED = re.compile(r"^\s*(\d{1,2})\.\s+")
_TIME = re.compile(r"^\s*\((\d+)\s*min\.?\)\s*", re.I)
_PAREN_REF = re.compile(r"\(\s*(lmd|lff)[^)]*\)", re.I)
_DASH_REFS = re.compile(r"\s*[—–]\s*(?=[^—–]*\d+:\d+)")


def _pids(html: str) -> dict[str, tuple[str, str]]:
    """{pid: (tag, text)} for every pid-bearing element of the article."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup
    out: dict[str, tuple[str, str]] = {}
    for el in article.select("[data-pid]"):
        pid = el.get("data-pid")
        text = _plain(el)
        if pid and text and pid not in out:
            out[pid] = (el.name, text)
    return out


def _ordered(html: str) -> list[tuple[str, str, str]]:
    """[(pid, tag, text)] in document order."""
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article") or soup
    out, seen = [], set()
    for el in article.select("[data-pid]"):
        pid = el.get("data-pid")
        text = _plain(el)
        if pid and text and pid not in seen:
            seen.add(pid)
            out.append((pid, el.name, text))
    return out


def _title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    return _clean(h1.get_text(" ", strip=True)) if h1 else ""


def split_statement(text: str) -> tuple[str, str]:
    """'2. The earth will never be destroyed.—Ps. 104:5; Eccl. 1:4.' →
    ('The earth will never be destroyed.', 'Ps. 104:5; Eccl. 1:4')."""
    body = _NUMBERED.sub("", text).strip()
    parts = _DASH_REFS.split(body, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip().rstrip(".").strip()
    return body, ""


# ---------------------------------------------------------------------------
# Truths We Love to Teach
# ---------------------------------------------------------------------------


def parse_truths(chk_html: str, en_html: str) -> dict:
    """Subjects with their numbered statements and scriptures, bilingual.

    Returns ``{"title": {chk, en}, "intro": {chk, en}, "subjects": [
        {"id", "title": {chk, en}, "statements": [
            {"n", "pid", "chk", "en", "scriptures": {chk, en}}]}]}``.
    """
    chk, en = _pids(chk_html), _pids(en_html)
    subjects: list[dict] = []
    current: dict | None = None
    intro = {"chk": "", "en": ""}
    for pid, tag, text in _ordered(en_html):
        if tag == "h1":
            continue
        chk_text = chk.get(pid, ("", ""))[1]
        if tag == "h2":
            current = {
                "id": re.sub(r"[^a-z]+", "-", text.lower()).strip("-"),
                "title": {"chk": chk_text.title() if chk_text.isupper() else chk_text, "en": text.title()},
                "statements": [],
            }
            subjects.append(current)
            continue
        m = _NUMBERED.match(text)
        if current is not None and m:
            en_body, en_refs = split_statement(text)
            chk_body, chk_refs = split_statement(chk_text)
            current["statements"].append(
                {
                    "n": int(m.group(1)),
                    "pid": pid,
                    "chk": chk_body,
                    "en": en_body,
                    "scriptures": {"chk": chk_refs, "en": en_refs},
                }
            )
        elif current is None and tag == "p" and len(text) > 80 and not intro["en"]:
            intro = {"chk": chk_text, "en": text}
    return {"title": {"chk": _title(chk_html), "en": _title(en_html)}, "intro": intro, "subjects": subjects}


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------


def parse_lesson(chk_html: str, en_html: str, number: int) -> dict:
    """One lmd lesson: stage, title, principle, and its numbered points with
    their bullet items (quoted items are phrases one can say or ask).

    Returns ``{"number", "stage": {chk, en}, "title": {chk, en},
    "principle": {chk, en}, "sections": [{"heading": {chk, en},
    "points": [{"n", "pid", "chk", "en", "items": [{"pid", "chk", "en",
    "quoted"}]}]}], "see_also": {chk, en}}``.
    """
    chk = _pids(chk_html)
    rows = _ordered(en_html)
    out: dict = {
        "number": number,
        "stage": {"chk": "", "en": ""},
        "title": {"chk": _title(chk_html), "en": _title(en_html)},
        "principle": {"chk": "", "en": ""},
        "sections": [],
        "see_also": {"chk": "", "en": ""},
    }
    section: dict | None = None
    point: dict | None = None
    see_also = False
    for pid, tag, text in rows:
        chk_text = chk.get(pid, ("", ""))[1]
        if tag == "h1":
            continue
        if tag == "h3" and text.strip().upper().startswith("SEE ALSO"):
            see_also = True
            continue
        if see_also:
            out["see_also"] = {"chk": chk_text, "en": text}
            see_also = False
            continue
        if tag == "h2":
            section = {"heading": {"chk": chk_text, "en": text}, "points": []}
            out["sections"].append(section)
            point = None
            continue
        if section is None:
            if text.isupper() and not out["stage"]["en"]:
                out["stage"] = {"chk": chk_text.title(), "en": text.title()}
            elif text.lower().startswith("principle") or chk_text.lower().startswith("kapasen emmwen"):
                out["principle"] = {"chk": chk_text, "en": text}
            continue
        m = _NUMBERED.match(text)
        if m:
            point = {"n": int(m.group(1)), "pid": pid, "chk": _NUMBERED.sub("", chk_text), "en": _NUMBERED.sub("", text), "items": []}
            section["points"].append(point)
        elif point is not None:
            quoted = text[:1] in "‘“\"'" or chk_text[:1] in "‘“\"'"
            point["items"].append({"pid": pid, "chk": chk_text, "en": text, "quoted": quoted})
        else:
            section["points"].append({"n": None, "pid": pid, "chk": chk_text, "en": text, "items": []})
    return out


def parse_plain(chk_html: str, en_html: str) -> dict:
    """A short article as paired paragraphs: {"title": {chk, en},
    "paragraphs": [{"pid", "tag", "chk", "en"}]}."""
    chk = _pids(chk_html)
    paragraphs = []
    for pid, tag, text in _ordered(en_html):
        if tag == "h1":
            continue
        paragraphs.append({"pid": pid, "tag": tag, "chk": chk.get(pid, ("", ""))[1], "en": text})
    return {"title": {"chk": _title(chk_html), "en": _title(en_html)}, "paragraphs": paragraphs}


# ---------------------------------------------------------------------------
# Meeting workbook weeks
# ---------------------------------------------------------------------------

_MONTHS = "january february march april may june july august september october november december".split()
_WEEK_RE = re.compile(
    r"^\s*([A-Z]+)\s+(\d{1,2})\s*[-–]\s*(?:([A-Z]+)\s+)?(\d{1,2})\s*$", re.I
)


def week_dates(title: str, year: int) -> tuple[str, str] | None:
    """'JANUARY 27–FEBRUARY 2' + 2025 → ('2025-01-27', '2025-02-02')."""
    m = _WEEK_RE.match(title or "")
    if not m:
        return None
    m1, d1, m2, d2 = m.group(1).lower(), int(m.group(2)), (m.group(3) or m.group(1)).lower(), int(m.group(4))
    if m1 not in _MONTHS or m2 not in _MONTHS:
        return None
    y2 = year + 1 if _MONTHS.index(m2) < _MONTHS.index(m1) else year
    return f"{year:04d}-{_MONTHS.index(m1) + 1:02d}-{d1:02d}", f"{y2:04d}-{_MONTHS.index(m2) + 1:02d}-{d2:02d}"


def _parse_ref(text: str) -> dict:
    out: dict = {}
    m = LMD_LESSON_RE.search(text)
    if m:
        out["lmd"] = {"lesson": int(m.group(1)), "points": re.sub(r"\s", "", m.group(2))}
    m = LFF_RE.search(text)
    if m:
        out["lff"] = {"lesson": int(m.group(1)), "points": re.sub(r"\s", "", m.group(2) or "")}
    return out


def parse_workbook_week(chk_html: str, en_html: str, doc_id: str, year: int) -> dict:
    """The field-ministry parts of one workbook week.

    Returns ``{"doc_id", "title": {chk, en}, "start", "end", "parts": [
        {"n", "title": {chk, en}, "minutes", "setting": {chk, en},
         "refs": {"lmd": {lesson, points}, "lff": {...}}}]}``.
    """
    chk = _pids(chk_html)
    rows = _ordered(en_html)
    title_en = _title(en_html)
    dates = week_dates(title_en, year)
    parts: list[dict] = []
    in_section = False
    part: dict | None = None
    for pid, tag, text in rows:
        chk_text = chk.get(pid, ("", ""))[1]
        if tag == "h2":
            in_section = "FIELD MINISTRY" in text.upper()
            part = None
            continue
        if not in_section:
            continue
        if tag == "h3":
            m = _NUMBERED.match(text)
            part = {
                "n": int(m.group(1)) if m else None,
                "title": {"chk": _NUMBERED.sub("", chk_text), "en": _NUMBERED.sub("", text)},
                "minutes": None,
                "setting": {"chk": "", "en": ""},
                "refs": {},
            }
            parts.append(part)
            continue
        if part is None or tag != "p":
            continue
        tm = _TIME.match(text)
        if tm:
            part["minutes"] = int(tm.group(1))
        part["refs"] = {**part["refs"], **_parse_ref(text)}

        def setting(s: str) -> str:
            s = _TIME.sub("", s)
            s = _PAREN_REF.sub("", s)
            s = LFF_RE.sub("", s).lstrip(" .")
            s = _clean(s).strip(" .")
            return s + "." if s else ""

        part["setting"] = {"chk": setting(chk_text), "en": setting(text)}
    return {
        "doc_id": doc_id,
        "title": {"chk": _title(chk_html), "en": title_en},
        "start": dates[0] if dates else None,
        "end": dates[1] if dates else None,
        "parts": parts,
    }


__all__ = [
    "LMD",
    "parse_truths",
    "parse_lesson",
    "parse_plain",
    "parse_workbook_week",
    "split_statement",
    "week_dates",
]
