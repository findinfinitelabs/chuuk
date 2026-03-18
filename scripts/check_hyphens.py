"""Check how many dictionary words have hyphens and analyze suffix patterns."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.dictionary_db import DictionaryDB
from collections import Counter

db = DictionaryDB()
results = list(
    db.dictionary_collection.find(
        {"type": "word", "chuukese_word": {"$regex": "-"}},
        {"chuukese_word": 1, "english_translation": 1, "definition": 1, "grammar": 1, "_id": 1},
    )
)

print(f"Total words with hyphen: {len(results)}")
print()

# Show examples
print("=== First 40 examples ===")
for r in results[:40]:
    ch = r.get("chuukese_word", "")
    en = str(r.get("english_translation", ""))[:50]
    defn = str(r.get("definition", ""))[:40]
    gt = r.get("grammar", "")
    print(f"  {ch:30s} | {en:50s} | {defn:40s} | {gt}")

print("...")
print()

# Suffix analysis
suffixes = []
multi_hyphen = []
for r in results:
    parts = r["chuukese_word"].split("-")
    if len(parts) == 2:
        suffixes.append(parts[1])
    else:
        multi_hyphen.append(r["chuukese_word"])

sc = Counter(suffixes)
print("=== Suffix frequency (top 30) ===")
for s, c in sc.most_common(30):
    print(f"  -{s}: {c}")

if multi_hyphen:
    print(f"\n=== Words with multiple hyphens ({len(multi_hyphen)}) ===")
    for w in multi_hyphen[:20]:
        print(f"  {w}")
