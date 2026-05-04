---
name: bible-epub-processing
description: Parse JW.org NWT EPUBs to extract individual Bible verses for verse previews, parallel-corpus building, and Bible-coverage analytics. Use when working with NWT EPUB files, building parallel Chuukese↔English Bible data, or wiring scripture preview features.
---

# Bible EPUB Processing

JW.org publishes the New World Translation as EPUB. We parse it on demand to fetch individual verses (for preview popups and coverage analytics), and bulk-extract for building parallel training data.

## The parser

[`src/utils/nwt_epub_parser.py`](../../../src/utils/nwt_epub_parser.py) — minimal, intentional surface:

```python
from src.utils.nwt_epub_parser import NWTEpubParser

parser = NWTEpubParser("config/data/bible/nwt_chk.epub")
text = parser.get_verse(book_num="40", chapter=1, verse=1)
# → "Chón anūn... Jesus Kraist..." or None if not found
```

That's it. There is **no** `get_book_list()`, `get_chapters()`, `get_verses()`, or `ParallelCorpusBuilder` class — older skill docs invented those. The full implementation:

- `__init__` loads the EPUB and calls `_build_chapter_map()`.
- `_build_chapter_map()` reads `toc.xhtml` and per-book `biblechapternav<N>.xhtml` files to map `{book_num_str: {"name": str, "chapters": {chapter_int: chapter_file}}}`.
- `get_verse(book_num, chapter, verse)` opens the chapter XHTML, finds the element with id `chapter{N}_verse{M}`, and returns its text.

Book numbers are **strings** keyed `"1"` through `"66"`. Pass `"40"` for Matthew, not `40`.

## Files & layout

- EPUBs live under [`config/data/bible/`](../../../config/data/) — typically `nwt_chk.epub` (Chuukese) and `nwt_en.epub` (English). **Not** under a top-level `data/` directory.
- Book number ↔ name mapping: [`config/bible_books.json`](../../../config/bible_books.json).
- Reference parsing (text → `(book, chapter, verse)`): [`config/scripture_books.json`](../../../config/scripture_books.json) + [`src/utils/scripture_parser.py`](../../../src/utils/scripture_parser.py#L77). See the [scripture-reference-parsing](../scripture-reference-parsing/SKILL.md) skill.

## Backend wiring

The parsers are **lazily** initialized — they're slow to construct (~1–2s per EPUB) so the app holds a singleton:

- Module-level slot + lazy getter at [app.py](../../../app.py#L41) (Chuukese) and [app.py](../../../app.py#L52) (English).
- Verse preview API: `GET /api/scripture/preview?ref=...` ([app.py](../../../app.py#L3541)) — returns CHK + EN side-by-side.
- Bible coverage analytics: `GET /api/bible/coverage` ([app.py](../../../app.py#L2881)) — summarises which verses appear how often across the corpus.

Anti-scrape robots policy on Bible endpoints: [app.py](../../../app.py#L3574). When you add a new Bible-related endpoint, route it through the same gate.

## Building parallel data

The "parallel corpus" is built ad-hoc by iterating book/chapter/verse triples and calling `get_verse` on both EPUBs. There is no class for it; the recipe lives in [`scripts/extract_brochure_sentences.py`](../../../scripts/extract_brochure_sentences.py) (for brochures) and analogous in-line code under `scripts/`. If you need a reusable parallel builder, write it new — just don't put it on `NWTEpubParser` itself, keep the parser's public API tiny.

```python
from src.utils.nwt_epub_parser import NWTEpubParser
chk = NWTEpubParser("config/data/bible/nwt_chk.epub")
en  = NWTEpubParser("config/data/bible/nwt_en.epub")

pairs = []
for book_num, book in chk.book_chapter_map.items():
    for ch_num in book["chapters"]:
        for v_num in range(1, 200):  # verses are sparse; break on None
            ch = chk.get_verse(book_num, ch_num, v_num)
            if ch is None: break
            en_text = en.get_verse(book_num, ch_num, v_num)
            if en_text:
                pairs.append({"chk": ch, "en": en_text, "ref": f"{book['name']} {ch_num}:{v_num}"})
```

Feed `pairs` into [`AITrainingDataGenerator.export_training_data(...)`](../../../src/training/ai_training_generator.py#L527) for the standard jsonl/huggingface/ollama outputs.

## Pitfalls

- `get_verse` returns `None` when the verse doesn't exist (end of chapter, missing book). Always handle `None` — don't assume continuous numbering.
- Both EPUBs must use the same JW.org schema. Older NWT EPUBs use `id="v{N}"` instead of `id="chapter{N}_verse{M}"` — the parser will silently return `None` for those. If extraction is empty, dump the chapter HTML and check the id format.
- Constructing the parser is heavy. **Always** use the singleton accessors in `app.py`; never `NWTEpubParser(...)` per request.
- The TOC parsing key (`href.startswith("biblechapternav")`) is brittle — JW.org occasionally changes filenames. If a new EPUB build breaks parsing, inspect `book.get_items()` filenames first.
- Verse text may contain footnote markers (e.g. `*`, `+`). Strip them before training data generation; preview UI keeps them.
