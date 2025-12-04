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
    print("Testing PublicationManager...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        pm = PublicationManager(temp_dir)
        
        # Test creating publication
        pub_id = pm.create_publication("Test Dictionary", "Test description")
        assert pub_id is not None, "Failed to create publication"
        print(f"  ✓ Created publication with ID: {pub_id}")
        
        # Test getting publication
        pub = pm.get_publication(pub_id)
        assert pub is not None, "Failed to retrieve publication"
        assert pub['title'] == "Test Dictionary", "Title mismatch"
        print(f"  ✓ Retrieved publication: {pub['title']}")
        
        # Test adding page
        success = pm.add_page(pub_id, "test_page.jpg", {"tesseract": "Sample text"})
        assert success, "Failed to add page"
        print(f"  ✓ Added page to publication")
        
        # Test listing publications
        pubs = pm.list_publications()
        assert len(pubs) == 1, "Publication list count mismatch"
        print(f"  ✓ Listed {len(pubs)} publication(s)")
    
    print("✓ PublicationManager tests passed!\n")


def test_jworg_lookup():
    """Test JW.org lookup basic functionality"""
    print("Testing JWOrgLookup...")
    
    lookup = JWOrgLookup()
    
    # Test language list
    langs = lookup.get_available_languages()
    assert len(langs) > 0, "No languages available"
    assert 'chk' in langs, "Chuukese not in language list"
    print(f"  ✓ Available languages: {len(langs)}")
    
    # Test word search (this will make actual HTTP requests)
    print("  Testing word search (this may take a moment)...")
    results = lookup.search_word("hello", "en")
    assert isinstance(results, list), "Results should be a list"
    assert len(results) > 0, "No search results returned"
    print(f"  ✓ Search returned {len(results)} result(s)")
    
    for result in results:
        print(f"    - {result['source']}: {result['status']}")
    
    print("✓ JWOrgLookup tests passed!\n")


def test_flask_app_import():
    """Test that Flask app can be imported"""
    print("Testing Flask app import...")
    
    try:
        import app
        assert hasattr(app, 'app'), "Flask app object not found"
        print("  ✓ Flask app imported successfully")
        print(f"  ✓ App has {len(app.app.url_map._rules)} routes")
    except ImportError as e:
        print(f"  ✗ Failed to import app: {e}")
        return False
    
    print("✓ Flask app import test passed!\n")
    return True


def main():
    """Run all tests"""
    print("=" * 50)
    print("Running Chuuk Dictionary OCR Tests")
    print("=" * 50 + "\n")
    
    try:
        test_publication_manager()
        test_jworg_lookup()
        test_flask_app_import()
        
        print("=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
