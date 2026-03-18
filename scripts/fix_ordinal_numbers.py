#!/usr/bin/env python3
"""
Script to fix ordinal number translations in the database.
The ordinal entries currently have generic "ordinal number" translations
instead of proper ordinal values (first, second, third, etc.)
"""

import os
import sys
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DB_TYPE"] = "cosmos"

from src.database.dictionary_db import DictionaryDB

# Chuukese number mappings
CHUUKESE_NUMBERS = {
    "eú": 1,
    "ew": 1,
    "rúú": 2,
    "ulungat": 3,
    "unungat": 3,
    "únúngat": 3,
    "rúánú": 4,
    "fáánú": 4,
    "nimu": 5,
    "wonu": 6,
    "onu": 6,
    "fisu": 7,
    "wanu": 8,
    "wálú": 8,
    "tiu": 9,
    "engón": 10,
    "engon": 10,
}

# Ordinal English translations
ORDINALS = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
}

# Cardinal English translations
CARDINALS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def extract_number_from_word(chuukese_word):
    """Extract the number value from a Chuukese word/phrase."""
    word_lower = chuukese_word.lower().strip()

    # Check for compound numbers with prefixes like ipúkú (100s), engonopúk (1000s), etc.
    # For now, focus on simple ordinals with "fáik me X"

    for chk_num, value in CHUUKESE_NUMBERS.items():
        if chk_num.lower() in word_lower:
            return value
    return None


def determine_ordinal_translation(chuukese_word):
    """Determine the correct ordinal translation for a Chuukese phrase."""
    word_lower = chuukese_word.lower().strip()

    # Pattern: "fáik me X" or "fáik me X / Y" (ordinal)
    if "fáik" in word_lower or "faik" in word_lower:
        if " me " in word_lower:
            # Extract the number part after "me"
            parts = word_lower.split(" me ")
            if len(parts) >= 2:
                num_part = parts[1].strip()
                # Handle alternatives like "eú / ew"
                num_part = num_part.split("/")[0].strip()

                for chk_num, value in CHUUKESE_NUMBERS.items():
                    if chk_num.lower() == num_part or num_part.startswith(chk_num.lower()):
                        return ORDINALS.get(value, f"{value}th")
        else:
            # Just "fáik" alone
            return "ordinal number marker (prefix for ordinals)"

    return None


def fix_ordinal_numbers(dry_run=True):
    """Fix ordinal number translations in the database."""
    db = DictionaryDB()

    if not db.client:
        print("❌ Failed to connect to database")
        return

    # Find all entries with "ordinal number" as the translation
    query = {
        "$or": [
            {"english_translation": "ordinal number"},
            {"english_translation": {"$regex": "^ordinal number$", "$options": "i"}},
        ]
    }

    entries = list(db.dictionary_collection.find(query))
    print(f"Found {len(entries)} entries with 'ordinal number' translation")

    updates = []
    skipped = []

    for entry in entries:
        chuukese = entry.get("chuukese_word", "")
        current_translation = entry.get("english_translation", "")
        entry_id = entry.get("_id")

        new_translation = determine_ordinal_translation(chuukese)

        if new_translation and new_translation != current_translation:
            updates.append(
                {
                    "_id": entry_id,
                    "chuukese_word": chuukese,
                    "old_translation": current_translation,
                    "new_translation": new_translation,
                    "new_definition": f"Ordinal number: {new_translation}",
                }
            )
        else:
            skipped.append(
                {
                    "chuukese_word": chuukese,
                    "reason": "Could not determine ordinal" if not new_translation else "Already correct",
                }
            )

    print("\n📊 Summary:")
    print(f"  - Will update: {len(updates)} entries")
    print(f"  - Skipped: {len(skipped)} entries")

    if updates:
        print("\n📝 Updates to apply:")
        for u in updates[:20]:  # Show first 20
            print(f"  {u['chuukese_word']}: '{u['old_translation']}' → '{u['new_translation']}'")
        if len(updates) > 20:
            print(f"  ... and {len(updates) - 20} more")

    if skipped:
        print("\n⏭️ Skipped entries (first 10):")
        for s in skipped[:10]:
            print(f"  {s['chuukese_word']}: {s['reason']}")

    if dry_run:
        print("\n🔍 DRY RUN - No changes made. Run with --apply to apply changes.")
        return updates

    # Apply updates
    print(f"\n⚡ Applying {len(updates)} updates...")
    success_count = 0
    error_count = 0

    for u in updates:
        try:
            result = db.dictionary_collection.update_one(
                {"_id": u["_id"]},
                {"$set": {"english_translation": u["new_translation"], "definition": u["new_definition"]}},
            )
            if result.modified_count > 0:
                success_count += 1
            else:
                print(f"  ⚠️ No modification for: {u['chuukese_word']}")
        except Exception as e:
            error_count += 1
            print(f"  ❌ Error updating {u['chuukese_word']}: {e}")

    print(f"\n✅ Complete: {success_count} updated, {error_count} errors")
    return updates


