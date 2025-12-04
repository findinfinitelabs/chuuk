#!/usr/bin/env python3
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
from .helsinki_translator import HelsinkiChuukeseTranslator

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
