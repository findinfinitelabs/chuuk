from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Check mwomw
entries_mwomw = list(db.dictionary_collection.find({'chuukese': 'mwomw'}))
print(f'Found {len(entries_mwomw)} entries for mwomw')
for entry in entries_mwomw:
    print(f'Chuukese: {entry.get("chuukese")}')
    print(f'English: {entry.get("english")}')
    print(f'Definition: {entry.get("definition")}')
    print('---')

# Check lúkúlúkúuk
entries_luku = list(db.dictionary_collection.find({'chuukese': 'lúkúlúkúuk'}))
print(f'Found {len(entries_luku)} entries for lúkúlúkúuk')
for entry in entries_luku:
    print(f'Chuukese: {entry.get("chuukese")}')
    print(f'English: {entry.get("english")}')
    print(f'Definition: {entry.get("definition")}')
    print('---')

# Also check what the model produces for lúkúlúkúuk
from transformers import pipeline
model = pipeline('translation', model='models/helsinki-chuukese_chuukese_to_english/finetuned')
result = model('lúkúlúkúuk', max_length=128)
print(f'Model translation of lúkúlúkúuk: {result[0]["translation_text"]}')