def fix_cardinal_numbers(dry_run=True):
    """Fix base cardinal number translations that are incorrectly set to 'ordinal number'."""
    db = DictionaryDB()

    if not db.client:
        print("❌ Failed to connect to database")
        return

    updates = []

    # Check each base number
    for chk_word, num_value in CHUUKESE_NUMBERS.items():
        # Find entries for this number word
        query = {
            "chuukese_word": {"$regex": f"^{re.escape(chk_word)}$", "$options": "i"},
            "english_translation": "ordinal number",
        }

        entries = list(db.dictionary_collection.find(query))

        for entry in entries:
            cardinal = CARDINALS.get(num_value, str(num_value))
            updates.append(
                {
                    "_id": entry.get("_id"),
                    "chuukese_word": entry.get("chuukese_word"),
                    "old_translation": entry.get("english_translation"),
                    "new_translation": cardinal,
                    "new_definition": f"Cardinal number: {cardinal} ({num_value})",
                }
            )

    print("\n📊 Cardinal Number Fixes:")
    print(f"  - Will update: {len(updates)} entries")

    if updates:
        print("\n📝 Updates to apply:")
        for u in updates:
            print(f"  {u['chuukese_word']}: '{u['old_translation']}' → '{u['new_translation']}'")

    if dry_run:
        print("\n🔍 DRY RUN - No changes made. Run with --apply to apply changes.")
        return updates

    # Apply updates
    print(f"\n⚡ Applying {len(updates)} updates...")
    success_count = 0

    for u in updates:
        try:
            result = db.dictionary_collection.update_one(
                {"_id": u["_id"]},
                {"$set": {"english_translation": u["new_translation"], "definition": u["new_definition"]}},
            )
            if result.modified_count > 0:
                success_count += 1
        except Exception as e:
            print(f"  ❌ Error updating {u['chuukese_word']}: {e}")

    print(f"\n✅ Complete: {success_count} cardinal numbers updated")
    return updates


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fix ordinal and cardinal number translations")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--ordinals-only", action="store_true", help="Only fix ordinal numbers")
    parser.add_argument("--cardinals-only", action="store_true", help="Only fix cardinal numbers")

    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Run with --apply to apply changes\n")
    else:
        print("⚡ APPLY MODE - Changes will be written to database\n")

    if not args.cardinals_only:
        print("=" * 60)
        print("FIXING ORDINAL NUMBERS (fáik me X → first, second, etc.)")
        print("=" * 60)
        fix_ordinal_numbers(dry_run=dry_run)

    if not args.ordinals_only:
        print("\n" + "=" * 60)
        print("FIXING CARDINAL NUMBERS (base numbers with wrong translations)")
        print("=" * 60)
        fix_cardinal_numbers(dry_run=dry_run)

    print("\n✨ Done!")
