#!/usr/bin/env python3
"""
Import the New World Translation from the uploaded files into
data/bible/nwt_en.json + nwt_chk_gs.json and the Cosmos `bible_chapters`
collection (lang "en" for Genesis–Revelation, lang "chk" for
Matthew–Revelation), so the app never fetches or translates a verse.

    .venv/bin/python scripts/import_nwt_bible.py ~/Downloads/nwt_E.pdf ~/Downloads/nwt_TE.epub [--no-db] [--from-json]

Prints a check of verse counts per chapter: English against the Chuukese
EPUB (Matthew–Revelation) and against the Liebenzell Paipel (Genesis–Malachi).
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core import liebenzell_bible as lb  # noqa: E402
from src.core import nwt_bible as nb  # noqa: E402


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def counts(bible):
    return {int(b): {int(c): len(v) for c, v in chs.items()} for b, chs in bible.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("epub", nargs="?")
    ap.add_argument("--no-db", action="store_true")
    ap.add_argument("--from-json", action="store_true", help="skip parsing; import the saved JSON files")
    args = ap.parse_args()

    if args.from_json:
        en = json.loads(nb.EN_FILE.read_text())["books"]
        chk = json.loads(nb.CHK_FILE.read_text())["books"]
    else:
        log("Parsing the English PDF…")
        en = nb.parse_pdf(args.pdf, log=log)
        nb.save(en, nb.EN_FILE, nb.SOURCE_EN)
        log(f"English: {len(en)} books, {sum(len(c) for c in en.values())} chapters, {sum(len(v) for c in en.values() for v in c.values())} verses → {nb.EN_FILE.name}")
        log("Parsing the Chuukese EPUB…")
        chk = nb.parse_epub(args.epub)
        nb.save(chk, nb.CHK_FILE, nb.SOURCE_CHK)
        log(f"Chuukese: {len(chk)} books, {sum(len(c) for c in chk.values())} chapters, {sum(len(v) for c in chk.values() for v in c.values())} verses → {nb.CHK_FILE.name}")

    # verse-count check
    en_c, chk_c = counts(en), counts(chk)
    lm = json.loads(lb.DATA_FILE.read_text()).get("books", {}) if lb.DATA_FILE.exists() else {}
    lm_c = counts(lm)
    bad = []
    for book in range(1, 67):
        ref = chk_c.get(book) if book >= 40 else lm_c.get(book)
        if not ref:
            continue
        mine = en_c.get(book, {})
        for ch, n in ref.items():
            if mine.get(ch) != n:
                bad.append(f"{nb.BOOKS[book-1]} {ch}: en {mine.get(ch)} vs ref {n}")
    log(f"Chapters whose English verse count differs from the Chuukese/Liebenzell reference: {len(bad)}")
    for line in bad[:60]:
        print("   ", line)
    gaps = []
    for b, chs in en.items():
        for c, vs in chs.items():
            nums = sorted(int(v) for v in vs)
            holes = [n for n in range(1, nums[-1] + 1) if n not in nums]
            if holes:
                gaps.append(f"{nb.BOOKS[int(b)-1]} {c}: missing {holes[:6]}")
    log(f"English chapters with a hole in the verse numbering: {len(gaps)}")
    for line in gaps[:40]:
        print("   ", line)
    missing = [nb.BOOKS[b-1] for b in range(1, 67) if b not in en_c]
    if missing:
        log(f"English books missing entirely: {missing}")
    if args.no_db:
        return
    from dotenv import load_dotenv
    from src.database.db_factory import get_cosmos_client

    load_dotenv()
    col = get_cosmos_client()["chuuk_dictionary"][nb.COLLECTION]
    n = 0
    for lang, bible, source in (("en", en, nb.SOURCE_EN), ("chk", chk, nb.SOURCE_CHK)):
        for book, chs in sorted(bible.items(), key=lambda kv: int(kv[0])):
            for chapter, vs in sorted(chs.items(), key=lambda kv: int(kv[0])):
                doc = {"lang": lang, "book": int(book), "chapter": int(chapter), "verses": {str(v): t for v, t in sorted(vs.items(), key=lambda kv: int(kv[0]))}, "source": source, "fetched_at": datetime.now(timezone.utc)}
                for attempt in range(8):
                    try:
                        col.update_one({"lang": lang, "book": int(book), "chapter": int(chapter)}, {"$set": doc}, upsert=True)
                        break
                    except Exception:
                        time.sleep(1.5 * (attempt + 1))
                        if attempt == 7:
                            raise
                n += 1
                time.sleep(0.08)
        log(f"{lang}: upserted so far {n}")
    log(f"upserted {n} chapters into {nb.COLLECTION}")


if __name__ == "__main__":
    main()
