"""Quick check: how many entries have references populated."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()
c = db.dictionary_collection

total_words = c.count_documents({"type": "word"})
with_refs = c.count_documents({"references": {"$exists": True, "$ne": ""}})
print(f"Words with references: {with_refs} / {total_words}")

# Show 5 samples
for s in c.find({"references": {"$exists": True, "$ne": ""}}, {"chuukese_word": 1, "references": 1}).limit(5):
    w = s.get("chuukese_word", "?")
    r = s.get("references", "")
    if len(r) > 100:
        r = r[:100] + "..."
    print(f"  {w}: {r}")
