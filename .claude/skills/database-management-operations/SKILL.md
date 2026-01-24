---
name: database-management-operations
description: Specialized database operations for Chuukese language data including dictionary management, phrase collections, translation pairs, and linguistic metadata. Supports Azure Cosmos DB with MongoDB API and local MongoDB. Use when working with Chuukese language databases, managing translation data, or performing database operations on linguistic datasets.
---

# Database Management Operations

## Overview

A specialized skill for managing database operations specific to Chuukese language data, including dictionary entries, phrase collections, translation pairs, and linguistic metadata. Designed to handle the unique requirements of low-resource language data management with proper accent character support and cultural context preservation.

**Primary Database**: Azure Cosmos DB with MongoDB API (production)
**Alternative**: Local MongoDB or SQLite (development)

## Capabilities

- **Dictionary Data Management**: CRUD operations for Chuukese-English dictionary entries
- **Phrase Collection Management**: Handle grouped phrases and contextual expressions
- **Translation Pair Operations**: Manage bidirectional translation relationships
- **Linguistic Metadata Handling**: Store and retrieve grammatical, cultural, and phonetic information
- **Unicode Support**: Proper handling of Chuukese accented characters in database operations
- **Search and Filtering**: Advanced search capabilities with fuzzy matching and cultural context
- **Cosmos DB Optimization**: RU-efficient queries and proper indexing strategies
- **Connection Pooling**: Managed connections for production workloads

## Database Configuration

### Environment Setup

```python
# .env configuration for database
DB_TYPE=cosmos  # or 'mongodb' or 'sqlite'
COSMOS_DB_URI=mongodb://your-account:your-key@your-account.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb
COSMOS_DB_KEY=your-primary-key
COSMOS_DB_NAME=chuuk-dictionary
```

### Database Factory Pattern

```python
# src/database/db_factory.py
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import logging

logger = logging.getLogger(__name__)

class DatabaseFactory:
    """Factory for creating database connections based on environment"""
    
    @staticmethod
    def get_database():
        db_type = os.getenv('DB_TYPE', 'cosmos')
        
        if db_type == 'cosmos':
            return DatabaseFactory._get_cosmos_db()
        elif db_type == 'mongodb':
            return DatabaseFactory._get_mongodb()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    @staticmethod
    def _get_cosmos_db():
        """Connect to Azure Cosmos DB with MongoDB API"""
        uri = os.getenv('COSMOS_DB_URI')
        db_name = os.getenv('COSMOS_DB_NAME', 'chuuk-dictionary')
        
        # Cosmos DB specific settings
        client = MongoClient(
            uri,
            maxPoolSize=50,
            minPoolSize=5,
            maxIdleTimeMS=30000,
            retryWrites=False,  # Cosmos DB doesn't support retryWrites
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=30000
        )
        
        # Verify connection
        try:
            client.admin.command('ping')
            logger.info("✅ Connected to Azure Cosmos DB")
        except ConnectionFailure as e:
            logger.error(f"❌ Failed to connect to Cosmos DB: {e}")
            raise
        
        return client[db_name]
    
    @staticmethod
    def _get_mongodb():
        """Connect to local MongoDB"""
        uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
        db_name = os.getenv('MONGODB_NAME', 'chuuk-dictionary')
        
        client = MongoClient(uri)
        return client[db_name]
```

## Core Components

### 1. Cosmos DB Collection Schema (MongoDB API)

```python
# Collection schemas for Cosmos DB with MongoDB API
# Note: Cosmos DB uses MongoDB wire protocol 4.0

DICTIONARY_SCHEMA = {
    "_id": "ObjectId",  # Auto-generated
    "chuukese_word": "string",  # Indexed, required
    "english_definition": "string",  # Required
    "pronunciation": "string",  # Optional, IPA
    "part_of_speech": "string",  # noun, verb, adjective, etc.
    "grammar_type": "string",  # base_word, phrase, etc.
    "cultural_context": "string",
    "difficulty_level": "string",  # beginner, intermediate, advanced
    "usage_frequency": "float",  # 0.0 to 1.0
    "word_family_id": "string",  # For related words
    "is_base_word": "boolean",
    "created_at": "datetime",
    "updated_at": "datetime"
}

PHRASES_SCHEMA = {
    "_id": "ObjectId",
    "chuukese_phrase": "string",
    "english_translation": "string",
    "context_category": "string",  # family, formal, casual, traditional
    "cultural_significance": "string",
    "usage_notes": "string",
    "source": "string",  # bible, brochure, dictionary
    "confidence_score": "float"
}

TRANSLATION_PAIRS_SCHEMA = {
    "_id": "ObjectId",
    "chuukese_text": "string",
    "english_text": "string",
    "quality_score": "float",
    "cultural_preservation_score": "float",
    "linguistic_accuracy_score": "float",
    "human_validated": "boolean",
    "validator_notes": "string",
    "source": "string"
}
```

