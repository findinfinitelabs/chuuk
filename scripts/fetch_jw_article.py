#!/usr/bin/env python3
"""
Fetch and parse articles from wol.jw.org in English and Chuukese.
Extract parallel sentences for the translation matching game.
"""
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

def get_language_url(english_url, lang_code='tr'):
    """Convert English URL to another language version."""
    # wol.jw.org URLs typically have format: /en/wol/... or /wol/...
    # Change 'en' to target language code (tr for Chuukese/Trukese)
    if '/en/wol/' in english_url:
        return english_url.replace('/en/wol/', f'/{lang_code}/wol/')
    elif '/wol/' in english_url and '/en/' not in english_url:
        # Some URLs might not have language code explicitly
        parsed = urlparse(english_url)
        return f"{parsed.scheme}://{parsed.netloc}/{lang_code}{parsed.path}{parsed.query}"
    return None

def fetch_article_content(url):
    """Fetch article content from wol.jw.org."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_article_sentences(html_content):
    """Parse sentences from article HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find main article content - wol.jw.org typically uses specific classes
    # Common selectors: article, .article, #article, .bodyTxt
    article_content = soup.find('article') or soup.find('div', class_='bodyTxt') or soup.find('div', id='article')
    
    if not article_content:
        return [], None
    
    # Get article title
    title = soup.find('h1')
    title_text = title.get_text(strip=True) if title else "Untitled"
    
    # Extract paragraphs
    paragraphs = article_content.find_all(['p', 'li'])
    
    sentences = []
    for idx, para in enumerate(paragraphs):
        # Get text, preserving some structure
        text = para.get_text(separator=' ', strip=True)
        
        # Skip very short text (likely not sentences)
        if len(text) < 15:
            continue
        
        # Skip if it's mostly numbers or special characters
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in text) / len(text) if text else 0
        if alpha_ratio < 0.5:
            continue
        
        # Split into sentences
        sent_list = re.split(r'(?<=[.!?])\s+', text)
        
        for sent in sent_list:
            sent = sent.strip()
            if len(sent) > 20:  # Minimum sentence length
                sentences.append({
                    'id': len(sentences) + 1,
                    'text': sent,
                    'paragraph_index': idx
                })
    
    return sentences, title_text

def fetch_parallel_articles(english_url):
    """Fetch both English and Chuukese versions of an article."""
    print(f"📖 Fetching English article from: {english_url}")
    
    # Fetch English content
    english_html = fetch_article_content(english_url)
    if not english_html:
        return None
    
    english_sentences, english_title = parse_article_sentences(english_html)
    print(f"   Found {len(english_sentences)} English sentences")
    print(f"   Title: {english_title}")
    
    # Get Chuukese URL
    chuukese_url = get_language_url(english_url, 'tr')
    if not chuukese_url:
        print("   Could not determine Chuukese URL")
        return None
    
    print(f"\n📖 Fetching Chuukese article from: {chuukese_url}")
    
    # Fetch Chuukese content
    chuukese_html = fetch_article_content(chuukese_url)
    if not chuukese_html:
        return None
    
    chuukese_sentences, chuukese_title = parse_article_sentences(chuukese_html)
    print(f"   Found {len(chuukese_sentences)} Chuukese sentences")
    print(f"   Title: {chuukese_title}")
    
    return {
        'english': {
            'url': english_url,
            'title': english_title,
            'sentences': english_sentences
        },
        'chuukese': {
            'url': chuukese_url,
            'title': chuukese_title,
            'sentences': chuukese_sentences
        },
        'metadata': {
            'source': 'wol.jw.org',
            'english_url': english_url,
            'chuukese_url': chuukese_url
        }
    }

if __name__ == '__main__':
    # Test with a sample URL
    test_url = input("Enter wol.jw.org article URL: ")
    result = fetch_parallel_articles(test_url)
    
    if result:
        print("\n✅ Successfully fetched articles!")
        print(f"English: {result['english']['title']} ({len(result['english']['sentences'])} sentences)")
        print(f"Chuukese: {result['chuukese']['title']} ({len(result['chuukese']['sentences'])} sentences)")
        
        # Preview
        print("\n📝 Preview (first 2 English sentences):")
        for sent in result['english']['sentences'][:2]:
            print(f"   {sent['id']}. {sent['text'][:100]}...")
        
        print("\n📝 Preview (first 2 Chuukese sentences):")
        for sent in result['chuukese']['sentences'][:2]:
            print(f"   {sent['id']}. {sent['text'][:100]}...")
    else:
        print("\n❌ Failed to fetch articles")
