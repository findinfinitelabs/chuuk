# AI Training Data Generation Skill

## Overview
A comprehensive skill for automatically generating high-quality training datasets from documents, text corpora, and structured content. Optimized for low-resource languages, dictionary content, and domain-specific knowledge extraction.

## Capabilities
- **Multi-strategy Generation**: Dictionary pairs, contextual definitions, completion tasks, classification examples
- **Quality Filtering**: Confidence scoring, duplicate removal, and content validation
- **Format Flexibility**: Support for multiple AI training formats (JSONL, HuggingFace, Ollama, OpenAI)
- **Language Awareness**: Multi-language support with special handling for accented characters
- **Scalable Processing**: Generate thousands of examples from large documents
- **Balance Management**: Ensure dataset diversity and prevent category imbalance

## Core Strategies

### 1. Dictionary Pair Extraction
**Purpose**: Extract word-definition pairs from structured and semi-structured text.

**Detection Patterns**:
- Separator-based: `word – definition`, `term: meaning`
- Linguistic indicators: `means`, `is defined as`, `refers to`
- Structural cues: Indentation, formatting, list structures
- Context analysis: Surrounding text for validation

**Quality Measures**:
- Word length validation (avoid fragments)
- Definition completeness (minimum content requirements)
- Language pattern matching (accented characters, etc.)
- Contextual relevance scoring

### 2. Contextual Definition Generation
**Purpose**: Create training examples that include surrounding context for better AI understanding.

**Context Strategies**:
- **Paragraph context**: Use surrounding sentences for definition context
- **Section context**: Include heading or topic information
- **Hierarchical context**: Reference document structure level
- **Semantic context**: Identify related terms and concepts

**Example Types**:
- `"In the context of [topic], what does [term] mean?"`
- `"Given the section about [subject], define [word]"`
- `"What is the meaning of [term] in this passage: [context]"`

### 3. Structural Learning Examples
**Purpose**: Help AI understand document organization and content hierarchy.

**Structure Recognition**:
- Heading level identification and description
- List item classification and numbering
- Indentation pattern recognition
- Section relationship mapping

**Training Examples**:
- `"What type of content is this: [text]"` → `"Level 2 heading"`
- `"What would you expect under this heading: [title]"` → `"[predicted content]"`
- `"Classify this text structure: [sample]"` → `"Dictionary entry"`

### 4. Language Pattern Recognition
**Purpose**: Train AI to recognize language-specific patterns and characteristics.

**Pattern Categories**:
- **Character patterns**: Accented characters, special symbols
- **Word formation**: Prefixes, suffixes, compound words
- **Language identification**: Distinguish between languages in mixed content
- **Pronunciation guides**: IPA notation, stress patterns

**Training Types**:
- Language identification tasks
- Character encoding recognition
- Word family relationships
- Phonetic pattern matching

### 5. Text Completion Tasks
**Purpose**: Generate examples for training autocompletion and text generation models.

**Completion Strategies**:
- **Sentence completion**: Partial sentences requiring natural endings
- **Definition completion**: Partial definitions requiring completion
- **Context completion**: Given context, predict likely content
- **Pattern completion**: Complete recurring patterns or structures

**Configuration Options**:
- Completion ratios (30%, 50%, 70% of original text)
- Multiple completion points per text
- Context window size adjustment
- Pattern-based vs. random splitting

## Implementation Pattern

### Basic Training Data Generation
```python
from .ai_training_generator import AITrainingDataGenerator

# Initialize generator
generator = AITrainingDataGenerator(min_confidence=0.7)

# Generate comprehensive training data
training_data = generator.generate_comprehensive_training_data(
    parsed_document,
    target_count=10000
)

# Export in multiple formats
files = generator.export_training_data(
    training_data,
    output_dir="training_output",
    format_type="ollama"
)
```

### Advanced Configuration
```python
# Custom confidence thresholds per strategy
generator = AITrainingDataGenerator(
    min_confidence=0.8,
    strategy_weights={
        'dictionary_pairs': 0.4,
        'contextual_definitions': 0.3,
        'structural_learning': 0.2,
        'language_patterns': 0.1
    }
)

# Generate targeted training data
specific_data = generator.generate_dictionary_training_data(
    document,
    focus_languages=['chuukese', 'english'],
    include_pronunciation=True
)
```

## Quality Assurance Framework

### Confidence Scoring System
- **Content validity**: Does the example make linguistic sense?
- **Pattern matching**: Does it follow expected language patterns?
- **Context appropriateness**: Is the context relevant and helpful?
- **Difficulty balance**: Mix of simple and complex examples
- **Uniqueness**: Avoid repetitive or duplicate content