### 2. Cosmos DB Indexing Strategy

```python
# Indexing for optimal RU consumption
def setup_cosmos_indexes(db):
    """Create indexes optimized for Cosmos DB"""
    
    # Dictionary collection indexes
    dictionary = db['dictionary']
    
    # Single field indexes
    dictionary.create_index('chuukese_word')
    dictionary.create_index('english_definition')
    dictionary.create_index('part_of_speech')
    dictionary.create_index('grammar_type')
    dictionary.create_index('is_base_word')
    
    # Compound index for common query patterns
    dictionary.create_index([
        ('grammar_type', 1),
        ('part_of_speech', 1)
    ])
    
    # Text index for full-text search (limited in Cosmos DB)
    # Use regex or application-level search instead
    
    # Phrases collection indexes
    phrases = db['phrases']
    phrases.create_index('chuukese_phrase')
    phrases.create_index('context_category')
    phrases.create_index('source')
    
    logger.info("✅ Cosmos DB indexes created")
```

### 3. Dictionary Database Manager (Cosmos DB / MongoDB)

```python
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, BulkWriteError
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import re
import logging

logger = logging.getLogger(__name__)

class DictionaryDB:
    """
    Database operations for Chuukese dictionary using Cosmos DB with MongoDB API
    """
    
    def __init__(self, db=None):
        if db is None:
            from .db_factory import DatabaseFactory
            db = DatabaseFactory.get_database()
        
        self.db = db
        self.dictionary = db['dictionary']
        self.phrases = db['phrases']
        self.translations = db['translation_pairs']
        self.pages = db['pages']
        
        # Accent normalization for searches
        self.accent_variants = {
            'a': ['á', 'à', 'ā', 'â', 'ă'],
            'e': ['é', 'è', 'ē', 'ê', 'ĕ'],
            'i': ['í', 'ì', 'ī', 'î', 'ĭ'],
            'o': ['ó', 'ò', 'ō', 'ô', 'ŏ'],
            'u': ['ú', 'ù', 'ū', 'û', 'ŭ']
        }
    
    # ==========================================================================
    # Dictionary Entry Operations
    # ==========================================================================
    
    def add_entry(self, entry_data: Dict[str, Any]) -> str:
        """Add new dictionary entry"""
        entry = {
            **entry_data,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        }
        
        result = self.dictionary.insert_one(entry)
        logger.info(f"Added entry: {entry_data.get('chuukese_word')}")
        return str(result.inserted_id)
    
    def get_entry(self, word: str) -> Optional[Dict]:
        """Get dictionary entry by Chuukese word"""
        return self.dictionary.find_one({'chuukese_word': word})
    
    def search_entries(
        self, 
        query: str, 
        search_type: str = 'fuzzy',
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """
        Search dictionary entries with accent-aware matching
        
        Args:
            query: Search term
            search_type: 'exact', 'fuzzy', 'partial', 'regex'
            limit: Maximum results (optimize for RU consumption)
            skip: Offset for pagination
        """
        if search_type == 'exact':
            cursor = self.dictionary.find(
                {'chuukese_word': query}
            ).skip(skip).limit(limit)
        
        elif search_type == 'fuzzy':
            # Create accent-insensitive regex pattern
            pattern = self._create_accent_pattern(query)
            cursor = self.dictionary.find({
                '$or': [
                    {'chuukese_word': {'$regex': pattern, '$options': 'i'}},
                    {'english_definition': {'$regex': pattern, '$options': 'i'}}
                ]
            }).skip(skip).limit(limit)
        
        elif search_type == 'partial':
            cursor = self.dictionary.find({
                '$or': [
                    {'chuukese_word': {'$regex': query, '$options': 'i'}},
                    {'english_definition': {'$regex': query, '$options': 'i'}}
                ]
            }).skip(skip).limit(limit)
        
        else:  # regex
            cursor = self.dictionary.find({
                'chuukese_word': {'$regex': query, '$options': 'i'}
            }).skip(skip).limit(limit)
        
        return list(cursor)
    
    def _create_accent_pattern(self, text: str) -> str:
        """Create regex pattern that matches accent variations"""
        pattern = ""
        for char in text.lower():
            if char in self.accent_variants:
                variants = ''.join(self.accent_variants[char])
                pattern += f"[{char}{variants}{char.upper()}{variants.upper()}]"
            else:
                pattern += re.escape(char)
        return pattern
    
    def update_entry(self, word: str, updates: Dict[str, Any]) -> bool:
        """Update dictionary entry"""
        updates['updated_at'] = datetime.now(timezone.utc)
        
        result = self.dictionary.update_one(
            {'chuukese_word': word},
            {'$set': updates}
        )
        return result.modified_count > 0
    
    def delete_entry(self, word: str) -> bool:
        """Delete dictionary entry"""
        result = self.dictionary.delete_one({'chuukese_word': word})
        return result.deleted_count > 0
    
    # ==========================================================================
    # Bulk Operations (RU-Optimized)
    # ==========================================================================
    
    def bulk_insert_entries(
        self, 
        entries: List[Dict], 
        batch_size: int = 100
    ) -> Dict[str, int]:
        """
        Bulk insert with batching to manage RU consumption
        
        Args:
            entries: List of entry dictionaries
            batch_size: Entries per batch (lower = less RU spike)
        """
        results = {'inserted': 0, 'failed': 0, 'errors': []}
        
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            
            # Add timestamps
            for entry in batch:
                entry['created_at'] = datetime.now(timezone.utc)
                entry['updated_at'] = datetime.now(timezone.utc)
            
            try:
                result = self.dictionary.insert_many(batch, ordered=False)
                results['inserted'] += len(result.inserted_ids)
            except BulkWriteError as e:
                results['inserted'] += e.details.get('nInserted', 0)
                results['failed'] += len(e.details.get('writeErrors', []))
                results['errors'].extend(e.details.get('writeErrors', []))
        
        logger.info(f"Bulk insert: {results['inserted']} inserted, {results['failed']} failed")
        return results
    
    # ==========================================================================
    # Aggregation Queries (RU-Optimized)
    # ==========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get collection statistics with efficient aggregation"""
        
        # Use aggregation pipeline for efficient counting
        stats_pipeline = [
            {
                '$facet': {
                    'total': [{'$count': 'count'}],
                    'by_grammar_type': [
                        {'$group': {'_id': '$grammar_type', 'count': {'$sum': 1}}}
                    ],
                    'by_part_of_speech': [
                        {'$group': {'_id': '$part_of_speech', 'count': {'$sum': 1}}}
                    ],
                    'base_words': [
                        {'$match': {'is_base_word': True}},
                        {'$count': 'count'}
                    ]
                }
            }
        ]
        
        result = list(self.dictionary.aggregate(stats_pipeline))
        
        if result:
            data = result[0]
            return {
                'total_entries': data['total'][0]['count'] if data['total'] else 0,
                'grammar_types': {
                    item['_id']: item['count'] 
                    for item in data['by_grammar_type'] if item['_id']
                },
                'parts_of_speech': {
                    item['_id']: item['count'] 
                    for item in data['by_part_of_speech'] if item['_id']
                },
                'base_words': data['base_words'][0]['count'] if data['base_words'] else 0
            }
        
        return {}
    
    def get_distinct_values(self, field: str) -> List[str]:
        """Get distinct values for a field (cached for performance)"""
        return self.dictionary.distinct(field)
    
    # ==========================================================================
    # Phrase Operations
    # ==========================================================================
    
    def add_phrase(self, phrase_data: Dict[str, Any]) -> str:
        """Add phrase entry"""
        phrase = {
            **phrase_data,
            'created_at': datetime.now(timezone.utc)
        }
        result = self.phrases.insert_one(phrase)
        return str(result.inserted_id)
    
    def search_phrases(
        self, 
        query: str, 
        context_filter: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Search phrases with optional context filter"""
        
        filter_query = {
            '$or': [
                {'chuukese_phrase': {'$regex': query, '$options': 'i'}},
                {'english_translation': {'$regex': query, '$options': 'i'}}
            ]
        }
        
        if context_filter:
            filter_query['context_category'] = context_filter
        
        return list(self.phrases.find(filter_query).limit(limit))
    
    # ==========================================================================
    # Translation Pair Operations
    # ==========================================================================
    
    def add_translation_pair(self, pair_data: Dict[str, Any]) -> str:
        """Add translation pair with quality metrics"""
        pair = {
            **pair_data,
            'created_at': datetime.now(timezone.utc)
        }
        result = self.translations.insert_one(pair)
        return str(result.inserted_id)
    
    def get_high_quality_translations(
        self, 
        min_score: float = 0.8,
        limit: int = 100
    ) -> List[Dict]:
        """Get translations above quality threshold"""
        return list(self.translations.find({
            'quality_score': {'$gte': min_score}
        }).sort('quality_score', DESCENDING).limit(limit))
    
    def get_translations_for_validation(self, limit: int = 50) -> List[Dict]:
        """Get unvalidated translations for human review"""
        return list(self.translations.find({
            'human_validated': {'$ne': True},
            'quality_score': {'$gte': 0.5}
        }).limit(limit))
```

