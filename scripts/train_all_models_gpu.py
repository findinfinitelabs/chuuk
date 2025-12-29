#!/usr/bin/env python3
"""
Complete Model Training Script with GPU Support
Trains both Helsinki-NLP and Ollama models using all database data
Designed to run overnight with comprehensive logging
"""

import os
import sys
import torch
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.dictionary_db import DictionaryDB
from src.training.helsinki_trainer import HelsinkiFineTuner
from src.translation.llm_trainer import ChuukeseLLMTrainer


class ComprehensiveModelTrainer:
    """Coordinates training of all AI models with GPU support"""
    
    def __init__(self, use_gpu=True):
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.db = DictionaryDB()
        self.log_file = Path("logs/training_overnight.log")
        self.log_file.parent.mkdir(exist_ok=True)
        
        self.log("="*80)
        self.log("🚀 COMPREHENSIVE MODEL TRAINING STARTED")
        self.log(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("="*80)
        
        self._detect_hardware()
    
    def _detect_hardware(self):
        """Detect and configure hardware"""
        if self.use_gpu:
            gpu_count = torch.cuda.device_count()
            if gpu_count > 0:
                gpu_name = torch.cuda.get_device_name(0)
                total_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
                self.log(f"🎮 GPU DETECTED: {gpu_name}")
                self.log(f"💾 GPU Memory: {total_memory:.1f} GB")
                self.log(f"🔢 GPU Count: {gpu_count}")
                
                # Configure for GPU training
                os.environ['CUDA_VISIBLE_DEVICES'] = ','.join(str(i) for i in range(gpu_count))
                
                # Set memory growth to prevent OOM
                for i in range(gpu_count):
                    torch.cuda.set_per_process_memory_fraction(0.9, i)
                
                self.log(f"✅ Configured to use all {gpu_count} GPU(s)")
            else:
                self.log("⚠️  No GPU detected, falling back to CPU")
                self.use_gpu = False
        else:
            self.log("🖥️  CPU mode selected")
            torch.set_num_threads(os.cpu_count() or 4)
    
    def log(self, message: str):
        """Log to both console and file"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + '\n')
    
    def gather_training_data(self):
        """Gather all training data from database"""
        self.log("\n📊 PHASE 1: GATHERING TRAINING DATA")
        self.log("-" * 80)
        
        # Get all entries from all collections
        training_data = {
            'words': [],
            'phrases': [],
            'sentences': [],
            'translation_game': []
        }
        
        # Words from dictionary_collection
        self.log("📖 Loading words from dictionary...")
        words = list(self.db.dictionary_collection.find({
            'search_direction': {'$ne': 'en_to_chk'}
        }))
        for word in words:
            chk = word.get('chuukese_word', '').strip()
            eng = word.get('english_translation', '').strip()
            if chk and eng and len(chk) > 1 and len(eng) > 2:
                training_data['words'].append({
                    'chuukese': chk,
                    'english': eng,
                    'type': 'word',
                    'grammar': word.get('grammar', ''),
                    'definition': word.get('definition', '')
                })
        
        # Phrases from phrases_collection
        self.log("💬 Loading phrases and sentences...")
        phrases = list(self.db.phrases_collection.find({}))
        for phrase in phrases:
            chk = (phrase.get('chuukese_sentence') or 
                   phrase.get('chuukese_phrase') or 
                   phrase.get('chuukese', '')).strip()
            eng = phrase.get('english_translation', '').strip()
            
            if chk and eng and len(chk) > 2 and len(eng) > 3:
                entry_type = phrase.get('type', 'phrase')
                source_type = phrase.get('source_type', '')
                
                if source_type == 'translation_game':
                    training_data['translation_game'].append({
                        'chuukese': chk,
                        'english': eng,
                        'type': entry_type,
                        'confidence': phrase.get('confidence', 1.0)
                    })
                elif entry_type == 'sentence':
                    training_data['sentences'].append({
                        'chuukese': chk,
                        'english': eng,
                        'type': 'sentence'
                    })
                else:
                    training_data['phrases'].append({
                        'chuukese': chk,
                        'english': eng,
                        'type': 'phrase'
                    })
        
        # Log statistics
        self.log("\n📈 TRAINING DATA STATISTICS:")
        self.log(f"   Words:              {len(training_data['words']):,}")
        self.log(f"   Phrases:            {len(training_data['phrases']):,}")
        self.log(f"   Sentences:          {len(training_data['sentences']):,}")
        self.log(f"   Translation Game:   {len(training_data['translation_game']):,}")
        
        total = sum(len(v) for v in training_data.values())
        self.log(f"   TOTAL:              {total:,} training pairs")
        
        # Save training data snapshot
        snapshot_path = Path("training_data/snapshot_overnight.json")
        snapshot_path.parent.mkdir(exist_ok=True)
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        self.log(f"💾 Saved training snapshot to: {snapshot_path}")
        
        return training_data
    
    def train_helsinki_models(self, training_data):
        """Train Helsinki-NLP models with GPU support"""
        self.log("\n🤖 PHASE 2: TRAINING HELSINKI-NLP MODELS")
        self.log("-" * 80)
        
        # Flatten all data into training pairs
        all_pairs = []
        for category in training_data.values():
            all_pairs.extend(category)
        
        self.log(f"📚 Total training pairs: {len(all_pairs):,}")
        
        def progress_callback(stage: str, progress: float):
            self.log(f"   {stage}: {progress:.1f}%")
        
        try:
            trainer = HelsinkiFineTuner(progress_callback=progress_callback)
            
            # Train Chuukese → English
            self.log("\n🔄 Training Chuukese → English model...")
            chk_to_en_success = trainer.fine_tune_model(
                training_pairs=all_pairs,
                direction='chk_to_en',
                epochs=3,  # More epochs for overnight training
                batch_size=8 if self.use_gpu else 2,
                learning_rate=5e-5
            )
            
            if chk_to_en_success:
                self.log("✅ Chuukese → English model trained successfully")
            else:
                self.log("❌ Chuukese → English training failed")
            
            # Train English → Chuukese
            self.log("\n🔄 Training English → Chuukese model...")
            en_to_chk_success = trainer.fine_tune_model(
                training_pairs=all_pairs,
                direction='en_to_chk',
                epochs=5,  # More epochs for better learning
                batch_size=16 if self.use_gpu else 2,  # Larger batches on GPU
                learning_rate=3e-5  # Slightly lower for stability
            )
            
            if en_to_chk_success:
                self.log("✅ English → Chuukese model trained successfully")
            else:
                self.log("❌ English → Chuukese training failed")
            
            return chk_to_en_success and en_to_chk_success
            
        except Exception as e:
            self.log(f"❌ Helsinki training error: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return False
    
    def train_ollama_model(self, training_data):
        """Train Ollama model"""
        self.log("\n🦙 PHASE 3: TRAINING OLLAMA MODEL")
        self.log("-" * 80)
        
        try:
            trainer = ChuukeseLLMTrainer()
            
            # Check if Ollama is running
            if not trainer.check_ollama_installation():
                self.log("❌ Ollama is not running. Please start Ollama and try again.")
                return False
            
            # Flatten all data
            all_examples = []
            for category_data in training_data.values():
                all_examples.extend(category_data)
            
            self.log(f"📚 Preparing {len(all_examples):,} training examples...")
            
            # Create comprehensive training data
            ollama_training = []
            for item in all_examples:
                # Various prompts for better training
                prompts = [
                    {
                        "input": f"Translate to English: {item['chuukese']}",
                        "output": item['english']
                    },
                    {
                        "input": f"What does '{item['chuukese']}' mean in English?",
                        "output": item['english']
                    },
                    {
                        "input": f"Translate to Chuukese: {item['english']}",
                        "output": item['chuukese']
                    }
                ]
                
                # Add type-specific prompts
                if item.get('type') == 'word' and item.get('grammar'):
                    prompts.append({
                        "input": f"What type of word is '{item['chuukese']}'?",
                        "output": f"'{item['chuukese']}' is a {item['grammar']} meaning {item['english']}"
                    })
                
                ollama_training.extend(prompts)
            
            self.log(f"✅ Created {len(ollama_training):,} training prompts")
            
            # Train the model
            self.log("🔄 Creating custom Ollama model...")
            success = trainer.create_custom_model(ollama_training)
            
            if success:
                self.log("✅ Ollama model trained successfully")
                
                # Test the model
                self.log("\n🧪 Testing Ollama model...")
                test_result = trainer.translate_text("seni", "chk_to_en")
                self.log(f"   Test translation: seni → {test_result}")
                
                return True
            else:
                self.log("❌ Ollama training failed")
                return False
                
        except Exception as e:
            self.log(f"❌ Ollama training error: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return False
    
    def run_complete_training(self):
        """Run complete training pipeline"""
        start_time = datetime.now()
        
        try:
            # Phase 1: Gather data
            training_data = self.gather_training_data()
            
            # Phase 2: Train Helsinki models
            helsinki_success = self.train_helsinki_models(training_data)
            
            # Phase 3: Train Ollama model
            ollama_success = self.train_ollama_model(training_data)
            
            # Summary
            end_time = datetime.now()
            duration = end_time - start_time
            
            self.log("\n" + "="*80)
            self.log("📊 TRAINING SUMMARY")
            self.log("="*80)
            self.log(f"⏱️  Total Duration: {duration}")
            self.log(f"🤖 Helsinki-NLP: {'✅ SUCCESS' if helsinki_success else '❌ FAILED'}")
            self.log(f"🦙 Ollama:       {'✅ SUCCESS' if ollama_success else '❌ FAILED'}")
            
            if helsinki_success and ollama_success:
                self.log("\n🎉 ALL MODELS TRAINED SUCCESSFULLY!")
                return True
            else:
                self.log("\n⚠️  Some models failed to train. Check logs above.")
                return False
                
        except Exception as e:
            self.log(f"\n❌ FATAL ERROR: {str(e)}")
            import traceback
            self.log(traceback.format_exc())
            return False
        finally:
            self.log(f"\n📅 End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.log("="*80)


def main():
    """Main training script"""
    print("🚀 Starting overnight model training...")
    print("📝 Logs will be saved to: logs/training_overnight.log")
    print("⏰ This will take several hours. You can monitor progress in the log file.")
    print()
    
    trainer = ComprehensiveModelTrainer(use_gpu=True)
    success = trainer.run_complete_training()
    
    if success:
        print("\n✅ Training completed successfully!")
        print("🎯 Models are ready to use")
    else:
        print("\n❌ Training encountered errors")
        print("📋 Check logs/training_overnight.log for details")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
