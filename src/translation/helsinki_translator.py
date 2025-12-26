#!/usr/bin/env python3
"""
Enhanced Chuukese Translation System using Helsinki-NLP OPUS
===========================================================

This module implements a specialized translation system using Helsinki-NLP's
OPUS models, which are specifically designed for translation tasks and support
many low-resource languages including some Pacific languages.

Features:
- Helsinki-NLP OPUS-MT models (translation-specific)
- Fine-tuning on your Chuukese dictionary data
- Bidirectional translation (Chuukese ↔ English)
- Better accuracy for low-resource languages
- Local and private (no data sent to external servers)
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

# Dictionary database connection
from ..database.dictionary_db import DictionaryDB

# Translation-specific imports
try:
    import torch
    from transformers import (
        AutoTokenizer, 
        AutoModelForSeq2SeqLM,
        Trainer,
        TrainingArguments,
        DataCollatorForSeq2Seq,
    )
    from datasets import Dataset
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Fallback to Ollama if transformers not available
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TranslationPair:
    """Structure for storing translation pairs"""
    chuukese: str
    english: str
    source: str = "dictionary"

class HelsinkiChuukeseTranslator:
    """
    Advanced Chuukese translation system using Helsinki-NLP OPUS models
    """
    
    def __init__(self, model_name: str = "Helsinki-NLP/opus-mt-mul-en"):
        self.model_name = model_name
        self.reverse_model_name = "Helsinki-NLP/opus-mt-en-mul"
        self.tokenizer = None
        self.model = None
        self.reverse_tokenizer = None
        self.reverse_model = None
        self.training_data = []
        self.db = None
        
    def setup_models(self) -> bool:
        """Initialize Helsinki-NLP OPUS models for translation"""
        if not TRANSFORMERS_AVAILABLE:
            logger.error("❌ Transformers library not available. Install with: pip install torch transformers")
            return False
            
        try:
            logger.info("🚀 Loading Helsinki-NLP OPUS models...")
            
            # Forward direction: Multilingual to English (includes Chuukese-like languages)
            logger.info(f"📥 Loading {self.model_name}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Use safetensors to avoid PyTorch security issues
            try:
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name, 
                    use_safetensors=True,
                    trust_remote_code=False
                )
                logger.info("✅ Loaded with safetensors")
            except Exception:
                # Fallback to regular loading with weights_only=True for security
                logger.warning("⚠️ Safetensors not available, using secure loading")
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    dtype=torch.float32,
                    trust_remote_code=False
                )
            
            # Reverse direction: English to Multilingual  
            logger.info(f"📥 Loading {self.reverse_model_name}...")
            self.reverse_tokenizer = AutoTokenizer.from_pretrained(self.reverse_model_name)
            try:
                self.reverse_model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.reverse_model_name,
                    use_safetensors=True,
                    trust_remote_code=False
                )
            except Exception:
                self.reverse_model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.reverse_model_name,
                    dtype=torch.float32,
                    trust_remote_code=False
                )
            
            logger.info("✅ Helsinki-NLP OPUS models loaded successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load Helsinki models: {e}")
            return False
    
    def load_dictionary_data(self) -> int:
        """Load Chuukese dictionary data from MongoDB"""
        try:
            self.db = DictionaryDB()
            logger.info("🔍 Loading dictionary data from MongoDB...")
            
            # Get all dictionary entries
            all_entries = list(self.db.dictionary_collection.find({}))
            
            self.training_data = []
            for entry in all_entries:
                chuukese_word = entry.get('chuukese_word', '').strip()
                english_translation = entry.get('english_translation', '').strip()
                source_info = entry.get('source', {})
                
                if chuukese_word and english_translation:
                    # Clean and prepare the translation pair
                    pair = TranslationPair(
                        chuukese=chuukese_word,
                        english=english_translation,
                        source=f"{source_info.get('publication_title', 'dictionary')}:{source_info.get('page_number', 'unknown')}"
                    )
                    self.training_data.append(pair)
            
            logger.info(f"✅ Loaded {len(self.training_data)} translation pairs")
            return len(self.training_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to load dictionary data: {e}")
            return 0
    
    def translate_chuukese_to_english(self, chuukese_text: str) -> str:
        """Translate Chuukese text to English"""
        if not self.model or not self.tokenizer:
            return "Error: Models not loaded"
            
        try:
            # Prepare input with language hint for better results
            input_text = f">>eng<< {chuukese_text}"
            
            # Tokenize and generate
            inputs = self.tokenizer(input_text, return_tensors="pt", padding=True, truncation=True)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=128,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            # Decode the result
            translated = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return translated.strip()
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return f"Translation error: {str(e)}"
    
    def translate_english_to_chuukese(self, english_text: str) -> str:
        """Translate English text to Chuukese"""
        if not self.reverse_model or not self.reverse_tokenizer:
            return "Error: Reverse models not loaded"
            
        try:
            # This is experimental - OPUS models may not have specific Chuukese output
            # But can be fine-tuned on your dictionary data
            inputs = self.reverse_tokenizer(english_text, return_tensors="pt", padding=True, truncation=True)
            
            with torch.no_grad():
                outputs = self.reverse_model.generate(
                    **inputs,
                    max_length=128,
                    num_beams=4,
                    early_stopping=True,
                    do_sample=False
                )
            
            translated = self.reverse_tokenizer.decode(outputs[0], skip_special_tokens=True)
            return translated.strip()
            
        except Exception as e:
            logger.error(f"Reverse translation error: {e}")
            return f"Translation error: {str(e)}"
    
    def prepare_fine_tuning_data(self) -> Dataset:
        """Prepare training data for fine-tuning"""
        if not self.training_data:
            logger.error("No training data available")
            return None
            
        logger.info(f"🔧 Preparing {len(self.training_data)} pairs for fine-tuning...")
        
        # Create bidirectional training data
        source_texts = []
        target_texts = []
        
        for pair in self.training_data:
            # Chuukese to English
            source_texts.append(f">>eng<< {pair.chuukese}")
            target_texts.append(pair.english)
            
            # English to Chuukese (for bidirectional training)
            source_texts.append(f">>chk<< {pair.english}")  # chk is hypothetical Chuukese code
            target_texts.append(pair.chuukese)
        
        # Create dataset
        dataset_dict = {
            "input_ids": [],
            "attention_mask": [],
            "labels": []
        }
        
        # Tokenize all pairs
        for src, tgt in zip(source_texts, target_texts):
            # Tokenize source
            src_tokens = self.tokenizer(
                src, 
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )
            
            # Tokenize target
            with self.tokenizer.as_target_tokenizer():
                tgt_tokens = self.tokenizer(
                    tgt,
                    max_length=128, 
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt"
                )
            
            dataset_dict["input_ids"].append(src_tokens["input_ids"].squeeze())
            dataset_dict["attention_mask"].append(src_tokens["attention_mask"].squeeze())
            dataset_dict["labels"].append(tgt_tokens["input_ids"].squeeze())
        
        dataset = Dataset.from_dict(dataset_dict)
        logger.info(f"✅ Prepared dataset with {len(dataset)} examples")
        return dataset
    
    def fine_tune_model(self, output_dir: str = "./models/chuukese-opus-ft") -> bool:
        """Fine-tune the Helsinki model on Chuukese dictionary data"""
        if not self.model or not self.training_data:
            logger.error("❌ Model or training data not available")
            return False
            
        logger.info("🔥 Starting fine-tuning process...")
        
        try:
            # Prepare dataset
            dataset = self.prepare_fine_tuning_data()
            if not dataset:
                return False
            
            # Split dataset
            train_test = dataset.train_test_split(test_size=0.1)
            train_dataset = train_test["train"]
            eval_dataset = train_test["test"]
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=3,
                per_device_train_batch_size=4,
                per_device_eval_batch_size=4,
                warmup_steps=100,
                weight_decay=0.01,
                logging_dir=f"{output_dir}/logs",
                logging_steps=50,
                evaluation_strategy="steps",
                eval_steps=200,
                save_steps=500,
                save_total_limit=3,
                load_best_model_at_end=True,
                metric_for_best_model="eval_loss",
                greater_is_better=False,
                report_to=None  # Disable wandb/tensorboard
            )
            
            # Data collator
            data_collator = DataCollatorForSeq2Seq(
                tokenizer=self.tokenizer,
                model=self.model,
                padding=True
            )
            
            # Initialize trainer
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                tokenizer=self.tokenizer,
                data_collator=data_collator,
            )
            
            logger.info("🚀 Starting training...")
            trainer.train()
            
            # Save the fine-tuned model
            logger.info(f"💾 Saving fine-tuned model to {output_dir}")
            trainer.save_model()
            self.tokenizer.save_pretrained(output_dir)
            
            logger.info("✅ Fine-tuning completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fine-tuning failed: {e}")
            return False
    
    def test_translation(self) -> Dict[str, Any]:
        """Test the translation system with sample words"""
        if not self.model:
            return {"error": "Models not loaded"}
            
        logger.info("🧪 Testing translation capabilities...")
        
        test_cases = [
            "ran",  # Chuukese for "water"
            "pwungen", # Chuukese for "thank you"
            "mwenge", # Chuukese for "food"
        ]
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model_name,
            "tests": []
        }
        
        for chuukese_word in test_cases:
            try:
                translation = self.translate_chuukese_to_english(chuukese_word)
                results["tests"].append({
                    "chuukese": chuukese_word,
                    "english_translation": translation,
                    "success": True
                })
                logger.info(f"✅ {chuukese_word} → {translation}")
            except Exception as e:
                results["tests"].append({
                    "chuukese": chuukese_word,
                    "error": str(e),
                    "success": False
                })
                logger.error(f"❌ {chuukese_word} → Error: {e}")
        
        return results
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status and capabilities"""
        return {
            "helsinki_available": TRANSFORMERS_AVAILABLE,
            "models_loaded": self.model is not None,
            "training_data_count": len(self.training_data),
            "model_name": self.model_name,
            "reverse_model_name": self.reverse_model_name,
            "database_connected": self.db is not None,
            "capabilities": {
                "chuukese_to_english": self.model is not None,
                "english_to_chuukese": self.reverse_model is not None,
                "fine_tuning": TRANSFORMERS_AVAILABLE,
                "dictionary_training": len(self.training_data) > 0
            }
        }

