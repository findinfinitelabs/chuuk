from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Search for entries containing 'lúkúlúkú'
entries_luku = list(db.dictionary_collection.find({
    'chuukese': {'$regex': 'lúkúlúkú'}
}))

print(f'Found {len(entries_luku)} entries containing "lúkúlúkú":')
for entry in entries_luku:
    chuukese = entry.get('chuukese', '')
    english = entry.get('english', '')
    print(f'{chuukese} -> {english}')

# Check for entries with hyphens or special characters
print('\nChecking for entries with hyphens...')
entries_hyphen = list(db.dictionary_collection.find({
    'chuukese': {'$regex': '-'}
}))
print(f'Found {len(entries_hyphen)} entries with hyphens')

# Check for multi-word entries
print('\nChecking for multi-word entries...')
entries_multiword = list(db.dictionary_collection.find({
    'chuukese': {'$regex': ' '}
}))
print(f'Found {len(entries_multiword)} multi-word entries')

# Show some examples
if entries_multiword:
    print('\nSample multi-word entries:')
    for entry in entries_multiword[:5]:
        print(f'{entry.get("chuukese")} -> {entry.get("english")}')