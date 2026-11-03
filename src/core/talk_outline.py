"""
Turn a talk outline (pasted text, or text extracted from a PDF or Word file)
into a structure the Talk Builder can hang sentences on.

An outline is a title, optionally a theme scripture, then main points with
sub-points beneath them, each possibly citing scriptures and carrying a time
mark such as "(5 min.)". Numbering styles vary (1. / I. / A. / • / –), and
sub-points are usually indented or lettered. The parser is deliberately
forgiving: anything it cannot place becomes a sub-point of the current main
point, and the person tidies the result on the page.

    parse_outline(text, language="en") -> {
        "title": str, "theme_scripture": str, "language": "en" | "chk",
        "points": [{"id", "label", "text", "scriptures": [..], "minutes",
                    "children": [{"id", "label", "text", "scriptures", "minutes"}]}],
        "total_minutes": int | None,
    }
"""

from __future__ import annotations

import re

from src.core.outline_refs import find_references
from src.utils.scripture_parser import get_scripture_reference_pattern

_REF = re.compile(get_scripture_reference_pattern())
_TIME = re.compile(r"\(\s*(\d{1,3})\s*min(?:ute)?s?\.?\s*\)|\b(\d{1,3})\s*min\.(?=\s|$)", re.I)
_MAIN = re.compile(r"^\s*(?:(\d{1,2})[.)]|([IVX]{1,4})[.)]|§)\s+(.*)$")
_SUB = re.compile(r"^\s*(?:([A-Za-z])[.)]|[•·\-–—*]|(\d{1,2})[.)](\d{1,2})[.)]?)\s+(.*)$")
_NOTE = re.compile(r"^\s*(?:PLEASE\s+)?NOTE\s*:", re.I)
_TOTAL = re.compile(r"TO BE COVERED IN\s+(\d{1,3})\s*MIN", re.I)
_BOILER = re.compile(r"^\s*(?:\[?Adhere closely|TO BE COVERED IN|©|S-\d+-[A-Z]+\b|\(?No\.\s*\d+\)?\s*$)", re.I)
_NUMBER = re.compile(r"^\s*(No\.\s*\d+)\s*(?=\S)")
_LANG_CHK = re.compile(r"\b(me|ngeni|ewe|ekkewe|pwe|iwe|nge|ren|ach|án|wóón|lón|seni|aramas|Jiowa|Kot)\b")


def detect_language(text: str) -> str:
    hits = len(_LANG_CHK.findall(text or ""))
    words = max(len(re.findall(r"\w+", text or "")), 1)
    return "chk" if hits / words > 0.04 else "en"


def _scriptures(text: str) -> list[str]:
    """Citations in the text, one per entry; "Job 26:7; Isa. 40:22" gives two,
    while "Ps. 62:8; 65:2" (same book) stays one."""
    out = []
    for m in _REF.findall(text or ""):
        parts = re.split(r";\s*(?=[1-3]?\s?[A-ZÀ-Þ])", re.sub(r"\s+", " ", m).strip())
        out.extend(p.strip() for p in parts if p.strip())
    return out


def _minutes(text: str) -> int | None:
    m = _TIME.search(text or "")
    return int(m.group(1) or m.group(2)) if m else None


def _clean(text: str) -> str:
    text = _TIME.sub("", text or "")
    text = re.sub(r"\(\s*\)", "", text)  # parentheses emptied by removing a citation
    return re.sub(r"\s+", " ", text).strip(" :;,-–—")


def is_heading(text: str) -> bool:
    """A section heading of a printed outline: a line set entirely in capitals
    ("TRUE FAITH IS SHOWN BY ACTIONS"), at least four letters long."""
    letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", text or "")
    return len(letters) >= 4 and letters.upper() == letters


