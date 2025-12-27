"""
Dictionary Database Manager for Chuuk Dictionary OCR
Handles indexing and searching of OCR'd dictionary content using MongoDB
"""
import re
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
from pymongo import MongoClient, TEXT, ASCENDING
from pymongo.errors import DuplicateKeyError, ConnectionFailure


class DictionaryDB:
    """Manages dictionary entries in MongoDB"""
    
    def __init__(self, connection_string: str = None):
        """Initialize database connection"""
        from .db_factory import get_database_client, get_database_config
        
        self.config = get_database_config()
        self.db_type = self.config['type']
        
        if self.db_type == 'cosmos':
            # Use Cosmos DB with MongoDB API
            self.client = get_database_client()
            self.db = self.client[self.config['database_name']]
            self.dictionary_collection = self.db[self.config['container_name']]
            self.pages_collection = self.db[self.config['pages_container']]
            self.words_collection = self.db[self.config['words_container']]
            self.phrases_collection = self.db[self.config['phrases_container']]
            self.paragraphs_collection = self.db[self.config['paragraphs_container']]
        else:
            # Fallback to MongoDB (not used in this setup)
            self.connection_string = connection_string or os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
            self.db_name = 'chuuk_dictionary'
            self.client = None
            self.db = None
            self.dictionary_collection = None
            self.pages_collection = None
            
        self._connect()
    
    def _connect(self):
        """Connect to database"""
        try:
            if self.db_type == 'cosmos':
                # Test Cosmos DB connection with MongoDB API
                try:
                    # Test connection - use list_database_names() which works with Cosmos DB
                    db_names = self.client.list_database_names()
                    print(f"Connected to Azure Cosmos DB with MongoDB API successfully. Databases: {db_names}")
                    self._create_indexes()
                except Exception as e:
                    print(f"Azure Cosmos DB connection failed: {e}")
                    import traceback
                    traceback.print_exc()
                    self.client = None
            else:
                # MongoDB connection (fallback)
                from pymongo import MongoClient, TEXT, ASCENDING
                self.client = MongoClient(self.connection_string, serverSelectionTimeoutMS=5000)
                # Test connection
                self.client.admin.command('ping')
                self.db = self.client[self.db_name]
                self.dictionary_collection = self.db.dictionary_entries
                self.pages_collection = self.db.dictionary_pages
                self.words_collection = self.db.words
                self.phrases_collection = self.db.phrases
                self.paragraphs_collection = self.db.paragraphs
                self._create_indexes()
                print("Connected to MongoDB successfully")
        except Exception as e:
            print(f"Database connection failed: {e}. Running without database indexing.")
            self.client = None
    
    def _create_indexes(self):
        """Create database indexes for efficient searching on all collections"""
        if not self.client:
            return
            
        try:
            # Cosmos DB MongoDB API doesn't support text indexes
            # Create regular indexes for common search fields
            self.dictionary_collection.create_index([('chuukese_word', ASCENDING)])
            self.dictionary_collection.create_index([('english_translation', ASCENDING)])
            self.dictionary_collection.create_index([('source_page', ASCENDING)])
            
            # Create indexes for pages collection
            self.pages_collection.create_index([('publication_id', ASCENDING)])
            self.pages_collection.create_index([('filename', ASCENDING)])
            
            # Create indexes for words collection
            self.words_collection.create_index([('chuukese', ASCENDING)])
            self.words_collection.create_index([('english_translation', ASCENDING)])
            self.words_collection.create_index([('grammar', ASCENDING)])
            self.words_collection.create_index([('date_added', ASCENDING)])
            
            # Create indexes for phrases collection (no text indexes for Cosmos DB)
            self.phrases_collection.create_index([('chuukese', ASCENDING)])
            self.phrases_collection.create_index([('english', ASCENDING)])
            self.phrases_collection.create_index([('chuukese_phrase', ASCENDING)])
            self.phrases_collection.create_index([('english_translation', ASCENDING)])
            self.phrases_collection.create_index([('source', ASCENDING)])
            self.phrases_collection.create_index([('date_added', ASCENDING)])
            
            # Create indexes for paragraphs collection (no text indexes for Cosmos DB)
            self.paragraphs_collection.create_index([('chuukese_paragraph', ASCENDING)])
            self.paragraphs_collection.create_index([('english_paragraph', ASCENDING)])
            self.paragraphs_collection.create_index([('source', ASCENDING)])
            self.paragraphs_collection.create_index([('date_added', ASCENDING)])
            
            print("✓ Created indexes for Cosmos DB")
        except Exception as e:
            print(f"Error creating indexes (may already exist): {str(e)}")

    @property
    def collection(self):
        """Property to access the main dictionary collection for API compatibility"""
        return self.dictionary_collection

    
    def add_dictionary_page(self, publication_id: str, filename: str, ocr_text: str, page_number: int = 1) -> str:
        """
        Add a dictionary page to the database and extract entries
        
        Args:
            publication_id: ID of the publication
            filename: Name of the image file
            ocr_text: OCR extracted text
            page_number: Page number within the document
            
        Returns:
            Page ID
        """
        if not self.client:
            return None
            
        page_data = {
            'publication_id': publication_id,
            'filename': filename,
            'page_number': page_number,
            'ocr_text': ocr_text,
            'processed_date': datetime.now(timezone.utc),
            'entries_extracted': 0
        }
        
        # Insert page
        result = self.pages_collection.insert_one(page_data)
        page_id = str(result.inserted_id)
        
        # Extract and index dictionary entries
        entries = self._extract_dictionary_entries(ocr_text, page_id, publication_id, filename, page_number)
        
        # Update page with number of entries extracted
        self.pages_collection.update_one(
            {'_id': result.inserted_id},
            {'$set': {'entries_extracted': len(entries)}}
        )
        
        return page_id
    
    def _extract_dictionary_entries(self, ocr_text: str, page_id: str, publication_id: str, filename: str, page_number: int = 1) -> List[Dict]:
        """
        Extract dictionary entries from OCR text using pattern matching
        
        Args:
            ocr_text: Raw OCR text
            page_id: Page database ID
            publication_id: Publication ID
            filename: Source filename
            page_number: Page number within document
            
        Returns:
            List of extracted entries
        """
        entries = []
        
        # Enhanced dictionary entry patterns for complex Chuukese dictionary structure
        patterns = [
            # Pattern 1: Simple "word – translation" or "word — translation"
            r'^([^\s\-—.]{2,30})\s*[–—-]\s*(.{3,150})$',
            
            # Pattern 2: "word – v. translation" (verb patterns)
            r'^([^\s\-—.]{2,30})\s*[–—-]\s*(v\.|vt\.|vi\.|verb)?\s*(.{3,150})$',
            
            # Pattern 3: Pronoun patterns "word, -ei, -uk*, -kem, -kemi, -ir, -kich – definition"
            r'^([^\s,]{2,30}),\s*([-\w,\s\*]+)\s*[–—-]\s*(.{3,150})\s*\([^)]*me[^)]*\)',
            
            # Pattern 4: "word: translation"
            r'^([^\s:]{2,30}):\s*(.{3,150})$',
            
            # Pattern 5: Numbered entries "1. word - translation"
            r'^\d+\.\s*([^\s\-—]{2,30})\s*[–—-]\s*(.{3,150})$',
            
            # Pattern 6: Related word forms (following main entry)
            r'^([a-z]\w{2,30})\s*[–—-]\s*(.{3,150})$',
            
            # Pattern 7: Complex forms with grammatical info
            r'^([^\s,\(]{2,30})\s*[,\s]*\([^)]+\)\s*[–—-]?\s*(.{3,150})$',
        ]
        
        lines = ocr_text.split('\n')
        current_root_word = None
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 5:
                continue
                
            # Skip header lines (common dictionary headers)
            if any(skip_pattern in line.lower() for skip_pattern in [
                'page ', 'see page', '(pronouns', '(directionals', 'pg.', 'see pg',
                'chuukese phrase', 'english translation', 'definition', 'notes',
                'type', 'direction', 'chuukese-english', 'english-chuukese',
                'dictionary', 'table of contents', 'index', 'appendix',
                'chapter ', 'section '
            ]):
                continue
            
            # Skip lines that look like column headers (all caps, short words)
            words_in_line = line.split()
            if len(words_in_line) <= 5 and all(w.isupper() or w.istitle() for w in words_in_line if len(w) > 1):
                continue
                
            for pattern_num, pattern in enumerate(patterns, 1):
                match = re.match(pattern, line, re.IGNORECASE | re.DOTALL)
                if match:
                    # Extract multiple entries from this line
                    line_entries = self._extract_multiple_entries(line, pattern_num, match, page_id, publication_id, filename, page_number, line_num + 1, current_root_word)
                    
                    # Update current root word if we found a base word
                    for entry in line_entries:
                        if entry.get('is_base_word') and len(entry['chuukese_word']) <= 10:
                            current_root_word = entry['chuukese_word']
                    
                    # Add entries with reverse lookups
                    for entry in line_entries:
                        entries.append(entry)
                        
                        # Create reverse entry (English to Chuukese)
                        reverse_entry = entry.copy()
                        reverse_entry.update({
                            'search_direction': 'en_to_chk',
                            'primary_language': 'english',
                            'secondary_language': 'chuukese'
                        })
                        entries.append(reverse_entry)
                    
                    break  # Found a match, move to next line
        
        # Insert entries into database with error handling
        if entries:
            try:
                self.dictionary_collection.insert_many(entries, ordered=False)
            except Exception as e:
                print(f"Error inserting entries: {e}")
                # Insert individually to handle duplicates
                for entry in entries:
                    try:
                        self.dictionary_collection.insert_one(entry)
                    except DuplicateKeyError:
                        # Update existing entry with better/missing fields
                        self._merge_duplicate_entry(entry, page_id, filename, page_number)
                    except Exception as insert_error:
                        print(f"Error inserting individual entry: {insert_error}")
        
        return entries
    
    def _extract_multiple_entries(self, line: str, pattern_num: int, match, page_id: str, 
                                 publication_id: str, filename: str, page_number: int, 
                                 line_number: int, current_root_word: str) -> List[Dict]:
        """Extract multiple dictionary entries from a complex line"""
        entries = []
        
        # Check if this is a complex line that should be split into multiple entries
        # Look for patterns indicating multiple word-definition pairs
        complex_indicators = [
            r',\s*\w+\s*[–\-]\s*v\.',  # Contains ", word – v."
            r'-\w+[*]?(?:,\s*-\w+[*]?)+',  # Contains multiple inflections like "-ei, -uk*"
            r',\s*[a-z]+[a-z]+,',  # Contains compound words in sequence
            r'\([^)]*(?:me|you|him|her|us|them)[^)]*\)'  # Contains pronoun references
        ]
        
        is_complex = any(re.search(indicator, line) for indicator in complex_indicators)
        
        if is_complex and pattern_num in [1, 2]:  # Simple patterns on complex lines
            # Use complex extraction for lines that have multiple components
            entries.extend(self._extract_complex_entries(line, pattern_num, match, page_id, publication_id, filename, page_number, line_number, current_root_word))
        else:
            # Use simple extraction for straightforward lines
            entries.extend(self._create_single_entry(line, pattern_num, match, page_id, publication_id, filename, page_number, line_number, current_root_word))
        
        return entries
    
    def _create_single_entry(self, line: str, pattern_num: int, match, page_id: str, 
                           publication_id: str, filename: str, page_number: int, 
                           line_number: int, current_root_word: str) -> List[Dict]:
        """Create a single dictionary entry from a simple line"""
        entries = []
        groups = match.groups()
        
        if len(groups) >= 2:
            chuukese_word = groups[0].strip()
            english_translation = groups[1].strip()
            
            # Clean up extracted text
            chuukese_word = re.sub(r'[^\w\s\-\']', '', chuukese_word).strip()
            english_translation = re.sub(r'^\W+|\W+$', '', english_translation).strip()
            
            if self._validate_entry(chuukese_word, english_translation):
                entry = self._build_entry(chuukese_word, english_translation, line, pattern_num, 
                                        page_id, publication_id, filename, page_number, line_number, 
                                        current_root_word, is_base_word=True)
                entries.append(entry)
        
        return entries
    
    def _extract_complex_entries(self, line: str, pattern_num: int, match, page_id: str, 
                               publication_id: str, filename: str, page_number: int, 
                               line_number: int, current_root_word: str) -> List[Dict]:
        """Extract multiple entries from complex dictionary lines"""
        entries = []
        
        # Parse complex line to find all word-definition pairs
        # Example: "chem – remember, chemeni – v. remember, chechchemeni, -ei, -uk*, -kem, -kemi, -ir, -kich – remember (me, you, etc.)"
        
        base_word = None
        base_definition = None
        
        # First, identify the primary base word and definition
        base_match = re.search(r'^([^–\-,]+)\s*[–\-]\s*([^,]+?)(?=\s*,|$)', line)
        if base_match:
            base_word = base_match.group(1).strip()
            base_definition = base_match.group(2).strip()
            
            # Clean base word
            base_word = re.sub(r'[^\w\s\-\']', '', base_word).strip().lower()
            base_definition = re.sub(r'^\W+|\W+$', '', base_definition).strip()
            
            if self._validate_entry(base_word, base_definition):
                entry = self._build_entry(base_word, base_definition, line, pattern_num, 
                                        page_id, publication_id, filename, page_number, line_number, 
                                        base_word, is_base_word=True)
                entries.append(entry)
        
        # Find additional word forms (like "chemeni – v. remember")
        additional_forms = re.finditer(r',\s*([^–\-,]+)\s*[–\-]\s*(v\.\s*)?([^,–\-]+?)(?=\s*,|$)', line)
        for form_match in additional_forms:
            word = form_match.group(1).strip()
            verb_marker = form_match.group(2) if form_match.group(2) else ""
            definition = form_match.group(3).strip()
            
            # Clean up
            word = re.sub(r'[^\w\s\-\']', '', word).strip().lower()
            full_definition = f"{verb_marker}{definition}".strip() if verb_marker else definition
            full_definition = re.sub(r'^\W+|\W+$', '', full_definition).strip()
            
            if self._validate_entry(word, full_definition):
                entry = self._build_entry(word, full_definition, line, pattern_num, 
                                        page_id, publication_id, filename, page_number, line_number, 
                                        base_word or current_root_word, is_base_word=False)
                entry['word_type'] = 'derived_form'
                entries.append(entry)
        
        # Handle inflection patterns like "-ei, -uk*, -kem, -kemi, -ir, -kich – remember (me, you, etc.)"
        inflection_match = re.search(r'(-\w+[*]?(?:,?\s*-\w+[*]?)*)\s*[–\-]\s*([^(]+?)(?:\(([^)]+)\))?', line)
        if inflection_match and base_word:
            inflection_string = inflection_match.group(1)
            base_meaning = inflection_match.group(2).strip()
            pronoun_info = inflection_match.group(3).strip() if inflection_match.group(3) else ""
            
            # Parse individual inflections
            inflections = re.findall(r'-(\w+[*]?)', inflection_string)
            
            for inflection in inflections:
                # Remove asterisk if present
                clean_inflection = inflection.rstrip('*')
                inflected_word = base_word + clean_inflection
                
                # Build full definition
                full_definition = base_meaning
                if pronoun_info:
                    full_definition += f" ({pronoun_info})"
                
                if self._validate_entry(inflected_word, full_definition):
                    entry = self._build_entry(inflected_word, full_definition, line, pattern_num, 
                                            page_id, publication_id, filename, page_number, line_number, 
                                            base_word, is_base_word=False)
                    entry['inflection_type'] = 'pronoun_form'
                    entry['base_inflection'] = f"-{inflection}"
                    entry['word_type'] = 'inflected_form'
                    entries.append(entry)
        
        # Handle standalone compound words (like "chechchemeni")
        standalone_match = re.search(r',\s*([a-z]+(?:[a-z]+)*)\s*(?=,|\s*-)', line)
        if standalone_match and base_word and base_definition:
            standalone_word = standalone_match.group(1).strip().lower()
            if len(standalone_word) > len(base_word) and base_word in standalone_word:
                if self._validate_entry(standalone_word, base_definition):
                    entry = self._build_entry(standalone_word, base_definition, line, pattern_num, 
                                            page_id, publication_id, filename, page_number, line_number, 
                                            base_word, is_base_word=False)
                    entry['word_type'] = 'compound_form'
                    entries.append(entry)
        
        return entries
    
    def _validate_entry(self, chuukese_word: str, english_translation: str) -> bool:
        """Validate if a word-definition pair is worth storing"""
        return (len(chuukese_word) >= 2 and len(english_translation) >= 3 and 
                len(chuukese_word) <= 40 and len(english_translation) <= 250 and
                chuukese_word.replace('-', '').replace('*', '').replace(' ', '').isalpha() and
                chuukese_word not in ['v', 'n', 'adj', 'adv', 'prep'])  # Exclude grammatical markers
    
    def _extract_word_type(self, line: str, english_translation: str) -> str:
        """Extract grammatical type from dictionary line with abbreviation mapping"""
        # Comprehensive grammatical marker patterns with abbreviations
        type_patterns = [
            # Verbs
            (r'\bv\.(?!\w)', 'verb'),  # v. but not part of a word
            (r'\bverb\b', 'verb'),
            (r'\bvt\.(?!\w)', 'transitive verb'),
            (r'\btransitive verb\b', 'transitive verb'),
            (r'\bvi\.(?!\w)', 'intransitive verb'),
            (r'\bintransitive verb\b', 'intransitive verb'),
            (r'\bvtr\.(?!\w)', 'transitive verb'),
            (r'\bvintr\.(?!\w)', 'intransitive verb'),
            
            # Nouns
            (r'\bn\.(?!\w)', 'noun'),
            (r'\bnoun\b', 'noun'),
            (r'\bnp\.(?!\w)', 'proper noun'),
            (r'\bproper noun\b', 'proper noun'),
            
            # Adjectives
            (r'\badj\.(?!\w)', 'adjective'),
            (r'\badjective\b', 'adjective'),
            
            # Adverbs
            (r'\badv\.(?!\w)', 'adverb'),
            (r'\badverb\b', 'adverb'),
            
            # Prepositions
            (r'\bprep\.(?!\w)', 'preposition'),
            (r'\bpreposition\b', 'preposition'),
            
            # Pronouns
            (r'\bpron\.(?!\w)', 'pronoun'),
            (r'\bpronoun\b', 'pronoun'),
            
            # Conjunctions
            (r'\bconj\.(?!\w)', 'conjunction'),
            (r'\bconjunction\b', 'conjunction'),
            
            # Other
            (r'\binterj\.(?!\w)', 'interjection'),
            (r'\binterjection\b', 'interjection'),
            (r'\bdet\.(?!\w)', 'determiner'),
            (r'\bdeterminer\b', 'determiner'),
            (r'\baux\.(?!\w)', 'auxiliary'),
            (r'\bauxiliary\b', 'auxiliary'),
            (r'\bpart\.(?!\w)', 'particle'),
            (r'\bparticle\b', 'particle'),
        ]
        
        # Search in the entire line first (case-insensitive)
        for pattern, word_type in type_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return word_type
        
        # Search in the translation
        for pattern, word_type in type_patterns:
            if re.search(pattern, english_translation, re.IGNORECASE):
                return word_type
        
        # Try to infer from context
        if re.search(r'\bto\s+\w+', english_translation.lower()):
            return 'verb'  # "to do something" pattern
        
        return 'unknown'  # Default if no type detected
    
    def _build_entry(self, chuukese_word: str, english_translation: str, line: str, 
                    pattern_num: int, page_id: str, publication_id: str, filename: str, 
                    page_number: int, line_number: int, base_word: str, is_base_word: bool = False) -> Dict:
        """Build a complete dictionary entry"""
        confidence = self._calculate_confidence(line, pattern_num, chuukese_word, english_translation)
        
        # Extract grammatical type from the line
        word_type = self._extract_word_type(line, english_translation)
        
        entry = {
            'chuukese_word': chuukese_word.lower(),
            'english_translation': english_translation,
            'definition': english_translation,
            'word_type': word_type,  # Added word type extraction
            'type': word_type,  # Alias for compatibility
            'source_page_id': page_id,
            'publication_id': publication_id,
            'filename': filename,
            'page_number': page_number,
            'line_number': line_number,
            'raw_line': line,
            'pattern_matched': pattern_num,
            'confidence': confidence,
            'citation': f"{filename}, page {page_number}, line {line_number}",
            'created_date': datetime.utcnow(),
            'word_family': base_word.lower() if base_word else None,
            'base_word': base_word.lower() if base_word else chuukese_word.lower(),
            'is_base_word': is_base_word,
            'entry_type': 'dictionary_pair',
            'reverse_lookup': True,
            'search_direction': 'chk_to_eng',  # Default direction
            'primary_language': 'chuukese',
            'secondary_language': 'english'
        }
        
        # Add word tokens for better searching
        entry['chuukese_tokens'] = self._tokenize_word(chuukese_word)
        entry['english_tokens'] = self._tokenize_phrase(english_translation)
        
        return entry
    
    def _calculate_confidence(self, line: str, pattern_num: int, chuukese_word: str, english_translation: str) -> float:
        """Calculate confidence score for a dictionary entry"""
        confidence = 0.3  # Base confidence
        
        # Pattern-based scoring - updated for all 10 patterns
        pattern_scores = {
            1: 0.4,    # Standard word – translation
            2: 0.35,   # Standard word, translation
            3: 0.3,    # Word (type) – translation
            4: 0.25,   # "translation" – word  
            5: 0.35,   # Word  –  translation (wider spacing)
            6: 0.3,    # Page references
            7: 0.35,   # Complex grammatical forms with pronouns
            8: 0.4,    # Root word with inflections (-ei, -uk, etc.)
            9: 0.3,    # Cross-references to grammar sections
            10: 0.25   # Complex entries with multiple components
        }
        confidence += pattern_scores.get(pattern_num, 0.1)
        
        # Length-based scoring
        if 3 <= len(chuukese_word) <= 20:
            confidence += 0.2
        if 5 <= len(english_translation) <= 80:
            confidence += 0.15
            
        # Content quality indicators
        if any(marker in line for marker in ['-', '—', ':', '(', ')']):
            confidence += 0.1
            
        # Special boosts for linguistic complexity
        if re.search(r'(\(me,|you,|him,|her,|us,|them)', english_translation.lower()):
            confidence += 0.15  # Pronoun patterns indicate good grammar
            
        if re.search(r'(-\w{1,3}[,\s])+', chuukese_word):
            confidence += 0.1   # Inflection patterns
            
        # Penalize very short or very long entries
        if len(line) < 8 or len(line) > 150:
            confidence -= 0.15
            
        # Boost if contains common dictionary formatting
        if re.search(r'\b(adj|noun|verb|adv|prep|v\.|n\.|adj\.)\b', line, re.IGNORECASE):
            confidence += 0.1
            
        return min(1.0, max(0.1, confidence))
    
    def _tokenize_word(self, word: str) -> List[str]:
        """Tokenize a word for better matching"""
        tokens = [word.lower()]
        
        # Add variations
        if len(word) > 3:
            tokens.append(word[:3])  # Prefix
            tokens.append(word[-3:])  # Suffix
            
        # Handle compound words
        if '-' in word:
            tokens.extend(word.split('-'))
            
        return list(set(tokens))
    
    def _tokenize_phrase(self, phrase: str) -> List[str]:
        """Tokenize an English phrase for better matching"""
        # Basic word tokenization
        words = re.findall(r'\b\w+\b', phrase.lower())
        
        # Remove very short words and common stopwords
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        meaningful_words = [w for w in words if len(w) > 2 and w not in stopwords]
        
        return meaningful_words
    
    def _merge_duplicate_entry(self, new_entry: Dict, page_id: str, filename: str, page_number: int):
        """Intelligently merge duplicate entry with existing one, updating missing or better fields"""
        try:
            # Find existing entry
            existing = self.dictionary_collection.find_one({
                'chuukese_word': new_entry['chuukese_word'],
                'english_translation': new_entry['english_translation']
            })
            
            if not existing:
                return
            
            # Build update with smart field merging
            update_fields = {}
            
            # Update type/word_type if missing or was 'unknown'
            if new_entry.get('type') and new_entry['type'] != 'unknown':
                if not existing.get('type') or existing.get('type') == 'unknown':
                    update_fields['type'] = new_entry['type']
                    update_fields['word_type'] = new_entry['type']
            
            # Update direction fields if missing
            if not existing.get('search_direction'):
                update_fields['search_direction'] = new_entry.get('search_direction', 'chk_to_eng')
            if not existing.get('primary_language'):
                update_fields['primary_language'] = new_entry.get('primary_language', 'chuukese')
            if not existing.get('secondary_language'):
                update_fields['secondary_language'] = new_entry.get('secondary_language', 'english')
            
            # Update definition if new one is longer/better
            if new_entry.get('definition') and len(new_entry['definition']) > len(existing.get('definition', '')):
                update_fields['definition'] = new_entry['definition']
            
            # Update tokens if missing
            if not existing.get('chuukese_tokens') and new_entry.get('chuukese_tokens'):
                update_fields['chuukese_tokens'] = new_entry['chuukese_tokens']
            if not existing.get('english_tokens') and new_entry.get('english_tokens'):
                update_fields['english_tokens'] = new_entry['english_tokens']
            
            # Always update if confidence is higher
            if new_entry.get('confidence', 0) > existing.get('confidence', 0):
                update_fields['confidence'] = new_entry['confidence']
            
            # Build the update operation
            update_operation = {}
            
            # Add new source to alternative_sources
            update_operation['$addToSet'] = {
                'alternative_sources': {
                    'page_id': page_id,
                    'filename': filename,
                    'page_number': page_number,
                    'citation': new_entry['citation']
                }
            }
            
            # Set updated fields
            if update_fields:
                update_fields['last_updated'] = datetime.utcnow()
                update_operation['$set'] = update_fields
            
            # Apply update
            self.dictionary_collection.update_one(
                {'_id': existing['_id']},
                update_operation
            )
            
            print(f"Updated entry '{new_entry['chuukese_word']}' with {len(update_fields)} field(s)")
            
        except Exception as e:
            print(f"Error merging duplicate entry: {e}")
    
    def reprocess_page(self, publication_id: str, filename: str, page_number: int = 1) -> Dict:
        """
        Reprocess an existing page, updating entries with better field values
        
        Args:
            publication_id: ID of the publication
            filename: Name of the image file
            page_number: Page number within the document
            
        Returns:
            Dict with statistics about updates
        """
        if not self.client:
            return {'error': 'No database connection'}
        
        # Find existing page
        existing_page = self.pages_collection.find_one({
            'publication_id': publication_id,
            'filename': filename,
            'page_number': page_number
        })
        
        if not existing_page:
            return {'error': 'Page not found', 'success': False}
        
        page_id = str(existing_page['_id'])
        ocr_text = existing_page.get('ocr_text', '')
        
        if not ocr_text:
            return {'error': 'No OCR text available', 'success': False}
        
        # Re-extract entries with current (improved) extraction logic
        entries = self._extract_dictionary_entries(ocr_text, page_id, publication_id, filename, page_number)
        
        stats = {
            'success': True,
            'entries_processed': len(entries),
            'new_entries': 0,
            'updated_entries': 0,
            'unchanged_entries': 0
        }
        
        # Process each entry
        for entry in entries:
            try:
                # Try to insert (will fail if duplicate)
                self.dictionary_collection.insert_one(entry)
                stats['new_entries'] += 1
            except DuplicateKeyError:
                # Merge with existing
                self._merge_duplicate_entry(entry, page_id, filename, page_number)
                stats['updated_entries'] += 1
            except Exception as e:
                print(f"Error processing entry: {e}")
                stats['unchanged_entries'] += 1
        
        # Update page's processed date
        self.pages_collection.update_one(
            {'_id': existing_page['_id']},
            {
                '$set': {
                    'reprocessed_date': datetime.now(timezone.utc),
                    'entries_extracted': len(entries)
                }
            }
        )
        
        return stats
    
    def _find_examples(self, lines: List[str], current_line: int) -> List[str]:
        """Find example sentences in nearby lines"""
        examples = []
        
        # Look at next 2 lines for examples
        for i in range(current_line + 1, min(current_line + 3, len(lines))):
            line = lines[i].strip()
            
            # Example patterns
            if any(marker in line.lower() for marker in ['ex:', 'example:', 'e.g.', 'eg.']):
                example = re.sub(r'^(ex:|example:|e\.g\.|eg\.)', '', line, flags=re.IGNORECASE).strip()
                if example:
                    examples.append(example)
        
        return examples
    
    def search_word(self, word: str, limit: int = 10, include_related: bool = True) -> List[Dict]:
        """
        Search for a word in the dictionary (uses denormalized related_words for efficiency)
        
        Args:
            word: Word to search for (Chuukese or English)
            limit: Maximum number of results
            include_related: Whether to include related words (now using denormalized data - no extra queries!)
            
        Returns:
            List of matching dictionary entries with related words embedded
        """
        if not self.client:
            return []
        
        # Build Cosmos DB compatible query using regex (no $text support)
        word_lower = word.lower().strip()
        
        query = {
            '$and': [
                {
                    '$or': [
                        # Exact match (uses index)
                        {'chuukese_word': word_lower},
                        # Starts with (more efficient than contains)
                        {'chuukese_word': {'$regex': f'^{re.escape(word_lower)}', '$options': 'i'}},
                        {'english_translation': {'$regex': f'^{re.escape(word)}', '$options': 'i'}},
                        # Contains match (fallback)
                        {'chuukese_word': {'$regex': re.escape(word_lower), '$options': 'i'}},
                        {'english_translation': {'$regex': re.escape(word), '$options': 'i'}},
                        {'definition': {'$regex': re.escape(word), '$options': 'i'}}
                    ]
                },
                {
                    '$or': [
                        {'search_direction': {'$exists': False}},
                        {'search_direction': {'$ne': 'en_to_chk'}}
                    ]
                }
            ]
        }
        
        # Single query gets everything including related_words!
        results = list(self.dictionary_collection.find(query).limit(limit))
        
        # Use a dictionary to track unique entries by word+translation combination
        unique_entries = {}
        
        for result in results:
            # Skip reverse lookup entries
            if result.get('search_direction') == 'en_to_chk':
                continue
            
            # Create unique key based on word and translation
            word = result.get('chuukese_word', '').lower().strip()
            translation = result.get('english_translation', '').strip()
            unique_key = f"{word}|{translation}"
            
            # Keep the entry with highest confidence if duplicate
            if unique_key not in unique_entries or result.get('confidence', 0) > unique_entries[unique_key].get('confidence', 0):
                unique_entries[unique_key] = result
        
        # Convert to list
        results = list(unique_entries.values())
        
        # Convert ObjectId to string and add relevance scoring
        for result in results:
            result['_id'] = str(result['_id'])
            result['relevance'] = self._calculate_relevance(word_lower, result)
            
            # Related words are already embedded in the document!
            # No additional queries needed - denormalized data wins!
            if not include_related and 'related_words' in result:
                # Optionally remove related words if user doesn't want them
                result.pop('related_words', None)
            
            # Convert datetime objects to strings for template rendering
            if 'created_date' in result and result['created_date']:
                result['created_date'] = result['created_date'].isoformat() if hasattr(result['created_date'], 'isoformat') else str(result['created_date'])
            if 'processed_date' in result and result['processed_date']:
                result['processed_date'] = result['processed_date'].isoformat() if hasattr(result['processed_date'], 'isoformat') else str(result['processed_date'])
            
            # Ensure we have clean, readable definitions for phrases
            if not result.get('english_translation') or len(result['english_translation'].strip()) < 3:
                # If no translation, try to extract from definition or raw_line
                if result.get('definition'):
                    result['english_translation'] = result['definition']
                elif result.get('raw_line'):
                    # Try to extract translation from raw line
                    line = result['raw_line']
                    match = re.search(r'[\u2013\-]\s*([^,\n]+)', line)
                    if match:
                        result['english_translation'] = match.group(1).strip()
        
        # Sort by relevance (exact matches first, then word family, then partial matches)
        results.sort(key=lambda x: (
            x['relevance'], 
            x.get('is_base_word', False),  # Prioritize base words
            -x.get('confidence', 0)  # Higher confidence first
        ), reverse=True)
        
        return results[:limit]
    
    def _calculate_relevance(self, search_word: str, entry: Dict) -> float:
        """Calculate relevance score for search results"""
        score = 0
        
        chuukese = entry.get('chuukese_word', '').lower()
        english = entry.get('english_translation', '').lower()
        
        # Exact matches get highest score
        if chuukese == search_word:
            score += 10
        if search_word in english:
            score += 8
        
        # Base word matches get high priority
        if entry.get('is_base_word') and chuukese == search_word:
            score += 12
        
        # Word family relationships
        if entry.get('base_word') == search_word or entry.get('word_family') == search_word:
            score += 6
        
        # Partial matches
        if search_word in chuukese:
            score += 5
        if any(search_word in word for word in english.split()):
            score += 3
        
        # Boost score based on confidence
        score += entry.get('confidence', 0.5) * 2
        
        # Boost for entries with examples or inflection info
        if entry.get('examples'):
            score += 0.5
        if entry.get('inflection_type'):
            score += 0.5
        
        return score
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        if not self.client:
            return {'error': 'Database not available'}
        
        return {
            'total_entries': self.dictionary_collection.count_documents({}),
            'total_pages': self.pages_collection.count_documents({}),
            'publications': len(self.pages_collection.distinct('publication_id')),
            'database_status': 'connected'
        }
    
    def get_stats(self) -> Dict:
        """Get enhanced database statistics for API"""
        if not self.client:
            return {
                'total_entries': 0,
                'total_chuukese_words': 0,
                'total_english_words': 0,
                'last_updated': None
            }
        
        try:
            total_entries = self.dictionary_collection.count_documents({})
            
            # Count unique Chuukese words (avoiding order-by issues)
            chuukese_words_pipeline = [
                {"$group": {"_id": "$chuukese_word"}},
                {"$count": "total"}
            ]
            chuukese_result = list(self.dictionary_collection.aggregate(chuukese_words_pipeline))
            chuukese_words = chuukese_result[0]["total"] if chuukese_result else 0
            
            # Count unique English translations
            english_words_pipeline = [
                {"$group": {"_id": "$english_translation"}},
                {"$count": "total"}
            ]
            english_result = list(self.dictionary_collection.aggregate(english_words_pipeline))
            english_words = english_result[0]["total"] if english_result else 0
            
            # Get last updated timestamp (avoid sorting by created_date due to Cosmos DB issues)
            last_updated = None
            sample_entry = self.dictionary_collection.find_one({})
            if sample_entry and 'created_date' in sample_entry:
                last_updated = sample_entry['created_date'].isoformat() if hasattr(sample_entry['created_date'], 'isoformat') else str(sample_entry['created_date'])
            
            return {
                'total_entries': total_entries,
                'total_chuukese_words': chuukese_words,
                'total_english_words': english_words,
                'last_updated': last_updated
            }
        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {
                'total_entries': 0,
                'total_chuukese_words': 0,
                'total_english_words': 0,
                'last_updated': None
            }
    
    def get_recent_entries(self, limit: int = 20) -> List[Dict]:
        """Get recently added dictionary entries"""
        if not self.client:
            return []
        
        results = list(
            self.dictionary_collection
            .find({})
            .sort('created_date', -1)
            .limit(limit)
        )
        
        for result in results:
            result['_id'] = str(result['_id'])
            
            # Convert datetime objects to strings for template rendering
            if 'created_date' in result and result['created_date']:
                result['created_date'] = result['created_date'].isoformat() if hasattr(result['created_date'], 'isoformat') else str(result['created_date'])
            if 'processed_date' in result and result['processed_date']:
                result['processed_date'] = result['processed_date'].isoformat() if hasattr(result['processed_date'], 'isoformat') else str(result['processed_date'])
        
        return results
    
    def get_pages_summary(self) -> List[Dict]:
        """Get summary of all processed pages"""
        if not self.client:
            return []
        
        results = list(
            self.pages_collection
            .find({})
            .sort('processed_date', -1)
        )
        
        for result in results:
            result['_id'] = str(result['_id'])
            
            # Convert datetime objects to strings for template rendering
            if 'created_date' in result and result['created_date']:
                result['created_date'] = result['created_date'].isoformat() if hasattr(result['created_date'], 'isoformat') else str(result['created_date'])
            if 'processed_date' in result and result['processed_date']:
                result['processed_date'] = result['processed_date'].isoformat() if hasattr(result['processed_date'], 'isoformat') else str(result['processed_date'])
        
        return results
    
    def get_entries_paginated(self, page: int = 1, per_page: int = 50, search: str = '') -> Dict:
        """Get paginated dictionary entries with optional search"""
        if not self.client:
            return {'entries': [], 'total': 0, 'page': page, 'per_page': per_page}
        
        # Build search query
        query = {}
        if search:
            query = {
                '$or': [
                    {'chuukese_word': {'$regex': search, '$options': 'i'}},
                    {'english_translation': {'$regex': search, '$options': 'i'}},
                    {'definition': {'$regex': search, '$options': 'i'}}
                ]
            }
        
        # Get total count
        total = self.dictionary_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * per_page
        results = list(
            self.dictionary_collection
            .find(query)
            .sort('created_date', -1)
            .skip(skip)
            .limit(per_page)
        )
        
        # Convert ObjectId to string and handle datetime objects
        for result in results:
            result['_id'] = str(result['_id'])
            
            # Convert datetime objects to strings for template rendering
            if 'created_date' in result and result['created_date']:
                result['created_date'] = result['created_date'].isoformat() if hasattr(result['created_date'], 'isoformat') else str(result['created_date'])
            if 'processed_date' in result and result['processed_date']:
                result['processed_date'] = result['processed_date'].isoformat() if hasattr(result['processed_date'], 'isoformat') else str(result['processed_date'])
        
        return {
            'entries': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }
    
    def get_all_pages(self) -> List[Dict]:
        """Get all processed pages"""
        if not self.client:
            return []
        
        results = list(
            self.pages_collection
            .find({})
            .sort('processed_date', -1)
        )
        
        for result in results:
            result['_id'] = str(result['_id'])
        
        return results
    
    def get_entry_by_id(self, entry_id: str) -> Optional[Dict]:
        """Get a specific entry by ID"""
        if not self.client:
            return None
        
        try:
            from bson.objectid import ObjectId
            result = self.dictionary_collection.find_one({'_id': ObjectId(entry_id)})
            if result:
                result['_id'] = str(result['_id'])
                
                # Convert datetime objects to strings for template rendering
                if 'created_date' in result and result['created_date']:
                    result['created_date'] = result['created_date'].isoformat() if hasattr(result['created_date'], 'isoformat') else str(result['created_date'])
                if 'processed_date' in result and result['processed_date']:
                    result['processed_date'] = result['processed_date'].isoformat() if hasattr(result['processed_date'], 'isoformat') else str(result['processed_date'])
            return result
        except Exception:
            return None
    
    def add_dictionary_from_csv(self, publication_id: str, filename: str, csv_content: str) -> Tuple[str, int]:
        """
        Add dictionary entries from CSV content
        
        Args:
            publication_id: ID of the publication
            filename: Name of the CSV file
            csv_content: Raw CSV content as string
            
        Returns:
            Tuple of (page_id, number of entries added)
        """
        if not self.client:
            return None, 0
            
        # Create a page entry for the CSV upload
        page_data = {
            'publication_id': publication_id,
            'filename': filename,
            'page_number': 1,
            'csv_content': csv_content[:1000],  # Store first 1000 chars for reference
            'processed_date': datetime.now(timezone.utc),
            'entries_extracted': 0,
            'source_type': 'csv_upload'
        }
        
        # Insert page
        result = self.pages_collection.insert_one(page_data)
        page_id = str(result.inserted_id)
        
        # Parse CSV and extract entries
        entries = self._extract_entries_from_csv(csv_content, page_id, publication_id, filename)
        
        # Update page with number of entries extracted
        self.pages_collection.update_one(
            {'_id': result.inserted_id},
            {'$set': {'entries_extracted': len(entries)}}
        )
        
        return page_id, len(entries)
    
    def _extract_entries_from_csv(self, csv_content: str, page_id: str, publication_id: str, filename: str) -> List[Dict]:
        """
        Extract dictionary entries from CSV content
        
        Args:
            csv_content: Raw CSV content
            page_id: Page database ID
            publication_id: Publication ID
            filename: Source filename
            
        Returns:
            List of extracted entries
        """
        import csv
        import io
        
        # Collections for different types
        words = []
        phrases = []
        sentences = []
        paragraphs = []
        
        try:
            # Parse CSV content - detect delimiter
            delimiter = '\t' if '\t' in csv_content else ','
            csv_reader = csv.reader(io.StringIO(csv_content), delimiter=delimiter)
            
            # Read header row to identify format
            header = next(csv_reader, None)
            if not header:
                print(f"⚠️ No header found in CSV")
                return []
            
            print(f"📋 CSV Header: {header}")
            print(f"📋 Header length: {len(header)}")
            
            # Normalize headers and build column index map
            header_lower = [h.lower().strip().replace('\ufeff', '').replace(' ', '_').replace('/', '_') for h in header]
            print(f"📋 Normalized headers: {header_lower}")
            
            col_map = {h: i for i, h in enumerate(header_lower)}
            
            # Check for new standard format: chuukese_phrase, english_translation, type, direction, definition_notes
            is_standard_format = 'chuukese_phrase' in col_map and 'english_translation' in col_map
            
            entries_processed = 0
            for row_num, row in enumerate(csv_reader, 2):
                if len(row) < 2:
                    continue
                
                if entries_processed < 3:
                    print(f"📝 Row {row_num}: {row}")
                entries_processed += 1
                
                try:
                    if is_standard_format:
                        # Standard format: chuukese_phrase, english_translation, type, grammar, search_direction, definition_notes
                        chuukese_text = row[col_map.get('chuukese_phrase', 0)].strip()
                        english_text = row[col_map.get('english_translation', 1)].strip()
                        entry_type = row[col_map.get('type', 2)].strip().lower() if len(row) > col_map.get('type', 2) else 'word'
                        grammar = row[col_map.get('grammar', 3)].strip().lower() if len(row) > col_map.get('grammar', 3) else ''
                        search_direction = row[col_map.get('search_direction', 4)].strip() if len(row) > col_map.get('search_direction', 4) else 'chk_to_en'
                        definition = row[col_map.get('definition_notes', 5)].strip() if len(row) > col_map.get('definition_notes', 5) else ''
                        
                        if not chuukese_text or not english_text:
                            continue
                        
                        # Base entry data
                        base_entry = {
                            'chuukese': chuukese_text,
                            'english': english_text,
                            'type': entry_type,
                            'grammar': grammar,
                            'search_direction': search_direction,
                            'definition': definition,
                            'page_id': page_id,
                            'publication_id': publication_id,
                            'filename': filename,
                            'line_number': row_num,
                            'source_type': 'csv_upload',
                            'created_date': datetime.now(timezone.utc)
                        }
                        
                        # Grammar abbreviation mapping table
                        grammar_mapping = {
                            'n.': 'noun', 'n': 'noun', 'noun': 'noun',
                            'v.': 'verb', 'v': 'verb', 'verb': 'verb',
                            'vt.': 'transitive verb', 'vt': 'transitive verb', 'transitive verb': 'transitive verb',
                            'vi.': 'intransitive verb', 'vi': 'intransitive verb', 'intransitive verb': 'intransitive verb',
                            'adj.': 'adjective', 'adj': 'adjective', 'adjective': 'adjective',
                            'adv.': 'adverb', 'adv': 'adverb', 'adverb': 'adverb',
                            'pron.': 'pronoun', 'pron': 'pronoun', 'pronoun': 'pronoun',
                            'prep.': 'preposition', 'prep': 'preposition', 'preposition': 'preposition',
                            'conj.': 'conjunction', 'conj': 'conjunction', 'conjunction': 'conjunction',
                            'aux.': 'auxiliary', 'aux': 'auxiliary', 'auxiliary': 'auxiliary',
                            'interj.': 'interjection', 'interj': 'interjection', 'interjection': 'interjection',
                            'det.': 'determiner', 'det': 'determiner', 'determiner': 'determiner',
                            'part.': 'particle', 'part': 'particle', 'particle': 'particle',
                            'art.': 'article', 'art': 'article', 'article': 'article',
                            'word': 'word'
                        }
                        
                        # Helper function to expand grammar abbreviations in compound types
                        def expand_grammar(grammar_str):
                            if not grammar_str:
                                return ''
                            # Check for exact match first
                            if grammar_str in grammar_mapping:
                                return grammar_mapping[grammar_str]
                            
                            # Handle compound types like "v., vt. + suffix" or "v., vt., adj. + suffix"
                            # First, separate the main part from the suffix (after +)
                            suffix_part = ''
                            main_part = grammar_str
                            if '+' in grammar_str:
                                parts = grammar_str.split('+', 1)
                                main_part = parts[0].strip()
                                suffix_part = parts[1].strip() if len(parts) > 1 else ''
                            
                            # Expand each comma-separated abbreviation in the main part
                            expanded_types = []
                            for abbrev in main_part.split(','):
                                abbrev = abbrev.strip().rstrip('.')  # Remove trailing period for matching
                                abbrev_with_dot = abbrev + '.'
                                if abbrev_with_dot in grammar_mapping:
                                    expanded_types.append(grammar_mapping[abbrev_with_dot])
                                elif abbrev in grammar_mapping:
                                    expanded_types.append(grammar_mapping[abbrev])
                                elif abbrev:  # Keep as-is if not found
                                    expanded_types.append(abbrev)
                            
                            # Combine expanded types
                            result = ', '.join(expanded_types)
                            
                            # Add suffix if present
                            if suffix_part:
                                result = f"{result} + {suffix_part}"
                            
                            return result if result else grammar_str
                        
                        # Route to appropriate collection based on type
                        # If type is a grammar type (noun, verb, etc.), treat as word and use type as grammar
                        if entry_type == 'word' or entry_type in grammar_mapping or '+' in entry_type:
                            # Map the grammar abbreviation to full form using expand_grammar
                            mapped_grammar = expand_grammar(grammar) if grammar else ''
                            # If entry_type is a grammar abbreviation or compound, use it as grammar if grammar column is empty
                            if not mapped_grammar and entry_type != 'word':
                                mapped_grammar = expand_grammar(entry_type)
                            
                            word_entry = {
                                'chuukese_word': chuukese_text.lower(),
                                'english_translation': english_text,
                                'definition': definition if definition else english_text,
                                'grammar': mapped_grammar,  # noun, verb, adjective, etc. (full form)
                                'type': 'word',  # Always 'word' for words collection
                                'search_direction': search_direction,
                                'page_id': page_id,
                                'publication_id': publication_id,
                                'filename': filename,
                                'line_number': row_num,
                                'confidence': 1.0,
                                'citation': f"{filename}:{row_num}",
                                'created_date': datetime.now(timezone.utc),
                                'source_type': 'csv_upload'
                            }
                            words.append(word_entry)
                        
                        elif entry_type == 'phrase':
                            phrase_entry = {
                                'chuukese_phrase': chuukese_text,
                                'english_translation': english_text,
                                'type': entry_type,
                                'grammar': grammar,
                                'search_direction': search_direction,
                                'definition': definition,
                                'page_id': page_id,
                                'publication_id': publication_id,
                                'filename': filename,
                                'line_number': row_num,
                                'source_type': 'csv_upload',
                                'created_date': datetime.now(timezone.utc)
                            }
                            phrases.append(phrase_entry)
                        
                        elif entry_type == 'sentence':
                            sentence_entry = {
                                'chuukese_sentence': chuukese_text,
                                'english_translation': english_text,
                                'type': entry_type,
                                'grammar': grammar,
                                'search_direction': search_direction,
                                'definition': definition,
                                'page_id': page_id,
                                'publication_id': publication_id,
                                'filename': filename,
                                'line_number': row_num,
                                'source_type': 'csv_upload',
                                'created_date': datetime.now(timezone.utc)
                            }
                            sentences.append(sentence_entry)
                        
                        elif entry_type == 'paragraph':
                            paragraph_entry = {
                                'chuukese_paragraph': chuukese_text,
                                'english_translation': english_text,
                                'type': entry_type,
                                'grammar': grammar,
                                'search_direction': search_direction,
                                'definition': definition,
                                'page_id': page_id,
                                'publication_id': publication_id,
                                'filename': filename,
                                'line_number': row_num,
                                'source_type': 'csv_upload',
                                'created_date': datetime.now(timezone.utc)
                            }
                            paragraphs.append(paragraph_entry)
                        
                        else:
                            # Default to words collection for unknown types
                            word_entry = {
                                'chuukese_word': chuukese_text.lower(),
                                'english_translation': english_text,
                                'definition': definition if definition else english_text,
                                'grammar': grammar if grammar else entry_type,
                                'type': 'word',
                                'search_direction': search_direction,
                                'page_id': page_id,
                                'publication_id': publication_id,
                                'filename': filename,
                                'line_number': row_num,
                                'confidence': 1.0,
                                'citation': f"{filename}:{row_num}",
                                'created_date': datetime.now(timezone.utc),
                                'source_type': 'csv_upload'
                            }
                            words.append(word_entry)
                    
                    else:
                        # Legacy format handling - treat as words
                        chuukese_word = row[0].strip() if len(row) > 0 else ''
                        english_translation = row[1].strip() if len(row) > 1 else ''
                        part_of_speech = row[2].strip() if len(row) > 2 else ''
                        
                        if not chuukese_word or not english_translation:
                            continue
                        
                        word_type = self._extract_word_type(part_of_speech, english_translation) if part_of_speech else None
                        
                        entry = {
                            'chuukese_word': chuukese_word.lower(),
                            'english_translation': english_translation,
                            'definition': english_translation,
                            'part_of_speech': part_of_speech,
                            'word_type': word_type,
                            'type': word_type or 'word',
                            'direction': 'chk_to_en',
                            'page_id': page_id,
                            'publication_id': publication_id,
                            'filename': filename,
                            'line_number': row_num,
                            'confidence': 1.0,
                            'citation': f"{filename}:{row_num}",
                            'created_date': datetime.now(timezone.utc),
                            'source_type': 'csv_upload'
                        }
                        words.append(entry)
                    
                except (IndexError, ValueError) as e:
                    print(f"Error parsing CSV row {row_num}: {e}")
                    continue
        
        except Exception as e:
            print(f"❌ Error parsing CSV content: {e}")
            import traceback
            traceback.print_exc()
            return []
        
        print(f"✅ Extracted: {len(words)} words, {len(phrases)} phrases, {len(sentences)} sentences, {len(paragraphs)} paragraphs")
        
        import time
        batch_size = 10  # Small batches to avoid Cosmos DB rate limiting
        all_entries = []
        
        # Insert words into dictionary_collection
        if words:
            inserted_count = self._batch_insert(self.dictionary_collection, words, batch_size, "words")
            all_entries.extend(words)
        
        # Insert phrases into phrases_collection
        if phrases:
            inserted_count = self._batch_insert(self.phrases_collection, phrases, batch_size, "phrases")
            all_entries.extend(phrases)
        
        # Insert sentences into phrases_collection (sentences are stored with phrases)
        if sentences:
            inserted_count = self._batch_insert(self.phrases_collection, sentences, batch_size, "sentences")
            all_entries.extend(sentences)
        
        # Insert paragraphs into paragraphs_collection
        if paragraphs:
            inserted_count = self._batch_insert(self.paragraphs_collection, paragraphs, batch_size, "paragraphs")
            all_entries.extend(paragraphs)
        
        return all_entries
    
    def _batch_insert(self, collection, items, batch_size, item_type):
        """Insert items in batches with rate limiting handling"""
        import time
        inserted_count = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            retries = 3
            
            while retries > 0:
                try:
                    collection.insert_many(batch, ordered=False)
                    inserted_count += len(batch)
                    print(f"  ✓ {item_type} batch {i//batch_size + 1}/{(len(items) + batch_size - 1)//batch_size} ({len(batch)} items)")
                    break
                except DuplicateKeyError:
                    for item in batch:
                        try:
                            collection.insert_one(item)
                            inserted_count += 1
                        except DuplicateKeyError:
                            pass  # Skip duplicates
                        except Exception as e:
                            print(f"  ⚠️ Error inserting {item_type}: {e}")
                    break
                except Exception as e:
                    error_str = str(e)
                    if '16500' in error_str or 'RetryAfterMs' in error_str:
                        retries -= 1
                        print(f"  ⏳ Rate limited, waiting 1s ({retries} retries left)")
                        time.sleep(1.0)
                    else:
                        print(f"  ❌ Error inserting {item_type} batch: {e}")
                        break
            
            time.sleep(0.2)
        
        print(f"✅ Inserted {inserted_count} {item_type} into database")
        return inserted_count
    
    def clear_database(self) -> bool:
        """
        Clear all dictionary entries, pages, and publications from the database
        
        Returns:
            Success status
        """
        if not self.client:
            print("Database not available for clearing")
            return False
        
        try:
            # Clear all collections
            self.dictionary_collection.delete_many({})
            self.pages_collection.delete_many({})
            
            # Also clear publications metadata
            from .publication_manager import PublicationManager
            pub_manager = PublicationManager()
            pub_manager.clear_publications()
            
            print("Database and publications cleared successfully")
            return True
        except Exception as e:
            print(f"Error clearing database: {e}")
            return False

    # ===== WORDS COLLECTION METHODS =====
    
    def add_word(self, chuukese: str, english_translation: str, grammar: str = None, **kwargs) -> Optional[str]:
        """
        Add a word to the words collection
        
        Args:
            chuukese: Chuukese word
            english_translation: English translation
            grammar: Grammar type (verb, noun, adjective, etc.)
            **kwargs: Additional fields
            
        Returns:
            Word ID if successful
        """
        if not self.client:
            return None
            
        word_data = {
            '_id': f"word_{chuukese}_{hash(english_translation) & 0x7FFFFFFF}",
            'chuukese': chuukese.strip(),
            'english_translation': english_translation.strip(),
            'grammar': grammar or 'unknown',
            'date_added': datetime.now(timezone.utc),
            'date_modified': datetime.now(timezone.utc),
            **kwargs
        }
        
        try:
            result = self.words_collection.insert_one(word_data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error adding word: {e}")
            return None
    
    def search_words(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search words by Chuukese word or English translation
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of matching word documents
        """
        if not self.client:
            return []
            
        try:
            # Use regex search for MongoDB API
            results = list(self.words_collection.find({
                "$or": [
                    {"chuukese": {"$regex": query, "$options": "i"}},
                    {"english_translation": {"$regex": query, "$options": "i"}}
                ]
            }).limit(limit))
                
            return results
        except Exception as e:
            print(f"Error searching words: {e}")
            return []
    
    def update_word(self, word_id: str, **updates) -> bool:
        """
        Update a word entry
        
        Args:
            word_id: Word ID to update
            **updates: Fields to update
            
        Returns:
            Success status
        """
        if not self.client:
            return False
            
        updates['date_modified'] = datetime.now(timezone.utc)
        
        try:
            if self.db_type == 'cosmos':
                # Read current item
                current_item = self.words_collection.read_item(item=word_id, partition_key=word_id)
                current_item.update(updates)
                self.words_collection.replace_item(item=word_id, body=current_item)
            else:
                self.words_collection.update_one(
                    {"id": word_id},
                    {"$set": updates}
                )
            return True
        except Exception as e:
            print(f"Error updating word: {e}")
            return False
    
    # ===== PHRASES COLLECTION METHODS =====
    
    def add_phrase(self, chuukese_phrase: str, english_translation: str, source: str = None, **kwargs) -> Optional[str]:
        """
        Add a phrase to the phrases collection
        
        Args:
            chuukese_phrase: Chuukese phrase
            english_translation: English translation
            source: Source of the phrase
            **kwargs: Additional fields
            
        Returns:
            Phrase ID if successful
        """
        if not self.client:
            return None
            
        phrase_data = {
            '_id': f"phrase_{hash(chuukese_phrase) & 0x7FFFFFFF}_{hash(english_translation) & 0x7FFFFFFF}",
            'chuukese_phrase': chuukese_phrase.strip(),
            'english_translation': english_translation.strip(),
            'source': source or 'unknown',
            'date_added': datetime.now(timezone.utc),
            'date_modified': datetime.now(timezone.utc),
            **kwargs
        }
        
        try:
            result = self.phrases_collection.insert_one(phrase_data)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error adding phrase: {e}")
            return None
    
    def search_phrases(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search phrases by Chuukese phrase or English translation
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of matching phrase documents
        """
        if not self.client:
            return []
            
        try:
            if self.db_type == 'cosmos':
                # Cosmos DB SQL query
                sql_query = """
                SELECT * FROM c 
                WHERE CONTAINS(c.chuukese_phrase, @query, true) 
                   OR CONTAINS(c.english_translation, @query, true)
                   OR CONTAINS(c.source, @query, true)
                ORDER BY c.date_added DESC
                """
                results = list(self.phrases_collection.query_items(
                    query=sql_query,
                    parameters=[{"name": "@query", "value": query}],
                    enable_cross_partition_query=True,
                    max_item_count=limit
                ))
            else:
                # MongoDB query
                results = list(self.phrases_collection.find(
                    {"$or": [
                        {"chuukese_phrase": {"$regex": query, "$options": "i"}},
                        {"english_translation": {"$regex": query, "$options": "i"}},
                        {"source": {"$regex": query, "$options": "i"}}
                    ]}
                ).limit(limit))
                
            return results
        except Exception as e:
            print(f"Error searching phrases: {e}")
            return []
    
    def update_phrase(self, phrase_id: str, **updates) -> bool:
        """
        Update a phrase entry
        
        Args:
            phrase_id: Phrase ID to update
            **updates: Fields to update
            
        Returns:
            Success status
        """
        if not self.client:
            return False
            
        updates['date_modified'] = datetime.now(timezone.utc)
        
        try:
            if self.db_type == 'cosmos':
                # Read current item
                current_item = self.phrases_collection.read_item(item=phrase_id, partition_key=phrase_id)
                current_item.update(updates)
                self.phrases_collection.replace_item(item=phrase_id, body=current_item)
            else:
                self.phrases_collection.update_one(
                    {"id": phrase_id},
                    {"$set": updates}
                )
            return True
        except Exception as e:
            print(f"Error updating phrase: {e}")
            return False
    
    # ===== PARAGRAPHS COLLECTION METHODS =====
    
    def add_paragraph(self, chuukese_paragraph: str, english_paragraph: str, source: str = None, **kwargs) -> Optional[str]:
        """
        Add a paragraph pair to the paragraphs collection
        
        Args:
            chuukese_paragraph: Chuukese paragraph
            english_paragraph: Corresponding English paragraph
            source: Source of the paragraph
            **kwargs: Additional fields
            
        Returns:
            Paragraph ID if successful
        """
        if not self.client:
            return None
            
        paragraph_data = {
            'id': f"paragraph_{hash(chuukese_paragraph) & 0x7FFFFFFF}_{hash(english_paragraph) & 0x7FFFFFFF}",
            'chuukese_paragraph': chuukese_paragraph.strip(),
            'english_paragraph': english_paragraph.strip(),
            'source': source or 'unknown',
            'date_added': datetime.now(timezone.utc),
            'date_modified': datetime.now(timezone.utc),
            **kwargs
        }
        
        try:
            if self.db_type == 'cosmos':
                self.paragraphs_collection.create_item(body=paragraph_data)
            else:
                self.paragraphs_collection.insert_one(paragraph_data)
            return paragraph_data['id']
        except Exception as e:
            print(f"Error adding paragraph: {e}")
            return None
    
    def search_paragraphs(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search paragraphs by content or source
        
        Args:
            query: Search query
            limit: Maximum results to return
            
        Returns:
            List of matching paragraph documents
        """
        if not self.client:
            return []
            
        try:
            if self.db_type == 'cosmos':
                # Cosmos DB SQL query
                sql_query = """
                SELECT * FROM c 
                WHERE CONTAINS(c.chuukese_paragraph, @query, true) 
                   OR CONTAINS(c.english_paragraph, @query, true)
                   OR CONTAINS(c.source, @query, true)
                ORDER BY c.date_added DESC
                """
                results = list(self.paragraphs_collection.query_items(
                    query=sql_query,
                    parameters=[{"name": "@query", "value": query}],
                    enable_cross_partition_query=True,
                    max_item_count=limit
                ))
            else:
                # MongoDB query
                results = list(self.paragraphs_collection.find(
                    {"$or": [
                        {"chuukese_paragraph": {"$regex": query, "$options": "i"}},
                        {"english_paragraph": {"$regex": query, "$options": "i"}},
                        {"source": {"$regex": query, "$options": "i"}}
                    ]}
                ).limit(limit))
                
            return results
        except Exception as e:
            print(f"Error searching paragraphs: {e}")
            return []
    
    def update_paragraph(self, paragraph_id: str, **updates) -> bool:
        """
        Update a paragraph entry
        
        Args:
            paragraph_id: Paragraph ID to update
            **updates: Fields to update
            
        Returns:
            Success status
        """
        if not self.client:
            return False
            
        updates['date_modified'] = datetime.now(timezone.utc)
        
        try:
            if self.db_type == 'cosmos':
                # Read current item
                current_item = self.paragraphs_collection.read_item(item=paragraph_id, partition_key=paragraph_id)
                current_item.update(updates)
                self.paragraphs_collection.replace_item(item=paragraph_id, body=current_item)
            else:
                self.paragraphs_collection.update_one(
                    {"id": paragraph_id},
                    {"$set": updates}
                )
            return True
        except Exception as e:
            print(f"Error updating paragraph: {e}")
            return False
    
    # ===== BULK OPERATIONS =====
    
    def bulk_add_words(self, words_data: List[Dict]) -> int:
        """
        Bulk add multiple words
        
        Args:
            words_data: List of word dictionaries with chuukese, english_translation, grammar fields
            
        Returns:
            Number of words successfully added
        """
        if not self.client or not words_data:
            return 0
            
        added_count = 0
        for word_data in words_data:
            if self.add_word(**word_data):
                added_count += 1
                
        return added_count
    
    def bulk_add_phrases(self, phrases_data: List[Dict]) -> int:
        """
        Bulk add multiple phrases
        
        Args:
            phrases_data: List of phrase dictionaries with chuukese_phrase, english_translation, source fields
            
        Returns:
            Number of phrases successfully added
        """
        if not self.client or not phrases_data:
            return 0
            
        added_count = 0
        for phrase_data in phrases_data:
            if self.add_phrase(**phrase_data):
                added_count += 1
                
        return added_count
    
    def bulk_add_paragraphs(self, paragraphs_data: List[Dict]) -> int:
        """
        Bulk add multiple paragraphs
        
        Args:
            paragraphs_data: List of paragraph dictionaries with chuukese_paragraph, english_paragraph, source fields
            
        Returns:
            Number of paragraphs successfully added
        """
        if not self.client or not paragraphs_data:
            return 0
            
        added_count = 0
        for paragraph_data in paragraphs_data:
            if self.add_paragraph(**paragraph_data):
                added_count += 1
                
        return added_count