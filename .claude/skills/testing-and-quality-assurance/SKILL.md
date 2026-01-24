---
name: testing-and-quality-assurance
description: Testing patterns for Python Flask APIs, ML translation models, and database operations. Use when writing tests, setting up test fixtures, or validating translation accuracy for the Chuuk Dictionary application.
---

# Testing and Quality Assurance

## Overview

Comprehensive testing strategies for the Chuuk Dictionary application including API endpoint testing, ML model validation, database operations, and translation accuracy assessment.

## Test Structure

```text
chuuk/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_api/
│   │   ├── test_dictionary.py
│   │   ├── test_translation.py
│   │   └── test_auth.py
│   ├── test_database/
│   │   ├── test_dictionary_db.py
│   │   └── test_cosmos_db.py
│   ├── test_translation/
│   │   ├── test_helsinki.py
│   │   └── test_accuracy.py
│   └── test_ocr/
│       └── test_processor.py
├── test_results/
└── pytest.ini
```

## pytest Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --color=yes
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests requiring external services
    ml: marks tests involving ML models
filterwarnings =
    ignore::DeprecationWarning
    ignore::UserWarning
```

### conftest.py - Shared Fixtures

```python
"""Shared test fixtures for Chuuk Dictionary tests."""
import os
import pytest
from flask import Flask
from unittest.mock import MagicMock, patch

# Set test environment before imports
os.environ['FLASK_ENV'] = 'testing'
os.environ['COSMOS_CONNECTION_STRING'] = 'test://localhost:27017'

from app import app as flask_app


