#!/usr/bin/env python3
"""
MADLAD-400 Chuukese Translation System
=====================================

Runtime translator built on Google's MADLAD-400 MT model (``google/madlad400-3b-mt``),
a T5-style encoder-decoder pre-trained on 400+ languages **including Chuukese (chk)**.
Unlike the Helsinki OPUS-MT ``mul-en`` / ``en-mul`` pair, a single MADLAD model handles
both directions; the target language is selected with a ``<2xx>`` prefix token on the
source text (``<2en>`` for English output, ``<2chk>`` for Chuukese output).

Fine-tuning is done with LoRA adapters (see ``src/training/madlad_trainer.py``). At
load time this class looks for, in order:

1. ``{model_root}/merged/``  — a fully merged checkpoint (adapter folded into weights)
2. ``{model_root}/lora/``    — a PEFT adapter, applied on top of the base model
3. the base model from the Hugging Face cache (``MADLAD_BASE_MODEL`` env override)

``model_root`` is ``$MODEL_STORE_PATH/madlad400-chuukese`` when ``MODEL_STORE_PATH``
is set (persistent Azure File Share), otherwise ``models/madlad400-chuukese``.

The public surface mirrors ``HelsinkiChuukeseTranslator`` so ``app.py`` and the
continuous trainer can swap engines via the ``TRANSLATION_ENGINE`` env var:

    translate_chuukese_to_english(text) -> str
    translate_english_to_chuukese(text) -> str
    setup_models() / reload_models() -> bool
    load_dictionary_data() -> int
    evaluate_translation_quality(pairs) -> dict   (BLEU + chrF)
    fine_tune_model(direction, ...) -> bool
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass

import torch

logger = logging.getLogger(__name__)

DEFAULT_BASE_MODEL = "google/madlad400-3b-mt"
MODEL_DIR_NAME = "madlad400-chuukese"

# MADLAD target-language prefix tokens
PREFIX_TO_EN = "<2en>"
PREFIX_TO_CHK = "<2chk>"


@dataclass
class TranslationPair:
    """Structure for storing translation pairs (same shape as the Helsinki module)."""

    chuukese: str
    english: str
    source: str = "dictionary"


def select_device() -> str:
    """CUDA → Apple Metal (MPS) → CPU."""
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available() and torch.backends.mps.is_built():
        _cap_mps_memory()
        return "mps"
    return "cpu"


def _cap_mps_memory() -> None:
    """Keep Metal allocations inside RAM, before the first MPS allocation.

    PyTorch's defaults (high 1.7, low 1.4 of the GPU working set) let one 3B
    process ask for more than the machine has and freeze macOS. Both ratios
    must be set together: the allocator rejects a low watermark above the high
    one ("invalid low watermark ratio").
    """
    high = os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.6")
    try:
        high_f = float(high)
    except ValueError:
        return
    low = os.environ.get("PYTORCH_MPS_LOW_WATERMARK_RATIO")
    if low is None or float(low) > high_f:
        os.environ["PYTORCH_MPS_LOW_WATERMARK_RATIO"] = str(min(0.5, high_f))


def model_root() -> str:
    """Directory that holds the ``lora/`` and ``merged/`` sub-folders."""
    store = os.getenv("MODEL_STORE_PATH", "").strip().rstrip("/")
    if store:
        return os.path.join(store, MODEL_DIR_NAME)
    return os.path.join("models", MODEL_DIR_NAME)


def base_model_id() -> str:
    return os.getenv("MADLAD_BASE_MODEL", DEFAULT_BASE_MODEL).strip() or DEFAULT_BASE_MODEL


def add_prefix(text: str, direction: str) -> str:
    """Prepend the MADLAD target-language token for ``direction``."""
    prefix = PREFIX_TO_EN if direction == "chk_to_en" else PREFIX_TO_CHK
    return f"{prefix} {text.strip()}"


class MadladChuukeseTranslator:
    """Bidirectional Chuukese ↔ English translator on MADLAD-400 (+ optional LoRA)."""

    def __init__(self, base_model: str | None = None, use_adapter: bool = True):
        """
        Args:
            base_model: HF id or path of the MADLAD checkpoint (default from env / 3B)
            use_adapter: when False, ignore any merged/LoRA weights on disk and load the
                         untouched base model — used for zero-shot baseline scoring
        """
        self.base_model = base_model or base_model_id()
        self.use_adapter = use_adapter
        self.root = model_root()
        self.lora_path = os.path.join(self.root, "lora")
        self.merged_path = os.path.join(self.root, "merged")

        self.tokenizer = None
        self.model = None
        self.device = select_device()
        self.dtype = torch.bfloat16 if self.device in ("cuda", "mps") else torch.float32
        self.training_data: list[TranslationPair] = []
        self.db = None
        # Kept for parity with the Helsinki translator's status reporting
        self.using_finetuned = {"chk_to_en": False, "en_to_chk": False}
        self.loaded_from = None
        self._lock = threading.Lock()

        self.num_beams = int(os.getenv("MADLAD_NUM_BEAMS", "4"))
        self.max_new_tokens = int(os.getenv("MADLAD_MAX_NEW_TOKENS", "256"))
        logger.info(f"🔧 MADLAD translator device: {self.device} ({self.dtype})")

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def setup_models(self) -> bool:
        """Load tokenizer + model (merged > LoRA adapter > base). Never raises."""
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            t0 = time.time()
            if self.use_adapter and os.path.exists(os.path.join(self.merged_path, "config.json")):
                logger.info(f"📥 Loading MERGED MADLAD model from {self.merged_path}...")
                self.tokenizer = AutoTokenizer.from_pretrained(self.merged_path)
                model = AutoModelForSeq2SeqLM.from_pretrained(self.merged_path, dtype=self.dtype)
                self.loaded_from = "merged"
                finetuned = True
            else:
                logger.info(f"📥 Loading base MADLAD model {self.base_model}...")
                self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
                model = AutoModelForSeq2SeqLM.from_pretrained(self.base_model, dtype=self.dtype)
                self.loaded_from = "base"
                finetuned = False

                if self.use_adapter and os.path.exists(os.path.join(self.lora_path, "adapter_config.json")):
                    from peft import PeftModel

                    logger.info(f"🔗 Applying LoRA adapter from {self.lora_path}...")
                    model = PeftModel.from_pretrained(model, self.lora_path)
                    # Fold the adapter in so inference costs nothing extra
                    model = model.merge_and_unload()
                    self.loaded_from = "base+lora"
                    finetuned = True

            self._check_prefix_tokens()

            model.eval()
            self.model = model.to(self.device)
            self.using_finetuned = {"chk_to_en": finetuned, "en_to_chk": finetuned}
            logger.info(
                f"✅ MADLAD ready ({self.loaded_from}) on {self.device} in {time.time() - t0:.1f}s"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load MADLAD model: {e}")
            self.model = None
            self.tokenizer = None
            return False

    def _check_prefix_tokens(self) -> None:
        """Fail loudly if the tokenizer doesn't know the Chuukese target token."""
        unk = self.tokenizer.unk_token_id
        for tok in (PREFIX_TO_EN, PREFIX_TO_CHK):
            tid = self.tokenizer.convert_tokens_to_ids(tok)
            if tid is None or tid == unk:
                raise ValueError(f"Tokenizer has no language token {tok!r}; wrong base model?")

    def reload_models(self) -> bool:
        """Drop current weights and reload (picks up a newly trained adapter)."""
        logger.info("🔄 Reloading MADLAD model...")
        with self._lock:
            self.model = None
            self.tokenizer = None
            import gc

            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()
            return self.setup_models()

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def translate_batch(self, texts: list[str], direction: str, batch_size: int = 16) -> list[str]:
        """Translate many strings in one direction. Order is preserved."""
        if not self.available:
            raise RuntimeError("MADLAD model not loaded")

        outputs: list[str] = []
        with self._lock:
            for i in range(0, len(texts), batch_size):
                chunk = [add_prefix(t, direction) for t in texts[i : i + batch_size]]
                enc = self.tokenizer(
                    chunk, return_tensors="pt", padding=True, truncation=True, max_length=512
                ).to(self.device)
                with torch.inference_mode():
                    gen = self.model.generate(
                        **enc,
                        num_beams=self.num_beams,
                        max_new_tokens=self.max_new_tokens,
                        early_stopping=True,
                    )
                outputs.extend(self.tokenizer.batch_decode(gen, skip_special_tokens=True))
        return [o.strip() for o in outputs]

    def translate(self, text: str, direction: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        return self.translate_batch([text], direction)[0]

    def translate_chuukese_to_english(self, chuukese_text: str) -> str:
        if not self.available:
            logger.error("❌ Translation model not loaded")
            return f"Translation model not available: {chuukese_text}"
        try:
            out = self.translate(chuukese_text, "chk_to_en")
            logger.info(f"🔄 Chuukese→English: '{chuukese_text}' → '{out}'")
            return out
        except Exception as e:
            logger.error(f"❌ Translation error: {e}")
            return f"Translation error: {chuukese_text}"

    def translate_english_to_chuukese(self, english_text: str) -> str:
        if not self.available:
            logger.error("❌ Translation model not loaded")
            return f"Translation model not available: {english_text}"
        try:
            out = self.translate(english_text, "en_to_chk")
            logger.info(f"🔄 English→Chuukese: '{english_text}' → '{out}'")
            return out
        except Exception as e:
            logger.error(f"❌ Translation error: {e}")
            return f"Translation error: {english_text}"

    # ------------------------------------------------------------------
    # Data / training hooks (parity with the Helsinki translator)
    # ------------------------------------------------------------------

    def load_dictionary_data(self) -> int:
        """Load Chuukese dictionary pairs from the DB into ``self.training_data``."""
        try:
            from src.database.dictionary_db import DictionaryDB

            self.db = DictionaryDB()
            if not self.db.client:
                logger.warning("⚠️ Database not available, skipping dictionary data loading")
                return 0

            rows = self.db.dictionary_collection.find(
                {"search_direction": {"$ne": "en_to_chk"}},
                {"chuukese_word": 1, "english_translation": 1, "source": 1},
            )
            self.training_data = []
            for entry in rows:
                chk = (entry.get("chuukese_word") or "").strip()
                eng = (entry.get("english_translation") or "").strip()
                if chk and eng:
                    src = entry.get("source", "dictionary")
                    self.training_data.append(
                        TranslationPair(chuukese=chk, english=eng, source=str(src) if src else "dictionary")
                    )
            logger.info(f"📚 Loaded {len(self.training_data)} translation pairs")
            return len(self.training_data)
        except Exception as e:
            logger.error(f"❌ Failed to load dictionary data: {e}")
            return 0

    def fine_tune_model(
        self,
        direction: str = "both",
        output_dir: str | None = None,
        num_epochs: int = 3,
        batch_size: int = 8,
    ) -> bool:
        """Run a LoRA fine-tune on ``self.training_data`` and reload the weights."""
        if not self.training_data:
            logger.error("❌ No training data available")
            return False
        from src.training.madlad_trainer import MadladFineTuner

        # Accept the Helsinki-style long direction names too
        direction = {
            "chuukese_to_english": "chk_to_en",
            "english_to_chuukese": "en_to_chk",
        }.get(direction, direction)

        pairs = [{"chuukese": p.chuukese, "english": p.english} for p in self.training_data]
        tuner = MadladFineTuner()
        ok = tuner.fine_tune_model(
            direction=direction,
            training_pairs=pairs,
            num_epochs=num_epochs,
            batch_size=batch_size,
            adapter_output_dir=output_dir,
        )
        if ok:
            self.reload_models()
        return ok

    def evaluate_translation_quality(
        self, test_pairs: list[TranslationPair] | None = None, batch_size: int = 8
    ) -> dict[str, float]:
        """Corpus BLEU and chrF in both directions on ``test_pairs``."""
        if not test_pairs:
            test_pairs = self.training_data[:50]
        if not test_pairs:
            logger.error("❌ No test data available")
            return {}
        if not self.available:
            logger.error("❌ Model not loaded")
            return {}

        try:
            from sacrebleu.metrics import BLEU, CHRF

            bleu, chrf = BLEU(), CHRF()
            chk = [p.chuukese for p in test_pairs]
            eng = [p.english for p in test_pairs]

            hyp_en = self.translate_batch(chk, "chk_to_en", batch_size=batch_size)
            hyp_chk = self.translate_batch(eng, "en_to_chk", batch_size=batch_size)

            results = {
                "chuukese_to_english_bleu": round(bleu.corpus_score(hyp_en, [eng]).score, 2),
                "chuukese_to_english_chrf": round(chrf.corpus_score(hyp_en, [eng]).score, 2),
                "english_to_chuukese_bleu": round(bleu.corpus_score(hyp_chk, [chk]).score, 2),
                "english_to_chuukese_chrf": round(chrf.corpus_score(hyp_chk, [chk]).score, 2),
                "test_samples": len(test_pairs),
            }
            logger.info("📊 Evaluation Results:")
            logger.info(
                f"   Chuukese→English BLEU {results['chuukese_to_english_bleu']}  chrF {results['chuukese_to_english_chrf']}"
            )
            logger.info(
                f"   English→Chuukese BLEU {results['english_to_chuukese_bleu']}  chrF {results['english_to_chuukese_chrf']}"
            )
            return results
        except Exception as e:
            logger.error(f"❌ Evaluation failed: {e}")
            return {}


def main():
    logging.basicConfig(level=logging.INFO)
    t = MadladChuukeseTranslator()
    if not t.setup_models():
        print("❌ Failed to load model")
        return
    for text in ["Ran annim", "Kinisou chapur", "Ua tongei Kot"]:
        print(f"{text!r} → {t.translate_chuukese_to_english(text)!r}")
    for text in ["Good morning", "Thank you very much", "I love God"]:
        print(f"{text!r} → {t.translate_english_to_chuukese(text)!r}")


if __name__ == "__main__":
    main()
