#!/usr/bin/env python3
"""
Enhanced Chuukese Translation System using Helsinki-NLP Models
=============================================================

This module implements a specialized translation system using Helsinki-NLP's
OPUS models for Chuukese language translation. Helsinki-NLP models are 
specifically designed for translation tasks and perform better than general
LLMs for language translation, especially for low-resource languages.

Features:
- Helsinki-NLP OPUS-MT models (specialized for translation)
- Fine-tuning capabilities on Chuukese dictionary data
- Bidirectional translation (Chuukese ↔ English)
- Support for training custom Chuukese models
- Better accuracy for Pacific languages
- Local and private (no external API calls)
"""

import os
import json
import torch
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

# Translation-specific imports
from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq,
    pipeline
)
from datasets import Dataset
import numpy as np

# Dictionary database connection
try:
    from ..database.dictionary_db import DictionaryDB
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from src.database.dictionary_db import DictionaryDB

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
    Specialized for translation tasks with fine-tuning capabilities.
    """
    
    def __init__(self, 
                 base_model: str = "Helsinki-NLP/opus-mt-mul-en",
                 reverse_model: str = "Helsinki-NLP/opus-mt-en-mul"):
        self.base_model = base_model
        self.reverse_model = reverse_model
        self.tokenizer = None
        self.model = None
        self.reverse_tokenizer = None
        self.reverse_model_obj = None
        self.translator_pipeline = None
        self.reverse_translator_pipeline = None
        self.training_data = []
        self.db = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"🔧 Using device: {self.device}")
        
    def setup_models(self) -> bool:
        """Initialize Helsinki-NLP OPUS models for translation"""
        try:
            logger.info("🚀 Loading Helsinki-NLP OPUS models...")
            
            # Forward direction: Multilingual to English
            logger.info(f"📥 Loading {self.base_model}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                self.base_model,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            ).to(self.device)
            
            # Create translation pipeline
            self.translator_pipeline = pipeline(
                "translation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1
            )
            
            # Reverse direction: English to Multilingual  
            logger.info(f"📥 Loading {self.reverse_model}...")
            self.reverse_tokenizer = AutoTokenizer.from_pretrained(self.reverse_model)
            if self.reverse_tokenizer.pad_token is None:
                self.reverse_tokenizer.pad_token = self.reverse_tokenizer.eos_token
                
            self.reverse_model_obj = AutoModelForSeq2SeqLM.from_pretrained(
                self.reverse_model,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            ).to(self.device)
            
            self.reverse_translator_pipeline = pipeline(
                "translation",
                model=self.reverse_model_obj,
                tokenizer=self.reverse_tokenizer,
                device=0 if self.device == "cuda" else -1
            )
            
            logger.info("✅ Helsinki-NLP OPUS models loaded successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load Helsinki models: {e}")
            return False
    
    def translate_chuukese_to_english(self, chuukese_text: str) -> str:
        """
        Translate Chuukese text to English using Helsinki-NLP model
        """
        if not self.translator_pipeline:
            logger.error("❌ Translation model not loaded")
            return f"Translation model not available: {chuukese_text}"
            
        try:
            # For multilingual models, we can try different approaches
            # 1. Direct translation (model might recognize Chuukese patterns)
            result = self.translator_pipeline(chuukese_text, max_length=512)
            translation = result[0]['translation_text']
            
            # 2. If direct doesn't work well, we can prefix with language hint
            if len(translation.split()) < 2:  # Very short translation might indicate poor recognition
                # Try with language context hints
                prefixed_text = f"Chuukese: {chuukese_text}"
                result = self.translator_pipeline(prefixed_text, max_length=512)
                alt_translation = result[0]['translation_text']
                if len(alt_translation.split()) > len(translation.split()):
                    translation = alt_translation
            
            logger.info(f"🔄 Chuukese→English: '{chuukese_text}' → '{translation}'")
            return translation
            
        except Exception as e:
            logger.error(f"❌ Translation error: {e}")
            return f"Translation error: {chuukese_text}"
    
    def translate_english_to_chuukese(self, english_text: str) -> str:
        """
        Translate English text to Chuukese using Helsinki-NLP model
        """
        if not self.reverse_translator_pipeline:
            logger.error("❌ Reverse translation model not loaded")
            return f"Translation model not available: {english_text}"
            
        try:
            # For English to multilingual, we need to specify target language
            # Since Chuukese might not be explicitly supported, we'll try related approaches
            
            # Try direct translation
            result = self.reverse_translator_pipeline(english_text, max_length=512)
            translation = result[0]['translation_text']
            
            # TODO: We can enhance this by fine-tuning the model on our Chuukese data
            logger.info(f"🔄 English→Chuukese: '{english_text}' → '{translation}'")
            return translation
            
        except Exception as e:
            logger.error(f"❌ Translation error: {e}")
            return f"Translation error: {english_text}"
    
    def load_dictionary_data(self) -> int:
        """Load Chuukese dictionary data from MongoDB for training"""
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
                
                # Handle case where source might be a string instead of dict
                if isinstance(source_info, str):
                    source_text = source_info
                elif isinstance(source_info, dict):
                    source_text = f"{source_info.get('publication_title', 'dictionary')}:{source_info.get('page_number', 'unknown')}"
                else:
                    source_text = "dictionary:unknown"
                
                if chuukese_word and english_translation:
                    pair = TranslationPair(
                        chuukese=chuukese_word,
                        english=english_translation,
                        source=source_text
                    )
                    self.training_data.append(pair)
            
            logger.info(f"📚 Loaded {len(self.training_data)} translation pairs")
            return len(self.training_data)
            
        except Exception as e:
            logger.error(f"❌ Failed to load dictionary data: {e}")
            return 0
    
    def prepare_training_dataset(self) -> Dict[str, Dataset]:
        """Prepare training datasets for fine-tuning"""
        if not self.training_data:
            logger.error("❌ No training data loaded")
            return {}
            
        # Clean and prepare data
        clean_pairs = []
        for pair in self.training_data:
            chuukese = str(pair.chuukese).strip()
            english = str(pair.english).strip()
            
            # Clean English translations - remove tabs and extra whitespace
            english = english.replace('\t', ' ').replace('  ', ' ').strip()
            
            # Skip empty or very short entries
            if len(chuukese) > 1 and len(english) > 2:
                clean_pairs.append((chuukese, english))
        
        # Prepare data for both directions
        chuukese_to_english = {
            "input_text": [pair[0] for pair in clean_pairs],
            "target_text": [pair[1] for pair in clean_pairs]
        }
        
        english_to_chuukese = {
            "input_text": [pair[1] for pair in clean_pairs],
            "target_text": [pair[0] for pair in clean_pairs]
        }
        
        # Create datasets
        datasets = {
            "chuukese_to_english": Dataset.from_dict(chuukese_to_english),
            "english_to_chuukese": Dataset.from_dict(english_to_chuukese)
        }
        
        logger.info(f"📊 Prepared datasets with {len(clean_pairs)} examples each")
        return datasets
    
    def fine_tune_model(self, 
                       direction: str = "chuukese_to_english",
                       output_dir: str = "models/helsinki-chuukese",
                       num_epochs: int = 3,
                       batch_size: int = 8) -> bool:
        """
        Fine-tune Helsinki-NLP model on Chuukese data
        
        Args:
            direction: "chuukese_to_english" or "english_to_chuukese"
            output_dir: Directory to save fine-tuned model
            num_epochs: Number of training epochs
            batch_size: Training batch size
        """
        if not self.training_data:
            logger.error("❌ No training data available")
            return False
            
        try:
            logger.info(f"🎯 Fine-tuning {direction} translation model...")
            
            # Select model and tokenizer based on direction
            if direction == "chuukese_to_english":
                model = self.model
                tokenizer = self.tokenizer
            else:
                model = self.reverse_model_obj
                tokenizer = self.reverse_tokenizer
                
            if not model or not tokenizer:
                logger.error("❌ Models not loaded")
                return False
            
            # Prepare dataset
            datasets = self.prepare_training_dataset()
            train_dataset = datasets[direction]
            
            # Tokenize the dataset
            def tokenize_function(examples):
                # Get the input and target texts
                inputs = examples["input_text"] 
                targets = examples["target_text"]
                
                # Tokenize inputs
                model_inputs = tokenizer(
                    inputs,
                    max_length=128,
                    truncation=True,
                    padding="max_length",
                    return_tensors=None
                )
                
                # Tokenize targets 
                labels = tokenizer(
                    text_target=targets,
                    max_length=128,
                    truncation=True,
                    padding="max_length",
                    return_tensors=None
                )
                
                # Use the tokenized targets as labels
                model_inputs["labels"] = labels["input_ids"]
                
                return model_inputs
            
            tokenized_dataset = train_dataset.map(tokenize_function, batched=True, batch_size=8)
            
            # Remove unused columns to avoid conflicts
            columns_to_remove = ['input_text', 'target_text']
            tokenized_dataset = tokenized_dataset.remove_columns(columns_to_remove)
            
            # Training arguments - optimized for translation
            training_args = TrainingArguments(
                output_dir=f"{output_dir}_{direction}",
                num_train_epochs=num_epochs,
                per_device_train_batch_size=batch_size,
                gradient_accumulation_steps=4,
                warmup_steps=100,
                weight_decay=0.01,
                logging_dir=f"{output_dir}_{direction}/logs",
                logging_steps=50,
                save_steps=1000,
                save_total_limit=1,
                load_best_model_at_end=False,
                remove_unused_columns=False,
                dataloader_pin_memory=False,
                dataloader_num_workers=0,
                group_by_length=False,
                report_to=None,  # Disable wandb/tensorboard
                push_to_hub=False,
            )
            
            # Data collator for sequence-to-sequence tasks
            data_collator = DataCollatorForSeq2Seq(
                tokenizer=tokenizer,
                model=model,
                padding=True,
                max_length=128,
                pad_to_multiple_of=None,
                label_pad_token_id=tokenizer.pad_token_id,
                return_tensors="pt"
            )
            
            # Trainer
            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
            )
            
            # Train the model
            logger.info("🚀 Starting fine-tuning...")
            trainer.train()
            
            # Save the model
            trainer.save_model()
            tokenizer.save_pretrained(f"{output_dir}_{direction}")
            
            logger.info(f"✅ Fine-tuning completed! Model saved to {output_dir}_{direction}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fine-tuning failed: {e}")
            return False
    
    def load_fine_tuned_model(self, model_path: str, direction: str = "chuukese_to_english") -> bool:
        """Load a previously fine-tuned model"""
        try:
            logger.info(f"📥 Loading fine-tuned model from {model_path}...")
            
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(self.device)
            
            if direction == "chuukese_to_english":
                self.tokenizer = tokenizer
                self.model = model
                self.translator_pipeline = pipeline(
                    "translation",
                    model=model,
                    tokenizer=tokenizer,
                    device=0 if self.device == "cuda" else -1
                )
            else:
                self.reverse_tokenizer = tokenizer
                self.reverse_model_obj = model
                self.reverse_translator_pipeline = pipeline(
                    "translation",
                    model=model,
                    tokenizer=tokenizer,
                    device=0 if self.device == "cuda" else -1
                )
            
            logger.info("✅ Fine-tuned model loaded successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load fine-tuned model: {e}")
            return False
    
    def evaluate_translation_quality(self, test_pairs: List[TranslationPair] = None) -> Dict[str, float]:
        """Evaluate translation quality using BLEU score"""
        if not test_pairs:
            # Use a subset of training data for evaluation
            test_pairs = self.training_data[:50] if len(self.training_data) > 50 else self.training_data
        
        if not test_pairs:
            logger.error("❌ No test data available")
            return {}
        
        try:
            from sacrebleu import BLEU
            bleu = BLEU()
            
            # Evaluate Chuukese to English
            predictions_en = []
            references_en = []
            
            for pair in test_pairs:
                pred = self.translate_chuukese_to_english(pair.chuukese)
                predictions_en.append(pred)
                references_en.append([pair.english])  # BLEU expects list of references
            
            bleu_score_en = bleu.corpus_score(predictions_en, references_en).score
            
            # Evaluate English to Chuukese
            predictions_ch = []
            references_ch = []
            
            for pair in test_pairs:
                pred = self.translate_english_to_chuukese(pair.english)
                predictions_ch.append(pred)
                references_ch.append([pair.chuukese])
            
            bleu_score_ch = bleu.corpus_score(predictions_ch, references_ch).score
            
            results = {
                "chuukese_to_english_bleu": bleu_score_en,
                "english_to_chuukese_bleu": bleu_score_ch,
                "test_samples": len(test_pairs)
            }
            
            logger.info(f"📊 Evaluation Results:")
            logger.info(f"   Chuukese→English BLEU: {bleu_score_en:.2f}")
            logger.info(f"   English→Chuukese BLEU: {bleu_score_ch:.2f}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Evaluation failed: {e}")
            return {}

def main():
    """Test the Helsinki Chuukese Translator"""
    translator = HelsinkiChuukeseTranslator()
    
    if translator.setup_models():
        print("✅ Models loaded successfully!")
        
        # Load dictionary data
        data_count = translator.load_dictionary_data()
        if data_count > 0:
            print(f"📚 Loaded {data_count} translation pairs")
            
            # Test translation
            test_chuukese = "noom"  # Example Chuukese word
            translation = translator.translate_chuukese_to_english(test_chuukese)
            print(f"Translation test: '{test_chuukese}' → '{translation}'")
            
        else:
            print("⚠️ No dictionary data found. Testing with basic translation...")
            test_text = "Hello"
            translation = translator.translate_english_to_chuukese(test_text)
            print(f"Translation test: '{test_text}' → '{translation}'")
    
    else:
        print("❌ Failed to load models")

if __name__ == "__main__":
    main()