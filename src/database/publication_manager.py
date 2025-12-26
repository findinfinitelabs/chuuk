"""
Module for managing dictionary publications and their pages
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional


class PublicationManager:
    """Manages dictionary publications and their OCR results"""
    
    def __init__(self, storage_dir: str = 'uploads', db=None):
        """
        Initialize publication manager
        
        Args:
            storage_dir: Directory to store publications and metadata
            db: Optional DictionaryDB instance for syncing with database pages
        """
        self.storage_dir = storage_dir
        self.metadata_file = os.path.join(storage_dir, 'publications.json')
        self.publications = self._load_metadata()
        self.db = db
        self.metadata_file = os.path.join(storage_dir, 'publications.json')
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_dir, exist_ok=True)
        
        # Load or create metadata
        self.publications = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load publication metadata from file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_metadata(self):
        """Save publication metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.publications, f, indent=2)
        except Exception as e:
            print(f"Error saving metadata: {e}")
    
    def create_publication(self, title: str, description: str = '') -> str:
        """
        Create a new publication entry
        
        Args:
            title: Title of the publication
            description: Optional description
            
        Returns:
            Publication ID
        """
        # Use UUID to ensure uniqueness and prevent timestamp collisions
        import uuid
        pub_id = datetime.now().strftime('%Y%m%d%H%M%S') + '_' + str(uuid.uuid4())[:8]
        
        self.publications[pub_id] = {
            'id': pub_id,
            'title': title,
            'description': description,
            'created_date': datetime.now().isoformat(),
            'pages': []
        }
        
        # Create publication directory
        pub_dir = os.path.join(self.storage_dir, pub_id)
        os.makedirs(pub_dir, exist_ok=True)
        
        self._save_metadata()
        return pub_id
    
    def add_page(self, pub_id: str, filename: str, ocr_results: Optional[Dict] = None, processed: bool = False, entries_count: int = 0) -> bool:
        """
        Add a page to a publication
        
        Args:
            pub_id: Publication ID
            filename: Filename of the page image
            ocr_results: Optional OCR results for the page
            processed: Whether the page has been processed for dictionary entries
            entries_count: Number of dictionary entries extracted
            
        Returns:
            Success status
        """
        if pub_id not in self.publications:
            return False
        
        # Extract OCR text from results
        ocr_text = ''
        if ocr_results:
            ocr_text = ocr_results.get('text', '')
        
        page_data = {
            'id': f"{pub_id}_{filename}",
            'filename': filename,
            'added_at': datetime.now().isoformat(),
            'ocr_results': ocr_results or {},
            'ocr_text': ocr_text,
            'processed': processed,
            'entries_count': entries_count
        }
        
        self.publications[pub_id]['pages'].append(page_data)
        self._save_metadata()
        return True
    
    def get_publication(self, pub_id: str) -> Optional[Dict]:
        """Get publication by ID"""
        return self.publications.get(pub_id)
    
    def list_publications(self) -> List[Dict]:
        """List all publications with page counts from database"""
        pubs = list(self.publications.values())
        
        # Add page counts from database if db connection available
        if self.db and self.db.client:
            for pub in pubs:
                pub_id = pub.get('id')
                if pub_id:
                    # Count pages from database
                    page_count = self.db.pages_collection.count_documents({'publication_id': pub_id})
                    pub['page_count'] = page_count
        else:
            # Fallback to JSON metadata
            for pub in pubs:
                pub['page_count'] = len(pub.get('pages', []))
        
        return pubs
    
    def clear_publications(self) -> bool:
        """
        Clear all publications metadata
        
        Returns:
            Success status
        """
        try:
            self.publications = {}
            self._save_metadata()
            print("Publications cleared successfully")
            return True
        except Exception as e:
            print(f"Error clearing publications: {e}")
            return False
    
    def get_page_path(self, pub_id: str, filename: str) -> str:
        """Get full path to a page file"""
        return os.path.join(self.storage_dir, pub_id, filename)
