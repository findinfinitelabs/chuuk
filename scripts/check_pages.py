#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.dictionary_db import DictionaryDB

db = DictionaryDB()
pages = list(db.pages_collection.find().limit(5))
print(f'Total pages in DB: {db.pages_collection.count_documents({})}')
for p in pages:
    print(f'  - {p.get("filename")} (Pub: {p.get("publication_id")}, Page: {p.get("page_number")})')
