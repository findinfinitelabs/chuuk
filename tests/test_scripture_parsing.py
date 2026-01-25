"""
Test scripture reference parsing patterns for the Translation Game.
These patterns ensure that scripture references stay attached to their sentences.
"""
import re
import sys
import os
import pytest

# Add the project root to the path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.scripture_parser import (
    get_scripture_reference_pattern,
    get_book_names_pattern,
    protect_scripture_references,
    restore_scripture_references
)

# Get the pattern from the utility (loaded from config file)
ANY_SCRIPTURE_PATTERN = get_scripture_reference_pattern()


class TestScripturePatternMatching:
    """Test scripture reference pattern matching."""
    
    def test_chuukese_abbreviation(self):
        """Test Chuukese scripture abbreviation."""
        text = 'See Féf. 5:42 for this.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) == 1
        assert 'Féf. 5:42' in matches[0]
    
    def test_english_abbreviation(self):
        """Test English scripture abbreviation."""
        text = 'Read 1 Cor. 15:33 for wisdom.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) == 1
        assert '1 Cor. 15:33' in matches[0]
    
    def test_full_book_name(self):
        """Test full book name (not abbreviated)."""
        text = 'Read 1 Corinthians 15:33 for wisdom.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) == 1
        assert '1 Corinthians 15:33' in matches[0]
    
    def test_acts_full_name(self):
        """Test Acts (full name, no abbreviation needed)."""
        text = 'See Acts 5:42 in the Bible.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) == 1
        assert 'Acts 5:42' in matches[0]
    
    def test_verse_range_comma(self):
        """Test scripture with comma-separated verses."""
        text = 'See 1 Cor. 13:4, 7 for love.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) == 1
        assert '1 Cor. 13:4, 7' in matches[0]
    
    def test_verse_range_hyphen(self):
        """Test scripture with verse range using hyphen."""
        text = 'Acts 19:8-10 describes Paul.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) == 1
        assert 'Acts 19:8-10' in matches[0]
    
    def test_multiple_refs_semicolon(self):
        """Test multiple scripture references separated by semicolons."""
        text = 'See Féf. 10:42; 1 Kor. 9:22, 23 for examples.'
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        assert len(matches) >= 1


class TestSentenceSplitting:
    """Test that sentences are split correctly while preserving scripture refs."""
    
    def protect_and_split(self, text):
        """Simulate the protection and splitting logic from app.py."""
        # Remove zero-width characters
        text = re.sub(r'[\u200b\u200c\u200d\u00ad\ufeff\u2060]', '', text)
        
        # Use the utility functions from scripture_parser
        text_protected, protected_refs = protect_scripture_references(text)
        
        # Split on sentence boundaries but not at placeholders
        sent_list = re.split(r'(?<=[.!?])\s+(?![<])', text_protected)
        
        # Restore protected refs using utility function
        result = []
        for sent in sent_list:
            sent = restore_scripture_references(sent, protected_refs)
            result.append(sent.strip())
        
        return result
    
    def test_keeps_emdash_scripture_attached(self):
        """Test that em-dash scripture stays with its sentence."""
        text = 'First sentence here. Second sentence.—Féf. 5:42. Third sentence here.'
        sentences = self.protect_and_split(text)
        
        # Second sentence should include the scripture reference
        assert any('Second sentence.—Féf. 5:42' in s for s in sentences)
    
    def test_inline_scripture_not_split(self):
        """Test that inline scripture references don't cause sentence splits."""
        text = 'Do not assume. (1 Cor. 13:4, 7) Instead, balance perseverance.—1 Cor. 9:26.'
        sentences = self.protect_and_split(text)
        
        # The scripture references should not split the text incorrectly
        full_text = ' '.join(sentences)
        assert '1 Cor. 13:4, 7' in full_text
        assert '1 Cor. 9:26' in full_text
    
    def test_full_book_name_not_split(self):
        """Test that full book names don't cause incorrect splits."""
        text = 'Read 1 Corinthians 15:33 carefully. It has wisdom.'
        sentences = self.protect_and_split(text)
        
        # Should have 2 sentences
        assert len(sentences) == 2
        assert '1 Corinthians 15:33' in sentences[0]
    
    def test_problematic_sentence(self):
        """Test the specific problematic sentence from the user."""
        text = (
            'Do not quickly assume that a person who is rarely at home or is often busy '
            'is not interested. (1 Cor. 13:4, 7) Instead, balance perseverance with making '
            'wise use of your time.—1 Cor. 9:26.'
        )
        sentences = self.protect_and_split(text)
        
        # The scripture "1 Cor." should NOT be split from its verse numbers
        full_text = ' '.join(sentences)
        assert '1 Cor. 13:4, 7' in full_text
        assert '1 Cor. 9:26' in full_text
        
        # Should NOT see fragments like ". 13:4" alone
        for sent in sentences:
            assert not sent.startswith('. 13')
            assert not sent.startswith('13:')
    
    def test_complex_paragraph(self):
        """Test a complex paragraph from wol.jw.org."""
        text = (
            'Rese úkútiw le sópweeló ar asukul me esilefeili ewe kapas allim.—Féf. 5:42. '
            'Pwata sia silei pwe Paul a tinikken lón an afalafala ewe kapas allim? '
            'A lamot sipwe awora ach fansoun me achocho pwe epwe fisiéch ach liwiniti.'
        )
        sentences = self.protect_and_split(text)
        
        # First sentence should include the scripture
        assert any('—Féf. 5:42' in s for s in sentences)
        # Should have 3 sentences total
        assert len(sentences) == 3


if __name__ == '__main__':
    print('Testing scripture reference pattern:')
    print('=' * 60)
    
    test_texts = [
        'See Féf. 5:42 for this.',
        'Read 1 Cor. 15:33 for wisdom.',
        'Read 1 Corinthians 15:33 for wisdom.',
        'See Acts 5:42 in the Bible.',
        'See 1 Cor. 13:4, 7 for love.',
        'Acts 19:8-10 describes Paul.',
    ]
    
    for text in test_texts:
        matches = re.findall(ANY_SCRIPTURE_PATTERN, text)
        print(f'Text: {text}')
        print(f'Matches: {matches}')
        print()
    
    print('Testing sentence splitting with protection:')
    print('=' * 60)
    
    test = TestSentenceSplitting()
    
    # Test the problematic sentence
    problem_text = (
        'Do not quickly assume that a person who is rarely at home or is often busy '
        'is not interested. (1 Cor. 13:4, 7) Instead, balance perseverance with making '
        'wise use of your time.—1 Cor. 9:26.'
    )
    sentences = test.protect_and_split(problem_text)
    print(f'Original: {problem_text[:80]}...')
    print(f'Split into {len(sentences)} sentences:')
    for i, s in enumerate(sentences):
        print(f'  {i+1}. {s}')
    
    print()
    print('Checking for splits:')
    full_text = ' '.join(sentences)
    print(f'  "1 Cor. 13:4, 7" intact: {"1 Cor. 13:4, 7" in full_text}')
    print(f'  "1 Cor. 9:26" intact: {"1 Cor. 9:26" in full_text}')
