#!/usr/bin/env python3
"""
Analyze all grammar types and extract core grammar types vs modifiers.
"""

from pathlib import Path
import json
import re
from collections import defaultdict

# Load the full grammar types analysis
with open(Path(__file__).resolve().parent / 'grammar_types_analysis.json', 'r') as f:
    data = json.load(f)

# Extract core grammar types and modifiers
core_types = set()
modifiers = set()
examples = defaultdict(list)

def extract_core_and_modifier(grammar_str):
    """Extract core grammar type and modifier from a grammar string."""
    if not grammar_str:
        return None, None
    
    # Pattern 1: "type (modifier)" - e.g., "verb (reduplicated)"
    match = re.match(r'^([^(]+)\s*\(([^)]+)\)$', grammar_str)
    if match:
        core = match.group(1).strip()
        modifier = match.group(2).strip()
        return core, modifier
    
    # Pattern 2: "type + modifier" - e.g., "noun + possessive"
    match = re.match(r'^([^+]+)\s*\+\s*(.+)$', grammar_str)
    if match:
        core = match.group(1).strip()
        modifier = match.group(2).strip()
        return core, modifier
    
    # Pattern 3: "type/other" - e.g., "verb/adjective" - take first as core
    match = re.match(r'^([^/]+)/(.+)$', grammar_str)
    if match:
        core = match.group(1).strip()
        modifier = f"or {match.group(2).strip()}"
        return core, modifier
    
    # Pattern 4: space-separated with common modifiers at the end
    common_modifiers = ['phrase', 'root', 'classifier', 'participle', 'suffix', 'prefix']
    words = grammar_str.split()
    if len(words) > 1 and words[-1] in common_modifiers:
        core = ' '.join(words[:-1])
        modifier = words[-1]
        return core, modifier
    
    # No modifier detected - it's a core type
    return grammar_str, None

print("Analyzing all 207 grammar types...")
print("=" * 80)

for item in data['unmapped_types']:
    grammar = item['grammar']
    count = item['count']
    
    core, modifier = extract_core_and_modifier(grammar)
    
    if core:
        core_types.add(core)
    if modifier:
        modifiers.add(modifier)
    
    examples[core].append({
        'full_grammar': grammar,
        'modifier': modifier,
        'count': count
    })

# Sort and display results
print(f"\nCORE GRAMMAR TYPES IDENTIFIED: {len(core_types)}")
print("-" * 80)
for core in sorted(core_types):
    examples_for_core = examples[core]
    total_count = sum(e['count'] for e in examples_for_core)
    print(f"\n{core} ({total_count} total entries)")
    for ex in sorted(examples_for_core, key=lambda x: -x['count'])[:5]:
        if ex['modifier']:
            print(f"  → {ex['full_grammar']} ({ex['count']})")
        else:
            print(f"  → [base form] ({ex['count']})")

print(f"\n\nMODIFIERS IDENTIFIED: {len(modifiers)}")
print("-" * 80)
for mod in sorted(modifiers):
    print(f"  - {mod}")

# Create the core grammar types JSON
core_grammar_types = {
    "description": "Core grammar types for Chuukese dictionary - primary grammatical categories",
    "version": "1.0",
    "date_created": "2026-01-10",
    "core_types": []
}

# Define core types with descriptions
core_definitions = {
    "noun": {
        "description": "A word that represents a person, place, thing, or idea",
        "example": "chala (basket)"
    },
    "verb": {
        "description": "A word that describes an action, state, or occurrence",
        "example": "chá (to go)"
    },
    "transitive verb": {
        "description": "A verb that requires a direct object",
        "example": "cháári (to carry something)"
    },
    "intransitive verb": {
        "description": "A verb that does not require a direct object",
        "example": "mááchááw (to be loud)"
    },
    "adjective": {
        "description": "A word that describes or modifies a noun",
        "example": "cháchcháák (big)"
    },
    "adverb": {
        "description": "A word that modifies a verb, adjective, or other adverb",
        "example": "chúen (well, properly)"
    },
    "pronoun": {
        "description": "A word that substitutes for a noun",
        "example": "ach (I, me)"
    },
    "possessive": {
        "description": "Indicates ownership or possession",
        "example": "ach (my)"
    },
    "preposition": {
        "description": "A word that shows relationship between nouns/pronouns and other words",
        "example": "aan (at, on)"
    },
    "conjunction": {
        "description": "A word that connects clauses or sentences",
        "example": "me (and)"
    },
    "particle": {
        "description": "A functional word that expresses grammatical relationships",
        "example": "aa (future marker)"
    },
    "interjection": {
        "description": "An exclamation or sudden remark",
        "example": "awe (yes)"
    },
    "auxiliary": {
        "description": "A helping verb used with main verbs",
        "example": "pwáán (used to)"
    },
    "article": {
        "description": "A word that defines a noun as specific or unspecific",
        "example": "e (the)"
    },
    "demonstrative": {
        "description": "A word that points to specific things",
        "example": "ei (this)"
    },
    "interrogative": {
        "description": "A word used to ask questions",
        "example": "ifa (who)"
    },
    "numeral": {
        "description": "A word representing a number",
        "example": "eú (one)"
    },
    "classifier": {
        "description": "A word used to count or classify nouns",
        "example": "eché (classifier for general objects)"
    },
    "ordinal": {
        "description": "A number indicating position or order",
        "example": "kaamesen (first)"
    },
    "quantifier": {
        "description": "A word that expresses quantity",
        "example": "fonuun (many)"
    },
    "locational noun": {
        "description": "A noun indicating location or place",
        "example": "lááw (outside)"
    },
    "relational noun": {
        "description": "A noun expressing spatial or kinship relations",
        "example": "aalen (on, surface of)"
    },
    "temporal noun": {
        "description": "A noun relating to time",
        "example": "raán (day)"
    },
    "number": {
        "description": "Numerical value (cardinal or ordinal)",
        "example": "eú (one)"
    }
}

# Add core types that exist in the data
for core in sorted(core_types):
    if core in core_definitions:
        core_grammar_types["core_types"].append({
            "name": core,
            "description": core_definitions[core]["description"],
            "example": core_definitions[core]["example"],
            "total_entries": sum(e['count'] for e in examples[core])
        })
    else:
        # Add without predefined description
        core_grammar_types["core_types"].append({
            "name": core,
            "description": f"{core.title()} category",
            "example": "",
            "total_entries": sum(e['count'] for e in examples[core])
        })

# Save core grammar types
output_file = str(Path(__file__).resolve().parent.parent / 'data' / 'grammar' / 'core_grammar_types.json')
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(core_grammar_types, f, indent=2, ensure_ascii=False)

print(f"\n\n✓ Core grammar types saved to: {output_file}")
print(f"Total core types: {len(core_grammar_types['core_types'])}")
print("=" * 80)