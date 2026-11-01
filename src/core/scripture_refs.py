"""
Expand a scripture citation as outlines and articles write it ("2 Tim. 3:16,
17", "Ps. 37:29", "Isa. 33:24; 35:5, 6", "Luke 1:67-73") into the single
verses the verse lookup understands ("2 Timothy 3:16", "2 Timothy 3:17", …),
with full English book names.

Chuukese abbreviations (Kölf., Mat., Jon…) are mapped too, so a Chuukese
outline resolves to the same verses.
"""

from __future__ import annotations

import re

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark",
    "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians",
    "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
    "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation",
]

# Abbreviation (lowercase, no period) → canonical book. English official and
# common forms, then Chuukese forms seen on wol.jw.org.
_ALIASES: dict[str, str] = {}
for _b in BOOKS:
    _ALIASES[_b.lower()] = _b
_ALIASES.update({
    "gen": "Genesis", "ex": "Exodus", "exod": "Exodus", "lev": "Leviticus", "num": "Numbers", "deut": "Deuteronomy", "de": "Deuteronomy",
    "josh": "Joshua", "judg": "Judges", "jg": "Judges", "ru": "Ruth", "1 sam": "1 Samuel", "2 sam": "2 Samuel", "1 ki": "1 Kings", "2 ki": "2 Kings",
    "1 chron": "1 Chronicles", "2 chron": "2 Chronicles", "1 chr": "1 Chronicles", "2 chr": "2 Chronicles", "neh": "Nehemiah", "esth": "Esther",
    "ps": "Psalms", "psalm": "Psalms", "prov": "Proverbs", "pr": "Proverbs", "eccl": "Ecclesiastes", "ec": "Ecclesiastes", "song": "Song of Solomon",
    "ca": "Song of Solomon", "isa": "Isaiah", "jer": "Jeremiah", "lam": "Lamentations", "ezek": "Ezekiel", "eze": "Ezekiel", "dan": "Daniel", "da": "Daniel",
    "hos": "Hosea", "ho": "Hosea", "joe": "Joel", "am": "Amos", "obad": "Obadiah", "ob": "Obadiah", "jon": "Jonah", "mic": "Micah", "nah": "Nahum",
    "hab": "Habakkuk", "zeph": "Zephaniah", "zep": "Zephaniah", "hag": "Haggai", "zech": "Zechariah", "zec": "Zechariah", "mal": "Malachi",
    "matt": "Matthew", "mt": "Matthew", "mr": "Mark", "mk": "Mark", "lu": "Luke", "lk": "Luke", "joh": "John", "jn": "John", "ac": "Acts",
    "rom": "Romans", "ro": "Romans", "1 cor": "1 Corinthians", "2 cor": "2 Corinthians", "1 co": "1 Corinthians", "2 co": "2 Corinthians",
    "gal": "Galatians", "ga": "Galatians", "eph": "Ephesians", "php": "Philippians", "phil": "Philippians", "col": "Colossians",
    "1 thess": "1 Thessalonians", "2 thess": "2 Thessalonians", "1 th": "1 Thessalonians", "2 th": "2 Thessalonians",
    "1 tim": "1 Timothy", "2 tim": "2 Timothy", "1 ti": "1 Timothy", "2 ti": "2 Timothy", "tit": "Titus", "philem": "Philemon", "phm": "Philemon",
    "heb": "Hebrews", "jas": "James", "1 pet": "1 Peter", "2 pet": "2 Peter", "1 pe": "1 Peter", "2 pe": "2 Peter", "1 jo": "1 John", "2 jo": "2 John",
    "3 jo": "3 John", "rev": "Revelation", "re": "Revelation",
    # Chuukese (wol.jw.org lp-te) book abbreviations and names
    "ken": "Genesis", "keneses": "Genesis", "eks": "Exodus", "ekistos": "Exodus", "lef": "Leviticus", "nam": "Numbers", "tut": "Deuteronomy",
    "jos": "Joshua", "sou": "Judges", "rut": "Ruth", "1 sam.": "1 Samuel", "1 kin": "1 Kings", "2 kin": "2 Kings", "1 kro": "1 Chronicles", "2 kro": "2 Chronicles",
    "esra": "Ezra", "nee": "Nehemiah", "est": "Esther", "jop": "Job", "kölf": "Psalms", "kolf": "Psalms", "kf": "Psalms", "kölfel": "Psalms",
    "salf": "Proverbs", "salaf": "Ecclesiastes", "kölün": "Song of Solomon", "ais": "Isaiah", "aisea": "Isaiah", "jer.": "Jeremiah", "sen": "Lamentations",
    "esek": "Ezekiel", "tan": "Daniel", "tanie": "Daniel", "osea": "Hosea", "sow": "Joel", "amo": "Amos", "opa": "Obadiah", "jona": "Jonah",
    "mika": "Micah", "nau": "Nahum", "apa": "Habakkuk", "sef": "Zephaniah", "akai": "Haggai", "sek": "Zechariah", "mal.": "Malachi",
    "mat": "Matthew", "mattu": "Matthew", "mar": "Mark", "markus": "Mark", "luk": "Luke", "lukas": "Luke", "jon.": "John", "féf": "Acts", "fef": "Acts",
    "féféér": "Acts", "rom.": "Romans", "1 kor": "1 Corinthians", "2 kor": "2 Corinthians", "kal": "Galatians", "efi": "Ephesians", "fil": "Philippians",
    "kol": "Colossians", "1 tes": "1 Thessalonians", "2 tes": "2 Thessalonians", "1 tim.": "1 Timothy", "2 tim.": "2 Timothy", "tai": "Titus",
    "filim": "Philemon", "ipru": "Hebrews", "jem": "James", "1 pit": "1 Peter", "2 pit": "2 Peter", "1 jon": "1 John", "2 jon": "2 John", "3 jon": "3 John",
    "jut": "Jude", "pwár": "Revelation", "pwar": "Revelation", "pwárátá": "Revelation",
})
_ALIASES = {k.rstrip("."): v for k, v in _ALIASES.items()}

