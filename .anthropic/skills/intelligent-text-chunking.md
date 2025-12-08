# Intelligent Text Chunking Skill

## Overview
A sophisticated text segmentation skill that splits large texts into meaningful, AI-optimized chunks while preserving semantic coherence, document structure, and contextual relationships. Essential for processing large documents for AI training, RAG systems, and memory-constrained applications.

## Capabilities
- **Semantic Awareness**: Respects topic boundaries and meaning transitions
- **Structure Preservation**: Maintains document hierarchy and formatting context
- **Multi-language Support**: Handles accented characters and diverse writing systems
- **Configurable Strategies**: Multiple chunking approaches for different use cases
- **Context Preservation**: Intelligent overlap management for context continuity
- **Quality Optimization**: Balances chunk size with content coherence

## Chunking Strategies

### 1. Semantic Chunking
**Purpose**: Split text based on meaning and topic boundaries rather than arbitrary size limits.

**Approach**:
- **Topic transition detection**: Identify natural topic shifts
- **Semantic boundary indicators**: Words like "however", "meanwhile", "furthermore"
- **Paragraph coherence**: Keep related sentences together
- **Context preservation**: Ensure chunks contain complete thoughts

**Best For**:
- Educational content and textbooks
- Research papers and articles
- Documentation with conceptual sections
- Content where meaning preservation is critical

### 2. Structural Chunking
**Purpose**: Follow document organization (headings, sections, lists) for natural divisions.

**Approach**:
- **Hierarchy respect**: Chunk by heading levels and sections
- **List preservation**: Keep lists and their context together
- **Format awareness**: Respect document formatting cues
- **Section completeness**: Include section headers with their content

**Best For**:
- Technical documentation
- Reference materials
- Structured reports
- Content with clear organizational hierarchy

### 3. Fixed-Size Chunking
**Purpose**: Create consistent-sized chunks with intelligent boundary selection.

**Approach**:
- **Size consistency**: Maintain target chunk sizes
- **Smart boundaries**: Find optimal split points near size limits
- **Sentence preservation**: Avoid breaking sentences when possible
- **Word boundaries**: Respect word integrity

**Best For**:
- AI model training with size constraints
- Memory-limited processing
- Consistent processing pipelines
- Embedding generation

### 4. Sliding Window Chunking
**Purpose**: Create overlapping chunks for enhanced context preservation.

**Approach**:
- **Configurable overlap**: Adjust overlap ratio based on needs
- **Context continuity**: Ensure information flow between chunks
- **Boundary optimization**: Find natural transition points
- **Redundancy management**: Balance overlap with efficiency

**Best For**:
- Question-answering systems
- RAG (Retrieval-Augmented Generation) applications
- Context-sensitive AI tasks
- Information retrieval systems

## Advanced Features

### Language-Aware Processing
```python
# Multi-language sentence detection
sentence_patterns = {
    'english': ['.', '!', '?', ';'],
    'chuukese': ['.', '!', '?'],
    'general': ['.', '!', '?', ';', '。', '！', '？']
}

# Accented character handling for low-resource languages
def detect_language_patterns(text):
    has_accents = bool(re.search(r'[áéíóúàèìòùāēīōūâêîôû]', text))
    return 'chuukese' if has_accents else 'english'
```

### Contextual Overlap Management
```python
def add_intelligent_overlap(chunks, overlap_ratio=0.1):
    """Add context-preserving overlap between chunks"""
    for i in range(1, len(chunks)):
        prev_chunk = chunks[i - 1]
        current_chunk = chunks[i]
        
        # Calculate semantic overlap
        overlap_size = int(len(prev_chunk) * overlap_ratio)
        overlap_text = extract_meaningful_overlap(prev_chunk, overlap_size)
        
        # Add to current chunk
        current_chunk.content = overlap_text + "\n" + current_chunk.content
```

