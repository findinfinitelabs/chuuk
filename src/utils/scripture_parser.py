"""
Scripture reference parsing utilities.
Loads book names from config and provides regex patterns for matching scripture references.
"""
import json
import os
import re
from functools import lru_cache


def get_config_path():
    """Get the path to the scripture_books.json config file."""
    # Try multiple possible locations
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'scripture_books.json'),
        os.path.join(os.path.dirname(__file__), '..', 'config', 'scripture_books.json'),
        os.path.join(os.getcwd(), 'config', 'scripture_books.json'),
        'config/scripture_books.json',
    ]
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path
    
    raise FileNotFoundError("scripture_books.json not found in any expected location")


@lru_cache(maxsize=1)
def load_scripture_books():
    """Load scripture book names from config file."""
    config_path = get_config_path()
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config['books']


@lru_cache(maxsize=1)
def get_all_book_names():
    """Get a flat list of all scripture book names (abbreviations and full names)."""
    books = load_scripture_books()
    all_names = []
    for key, names in books.items():
        all_names.extend(names)
    return all_names


@lru_cache(maxsize=1)
def get_book_names_pattern():
    """Build regex pattern for matching any scripture book name."""
    all_names = get_all_book_names()
    # Sort by length descending so longer names match first (e.g., "Corinthians" before "Cor")
    all_names_sorted = sorted(all_names, key=len, reverse=True)
    return r'(?:' + '|'.join(re.escape(name) for name in all_names_sorted) + r')'


@lru_cache(maxsize=1)
def get_scripture_reference_pattern():
    """
    Build regex pattern for matching scripture references.
    
    Examples matched:
    - 1 Cor. 13:4, 7
    - Féf. 5:42
    - Acts 19:8-10
    - 1 Corinthians 15:33
    - Mateus 5:3
    """
    book_names = get_book_names_pattern()
    # Pattern: [optional 1-3] BookName[.] chapter:verse(s)
    # Supports comma and hyphen verse ranges, semicolon for multiple refs
    pattern = rf'([1-3]?\s*{book_names}\.?\s+\d+:\s*\d+(?:\s*[-–,]\s*\d+)*(?:\s*;\s*[1-3]?\s*{book_names}\.?\s+\d+:\s*\d+(?:\s*[-–,]\s*\d+)*)*)'
    return pattern


def protect_scripture_references(text):
    """
    Protect scripture references in text from being split by sentence boundaries.
    
    Returns:
        tuple: (protected_text, list of protected references)
    """
    pattern = get_scripture_reference_pattern()
    protected_refs = []
    
    def protect_ref(match):
        placeholder = f"<<<REF_{len(protected_refs)}>>>"
        protected_refs.append(match.group(0))
        return placeholder
    
    protected_text = re.sub(pattern, protect_ref, text)
    return protected_text, protected_refs


def restore_scripture_references(text, protected_refs):
    """Restore protected scripture references in text."""
    for i, ref in enumerate(protected_refs):
        text = text.replace(f"<<<REF_{i}>>>", ref)
    return text


# For backwards compatibility and direct import
def get_pattern():
    """Alias for get_scripture_reference_pattern()."""
    return get_scripture_reference_pattern()