_PART = re.compile(r"^\s*([1-3]?\s?[^\d\s][^\d:]*?)\.?\s*(\d+)\s*:\s*(.+)$")
_CHAPTER_ONLY = re.compile(r"^\s*(\d+)\s*:\s*(.+)$")


def canonical_book(name: str) -> str | None:
    key = re.sub(r"\s+", " ", name.strip().lower()).rstrip(".")
    return _ALIASES.get(key)


def _verses(spec: str) -> list[int]:
    """'16, 17' → [16, 17]; '67-73' → [67..73]; '3a' → [3]."""
    out: list[int] = []
    for piece in re.split(r"\s*,\s*", spec.strip().rstrip(".")):
        piece = re.sub(r"[ab]\b", "", piece)
        m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", piece)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b >= a and b - a <= 40:
                out.extend(range(a, b + 1))
        elif piece.strip().isdigit():
            out.append(int(piece))
    return out


def expand(citation: str) -> list[tuple[str, str]]:
    """[(label, 'Book C:V'), …] for every verse of a citation. The label is
    how the verse is shown ('2 Timothy 3:16'); the second item is what the
    verse lookup takes. Unknown books give an empty list."""
    out: list[tuple[str, str]] = []
    book = None
    for part in re.split(r"\s*;\s*", (citation or "").strip()):
        if not part:
            continue
        m = _PART.match(part)
        if m:
            book = canonical_book(m.group(1))
            chapter, spec = m.group(2), m.group(3)
        else:
            m2 = _CHAPTER_ONLY.match(part)
            if not m2:
                continue
            chapter, spec = m2.group(1), m2.group(2)
        if not book:
            continue
        for v in _verses(spec):
            out.append((f"{book} {chapter}:{v}", f"{book} {chapter}:{v}"))
    return out


__all__ = ["expand", "canonical_book", "BOOKS"]
