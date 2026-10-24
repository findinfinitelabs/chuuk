"""
Engine selection for translation models.

``TRANSLATION_ENGINE`` env var:
    helsinki  (default) — Helsinki-NLP OPUS-MT Marian models, one per direction
    madlad              — Google MADLAD-400 3B with a LoRA adapter, one model for both directions

Both the runtime translator and the fine-tuner are chosen here so ``app.py`` and
``continuous_trainer.py`` never need to know which engine is active.
"""

from __future__ import annotations

import os
from collections.abc import Callable

VALID_ENGINES = ("helsinki", "madlad")


def translation_engine() -> str:
    engine = os.getenv("TRANSLATION_ENGINE", "helsinki").strip().lower()
    return engine if engine in VALID_ENGINES else "helsinki"


def engine_display_name(engine: str | None = None) -> str:
    engine = engine or translation_engine()
    return "MADLAD-400" if engine == "madlad" else "Helsinki-NLP"


def get_translator():
    """Instantiate (but do not load) the runtime translator for the active engine."""
    if translation_engine() == "madlad":
        from src.translation.madlad_translator import MadladChuukeseTranslator

        return MadladChuukeseTranslator()
    from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator

    return HelsinkiChuukeseTranslator()


def get_fine_tuner(progress_callback: Callable | None = None):
    """Instantiate the fine-tuner for the active engine."""
    if translation_engine() == "madlad":
        from src.training.madlad_trainer import MadladFineTuner

        return MadladFineTuner(progress_callback=progress_callback)
    from src.training.helsinki_trainer import HelsinkiFineTuner

    return HelsinkiFineTuner(progress_callback=progress_callback)
