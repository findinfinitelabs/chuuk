"""
Module for looking up words and phrases from JW.org Chuukese sources and local publications
"""
import requests
import os
import json
from typing import List, Dict, Optional
from urllib.parse import quote


class JWOrgLookup:
    """Handles word and phrase lookups from JW.org Chuukese sources"""
    
    BASE_URLS = [
        "https://www.jw.org/chk",
        "https://wol.jw.org/chk/wol/h/r303/lp-te"
    ]
    
    def __init__(self, publication_manager=None):
        """Initialize the lookup service"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.publication_manager = publication_manager
    
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
    
    def translate_text(self, text: str, source_lang: str = 'chk', target_lang: str = 'en') -> Optional[Dict[str, str]]:
        """
        Translate text from source language to target language using Google Translate
        
        Args:
            text: Text to translate
            source_lang: Source language code (default: 'chk' for Chuukese)
            target_lang: Target language code (default: 'en' for English)
            
        Returns:
            Dictionary containing translation result or None if translation fails
        """
        if not self.translate_client:
            return None
            
        try:
            # Note: Google Translate may not directly support Chuukese (chk)
            # We'll try anyway, and if it fails, we'll return None
            result = self.translate_client.translate(
                text,
                source_language=source_lang if source_lang != 'chk' else None,  # Let Google auto-detect for Chuukese
                target_language=target_lang
            )
            
            return {
                'translated_text': result['translatedText'],
                'detected_source_language': result.get('detectedSourceLanguage', source_lang),
                'confidence': result.get('confidence'),
                'source_text': text
            }
            
        except Exception as e:
            print(f"Translation error: {e}")
            return None
    
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
