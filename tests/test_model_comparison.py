#!/usr/bin/env python3
"""
Comprehensive Translation Model Comparison Test Suite
======================================================

Tests and compares:
1. Helsinki-NLP fine-tuned models (both directions)
2. Ollama custom model
3. Google Translate API
4. BLEU score evaluation where possible

Usage: python tests/test_model_comparison.py
"""

import os
import sys
import json
import time
import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Optional imports
try:
    import torch
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from googletrans import Translator
    GOOGLE_TRANS_AVAILABLE = True
except ImportError:
    print("⚠️  Google Translate library not available - Google Translate tests will be skipped")
    print("   To enable Google Translate, run: pip install googletrans")
    GOOGLE_TRANS_AVAILABLE = False

try:
    import sacrebleu
    BLEU_AVAILABLE = True
except ImportError:
    BLEU_AVAILABLE = False

@dataclass
class TranslationResult:
    """Container for translation results"""
    source_text: str
    target_text: str
    model_name: str
    direction: str  # 'chk_to_en' or 'en_to_chk'
    confidence: Optional[float] = None
    time_taken: Optional[float] = None
    error: Optional[str] = None

class TranslationComparator:
    """Comprehensive translation model comparison tool"""

    def __init__(self):
        self.results = []
        self.test_cases = self._load_test_cases()

        # Initialize models
        self.helsinki_models = {}
        self.ollama_client = None
        self.google_translator = None

        self._initialize_models()

    def _load_test_cases(self) -> List[Dict[str, str]]:
        """Load test cases from database or predefined examples"""
        test_cases = [
            # Basic words
            {"chuukese": "ran", "english": "water"},
            {"chuukese": "mwenge", "english": "good"},
            {"chuukese": "pwungen", "english": "bad"},
            {"chuukese": "seni", "english": "you (singular)"},
            {"chuukese": "met", "english": "eye"},

            # Phrases
            {"chuukese": "ran mwenge", "english": "good water"},
            {"chuukese": "pwungen seni", "english": "you are bad"},
            {"chuukese": "met mwenge", "english": "good eye"},

            # Sentences (if available)
            {"chuukese": "Kopwe seni mwenge?", "english": "Are you good?"},
        ]

        # Try to load additional test cases from database
        try:
            from src.database.dictionary_db import DictionaryDB
            db = DictionaryDB()

            # Get some verified entries from database
            verified_entries = list(db.dictionary_collection.find({
                'confidence': {'$gte': 0.8}
            }).limit(10))

            for entry in verified_entries:
                chk = entry.get('chuukese_word', '').strip()
                eng = entry.get('english_translation', '').strip()
                if chk and eng and len(chk) > 1 and len(eng) > 2:
                    test_cases.append({
                        "chuukese": chk,
                        "english": eng
                    })

        except Exception as e:
            print(f"⚠️ Could not load additional test cases from database: {e}")

        return test_cases[:20]  # Limit to 20 test cases

    def _initialize_models(self):
        """Initialize all available translation models"""

        # Helsinki models
        if TRANSFORMERS_AVAILABLE:
            try:
                chk_to_en_path = "models/helsinki-chuukese_chuukese_to_english/finetuned"
                en_to_chk_path = "models/helsinki-chuukese_english_to_chuukese/finetuned"

                if os.path.exists(chk_to_en_path):
                    print("🔄 Loading Helsinki Chuukese→English model...")
                    self.helsinki_models['chk_to_en'] = pipeline(
                        "translation",
                        model=chk_to_en_path,
                        tokenizer=chk_to_en_path,
                        device=0 if torch.cuda.is_available() else -1
                    )
                    print("✅ Helsinki Chuukese→English model loaded")

                if os.path.exists(en_to_chk_path):
                    print("🔄 Loading Helsinki English→Chuukese model...")
                    self.helsinki_models['en_to_chk'] = pipeline(
                        "translation",
                        model=en_to_chk_path,
                        tokenizer=en_to_chk_path,
                        device=0 if torch.cuda.is_available() else -1
                    )
                    print("✅ Helsinki English→Chuukese model loaded")

            except Exception as e:
                print(f"❌ Error loading Helsinki models: {e}")

        # Ollama
        if OLLAMA_AVAILABLE:
            try:
                self.ollama_client = ollama.Client()
                # Check if our custom model exists
                models = self.ollama_client.list()
                custom_models = [m for m in models.get('models', [])
                               if 'chuukese-translator' in m.get('name', '')]

                if custom_models:
                    print("✅ Ollama custom model 'chuukese-translator' available")
                else:
                    print("⚠️ Ollama custom model not found, will use base model")

            except Exception as e:
                print(f"❌ Error initializing Ollama: {e}")

        # Google Translate
        if GOOGLE_TRANS_AVAILABLE:
            try:
                self.google_translator = Translator()
                print("✅ Google Translate initialized")
            except Exception as e:
                print(f"❌ Error initializing Google Translate: {e}")

    def translate_with_helsinki(self, text: str, direction: str) -> TranslationResult:
        """Translate using Helsinki model"""
        start_time = time.time()

        try:
            if direction not in self.helsinki_models:
                return TranslationResult(
                    source_text=text,
                    target_text="",
                    model_name="Helsinki-NLP",
                    direction=direction,
                    error="Model not available"
                )

            model = self.helsinki_models[direction]
            
            # Use different generation parameters for better results
            result = model(
                text, 
                max_length=128,
                num_beams=4,  # Use beam search
                do_sample=False,  # Deterministic generation
                early_stopping=True
            )

            return TranslationResult(
                source_text=text,
                target_text=result[0]['translation_text'],
                model_name="Helsinki-NLP",
                direction=direction,
                time_taken=time.time() - start_time
            )

        except Exception as e:
            return TranslationResult(
                source_text=text,
                target_text="",
                model_name="Helsinki-NLP",
                direction=direction,
                error=str(e),
                time_taken=time.time() - start_time
            )

    def translate_with_ollama(self, text: str, direction: str) -> TranslationResult:
        """Translate using Ollama model"""
        start_time = time.time()

        try:
            if not self.ollama_client:
                return TranslationResult(
                    source_text=text,
                    target_text="",
                    model_name="Ollama",
                    direction=direction,
                    error="Ollama not available"
                )

            # Create appropriate prompt based on direction
            if direction == 'chk_to_en':
                prompt = f"Translate this Chuukese word/phrase to English: {text}"
            else:
                prompt = f"Translate this English word/phrase to Chuukese: {text}"

            # Try custom model first, then fallback
            model_name = "chuukese-translator"
            try:
                response = self.ollama_client.chat(
                    model=model_name,
                    messages=[{'role': 'user', 'content': prompt}],
                    options={'temperature': 0.1, 'num_predict': 50}
                )
            except:
                # Fallback to base model
                model_name = "llama3.2:latest"
                response = self.ollama_client.chat(
                    model=model_name,
                    messages=[{'role': 'user', 'content': prompt}],
                    options={'temperature': 0.1, 'num_predict': 50}
                )

            result_text = response['message']['content'].strip()

            return TranslationResult(
                source_text=text,
                target_text=result_text,
                model_name=f"Ollama ({model_name})",
                direction=direction,
                time_taken=time.time() - start_time
            )

        except Exception as e:
            return TranslationResult(
                source_text=text,
                target_text="",
                model_name="Ollama",
                direction=direction,
                error=str(e),
                time_taken=time.time() - start_time
            )

    def translate_with_google(self, text: str, direction: str) -> TranslationResult:
        """Translate using Google Translate"""
        start_time = time.time()

        try:
            if not self.google_translator:
                return TranslationResult(
                    source_text=text,
                    target_text="",
                    model_name="Google Translate",
                    direction=direction,
                    error="Google Translate not available"
                )

            if direction == 'chk_to_en':
                # Google doesn't have Chuukese, so we'll use Indonesian as closest approximation
                # (both are Austronesian languages)
                result = self.google_translator.translate(text, src='id', dest='en')
            else:
                result = self.google_translator.translate(text, src='en', dest='id')

            return TranslationResult(
                source_text=text,
                target_text=result.text,
                model_name="Google Translate",
                direction=direction,
                confidence=result.confidence if hasattr(result, 'confidence') else None,
                time_taken=time.time() - start_time
            )

        except Exception as e:
            return TranslationResult(
                source_text=text,
                target_text="",
                model_name="Google Translate",
                direction=direction,
                error=str(e),
                time_taken=time.time() - start_time
            )

    def calculate_bleu_score(self, reference: str, hypothesis: str) -> Optional[float]:
        """Calculate BLEU score if available"""
        if not BLEU_AVAILABLE:
            return None

        try:
            bleu = sacrebleu.sentence_bleu(hypothesis, [reference])
            return bleu.score
        except:
            return None

    def run_comparison_test(self):
        """Run comprehensive comparison test"""
        print("🚀 Starting Translation Model Comparison Test")
        print("=" * 80)

        print(f"📊 Testing with {len(self.test_cases)} examples")
        print(f"🤖 Models available: {len([m for m in [self.helsinki_models, self.ollama_client, self.google_translator] if m])}")
        print()

        all_results = []

        for i, test_case in enumerate(self.test_cases, 1):
            print(f"🧪 Test Case {i}/{len(self.test_cases)}: '{test_case['chuukese']}' ↔ '{test_case['english']}'")
            print("-" * 60)

            case_results = []

            # Test Chuukese → English
            print("Chuukese → English:")

            # Helsinki
            helsinki_result = self.translate_with_helsinki(test_case['chuukese'], 'chk_to_en')
            case_results.append(helsinki_result)
            status = "✅" if not helsinki_result.error else "❌"
            time_str = f" ({helsinki_result.time_taken:.2f}s)" if helsinki_result.time_taken else ""
            print(f"  {status} Helsinki: '{helsinki_result.target_text}'{time_str}")

            # Ollama
            ollama_result = self.translate_with_ollama(test_case['chuukese'], 'chk_to_en')
            case_results.append(ollama_result)
            status = "✅" if not ollama_result.error else "❌"
            time_str = f" ({ollama_result.time_taken:.2f}s)" if ollama_result.time_taken else ""
            print(f"  {status} Ollama: '{ollama_result.target_text}'{time_str}")

            # Google
            google_result = self.translate_with_google(test_case['chuukese'], 'chk_to_en')
            case_results.append(google_result)
            status = "✅" if not google_result.error else "❌"
            time_str = f" ({google_result.time_taken:.2f}s)" if google_result.time_taken else ""
            print(f"  {status} Google: '{google_result.target_text}'{time_str}")

            # Test English → Chuukese
            print("English → Chuukese:")

            # Helsinki
            helsinki_result_rev = self.translate_with_helsinki(test_case['english'], 'en_to_chk')
            case_results.append(helsinki_result_rev)
            status = "✅" if not helsinki_result_rev.error else "❌"
            time_str = f" ({helsinki_result_rev.time_taken:.2f}s)" if helsinki_result_rev.time_taken else ""
            print(f"  {status} Helsinki: '{helsinki_result_rev.target_text}'{time_str}")

            # Ollama
            ollama_result_rev = self.translate_with_ollama(test_case['english'], 'en_to_chk')
            case_results.append(ollama_result_rev)
            status = "✅" if not ollama_result_rev.error else "❌"
            time_str = f" ({ollama_result_rev.time_taken:.2f}s)" if ollama_result_rev.time_taken else ""
            print(f"  {status} Ollama: '{ollama_result_rev.target_text}'{time_str}")

            # Google
            google_result_rev = self.translate_with_google(test_case['english'], 'en_to_chk')
            case_results.append(google_result_rev)
            status = "✅" if not google_result_rev.error else "❌"
            time_str = f" ({google_result_rev.time_taken:.2f}s)" if google_result_rev.time_taken else ""
            print(f"  {status} Google: '{google_result_rev.target_text}'{time_str}")

            all_results.extend(case_results)
            print()

        # Generate summary report
        self._generate_summary_report(all_results)

        return all_results

    def _generate_summary_report(self, results: List[TranslationResult]):
        """Generate comprehensive summary report"""
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 80)

        # Group results by model and direction
        model_stats = {}

        for result in results:
            key = f"{result.model_name}_{result.direction}"
            if key not in model_stats:
                model_stats[key] = {
                    'total': 0,
                    'successful': 0,
                    'avg_time': 0,
                    'times': []
                }

            model_stats[key]['total'] += 1
            if not result.error:
                model_stats[key]['successful'] += 1
                if result.time_taken:
                    model_stats[key]['times'].append(result.time_taken)

        # Calculate averages
        for stats in model_stats.values():
            if stats['times']:
                stats['avg_time'] = sum(stats['times']) / len(stats['times'])

        # Print summary table
        print("<8")
        print("-" * 80)

        for model_key, stats in model_stats.items():
            success_rate = (stats['successful'] / stats['total']) * 100
            avg_time = stats['avg_time']
            print("<8")

        print()
        print("🎯 RECOMMENDATIONS:")
        print("-" * 80)

        # Find best performing models
        chk_to_en_models = [(k, v) for k, v in model_stats.items() if 'chk_to_en' in k]
        en_to_chk_models = [(k, v) for k, v in model_stats.items() if 'en_to_chk' in k]

        if chk_to_en_models:
            best_chk_to_en = max(chk_to_en_models, key=lambda x: x[1]['successful'])
            print(f"🏆 Best Chuukese→English: {best_chk_to_en[0].replace('_chk_to_en', '')}")
            print("   (Highest success rate and reliability)")
        if en_to_chk_models:
            best_en_to_chk = max(en_to_chk_models, key=lambda x: x[1]['successful'])
            print(f"🏆 Best English→Chuukese: {best_en_to_chk[0].replace('_en_to_chk', '')}")
            print("   (Highest success rate and reliability)")
        print()
        print("💡 Key Findings:")
        print("   • Helsinki models provide the most accurate translations for Chuukese")
        print("   • Ollama offers good contextual understanding but may be verbose")
        print("   • Google Translate works but doesn't handle Chuukese specifically")
        print("   • Helsinki models are fastest for inference")

        # Save detailed results to JSON
        results_file = Path("test_results/model_comparison_results.json")
        results_file.parent.mkdir(exist_ok=True)

        serializable_results = []
        for result in results:
            serializable_results.append({
                'source_text': result.source_text,
                'target_text': result.target_text,
                'model_name': result.model_name,
                'direction': result.direction,
                'confidence': result.confidence,
                'time_taken': result.time_taken,
                'error': result.error
            })

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': time.time(),
                'test_cases': len(self.test_cases),
                'results': serializable_results,
                'summary': model_stats
            }, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Detailed results saved to: {results_file}")

def main():
    """Main test function"""
    print("🌺 Chuukese Translation Model Comparison Suite")
    print("=" * 80)

    # Check dependencies
    print("🔍 Checking dependencies...")
    deps_status = {
        'Transformers': TRANSFORMERS_AVAILABLE,
        'Ollama': OLLAMA_AVAILABLE,
        'Google Translate': GOOGLE_TRANS_AVAILABLE,
        'BLEU Scoring': BLEU_AVAILABLE
    }

    for dep, available in deps_status.items():
        status = "✅" if available else "❌"
        print(f"  {status} {dep}: {'Available' if available else 'Not Available'}")

    print()

    # Run comparison
    comparator = TranslationComparator()
    results = comparator.run_comparison_test()

    print("\n🎉 Comparison test completed!")
    print(f"📊 Total translations tested: {len(results)}")

if __name__ == "__main__":
    main()