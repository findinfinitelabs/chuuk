#!/usr/bin/env python3
"""
Enhanced Helsinki-NLP Retraining Plan for Chuukese Translation
Focuses on validated word entries with grammar-aware training
"""

from src.database.dictionary_db import DictionaryDB
from typing import List, Dict, Tuple
import json
from pathlib import Path

class EnhancedHelsinkiTrainer:
    """Enhanced trainer that uses grammar information and handles multiple meanings"""

    def __init__(self):
        self.db = DictionaryDB()

    def prepare_enhanced_training_data(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Prepare high-quality training data from validated word entries with grammar context

        Returns:
            Tuple of (chk_to_en_pairs, en_to_chk_pairs)
        """
        # Only use validated word entries
        word_entries = list(self.db.dictionary_collection.find({'type': 'word'}))

        chk_to_en_pairs = []
        en_to_chk_pairs = []

        for entry in word_entries:
            chuukese = entry.get('chuukese_word', '').strip()
            english = entry.get('english_translation', '').strip()
            grammar = (entry.get('grammar') or '').strip()

            if not chuukese or not english:
                continue

            # Handle multiple meanings
            english_meanings = [m.strip() for m in english.split(',') if m.strip()]

            for meaning in english_meanings:
                # Create grammar-aware training pairs
                # Format: "[grammar] chuukese_word" -> "english_translation"
                # This helps the model understand grammatical context
                grammar_prefix = f"[{grammar}]" if grammar else ""

                chk_to_en_pair = {
                    'chuukese': f"{grammar_prefix} {chuukese}".strip(),
                    'english': meaning,
                    'grammar': grammar,
                    'source': 'validated_word',
                    'original_chuukese': chuukese,
                    'original_english': english
                }

                # For English to Chuukese, include grammar hint in English
                en_to_chk_pair = {
                    'english': f"{grammar_prefix} {meaning}".strip(),
                    'chuukese': chuukese,
                    'grammar': grammar,
                    'source': 'validated_word',
                    'original_chuukese': chuukese,
                    'original_english': english
                }

                chk_to_en_pairs.append(chk_to_en_pair)
                en_to_chk_pairs.append(en_to_chk_pair)

        return chk_to_en_pairs, en_to_chk_pairs

    def analyze_data_quality(self) -> Dict:
        """Analyze the quality of training data"""
        chk_pairs, en_pairs = self.prepare_enhanced_training_data()

        stats = {
            'total_chk_to_en_pairs': len(chk_pairs),
            'total_en_to_chk_pairs': len(en_pairs),
            'unique_chuukese_words': len(set(p['chuukese'] for p in chk_pairs)),
            'unique_english_words': len(set(p['english'] for p in chk_pairs)),
            'grammar_types': {}
        }

        # Grammar distribution
        for pair in chk_pairs:
            grammar = pair.get('grammar', 'unknown')
            stats['grammar_types'][grammar] = stats['grammar_types'].get(grammar, 0) + 1

        return stats

    def save_training_data(self, output_dir: str = 'training_data'):
        """Save the enhanced training data"""
        Path(output_dir).mkdir(exist_ok=True)

        chk_pairs, en_pairs = self.prepare_enhanced_training_data()

        # Save Chuukese to English
        with open(f'{output_dir}/chuukese_to_english_validated.json', 'w', encoding='utf-8') as f:
            json.dump(chk_pairs, f, ensure_ascii=False, indent=2)

        # Save English to Chuukese
        with open(f'{output_dir}/english_to_chuukese_validated.json', 'w', encoding='utf-8') as f:
            json.dump(en_pairs, f, ensure_ascii=False, indent=2)

        print(f"Saved {len(chk_pairs)} Chuukese→English pairs")
        print(f"Saved {len(en_pairs)} English→Chuukese pairs")

if __name__ == '__main__':
    trainer = EnhancedHelsinkiTrainer()

    print("=== ENHANCED TRAINING DATA ANALYSIS ===")
    stats = trainer.analyze_data_quality()

    print(f"Total training pairs: {stats['total_chk_to_en_pairs']:,} (each direction)")
    print(f"Unique Chuukese words: {stats['unique_chuukese_words']:,}")
    print(f"Unique English words: {stats['unique_english_words']:,}")

    print("\nGrammar type distribution:")
    for grammar, count in sorted(stats['grammar_types'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {grammar}: {count}")

    print("\n=== SAVING ENHANCED TRAINING DATA ===")
    trainer.save_training_data()