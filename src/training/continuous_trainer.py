#!/usr/bin/env python3
"""
Continuous Training Engine for Helsinki-NLP Models
====================================================
Collects CHK↔EN pairs from all sources in the DB (dictionary, phrases,
paragraphs, article analyses, translation-game sentences, user corrections),
runs LoRA adapters for instant "teach one pair now" interactions, and
schedules full fine-tune merges on a configurable interval.

Sources ingested:
  - dictionary_collection    (chuukese_word / english_translation)
  - phrases_collection       (multi-word / sentence pairs, incl. game saves)
  - paragraphs_collection    (paragraph-level bilingual text)
  - article_analysis_paragraphs (CHK sentence + assembled English tokens)
  - user corrections         (source="user_correction", high confidence)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (overridable by env)
# ---------------------------------------------------------------------------
TRAINING_INTERVAL_MINUTES = int(os.getenv("TRAINING_INTERVAL_MINUTES", "30"))
TRAINING_MIN_NEW_PAIRS = int(os.getenv("TRAINING_MIN_NEW_PAIRS", "10"))
LORA_MERGE_THRESHOLD = int(os.getenv("LORA_MERGE_THRESHOLD", "50"))
LORA_ADAPTER_DIR = "models/lora_adapters"
TRAINING_LOG_DIR = "training_data/logs"
PAIR_HASH_FILE = "training_data/data_hash.txt"


# ---------------------------------------------------------------------------
# Data-pair collector
# ---------------------------------------------------------------------------

class TrainingPairCollector:
    """Pulls CHK↔EN pairs from every available DB source."""

    def __init__(self, db=None):
        self._db = db  # lazily resolved

    @property
    def db(self):
        if self._db is None:
            from src.database.dictionary_db import DictionaryDB
            self._db = DictionaryDB()
        return self._db

    # ------------------------------------------------------------------
    # Individual source extractors
    # ------------------------------------------------------------------

    def _from_dictionary(self) -> list[dict]:
        """dictionary_collection — word-level entries."""
        pairs = []
        try:
            rows = self.db.dictionary_collection.find(
                {"search_direction": {"$ne": "en_to_chk"},
                 "chuukese_word": {"$exists": True},
                 "english_translation": {"$exists": True}},
                {"chuukese_word": 1, "english_translation": 1,
                 "definition": 1, "word_type": 1, "confidence_score": 1}
            )
            for r in rows:
                chk = (r.get("chuukese_word") or "").strip()
                eng = (r.get("english_translation") or "").strip()
                if chk and eng and len(chk) > 1 and len(eng) > 1:
                    pairs.append({
                        "chuukese": chk,
                        "english": eng,
                        "source": "dictionary",
                        "confidence": r.get("confidence_score", 70),
                        "definition": (r.get("definition") or "").strip(),
                        "word_type": (r.get("word_type") or "").strip(),
                    })
        except Exception as e:
            logger.warning("dictionary collection error: %s", e)
        return pairs

    def _from_phrases(self) -> list[dict]:
        """phrases_collection — multi-word and sentence pairs."""
        pairs = []
        try:
            rows = self.db.phrases_collection.find(
                {},
                {"chuukese_phrase": 1, "chuukese_sentence": 1, "chuukese": 1,
                 "english_translation": 1, "english": 1, "confidence_score": 1, "source": 1}
            )
            for r in rows:
                chk = (r.get("chuukese_phrase") or r.get("chuukese_sentence") or
                       r.get("chuukese") or "").strip()
                eng = (r.get("english_translation") or r.get("english") or "").strip()
                if chk and eng and len(chk) > 1 and len(eng) > 1:
                    pairs.append({
                        "chuukese": chk,
                        "english": eng,
                        "source": r.get("source", "phrase"),
                        "confidence": r.get("confidence_score", 70),
                    })
        except Exception as e:
            logger.warning("phrases collection error: %s", e)
        return pairs

    def _from_paragraphs(self) -> list[dict]:
        """paragraphs_collection — paragraph-level bilingual text."""
        pairs = []
        try:
            rows = self.db.paragraphs_collection.find(
                {"chuukese_paragraph": {"$exists": True},
                 "english_paragraph": {"$exists": True}},
                {"chuukese_paragraph": 1, "english_paragraph": 1}
            )
            for r in rows:
                chk = (r.get("chuukese_paragraph") or "").strip()
                eng = (r.get("english_paragraph") or "").strip()
                if chk and eng and len(chk) > 5 and len(eng) > 5:
                    pairs.append({
                        "chuukese": chk,
                        "english": eng,
                        "source": "paragraph",
                        "confidence": 65,
                    })
        except Exception as e:
            logger.warning("paragraphs collection error: %s", e)
        return pairs

    def _from_article_analyses(self) -> list[dict]:
        """
        article_analysis_paragraphs — each paragraph doc holds per-sentence
        CHK tokens + assembled English.  We extract every sentence pair.
        """
        pairs = []
        try:
            # Collection is created lazily in app.py; fall back gracefully
            try:
                client = self.db.client
                db = client["chuuk_dictionary"]
                col = db["article_analysis_paragraphs"]
            except Exception:
                return pairs

            for para_doc in col.find({"paragraph": {"$exists": True}}):
                para = para_doc.get("paragraph", {})
                sentences = para.get("sentences", [])
                for sent in sentences:
                    chk = (sent.get("text_only") or sent.get("chuukese") or "").strip()
                    eng = (sent.get("english_text") or sent.get("english_assembled") or "").strip()
                    if chk and eng and len(chk) > 3 and len(eng) > 3:
                        pairs.append({
                            "chuukese": chk,
                            "english": eng,
                            "source": "article_analysis",
                            "confidence": 75,
                        })
        except Exception as e:
            logger.warning("article analysis collection error: %s", e)
        return pairs

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def collect_all(self, min_confidence: float = 50) -> list[dict]:
        """Return de-duplicated pairs from all sources above min_confidence."""
        all_pairs: list[dict] = []
        all_pairs.extend(self._from_dictionary())
        all_pairs.extend(self._from_phrases())
        all_pairs.extend(self._from_paragraphs())
        all_pairs.extend(self._from_article_analyses())

        # De-duplicate on (chuukese, english) key, keeping highest confidence
        seen: dict[tuple, dict] = {}
        for p in all_pairs:
            key = (p["chuukese"].lower(), p["english"].lower())
            if key not in seen or p["confidence"] > seen[key]["confidence"]:
                seen[key] = p

        filtered = [p for p in seen.values() if p["confidence"] >= min_confidence]
        logger.info("Collected %d pairs (after dedup + confidence filter)", len(filtered))
        return filtered

    def count_new_pairs(self, since_pairs_count: int) -> int:
        """Quick estimate of new pairs since last count."""
        try:
            total = (
                self.db.dictionary_collection.count_documents({}) +
                self.db.phrases_collection.count_documents({}) +
                self.db.paragraphs_collection.count_documents({})
            )
            # Count individual sentences inside article_analysis_paragraphs,
            # not paragraph documents — each sentence is one training pair.
            try:
                col = self.db.client["chuuk_dictionary"]["article_analysis_paragraphs"]
                result = list(col.aggregate([
                    {"$project": {"sentence_count": {"$size": {"$ifNull": ["$paragraph.sentences", []]}}}},
                    {"$group": {"_id": None, "total": {"$sum": "$sentence_count"}}},
                ]))
                total += result[0]["total"] if result else 0
            except Exception:
                pass
            return max(0, total - since_pairs_count)
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# Training run record
# ---------------------------------------------------------------------------

class TrainingRun:
    def __init__(self, run_id: str, trigger: str):
        self.run_id = run_id
        self.trigger = trigger          # "scheduled" | "manual" | "lora_merge" | "correction"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.status = "running"         # running | completed | failed
        self.mode = "unknown"           # full | lora | both
        self.pairs_used: int = 0
        self.chk_to_en_loss: float | None = None
        self.en_to_chk_loss: float | None = None
        self.lora_updates: int = 0
        self.message = ""
        self.logs: list[str] = []

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "mode": self.mode,
            "pairs_used": self.pairs_used,
            "chk_to_en_loss": self.chk_to_en_loss,
            "en_to_chk_loss": self.en_to_chk_loss,
            "lora_updates": self.lora_updates,
            "message": self.message,
            "logs": self.logs[-50:],   # keep last 50 log lines in the run record
        }

    def log(self, msg: str):
        self.logs.append(f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}")
        logger.info("[run %s] %s", self.run_id[:8], msg)


# ---------------------------------------------------------------------------
# Continuous trainer
# ---------------------------------------------------------------------------

class ContinuousTrainer:
    """
    Singleton-ish training engine.  Call get_instance() rather than __init__.

    - Maintains an in-process training event queue.
    - Schedules full fine-tunes via a background daemon thread.
    - Supports LoRA "quick teach" that applies in seconds.
    - Persists run history to training_data/logs/.
    - Broadcasts progress via a registered callback (used by the SSE route).
    """

    _instance: "ContinuousTrainer | None" = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ContinuousTrainer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ContinuousTrainer()
            return cls._instance

    def __init__(self):
        self.collector = TrainingPairCollector()

        # State
        self._current_run: TrainingRun | None = None
        self._run_history: deque[TrainingRun] = deque(maxlen=50)
        self._lora_update_count = 0
        self._last_pair_count = 0
        self._scheduler_thread: threading.Thread | None = None
        self._running = False
        self._progress_callbacks: list[Callable] = []
        self._state_lock = threading.Lock()

        # Dirs
        Path(LORA_ADAPTER_DIR).mkdir(parents=True, exist_ok=True)
        Path(TRAINING_LOG_DIR).mkdir(parents=True, exist_ok=True)

        logger.info("ContinuousTrainer initialised")

    # ------------------------------------------------------------------
    # Progress / event broadcasting
    # ------------------------------------------------------------------

    def register_progress_callback(self, cb: Callable) -> None:
        """Register a callback(event: dict) for live progress pushes."""
        self._progress_callbacks.append(cb)

    def _emit(self, event: dict) -> None:
        for cb in list(self._progress_callbacks):
            try:
                cb(event)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def start_scheduler(self) -> None:
        """Start the background scheduling thread (call once at app boot)."""
        if self._running:
            return
        self._running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="continuous-trainer"
        )
        self._scheduler_thread.start()
        logger.info("Continuous trainer scheduler started (interval=%dm, min_pairs=%d)",
                    TRAINING_INTERVAL_MINUTES, TRAINING_MIN_NEW_PAIRS)

    def stop_scheduler(self) -> None:
        self._running = False

    def _scheduler_loop(self) -> None:
        interval_secs = TRAINING_INTERVAL_MINUTES * 60
        next_run = time.monotonic() + interval_secs
        while self._running:
            time.sleep(10)
            if not self._running:
                break
            if time.monotonic() >= next_run:
                next_run = time.monotonic() + interval_secs
                new_pairs = self.collector.count_new_pairs(self._last_pair_count)
                if new_pairs >= TRAINING_MIN_NEW_PAIRS:
                    logger.info("Scheduler: %d new pairs detected, triggering scheduled run", new_pairs)
                    self.run_full_training_async(trigger="scheduled")
                else:
                    logger.debug("Scheduler: only %d new pairs (need %d), skipping",
                                 new_pairs, TRAINING_MIN_NEW_PAIRS)

    # ------------------------------------------------------------------
    # Status / history
    # ------------------------------------------------------------------

    @property
    def is_training(self) -> bool:
        with self._state_lock:
            return self._current_run is not None and self._current_run.status == "running"

    def get_status(self) -> dict:
        with self._state_lock:
            current = self._current_run.to_dict() if self._current_run else None
            history = [r.to_dict() for r in reversed(self._run_history)]
        return {
            "is_training": self.is_training,
            "current_run": current,
            "lora_update_count": self._lora_update_count,
            "lora_merge_threshold": LORA_MERGE_THRESHOLD,
            "scheduler_interval_minutes": TRAINING_INTERVAL_MINUTES,
            "scheduler_min_new_pairs": TRAINING_MIN_NEW_PAIRS,
            "recent_runs": history[:10],
            "ollama_enabled": os.getenv("OLLAMA_ENABLED", "false").lower() == "true",
        }

    # ------------------------------------------------------------------
    # LoRA quick-teach (single pair or small batch)
    # ------------------------------------------------------------------

    def teach_pair_lora(
        self,
        chuukese: str,
        english: str,
        direction: str = "both",
        progress_cb: Callable | None = None,
    ) -> dict:
        """
        Apply a LoRA adapter update for a single correction pair.
        Fast: typically < 30s on CPU, < 5s on GPU/MPS.
        Returns {"success": bool, "message": str, "lora_updates": int}.
        """
        run_id = str(uuid.uuid4())
        run = TrainingRun(run_id, trigger="correction")
        run.mode = "lora"
        run.pairs_used = 1

        def _emit_progress(msg: str, pct: int | None = None):
            event = {
                "type": "lora_progress",
                "run_id": run_id,
                "message": msg,
                "progress": pct,
            }
            self._emit(event)
            if progress_cb:
                progress_cb(event)

        try:
            run.log(f"LoRA teach: '{chuukese}' ↔ '{english}' [{direction}]")
            _emit_progress(f"LoRA update: teaching '{chuukese}' ↔ '{english}'", 10)

            from src.training.helsinki_trainer import HelsinkiFineTuner
            tuner = HelsinkiFineTuner(
                progress_callback=lambda stage, pct, **kw: _emit_progress(stage, pct)
            )

            pairs = [{"chuukese": chuukese, "english": english}]
            directions = []
            if direction in ("both", "chk_to_en"):
                directions.append("chk_to_en")
            if direction in ("both", "en_to_chk"):
                directions.append("en_to_chk")

            success = True
            for d in directions:
                ok = tuner.fine_tune_model_lora(
                    direction=d,
                    training_pairs=pairs,
                    num_epochs=3,
                    batch_size=1,
                    adapter_output_dir=f"{LORA_ADAPTER_DIR}/{d}_latest",
                )
                if not ok:
                    success = False
                    run.log(f"LoRA {d} failed")

            with self._state_lock:
                self._lora_update_count += 1
                run.lora_updates = self._lora_update_count

            # Trigger merge if threshold reached
            if self._lora_update_count % LORA_MERGE_THRESHOLD == 0:
                run.log("LoRA merge threshold reached — scheduling merge+retrain")
                _emit_progress("LoRA threshold reached — scheduling merge run", 95)
                self.run_full_training_async(trigger="lora_merge")

            run.status = "completed" if success else "failed"
            run.finished_at = datetime.now(timezone.utc).isoformat()
            run.message = "LoRA update applied" if success else "LoRA update failed"
            _emit_progress(run.message, 100)

            # Reload translator weights
            self._reload_translator()

            return {"success": success, "message": run.message,
                    "lora_updates": self._lora_update_count}

        except Exception as e:
            run.status = "failed"
            run.message = str(e)
            run.finished_at = datetime.now(timezone.utc).isoformat()
            run.log(f"Error: {e}")
            logger.exception("LoRA teach_pair_lora error")
            return {"success": False, "message": str(e), "lora_updates": self._lora_update_count}
        finally:
            with self._state_lock:
                self._run_history.appendleft(run)
            self._save_run(run)

    # ------------------------------------------------------------------
    # Full fine-tune (scheduled, manual, or post-LoRA merge)
    # ------------------------------------------------------------------

    def run_full_training_async(
        self,
        trigger: str = "manual",
        progress_cb: Callable | None = None,
        num_epochs: int = 3,
        batch_size: int = 2,
    ) -> str:
        """
        Start a full fine-tune run in a background thread.
        Returns the run_id immediately.
        """
        if self.is_training:
            # Return current run id so caller can poll it
            return self._current_run.run_id if self._current_run else ""

        run_id = str(uuid.uuid4())
        t = threading.Thread(
            target=self._run_full_training,
            args=(run_id, trigger, progress_cb, num_epochs, batch_size),
            daemon=True,
            name=f"trainer-{run_id[:8]}",
        )
        t.start()
        return run_id

    def _run_full_training(
        self,
        run_id: str,
        trigger: str,
        progress_cb: Callable | None,
        num_epochs: int,
        batch_size: int,
    ) -> None:
        run = TrainingRun(run_id, trigger)
        run.mode = "full"

        with self._state_lock:
            self._current_run = run

        def emit(msg: str, pct: int | None = None, **kw):
            event = {
                "type": "training_progress",
                "run_id": run_id,
                "message": msg,
                "progress": pct,
                **kw,
            }
            self._emit(event)
            if progress_cb:
                try:
                    progress_cb(event)
                except Exception:
                    pass
            run.log(msg)

        try:
            emit("Collecting training pairs from all sources…", 5)
            pairs = self.collector.collect_all(min_confidence=50)
            run.pairs_used = len(pairs)
            self._last_pair_count = len(pairs)

            if len(pairs) < 5:
                run.status = "failed"
                run.message = f"Not enough pairs ({len(pairs)}); skipping."
                emit(run.message, 0)
                return

            emit(f"Loaded {len(pairs)} training pairs. Starting fine-tune…", 10)

            from src.training.helsinki_trainer import HelsinkiFineTuner

            def hk_progress(stage, pct, epoch=None, total_epochs=None,
                            epoch_step_pct=None, epoch_loss=None, **kw):
                emit(stage, pct,
                     epoch=epoch, total_epochs=total_epochs,
                     epoch_step_pct=epoch_step_pct, epoch_loss=epoch_loss)
                if epoch_loss is not None:
                    run.chk_to_en_loss = epoch_loss

            tuner = HelsinkiFineTuner(progress_callback=hk_progress)

            emit("Fine-tuning Chuukese→English…", 15)
            ok1 = tuner.fine_tune_model(
                direction="chk_to_en",
                training_pairs=pairs,
                num_epochs=num_epochs,
                batch_size=batch_size,
            )

            emit("Fine-tuning English→Chuukese…", 55)
            ok2 = tuner.fine_tune_model(
                direction="en_to_chk",
                training_pairs=pairs,
                num_epochs=num_epochs,
                batch_size=batch_size,
            )

            if ok1 and ok2:
                run.status = "completed"
                run.message = f"Fine-tune complete — {len(pairs)} pairs, {num_epochs} epochs"
                emit(run.message, 100)
                self._reload_translator()
                # Reset LoRA counter after successful full merge
                with self._state_lock:
                    self._lora_update_count = 0
            else:
                run.status = "failed"
                run.message = f"Fine-tune partial failure (chk→en={ok1}, en→chk={ok2})"
                emit(run.message, 100)

        except Exception as e:
            run.status = "failed"
            run.message = str(e)
            run.finished_at = datetime.now(timezone.utc).isoformat()
            run.log(f"Error: {e}")
            emit(f"Training error: {e}", 0)
            logger.exception("Full training run error")
        finally:
            run.finished_at = datetime.now(timezone.utc).isoformat()
            with self._state_lock:
                self._current_run = None
                self._run_history.appendleft(run)
            self._save_run(run)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reload_translator() -> None:
        """Tell the running Helsinki translator singleton to reload its weights."""
        try:
            import app as flask_app  # noqa: PLC0415
            if flask_app.helsinki_translator:
                flask_app.helsinki_translator.reload_models()
                logger.info("Helsinki translator weights reloaded")
        except Exception as e:
            logger.warning("Could not reload translator: %s", e)

    def _save_run(self, run: TrainingRun) -> None:
        try:
            path = Path(TRAINING_LOG_DIR) / f"{run.run_id}.json"
            with open(path, "w") as f:
                json.dump(run.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning("Could not save run log: %s", e)

    def get_run_history(self, limit: int = 20) -> list[dict]:
        with self._state_lock:
            return [r.to_dict() for r in list(self._run_history)[:limit]]

    def get_training_data_stats(self) -> dict:
        """Summary stats for the AI Training page data-sources panel."""
        try:
            db = self.collector.db
            dict_count = db.dictionary_collection.count_documents({})
            phrase_count = db.phrases_collection.count_documents({})
            para_count = db.paragraphs_collection.count_documents({})
            # Count individual sentences (each = one training pair), not paragraph docs
            try:
                col = db.client["chuuk_dictionary"]["article_analysis_paragraphs"]
                result = list(col.aggregate([
                    {"$project": {"sentence_count": {"$size": {"$ifNull": ["$paragraph.sentences", []]}}}},
                    {"$group": {"_id": None, "total": {"$sum": "$sentence_count"}}},
                ]))
                article_sentence_count = result[0]["total"] if result else 0
            except Exception:
                article_sentence_count = 0
            total = dict_count + phrase_count + para_count + article_sentence_count
            return {
                "dictionary_entries": dict_count,
                "phrase_pairs": phrase_count,
                "paragraph_pairs": para_count,
                "article_sentences": article_sentence_count,
                "total_pairs": total,
                "lora_update_count": self._lora_update_count,
            }
        except Exception as e:
            logger.warning("Stats error: %s", e)
            return {}
