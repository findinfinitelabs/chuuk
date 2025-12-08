#!/usr/bin/env python3
"""
AI Training Data Generator for Large Documents
==============================================

Automatically generates high-quality training datasets from parsed documents
with multiple strategies for different AI model types.
"""

import os
import re
import json
import hashlib
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from collections import defaultdict, Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TrainingExample:
    """Single training example with metadata"""
    input_text: str
    output_text: str
    example_type: str
    confidence_score: float
    source_page: int
    context: str
    metadata: Dict[str, any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class AITrainingDataGenerator:
    """
    Advanced training data generator for AI models using large documents
    """
    
    def __init__(self, min_confidence: float = 0.7):
        self.min_confidence = min_confidence
        self.word_patterns = {
            'chuukese': re.compile(r'[áéíóúàèìòùāēīōūâêîôû]'),  # Accented characters
            'english': re.compile(r'^[a-zA-Z\s\-\']+$'),
            'mixed_language': re.compile(r'[a-zA-Z\s\-\'].*[áéíóúàèìòùāēīōūâêîôû]|[áéíóúàèìòùāēīōūâêîôû].*[a-zA-Z\s\-\']')
        }
        
        self.separator_patterns = [
            r'(\s*[–—-]\s*)',  # Em dash, en dash, hyphen
            r'(\s+means?\s+)',   # "means" or "mean"
            r'(\s+is\s+)',       # "is"
            r'(\s*:\s*)',        # Colon
            r'(\s*;\s*)',        # Semicolon
            r'(\s*\|\s*)',       # Pipe
            r'(\s{3,})',         # Multiple spaces
            r'(\t+)',            # Tabs
        ]
        
        # Common dictionary indicators
        self.dictionary_indicators = {
            'entry_starters': ['n.', 'v.', 'adj.', 'adv.', 'prep.', 'int.', 'vt.', 'vi.'],
            'definition_words': ['means', 'is', 'refers to', 'indicates', 'denotes'],
            'example_markers': ['Ex:', 'Example:', 'e.g.', 'for example'],
            'pronunciation_markers': ['(', '[', '/', 'IPA:']
        }
        
    def generate_comprehensive_training_data(self, 
                                           parsed_doc, 
                                           target_count: int = 10000) -> Dict[str, List[TrainingExample]]:
        """
        Generate comprehensive training data using multiple strategies
        
        Args:
            parsed_doc: ParsedDocument from AdvancedDocumentParser
            target_count: Target number of training examples
            
        Returns:
            Dictionary of training data categorized by type
        """
        logger.info(f"🎯 Generating comprehensive training data (target: {target_count} examples)")
        
        training_data = {
            'dictionary_pairs': [],
            'contextual_definitions': [],
            'structural_learning': [],
            'language_patterns': [],
            'completion_tasks': [],
            'classification_tasks': []
        }
        
        # Strategy 1: Extract dictionary pairs
        dict_pairs = self._extract_dictionary_pairs(parsed_doc)
        training_data['dictionary_pairs'].extend(dict_pairs)
        
        # Strategy 2: Generate contextual definitions
        contextual_defs = self._generate_contextual_definitions(parsed_doc)
        training_data['contextual_definitions'].extend(contextual_defs)
        
        # Strategy 3: Structural learning examples
        structural_examples = self._generate_structural_examples(parsed_doc)
        training_data['structural_learning'].extend(structural_examples)
        
        # Strategy 4: Language pattern recognition
        pattern_examples = self._generate_pattern_examples(parsed_doc)
        training_data['language_patterns'].extend(pattern_examples)
        
        # Strategy 5: Text completion tasks
        completion_examples = self._generate_completion_tasks(parsed_doc)
        training_data['completion_tasks'].extend(completion_examples)
        
        # Strategy 6: Classification tasks
        classification_examples = self._generate_classification_tasks(parsed_doc)
        training_data['classification_tasks'].extend(classification_examples)
        
        # Quality filtering and balancing
        training_data = self._filter_and_balance_data(training_data, target_count)
        
        # Generate statistics
        total_examples = sum(len(examples) for examples in training_data.values())
        logger.info(f"✅ Generated {total_examples} training examples across {len(training_data)} categories")
        
        for category, examples in training_data.items():
            avg_confidence = sum(ex.confidence_score for ex in examples) / max(len(examples), 1)
            logger.info(f"   📊 {category}: {len(examples)} examples (avg confidence: {avg_confidence:.2f})")
        
        return training_data
    
    def _extract_dictionary_pairs(self, parsed_doc) -> List[TrainingExample]:
        """Extract word-definition pairs from structured text"""
        pairs = []
        
        for node in parsed_doc.structure_tree:
            text = node.text.strip()
            
            # Skip very short or very long texts
            if len(text) < 5 or len(text) > 500:
                continue
            
            # Try different separation patterns
            for pattern in self.separator_patterns:
                matches = re.split(pattern, text)
                if len(matches) >= 3:  # Pattern found with separators
                    # Reconstruct parts around separator
                    for i in range(0, len(matches) - 2, 2):
                        left_part = matches[i].strip()
                        separator = matches[i + 1] if i + 1 < len(matches) else ''
                        right_part = matches[i + 2].strip() if i + 2 < len(matches) else ''
                        
                        if self._is_valid_dictionary_pair(left_part, right_part, separator):
                            confidence = self._calculate_pair_confidence(left_part, right_part, separator)
                            
                            if confidence >= self.min_confidence:
                                # Generate multiple variations
                                variations = self._generate_pair_variations(left_part, right_part)
                                
                                for source, target in variations:
                                    pairs.append(TrainingExample(
                                        input_text=source,
                                        output_text=target,
                                        example_type='dictionary_pair',
                                        confidence_score=confidence,
                                        source_page=node.page_number,
                                        context=f"Separator: '{separator}', Level: {node.level}",
                                        metadata={
                                            'original_text': text,
                                            'extraction_method': 'pattern_split'
                                        }
                                    ))
        
        logger.info(f"📖 Extracted {len(pairs)} dictionary pairs")
        return pairs
    
    def _generate_contextual_definitions(self, parsed_doc) -> List[TrainingExample]:
        """Generate contextual definition examples"""
        examples = []
        
        # Group related content by page and level
        context_groups = defaultdict(list)
        
        for node in parsed_doc.structure_tree:
            if node.level <= 4 and len(node.text) > 20:  # Substantial content
                key = (node.page_number, node.level)
                context_groups[key].append(node)
        
        for (page, level), nodes in context_groups.items():
            if len(nodes) >= 2:
                # Create context-based examples
                for i, primary_node in enumerate(nodes):
                    # Use surrounding nodes as context
                    context_nodes = nodes[max(0, i-1):i+2]
                    context_text = ' '.join(n.text for n in context_nodes if n != primary_node)
                    
                    # Look for definitions within the context
                    for def_word in self.dictionary_indicators['definition_words']:
                        if def_word in primary_node.text.lower():
                            parts = re.split(f'\\s{def_word}\\s', primary_node.text, 1)
                            if len(parts) == 2:
                                word = parts[0].strip().rstrip('.,;:')
                                definition = parts[1].strip()
                                
                                if self._is_valid_word(word) and len(definition) > 5:
                                    examples.append(TrainingExample(
                                        input_text=f"In the context of '{context_text[:100]}...', what does '{word}' mean?",
                                        output_text=definition,
                                        example_type='contextual_definition',
                                        confidence_score=0.8,
                                        source_page=page,
                                        context=f"Context length: {len(context_text)} chars",
                                        metadata={
                                            'definition_word': def_word,
                                            'context': context_text[:200]
                                        }
                                    ))
        
        logger.info(f"🧠 Generated {len(examples)} contextual definition examples")
        return examples
    
    def _generate_structural_examples(self, parsed_doc) -> List[TrainingExample]:
        """Generate examples based on document structure"""
        examples = []
        
        # Analyze structure patterns
        level_patterns = defaultdict(list)
        for node in parsed_doc.structure_tree:
            level_patterns[node.level].append(node)
        
        # Generate structure-based examples
        for level, nodes in level_patterns.items():
            if len(nodes) >= 3:  # Enough examples for pattern learning
                sample_nodes = nodes[:min(10, len(nodes))]  # Limit samples
                
                for node in sample_nodes:
                    # Structure recognition task
                    examples.append(TrainingExample(
                        input_text=f"What is the structural level of this text: '{node.text[:100]}...'?",
                        output_text=f"Level {level} - {self._describe_level(level)}",
                        example_type='structure_recognition',
                        confidence_score=0.9,
                        source_page=node.page_number,
                        context=f"Document structure analysis",
                        metadata={
                            'structure_level': level,
                            'formatting': str(node.formatting)
                        }
                    ))
                    
                    # Hierarchy explanation task
                    if node.children:
                        child_texts = [child.text[:50] for child in node.children[:3]]
                        examples.append(TrainingExample(
                            input_text=f"Given the heading '{node.text}', what content would you expect underneath?",
                            output_text=f"Content like: {'; '.join(child_texts)}",
                            example_type='hierarchy_prediction',
                            confidence_score=0.7,
                            source_page=node.page_number,
                            context=f"Hierarchy analysis",
                            metadata={
                                'parent_text': node.text,
                                'child_count': len(node.children)
                            }
                        ))
        
        logger.info(f"🏗️ Generated {len(examples)} structural examples")
        return examples
    
    def _generate_pattern_examples(self, parsed_doc) -> List[TrainingExample]:
        """Generate language pattern recognition examples"""
        examples = []
        
        # Collect all text for pattern analysis
        all_texts = [node.text for node in parsed_doc.structure_tree]
        
        # Extract word patterns
        chuukese_words = set()
        english_words = set()
        mixed_phrases = set()
        
        for text in all_texts:
            words = re.findall(r'\b\w+\b', text)
            for word in words:
                if self.word_patterns['chuukese'].search(word):
                    chuukese_words.add(word)
                elif self.word_patterns['english'].match(word) and len(word) > 2:
                    english_words.add(word)
            
            # Look for mixed language phrases
            if self.word_patterns['mixed_language'].search(text):
                sentences = re.split(r'[.!?]+', text)
                for sentence in sentences:
                    if len(sentence.strip()) > 10 and self.word_patterns['mixed_language'].search(sentence):
                        mixed_phrases.add(sentence.strip())
        
        # Generate language identification examples
        for word in list(chuukese_words)[:50]:  # Limit samples
            examples.append(TrainingExample(
                input_text=f"What language is this word: '{word}'?",
                output_text="Chuukese",
                example_type='language_identification',
                confidence_score=0.95,
                source_page=1,
                context="Language pattern analysis",
                metadata={'word_type': 'chuukese', 'has_accents': True}
            ))
        
        for word in list(english_words)[:50]:
            examples.append(TrainingExample(
                input_text=f"What language is this word: '{word}'?",
                output_text="English",
                example_type='language_identification',
                confidence_score=0.9,
                source_page=1,
                context="Language pattern analysis",
                metadata={'word_type': 'english', 'has_accents': False}
            ))
        
        logger.info(f"🔤 Generated {len(examples)} pattern recognition examples")
        return examples
    
    def _generate_completion_tasks(self, parsed_doc) -> List[TrainingExample]:
        """Generate text completion tasks for training"""
        examples = []
        
        for node in parsed_doc.structure_tree:
            text = node.text.strip()
            
            # Skip very short texts
            if len(text.split()) < 6:
                continue
            
            words = text.split()
            text_length = len(words)
            
            # Generate completion tasks of different lengths
            for completion_ratio in [0.3, 0.5, 0.7]:
                split_point = int(text_length * completion_ratio)
                if split_point > 0 and split_point < text_length:
                    input_part = ' '.join(words[:split_point])
                    output_part = ' '.join(words[split_point:])
                    
                    examples.append(TrainingExample(
                        input_text=f"Complete this text: '{input_part}'",
                        output_text=output_part,
                        example_type='text_completion',
                        confidence_score=0.6,
                        source_page=node.page_number,
                        context=f"Completion ratio: {completion_ratio}",
                        metadata={
                            'completion_ratio': completion_ratio,
                            'input_length': len(input_part),
                            'output_length': len(output_part)
                        }
                    ))
        
        logger.info(f"📝 Generated {len(examples)} completion task examples")
        return examples
    
    def _generate_classification_tasks(self, parsed_doc) -> List[TrainingExample]:
        """Generate text classification tasks"""
        examples = []
        
        # Classify content types
        content_types = {
            'definition': [],
            'example': [],
            'heading': [],
            'list_item': [],
            'explanation': []
        }
        
        for node in parsed_doc.structure_tree:
            text = node.text.strip()
            
            # Classify based on structure level and content
            if node.level <= 2:
                content_types['heading'].append((text, node))
            elif any(marker in text.lower() for marker in self.dictionary_indicators['example_markers']):
                content_types['example'].append((text, node))
            elif any(word in text.lower() for word in self.dictionary_indicators['definition_words']):
                content_types['definition'].append((text, node))
            elif text.startswith('-') or text.startswith('•') or re.match(r'^\d+\.', text):
                content_types['list_item'].append((text, node))
            else:
                content_types['explanation'].append((text, node))
        
        # Generate classification examples
        for content_type, items in content_types.items():
            for text, node in items[:20]:  # Limit per category
                examples.append(TrainingExample(
                    input_text=f"Classify this text type: '{text[:100]}...'",
                    output_text=content_type.replace('_', ' '),
                    example_type='content_classification',
                    confidence_score=0.8,
                    source_page=node.page_number,
                    context=f"Structure level: {node.level}",
                    metadata={
                        'true_type': content_type,
                        'structure_level': node.level
                    }
                ))
        
        logger.info(f"🏷️ Generated {len(examples)} classification examples")
        return examples
    
    def _is_valid_dictionary_pair(self, left: str, right: str, separator: str) -> bool:
        """Validate if left-right pair forms a valid dictionary entry"""
        # Basic length checks
        if len(left) < 2 or len(right) < 3 or len(left) > 100 or len(right) > 300:
            return False
        
        # Check if left side looks like a word (not a sentence)
        left_words = left.split()
        if len(left_words) > 5:  # Too many words for a dictionary entry
            return False
        
        # Check for proper separator context
        if separator.strip() in ['-', '–', '—', 'means', 'is', ':']:
            return True
        
        # Check language patterns
        has_chuukese = self.word_patterns['chuukese'].search(left)
        has_english = self.word_patterns['english'].search(right)
        
        return has_chuukese or has_english
    
    def _calculate_pair_confidence(self, left: str, right: str, separator: str) -> float:
        """Calculate confidence score for dictionary pair"""
        confidence = 0.5  # Base confidence
        
        # Separator quality
        if separator.strip() in ['–', '—', 'means', 'is']:
            confidence += 0.2
        elif separator.strip() in ['-', ':']:
            confidence += 0.1
        
        # Length appropriateness
        left_len, right_len = len(left.split()), len(right.split())
        if 1 <= left_len <= 3 and 2 <= right_len <= 20:
            confidence += 0.2
        
        # Language pattern match
        if self.word_patterns['chuukese'].search(left):
            confidence += 0.1
        if self.word_patterns['english'].search(right):
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _generate_pair_variations(self, source: str, target: str) -> List[Tuple[str, str]]:
        """Generate multiple training variations from a source-target pair"""
        variations = []
        
        # Direct translation
        variations.append((f"Translate: {source}", target))
        variations.append((f"What does '{source}' mean?", target))
        variations.append((f"Definition of {source}:", target))
        
        # Reverse if appropriate
        if self.word_patterns['english'].search(target):
            variations.append((f"How do you say '{target}' in Chuukese?", source))
            variations.append((f"Translate to Chuukese: {target}", source))
        
        return variations
    
    def _is_valid_word(self, word: str) -> bool:
        """Check if string is a valid word for dictionary purposes"""
        word = word.strip()
        if len(word) < 2 or len(word) > 50:
            return False
        
        # Should contain letters
        if not re.search(r'[a-zA-Z]', word):
            return False
        
        # Shouldn't be all numbers or punctuation
        if re.match(r'^[\d\W]+$', word):
            return False
        
        return True
    
    def _describe_level(self, level: int) -> str:
        """Describe what a structure level represents"""
        descriptions = {
            1: "Major heading",
            2: "Section heading", 
            3: "Subsection heading",
            4: "List item or minor heading",
            5: "Dictionary entry or indented content",
            6: "Body text or paragraph"
        }
        return descriptions.get(level, f"Level {level} content")
    
    def _filter_and_balance_data(self, training_data: Dict[str, List[TrainingExample]], 
                                target_count: int) -> Dict[str, List[TrainingExample]]:
        """Filter low-quality examples and balance dataset"""
        filtered_data = {}
        
        # Filter by confidence
        for category, examples in training_data.items():
            filtered = [ex for ex in examples if ex.confidence_score >= self.min_confidence]
            
            # Remove duplicates based on input text
            seen_inputs = set()
            unique_examples = []
            for ex in filtered:
                input_hash = hashlib.md5(ex.input_text.encode()).hexdigest()
                if input_hash not in seen_inputs:
                    seen_inputs.add(input_hash)
                    unique_examples.append(ex)
            
            # Sort by confidence and take best examples
            unique_examples.sort(key=lambda x: x.confidence_score, reverse=True)
            filtered_data[category] = unique_examples
        
        # Balance dataset
        total_examples = sum(len(examples) for examples in filtered_data.values())
        if total_examples > target_count:
            # Proportionally reduce each category
            for category in filtered_data:
                current_count = len(filtered_data[category])
                target_for_category = max(1, int((current_count / total_examples) * target_count))
                filtered_data[category] = filtered_data[category][:target_for_category]
        
        return filtered_data
    
    def export_training_data(self, training_data: Dict[str, List[TrainingExample]], 
                           output_dir: str, format_type: str = 'jsonl') -> Dict[str, str]:
        """
        Export training data in various formats
        
        Args:
            training_data: Generated training data
            output_dir: Output directory
            format_type: 'jsonl', 'csv', 'huggingface', 'ollama'
            
        Returns:
            Dictionary of saved file paths
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        saved_files = {}
        
        for category, examples in training_data.items():
            if not examples:
                continue
            
            file_base = f"training_{category}"
            
            if format_type == 'jsonl':
                file_path = output_path / f"{file_base}.jsonl"
                with open(file_path, 'w', encoding='utf-8') as f:
                    for ex in examples:
                        json_obj = {
                            'input': ex.input_text,
                            'output': ex.output_text,
                            'type': ex.example_type,
                            'confidence': ex.confidence_score,
                            'metadata': ex.metadata
                        }
                        f.write(json.dumps(json_obj, ensure_ascii=False) + '\n')
                
            elif format_type == 'huggingface':
                file_path = output_path / f"{file_base}_hf.json"
                hf_format = {
                    'train': [{
                        'text': f"### Instruction:\n{ex.input_text}\n\n### Response:\n{ex.output_text}"
                    } for ex in examples]
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(hf_format, f, indent=2, ensure_ascii=False)
            
            elif format_type == 'ollama':
                file_path = output_path / f"{file_base}_ollama.jsonl"
                with open(file_path, 'w', encoding='utf-8') as f:
                    for ex in examples:
                        ollama_obj = {
                            'prompt': ex.input_text,
                            'response': ex.output_text,
                            'system': f"You are a helpful assistant specialized in Chuukese language and dictionary content."
                        }
                        f.write(json.dumps(ollama_obj, ensure_ascii=False) + '\n')
            
            saved_files[category] = str(file_path)
        
        # Create summary file
        summary_path = output_path / "training_summary.json"
        summary = {
            'total_categories': len(training_data),
            'total_examples': sum(len(examples) for examples in training_data.values()),
            'categories': {cat: len(examples) for cat, examples in training_data.items()},
            'format': format_type,
            'files': saved_files,
            'confidence_stats': {
                cat: {
                    'min': min(ex.confidence_score for ex in examples) if examples else 0,
                    'max': max(ex.confidence_score for ex in examples) if examples else 0,
                    'avg': sum(ex.confidence_score for ex in examples) / len(examples) if examples else 0
                } for cat, examples in training_data.items()
            }
        }
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Training data exported to {output_dir}")
        logger.info(f"📋 Summary saved to {summary_path}")
        
        return saved_files

# CLI interface
def main():
    """CLI for training data generation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Training Data Generator for Large Documents')
    parser.add_argument('structure_file', help='Path to parsed document structure JSON')
    parser.add_argument('--output-dir', default='training_output', help='Output directory')
    parser.add_argument('--target-count', type=int, default=5000, help='Target number of examples')
    parser.add_argument('--format', choices=['jsonl', 'csv', 'huggingface', 'ollama'], 
                       default='jsonl', help='Output format')
    parser.add_argument('--min-confidence', type=float, default=0.7, help='Minimum confidence threshold')
    
    args = parser.parse_args()
    
    # Load parsed document structure
    with open(args.structure_file, 'r', encoding='utf-8') as f:
        structure_data = json.load(f)
    
    # Initialize generator
    generator = AITrainingDataGenerator(min_confidence=args.min_confidence)
    
    # Generate training data
    # Note: Would need to reconstruct ParsedDocument from JSON for full functionality
    logger.info("📊 This tool requires integration with AdvancedDocumentParser output")
    logger.info("🔧 Use together with advanced_document_parser.py for best results")

if __name__ == "__main__":
    main()