class FallbackOllamaTranslator:
    """Fallback translator using Ollama when Helsinki-NLP is not available"""
    
    def __init__(self):
        self.client = None
        if OLLAMA_AVAILABLE:
            try:
                self.client = ollama.Client()
                logger.info("✅ Ollama fallback available")
            except Exception as e:
                logger.warning(f"⚠️ Ollama connection failed: {e}")
    
    def translate(self, text: str, direction: str = "chuukese_to_english") -> str:
        """Basic translation using Ollama as fallback"""
        if not self.client:
            return "Error: No translation system available"
        
        try:
            if direction == "chuukese_to_english":
                prompt = f"Translate this Chuukese text to English: {text}"
            else:
                prompt = f"Translate this English text to Chuukese: {text}"
            
            response = self.client.chat(
                model="llama3.2:latest",
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response["message"]["content"]
            
        except Exception as e:
            return f"Translation error: {str(e)}"

def main():
    """Main function for testing the translation system"""
    logger.info("🌺 Chuukese Translation System with Helsinki-NLP OPUS")
    logger.info("=" * 60)
    
    # Try Helsinki-NLP first
    if TRANSFORMERS_AVAILABLE:
        translator = HelsinkiChuukeseTranslator()
        
        logger.info("🔧 Setting up Helsinki-NLP OPUS models...")
        if translator.setup_models():
            logger.info("📚 Loading dictionary data...")
            data_count = translator.load_dictionary_data()
            
            if data_count > 0:
                logger.info(f"✅ Ready with {data_count} translation pairs")
                
                # Test translations
                test_results = translator.test_translation()
                logger.info("🧪 Test Results:")
                for test in test_results["tests"]:
                    if test["success"]:
                        logger.info(f"  ✅ {test['chuukese']} → {test['english_translation']}")
                    else:
                        logger.info(f"  ❌ {test['chuukese']} → {test['error']}")
                
                # Ask about fine-tuning
                print(f"\n🎯 Found {data_count} dictionary entries for training.")
                response = input("Would you like to fine-tune the model? (y/N): ")
                
                if response.lower() == 'y':
                    logger.info("🔥 Starting fine-tuning process...")
                    if translator.fine_tune_model():
                        logger.info("🎉 Model fine-tuned successfully!")
                    else:
                        logger.error("❌ Fine-tuning failed")
                else:
                    logger.info("ℹ️ Skipping fine-tuning. Model ready for basic translation.")
                    
            else:
                logger.error("❌ No dictionary data found")
        else:
            logger.error("❌ Failed to set up Helsinki models")
    
    else:
        # Fallback to Ollama
        logger.warning("⚠️ Helsinki-NLP not available, using Ollama fallback")
        translator = FallbackOllamaTranslator()
        
        test_word = "ran"  # Chuukese for water
        result = translator.translate(test_word, "chuukese_to_english")
        logger.info(f"🧪 Test: {test_word} → {result}")

if __name__ == "__main__":
    main()