### 4. Database Operations Manager (Legacy SQLAlchemy Support)

```python
from sqlalchemy import create_engine, or_, and_, func
from sqlalchemy.orm import sessionmaker
import json
import re
from difflib import get_close_matches

class ChuukeseDatabaseManager:
    def __init__(self, database_url):
        self.engine = create_engine(database_url, echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Initialize text normalization for searches
        self.accent_variants = {
            'a': ['á', 'à', 'ā', 'â', 'ă'],
            'e': ['é', 'è', 'ē', 'ê', 'ĕ'],
            'i': ['í', 'ì', 'ī', 'î', 'ĭ'],
            'o': ['ó', 'ò', 'ō', 'ô', 'ŏ'],
            'u': ['ú', 'ù', 'ū', 'û', 'ŭ']
        }
    
    def normalize_for_search(self, text):
        """Normalize text for accent-insensitive searching"""
        normalized = text.lower()
        for base_char, variants in self.accent_variants.items():
            for variant in variants:
                normalized = normalized.replace(variant, base_char)
        return normalized
    
    def create_search_pattern(self, search_term):
        """Create fuzzy search pattern that handles accent variations"""
        pattern = ""
        for char in search_term.lower():
            if char in self.accent_variants:
                # Create character class for accent variations
                variants = ''.join(self.accent_variants[char])
                pattern += f"[{char}{variants}]"
            else:
                pattern += char
        return pattern

    # Dictionary Entry Operations
    def add_dictionary_entry(self, chuukese_word, english_definition, **kwargs):
        """Add new dictionary entry with optional metadata"""
        entry = DictionaryEntry(
            chuukese_word=chuukese_word,
            english_definition=english_definition,
            pronunciation=kwargs.get('pronunciation'),
            part_of_speech=kwargs.get('part_of_speech'),
            cultural_context=kwargs.get('cultural_context'),
            difficulty_level=kwargs.get('difficulty_level', 'intermediate'),
            usage_frequency=kwargs.get('usage_frequency', 0.5)
        )
        
        self.session.add(entry)
        self.session.commit()
        return entry.id
    
    def search_dictionary_entries(self, search_term, search_type='fuzzy', limit=10):
        """Search dictionary entries with accent-aware fuzzy matching"""
        if search_type == 'exact':
            results = self.session.query(DictionaryEntry).filter(
                or_(
                    DictionaryEntry.chuukese_word == search_term,
                    DictionaryEntry.english_definition.contains(search_term)
                )
            ).limit(limit).all()
        
        elif search_type == 'fuzzy':
            # Create accent-insensitive pattern
            pattern = self.create_search_pattern(search_term)
            results = self.session.query(DictionaryEntry).filter(
                or_(
                    DictionaryEntry.chuukese_word.op('~*')(pattern),
                    DictionaryEntry.english_definition.op('~*')(pattern)
                )
            ).limit(limit).all()
        
        elif search_type == 'partial':
            results = self.session.query(DictionaryEntry).filter(
                or_(
                    DictionaryEntry.chuukese_word.contains(search_term),
                    DictionaryEntry.english_definition.contains(search_term)
                )
            ).limit(limit).all()
        
        return results
    
    def get_entries_by_cultural_context(self, context_category):
        """Get entries filtered by cultural context"""
        return self.session.query(DictionaryEntry).filter(
            DictionaryEntry.cultural_context.contains(context_category)
        ).all()

    # Phrase Operations
    def add_phrase_entry(self, chuukese_phrase, english_translation, context_category=None, **kwargs):
        """Add phrase entry with cultural context"""
        phrase = PhraseEntry(
            chuukese_phrase=chuukese_phrase,
            english_translation=english_translation,
            context_category=context_category,
            cultural_significance=kwargs.get('cultural_significance'),
            usage_notes=kwargs.get('usage_notes'),
            dictionary_entry_id=kwargs.get('dictionary_entry_id')
        )
        
        self.session.add(phrase)
        self.session.commit()
        return phrase.id
    
    def search_phrases(self, search_term, context_filter=None):
        """Search phrases with optional context filtering"""
        query = self.session.query(PhraseEntry)
        
        # Apply text search
        pattern = self.create_search_pattern(search_term)
        query = query.filter(
            or_(
                PhraseEntry.chuukese_phrase.op('~*')(pattern),
                PhraseEntry.english_translation.op('~*')(pattern)
            )
        )
        
        # Apply context filter if provided
        if context_filter:
            query = query.filter(PhraseEntry.context_category == context_filter)
        
        return query.all()

    # Translation Pair Operations
    def add_translation_pair(self, chuukese_text, english_text, quality_scores=None, **kwargs):
        """Add translation pair with quality metrics"""
        translation = TranslationPair(
            chuukese_text=chuukese_text,
            english_text=english_text,
            quality_score=quality_scores.get('overall_score', 0.0) if quality_scores else 0.0,
            cultural_preservation_score=quality_scores.get('cultural_score', 0.0) if quality_scores else 0.0,
            linguistic_accuracy_score=quality_scores.get('linguistic_score', 0.0) if quality_scores else 0.0,
            human_validated=kwargs.get('human_validated', False),
            validator_notes=kwargs.get('validator_notes'),
            chuukese_entry_id=kwargs.get('chuukese_entry_id')
        )
        
        self.session.add(translation)
        self.session.commit()
        return translation.id
    
    def get_high_quality_translations(self, min_quality_score=0.8):
        """Get translations above quality threshold"""
        return self.session.query(TranslationPair).filter(
            TranslationPair.quality_score >= min_quality_score
        ).all()
    
    def get_translations_for_validation(self, limit=50):
        """Get translations that need human validation"""
        return self.session.query(TranslationPair).filter(
            and_(
                TranslationPair.human_validated == False,
                TranslationPair.quality_score > 0.5  # Basic quality threshold
            )
        ).limit(limit).all()

    # Advanced Search and Analytics
    def get_vocabulary_statistics(self):
        """Get comprehensive vocabulary statistics"""
        stats = {}
        
        # Total counts
        stats['total_dictionary_entries'] = self.session.query(DictionaryEntry).count()
        stats['total_phrases'] = self.session.query(PhraseEntry).count()
        stats['total_translation_pairs'] = self.session.query(TranslationPair).count()
        
        # Part of speech distribution
        pos_counts = self.session.query(
            DictionaryEntry.part_of_speech,
            func.count(DictionaryEntry.id)
        ).group_by(DictionaryEntry.part_of_speech).all()
        stats['part_of_speech_distribution'] = {pos: count for pos, count in pos_counts}
        
        # Difficulty level distribution
        difficulty_counts = self.session.query(
            DictionaryEntry.difficulty_level,
            func.count(DictionaryEntry.id)
        ).group_by(DictionaryEntry.difficulty_level).all()
        stats['difficulty_distribution'] = {level: count for level, count in difficulty_counts}
        
        # Cultural context categories
        context_counts = self.session.query(
            PhraseEntry.context_category,
            func.count(PhraseEntry.id)
        ).group_by(PhraseEntry.context_category).all()
        stats['cultural_context_distribution'] = {ctx: count for ctx, count in context_counts if ctx}
        
        # Quality metrics
        avg_quality = self.session.query(func.avg(TranslationPair.quality_score)).scalar()
        stats['average_translation_quality'] = float(avg_quality) if avg_quality else 0.0
        
        validated_count = self.session.query(TranslationPair).filter(
            TranslationPair.human_validated == True
        ).count()
        stats['human_validated_translations'] = validated_count
        
        return stats
    
    def find_missing_translations(self):
        """Identify dictionary entries without corresponding translation pairs"""
        entries_with_translations = self.session.query(TranslationPair.chuukese_entry_id).distinct()
        missing = self.session.query(DictionaryEntry).filter(
            ~DictionaryEntry.id.in_(entries_with_translations)
        ).all()
        
        return missing
    
    def get_cultural_term_coverage(self):
        """Analyze coverage of culturally significant terms"""
        cultural_entries = self.session.query(DictionaryEntry).filter(
            DictionaryEntry.cultural_context.isnot(None)
        ).all()
        
        coverage_report = {
            'total_cultural_terms': len(cultural_entries),
            'categories': {},
            'high_importance_missing': []
        }
        
        # Analyze by cultural categories (this would be expanded based on actual categories)
        for entry in cultural_entries:
            # Extract categories from cultural_context (assuming JSON or comma-separated)
            context = entry.cultural_context or ""
            categories = [cat.strip() for cat in context.split(',')]
            
            for category in categories:
                if category:
                    if category not in coverage_report['categories']:
                        coverage_report['categories'][category] = 0
                    coverage_report['categories'][category] += 1
        
        return coverage_report

    # Batch Operations
    def import_dictionary_batch(self, entries_data):
        """Import multiple dictionary entries from structured data"""
        import_results = {
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for entry_data in entries_data:
            try:
                self.add_dictionary_entry(
                    chuukese_word=entry_data['chuukese_word'],
                    english_definition=entry_data['english_definition'],
                    pronunciation=entry_data.get('pronunciation'),
                    part_of_speech=entry_data.get('part_of_speech'),
                    cultural_context=entry_data.get('cultural_context'),
                    difficulty_level=entry_data.get('difficulty_level', 'intermediate')
                )
                import_results['successful'] += 1
                
            except Exception as e:
                import_results['failed'] += 1
                import_results['errors'].append({
                    'entry': entry_data,
                    'error': str(e)
                })
        
        return import_results
    
    def export_dictionary_data(self, format_type='json', filters=None):
        """Export dictionary data in specified format"""
        query = self.session.query(DictionaryEntry)
        
        # Apply filters if provided
        if filters:
            if 'part_of_speech' in filters:
                query = query.filter(DictionaryEntry.part_of_speech == filters['part_of_speech'])
            if 'difficulty_level' in filters:
                query = query.filter(DictionaryEntry.difficulty_level == filters['difficulty_level'])
            if 'cultural_context' in filters:
                query = query.filter(DictionaryEntry.cultural_context.contains(filters['cultural_context']))
        
        entries = query.all()
        
        if format_type == 'json':
            return [
                {
                    'id': entry.id,
                    'chuukese_word': entry.chuukese_word,
                    'english_definition': entry.english_definition,
                    'pronunciation': entry.pronunciation,
                    'part_of_speech': entry.part_of_speech,
                    'cultural_context': entry.cultural_context,
                    'difficulty_level': entry.difficulty_level,
                    'usage_frequency': entry.usage_frequency
                }
                for entry in entries
            ]
        
        elif format_type == 'tsv':
            output = "chuukese_word\tenglish_definition\tpronunciation\tpart_of_speech\tcultural_context\tdifficulty_level\n"
            for entry in entries:
                output += f"{entry.chuukese_word}\t{entry.english_definition}\t{entry.pronunciation or ''}\t{entry.part_of_speech or ''}\t{entry.cultural_context or ''}\t{entry.difficulty_level}\n"
            return output
        
        return entries

    # Database Maintenance
    def cleanup_duplicates(self):
        """Remove duplicate entries based on Chuukese word"""
        # Find duplicates
        duplicates = self.session.query(
            DictionaryEntry.chuukese_word,
            func.count(DictionaryEntry.id)
        ).group_by(DictionaryEntry.chuukese_word).having(
            func.count(DictionaryEntry.id) > 1
        ).all()
        
        removed_count = 0
        for word, count in duplicates:
            entries = self.session.query(DictionaryEntry).filter(
                DictionaryEntry.chuukese_word == word
            ).order_by(DictionaryEntry.created_at.desc()).all()
            
            # Keep the newest, remove others
            for entry in entries[1:]:
                self.session.delete(entry)
                removed_count += 1
        
        self.session.commit()
        return removed_count
    
    def update_usage_frequencies(self, usage_data):
        """Update usage frequency scores based on corpus analysis"""
        updated_count = 0
        
        for word, frequency in usage_data.items():
            entry = self.session.query(DictionaryEntry).filter(
                DictionaryEntry.chuukese_word == word
            ).first()
            
            if entry:
                entry.usage_frequency = frequency
                updated_count += 1
        
        self.session.commit()
        return updated_count
    
    def __del__(self):
        """Cleanup database connection"""
        if hasattr(self, 'session'):
            self.session.close()
```

