#!/usr/bin/env python3

from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator


def test_helsinki_training():
    print("🚀 Testing Helsinki training pipeline...")
    translator = HelsinkiChuukeseTranslator()

    print("📥 Setting up models...")
    setup_success = translator.setup_models()

    if not setup_success:
        print("❌ Model setup failed")
        return False

    # Load data
    print("📚 Loading dictionary data...")
    data_count = translator.load_dictionary_data()

    if data_count == 0:
        print("❌ No training data available")
        return False

    print(f"✅ Loaded {data_count} translation pairs")

    # Use only a small subset for testing (50 examples)
    original_data = translator.training_data
    translator.training_data = original_data[:50]
    print(f"🧪 Testing with {len(translator.training_data)} examples...")

    # Test dataset preparation
    datasets = translator.prepare_training_dataset()
    train_dataset = datasets["chuukese_to_english"]

    print("Dataset examples:")
    for i in range(min(3, len(train_dataset))):
        example = train_dataset[i]
        print(f'  {i+1}. "{example["input_text"]}" -> "{example["target_text"]}"')

    # Test training with minimal configuration
    print("🎯 Starting training test...")
    try:
        success = translator.fine_tune_model(
            direction="chuukese_to_english", output_dir="models/test-helsinki", num_epochs=1, batch_size=1
        )

        if success:
            print("✅ Helsinki training completed successfully!")

            # Test the trained model
            print("🧪 Testing trained model...")
            result = translator.translate_chuukese_to_english("mwenge")
            print(f"Test translation: mwenge -> {result}")
            return True
        else:
            print("❌ Training failed")
            return False

    except Exception as e:
        print(f"❌ Training error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_helsinki_training()
