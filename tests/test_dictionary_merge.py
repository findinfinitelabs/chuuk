"""Merging duplicate dictionary entries."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.dictionary_merge import merge_group, merge_new_into_existing, merge_senses


def test_merge_senses_dedupes_and_keeps_distinct():
    assert merge_senses("ghost of", "color of", "ghost of") == "ghost of; color of"
    assert merge_senses("keep, own, possess", "keep, possess, have") == "keep, own, possess; keep, possess, have"
    assert merge_senses("keep, possess", "keep, possess, have") == "keep, possess, have"
    assert merge_senses("cause to happen", "Cause to happen.") == "cause to happen"


def test_identical_copies_collapse_without_changes():
    a = {"_id": "1", "chuukese_word": "efisi", "english_translation": "cause to happen", "grammar": "verb", "definition": "From fis"}
    b = {**a, "_id": "2"}
    r = merge_group([a, b])
    assert r["identical"] is True
    assert r["survivor"]["_id"] == "1"
    assert r["absorbed"] == ["2"]
    assert r["update"] == {}


def test_different_senses_merge_and_longest_definition_wins():
    a = {"_id": "1", "chuukese_word": "élúwen", "english_translation": "ghost of", "grammar": "noun", "definition": "Means “ghost of (someone).”"}
    b = {"_id": "2", "chuukese_word": "élúwen", "english_translation": "color of", "grammar": "noun", "definition": "Means “color of ___.”"}
    r = merge_group([a, b])
    assert r["identical"] is False
    assert r["update"]["english_translation"] == "ghost of; color of"
    assert r["update"].get("definition") in (None, "Means “ghost of (someone).”")
    assert r["update"]["other_definitions"] == ["Means “color of ___.”"]
    assert r["grammar_conflict"] is None


def test_grammar_majority_applied_and_conflict_reported():
    copies = [
        {"_id": "1", "chuukese_word": "epwe", "english_translation": "he/she/it will", "grammar": "particle", "definition": "Future marker"},
        {"_id": "2", "chuukese_word": "epwe", "english_translation": "he/she/it will", "grammar": "particle", "definition": "Simple future."},
        {"_id": "3", "chuukese_word": "epwe", "english_translation": "he/she/it will", "grammar": "pronoun", "definition": "future"},
    ]
    r = merge_group(copies)
    assert r["grammar_conflict"]["majority"] == "particle"
    assert r["grammar_conflict"]["votes"] == {"particle": 2, "pronoun": 1}
    assert "grammar" not in r["update"] or r["update"]["grammar"] == "particle"


def test_grammar_tie_is_left_for_review():
    copies = [
        {"_id": "1", "chuukese_word": "x", "english_translation": "a", "grammar": "verb", "definition": "d"},
        {"_id": "2", "chuukese_word": "x", "english_translation": "a", "grammar": "noun", "definition": "d"},
    ]
    r = merge_group(copies)
    assert r["grammar_conflict"]["majority"] is None
    assert "grammar" not in r["update"]


def test_survivor_is_best_populated_then_oldest():
    sparse = {"_id": "1", "chuukese_word": "x", "english_translation": "a", "grammar": None, "definition": ""}
    rich = {"_id": "2", "chuukese_word": "x", "english_translation": "a", "grammar": "verb", "definition": "long definition"}
    assert merge_group([sparse, rich])["survivor"]["_id"] == "2"


def test_import_merge_adds_sense_but_never_flips_grammar():
    existing = {"_id": "1", "chuukese_word": "x", "english_translation": "ghost of", "grammar": "noun", "definition": "Means ghost of."}
    new = {"chuukese_word": "x", "english_translation": "color of", "grammar": "verb", "definition": "Means color of (something), fully."}
    update = merge_new_into_existing(existing, new)
    assert update["english_translation"] == "ghost of; color of"
    assert update["definition"].startswith("Means color of")
    assert "grammar" not in update
    assert merge_new_into_existing(existing, {**existing, "_id": None}) == {}
