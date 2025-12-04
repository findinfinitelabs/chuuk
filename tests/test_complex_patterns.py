#!/usr/bin/env python3
"""Test the enhanced dictionary pattern recognition with complex Chuukese examples"""

import re
from src.database.dictionary_db import DictionaryDB
import tempfile
import os

def test_complex_patterns():
    """Test complex dictionary patterns with real Chuukese examples"""
    
    # Test lines representing complex Chuukese dictionary structures
    test_lines = [
        # Your provided example
        "chem – remember, chemeni – v. remember, chechchemeni, -ei, -uk*, -kem, -kemi, -ir, -kich – remember (me, you, etc.)",
        
        # Similar complex patterns
        "mwoch – sleep, mwocheni – v. sleep, chemwocheni, -ei, -uk, -kem, -kemi, -ir, -kich – sleep (with me, you, etc.)",
        
        # Root word with simple inflections
        "kopwe – will, -ei, -uk, -ir – future tense markers (me, you, him)",
        
        # Cross-reference pattern
        "fansoun – see fansou, Grammar 4.2.1",
        
        # Complex grammatical entry
        "pwata (n.) – thing, pwateki, -ei, -uk*, -kem, -kemi, -ir, -kich – things (my, your, his, our, your pl., their)",
        
        # Standard entries for comparison
        "mwenge – feast",
        "aninis – ant, insect",
        
        # Page reference
        "kopwe - see page 45, Grammar section 2.3"
    ]
    
    # Create temporary database instance
    db = DictionaryDB()
    
    print("Testing Enhanced Dictionary Pattern Recognition")
    print("=" * 60)
    
    for i, line in enumerate(test_lines, 1):
        print(f"\nTest {i}: {line}")
        print("-" * 50)
        
        # Test each pattern against the line
        patterns = [
            (r'^([^–\-,]+)\s*[–\-]\s*([^,]+)(?:,|$)', "Pattern 1: Standard word – translation"),
            (r'^([^,]+),\s*([^,\n]+)$', "Pattern 2: Standard word, translation"),
            (r'^([^\(]+)\s*\([^\)]+\)\s*[–\-]\s*([^,\n]+)', "Pattern 3: Word (type) – translation"),
            (r'"([^"]+)"\s*[–\-]\s*([^,\n]+)', "Pattern 4: 'translation' – word"),
            (r'^([^\s]+)\s{2,}[–\-]\s{2,}([^,\n]+)', "Pattern 5: Word  –  translation (wide spacing)"),
            (r'see page \d+|Grammar \d+\.\d+|section \d+\.\d+', "Pattern 6: Page references"),
            (r'^([^–\-,]+)\s*[–\-][^,]*, ([^,]+), ([^–\-]+)\s*[–\-]\s*([^(]+)\(([^)]+)\)', "Pattern 7: Complex grammatical forms"),
            (r'^([^–\-,]+).*?(-\w{1,3}[*]?,?\s*)+.*?[–\-]\s*([^(]+)\(([^)]+)\)', "Pattern 8: Root word with inflections"),
            (r'see \w+|Grammar \d+\.\d+\.\d+', "Pattern 9: Cross-references"),
            (r'^([^–\-,]+)[–\-][^,]*,\s*([^–\-]+)[–\-][^,]*,.*?[–\-]\s*([^(]+)\(([^)]+)\)', "Pattern 10: Complex multi-component")
        ]
        
        matches = []
        for j, (pattern, description) in enumerate(patterns, 1):
            match = re.search(pattern, line)
            if match:
                matches.append((j, description, match.groups()))
        
        if matches:
            for pattern_num, desc, groups in matches:
                print(f"  ✓ {desc}")
                print(f"    Groups: {groups}")
        else:
            print("  ✗ No patterns matched")
    
    print("\n" + "=" * 60)
    print("Enhanced Pattern Recognition Test Complete")

if __name__ == "__main__":
    test_complex_patterns()