### Quality Optimization
```python
def optimize_chunk_quality(chunks):
    """Optimize chunks for better coherence and utility"""
    optimized = []
    
    for chunk in chunks:
        # Merge very small chunks
        if len(chunk) < min_chunk_size:
            merge_with_adjacent(chunk, optimized)
        
        # Split very large chunks
        elif len(chunk) > max_chunk_size * 1.5:
            sub_chunks = split_large_chunk(chunk)
            optimized.extend(sub_chunks)
        
        # Adjust boundaries for better sentence completion
        else:
            adjusted = adjust_boundaries(chunk)
            optimized.append(adjusted)
    
    return optimized
```

## Implementation Pattern

### Basic Usage
```python
from .intelligent_chunker import IntelligentTextChunker, ChunkType

# Initialize chunker
chunker = IntelligentTextChunker(
    max_chunk_size=512,
    min_chunk_size=50,
    overlap_ratio=0.1
)

# Chunk text semantically
chunks = chunker.chunk_document(text, ChunkType.SEMANTIC)

# Access chunk properties
for chunk in chunks:
    print(f"Chunk {chunk.chunk_id}: {len(chunk)} chars, {chunk.word_count} words")
```

### Advanced Configuration
```python
# Custom chunker for specific use case
specialized_chunker = IntelligentTextChunker(
    max_chunk_size=1024,
    min_chunk_size=100,
    overlap_ratio=0.15,
    preserve_sentences=True,
    preserve_paragraphs=True
)

# Configure for specific language patterns
chunker.configure_language_support(
    primary_language='chuukese',
    accent_handling=True,
    custom_sentence_patterns=['!', '?', '.']
)
```

## Chunk Quality Assessment

### Statistical Metrics
```python
def analyze_chunk_quality(chunks):
    """Generate comprehensive chunk statistics"""
    stats = {
        'total_chunks': len(chunks),
        'size_distribution': calculate_size_distribution(chunks),
        'overlap_analysis': analyze_overlap_patterns(chunks),
        'coherence_scores': calculate_coherence_scores(chunks),
        'boundary_quality': assess_boundary_decisions(chunks)
    }
    return stats
```

### Quality Indicators
- **Size consistency**: Variance in chunk sizes
- **Boundary appropriateness**: Sentence/paragraph boundary respect
- **Content completeness**: Percentage of complete thoughts preserved
- **Overlap effectiveness**: Context preservation without excessive redundancy
- **Processing efficiency**: Chunks per second generation rate

## Integration Patterns

### With Document Processing
```python
def integrate_with_document_parser(parsed_doc):
    """Integrate chunking with document structure analysis"""
    
    # Use document structure to guide chunking
    structure_aware_chunker = IntelligentTextChunker()
    
    # Configure based on document analysis
    if parsed_doc.has_complex_structure():
        chunk_type = ChunkType.STRUCTURAL
    elif parsed_doc.is_narrative_content():
        chunk_type = ChunkType.SEMANTIC
    else:
        chunk_type = ChunkType.FIXED_SIZE
    
    return structure_aware_chunker.chunk_document(
        parsed_doc.text, 
        chunk_type
    )
```

### With AI Training Pipelines
```python
def prepare_chunks_for_training(text, model_context_length=512):
    """Optimize chunks for specific AI model requirements"""
    
    # Configure for model constraints
    chunker = IntelligentTextChunker(
        max_chunk_size=model_context_length - 50,  # Leave room for prompt
        overlap_ratio=0.1,  # Maintain context
        preserve_sentences=True
    )
    
    chunks = chunker.chunk_document(text, ChunkType.SEMANTIC)
    
    # Add metadata for training
    for chunk in chunks:
        chunk.metadata['model_ready'] = True
        chunk.metadata['context_length'] = model_context_length
    
    return chunks
```

### With RAG Systems
```python
def create_rag_optimized_chunks(documents):
    """Create chunks optimized for retrieval-augmented generation"""
    
    rag_chunker = IntelligentTextChunker(
        max_chunk_size=400,  # Optimal for embedding models
        overlap_ratio=0.2,   # High overlap for better retrieval
        preserve_paragraphs=True
    )
    
    all_chunks = []
    for doc in documents:
        chunks = rag_chunker.chunk_document(doc.text, ChunkType.SLIDING_WINDOW)
        
        # Add retrieval metadata
        for chunk in chunks:
            chunk.metadata['source_document'] = doc.id
            chunk.metadata['retrieval_optimized'] = True
            chunk.metadata['embedding_ready'] = True
        
        all_chunks.extend(chunks)
    
    return all_chunks
```

