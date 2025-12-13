"""
Basic functionality tests for the Chuuk Dictionary OCR application
"""
import os
import sys
import tempfile
from io import BytesIO

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.publication_manager import PublicationManager
from src.core.jworg_lookup import JWOrgLookup


def test_publication_manager():
    """Test publication manager basic functionality"""
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        pm = PublicationManager(temp_dir)
        
        # Test creating publication
        pub_id = pm.create_publication("Test Dictionary", "Test description")
        assert pub_id is not None, "Failed to create publication"
        
        # Test getting publication
        pub = pm.get_publication(pub_id)
        assert pub is not None, "Failed to retrieve publication"
        assert pub['title'] == "Test Dictionary", "Title mismatch"
        
        # Test adding page
        success = pm.add_page(pub_id, "test_page.jpg", {"tesseract": "Sample text"})
        assert success, "Failed to add page"
        
        # Test listing publications
        pubs = pm.list_publications()
        assert len(pubs) == 1, "Publication list count mismatch"


def test_jworg_lookup():
    """Test JW.org lookup basic functionality"""
    
    lookup = JWOrgLookup()
    
    # Test language list
    langs = lookup.get_available_languages()
    assert len(langs) > 0, "No languages available"
    assert 'chk' in langs, "Chuukese not in language list"
    
    # Test word search (this will make actual HTTP requests)
    results = lookup.search_word("hello", "en")
    assert isinstance(results, list), "Results should be a list"
    assert len(results) > 0, "No search results returned"


def test_flask_app_import():
    """Test that Flask app can be imported"""
    
    try:
        import app
        assert hasattr(app, 'app'), "Flask app object not found"
    except ImportError as e:
        raise AssertionError(f"Failed to import app: {e}")
