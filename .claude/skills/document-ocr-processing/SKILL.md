---
name: document-ocr-processing
description: OCR pipeline for the Chuuk Dictionary — Tesseract + Google Vision via `OCRProcessor`, large-document handling via `EnhancedOCRProcessor`, structure-aware parsing via `AdvancedDocumentParser`. Use when ingesting scanned dictionary pages, PDFs, or DOCX files, or debugging extraction quality.
---

# Document OCR Processing

The OCR layer is three coordinating classes, all under [`src/ocr/`](../../../src/ocr/). Pick the right one for the document type — they are not interchangeable.

## Components

### 1. [`OCRProcessor`](../../../src/ocr/ocr_processor.py#L42)

The default processor for individual pages. Handles:
- **Images** (PNG, JPG, TIFF) via Tesseract (`pytesseract`) and optionally Google Vision.
- **PDF** by rasterizing pages with `pdf2image` then routing to image OCR.
- **DOCX** by direct text extraction via `python-docx` (no OCR — text is already there).

Authentication for Google Vision uses **either**:
- `GOOGLE_APPLICATION_CREDENTIALS` (path to service-account JSON), or
- `GOOGLE_CLOUD_API_KEY` (REST key — preferred in production).

The app prefers the API key when both are set (see [app.py](../../../app.py#L184), [app.py](../../../app.py#L1480)).

### 2. [`EnhancedOCRProcessor`](../../../src/ocr/enhanced_ocr_processor.py#L34)

For large multi-page documents. Wraps `OCRProcessor` and adds:
- Streaming page-by-page processing with progress callbacks (used by the SSE channel).
- Integration with the [`IntelligentTextChunker`](../../../src/utils/intelligent_chunker.py#L47) for downstream chunking. See [`enhanced_ocr_processor.py`](../../../src/ocr/enhanced_ocr_processor.py#L102).
- Memory-bounded processing (one page in memory at a time).

Use this when total page count > ~20 or the file is > ~50 MB.

### 3. [`AdvancedDocumentParser`](../../../src/ocr/advanced_document_parser.py#L66)

Structure-aware parser for dictionary-style documents. Detects:
- Two-column layouts.
- Headword/definition pairs.
- Pronunciation parentheticals.
- Section headings.

Output is a `ParsedDocument` consumed by [`AITrainingDataGenerator`](../../../src/training/ai_training_generator.py#L73) — that's the path from raw scan → training pairs.

## Pipeline integration

```python
from src.ocr.ocr_processor import OCRProcessor
from src.ocr.enhanced_ocr_processor import EnhancedOCRProcessor
from src.ocr.advanced_document_parser import AdvancedDocumentParser

# Single image
text, conf = OCRProcessor().process_image(path, language="chk+eng")

# Large PDF with progress streaming
def on_progress(stage, pct, **kw): push_sse(stage, pct, **kw)
processor = EnhancedOCRProcessor(progress_callback=on_progress)
result = processor.process_document(path)

# Dictionary-style structure extraction
parsed = AdvancedDocumentParser().parse(path)
```

The Flask layer at [app.py](../../../app.py#L1180) decides which processor to invoke based on file size and the `?process_now` flag.

## Tesseract languages

Required Tesseract data packs:
- `eng` (always)
- `chk` if available locally — Chuukese is not a packaged Tesseract language. The Dockerfile installs only `tesseract-ocr-eng` (see [Dockerfile](../../../Dockerfile#L18)). Chuukese-specific accents are recovered in **post-processing**, not at the Tesseract layer.

When you call into Tesseract for Chuukese pages, pass `lang="eng"` — better than `lang="chk"` which will warn-and-fallback.

## Post-processing for accented characters

Common OCR confusions on Chuukese text:

| Tesseract output | Likely correction |
|---|---|
| `a` after consonant | `á` |
| `e` in stressed position | `é` |
| `o` followed by `n`/`s` | `ó` |
| `u` with macron-like glyph | `ū` |
| `1` between letters | `l` |
| `0` between letters | `o` |

`OCRProcessor` applies a conservative pass; aggressive correction lives in [`scripts/identify_base_words.py`](../../../scripts/identify_base_words.py) and [`scripts/check_hyphens.py`](../../../scripts/check_hyphens.py) for batch cleanup.

## Confidence scoring

Each extracted word/entry carries a `confidence_score` (0.0–1.0). Sources:
- Tesseract per-word confidence (averaged).
- Google Vision page-level confidence (when used).
- Heuristic boosts when the word matches an existing dictionary entry exactly.

The [`PublicationDetail`](../../../frontend/src/pages/PublicationDetail.tsx) page surfaces these scores so editors can review low-confidence rows. Updates land via `POST /api/dictionary/entries`.

## Common workflows

### Reprocess a single page
```python
proc = OCRProcessor()
text, conf = proc.process_image(f"uploads/{pub_id}/{page_filename}", language="eng")
```

### Process a new publication end-to-end
Use the upload endpoint with `process_now=true`:
```
POST /api/publications/<id>/upload
form-data: file=<page>, process_now=true
```
The SSE stream surfaces per-page progress.

## Pitfalls

- The repo previously had classes named `ChuukeseOCRProcessor` / `BatchOCRProcessor`. They are gone — use the three classes above.
- `pdf2image` requires `poppler-utils` (installed in [Dockerfile](../../../Dockerfile#L17)). Local devs without poppler will get a confusing `pdftoppm` error.
- DOCX extraction does **not** go through OCR — if a DOCX contains scanned page images you'll get empty text. Convert to PDF first.
- Google Vision quotas are billed per-page — guard expensive calls behind `if not text or conf < 0.5`.
- The chunker integrated by `EnhancedOCRProcessor` does **not** protect scripture references; for Bible/brochure inputs wrap the call with `protect_scripture_references` (see the [scripture-reference-parsing](../scripture-reference-parsing/SKILL.md) skill).
