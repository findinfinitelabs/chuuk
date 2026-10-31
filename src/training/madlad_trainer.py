#!/usr/bin/env python3
"""
MADLAD-400 LoRA Fine-tuner for Chuukese ↔ English
=================================================

Trains a LoRA adapter on top of ``google/madlad400-3b-mt`` (T5 architecture).
One adapter serves both directions: each training pair becomes two examples,

    "<2en> <chuukese>"  → "<english>"
    "<2chk> <english>"  → "<chuukese>"

Device selection: CUDA → Apple Metal (MPS) → CPU. On CUDA/MPS the frozen base
weights are loaded in bfloat16 (~6 GB for 3B) and only the LoRA parameters are
trained in float32, so the whole run fits comfortably in 36 GB of unified memory.

Output layout (``model_root()`` from ``madlad_translator``):

    models/madlad400-chuukese/lora/      adapter weights + tokenizer (tens of MB)
    models/madlad400-chuukese/lora/training_metrics.json
    models/madlad400-chuukese/merged/    optional full merged checkpoint (``merge=True``)

The class exposes the same method names as ``HelsinkiFineTuner`` so the
continuous trainer can drive either engine:

    fine_tune_model(direction, training_pairs, num_epochs, batch_size, ...)
    fine_tune_model_lora(...)      alias — every MADLAD run is a LoRA run
    fine_tune_both_models(...)     bidirectional run from DB data
"""

from __future__ import annotations

import json
import os
import random
import time
from collections.abc import Callable

import torch

from src.translation.madlad_translator import (
    add_prefix,
    base_model_id,
    model_root,
    select_device,
)

# Reuse the progress bridge the UI already understands (epoch / loss kwargs).
from src.training.helsinki_trainer import EpochProgressCallback

# T5 attention + feed-forward projection names
ATTN_TARGETS = ["q", "k", "v", "o"]
FFN_TARGETS = ["wi_0", "wi_1", "wo"]


def build_examples(training_pairs: list[dict], direction: str = "both") -> list[dict]:
    """Turn {chuukese, english} pairs into prefixed source/target examples."""
    examples = []
    for p in training_pairs:
        chk = (p.get("chuukese") or "").strip()
        eng = (p.get("english") or "").strip()
        if not chk or not eng:
            continue
        if direction in ("both", "chk_to_en"):
            examples.append({"source": add_prefix(chk, "chk_to_en"), "target": eng})
        if direction in ("both", "en_to_chk"):
            examples.append({"source": add_prefix(eng, "en_to_chk"), "target": chk})
    return examples


def split_pairs(pairs: list[dict], eval_fraction: float = 0.05, seed: int = 42, max_eval: int = 500):
    """Deterministic train/eval split at the *pair* level (so no sentence leaks across)."""
    pairs = list(pairs)
    rng = random.Random(seed)
    rng.shuffle(pairs)
    n_eval = min(max_eval, max(1, int(len(pairs) * eval_fraction))) if len(pairs) > 20 else 0
    return pairs[n_eval:], pairs[:n_eval]