@pytest.fixture(scope='session')
def app():
    """Create test Flask application."""
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })
    yield flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client."""
    with client.session_transaction() as sess:
        sess['user_email'] = 'test@example.com'
        sess['session_id'] = 'test-session-id'
    return client


@pytest.fixture
def mock_db():
    """Mock database connection."""
    mock = MagicMock()
    mock.search_entries.return_value = [
        {
            '_id': 'test123',
            'chuukese_word': 'ran',
            'english_definition': 'day',
            'part_of_speech': 'noun'
        }
    ]
    mock.get_entry.return_value = {
        '_id': 'test123',
        'chuukese_word': 'ran',
        'english_definition': 'day'
    }
    return mock


@pytest.fixture
def sample_entries():
    """Sample dictionary entries for testing."""
    return [
        {
            'chuukese_word': 'ran',
            'english_definition': 'day',
            'part_of_speech': 'noun',
            'example_sentence': 'Ewe ran a mwoch.',
            'example_translation': 'The day is good.'
        },
        {
            'chuukese_word': 'meinisin',
            'english_definition': 'everything, all things',
            'part_of_speech': 'pronoun'
        },
        {
            'chuukese_word': 'fen',
            'english_definition': 'stone, rock',
            'part_of_speech': 'noun'
        }
    ]


@pytest.fixture
def mock_translator():
    """Mock Helsinki translator."""
    mock = MagicMock()
    mock.translate.return_value = 'translated text'
    mock.is_available = True
    return mock


@pytest.fixture
def translation_pairs():
    """Known good translation pairs for accuracy testing."""
    return [
        ('ran', 'day'),
        ('pwe', 'because'),
        ('Kot', 'God'),
        ('aramas', 'person, people'),
        ('neni', 'place, location'),
    ]
```

## API Testing

### test_dictionary.py

```python
"""Tests for dictionary API endpoints."""
import pytest
import json
from unittest.mock import patch


class TestDictionarySearch:
    """Test dictionary search endpoint."""
    
    def test_search_empty_query(self, client):
        """Test search with empty query returns empty results."""
        response = client.get('/api/dictionary/search?query=')
        data = response.get_json()
        
        assert response.status_code == 200
        assert data['entries'] == []
        assert data['total'] == 0
    
    def test_search_valid_query(self, client, mock_db):
        """Test search with valid query returns results."""
        with patch('app.db', mock_db):
            response = client.get('/api/dictionary/search?query=ran')
            data = response.get_json()
        
        assert response.status_code == 200
        assert len(data['entries']) > 0
        assert data['query'] == 'ran'
    
    def test_search_with_limit(self, client, mock_db):
        """Test search respects limit parameter."""
        with patch('app.db', mock_db):
            response = client.get('/api/dictionary/search?query=test&limit=10')
        
        assert response.status_code == 200
        mock_db.search_entries.assert_called_with(
            'test', search_type='fuzzy', limit=10
        )
    
    def test_search_type_parameter(self, client, mock_db):
        """Test search type parameter is passed correctly."""
        with patch('app.db', mock_db):
            response = client.get('/api/dictionary/search?query=test&type=exact')
        
        mock_db.search_entries.assert_called_with(
            'test', search_type='exact', limit=50
        )


class TestDictionaryEntry:
    """Test single entry endpoints."""
    
    def test_get_entry_exists(self, client, mock_db):
        """Test getting existing entry."""
        with patch('app.db', mock_db):
            response = client.get('/api/dictionary/entry/ran')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['chuukese_word'] == 'ran'
    
    def test_get_entry_not_found(self, client, mock_db):
        """Test getting non-existent entry."""
        mock_db.get_entry.return_value = None
        
        with patch('app.db', mock_db):
            response = client.get('/api/dictionary/entry/nonexistent')
        
        assert response.status_code == 404
    
    def test_create_entry_unauthenticated(self, client):
        """Test creating entry without authentication fails."""
        response = client.post(
            '/api/dictionary/entry',
            json={'chuukese_word': 'test', 'english_definition': 'test'}
        )
        
        assert response.status_code == 401
    
    def test_create_entry_authenticated(self, authenticated_client, mock_db):
        """Test creating entry with authentication succeeds."""
        mock_db.add_entry.return_value = 'new-entry-id'
        
        with patch('app.db', mock_db):
            response = authenticated_client.post(
                '/api/dictionary/entry',
                json={'chuukese_word': 'test', 'english_definition': 'test word'}
            )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data['id'] == 'new-entry-id'
    
    def test_create_entry_missing_fields(self, authenticated_client):
        """Test creating entry with missing required fields fails."""
        response = authenticated_client.post(
            '/api/dictionary/entry',
            json={'chuukese_word': 'test'}  # Missing english_definition
        )
        
        assert response.status_code == 400
        assert 'english_definition' in response.get_json()['error']
```

### test_translation.py

```python
"""Tests for translation API endpoints."""
import pytest
from unittest.mock import patch, MagicMock


class TestTranslation:
    """Test translation endpoints."""
    
    def test_translate_empty_text(self, client):
        """Test translation with empty text fails."""
        response = client.post('/api/translate', json={'text': ''})
        
        assert response.status_code == 400
        assert 'No text provided' in response.get_json()['error']
    
    def test_translate_invalid_direction(self, client):
        """Test translation with invalid direction fails."""
        response = client.post('/api/translate', json={
            'text': 'hello',
            'direction': 'invalid'
        })
        
        assert response.status_code == 400
        assert 'Invalid direction' in response.get_json()['error']
    
    def test_translate_chk_to_en(self, client, mock_translator):
        """Test Chuukese to English translation."""
        mock_translator.translate.return_value = 'day'
        
        with patch('app.get_translator', return_value=mock_translator):
            response = client.post('/api/translate', json={
                'text': 'ran',
                'direction': 'chk_to_en'
            })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['original'] == 'ran'
        assert data['translated'] == 'day'
        assert data['direction'] == 'chk_to_en'
    
    def test_translate_en_to_chk(self, client, mock_translator):
        """Test English to Chuukese translation."""
        mock_translator.translate.return_value = 'ran'
        
        with patch('app.get_translator', return_value=mock_translator):
            response = client.post('/api/translate', json={
                'text': 'day',
                'direction': 'en_to_chk'
            })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['translated'] == 'ran'
    
    def test_translate_batch(self, client, mock_translator):
        """Test batch translation."""
        mock_translator.translate.side_effect = ['day', 'stone']
        
        with patch('app.get_translator', return_value=mock_translator):
            response = client.post('/api/translate/batch', json={
                'texts': ['ran', 'fen'],
                'direction': 'chk_to_en'
            })
        
        assert response.status_code == 200
        results = response.get_json()['results']
        assert len(results) == 2
        assert all(r['success'] for r in results)
```

## Translation Accuracy Testing

### test_accuracy.py

```python
"""Translation accuracy tests using reference translations."""
import pytest
from sacrebleu.metrics import CHRF
from typing import List, Tuple


class TranslationAccuracyTest:
    """Test translation accuracy with known pairs."""
    
    @pytest.fixture
    def chrf_scorer(self):
        """Initialize chrF scorer."""
        return CHRF()
    
    @pytest.fixture
    def reference_translations(self) -> List[Tuple[str, str, str]]:
        """Known good translations: (source, reference, direction)."""
        return [
            ('ran', 'day', 'chk_to_en'),
            ('Kot', 'God', 'chk_to_en'),
            ('pwe', 'because', 'chk_to_en'),
            ('aramas', 'person', 'chk_to_en'),
            ('fen', 'stone', 'chk_to_en'),
            ('day', 'ran', 'en_to_chk'),
            ('God', 'Kot', 'en_to_chk'),
            ('water', 'kinikini', 'en_to_chk'),
        ]
    
    @pytest.mark.ml
    @pytest.mark.slow
    def test_single_word_accuracy(self, reference_translations, chrf_scorer):
        """Test translation accuracy on single words."""
        from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
        
        translator = HelsinkiChuukeseTranslator()
        translator.setup_models()
        
        scores = []
        failed = []
        
        for source, reference, direction in reference_translations:
            hypothesis = translator.translate(source, direction)
            score = chrf_scorer.sentence_score(hypothesis, [reference])
            scores.append(score.score)
            
            if score.score < 50:  # Less than 50% chrF is concerning
                failed.append({
                    'source': source,
                    'expected': reference,
                    'got': hypothesis,
                    'score': score.score
                })
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Assert reasonable accuracy
        assert avg_score > 40, f"Average chrF score {avg_score:.1f} below threshold"
        
        # Log failures for analysis
        if failed:
            print(f"\nFailed translations ({len(failed)}):")
            for f in failed:
                print(f"  {f['source']} -> expected '{f['expected']}' got '{f['got']}' (score: {f['score']:.1f})")
    
    @pytest.mark.ml
    @pytest.mark.slow
    def test_sentence_translation(self):
        """Test full sentence translation."""
        from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
        
        translator = HelsinkiChuukeseTranslator()
        translator.setup_models()
        
        test_sentences = [
            {
                'source': 'Ewe Kot a kamour Adamu seni pwunupwun.',
                'reference': 'God created Adam from dust.',
                'direction': 'chk_to_en'
            }
        ]
        
        for test in test_sentences:
            result = translator.translate(test['source'], test['direction'])
            assert result is not None
            assert len(result) > 0
            # Log for manual review
            print(f"\nSource: {test['source']}")
            print(f"Reference: {test['reference']}")
            print(f"Result: {result}")


class TestModelComparison:
    """Compare model versions."""
    
    @pytest.mark.ml
    @pytest.mark.slow
    def test_finetuned_vs_base(self, translation_pairs, chrf_scorer):
        """Compare fine-tuned model against base model."""
        # Load both models
        from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
        
        finetuned = HelsinkiChuukeseTranslator(
            model_path='models/helsinki-chuukese_chuukese_to_english'
        )
        finetuned.setup_models()
        
        # Compare on test set
        finetuned_scores = []
        
        for source, reference in translation_pairs:
            hyp = finetuned.translate(source, 'chk_to_en')
            score = chrf_scorer.sentence_score(hyp, [reference])
            finetuned_scores.append(score.score)
        
        avg_finetuned = sum(finetuned_scores) / len(finetuned_scores)
        
        # Fine-tuned should perform reasonably well
        assert avg_finetuned > 30, f"Fine-tuned model score {avg_finetuned:.1f} too low"
        
        print(f"\nFine-tuned model average chrF: {avg_finetuned:.2f}")
```

## Database Testing

### test_dictionary_db.py

```python
"""Tests for database operations."""
import pytest
from unittest.mock import MagicMock, patch


class TestDictionaryDB:
    """Test DictionaryDB operations."""
    
    @pytest.fixture
    def mock_collection(self):
        """Mock MongoDB collection."""
        return MagicMock()
    
    @pytest.fixture
    def db_instance(self, mock_collection):
        """Create DictionaryDB with mocked connection."""
        with patch('src.database.dictionary_db.MongoClient'):
            from src.database.dictionary_db import DictionaryDB
            db = DictionaryDB.__new__(DictionaryDB)
            db.collection = mock_collection
            return db
    
    def test_search_entries_exact(self, db_instance, mock_collection):
        """Test exact search."""
        mock_collection.find.return_value = [
            {'chuukese_word': 'ran', 'english_definition': 'day'}
        ]
        
        results = db_instance.search_entries('ran', search_type='exact')
        
        mock_collection.find.assert_called_once()
        assert len(results) == 1
    
    def test_search_entries_fuzzy(self, db_instance, mock_collection):
        """Test fuzzy search with regex."""
        mock_collection.find.return_value = [
            {'chuukese_word': 'ran', 'english_definition': 'day'},
            {'chuukese_word': 'rana', 'english_definition': 'branch'}
        ]
        
        results = db_instance.search_entries('ran', search_type='fuzzy')
        
        # Should use regex pattern
        call_args = mock_collection.find.call_args[0][0]
        assert '$regex' in str(call_args) or 'ran' in str(call_args)
    
    def test_add_entry(self, db_instance, mock_collection):
        """Test adding new entry."""
        mock_collection.insert_one.return_value.inserted_id = 'new-id'
        
        entry = {
            'chuukese_word': 'test',
            'english_definition': 'test word'
        }
        
        result = db_instance.add_entry(entry)
        
        mock_collection.insert_one.assert_called_once()
        assert result == 'new-id'
    
    def test_update_entry(self, db_instance, mock_collection):
        """Test updating entry."""
        mock_collection.update_one.return_value.modified_count = 1
        
        result = db_instance.update_entry('ran', {'english_definition': 'updated'})
        
        mock_collection.update_one.assert_called_once()
        assert result is True
    
    def test_delete_entry(self, db_instance, mock_collection):
        """Test deleting entry."""
        mock_collection.delete_one.return_value.deleted_count = 1
        
        result = db_instance.delete_entry('ran')
        
        mock_collection.delete_one.assert_called_once()
        assert result is True


class TestBulkOperations:
    """Test bulk database operations."""
    
    @pytest.fixture
    def db_instance(self):
        """Create DictionaryDB with mocked connection."""
        with patch('src.database.dictionary_db.MongoClient'):
            from src.database.dictionary_db import DictionaryDB
            db = DictionaryDB.__new__(DictionaryDB)
            db.collection = MagicMock()
            return db
    
    def test_bulk_insert(self, db_instance):
        """Test bulk insert operation."""
        entries = [
            {'chuukese_word': 'word1', 'english_definition': 'def1'},
            {'chuukese_word': 'word2', 'english_definition': 'def2'},
        ]
        
        db_instance.collection.insert_many.return_value.inserted_ids = ['id1', 'id2']
        
        result = db_instance.bulk_insert(entries)
        
        assert len(result) == 2
```

## Running Tests

### Common Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api/test_dictionary.py

# Run specific test class
pytest tests/test_api/test_dictionary.py::TestDictionarySearch

# Run specific test
pytest tests/test_api/test_dictionary.py::TestDictionarySearch::test_search_valid_query

# Skip slow/ML tests
pytest -m "not slow and not ml"

# Run only integration tests
pytest -m integration

# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s
```

### Test Coverage

```bash
# Install coverage
pip install pytest-cov

# Generate HTML report
pytest --cov=src --cov=app --cov-report=html

# Open report
open htmlcov/index.html
```

## Best Practices

### Test Organization

1. **One assertion per test** when possible
2. **Descriptive test names**: `test_search_returns_empty_when_no_matches`
3. **Use fixtures** for common setup
4. **Mark slow tests** with `@pytest.mark.slow`

### Mocking Guidelines

1. **Mock external dependencies**: Database, APIs, file system
2. **Use patch decorators** for cleaner code
3. **Don't over-mock**: Test real behavior when practical
4. **Mock at boundaries**: Mock the interface, not internals

### ML Testing

1. **Use reference translations** with known good output
2. **Test on representative samples** not entire datasets
3. **Set reasonable thresholds** for accuracy assertions
4. **Log failures** for manual review

## Dependencies

- `pytest==7.4.0`: Test framework
- `pytest-cov==4.1.0`: Coverage reporting
- `sacrebleu==2.3.1`: Translation metrics
- `unittest.mock`: Mocking library (built-in)
