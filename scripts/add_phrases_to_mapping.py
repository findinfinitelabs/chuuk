#!/usr/bin/env python3
"""Add missing phrase grammar types to mapping."""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.dictionary_db import DictionaryDB

# Load existing mapping
MAPPING_FILE = str(Path(__file__).resolve().parent.parent / 'data' / 'grammar' / 'grammar_mapping.json')
with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
    mapping_data = json.load(f)
    existing_mapping = mapping_data['mapping']

# New mappings for phrases_collection grammar types
new_mappings = {
    # Phrase types
    'phrase': {'core': 'phrase', 'modifier': None},
    'example phrase': {'core': 'phrase', 'modifier': 'example'},
    'fractional phrase': {'core': 'phrase', 'modifier': 'fractional'},
    'idiomatic phrase': {'core': 'phrase', 'modifier': 'idiomatic'},
    'noun phrase': {'core': 'phrase', 'modifier': 'noun'},
    'verb phrase': {'core': 'phrase', 'modifier': 'verb'},
    'adverb phrase': {'core': 'phrase', 'modifier': 'adverb'},
    'verbal phrase': {'core': 'phrase', 'modifier': 'verbal'},
    'preposition phrase': {'core': 'phrase', 'modifier': 'preposition'},
    'numeral phrase': {'core': 'phrase', 'modifier': 'numeral'},
    'comparison phrase': {'core': 'phrase', 'modifier': 'comparison'},
    'adj. phrase': {'core': 'phrase', 'modifier': 'adjective'},
    'number phrase': {'core': 'phrase', 'modifier': 'number'},
    'verb phrase / noun phrase': {'core': 'phrase', 'modifier': 'verb or noun'},
    
    # Expression types
    'expression': {'core': 'expression', 'modifier': None},
    'comparative expression': {'core': 'expression', 'modifier': 'comparative'},
    'polite expression': {'core': 'expression', 'modifier': 'polite'},
    'polite expression + pronoun': {'core': 'expression', 'modifier': 'polite + pronoun'},
    'pronoun suffix expression': {'core': 'expression', 'modifier': 'pronoun suffix'},
    'adv./expression': {'core': 'expression', 'modifier': 'adverb'},
    
    # Sentence types
    'sentence': {'core': 'sentence', 'modifier': None},
    'example': {'core': 'sentence', 'modifier': 'example'},
    
    # Greeting/exclamation
    'greeting': {'core': 'interjection', 'modifier': 'greeting'},
    'exclamation': {'core': 'interjection', 'modifier': 'exclamation'},
    
    # Directionals
    'directionals': {'core': 'particle', 'modifier': 'directional'},
    
    # Verb forms with abbreviations
    'vt. + pronoun suffix': {'core': 'verb', 'modifier': 'transitive + pronoun suffix'},
    'vt. + suffix': {'core': 'verb', 'modifier': 'transitive + suffix'},
    'vt. + directional': {'core': 'verb', 'modifier': 'transitive + directional'},
    'vt. + suffix + directional': {'core': 'verb', 'modifier': 'transitive + suffix + directional'},
    'vt. + pronoun + directional': {'core': 'verb', 'modifier': 'transitive + pronoun + directional'},
    'vt. + prep.': {'core': 'verb', 'modifier': 'transitive + preposition'},
    'verb (causative)': {'core': 'verb', 'modifier': 'causative'},
    'verb (object pronoun)': {'core': 'verb', 'modifier': 'object pronoun'},
    'verb (object suffix)': {'core': 'verb', 'modifier': 'object suffix'},
    'verb + preposition': {'core': 'verb', 'modifier': 'preposition'},
    'verb + pronoun ending': {'core': 'verb', 'modifier': 'pronoun ending'},
    'verb + directional suffix': {'core': 'verb', 'modifier': 'directional suffix'},
    'verb + possessive suffix': {'core': 'verb', 'modifier': 'possessive suffix'},
    'verb phrase + pronoun': {'core': 'verb', 'modifier': 'phrase + pronoun'},
    'reciprocal verb + pronoun': {'core': 'verb', 'modifier': 'reciprocal + pronoun'},
    'reduplicated reciprocal verb': {'core': 'verb', 'modifier': 'reduplicated + reciprocal'},
    'reduplicated reciprocal verb + pronoun': {'core': 'verb', 'modifier': 'reduplicated + reciprocal + pronoun'},
    
    # Noun forms
    'noun possessive': {'core': 'noun', 'modifier': 'possessive'},
    'noun + poss. suffix': {'core': 'noun', 'modifier': 'possessive suffix'},
    'noun + directional': {'core': 'noun', 'modifier': 'directional'},
    
    # Adjective forms
    'possessed adjective': {'core': 'adjective', 'modifier': 'possessed'},
    'adj. + pronoun suffix': {'core': 'adjective', 'modifier': 'pronoun suffix'},
    'adj. + prep.': {'core': 'adjective', 'modifier': 'preposition'},
    
    # Adverb forms
    'adv. phrase + pronoun suffix': {'core': 'adverb', 'modifier': 'phrase + pronoun suffix'},
    'adv. + pronoun suffix': {'core': 'adverb', 'modifier': 'pronoun suffix'},
    
    # Preposition forms
    'preposition + pronoun': {'core': 'preposition', 'modifier': 'pronoun'},
    'prep. + pronoun suffix': {'core': 'preposition', 'modifier': 'pronoun suffix'},
    
    # Classifier forms
    'relational classifier': {'core': 'classifier', 'modifier': 'relational'},
    'ordinal classifier': {'core': 'classifier', 'modifier': 'ordinal'},
    
    # Possessive structures
    'possessive structure': {'core': 'possessive', 'modifier': 'structure'},
}

# Merge with existing
for key, value in new_mappings.items():
    if key not in existing_mapping:
        existing_mapping[key] = value
        print(f"Added: {key} → {value['core']}, {value['modifier']}")
    else:
        print(f"Skipped (exists): {key}")

# Save updated mapping
mapping_data['mapping'] = existing_mapping
with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
    json.dump(mapping_data, f, indent=2, ensure_ascii=False)

print(f"\nTotal mappings: {len(existing_mapping)}")
print(f"Mapping file updated: {MAPPING_FILE}")
