---
name: intelligent-text-chunking
description: Split long Chuukese/English documents into chunks for OCR pipelines, AI training, or retrieval — using the in-repo `IntelligentTextChunker`. Use when a downstream consumer requires bounded context windows or when feeding large documents into the training generator.
---

# Intelligent Text Chunking

There is a real implementation at [`src/utils/intelligent_chunker.py`](../../../src/utils/intelligent_chunker.py). Use it; don't roll your own splitter.

## API

```python
from src.utils.intelligent_chunker import IntelligentTextChunker, ChunkType, TextChunk

chunker = IntelligentTextChunker(
    max_chunk_size=512,      # tokens/characters per chunk
    min_chunk_size=50,
    overlap_ratio=0.1,       # 0.0–0.5
    preserve_sentences=True,
    preserve_paragraphs=True,
)
chunks: list[TextChunk] = chunker.chunk(text)
# Each TextChunk has: content, start_position, end_position, chunk_id,
#   chunk_type (ChunkType enum), metadata, overlap_with_previous, overlap_with_next
```

`ChunkType` enum: `SEMANTIC`, `STRUCTURAL`, `FIXED_SIZE`, `SLIDING_WINDOW` ([intelligent_chunker.py](../../../src/utils/intelligent_chunker.py#L16)).

The chunker has built-in awareness of:
- Multi-language sentence boundaries (English, Chuukese, generic CJK punctuation).
- Structure markers (markdown headings, list items, dictionary entries, page breaks).
- Semantic transition phrases (topic change, continuation, conclusion, examples).

## Where it's used

- [`EnhancedOCRProcessor`](../../../src/ocr/enhanced_ocr_processor.py#L102) — chunks OCR output for downstream training/storage.
- [`LargeDocumentProcessor`](../../../src/pipeline/large_document_processor.py#L43) — top-level pipeline for 200+ page documents.
- [`AITrainingDataGenerator`](../../../src/training/ai_training_generator.py#L73) consumes chunks indirectly through `ParsedDocument`.

## Critical: scripture references aren't protected

The chunker does **not** know about Bible references — it will happily split `1 Cor. 13:4-7` across chunks. Always wrap calls with `protect_scripture_references` / `restore_scripture_references` from [`src/utils/scripture_parser.py`](../../../src/utils/scripture_parser.py#L77) when input may contain them. See the [scripture-reference-parsing](../scripture-reference-parsing/SKILL.md) skill.

```python
from src.utils.scripture_parser import (
    protect_scripture_references, restore_scripture_references
)

protected, refs = protect_scripture_references(raw)
chunks = chunker.chunk(protected)
chunks = [
    TextChunk(content=restore_scripture_references(c.content, refs), **c_meta)
    for c in chunks
]
```

## Choosing parameters

| Use case | max_chunk_size | overlap_ratio |
|---|---|---|
| Training pairs | 256–512 | 0.0–0.05 |
| RAG / retrieval | 512–1024 | 0.10–0.15 |
| Summarization input | 1024–2048 | 0.05 |

Chuukese text is denser per-character than English — when budgeting tokens for an LLM downstream, count tokens, not characters.

## Pitfalls

- `max_chunk_size` is in **characters** by default (the dataclass `__len__` returns `len(content)`). If you need token counts, post-process with the model's tokenizer.
- Setting `preserve_paragraphs=True` plus a small `max_chunk_size` will produce oversized chunks rather than break a paragraph — verify chunk lengths if you have hard caps.
- The chunker emits `chunk_id`s that are not deterministic across runs (they include positional info). Don't use them as DB primary keys.
- Don't subclass — the public API is small. If you need different behavior, configure the constructor or post-process the chunk list.
