import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DB_TYPE'] = 'cosmos'
from src.database.dictionary_db import DictionaryDB
db = DictionaryDB()

# Check actual values in database for fáik entries - get more fields
results = list(db.dictionary_collection.find({'chuukese_word': {'$regex': 'fáik', '$options': 'i'}}).limit(15))
print(f"Found {len(results)} entries containing 'fáik':")
for r in results:
    print(f"  Word: '{r.get('chuukese_word', '')}' | Translation: '{r.get('english_translation', '')}' | Def: '{r.get('definition', '')[:50] if r.get('definition') else ''}' | Grammar: '{r.get('grammar', '')}'")

# Also check for ordinal entries
print("\n\nSearching for 'ordinal' in definition or grammar:")
ordinal_results = list(db.dictionary_collection.find({
    '$or': [
        {'definition': {'$regex': 'ordinal', '$options': 'i'}},
        {'grammar': {'$regex': 'ordinal', '$options': 'i'}},
        {'type': {'$regex': 'ordinal', '$options': 'i'}}
    ]
}).limit(10))
print(f"Found {len(ordinal_results)} ordinal-related entries:")
for r in ordinal_results:
    print(f"  Word: '{r.get('chuukese_word', '')}' | Translation: '{r.get('english_translation', '')}' | Def: '{r.get('definition', '')[:50] if r.get('definition') else ''}'  | Grammar: '{r.get('grammar', '')}'")