## Performance Optimization

### Memory Management
```python
def chunk_large_document_efficiently(large_text):
    """Handle very large documents with memory efficiency"""
    
    # Stream processing for memory efficiency
    chunk_size = 1000000  # 1MB chunks for processing
    text_stream = StringIO(large_text)
    
    all_chunks = []
    buffer = ""
    
    while True:
        chunk = text_stream.read(chunk_size)
        if not chunk:
            break
        
        # Process chunk with overlap buffer
        combined_text = buffer + chunk
        processed_chunks = chunker.chunk_document(combined_text)
        
        # Keep last chunk as buffer for next iteration
        if len(processed_chunks) > 1:
            all_chunks.extend(processed_chunks[:-1])
            buffer = processed_chunks[-1].content
        else:
            buffer = combined_text
    
    return all_chunks
```

### Parallel Processing
```python
from concurrent.futures import ThreadPoolExecutor

def chunk_multiple_documents(documents, max_workers=4):
    """Process multiple documents in parallel"""
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(chunker.chunk_document, doc.text): doc 
            for doc in documents
        }
        
        results = {}
        for future in as_completed(futures):
            doc = futures[future]
            try:
                chunks = future.result()
                results[doc.id] = chunks
            except Exception as e:
                logger.error(f"Error processing {doc.id}: {e}")
    
    return results
```

## Configuration Options

### Size Management
```python
ChunkConfig = {
    'max_chunk_size': 512,      # Maximum characters per chunk
    'min_chunk_size': 50,       # Minimum viable chunk size
    'target_size': 400,         # Preferred chunk size
    'size_tolerance': 0.2       # Acceptable size variance
}
```

### Overlap Strategy
```python
OverlapConfig = {
    'overlap_ratio': 0.1,       # Fraction of chunk to overlap
    'min_overlap': 20,          # Minimum overlap in characters
    'max_overlap': 100,         # Maximum overlap limit
    'semantic_overlap': True    # Use semantic boundaries for overlap
}
```

### Boundary Detection
```python
BoundaryConfig = {
    'respect_sentences': True,    # Avoid breaking sentences
    'respect_paragraphs': True,   # Preserve paragraph boundaries
    'respect_sections': True,     # Keep sections intact when possible
    'custom_boundaries': ['\n\n', '---', '***']  # Custom boundary markers
}
```

## Best Practices

### Content-Specific Optimization
1. **Technical documentation**: Use structural chunking with section awareness
2. **Narrative content**: Apply semantic chunking for story flow preservation
3. **Reference materials**: Employ fixed-size chunking with smart boundaries
4. **Mixed content**: Use adaptive strategy based on content analysis

### AI Training Considerations
1. **Model context limits**: Configure chunk size based on target model capacity
2. **Training diversity**: Use multiple chunking strategies for varied examples
3. **Context preservation**: Ensure sufficient overlap for contextual understanding
4. **Quality filtering**: Remove low-quality chunks before training

### Production Deployment
1. **Performance monitoring**: Track chunking speed and memory usage
2. **Quality validation**: Regular assessment of chunk coherence
3. **Configuration tuning**: Adjust parameters based on real-world performance
4. **Error handling**: Robust handling of malformed or edge-case content

## Dependencies
- `re`: Pattern matching for boundary detection
- `io`: String stream processing for memory efficiency
- `concurrent.futures`: Parallel processing capabilities
- `dataclasses`: Structured data representation
- `enum`: Type-safe chunking strategy enumeration
- `logging`: Processing activity tracking

## Validation Criteria
A successful implementation should:
- ✅ Maintain semantic coherence within chunks
- ✅ Respect document structure and formatting
- ✅ Handle multiple languages and character sets
- ✅ Process efficiently without memory issues
- ✅ Provide configurable chunking strategies
- ✅ Generate useful metadata and statistics
- ✅ Integrate seamlessly with AI pipelines
- ✅ Support both streaming and batch processing modes