#!/usr/bin/env python3
"""
Extract sentences from English and Chuukese brochure PDFs.
Splits text into sentences and saves to JSON for the translation matching game.
"""
import json
import re
from pathlib import Path
try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'pdfplumber'])
    import pdfplumber

def extract_text_from_pdf(pdf_path):
    """Extract all text from a PDF file."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def clean_text(text):
    """Clean extracted PDF text from encoding issues and formatting problems."""
    # Remove (cid:X) patterns - these are character ID references that failed to decode
    text = re.sub(r'\(cid:\d+\)', '', text)
    
    # Remove excessive underscores and dots (fill-in-the-blank sections)
    text = re.sub(r'_{3,}', ' ', text)
    text = re.sub(r'\.{3,}', '...', text)
    
    # Fix missing spaces before capital letters (e.g., "Father'sCareforUs" -> "Father's Care for Us")
    # But preserve acronyms like "NASA" or "USA"
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    
    # Fix missing spaces after punctuation
    text = re.sub(r'([.!?,;:])([A-Z])', r'\1 \2', text)
    
    # Fix missing spaces around "and" when it's jammed between words
    text = re.sub(r'([a-z])(and)([A-Z])', r'\1 and \2', text)
    
    # Fix common word concatenations
    text = re.sub(r'([a-z])(the|for|from|with|about|that|this|into|onto)([A-Z])', r'\1 \2 \3', text)
    
    # Remove very long sequences of repeated characters (formatting artifacts)
    text = re.sub(r'(.)\1{10,}', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def split_into_sentences(text):
    """Split text into sentences, cleaning and filtering."""
    # First clean the text
    text = clean_text(text)
    
    # Split on sentence boundaries (., !, ?)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    # Clean and filter sentences
    cleaned = []
    for sentence in sentences:
        sentence = sentence.strip()
        
        # Skip if too short
        if len(sentence) < 20:
            continue
        
        # Skip if it's mostly non-alphabetic characters
        alpha_chars = sum(c.isalpha() or c.isspace() for c in sentence)
        if alpha_chars < len(sentence) * 0.6:
            continue
        
        # Skip if it has no spaces (corrupted text like "onwhatsimpledetaildidhefocus")
        if ' ' not in sentence:
            continue
        
        # Check for long words without spaces (likely corrupted)
        # If we find a word longer than 30 chars, probably corrupted
        words = sentence.split()
        has_long_word = any(len(word) > 30 for word in words)
        if has_long_word:
            continue
        
        # Skip URLs, emails, copyright notices
        lower_sent = sentence.lower()
        if any(pattern in lower_sent for pattern in ['http://', 'https://', 'www.', '.org/', '.com/', '©', 'copyright', 'licensed under']):
            continue
        
        # Skip if mostly uppercase (headers/artifacts)
        alpha_only = [c for c in sentence if c.isalpha()]
        if alpha_only and sum(c.isupper() for c in alpha_only) > len(alpha_only) * 0.7:
            continue
        
        # Skip sentences that look like spacing artifacts (lots of single letters)
        single_letter_words = sum(1 for word in words if len(word) == 1 and word.isalpha())
        if single_letter_words > len(words) * 0.3:
            continue
        
        cleaned.append(sentence)
    
    return cleaned

def main():
    # Paths
    base_dir = Path(__file__).parent.parent
    brochures_dir = base_dir / 'data' / 'brochures'
    output_file = base_dir / 'data' / 'brochure_sentences.json'
    
    english_pdf = brochures_dir / 'lmd_E.pdf'
    chuukese_pdf = brochures_dir / 'lmd_TE.pdf'
    
    # Check files exist
    if not english_pdf.exists():
        print(f"Error: {english_pdf} not found")
        return
    if not chuukese_pdf.exists():
        print(f"Error: {chuukese_pdf} not found")
        return
    
    print("📖 Extracting text from English brochure...")
    english_text = extract_text_from_pdf(english_pdf)
    english_sentences = split_into_sentences(english_text)
    print(f"   Found {len(english_sentences)} English sentences")
    
    print("📖 Extracting text from Chuukese brochure...")
    chuukese_text = extract_text_from_pdf(chuukese_pdf)
    chuukese_sentences = split_into_sentences(chuukese_text)
    print(f"   Found {len(chuukese_sentences)} Chuukese sentences")
    
    # Create data structure
    data = {
        'english': [{'id': i+1, 'text': sent} for i, sent in enumerate(english_sentences)],
        'chuukese': [{'id': i+1, 'text': sent} for i, sent in enumerate(chuukese_sentences)],
        'metadata': {
            'source': 'lmd brochures',
            'english_file': 'lmd_E.pdf',
            'chuukese_file': 'lmd_TE.pdf',
            'total_english': len(english_sentences),
            'total_chuukese': len(chuukese_sentences)
        }
    }
    
    # Save to JSON
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Saved sentences to {output_file}")
    print(f"   English: {len(english_sentences)} sentences")
    print(f"   Chuukese: {len(chuukese_sentences)} sentences")
    
    # Preview first few sentences
    print("\n📝 Preview (first 3 English sentences):")
    for sent in english_sentences[:3]:
        print(f"   - {sent[:80]}...")
    
    print("\n📝 Preview (first 3 Chuukese sentences):")
    for sent in chuukese_sentences[:3]:
        print(f"   - {sent[:80]}...")

if __name__ == '__main__':
    main()
