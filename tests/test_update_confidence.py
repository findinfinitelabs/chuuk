#!/usr/bin/env python3
"""Test script for update confidence endpoint with batched updates"""
import sys
import time
import re
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')

from src.database.dictionary_db import DictionaryDB


def batch_update_collection(collection, query, confidence_score, collection_name):
    """Update documents in batches to avoid Cosmos DB rate limiting"""
    updated_count = 0
    batch_size = 50
    max_retries = 5
    
    # Get all document IDs first
    docs = list(collection.find(query, {'_id': 1}))
    total_docs = len(docs)
    
    if total_docs == 0:
        print(f"   [{collection_name}] No documents found")
        return 0
    
    print(f"   [{collection_name}] Found {total_docs} documents to update")
    
    for i in range(0, total_docs, batch_size):
        batch_ids = [doc['_id'] for doc in docs[i:i + batch_size]]
        batch_num = i // batch_size + 1
        total_batches = (total_docs + batch_size - 1) // batch_size
        
        retries = max_retries
        while retries > 0:
            try:
                result = collection.update_many(
                    {'_id': {'$in': batch_ids}},
                    {'$set': {'confidence_score': confidence_score}}
                )
                updated_count += result.modified_count
                print(f"   [{collection_name}] Batch {batch_num}/{total_batches}: {result.modified_count} updated")
                break
            except Exception as e:
                error_str = str(e)
                if '16500' in error_str:
                    retries -= 1
                    retry_match = re.search(r'RetryAfterMs=(\d+)', error_str)
                    delay = max(int(retry_match.group(1)) / 1000.0 if retry_match else 1.0, 1.0)
                    delay = min(delay * (2 ** (max_retries - retries)), 10.0)
                    print(f"   [{collection_name}] Rate limited, waiting {delay:.1f}s ({retries} retries left)")
                    time.sleep(delay)
                else:
                    print(f"   [{collection_name}] Error: {e}")
                    break
        
        time.sleep(0.3)  # Small delay between batches
    
    return updated_count


db = DictionaryDB()

pub_id = '20251224160032_653c5045'
confidence_score = 100

print(f'Testing batched update_many on publication: {pub_id}')

# Test update on dictionary_collection
print('\n1. Testing dictionary_collection...')
dict_updated = batch_update_collection(
    db.dictionary_collection, 
    {'publication_id': pub_id}, 
    confidence_score, 
    "dictionary"
)

# Test update on phrases_collection
print('\n2. Testing phrases_collection...')
phrases_updated = batch_update_collection(
    db.phrases_collection, 
    {'publication_id': pub_id}, 
    confidence_score, 
    "phrases"
)

# Test update on paragraphs_collection
print('\n3. Testing paragraphs_collection...')
paragraphs_updated = batch_update_collection(
    db.paragraphs_collection, 
    {'publication_id': pub_id}, 
    confidence_score, 
    "paragraphs"
)

total = dict_updated + phrases_updated + paragraphs_updated
print(f'\n✅ Done! Total updated: {total}')
