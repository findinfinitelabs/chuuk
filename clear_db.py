#!/usr/bin/env python3
"""Clear all records from the database"""
import sys
import time
sys.path.insert(0, '/Users/findinfinitelabs/DevApps/chuuk')
from src.database.db_factory import get_database_client, get_database_config

client = get_database_client()
config = get_database_config()
db = client[config['database_name']]
collection = db[config['container_name']]
pages_collection = db[config['pages_container']]

# Delete entries one at a time to avoid rate limiting
total_deleted = 0
while True:
    doc = collection.find_one({})
    if not doc:
        break
    try:
        collection.delete_one({'_id': doc['_id']})
        total_deleted += 1
        if total_deleted % 10 == 0:
            print(f'Deleted {total_deleted} entries...')
            time.sleep(0.3)  # Pause every 10 deletes
    except Exception as e:
        print(f'Rate limited, waiting... ({e})')
        time.sleep(2)

print(f'Total dictionary entries deleted: {total_deleted}')

# Delete pages one at a time
pages_deleted = 0
while True:
    doc = pages_collection.find_one({})
    if not doc:
        break
    try:
        pages_collection.delete_one({'_id': doc['_id']})
        pages_deleted += 1
        if pages_deleted % 5 == 0:
            print(f'Deleted {pages_deleted} pages...')
            time.sleep(0.3)
    except Exception as e:
        print(f'Rate limited on pages, waiting... ({e})')
        time.sleep(2)

print(f'Total pages deleted: {pages_deleted}')
print('Database cleared successfully!')
