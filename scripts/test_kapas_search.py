#!/usr/bin/env python3
"""
Test script to debug "kapas eis" search issue
"""
import os
import sys
import re
from urllib.parse import quote_plus

# Setup path before any imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env file manually
from pathlib import Path
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path, override=True)

# Now import pymongo directly
from pymongo import MongoClient

def test_kapas_search():
    # Connect directly to database
    endpoint = os.getenv('COSMOS_DB_URI')
    key = os.getenv('COSMOS_DB_KEY')
    
    if not endpoint or not key:
        print(f"Missing COSMOS_DB_URI or COSMOS_DB_KEY")
        print(f"  endpoint: {endpoint}")
        print(f"  key exists: {bool(key)}")
        return
    
    # Build MongoDB connection string for Cosmos DB
    # Extract account name from endpoint
    account_name = endpoint.split('//')[1].split('.')[0]
    host = f"{account_name}.mongo.cosmos.azure.com"
    encoded_key = quote_plus(key)
    
    connection_string = f"mongodb://{account_name}:{encoded_key}@{host}:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000"
    
    client = MongoClient(connection_string)
    db = client['chuuk_dictionary']
    dictionary_collection = db['dictionary']
    phrases_collection = db['phrases']
    
    word = "kapas"
    
    print("=" * 60)
    print("TESTING KAPAS SEARCH")
    print("=" * 60)
    
    # Check dictionary_collection
    print("\n1. Searching dictionary_collection for 'kapas'...")
    query = {
        '$or': [
            {'chuukese_word': {'$regex': re.escape(word), '$options': 'i'}},
            {'english_translation': {'$regex': re.escape(word), '$options': 'i'}},
            {'definition': {'$regex': re.escape(word), '$options': 'i'}}
        ]
    }
    word_results = list(dictionary_collection.find(query).limit(100))
    print(f"   Found {len(word_results)} results in dictionary_collection")
    for r in word_results[:15]:
        print(f"   - '{r.get('chuukese_word', 'N/A')}' -> '{r.get('english_translation', 'N/A')[:50]}'")
    
    # Check phrases_collection
    print("\n2. Searching phrases_collection for 'kapas'...")
    phrase_query = {
        '$or': [
            {'chuukese_sentence': {'$regex': re.escape(word), '$options': 'i'}},
            {'chuukese_phrase': {'$regex': re.escape(word), '$options': 'i'}},
            {'chuukese_word': {'$regex': re.escape(word), '$options': 'i'}},
            {'english_translation': {'$regex': re.escape(word), '$options': 'i'}},
            {'definition': {'$regex': re.escape(word), '$options': 'i'}}
        ]
    }
    phrase_results = list(phrases_collection.find(phrase_query).limit(100))
    print(f"   Found {len(phrase_results)} results in phrases_collection")
    for r in phrase_results[:15]:
        text = r.get('chuukese_word') or r.get('chuukese_sentence') or r.get('chuukese_phrase') or 'N/A'
        print(f"   - '{text}' -> '{r.get('english_translation', 'N/A')[:50]}'")
    
    # Check specifically for "kapas eis"
    print("\n3. Direct search for 'kapas eis'...")
    direct_query = {'chuukese_word': {'$regex': 'kapas eis', '$options': 'i'}}
    direct_results = list(dictionary_collection.find(direct_query))
    direct_results += list(phrases_collection.find(direct_query))
    print(f"   Found {len(direct_results)} direct matches for 'kapas eis'")
    for r in direct_results:
        print(f"   - '{r.get('chuukese_word', 'N/A')}' -> '{r.get('english_translation', 'N/A')}'")
    
    # Check all fields for kapas eis
    print("\n4. Checking all text fields for 'kapas eis'...")
    any_query = {
        '$or': [
            {'chuukese_word': {'$regex': 'kapas.*eis', '$options': 'i'}},
            {'chuukese_sentence': {'$regex': 'kapas.*eis', '$options': 'i'}},
            {'chuukese_phrase': {'$regex': 'kapas.*eis', '$options': 'i'}},
            {'definition': {'$regex': 'kapas.*eis', '$options': 'i'}},
            {'english_translation': {'$regex': 'kapas.*eis', '$options': 'i'}}
        ]
    }
    any_results = list(dictionary_collection.find(any_query))
    any_results += list(phrases_collection.find(any_query))
    print(f"   Found {len(any_results)} matches for 'kapas.*eis' pattern")
    for r in any_results:
        text = r.get('chuukese_word') or r.get('chuukese_sentence') or r.get('chuukese_phrase')
        print(f"   - '{text}' -> '{r.get('english_translation', 'N/A')}'")
        print(f"     Definition: {r.get('definition', 'N/A')[:100]}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_kapas_search()
