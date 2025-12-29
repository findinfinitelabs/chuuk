#!/usr/bin/env python3
"""
Extract clean text from .jwpub files (JW Library publication format).
These are ZIP archives containing a SQLite database with compressed HTML content.
"""
import json
import re
import sqlite3
import zlib
from pathlib import Path
from html import unescape
from html.parser import HTMLParser

class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML, removing tags."""
    def __init__(self):
        super().__init__()
        self.text = []
        
    def handle_data(self, data):
        self.text.append(data)
        
    def get_text(self):
        return ''.join(self.text)

def extract_text_from_jwpub(jwpub_path):
    """Extract text content from a .jwpub database."""
    db_path = jwpub_path
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all documents with content
    cursor.execute("""
        SELECT Title, Content, Type 
        FROM Document 
        WHERE Content IS NOT NULL 
        ORDER BY DocumentId
    """)
    
    all_text = []
    for title, content_blob, doc_type in cursor.fetchall():
        if content_blob:
            try:
                # Try different decompression methods
                html_content = None
                
                # Try zlib
                try:
                    html_content = zlib.decompress(content_blob).decode('utf-8')
                except:
                    pass
                
                # Try raw decode (might not be compressed)
                if not html_content:
                    try:
                        html_content = content_blob.decode('utf-8')
                    except:
                        pass
                
                # Try gzip
                if not html_content:
                    import gzip
                    try:
                        html_content = gzip.decompress(content_blob).decode('utf-8')
                    except:
                        pass
                
                if not html_content:
                    print(f"Could not decompress: {title}")
                    continue
                
                # Extract text from HTML
                parser = HTMLTextExtractor()
                parser.feed(html_content)
                text = parser.get_text()
                
                # Clean up the text
                text = unescape(text)  # Convert HTML entities
                text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
                text = text.strip()
                
                if text and len(text) > 20:
                    all_text.append(text)
                    
            except Exception as e:
                print(f"Error processing document '{title}': {e}")
                continue
    
    conn.close()
    return '\n\n'.join(all_text)

def split_into_sentences(text):
    """Split text into sentences with better quality filtering."""
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    cleaned = []
    for sentence in sentences:
        sentence = sentence.strip()
        
        # Skip if too short
        if len(sentence) < 25:
            continue
        
        # Skip if it's mostly non-alphabetic
        alpha_chars = sum(c.isalpha() or c.isspace() for c in sentence)
        if alpha_chars < len(sentence) * 0.65:
            continue
        
        # Skip if no spaces (corrupted)
        if ' ' not in sentence:
            continue
        
        # Skip URLs, copyright notices, etc.
        lower_sent = sentence.lower()
        if any(pattern in lower_sent for pattern in [
            'http://', 'https://', 'www.', '.org/', '.com/', 
            '©', 'copyright', 'jw.org', 'watchtower'
        ]):
            continue
        
        # Skip if mostly uppercase (headers)
        alpha_only = [c for c in sentence if c.isalpha()]
        if alpha_only and sum(c.isupper() for c in alpha_only) > len(alpha_only) * 0.6:
            continue
        
        # Skip table of contents entries and navigation text
        if any(word in lower_sent for word in ['lesson', 'section', 'appendix', 'page']) and len(sentence) < 50:
            continue
        
        cleaned.append(sentence)
    
    return cleaned

def main():
    # Paths
    base_dir = Path(__file__).parent.parent
    brochures_dir = base_dir / 'data' / 'brochures'
    extracted_dir = brochures_dir / 'lmd_E_extracted' / 'contents_extracted'
    output_file = base_dir / 'data' / 'brochure_sentences.json'
    
    english_db = extracted_dir / 'lmd_E.db'
    
    # Check if we need to extract the .jwpub first
    if not english_db.exists():
        print("Database not found. Please extract lmd_E.jwpub first")
        return
    
    # Also check for Chuukese version
    chuukese_extracted = brochures_dir / 'lmd_TE_extracted' / 'contents_extracted'
    chuukese_db = chuukese_extracted / 'lmd_TE.db'
    
    # Extract Chuukese .jwpub if needed
    if not chuukese_db.exists():
        print("📦 Extracting Chuukese .jwpub...")
        import subprocess
        chuukese_jwpub = brochures_dir / 'lmd_TE.jwpub'
        if chuukese_jwpub.exists():
            chuukese_extracted.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['unzip', '-q', str(chuukese_jwpub), '-d', str(chuukese_extracted.parent)])
            subprocess.run(['unzip', '-q', str(chuukese_extracted.parent / 'contents'), '-d', str(chuukese_extracted)])
    
    print("📖 Extracting text from English database...")
    english_text = extract_text_from_jwpub(english_db)
    english_sentences = split_into_sentences(english_text)
    print(f"   Found {len(english_sentences)} English sentences")
    
    print("📖 Extracting text from Chuukese database...")
    chuukese_text = extract_text_from_jwpub(chuukese_db)
    chuukese_sentences = split_into_sentences(chuukese_text)
    print(f"   Found {len(chuukese_sentences)} Chuukese sentences")
    
    # Create data structure
    data = {
        'english': [{'id': i+1, 'text': sent} for i, sent in enumerate(english_sentences)],
        'chuukese': [{'id': i+1, 'text': sent} for i, sent in enumerate(chuukese_sentences)],
        'metadata': {
            'source': 'lmd brochures (jwpub format)',
            'english_file': 'lmd_E.jwpub',
            'chuukese_file': 'lmd_TE.jwpub',
            'total_english': len(english_sentences),
            'total_chuukese': len(chuukese_sentences),
            'extraction_method': 'SQLite database with zlib decompression'
        }
    }
    
    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved sentences to {output_file}")
    print(f"   English: {len(english_sentences)} sentences")
    print(f"   Chuukese: {len(chuukese_sentences)} sentences")
    
    # Preview
    print("\n📝 Preview (first 3 English sentences):")
    for sent in english_sentences[:3]:
        print(f"   - {sent[:100]}...")
    
    print("\n📝 Preview (first 3 Chuukese sentences):")
    for sent in chuukese_sentences[:3]:
        print(f"   - {sent[:100]}...")

if __name__ == '__main__':
    main()
