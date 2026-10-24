"""
Unit tests for the MADLAD-400 trainer / translator plumbing.

These never load the 3B model — they cover the pure-Python pieces: prefix
tokens, example construction, train/eval splitting, engine selection, and the
model-root resolution that decides where adapters are written.
"""

import os

import pytest

from src.training import trainer_factory
from src.training.madlad_trainer import build_examples, split_pairs
from src.translation import madlad_translator as mt


PAIRS = [
    {"chuukese": "ran annim", "english": "good day"},
    {"chuukese": "kinisou", "english": "thank you"},
    {"chuukese": "", "english": "dropped"},
    {"chuukese": "   ", "english": "also dropped"},
]


def test_add_prefix_uses_madlad_language_tokens():
    assert mt.add_prefix("ran annim", "chk_to_en") == "<2en> ran annim"
    assert mt.add_prefix("  good day ", "en_to_chk") == "<2chk> good day"


def test_build_examples_both_directions_skips_empty():
    ex = build_examples(PAIRS, "both")
    assert len(ex) == 4
    assert {"source": "<2en> ran annim", "target": "good day"} in ex
    assert {"source": "<2chk> good day", "target": "ran annim"} in ex


@pytest.mark.parametrize("direction,prefix", [("chk_to_en", "<2en>"), ("en_to_chk", "<2chk>")])
def test_build_examples_single_direction(direction, prefix):
    ex = build_examples(PAIRS, direction)
    assert len(ex) == 2
    assert all(e["source"].startswith(prefix) for e in ex)


def test_split_pairs_is_deterministic_and_disjoint():
    pairs = [{"chuukese": f"c{i}", "english": f"e{i}"} for i in range(200)]
    train1, eval1 = split_pairs(pairs, eval_fraction=0.1, seed=7)
    train2, eval2 = split_pairs(pairs, eval_fraction=0.1, seed=7)
    assert eval1 == eval2 and train1 == train2
    assert len(eval1) == 20
    assert not {p["chuukese"] for p in eval1} & {p["chuukese"] for p in train1}


def test_split_pairs_no_eval_for_tiny_sets():
    pairs = [{"chuukese": f"c{i}", "english": f"e{i}"} for i in range(5)]
    train, ev = split_pairs(pairs)
    assert ev == [] and len(train) == 5


def test_model_root_prefers_model_store(monkeypatch):
    monkeypatch.delenv("MODEL_STORE_PATH", raising=False)
    assert mt.model_root() == os.path.join("models", "madlad400-chuukese")
    monkeypatch.setenv("MODEL_STORE_PATH", "/mnt/store/")
    assert mt.model_root() == "/mnt/store/madlad400-chuukese"


def test_engine_selection_defaults_to_helsinki(monkeypatch):
    monkeypatch.delenv("TRANSLATION_ENGINE", raising=False)
    assert trainer_factory.translation_engine() == "helsinki"
    monkeypatch.setenv("TRANSLATION_ENGINE", "MADLAD")
    assert trainer_factory.translation_engine() == "madlad"
    assert trainer_factory.engine_display_name() == "MADLAD-400"
    monkeypatch.setenv("TRANSLATION_ENGINE", "bogus")
    assert trainer_factory.translation_engine() == "helsinki"


def test_madlad_fine_tuner_is_bidirectional(monkeypatch):
    monkeypatch.setenv("TRANSLATION_ENGINE", "madlad")
    monkeypatch.setenv("FORCE_CPU", "1")
    tuner = trainer_factory.get_fine_tuner()
    assert tuner.bidirectional is True
    assert tuner.device == "cpu"
    assert tuner.lora_path.endswith(os.path.join("madlad400-chuukese", "lora"))