def restructure(outline: dict) -> dict:
    """Give an outline whose headings were lost as sub-points their structure
    back: every capitalised heading becomes a section, the lines after it its
    points; "PLEASE NOTE" text becomes the outline's note; the printed
    footer (timing reminder, copyright, form number) is dropped. Point ids
    are kept, so lines collected under them stay attached. Outlines with no
    capitalised heading are returned unchanged."""
    points = outline.get("points") or []
    flat = []
    for p in points:
        flat.append(p)
        flat.extend(p.get("children") or [])
    if not any(is_heading(p.get("text", "")) for p in flat):
        return outline
    sections, note, dropped = [], [], []
    total = outline.get("total_minutes")
    for p in flat:
        text = p.get("text", "")
        m_total = _TOTAL.search(text)
        if m_total:
            total = int(m_total.group(1))
            dropped.append(p["id"])
            continue
        if _NOTE.match(text):
            note.append(_NOTE.sub("", text).strip())
            dropped.append(p["id"])
            continue
        if _BOILER.match(text):
            dropped.append(p["id"])
            continue
        if is_heading(text) or not sections:
            p["children"] = []
            sections.append(p)
        else:
            p.pop("children", None)
            sections[-1]["children"].append(p)
    out = dict(outline)
    out["points"] = sections
    out["note"] = " ".join(note) or outline.get("note") or ""
    out["dropped"] = dropped
    out["total_minutes"] = total or sum(s.get("minutes") or 0 for s in sections) or None
    m = _NUMBER.match(out.get("title") or "")
    if m:
        out["number"] = m.group(1)
        out["title"] = out["title"][m.end():].strip()
    return out


def parse_outline(text: str, language: str | None = None) -> dict:
    lines = [ln.rstrip() for ln in (text or "").replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln.strip()]
    lang = language or detect_language(text)
    out: dict = {"title": "", "theme_scripture": "", "language": lang, "points": [], "total_minutes": None}
    if not lines:
        return out

    # Title: first line, unless it is already a numbered point.
    first = lines[0]
    if not _MAIN.match(first) and not _SUB.match(first):
        out["title"] = _clean(_REF.sub("", first)) or first.strip()
        refs = _scriptures(first)
        if refs:
            out["theme_scripture"] = refs[0]
        lines = lines[1:]
        # A lone scripture line under the title is the theme text.
        if lines and _REF.fullmatch(lines[0].strip().rstrip(".")):
            out["theme_scripture"] = lines[0].strip().rstrip(".")
            lines = lines[1:]

    points: list[dict] = []
    counter = 0

    def new_point(label: str, body: str) -> dict:
        nonlocal counter
        counter += 1
        return {"id": f"p{counter}", "label": label, "text": _clean(body), "scriptures": _scriptures(body), "references": find_references(body), "minutes": _minutes(body), "children": []}

    for raw in lines:
        indented = raw.startswith((" ", "\t"))
        m_main = _MAIN.match(raw)
        m_sub = _SUB.match(raw)
        if m_main and not indented:
            label = m_main.group(1) or m_main.group(2) or ""
            points.append(new_point(label, m_main.group(3)))
        elif m_sub or indented:
            body = m_sub.group(4) if m_sub else raw.strip()
            label = (m_sub.group(1) or (f"{m_sub.group(2)}.{m_sub.group(3)}" if m_sub and m_sub.group(2) else "")) if m_sub else ""
            if not points:
                points.append(new_point("", body))
            else:
                child = new_point(label, body)
                child.pop("children")
                points[-1]["children"].append(child)
        elif m_main:
            points.append(new_point(m_main.group(1) or m_main.group(2) or "", m_main.group(3)))
        else:
            # Plain sentence: a main point if nothing is open yet, else a sub-point.
            if not points:
                points.append(new_point("", raw))
            else:
                child = new_point("", raw)
                child.pop("children")
                points[-1]["children"].append(child)

    total = sum(p["minutes"] or 0 for p in points) + sum(c["minutes"] or 0 for p in points for c in p["children"] if not p["minutes"])
    out["points"] = points
    out["total_minutes"] = total or None
    return restructure(out)


def extract_text(filename: str, data: bytes) -> str:
    """Plain text from a .txt, .docx or .pdf upload."""
    name = (filename or "").lower()
    if name.endswith(".docx"):
        import io
        import zipfile
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml")
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paras = []
        for p in ET.fromstring(xml).iter("{%s}p" % ns["w"]):
            indent = p.find(".//w:ind", ns)
            level = p.find(".//w:ilvl", ns)
            text = "".join(t.text or "" for t in p.iter("{%s}t" % ns["w"])).strip()
            if not text:
                continue
            lvl = int(level.get("{%s}val" % ns["w"])) if level is not None else 0
            if lvl == 0 and indent is not None and int(indent.get("{%s}left" % ns["w"], "0") or 0) > 300:
                lvl = 1
            paras.append(("  " * lvl) + text)
        return "\n".join(paras)
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:  # pragma: no cover
            from PyPDF2 import PdfReader  # type: ignore
        import io

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8", errors="replace")


__all__ = ["parse_outline", "extract_text", "detect_language"]
