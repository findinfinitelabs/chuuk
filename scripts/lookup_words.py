import sys
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')
from src.database.db_factory import get_database_client, get_database_config

config = get_database_config()
client = get_database_client()
db = client[config['database_name']]
dictionary = db['dictionary_entries']

# All nouns from grammarData.json
nouns = [
    'book', 'magazine', 'brochure', 'tract', 'songbook', 'Bible', 'textbook', 
    'notepad', 'pen', 'photograph', 'map', 'microphone', 'skipping rope',
    'coin', 'cake', 'apple', 'tomato', 'ant', 'mouse', 'cat'
]

# All locations from grammarData.json  
locations = [
    'shelf', 'car', 'refrigerator', 'store', 'table', 'house', 
    'school', 'room', 'floor', 'bag'
]

all_words = nouns + locations

print("=== NOUN TRANSLATIONS ===")
for w in nouns:
    r = list(dictionary.find({'english_translation': {'$regex': f'^{w}$', '$options': 'i'}}).limit(1))
    if not r:
        # Try partial match
        r = list(dictionary.find({'english_translation': {'$regex': w, '$options': 'i'}}).limit(1))
    if r:
        print(f'"{w}": "{r[0].get("chuukese_word")}"')
    else:
        print(f'"{w}": NOT FOUND')

print("\n=== LOCATION TRANSLATIONS ===")
for w in locations:
    r = list(dictionary.find({'english_translation': {'$regex': f'^{w}$', '$options': 'i'}}).limit(1))
    if not r:
        r = list(dictionary.find({'english_translation': {'$regex': w, '$options': 'i'}}).limit(1))
    if r:
        print(f'"{w}": "{r[0].get("chuukese_word")}"')
    else:
        print(f'"{w}": NOT FOUND')
