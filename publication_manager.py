"""
Module for managing dictionary publications and their pages
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Optional


class PublicationManager:
    """Manages dictionary publications and their OCR results"""
    
    def __init__(self, storage_dir: str = 'uploads'):
        """
        Initialize publication manager
        
        Args:
            storage_dir: Directory to store publications and metadata
        """
        self.storage_dir = storage_dir
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
        pub_id = datetime.now().strftime('%Y%m%d%H%M%S')
        
        self.publications[pub_id] = {
            'id': pub_id,
            'title': title,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'pages': []
        }
        
        # Create publication directory
        pub_dir = os.path.join(self.storage_dir, pub_id)
        os.makedirs(pub_dir, exist_ok=True)
        
        self._save_metadata()
        return pub_id
    
    def add_page(self, pub_id: str, filename: str, ocr_results: Optional[Dict] = None) -> bool:
        """
        Add a page to a publication
        
        Args:
            pub_id: Publication ID
            filename: Filename of the page image
            ocr_results: Optional OCR results for the page
            
        Returns:
            Success status
        """
        if pub_id not in self.publications:
            return False
        
        page_data = {
            'filename': filename,
            'added_at': datetime.now().isoformat(),
            'ocr_results': ocr_results or {}
        }
        
        self.publications[pub_id]['pages'].append(page_data)
        self._save_metadata()
        return True
    
    def get_publication(self, pub_id: str) -> Optional[Dict]:
        """Get publication by ID"""
        return self.publications.get(pub_id)
    
    def list_publications(self) -> List[Dict]:
        """List all publications"""
        return list(self.publications.values())
    
    def get_page_path(self, pub_id: str, filename: str) -> str:
        """Get full path to a page file"""
        return os.path.join(self.storage_dir, pub_id, filename)
