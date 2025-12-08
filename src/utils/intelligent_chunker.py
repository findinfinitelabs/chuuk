#!/usr/bin/env python3
"""
Intelligent Text Chunking for Large Documents
==============================================

Smart text chunking that preserves semantic meaning, handles multiple
languages, respects document structure, and optimizes for AI training.
"""

import re
import math
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChunkType(Enum):
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"
    FIXED_SIZE = "fixed_size"
    SLIDING_WINDOW = "sliding_window"

@dataclass
class TextChunk:
    """Represents a chunk of text with metadata"""
    content: str
    start_position: int
    end_position: int
    chunk_id: str
    chunk_type: ChunkType
    metadata: Dict[str, any]
    overlap_with_previous: int = 0
    overlap_with_next: int = 0
    
    def __len__(self):
        return len(self.content)
    
    @property
    def word_count(self):
        return len(self.content.split())

class IntelligentTextChunker:
    """
    Advanced text chunker that intelligently segments large documents
    while preserving semantic coherence and document structure
    """
    
    def __init__(self, 
                 max_chunk_size: int = 512,
                 min_chunk_size: int = 50,
                 overlap_ratio: float = 0.1,
                 preserve_sentences: bool = True,
                 preserve_paragraphs: bool = True):
        """
        Initialize the text chunker
        
        Args:
            max_chunk_size: Maximum tokens/characters per chunk
            min_chunk_size: Minimum tokens/characters per chunk
            overlap_ratio: Ratio of overlap between chunks (0.0-0.5)
            preserve_sentences: Try to keep sentences intact
            preserve_paragraphs: Try to keep paragraphs intact
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_ratio = overlap_ratio
        self.preserve_sentences = preserve_sentences
        self.preserve_paragraphs = preserve_paragraphs
        
        # Language-aware sentence boundaries
        self.sentence_endings = {
            'english': ['.', '!', '?', ';'],
            'chuukese': ['.', '!', '?'],  # May need adjustment for Chuukese
            'general': ['.', '!', '?', ';', '。', '！', '？']  # Multi-language
        }
        
        # Structure markers for intelligent chunking
        self.structure_markers = {
            'heading': re.compile(r'^#{1,6}\s+.+$|^[A-Z][A-Z\s]+$', re.MULTILINE),
            'list_item': re.compile(r'^\s*[-*•]\s+|^\s*\d+\.\s+', re.MULTILINE),
            'dictionary_entry': re.compile(r'^[^\s]+\s+[-–—]\s+.+$', re.MULTILINE),
            'paragraph_break': re.compile(r'\n\s*\n'),
            'page_break': re.compile(r'page\s+\d+|\f|\n\s*---\s*\n', re.IGNORECASE)
        }
        
        # Semantic boundary indicators
        self.semantic_indicators = {
            'topic_change': ['however', 'meanwhile', 'furthermore', 'in contrast', 'on the other hand'],
            'continuation': ['moreover', 'additionally', 'also', 'furthermore', 'similarly'],
            'conclusion': ['therefore', 'thus', 'in conclusion', 'finally', 'to sum up'],
            'example': ['for example', 'for instance', 'such as', 'namely', 'specifically']
        }
    
    def chunk_document(self, text: str, chunk_type: ChunkType = ChunkType.SEMANTIC) -> List[TextChunk]:
        """
        Chunk a document using the specified strategy
        
        Args:
            text: Input text to chunk
            chunk_type: Chunking strategy to use
            
        Returns:
            List of TextChunk objects
        """
        logger.info(f"🔪 Chunking document ({len(text)} chars) using {chunk_type.value} strategy")
        
        if chunk_type == ChunkType.SEMANTIC:
            chunks = self._semantic_chunking(text)
        elif chunk_type == ChunkType.STRUCTURAL:
            chunks = self._structural_chunking(text)
        elif chunk_type == ChunkType.FIXED_SIZE:
            chunks = self._fixed_size_chunking(text)
        elif chunk_type == ChunkType.SLIDING_WINDOW:
            chunks = self._sliding_window_chunking(text)
        else:
            raise ValueError(f"Unsupported chunk type: {chunk_type}")
        
        # Post-process chunks
        chunks = self._optimize_chunks(chunks)
        chunks = self._add_overlap(chunks)
        
        logger.info(f"✅ Created {len(chunks)} chunks (avg size: {sum(len(c) for c in chunks) / len(chunks):.0f} chars)")
        
        return chunks
    
    def _semantic_chunking(self, text: str) -> List[TextChunk]:
        """
        Chunk text based on semantic boundaries while respecting structure
        """
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_id = 0
        
        # First split by major structural boundaries
        sections = self._split_by_structure(text)
        
        for section_start, section_end, section_text in sections:
            # Further split large sections by semantic boundaries
            subsections = self._split_by_semantic_boundaries(section_text)
            
            section_position = section_start
            for subsection in subsections:
                subsection_chunks = self._split_by_sentences(subsection)
                
                for sentence_chunk in subsection_chunks:
                    # Check if adding this chunk would exceed size limit
                    potential_chunk = current_chunk + ("\n" if current_chunk else "") + sentence_chunk
                    
                    if len(potential_chunk) > self.max_chunk_size and current_chunk:
                        # Save current chunk and start new one
                        if len(current_chunk.strip()) >= self.min_chunk_size:
                            chunks.append(TextChunk(
                                content=current_chunk.strip(),
                                start_position=current_start,
                                end_position=current_start + len(current_chunk),
                                chunk_id=f"semantic_{chunk_id}",
                                chunk_type=ChunkType.SEMANTIC,
                                metadata={'section_start': section_start, 'section_end': section_end}
                            ))
                            chunk_id += 1
                        
                        current_chunk = sentence_chunk
                        current_start = section_position
                    else:
                        current_chunk = potential_chunk
                        if not current_chunk:  # First chunk
                            current_start = section_position
                    
                    section_position += len(sentence_chunk) + 1
        
        # Add final chunk
        if current_chunk.strip() and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(TextChunk(
                content=current_chunk.strip(),
                start_position=current_start,
                end_position=current_start + len(current_chunk),
                chunk_id=f"semantic_{chunk_id}",
                chunk_type=ChunkType.SEMANTIC,
                metadata={}
            ))
        
        return chunks
    
    def _structural_chunking(self, text: str) -> List[TextChunk]:
        """
        Chunk text based on document structure (headings, paragraphs, etc.)
        """
        chunks = []
        chunk_id = 0
        
        # Split by major structural elements
        sections = self._identify_structural_sections(text)
        
        for section in sections:
            # Each structural section becomes one or more chunks
            section_chunks = self._split_section_by_size(section)
            
            for chunk_text, start_pos, end_pos in section_chunks:
                if len(chunk_text.strip()) >= self.min_chunk_size:
                    chunks.append(TextChunk(
                        content=chunk_text.strip(),
                        start_position=start_pos,
                        end_position=end_pos,
                        chunk_id=f"structural_{chunk_id}",
                        chunk_type=ChunkType.STRUCTURAL,
                        metadata=section['metadata']
                    ))
                    chunk_id += 1
        
        return chunks
    
    def _fixed_size_chunking(self, text: str) -> List[TextChunk]:
        """
        Chunk text into fixed-size pieces with smart boundaries
        """
        chunks = []
        chunk_id = 0
        position = 0
        
        while position < len(text):
            # Determine chunk end position
            chunk_end = min(position + self.max_chunk_size, len(text))
            
            # Try to find a good boundary near the chunk end
            if chunk_end < len(text):
                # Look for sentence boundary within last 20% of chunk
                search_start = max(position, chunk_end - int(self.max_chunk_size * 0.2))
                boundary = self._find_sentence_boundary(text, search_start, chunk_end)
                
                if boundary > position:
                    chunk_end = boundary
            
            chunk_text = text[position:chunk_end].strip()
            
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(TextChunk(
                    content=chunk_text,
                    start_position=position,
                    end_position=chunk_end,
                    chunk_id=f"fixed_{chunk_id}",
                    chunk_type=ChunkType.FIXED_SIZE,
                    metadata={'target_size': self.max_chunk_size}
                ))
                chunk_id += 1
            
            position = chunk_end
        
        return chunks
    
    def _sliding_window_chunking(self, text: str) -> List[TextChunk]:
        """
        Create overlapping chunks using sliding window approach
        """
        chunks = []
        chunk_id = 0
        step_size = int(self.max_chunk_size * (1 - self.overlap_ratio))
        position = 0
        
        while position < len(text):
            chunk_end = min(position + self.max_chunk_size, len(text))
            
            # Try to find sentence boundary
            if chunk_end < len(text) and self.preserve_sentences:
                boundary = self._find_sentence_boundary(text, position, chunk_end)
                if boundary > position:
                    chunk_end = boundary
            
            chunk_text = text[position:chunk_end].strip()
            
            if len(chunk_text) >= self.min_chunk_size:
                # Calculate actual overlap with previous chunk
                prev_overlap = 0
                if chunks:
                    prev_end = chunks[-1].end_position
                    prev_overlap = max(0, prev_end - position)
                
                chunks.append(TextChunk(
                    content=chunk_text,
                    start_position=position,
                    end_position=chunk_end,
                    chunk_id=f"sliding_{chunk_id}",
                    chunk_type=ChunkType.SLIDING_WINDOW,
                    metadata={'step_size': step_size, 'target_overlap': self.overlap_ratio},
                    overlap_with_previous=prev_overlap
                ))
                chunk_id += 1
            
            # Move position by step size
            position += step_size
            
            # Stop if we've covered the entire text
            if chunk_end >= len(text):
                break
        
        return chunks
    
    def _split_by_structure(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Split text by major structural boundaries
        
        Returns:
            List of (start_pos, end_pos, text) tuples
        """
        sections = []
        
        # Find paragraph breaks as primary structure
        paragraphs = re.split(self.structure_markers['paragraph_break'], text)
        position = 0
        
        for paragraph in paragraphs:
            if paragraph.strip():
                start_pos = position
                end_pos = position + len(paragraph)
                sections.append((start_pos, end_pos, paragraph.strip()))
                
            # Move position past the paragraph and separator
            position += len(paragraph) + 2  # Assuming 2-char separator (\n\n)
        
        return sections
    
    def _split_by_semantic_boundaries(self, text: str) -> List[str]:
        """
        Split text by semantic boundaries (topic changes, etc.)
        """
        # Simple implementation - can be enhanced with NLP
        sentences = self._split_into_sentences(text)
        sections = []
        current_section = []
        
        for i, sentence in enumerate(sentences):
            current_section.append(sentence)
            
            # Look for semantic indicators
            sentence_lower = sentence.lower()
            
            # Check for topic change indicators
            has_topic_change = any(indicator in sentence_lower 
                                 for indicator in self.semantic_indicators['topic_change'])
            
            # Check for conclusion indicators (end of section)
            has_conclusion = any(indicator in sentence_lower 
                               for indicator in self.semantic_indicators['conclusion'])
            
            # Split if we detect a boundary and have enough content
            if (has_topic_change or has_conclusion) and len(' '.join(current_section)) > self.min_chunk_size:
                sections.append(' '.join(current_section))
                current_section = []
        
        # Add remaining content
        if current_section:
            sections.append(' '.join(current_section))
        
        return sections
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Split text by sentences while preserving meaning
        """
        if not self.preserve_sentences:
            return [text]
        
        sentences = self._split_into_sentences(text)
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # Check if adding this sentence would exceed limit
            if current_length + sentence_length > self.max_chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length + 1  # +1 for space
        
        # Add remaining sentences
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using language-aware rules
        """
        # Enhanced sentence splitting for multi-language support
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZÀ-ÿ])|(?<=[.!?])\s*\n+\s*(?=[A-ZÀ-ÿ])'
        sentences = re.split(sentence_pattern, text.strip())
        
        # Clean up and filter sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 3:  # Filter very short fragments
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """
        Find the best sentence boundary within a range
        """
        # Look for sentence endings in reverse from the end position
        search_text = text[start:end]
        
        for i in range(len(search_text) - 1, -1, -1):
            char = search_text[i]
            
            # Check if this is a sentence ending
            if char in self.sentence_endings['general']:
                # Make sure it's followed by whitespace or end of text
                if i + 1 < len(search_text):
                    next_char = search_text[i + 1]
                    if next_char.isspace():
                        return start + i + 1
                else:
                    return start + i + 1
        
        # No good boundary found, return original end
        return end
    
    def _identify_structural_sections(self, text: str) -> List[Dict]:
        """
        Identify structural sections in the document
        """
        sections = []
        lines = text.split('\n')
        current_section = {'text': '', 'metadata': {}, 'start': 0}
        position = 0
        
        for line_num, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Check for headings
            if self.structure_markers['heading'].match(line_stripped):
                # Save previous section
                if current_section['text'].strip():
                    current_section['end'] = position
                    sections.append(current_section)
                
                # Start new section
                current_section = {
                    'text': line + '\n',
                    'metadata': {'type': 'section', 'heading': line_stripped, 'line': line_num},
                    'start': position
                }
            else:
                current_section['text'] += line + '\n'
            
            position += len(line) + 1
        
        # Add final section
        if current_section['text'].strip():
            current_section['end'] = position
            sections.append(current_section)
        
        return sections
    
    def _split_section_by_size(self, section: Dict) -> List[Tuple[str, int, int]]:
        """
        Split a structural section by size constraints
        """
        text = section['text']
        chunks = []
        
        if len(text) <= self.max_chunk_size:
            return [(text, section['start'], section['end'])]
        
        # Split large sections by paragraphs first, then by sentences
        paragraphs = text.split('\n\n')
        position = section['start']
        
        for paragraph in paragraphs:
            if len(paragraph) <= self.max_chunk_size:
                chunks.append((paragraph, position, position + len(paragraph)))
            else:
                # Split paragraph further
                para_chunks = self._split_by_sentences(paragraph)
                para_pos = position
                
                for chunk in para_chunks:
                    chunks.append((chunk, para_pos, para_pos + len(chunk)))
                    para_pos += len(chunk)
            
            position += len(paragraph) + 2  # +2 for \n\n
        
        return chunks
    
    def _optimize_chunks(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        Optimize chunks by merging small ones and splitting large ones
        """
        optimized = []
        i = 0
        
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # Try to merge small chunks with next chunk
            if (len(current_chunk) < self.min_chunk_size and 
                i + 1 < len(chunks) and
                len(current_chunk) + len(chunks[i + 1]) <= self.max_chunk_size):
                
                next_chunk = chunks[i + 1]
                merged_content = current_chunk.content + "\n\n" + next_chunk.content
                
                merged_chunk = TextChunk(
                    content=merged_content,
                    start_position=current_chunk.start_position,
                    end_position=next_chunk.end_position,
                    chunk_id=f"{current_chunk.chunk_id}_merged",
                    chunk_type=current_chunk.chunk_type,
                    metadata={**current_chunk.metadata, 'merged': True}
                )
                
                optimized.append(merged_chunk)
                i += 2  # Skip next chunk as it was merged
            else:
                optimized.append(current_chunk)
                i += 1
        
        return optimized
    
    def _add_overlap(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        Add overlap between chunks for better context preservation
        """
        if self.overlap_ratio <= 0 or len(chunks) <= 1:
            return chunks
        
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            current_chunk = chunks[i]
            
            # Calculate overlap size
            overlap_size = int(len(prev_chunk) * self.overlap_ratio)
            
            if overlap_size > 0:
                # Get overlap text from end of previous chunk
                overlap_text = prev_chunk.content[-overlap_size:]
                
                # Add overlap to current chunk
                current_chunk.content = overlap_text + "\n" + current_chunk.content
                current_chunk.overlap_with_previous = len(overlap_text)
                
                # Update metadata
                current_chunk.metadata['overlap_added'] = True
                current_chunk.metadata['overlap_size'] = len(overlap_text)
        
        return chunks
    
    def get_chunk_statistics(self, chunks: List[TextChunk]) -> Dict[str, any]:
        """
        Generate statistics about the chunking results
        """
        if not chunks:
            return {'error': 'No chunks provided'}
        
        sizes = [len(chunk) for chunk in chunks]
        word_counts = [chunk.word_count for chunk in chunks]
        
        stats = {
            'total_chunks': len(chunks),
            'total_characters': sum(sizes),
            'total_words': sum(word_counts),
            'size_stats': {
                'min_chars': min(sizes),
                'max_chars': max(sizes),
                'avg_chars': sum(sizes) / len(sizes),
                'median_chars': sorted(sizes)[len(sizes) // 2]
            },
            'word_stats': {
                'min_words': min(word_counts),
                'max_words': max(word_counts),
                'avg_words': sum(word_counts) / len(word_counts)
            },
            'chunk_types': {chunk.chunk_type.value: sum(1 for c in chunks if c.chunk_type == chunk.chunk_type) 
                           for chunk in chunks},
            'overlap_stats': {
                'chunks_with_overlap': sum(1 for c in chunks if c.overlap_with_previous > 0),
                'avg_overlap': sum(c.overlap_with_previous for c in chunks) / len(chunks)
            }
        }
        
        return stats

# Usage example and CLI
def main():
    """CLI interface for text chunking"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Intelligent Text Chunking Tool')
    parser.add_argument('input_file', help='Input text file')
    parser.add_argument('--output-dir', default='chunks_output', help='Output directory')
    parser.add_argument('--chunk-type', choices=['semantic', 'structural', 'fixed_size', 'sliding_window'],
                       default='semantic', help='Chunking strategy')
    parser.add_argument('--max-size', type=int, default=512, help='Maximum chunk size')
    parser.add_argument('--min-size', type=int, default=50, help='Minimum chunk size')
    parser.add_argument('--overlap', type=float, default=0.1, help='Overlap ratio (0.0-0.5)')
    parser.add_argument('--preserve-sentences', action='store_true', default=True, help='Preserve sentences')
    parser.add_argument('--preserve-paragraphs', action='store_true', default=True, help='Preserve paragraphs')
    
    args = parser.parse_args()
    
    # Read input file
    with open(args.input_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Initialize chunker
    chunker = IntelligentTextChunker(
        max_chunk_size=args.max_size,
        min_chunk_size=args.min_size,
        overlap_ratio=args.overlap,
        preserve_sentences=args.preserve_sentences,
        preserve_paragraphs=args.preserve_paragraphs
    )
    
    # Chunk the text
    chunk_type = ChunkType(args.chunk_type)
    chunks = chunker.chunk_document(text, chunk_type)
    
    # Create output directory
    from pathlib import Path
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Save chunks
    for i, chunk in enumerate(chunks):
        chunk_file = output_dir / f"chunk_{i:04d}.txt"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(chunk.content)
    
    # Save metadata
    metadata = {
        'input_file': args.input_file,
        'chunking_config': {
            'chunk_type': args.chunk_type,
            'max_size': args.max_size,
            'min_size': args.min_size,
            'overlap_ratio': args.overlap
        },
        'chunks': [{
            'chunk_id': chunk.chunk_id,
            'file': f"chunk_{i:04d}.txt",
            'size_chars': len(chunk),
            'size_words': chunk.word_count,
            'start_position': chunk.start_position,
            'end_position': chunk.end_position,
            'overlap_previous': chunk.overlap_with_previous,
            'metadata': chunk.metadata
        } for i, chunk in enumerate(chunks)],
        'statistics': chunker.get_chunk_statistics(chunks)
    }
    
    metadata_file = output_dir / "chunking_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Created {len(chunks)} chunks in {output_dir}")
    print(f"📊 Statistics saved to {metadata_file}")

if __name__ == "__main__":
    main()