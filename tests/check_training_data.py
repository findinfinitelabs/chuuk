from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Get some sample entries to see the data format
entries = list(db.dictionary_collection.find().limit(20))

print(f'Found {len(entries)} entries')
print('Sample entries:')
for i, entry in enumerate(entries[:10]):
    chuukese = entry.get('chuukese_word', '')
    english = entry.get('english_translation', '')
    print(f'{i+1}. CHK: "{chuukese}" -> EN: "{english}"')

# Check for entries that would be used in English->Chuukese training
# (These would be reversed)
valid_entries = []
for entry in entries:
    chuukese = entry.get('chuukese_word', '').strip()
    english = entry.get('english_translation', '').strip()
    if chuukese and english:
        valid_entries.append((english, chuukese))

print(f'\nValid entries for EN->CHK training: {len(valid_entries)}')
print('Sample EN->CHK pairs:')
for i, (en, chk) in enumerate(valid_entries[:10]):
    print(f'{i+1}. EN: "{en}" -> CHK: "{chk}"')