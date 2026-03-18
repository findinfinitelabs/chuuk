#!/usr/bin/env python3
"""
Quick setup check and training script for Chuukese LLM
"""

import subprocess


def check_ollama():
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama is installed")
            return True
        else:
            print("❌ Ollama is not working properly")
            return False
    except FileNotFoundError:
        print("❌ Ollama is not installed")
        return False


def install_ollama_instructions():
    """Provide Ollama installation instructions"""
    print("""
🔧 INSTALL OLLAMA:

For macOS:
1. Visit: https://ollama.com/download
2. Download and install the macOS app
3. Or via command line: brew install ollama

For Linux:
curl -fsSL https://ollama.com/install.sh | sh

After installation:
ollama pull llama3.2:3b
    """)


def check_database():
    """Check if we have dictionary data"""
    try:
        from ..src.database.dictionary_db import DictionaryDB

        db = DictionaryDB()
        stats = db.get_statistics()
        entries = stats.get("total_entries", 0)

        if entries > 0:
            print(f"✅ Database has {entries} dictionary entries ready for training")
            return True
        else:
            print("❌ No dictionary entries found")
            print("   Please upload dictionary files first via the web interface")
            return False
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False


def train_model():
    """Train the LLM model"""
    try:
        from ..src.translation.llm_trainer import ChuukeseLLMTrainer

        trainer = ChuukeseLLMTrainer()

        print("🚀 Starting LLM training...")
        success = trainer.train_full_pipeline()

        if success:
            print("🎉 Training completed successfully!")
            print("💬 You can now use the AI translation feature")
            return True
        else:
            print("❌ Training failed")
            return False

    except Exception as e:
        print(f"❌ Training error: {e}")
        return False


def main():
    print("🤖 Chuukese LLM Setup & Training")
    print("=" * 50)

    # Check prerequisites
    ollama_ok = check_ollama()
    if not ollama_ok:
        install_ollama_instructions()
        return

    db_ok = check_database()
    if not db_ok:
        print("\n📚 Please add dictionary content first:")
        print("1. Go to http://localhost:5001")
        print("2. Upload dictionary files (PDF/DOCX)")
        print("3. Enable 'Index Dictionary' option")
        print("4. Process the files")
        print("5. Run this script again")
        return

    # Everything looks good, start training
    print("\n🎯 All prerequisites met!")
    response = input("Start training the AI model? (y/N): ").strip().lower()

    if response in ["y", "yes"]:
        train_model()
    else:
        print("Training cancelled. Run this script again when ready.")


if __name__ == "__main__":
    main()