## Usage Examples

### Basic Database Operations

```python
# Initialize database manager
db = ChuukeseDatabaseManager('sqlite:///chuukese_dictionary.db')

# Add dictionary entry
entry_id = db.add_dictionary_entry(
    chuukese_word="chomong",
    english_definition="to help, assist",
    pronunciation="tʃomoŋ",
    part_of_speech="verb",
    cultural_context="community cooperation, traditional value",
    difficulty_level="beginner"
)

# Search with accent handling
results = db.search_dictionary_entries("chomong", search_type='fuzzy')
```

### Advanced Search Operations

```python
# Search by cultural context
cultural_terms = db.get_entries_by_cultural_context("traditional")

# Find high-quality translations
quality_translations = db.get_high_quality_translations(min_quality_score=0.85)

# Get comprehensive statistics
stats = db.get_vocabulary_statistics()
print(f"Total entries: {stats['total_dictionary_entries']}")
```

### Batch Import and Export

```python
# Import from structured data
dictionary_data = [
    {
        'chuukese_word': 'ngang',
        'english_definition': 'fish',
        'part_of_speech': 'noun',
        'difficulty_level': 'beginner'
    },
    # ... more entries
]

import_results = db.import_dictionary_batch(dictionary_data)
print(f"Imported {import_results['successful']} entries")

# Export filtered data
exported_data = db.export_dictionary_data(
    format_type='json',
    filters={'part_of_speech': 'noun'}
)
```

