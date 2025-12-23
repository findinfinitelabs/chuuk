#!/usr/bin/env python3
"""
Helsinki-NLP Model Fine-tuning System for Chuukese
Implements real fine-tuning of OPUS-MT models with dictionary corrections
"""

import os
import torch
from transformers import (
    MarianMTModel, 
    MarianTokenizer,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq
)
from datasets import Dataset
from typing import List, Dict, Optional, Callable
import json
from pathlib import Path


class HelsinkiFineTuner:
    """Fine-tunes Helsinki-NLP OPUS models with new dictionary data"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        """
        Args:
            progress_callback: Optional function to call with progress updates
                              Should accept (stage: str, progress: float) parameters
        """
        self.progress_callback = progress_callback
        
        # Limit GPU usage to prevent system crashes
        if torch.cuda.is_available():
            # Use only 1 GPU
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'
            # Set memory fraction to 80% to leave room for system
            torch.cuda.set_per_process_memory_fraction(0.8, 0)
            self.device = "cuda"
            print(f"🎮 Using GPU with 80% memory limit")
        else:
            self.device = "cpu"
            # Limit CPU threads to prevent overload
            torch.set_num_threads(4)
            print(f"🖥️  Using CPU with 4 threads")
        
        print(f"🖥️  Using device: {self.device}")
        if self.device == "cpu":
            print("⚠️  Warning: Training on CPU will be slow. GPU recommended for production.")
        
        # Model paths
        self.chk_to_en_model_path = "models/helsinki-chuukese_chuukese_to_english"
        self.en_to_chk_model_path = "models/helsinki-chuukese_english_to_chuukese"
        
        # Base model names (for fallback if local models don't exist)
        self.chk_to_en_base = "Helsinki-NLP/opus-mt-mul-en"
        self.en_to_chk_base = "Helsinki-NLP/opus-mt-en-mul"
        
        # Safety limits
        self.max_length = 128  # Limit sequence length to save memory
        self.gradient_accumulation_steps = 2  # Accumulate gradients to simulate larger batches
        
        print(f"🖥️  Using device: {self.device}")
        if self.device == "cpu":
            print("⚠️  Warning: Training on CPU will be slow. GPU recommended for production.")
    
    def _update_progress(self, stage: str, progress: float):
        """Update progress through callback if provided"""
        if self.progress_callback:
            self.progress_callback(stage, progress)
    
    def load_training_data_from_db(self) -> List[Dict[str, str]]:
        """Load training data from dictionary database"""
        from src.database.dictionary_db import DictionaryDB
        
        self._update_progress("Loading dictionary data", 5)
        
        db = DictionaryDB()
        entries = list(db.dictionary_collection.find({
            'search_direction': {'$ne': 'en_to_chk'}  # Get original entries
        }))
        
        training_pairs = []
        for entry in entries:
            chuukese = entry.get('chuukese_word', '').strip()
            english = entry.get('english_translation', '').strip()
            
            if chuukese and english and len(chuukese) > 1 and len(english) > 2:
                training_pairs.append({
                    'chuukese': chuukese,
                    'english': english
                })
        
        print(f"📚 Loaded {len(training_pairs)} training pairs from database")
        self._update_progress("Data loaded", 10)
        return training_pairs
    
    def prepare_dataset(self, training_pairs: List[Dict[str, str]], direction: str) -> Dataset:
        """
        Prepare dataset for training
        
        Args:
            training_pairs: List of {'chuukese': str, 'english': str} dicts
            direction: 'chk_to_en' or 'en_to_chk'
        """
        if direction == 'chk_to_en':
            data = {
                'source': [pair['chuukese'] for pair in training_pairs],
                'target': [pair['english'] for pair in training_pairs]
            }
        else:  # en_to_chk
            data = {
                'source': [pair['english'] for pair in training_pairs],
                'target': [pair['chuukese'] for pair in training_pairs]
            }
        
        return Dataset.from_dict(data)
    
    def tokenize_dataset(self, dataset: Dataset, tokenizer, max_length: int = 128):
        """Tokenize dataset for training"""
        
        def tokenize_function(examples):
            model_inputs = tokenizer(
                examples['source'],
                max_length=max_length,
                truncation=True,
                padding='max_length'
            )
            
            # Setup the tokenizer for targets
            with tokenizer.as_target_tokenizer():
                labels = tokenizer(
                    examples['target'],
                    max_length=max_length,
                    truncation=True,
                    padding='max_length'
                )
            
            model_inputs['labels'] = labels['input_ids']
            return model_inputs
        
        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names
        )
        
        return tokenized_dataset
    
    def fine_tune_model(
        self, 
        direction: str,
        num_epochs: int = 3,
        batch_size: int = 2,  # Reduced default for safety
        learning_rate: float = 3e-5,
        save_steps: int = 50
    ) -> bool:
        """
        Fine-tune a Helsinki model
        
        Args:
            direction: 'chk_to_en' or 'en_to_chk'
            num_epochs: Number of training epochs
            batch_size: Training batch size (keep small: 2-4)
            learning_rate: Learning rate for optimizer
            save_steps: Save checkpoint every N steps
        """
        try:
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()
            
            # Determine model paths
            if direction == 'chk_to_en':
                model_path = self.chk_to_en_model_path
                base_model = self.chk_to_en_base
                output_dir = f"{model_path}/finetuned"
                stage_name = "Chuukese→English"
            else:
                model_path = self.en_to_chk_model_path
                base_model = self.en_to_chk_base
                output_dir = f"{model_path}/finetuned"
                stage_name = "English→Chuukese"
            
            print(f"\n🔧 Fine-tuning {stage_name} model...")
            self._update_progress(f"Loading {stage_name} model", 15)
            
            # Load model and tokenizer
            if os.path.exists(model_path):
                print(f"📂 Loading local model from {model_path}")
                model = MarianMTModel.from_pretrained(model_path)
                tokenizer = MarianTokenizer.from_pretrained(model_path)
            else:
                print(f"📥 Downloading base model: {base_model}")
                model = MarianMTModel.from_pretrained(base_model)
                tokenizer = MarianTokenizer.from_pretrained(base_model)
            
            model = model.to(self.device)
            
            # Load training data
            self._update_progress(f"Preparing {stage_name} data", 20)
            training_pairs = self.load_training_data_from_db()
            
            if len(training_pairs) < 10:
                print(f"⚠️  Warning: Only {len(training_pairs)} training pairs. More data recommended.")
            
            # Prepare dataset
            dataset = self.prepare_dataset(training_pairs, direction)
            tokenized_dataset = self.tokenize_dataset(dataset, tokenizer)
            
            # Split into train/eval (90/10)
            split = tokenized_dataset.train_test_split(test_size=0.1, seed=42)
            train_dataset = split['train']
            eval_dataset = split['test']
            
            print(f"📊 Training samples: {len(train_dataset)}, Eval samples: {len(eval_dataset)}")
            
            # Training arguments
            training_args = Seq2SeqTrainingArguments(
                output_dir=output_dir,
                eval_strategy="steps",
                eval_steps=save_steps,
                save_strategy="steps",
                save_steps=save_steps,
                learning_rate=learning_rate,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                gradient_accumulation_steps=self.gradient_accumulation_steps,
                num_train_epochs=num_epochs,
                weight_decay=0.01,
                save_total_limit=2,  # Keep only 2 checkpoints
                predict_with_generate=True,
                fp16=self.device == "cuda",  # Use mixed precision on GPU
                fp16_full_eval=False,  # Don't use fp16 for eval to save memory
                logging_steps=10,
                load_best_model_at_end=True,
                metric_for_best_model="eval_loss",
                greater_is_better=False,
                push_to_hub=False,
                dataloader_num_workers=0,  # Single-threaded data loading for stability
                max_grad_norm=1.0,  # Gradient clipping for stability
            )
            
            # Data collator
            data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)
            
            # Trainer
            self._update_progress(f"Training {stage_name} model", 30)
            
            trainer = Seq2SeqTrainer(
                model=model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                data_collator=data_collator,
                tokenizer=tokenizer,
            )
            
            # Train!
            print(f"🚀 Starting training for {num_epochs} epochs...")
            train_result = trainer.train()
            
            # Save the fine-tuned model
            self._update_progress(f"Saving {stage_name} model", 90)
            print(f"💾 Saving fine-tuned model to {output_dir}")
            trainer.save_model(output_dir)
            tokenizer.save_pretrained(output_dir)
            
            # Save training metrics
            metrics_path = f"{output_dir}/training_metrics.json"
            with open(metrics_path, 'w') as f:
                json.dump(train_result.metrics, f, indent=2)
            
            print(f"✅ {stage_name} fine-tuning complete!")
            print(f"   Final loss: {train_result.metrics.get('train_loss', 'N/A')}")
            
            # Clear memory after training
            if self.device == "cuda":
                del model
                del trainer
                torch.cuda.empty_cache()
            
            return True
            
        except Exception as e:
            print(f"❌ Fine-tuning error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def fine_tune_both_models(
        self,
        num_epochs: int = 3,
        batch_size: int = 4
    ) -> bool:
        """Fine-tune both translation models"""
        
        print("🚀 Starting fine-tuning for both Helsinki models")
        print("=" * 60)
        
        # Fine-tune Chuukese → English
        self._update_progress("Fine-tuning Chuukese→English", 25)
        chk_to_en_success = self.fine_tune_model(
            direction='chk_to_en',
            num_epochs=num_epochs,
            batch_size=batch_size
        )
        
        if not chk_to_en_success:
            print("❌ Chuukese→English fine-tuning failed")
            return False
        
        # Fine-tune English → Chuukese
        self._update_progress("Fine-tuning English→Chuukese", 60)
        en_to_chk_success = self.fine_tune_model(
            direction='en_to_chk',
            num_epochs=num_epochs,
            batch_size=batch_size
        )
        
        if not en_to_chk_success:
            print("❌ English→Chuukese fine-tuning failed")
            return False
        
        self._update_progress("Fine-tuning complete", 95)
        print("\n" + "=" * 60)
        print("🎉 Both models fine-tuned successfully!")
        return True


if __name__ == "__main__":
    # Test the trainer
    def progress_callback(stage, progress):
        print(f"[{progress}%] {stage}")
    
    trainer = HelsinkiFineTuner(progress_callback=progress_callback)
    
    # Quick test with small configuration
    success = trainer.fine_tune_both_models(
        num_epochs=1,  # Quick test
        batch_size=2   # Small batch for testing
    )
    
    if success:
        print("✅ Training test successful!")
    else:
        print("❌ Training test failed")