class MadladFineTuner:
    """LoRA fine-tuning for the MADLAD-400 translation model."""

    def __init__(self, progress_callback: Callable | None = None, base_model: str | None = None):
        self.progress_callback = progress_callback
        self.base_model = base_model or base_model_id()
        self.root = model_root()
        self.lora_path = os.path.join(self.root, "lora")
        self.merged_path = os.path.join(self.root, "merged")

        force_cpu = os.environ.get("FORCE_CPU", "0") == "1"
        self.device = "cpu" if force_cpu else select_device()
        self.dtype = torch.bfloat16 if self.device in ("cuda", "mps") else torch.float32
        self.bidirectional = True  # one model, both directions

        if self.device == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = True
            print(f"🎮 Using CUDA: {torch.cuda.get_device_name(0)}")
        elif self.device == "mps":
            # Let PyTorch fall back to CPU for the handful of ops Metal lacks
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            # Cap Metal allocations at 60% of the GPU working set (set before the
            # first MPS allocation). The default ratio, 1.7, lets one training
            # process exhaust system RAM and freeze the Mac rather than erroring.
            os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.6")
            os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.5")
            print("🍎 Using Apple Silicon GPU (Metal / MPS)")
        else:
            torch.set_num_threads(min(8, os.cpu_count() or 4))
            print(f"🖥️  Using CPU with {torch.get_num_threads()} threads (slow for a 3B model)")

        self.max_source_length = int(os.getenv("MADLAD_MAX_SOURCE_LEN", "128"))
        self.max_target_length = int(os.getenv("MADLAD_MAX_TARGET_LEN", "128"))

    # ------------------------------------------------------------------
    def _progress(self, stage: str, pct: float | None, **kw):
        if self.progress_callback:
            self.progress_callback(stage, pct, **kw)

    # ------------------------------------------------------------------
    def load_training_data_from_db(self) -> list[dict]:
        """Dictionary + phrase pairs from Cosmos (same filters as the Helsinki tuner)."""
        from src.database.dictionary_db import DictionaryDB

        self._progress("Loading dictionary data", 5)
        db = DictionaryDB()
        pairs = []
        for e in db.dictionary_collection.find(
            {"search_direction": {"$ne": "en_to_chk"}}, {"chuukese_word": 1, "english_translation": 1}
        ):
            chk = (e.get("chuukese_word") or "").strip()
            eng = (e.get("english_translation") or "").strip()
            if chk and eng and len(chk) > 1 and len(eng) > 2:
                pairs.append({"chuukese": chk, "english": eng})
        for p in db.phrases_collection.find({}):
            chk = (p.get("chuukese_sentence") or p.get("chuukese_phrase") or p.get("chuukese") or "").strip()
            eng = (p.get("english_translation") or p.get("english") or "").strip()
            if chk and eng and len(chk) > 2 and len(eng) > 3:
                pairs.append({"chuukese": chk, "english": eng})
        print(f"📚 Loaded {len(pairs)} training pairs from database")
        self._progress("Data loaded", 10)
        return pairs

    # ------------------------------------------------------------------
    def _load_base(self):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        print(f"📥 Loading base model {self.base_model} ({self.dtype}) ...")
        tokenizer = AutoTokenizer.from_pretrained(self.base_model)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.base_model, dtype=self.dtype)

        unk = tokenizer.unk_token_id
        for tok in ("<2en>", "<2chk>"):
            if tokenizer.convert_tokens_to_ids(tok) in (None, unk):
                raise ValueError(f"Tokenizer lacks {tok!r} — is MADLAD_BASE_MODEL a MADLAD checkpoint?")
        return model, tokenizer

    def _tokenize(self, examples: list[dict], tokenizer):
        from datasets import Dataset

        ds = Dataset.from_dict(
            {"source": [e["source"] for e in examples], "target": [e["target"] for e in examples]}
        )

        def fn(batch):
            enc = tokenizer(batch["source"], max_length=self.max_source_length, truncation=True)
            lab = tokenizer(text_target=batch["target"], max_length=self.max_target_length, truncation=True)
            enc["labels"] = lab["input_ids"]
            return enc

        return ds.map(fn, batched=True, remove_columns=ds.column_names)

    # ------------------------------------------------------------------
    def fine_tune_model(
        self,
        direction: str = "both",
        training_pairs: list[dict] | None = None,
        num_epochs: int = 3,
        batch_size: int = 8,
        learning_rate: float = 2e-4,
        gradient_accumulation_steps: int = 2,
        lora_r: int = 16,
        lora_alpha: int = 32,
        lora_dropout: float = 0.05,
        train_ffn: bool = False,
        eval_fraction: float = 0.05,
        save_steps: int = 500,
        adapter_output_dir: str | None = None,
        resume_adapter: bool = True,
        merge: bool = False,
        resume_from_checkpoint: str | None = None,
        **_ignored,
    ) -> bool:
        """
        Train (or continue training) the LoRA adapter.

        Args:
            direction: 'both' (recommended), 'chk_to_en' or 'en_to_chk'
            training_pairs: [{'chuukese': str, 'english': str}, ...]; loads from DB if None
            resume_adapter: continue from the existing adapter in ``lora/`` if present
            resume_from_checkpoint: a Trainer checkpoint dir (``lora/checkpoints/checkpoint-N``) to
                continue an interrupted run from — restores adapter, optimizer, scheduler and data
                position, so the training pairs must be the same ones that run used
            train_ffn: also adapt the T5 feed-forward layers (more capacity, more memory)
            merge: additionally write a fully merged checkpoint to ``merged/``
        """
        t_start = time.time()
        try:
            from peft import LoraConfig, PeftModel, TaskType, get_peft_model
            from transformers import DataCollatorForSeq2Seq, Seq2SeqTrainer, Seq2SeqTrainingArguments

            adapter_dir = adapter_output_dir or self.lora_path
            os.makedirs(adapter_dir, exist_ok=True)
            stage = {"both": "Chuukese⇄English", "chk_to_en": "Chuukese→English", "en_to_chk": "English→Chuukese"}[
                direction
            ]

            if training_pairs is None:
                training_pairs = self.load_training_data_from_db()
            if len(training_pairs) < 10:
                print(f"⚠️  Only {len(training_pairs)} pairs — results will be weak.")

            self._progress(f"Loading MADLAD base model ({stage})", 15)
            model, tokenizer = self._load_base()

            # ---- LoRA ---------------------------------------------------
            targets = ATTN_TARGETS + (FFN_TARGETS if train_ffn else [])
            if resume_adapter and os.path.exists(os.path.join(adapter_dir, "adapter_config.json")):
                print(f"🔗 Resuming from existing adapter: {adapter_dir}")
                model = PeftModel.from_pretrained(model, adapter_dir, is_trainable=True)
            else:
                cfg = LoraConfig(
                    task_type=TaskType.SEQ_2_SEQ_LM,
                    r=lora_r,
                    lora_alpha=lora_alpha,
                    lora_dropout=lora_dropout,
                    target_modules=targets,
                    bias="none",
                )
                model = get_peft_model(model, cfg)
            model.print_trainable_parameters()

            # Gradient checkpointing keeps activation memory flat for 3B on MPS
            model.config.use_cache = False
            model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
            model.enable_input_require_grads()
            model = model.to(self.device)

            # ---- Data ---------------------------------------------------
            self._progress(f"Preparing data ({stage})", 20)
            train_pairs, eval_pairs = split_pairs(training_pairs, eval_fraction=eval_fraction)
            train_ds = self._tokenize(build_examples(train_pairs, direction), tokenizer)
            eval_ds = self._tokenize(build_examples(eval_pairs, direction), tokenizer) if eval_pairs else None
            print(f"📊 Train examples: {len(train_ds):,}   Eval examples: {len(eval_ds) if eval_ds else 0:,}")

            collator = DataCollatorForSeq2Seq(tokenizer, model=model, label_pad_token_id=-100, pad_to_multiple_of=8)

            # ---- Trainer ------------------------------------------------
            args = Seq2SeqTrainingArguments(
                output_dir=os.path.join(adapter_dir, "checkpoints"),
                num_train_epochs=num_epochs,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                gradient_accumulation_steps=gradient_accumulation_steps,
                learning_rate=learning_rate,
                lr_scheduler_type="cosine",
                warmup_ratio=0.03,
                weight_decay=0.0,
                max_grad_norm=1.0,
                logging_steps=20,
                eval_strategy="steps" if eval_ds is not None else "no",
                eval_steps=save_steps,
                save_strategy="steps",
                save_steps=save_steps,
                save_total_limit=2,
                predict_with_generate=False,  # eval_loss only during training; BLEU/chrF run separately
                group_by_length=True,
                dataloader_num_workers=0,
                report_to=[],
                push_to_hub=False,
                use_cpu=self.device == "cpu",
                label_names=["labels"],
                remove_unused_columns=True,
            )

            epoch_cb = EpochProgressCallback(self.progress_callback, num_epochs, stage)
            trainer = Seq2SeqTrainer(
                model=model,
                args=args,
                train_dataset=train_ds,
                eval_dataset=eval_ds,
                data_collator=collator,
                processing_class=tokenizer,
                callbacks=[epoch_cb],
            )

            self._progress(f"Training LoRA ({stage})", 30)
            print(f"🚀 LoRA training: {num_epochs} epochs, batch {batch_size}×{gradient_accumulation_steps}, lr {learning_rate}")
            if resume_from_checkpoint:
                print(f"⏯  Resuming from checkpoint: {resume_from_checkpoint}")
            result = trainer.train(resume_from_checkpoint=resume_from_checkpoint or None)

            # ---- Save ---------------------------------------------------
            self._progress(f"Saving adapter ({stage})", 90)
            model.save_pretrained(adapter_dir)
            tokenizer.save_pretrained(adapter_dir)

            metrics = dict(result.metrics)
            if eval_ds is not None:
                metrics.update(trainer.evaluate())
            metrics.update(
                {
                    "direction": direction,
                    "pairs": len(training_pairs),
                    "train_examples": len(train_ds),
                    "eval_examples": len(eval_ds) if eval_ds is not None else 0,
                    "base_model": self.base_model,
                    "lora_r": lora_r,
                    "lora_alpha": lora_alpha,
                    "target_modules": targets,
                    "device": self.device,
                    "wall_seconds": round(time.time() - t_start, 1),
                    "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
            with open(os.path.join(adapter_dir, "training_metrics.json"), "w") as f:
                json.dump(metrics, f, indent=2)
            print(f"✅ Adapter saved to {adapter_dir}  (train_loss={metrics.get('train_loss')}, eval_loss={metrics.get('eval_loss')})")

            if merge:
                self._progress("Merging adapter into base weights", 95)
                merged = model.merge_and_unload()
                os.makedirs(self.merged_path, exist_ok=True)
                merged.save_pretrained(self.merged_path, safe_serialization=True)
                tokenizer.save_pretrained(self.merged_path)
                print(f"💾 Merged checkpoint written to {self.merged_path}")

            del trainer, model
            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()
            return True

        except Exception as e:
            print(f"❌ MADLAD fine-tuning error: {e}")
            import traceback

            traceback.print_exc()
            return False

    # Every MADLAD run is a LoRA run; keep the Helsinki method name working.
    def fine_tune_model_lora(self, direction: str, training_pairs: list[dict], num_epochs: int = 3,
                             batch_size: int = 1, learning_rate: float = 1e-4,
                             adapter_output_dir: str | None = None, **kw) -> bool:
        return self.fine_tune_model(
            direction=direction,
            training_pairs=training_pairs,
            num_epochs=num_epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            adapter_output_dir=adapter_output_dir,
            eval_fraction=0.0,
            **kw,
        )

    def fine_tune_both_models(self, num_epochs: int = 3, batch_size: int = 8, training_pairs=None, **kw) -> bool:
        """Single bidirectional run (one model covers both directions)."""
        print("🚀 Starting bidirectional MADLAD LoRA fine-tune")
        self._progress("Fine-tuning Chuukese⇄English", 25)
        ok = self.fine_tune_model(direction="both", training_pairs=training_pairs,
                                  num_epochs=num_epochs, batch_size=batch_size, **kw)
        self._progress("Fine-tuning complete" if ok else "Fine-tuning failed", 95)
        return ok


if __name__ == "__main__":
    tuner = MadladFineTuner(progress_callback=lambda s, p, **kw: print(f"[{p}] {s} {kw or ''}"))
    print("✅" if tuner.fine_tune_both_models(num_epochs=1, batch_size=4) else "❌")
