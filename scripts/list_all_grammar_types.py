#!/usr/bin/env python3
"""
Script to list all unique grammar types with their IDs and counts from the database.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.dictionary_db import DictionaryDB, GRAMMAR_NORMALIZATION


def get_all_grammar_types():
    """Get all unique grammar types with document IDs and counts."""
    db = DictionaryDB()

    if not db.client:
        print("Failed to connect to database")
        return

    print("\n" + "=" * 80)
    print("GRAMMAR TYPES ANALYSIS")
    print("=" * 80)

    # Get all unique grammar values with counts using aggregation
    pipeline = [
        {"$match": {"grammar": {"$exists": True, "$ne": None, "$ne": ""}}},
        {
            "$group": {
                "_id": "$grammar",
                "count": {"$sum": 1},
                "sample_ids": {"$push": "$_id"},
                "sample_words": {"$push": "$chuukese_word"},
            }
        },
        {
            "$project": {
                "grammar": "$_id",
                "count": 1,
                "sample_ids": {"$slice": ["$sample_ids", 5]},
                "sample_words": {"$slice": ["$sample_words", 3]},
            }
        },
        {"$sort": {"count": -1}},
    ]

    try:
        results = list(db.dictionary_collection.aggregate(pipeline))
    except Exception as e:
        print(f"Error querying database: {e}")
        return

    print(f"\nTotal unique grammar types: {len(results)}")
    print(f"Total entries with grammar: {sum(r['count'] for r in results)}")

    # Check which grammar types are NOT in the normalization map
    unmapped_types = []
    mapped_types = []

    print("\n" + "-" * 80)
    print("GRAMMAR TYPES BREAKDOWN")
    print("-" * 80)
    print(f"{'Grammar Type':<50} {'Count':>10} {'Status':>15}")
    print("-" * 80)

    for result in results:
        grammar = result["grammar"]
        count = result["count"]

        # Skip None values
        if grammar is None:
            continue

        # Check if this grammar type needs normalization
        if grammar in GRAMMAR_NORMALIZATION:
            status = "→ MAPPED"
            mapped_types.append(
                {
                    "original": grammar,
                    "mapped_to": GRAMMAR_NORMALIZATION[grammar],
                    "count": count,
                    "sample_ids": [str(id) for id in result["sample_ids"]],  # Convert ObjectId to string
                    "sample_words": result["sample_words"],
                }
            )
        else:
            status = "✓ STANDARD"
            unmapped_types.append(
                {
                    "grammar": grammar,
                    "count": count,
                    "sample_ids": [str(id) for id in result["sample_ids"]],  # Convert ObjectId to string
                    "sample_words": result["sample_words"],
                }
            )

        print(f"{grammar:<50} {count:>10} {status:>15}")

    # Show mapping details
    if mapped_types:
        print("\n" + "=" * 80)
        print("TYPES THAT NEED NORMALIZATION")
        print("=" * 80)
        for item in mapped_types:
            normalized = GRAMMAR_NORMALIZATION[item["original"]]
            if normalized is None:
                action = "REMOVE (invalid)"
            else:
                action = f"→ '{normalized}'"
            print(f"\n'{item['original']}' ({item['count']} entries) {action}")
            print(f"  Sample IDs: {', '.join(str(id) for id in item['sample_ids'][:3])}")
            print(f"  Sample words: {', '.join(item['sample_words'][:3])}")

    # Show standard types
    print("\n" + "=" * 80)
    print("STANDARD GRAMMAR TYPES (no normalization needed)")
    print("=" * 80)
    print(f"{'Type':<40} {'Count':>10} {'Sample Words':>25}")
    print("-" * 80)
    for item in unmapped_types[:20]:  # Show top 20
        words = ", ".join(item["sample_words"][:2])
        print(f"{item['grammar']:<40} {item['count']:>10}  {words[:25]}")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total unique types: {len(results)}")
    print(f"Types needing normalization: {len(mapped_types)}")
    print(f"Already standard types: {len(unmapped_types)}")
    print(f"Entries affected by normalization: {sum(m['count'] for m in mapped_types)}")

    # Export to JSON for further analysis
    export_data = {
        "total_unique_types": len(results),
        "types_needing_normalization": len(mapped_types),
        "standard_types": len(unmapped_types),
        "mapped_types": mapped_types,
        "unmapped_types": unmapped_types,
        "normalization_map": GRAMMAR_NORMALIZATION,
    }

    output_file = str(Path(__file__).resolve().parent / "grammar_types_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Full analysis exported to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    get_all_grammar_types()
