#!/usr/bin/env python3
"""
Quick test of the new translation system
========================================
"""

import sys
import os
sys.path.insert(0, os.getcwd())

def test_current_system():
    """Test the current Ollama-based system"""
    print("🧪 Testing Current Ollama System")
    print("=" * 40)
    
    try:
        from src.translation.llm_trainer import ChuukeseLLMTrainer
        trainer = ChuukeseLLMTrainer()
        
        if trainer.check_ollama_installation():
            print("✅ Ollama is running")
            
            # Test translation
            test_words = ["ran", "pwungen", "mwenge"]
            for word in test_words:
                try:
                    result = trainer.translate_text(word, "chuukese_to_english")
                    print(f"  {word} → {result}")
                except Exception as e:
                    print(f"  {word} → Error: {e}")
        else:
            print("❌ Ollama not running")
            
    except Exception as e:
        print(f"❌ Current system error: {e}")

def test_simple_ollama():
    """Test direct Ollama connection"""
    print("\n🔗 Testing Direct Ollama Connection")
    print("=" * 40)
    
    try:
        import ollama
        client = ollama.Client()
        
        # Test if model is available
        models = client.list()
        llama_models = [m for m in models.get('models', []) if 'llama3.2' in m.get('name', '')]
        
        if llama_models:
            print(f"✅ Found model: {llama_models[0]['name']}")
            
            # Test simple translation
            response = client.chat(
                model='llama3.2:latest',
                messages=[{
                    'role': 'user', 
                    'content': 'Translate this Chuukese word to English: ran (it means water)'
                }]
            )
            
            result = response['message']['content']
            print(f"  Test translation: ran → {result}")
            
        else:
            print("❌ No llama3.2 model found")
            print("Available models:", [m.get('name') for m in models.get('models', [])])
            
    except Exception as e:
        print(f"❌ Direct Ollama error: {e}")

def test_database():
    """Test database connection and data"""
    print("\n📚 Testing Database Connection")
    print("=" * 40)
    
    try:
        from src.database.dictionary_db import DictionaryDB
        db = DictionaryDB()
        
        count = db.dictionary_collection.count_documents({})
        print(f"✅ Database connected: {count} entries")
        
        if count > 0:
            # Show a few examples
            sample = list(db.dictionary_collection.find({}).limit(3))
            print("Sample entries:")
            for entry in sample:
                chuukese = entry.get('chuukese_word', 'N/A')
                english = entry.get('english_translation', 'N/A')
                print(f"  {chuukese} → {english}")
        
    except Exception as e:
        print(f"❌ Database error: {e}")

def get_system_recommendations():
    """Get recommendations based on current system state"""
    print("\n💡 System Recommendations")
    print("=" * 40)
    
    # Check Python 3.12 environment
    if os.path.exists('.venv312/bin/python'):
        print("✅ Python 3.12 environment available for Helsinki-NLP")
        
        # Test if Helsinki-NLP can be imported
        try:
            import subprocess
            result = subprocess.run([
                '.venv312/bin/python', '-c', 
                'import torch; from transformers import AutoTokenizer; print("SUCCESS")'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and 'SUCCESS' in result.stdout:
                print("✅ Helsinki-NLP dependencies ready")
                print("🎯 RECOMMENDATION: Switch to Helsinki-NLP for better translation accuracy")
                print("   Run: .venv312/bin/python helsinki_translator.py")
            else:
                print("⚠️ Helsinki-NLP dependencies have issues")
                print("🎯 RECOMMENDATION: Use current Ollama setup (working)")
        except Exception as e:
            print(f"⚠️ Helsinki-NLP test failed: {e}")
            print("🎯 RECOMMENDATION: Use current Ollama setup")
    else:
        print("⚠️ No Python 3.12 environment found")
        print("🎯 RECOMMENDATION: Use current Ollama setup")

def main():
    print("🌺 Chuukese Translation System Test")
    print("=" * 50)
    
    test_database()
    test_current_system() 
    test_simple_ollama()
    get_system_recommendations()
    
    print("\n🎉 Test completed!")

if __name__ == "__main__":
    main()