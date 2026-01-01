import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')
from src.database.db_factory import get_database_client, get_database_config

config = get_database_config()
client = get_database_client()
db = client[config['database_name']]
dictionary = db['dictionary_entries']

# Search for words with word boundaries
words = ['book', 'car', 'table', 'house', 'store', 'school', 'cat', 'ant', 'pen', 'room', 'bag', 'shelf', 'apple', 'coin', 'mouse', 'cake']
for w in words:
    results = list(dictionary.find({'english_translation': {'$regex': f'\\b{w}\\b', '$options': 'i'}}).limit(3))
    print(f'{w}:')
    for r in results:
        print(f"  {r.get('chuukese_word')} -> {r.get('english_translation')}")
    if not results:
        print('  NOT FOUND')
