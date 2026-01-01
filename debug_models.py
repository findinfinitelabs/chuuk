#!/usr/bin/env python3
"""Debug model loading and translation"""

from transformers import pipeline
from pathlib import Path

def test_model(model_path, test_text, model_name="finetuned"):
    print(f"Testing model at: {model_path}")
    print(f"Test text: '{test_text}'")

    try:
        # Check if path exists
        if not Path(model_path).exists():
            print(f"❌ Model path does not exist: {model_path}")
            return

        # Load model
        print("Loading model...")
        model = pipeline('translation', model=str(model_path))
        print("Model loaded successfully")

        # Test translation
        print("Testing translation...")
        result = model(test_text, max_length=128)
        translation = result[0]['translation_text']
        print(f"✅ Translation result: '{translation}'")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_base_model(model_name, test_text):
    print(f"Testing base model: {model_name}")
    print(f"Test text: '{test_text}'")

    try:
        model = pipeline('translation', model=model_name)
        result = model(test_text, max_length=128)
        translation = result[0]['translation_text']
        print(f"✅ Base model result: '{translation}'")
    except Exception as e:
        print(f"❌ Base model error: {e}")

if __name__ == "__main__":
    # Test base models first
    print("=== TESTING BASE MODELS ===")
    test_base_model("Helsinki-NLP/opus-mt-en-chk", "[noun] dollar")
    print()
    test_base_model("Helsinki-NLP/opus-mt-chk-en", "[noun] chala")
    print("\n" + "="*50 + "\n")

    # Test fine-tuned models with actual training data
    print("=== TESTING FINE-TUNED MODELS WITH TRAINING DATA ===")
    chk_to_en_path = "models/helsinki-chuukese_chuukese_to_english/finetuned"
    test_model(chk_to_en_path, "[noun] chala")  # Should translate to "dollar"

    print("\n" + "="*50 + "\n")

    en_to_chk_path = "models/helsinki-chuukese_english_to_chuukese/finetuned"
    test_model(en_to_chk_path, "[noun] dollar")  # Should translate to "chala"