#!/usr/bin/env python3
"""Query Cosmos DB for single-word Chuukese entries that match a base word + suffix pattern.

Example:
  ./ .venv/bin/python scripts/query_suffix_words.py aal

This prints entries like: aal-ach, aal-an, aal-ei, aal-emi
Excludes phrases/sentences by:
- requiring no whitespace in chuukese_word
- excluding type in {phrase, sentence} when present
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.db_factory import get_database_client, get_database_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "base",
        nargs="?",
        default="aal",
        help="Base word to match (default: aal). Ignored when --list-suffixes is used.",
    )
    parser.add_argument(
        "--list-suffixes",
        action="store_true",
        help="List all hyphen suffixes found in single-word entries (no spaces), with counts and examples.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=100,
        help="When --list-suffixes is used, show only the top N suffixes by count (default: 100).",
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=8,
        help="When --list-suffixes is used, show up to this many example words per suffix (default: 8).",
    )
    args = parser.parse_args()

    base = (args.base or "").strip()
    if not args.list_suffixes and not base:
        raise SystemExit("Base word is required")

    cfg = get_database_config()
    client = get_database_client()
    collection = client[cfg["database_name"]][cfg["container_name"]]

    projection = {"_id": 0, "chuukese_word": 1, "type": 1}

    if args.list_suffixes:
        # Single words only (no whitespace), must contain at least one hyphen.
        query = {
            "chuukese_word": {"$regex": r"^[^\s]+-[^\s]+$", "$options": "i"},
            "type": {"$nin": ["phrase", "sentence"]},
        }

        suffix_counts: dict[str, int] = {}
        suffix_examples: dict[str, list[str]] = {}

        for doc in collection.find(query, projection):
            word = doc.get("chuukese_word")
            if not word or "-" not in word or re.search(r"\s", word):
                continue

            # Suffix is the part after the last hyphen.
            suffix = word.rsplit("-", 1)[-1].strip().lower()
            if not suffix:
                continue

            suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
            if suffix not in suffix_examples:
                suffix_examples[suffix] = []
            if len(suffix_examples[suffix]) < max(0, args.examples):
                suffix_examples[suffix].append(word)

        ordered = sorted(suffix_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if args.top and args.top > 0:
            ordered = ordered[: args.top]

        total_suffixes = len(suffix_counts)
        total_words = sum(suffix_counts.values())
        print(f"Found {total_suffixes} distinct hyphen suffix(es) across {total_words} hyphenated WORD(s).")

        for suffix, count in ordered:
            examples = ", ".join(suffix_examples.get(suffix, [])[: max(0, args.examples)])
            if examples:
                print(f"-{suffix}  ({count})  e.g. {examples}")
            else:
                print(f"-{suffix}  ({count})")

    else:
        # Match: base-<suffix> where suffix has no whitespace
        # Case-insensitive per user request.
        pattern = rf"^{re.escape(base)}-[^\s]+$"
        query = {
            "chuukese_word": {"$regex": pattern, "$options": "i"},
            "type": {"$nin": ["phrase", "sentence"]},
        }

        words = sorted(
            {
                doc.get("chuukese_word")
                for doc in collection.find(query, projection)
                if doc.get("chuukese_word")
            },
            key=lambda w: w.lower(),
        )

        print(f"Found {len(words)} WORDS matching {base}-<suffix>:")
        for word in words:
            print(word)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
