from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()

# Analyze word entries
word_entries = list(db.dictionary_collection.find({'type': 'word'}))

print(f'Total entries: {db.dictionary_collection.count_documents({})}')
print(f'Word entries: {len(word_entries)}')

# Analyze grammar distribution
grammar_counts = {}
for entry in word_entries:
    grammar = entry.get('grammar') or 'unknown'
    grammar_counts[grammar] = grammar_counts.get(grammar, 0) + 1

print(f'\nGrammar distribution in word entries:')
for grammar in sorted(grammar_counts.keys()):
    count = grammar_counts[grammar]
    print(f'  {grammar}: {count}')

# Check for multiple meanings (comma-separated)
multiple_meanings = []
single_meanings = []
for entry in word_entries:
    english = entry.get('english_translation', '')
    if ',' in english:
        multiple_meanings.append(entry)
    else:
        single_meanings.append(entry)

print(f'\nMultiple meanings entries: {len(multiple_meanings)}')
print(f'Single meaning entries: {len(single_meanings)}')

# Sample multiple meanings
print('\nSample multiple meanings entries:')
for entry in multiple_meanings[:5]:
    chuukese = entry.get('chuukese_word', '')
    english = entry.get('english_translation', '')
    grammar = entry.get('grammar', '')
    print(f'CHK: "{chuukese}" | EN: "{english}" | Grammar: {grammar}')

print('\nSample single meaning entries:')
for entry in single_meanings[:5]:
    chuukese = entry.get('chuukese_word', '')
    english = entry.get('english_translation', '')
    grammar = entry.get('grammar', '')
    print(f'CHK: "{chuukese}" | EN: "{english}" | Grammar: {grammar}')