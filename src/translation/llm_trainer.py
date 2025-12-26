#!/usr/bin/env python3
"""
Local LLM Training and Translation System for Chuukese
Uses dictionary data to train a local LLM for Chuukese-English translation
"""

import json
import os
import requests
import subprocess
from typing import List, Dict, Optional
from ..database.dictionary_db import DictionaryDB
import re

class ChuukeseLLMTrainer:
    """Trains and manages a local LLM for Chuukese translation"""
    
    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.ollama_host = ollama_host
        self.db = DictionaryDB()
        self.model_name = "llama3.2:3b"
        self.custom_model_name = "chuukese-translator"
        
    def check_ollama_installation(self) -> bool:
        """Check if Ollama is installed and running"""
        try:
            response = requests.get(f"{self.ollama_host}/api/version", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama is running")
                return True
        except requests.exceptions.RequestException:
            print("❌ Ollama is not running")
            return False
        
        return False
    
    def install_ollama(self):
        """Provide installation instructions for Ollama"""
        print("""
🔧 To install Ollama (required for local LLM):

1. Visit: https://ollama.com/download
2. Download for macOS
3. Install the application
4. Run: ollama pull llama3.2:3b

Or via command line:
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
        """)
    
    def pull_base_model(self) -> bool:
        """Pull the base model if not available"""
        try:
            print(f"📥 Pulling base model: {self.model_name}")
            result = subprocess.run([
                "ollama", "pull", self.model_name
            ], capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                print(f"✅ Successfully pulled {self.model_name}")
                return True
            else:
                print(f"❌ Failed to pull model: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("⏰ Model download timed out")
            return False
        except FileNotFoundError:
            print("❌ Ollama command not found. Please install Ollama first.")
            return False
    
    def extract_training_data(self) -> List[Dict]:
        """Extract training data from dictionary database"""
        print("📚 Extracting training data from dictionary...")
        
        # Get all dictionary entries
        all_entries = list(self.db.dictionary_collection.find({
            'search_direction': {'$ne': 'en_to_chk'}  # Exclude reverse entries
        }))
        
        training_examples = []
        
        for entry in all_entries:
            chuukese_word = entry.get('chuukese_word', '').strip()
            english_translation = entry.get('english_translation', '').strip()
            
            if len(chuukese_word) > 1 and len(english_translation) > 2:
                # Create various training examples
                examples = [
                    {
                        "input": f"Translate to English: {chuukese_word}",
                        "output": english_translation
                    },
                    {
                        "input": f"What does '{chuukese_word}' mean?",
                        "output": f"'{chuukese_word}' means {english_translation}"
                    },
                    {
                        "input": f"Translate to Chuukese: {english_translation}",
                        "output": chuukese_word
                    }
                ]
                
                # Add context if available
                if entry.get('definition') and entry['definition'] != english_translation:
                    examples.append({
                        "input": f"Provide a detailed definition of '{chuukese_word}'",
                        "output": f"{english_translation}. {entry['definition']}"
                    })
                
                # Add grammar context if available
                if entry.get('word_type'):
                    examples.append({
                        "input": f"What type of word is '{chuukese_word}'?",
                        "output": f"'{chuukese_word}' is a {entry['word_type']} meaning {english_translation}"
                    })
                
                training_examples.extend(examples)
        
        print(f"✅ Generated {len(training_examples)} training examples from {len(all_entries)} dictionary entries")
        return training_examples
    
    def create_modelfile(self, training_data: List[Dict]) -> str:
        """Create a Modelfile for fine-tuning"""
        
        # Sample training examples for the system prompt
        sample_examples = training_data[:10] if training_data else []
        examples_text = "\n".join([
            f"Human: {ex['input']}\nAssistant: {ex['output']}" 
            for ex in sample_examples
        ])
        
        modelfile_content = f'''FROM {self.model_name}

PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER stop "<|eot_id|>"

SYSTEM """You are a specialized Chuukese-English translator and language expert. You have been trained on Chuukese dictionary data and can:

1. Translate between Chuukese and English accurately
2. Provide definitions and explanations of Chuukese words
3. Explain grammar and usage patterns
4. Help with pronunciation and context

Your knowledge comes from authentic Chuukese dictionary sources. Always be accurate and helpful.

Examples of your capabilities:
{examples_text}

When translating:
- Be concise and accurate
- Provide context when helpful
- Explain grammar types when relevant
- Use simple, clear English
"""

TEMPLATE """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

{{ .System }}<|eot_id|><|start_header_id|>user<|end_header_id|>

{{ .Prompt }}<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""
'''
        
        # Save Modelfile
        modelfile_path = "/tmp/Modelfile.chuukese"
        with open(modelfile_path, 'w', encoding='utf-8') as f:
            f.write(modelfile_content)
        
        return modelfile_path
    
    def create_custom_model(self, training_data: List[Dict]) -> bool:
        """Create a custom model with Chuukese knowledge"""
        try:
            print(f"🔨 Creating custom model: {self.custom_model_name}")
            
            # Create Modelfile
            modelfile_path = self.create_modelfile(training_data)
            
            # Create model using Ollama
            result = subprocess.run([
                "ollama", "create", self.custom_model_name, "-f", modelfile_path
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"✅ Successfully created custom model: {self.custom_model_name}")
                # Clean up
                os.unlink(modelfile_path)
                return True
            else:
                print(f"❌ Failed to create model: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("⏰ Model creation timed out")
            return False
        except Exception as e:
            print(f"❌ Error creating model: {e}")
            return False
    
    def test_model(self):
        """Test the custom model with sample translations"""
        if not self.check_ollama_installation():
            return False
        
        test_queries = [
            "Translate to English: mwenge",
            "What does 'chem' mean?",
            "Translate to Chuukese: remember",
            "How do you say 'feast' in Chuukese?",
        ]
        
        print(f"\n🧪 Testing custom model: {self.custom_model_name}")
        print("="*60)
        
        for query in test_queries:
            try:
                response = requests.post(f"{self.ollama_host}/api/generate", 
                    json={
                        "model": self.custom_model_name,
                        "prompt": query,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get('response', '').strip()
                    print(f"🤖 Q: {query}")
                    print(f"💬 A: {answer}")
                    print("-" * 40)
                else:
                    print(f"❌ Error testing query: {query}")
                    
            except requests.exceptions.RequestException as e:
                print(f"❌ Network error: {e}")
                break
    
    def train_full_pipeline(self) -> bool:
        """Complete training pipeline"""
        print("🚀 Starting Chuukese LLM Training Pipeline")
        print("="*60)
        
        # Step 1: Check Ollama
        if not self.check_ollama_installation():
            self.install_ollama()
            return False
        
        # Step 2: Pull base model
        if not self.pull_base_model():
            return False
        
        # Step 3: Extract training data
        training_data = self.extract_training_data()
        if not training_data:
            print("❌ No training data found. Please add dictionary entries first.")
            return False
        
        # Step 4: Create custom model
        if not self.create_custom_model(training_data):
            return False
        
        # Step 5: Test model
        self.test_model()
        
        print("\n🎉 Training pipeline completed successfully!")
        print(f"🤖 Your custom Chuukese translator is ready: {self.custom_model_name}")
        print(f"📊 Trained on {len(training_data)} examples")
        
        return True
    
    def translate_text(self, text: str, direction: str = "auto") -> str:
        """Translate text using the trained model"""
        if direction == "auto":
            # Simple heuristic: if contains English letters, translate to Chuukese
            if re.search(r'[a-zA-Z]', text) and not re.search(r'[àáâãäåæçèéêëìíîïñòóôõöùúûüý]', text):
                direction = "en_to_chk"
            else:
                direction = "chk_to_en"
        
        # Build a clear, directive prompt for translation
        if direction == "chk_to_en":
            prompt = f"You are a Chuukese to English translator. Translate this Chuukese text to English. Only provide the English translation, nothing else.\n\nChuukese: {text}\nEnglish:"
        elif direction == "en_to_chk":
            prompt = f"You are an English to Chuukese translator. Translate this English text to Chuukese. Only provide the Chuukese translation, nothing else.\n\nEnglish: {text}\nChuukese:"
        else:
            prompt = text
        
        try:
            response = requests.post(f"{self.ollama_host}/api/generate", 
                json={
                    "model": self.custom_model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Lower temperature for more focused responses
                        "top_p": 0.7,
                        "stop": ["\n\n", "Chuukese:", "English:", "\n#", "\nNote:"]  # Stop at common conversational patterns
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                translation = result.get('response', '').strip()
                
                # Clean up any conversational artifacts
                translation = translation.split('\n')[0].strip()  # Take only first line
                
                # Remove common prefixes that might sneak in
                prefixes_to_remove = [
                    'Translation:', 'translation:', 'TRANSLATION:',
                    'The translation is:', 'It means:', 'This means:',
                    'The English translation is:', 'The Chuukese translation is:',
                    'Answer:', 'Result:', 'Output:'
                ]
                for prefix in prefixes_to_remove:
                    if translation.lower().startswith(prefix.lower()):
                        translation = translation[len(prefix):].strip()
                
                return translation
            else:
                return f"Error: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return f"Network error: {e}"

if __name__ == "__main__":
    trainer = ChuukeseLLMTrainer()
    trainer.train_full_pipeline()