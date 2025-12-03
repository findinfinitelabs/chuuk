"""
Module for looking up words and phrases from JW.org Chuukese sources
"""
import requests
from typing import List, Dict
from urllib.parse import quote


class JWOrgLookup:
    """Handles word and phrase lookups from JW.org Chuukese sources"""
    
    BASE_URLS = [
        "https://www.jw.org/chk",
        "https://wol.jw.org/chk/wol/h/r303/lp-te"
    ]
    
    def __init__(self):
        """Initialize the lookup service"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search_word(self, word: str, language_code: str = 'chk') -> List[Dict[str, str]]:
        """
        Search for a word or phrase across JW.org sources
        
        Args:
            word: The word or phrase to search for
            language_code: Language code (default: 'chk' for Chuukese)
            
        Returns:
            List of dictionaries containing search results
        """
        results = []
        
        # Search on main JW.org site
        try:
            search_url = f"https://www.jw.org/{language_code}/search/?q={quote(word)}"
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                results.append({
                    'source': 'JW.org Main Site',
                    'url': search_url,
                    'status': 'success',
                    'word': word
                })
        except Exception as e:
            results.append({
                'source': 'JW.org Main Site',
                'url': search_url,
                'status': 'error',
                'error': str(e)
            })
        
        # Search on WOL (Watchtower Online Library)
        try:
            wol_search_url = f"https://wol.jw.org/{language_code}/wol/s/r303/lp-te?q={quote(word)}"
            response = self.session.get(wol_search_url, timeout=10)
            
            if response.status_code == 200:
                results.append({
                    'source': 'Watchtower Online Library',
                    'url': wol_search_url,
                    'status': 'success',
                    'word': word
                })
        except Exception as e:
            results.append({
                'source': 'Watchtower Online Library',
                'url': wol_search_url,
                'status': 'error',
                'error': str(e)
            })
        
        return results
    
    def get_available_languages(self) -> List[str]:
        """
        Get list of commonly available language codes on JW.org
        
        Returns:
            List of language codes
        """
        return [
            'chk',  # Chuukese
            'en',   # English
            'es',   # Spanish
            'pt',   # Portuguese
            'fr',   # French
            'de',   # German
            'it',   # Italian
            'ja',   # Japanese
            'ko',   # Korean
            'zh',   # Chinese
        ]
