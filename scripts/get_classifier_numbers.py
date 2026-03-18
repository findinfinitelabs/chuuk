#!/usr/bin/env python3
"""Get classifier numbers 1-10 for each type"""

from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()
connection_string = os.getenv("COSMOS_CONNECTION_STRING")
client = MongoClient(connection_string)
db = client["chuuk-dictionary"]

# Search for classifier numbers
classifiers = {"person_or_animal": "person", "long_objects": "long", "flat_objects": "flat", "round_objects": "round"}

print("Searching numbers_collection for classifiers...")
for key, term in classifiers.items():
    print(f"\n{key.upper().replace('_', ' ')}:")
    results = list(
        db.numbers_collection.find(
            {
                "$or": [
                    {"grammar_modifier": {"$regex": term, "$options": "i"}},
                    {"type": {"$regex": term, "$options": "i"}},
                    {"definition": {"$regex": term, "$options": "i"}},
                ],
                "number_value": {"$lte": 10},
            }
        )
        .sort("number_value", 1)
        .limit(10)
    )

    if results:
        for r in results:
            print(
                f"  {r.get('number_value', 'N/A')}: {r.get('chuukese_word', 'N/A')} - {r.get('english_translation', '')}"
            )
    else:
        print("  No results found")

print("\n\nAll numbers 1-10:")
all_nums = list(db.numbers_collection.find({"number_value": {"$lte": 10}}).sort("number_value", 1))
for r in all_nums[:20]:
    print(
        f"  {r.get('number_value', 'N/A')}: {r.get('chuukese_word', 'N/A')} - Type: {r.get('type', 'N/A')} - Grammar: {r.get('grammar', 'N/A')}/{r.get('grammar_modifier', 'N/A')}"
    )