## Best Practices

### Database Design

1. **Unicode support**: Ensure proper UTF-8 encoding for accented characters
2. **Indexing strategy**: Index frequently searched fields (words, categories)
3. **Normalization**: Balance between normalization and query performance
4. **Backup strategy**: Regular backups of linguistic data

### Search and Retrieval

1. **Accent handling**: Implement fuzzy search for accent variations
2. **Cultural context**: Index and search by cultural significance
3. **Performance optimization**: Use appropriate indexes and query optimization
4. **Flexible searching**: Support multiple search strategies (exact, partial, fuzzy)

### Data Quality

1. **Validation rules**: Implement data validation for consistency
2. **Duplicate detection**: Regular cleanup of duplicate entries
3. **Quality metrics**: Track and maintain translation quality scores
4. **Human validation**: Workflow for community review and validation

## Dependencies

- `sqlalchemy`: Database ORM and operations
- `re`: Regular expression pattern matching
- `difflib`: Fuzzy string matching
- `json`: Data serialization
- `datetime`: Timestamp management

## Validation Criteria

A successful implementation should:

- ✅ Handle Chuukese accented characters correctly in all operations
- ✅ Provide efficient search with cultural context awareness
- ✅ Support batch import/export operations
- ✅ Include comprehensive quality metrics and analytics
- ✅ Handle duplicate detection and cleanup
- ✅ Support multiple data export formats
- ✅ Provide database maintenance and optimization features