### Filtering Mechanisms
```python
def validate_training_example(example):
    checks = [
        length_validation(example.input_text, example.output_text),
        language_pattern_check(example),
        content_quality_assessment(example),
        duplication_detection(example, existing_examples)
    ]
    return all(checks)
```

### Balance Management
- **Category distribution**: Ensure balanced representation across training types
- **Difficulty progression**: Include examples of varying complexity
- **Language representation**: Balance between source and target languages
- **Context diversity**: Vary context types and sources

## Output Format Specifications

### JSONL Format (Standard)
```json
{"input": "What does 'ááfengen' mean?", "output": "very good, excellent", "type": "dictionary_pair", "confidence": 0.95}
{"input": "Complete this definition: ran –", "output": "water", "type": "completion_task", "confidence": 0.88}
```

### Ollama Format
```json
{"prompt": "Translate this Chuukese word: ngang", "response": "fish", "system": "You are a Chuukese-English translator."}
```

### HuggingFace Format
```json
{"text": "### Instruction:\nWhat does 'chomong' mean in Chuukese?\n\n### Response:\nto help, assist"}
```

### OpenAI Fine-tuning Format
```json
{"messages": [{"role": "user", "content": "Define: kúún"}, {"role": "assistant", "content": "to go, to leave"}]}
```

## Integration Strategies

### With Document Processing Pipeline
```python
# Integrate with document parser
from .large_document_processor import LargeDocumentProcessor

processor = LargeDocumentProcessor()
results = processor.process_large_document("document.docx")

# Generate training data from processed structure
training_data = generator.generate_from_processed_document(
    results['parsed_document']
)
```

### With Existing ML Pipelines
```python
# Export for specific frameworks
def prepare_for_training(training_data, framework='transformers'):
    if framework == 'transformers':
        return convert_to_huggingface_format(training_data)
    elif framework == 'ollama':
        return convert_to_ollama_format(training_data)
    # Add other framework converters
```

## Validation Metrics

### Quantitative Metrics
- **Generation rate**: Examples per minute of source text
- **Quality score**: Average confidence across all examples
- **Diversity index**: Unique patterns and structures represented
- **Coverage ratio**: Percentage of source content converted to training data
- **Balance coefficient**: Distribution evenness across categories

### Qualitative Assessment
- **Linguistic accuracy**: Manual review of sample examples
- **Cultural appropriateness**: Sensitivity to cultural context
- **Educational value**: Learning potential for target models
- **Contextual relevance**: Appropriateness of context usage
- **Practical utility**: Real-world applicability of examples

## Best Practices

### Data Quality
1. **Multiple validation passes**: Automated and manual quality checks
2. **Confidence thresholds**: Adjust based on use case requirements
3. **Human review sampling**: Periodic manual validation of generated examples
4. **Iterative improvement**: Refine patterns based on quality feedback

### Scalability
1. **Incremental processing**: Process large datasets in manageable chunks
2. **Parallel generation**: Utilize multiple cores for faster processing
3. **Memory management**: Efficient handling of large training datasets
4. **Storage optimization**: Compress and optimize output formats

### Maintenance
1. **Pattern updates**: Regularly update extraction patterns
2. **Quality monitoring**: Track generation quality over time
3. **Format evolution**: Adapt to new AI training format requirements
4. **Feedback integration**: Incorporate user feedback into improvements

## Dependencies
- `re`: Regular expression pattern matching
- `json`: Data serialization and export
- `hashlib`: Duplicate detection and content hashing
- `collections`: Data structure utilities and counting
- `pathlib`: File system operations
- `logging`: Processing activity tracking

## Validation Criteria
A successful implementation should:
- ✅ Generate 1000+ training examples per 100 pages of source text
- ✅ Maintain >80% confidence score across generated examples
- ✅ Support multiple output formats without data loss
- ✅ Process efficiently without memory or performance issues
- ✅ Produce balanced datasets across different example types
- ✅ Include comprehensive quality metrics and reporting
- ✅ Handle multiple languages and special characters correctly

## Extension Points
- **Custom extractors**: Add domain-specific pattern recognition
- **Quality analyzers**: Implement advanced quality assessment algorithms
- **Format adapters**: Create converters for new AI frameworks
- **Language processors**: Add support for additional languages
- **Context enhancers**: Improve contextual understanding and generation
- **Feedback loops**: Integrate model performance feedback for quality improvement