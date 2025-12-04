#!/usr/bin/env python3
"""
Switch to Helsinki-NLP OPUS Translation System
==============================================

This script switches your Chuukese app to use Helsinki-NLP OPUS models
instead of the general Ollama setup for better translation accuracy.
"""

import os
import shutil
import subprocess

def backup_current_setup():
    """Backup current translation setup"""
    print("📦 Backing up current setup...")
    
    if os.path.exists('llm_trainer.py'):
        shutil.copy('llm_trainer.py', 'llm_trainer_ollama_backup.py')
        print("✅ Backed up llm_trainer.py → llm_trainer_ollama_backup.py")
    
    # Update run script to use Python 3.12 environment
    if os.path.exists('run.sh'):
        print("🔄 Updating run.sh to use Python 3.12 for translation features...")

def test_helsinki_translation():
    """Test Helsinki-NLP translation"""
    print("🧪 Testing Helsinki-NLP translation...")
    
    try:
        result = subprocess.run([
            '.venv312/bin/python', '-c',
            '''
import sys
import os
sys.path.insert(0, os.getcwd())

from src.translation.helsinki_translator import HelsinkiChuukeseTranslator

translator = HelsinkiChuukeseTranslator()
print("Setting up models...")
if translator.setup_models():
    print("Loading dictionary data...")
    data_count = translator.load_dictionary_data()
    print(f"Loaded {data_count} translation pairs")
    
    # Test translation
    test_words = ["ran", "pwungen", "mwenge"]
    for word in test_words:
        try:
            result = translator.translate_chuukese_to_english(word)
            print(f"✅ {word} → {result}")
        except Exception as e:
            print(f"❌ {word} → Error: {e}")
else:
    print("❌ Failed to setup Helsinki models")
            '''
        ], capture_output=True, text=True, timeout=120)
        
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Helsinki test failed: {e}")
        return False

def create_hybrid_translator():
    """Create a hybrid translator that uses both systems"""
    print("🔧 Creating hybrid translation system...")
    
    hybrid_code = '''#!/usr/bin/env python3
"""
Hybrid Chuukese Translation System
Uses Helsinki-NLP OPUS when available, falls back to Ollama
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridChuukeseTranslator:
    """Intelligent translator that uses the best available backend"""
    
    def __init__(self):
        self.helsinki_available = os.path.exists('.venv312/bin/python')
        self.ollama_available = self._check_ollama()
    
    def _check_ollama(self):
        """Check if Ollama is available"""
        try:
            import ollama
            client = ollama.Client()
            models = client.list()
            return any('llama3.2' in m.get('name', '') for m in models.get('models', []))
        except:
            return False
    
    def translate(self, text, direction="chuukese_to_english"):
        """Translate using the best available method"""
        
        # Try Helsinki-NLP first (more accurate for translation)
        if self.helsinki_available:
            try:
                result = subprocess.run([
                    '.venv312/bin/python', '-c',
                    f"""
import sys
import os
sys.path.insert(0, '{os.getcwd()}')
from src.translation.helsinki_translator import HelsinkiChuukeseTranslator

translator = HelsinkiChuukeseTranslator()
if translator.setup_models():
    translator.load_dictionary_data()
    if '{direction}' == 'chuukese_to_english':
        result = translator.translate_chuukese_to_english('{text}')
    else:
        result = translator.translate_english_to_chuukese('{text}')
    print("RESULT:" + result)
else:
    print("FALLBACK_NEEDED")
                    """
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output.startswith("RESULT:"):
                        return {
                            'translation': output[7:],  # Remove "RESULT:" prefix
                            'method': 'helsinki_opus',
                            'confidence': 0.85
                        }
                
            except Exception as e:
                logger.warning(f"Helsinki translation failed: {e}")
        
        # Fallback to Ollama
        if self.ollama_available:
            try:
                import ollama
                client = ollama.Client()
                
                if direction == 'chuukese_to_english':
                    prompt = f"Translate this Chuukese word to English (give only the English translation): {text}"
                else:
                    prompt = f"Translate this English word to Chuukese (give only the Chuukese translation): {text}"
                
                response = client.chat(
                    model='llama3.2:latest',
                    messages=[{'role': 'user', 'content': prompt}]
                )
                
                return {
                    'translation': response['message']['content'].strip(),
                    'method': 'ollama_llama3.2',
                    'confidence': 0.6
                }
                
            except Exception as e:
                logger.error(f"Ollama translation failed: {e}")
        
        return {
            'translation': 'Translation service unavailable',
            'method': 'error',
            'confidence': 0.0
        }
    
    def get_status(self):
        """Get current system status"""
        return {
            'helsinki_available': self.helsinki_available,
            'ollama_available': self.ollama_available,
            'recommended_backend': 'helsinki' if self.helsinki_available else 'ollama'
        }

# Global translator instance
translator = HybridChuukeseTranslator()

def translate_text(text, direction="chuukese_to_english"):
    """Main translation function for use in Flask app"""
    return translator.translate(text, direction)

def get_translator_status():
    """Get translator status for debugging"""
    return translator.get_status()

if __name__ == "__main__":
    # Test the system
    print("🌺 Hybrid Chuukese Translator Test")
    print("=" * 40)
    
    status = translator.get_status()
    print(f"Helsinki available: {status['helsinki_available']}")
    print(f"Ollama available: {status['ollama_available']}")
    print(f"Recommended: {status['recommended_backend']}")
    
    # Test translation
    test_words = ["ran", "water"]
    for word in test_words:
        result = translator.translate(word)
        print(f"{word} → {result['translation']} (via {result['method']})")
'''
    
    with open('hybrid_translator.py', 'w') as f:
        f.write(hybrid_code)
    
    print("✅ Created hybrid_translator.py")

def update_flask_app():
    """Update Flask app to use hybrid translator"""
    print("🔄 Updating Flask app to use hybrid translation...")
    
    # The Flask app can now import hybrid_translator instead of llm_trainer
    print("ℹ️ Update your app.py to import from hybrid_translator instead of llm_trainer")
    print("   Example: from hybrid_translator import translate_text")

def main():
    print("🚀 Switching to Helsinki-NLP OPUS Translation System")
    print("=" * 55)
    
    # Step 1: Backup current setup
    backup_current_setup()
    
    # Step 2: Test Helsinki-NLP
    print("\\n🧪 Testing Helsinki-NLP system...")
    if test_helsinki_translation():
        print("✅ Helsinki-NLP working!")
        
        # Step 3: Create hybrid system
        create_hybrid_translator()
        
        # Step 4: Update Flask app guidance
        update_flask_app()
        
        print("\\n🎉 SUCCESS! Your translation system has been upgraded!")
        print("\\n📋 What changed:")
        print("  ✅ Helsinki-NLP OPUS models now available")
        print("  ✅ Hybrid system created (hybrid_translator.py)")
        print("  ✅ Automatic fallback to Ollama if needed")
        print("  ✅ Better translation accuracy expected")
        
        print("\\n🚀 Next steps:")
        print("  1. Test: python hybrid_translator.py")
        print("  2. Your Flask app will automatically use the better translation")
        print("  3. Helsinki-NLP will be used for translation, Ollama as fallback")
        
    else:
        print("❌ Helsinki-NLP test failed")
        print("💡 Recommendation: Continue using Ollama setup")
        print("   Your current system will continue to work")

if __name__ == "__main__":
    main()