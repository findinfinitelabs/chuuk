---
name: helsinki-nlp-model-training
description: Fine-tuning the Helsinki-NLP OPUS-MT models for Chuukese ↔ English in this repo — `HelsinkiFineTuner` device selection, training-data assembly from `DictionaryDB`, BLEU evaluation, and where the trained models live. Use when modifying the trainer, adding evaluation metrics, debugging a training run, or changing model paths.
---

# Helsinki-NLP Model Training

The runtime translator is the [`HelsinkiTranslator`](../../../src/translation/helsinki_translator_v2.py#L87) (loads pre-trained Marian models). The fine-tuner that produces those models is [`HelsinkiFineTuner`](../../../src/training/helsinki_trainer.py#L72). The orchestration around it (data assembly, scheduling, status surfacing) is documented in the [production-retraining-orchestration](../production-retraining-orchestration/SKILL.md) skill — this skill focuses on the trainer and translator internals.

## Model layout

Two direction-specific models, hard-coded paths:

```
models/helsinki-chuukese_chuukese_to_english/
models/helsinki-chuukese_english_to_chuukese/
```

Each directory holds a Hugging Face Marian checkpoint (config + tokenizer + weights). They're baked into the production Docker image (see [docker-containerization](../docker-containerization/SKILL.md)). A `models/test-helsinki_*/` pair exists for ephemeral test runs — don't ship those.

## Translator API

```python
from src.translation.helsinki_translator_v2 import HelsinkiTranslator

t = HelsinkiTranslator()
t.setup_models()                          # loads BOTH directions if present; no `direction` arg
t.translate("ran", "chk_to_en")           # → "water"
t.translate("water", "en_to_chk")         # → "ran"
score = t.evaluate_translation_quality(   # [helsinki_translator_v2.py](../../../src/translation/helsinki_translator_v2.py#L460)
    references=["ran"], hypotheses=["ran"]
)                                          # BLEU-based; chrF/ROUGE are NOT wired up
```

If the model directory is empty/missing, `setup_models` should leave the translator's `available` flag false rather than raising — the `/api/translate` endpoint relies on this.

## Fine-tuner API

```python
from src.training.helsinki_trainer import HelsinkiFineTuner

ft = HelsinkiFineTuner(progress_callback=lambda stage, pct, **kw: ...)
ft.train(
    direction="chk_to_en",       # or "en_to_chk"
    pairs=[{"src": "ran", "tgt": "water"}, ...],
    num_epochs=3,
)
```

Device selection happens in `__init__` ([helsinki_trainer.py](../../../src/training/helsinki_trainer.py#L72)):
- CUDA → uses **all** visible GPUs, sets per-process memory to 90%, enables TF32 + cuDNN benchmark.
- Apple Silicon → MPS.
- Else → CPU, capped at 8 threads. Slow.

The progress callback receives positional `(stage, progress)` plus kwargs `epoch`, `total_epochs`, `epoch_step_pct`, `epoch_loss`. The frontend reads these directly via the training-status endpoint — keep the kwarg names stable.

## Pulling training data from the DB

In scripts you'll see direct PyMongo access on the collection attributes (NOT method names):

```python
from src.database.dictionary_db import DictionaryDB
db = DictionaryDB()

# Forward direction examples (skip auto-generated reverse rows)
chk_to_en = list(db.dictionary_collection.find(
    {"search_direction": {"$ne": "en_to_chk"}}
))
phrases = list(db.phrases_collection.find({}))
```

`db.dictionary` / `db.phrases` are **not** attributes — only `db.dictionary_collection` / `db.phrases_collection` exist. Older docs got this wrong.

For the canonical assembly logic see [`scripts/train_from_db.py`](../../../scripts/train_from_db.py#L36) and [`scripts/retrain_with_latest_data.py`](../../../scripts/retrain_with_latest_data.py#L30).

## Evaluation

In-repo evaluation uses BLEU only ([helsinki_translator_v2.py](../../../src/translation/helsinki_translator_v2.py#L460)). If you need chrF or ROUGE, add them inside `evaluate_translation_quality` rather than introducing a parallel evaluator — the surface that consumes scores is small (one endpoint, one UI surface) and a single evaluator keeps it consistent.

For sample-level inspection, scripts like [`tests/test_model_comparison.py`](../../../tests/test_model_comparison.py) and [`tests/debug_models.py`](../../../tests/debug_models.py) are useful but treat them as exploratory — they're not part of the pytest suite proper (mark them `slow`/`translation` if you formalize them).

## Hyperparameters in current use

Defaults inside `HelsinkiFineTuner.train()`:
- 3 epochs (overridable).
- `Seq2SeqTrainingArguments` with `predict_with_generate=True`, `fp16=True` on CUDA, mixed-precision off on MPS/CPU.
- Tokenizer max length 128 — Chuukese sentences are short; raising this slows training without quality gain.

If you change defaults, update both directions in lockstep — asymmetric configs lead to confusing direction-dependent quality regressions.

## Pitfalls

- `setup_models()` takes no `direction` argument. Old skill docs invent one.
- Marian weights are **direction-specific**. Don't try to share a model between `chk_to_en` and `en_to_chk`.
- CUDA + multi-GPU: the trainer enables `os.environ["CUDA_VISIBLE_DEVICES"]` and 90% memory cap. If you hit OOM, lower the cap rather than dropping batch size — Marian batches are already small.
- Cold-start of the translator is ~5-10s per direction. Lazy-loading is intentional; don't move model load to import time.
- The retraining script short-circuits on unchanged dataset hash. Delete `training_data/data_hash.txt` to force a re-run.
- After training, the running app does **not** hot-reload weights. Restart workers (or, in prod, redeploy with the new image) to pick them up.
