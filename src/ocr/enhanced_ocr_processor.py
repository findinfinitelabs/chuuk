#!/usr/bin/env python3
"""
Enhanced OCR Processor with Large Document Support
==================================================

Extends the existing OCR processor with advanced document parsing
and large document processing capabilities.
"""

import os
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
import logging

# Import existing OCR processor
from .ocr_processor import OCRProcessor

# Import new advanced capabilities
try:
    from .advanced_document_parser import AdvancedDocumentParser
    from ..training.ai_training_generator import AITrainingDataGenerator
    from ..pipeline.large_document_processor import LargeDocumentProcessor, ProcessingConfig
    from ..utils.intelligent_chunker import IntelligentTextChunker, ChunkType
    ADVANCED_FEATURES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Advanced features not available: {e}")
    ADVANCED_FEATURES_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedOCRProcessor(OCRProcessor):
    """
    Enhanced OCR processor with large document processing capabilities
    """
    
    def __init__(self, use_google_vision: bool = False, enable_advanced_features: bool = True):
        """
        Initialize enhanced OCR processor
        
        Args:
            use_google_vision: Whether to use Google Vision API
            enable_advanced_features: Whether to enable advanced document processing
        """
        super().__init__(use_google_vision)
        
        self.enable_advanced_features = enable_advanced_features and ADVANCED_FEATURES_AVAILABLE
        
        if self.enable_advanced_features:
            self.advanced_parser = AdvancedDocumentParser()
            self.training_generator = AITrainingDataGenerator()
            self.text_chunker = IntelligentTextChunker()
            self.large_doc_processor = LargeDocumentProcessor()
            logger.info("🚀 Enhanced OCR processor initialized with advanced features")
        else:
            logger.info("📄 Standard OCR processor initialized")
    
    def process_large_document(self, file_path: str, 
                              output_dir: str = None,
                              generate_training_data: bool = True,
                              chunk_for_ai: bool = True) -> Dict[str, any]:
        """
        Process large documents (200+ pages) with advanced analysis
        
        Args:
            file_path: Path to large document (DOCX or PDF)
            output_dir: Output directory (auto-generated if None)
            generate_training_data: Whether to generate AI training data
            chunk_for_ai: Whether to create AI-optimized chunks
            
        Returns:
            Dictionary with processing results
        """
        if not self.enable_advanced_features:
            logger.warning("⚠️ Advanced features not available, falling back to standard processing")
            return self.process_image(file_path)
        
        logger.info(f"📚 Processing large document: {os.path.basename(file_path)}")
        
        # Auto-generate output directory
        if not output_dir:
            file_stem = Path(file_path).stem
            output_dir = f"output/large_documents/{file_stem}_{int(time.time())}"
        
        # Configure processing
        config = ProcessingConfig(
            generate_training_data=generate_training_data,
            target_training_examples=10000 if generate_training_data else 0,
            preserve_formatting=True,
            parallel_workers=2  # Conservative for stability
        )
        
        # Process with large document pipeline
        results = self.large_doc_processor.process_large_document(
            file_path, output_dir
        )
        
        # Add AI chunking if requested
        if chunk_for_ai and 'text_file' in results.get('stages', {}).get('export_structure', {}):
            text_file = results['stages']['export_structure']['text_file']
            chunk_results = self._create_ai_chunks(text_file, output_dir)
            results['ai_chunks'] = chunk_results
        
        # Enhance with OCR-specific metadata
        results['ocr_metadata'] = {
            'processor_type': 'enhanced_ocr_large_document',
            'google_vision_used': self.use_google_vision,
            'advanced_features': True,
            'processing_timestamp': time.time()
        }
        
        return results
    
    def process_with_intelligent_chunking(self, file_path: str, 
                                        chunk_type: str = "semantic",
                                        max_chunk_size: int = 512) -> Dict[str, any]:
        """
        Process document with intelligent chunking for AI training
        
        Args:
            file_path: Path to document
            chunk_type: Type of chunking (semantic, structural, fixed_size, sliding_window)
            max_chunk_size: Maximum size per chunk
            
        Returns:
            Dictionary with chunked results
        """
        if not self.enable_advanced_features:
            return self.process_image(file_path)
        
        logger.info(f"🔪 Processing with intelligent chunking: {chunk_type}")
        
        # First do standard OCR processing
        ocr_results = self.process_image(file_path)
        
        if 'text' not in ocr_results:
            return ocr_results
        
        # Apply intelligent chunking
        chunker = IntelligentTextChunker(max_chunk_size=max_chunk_size)
        chunk_type_enum = ChunkType(chunk_type)
        chunks = chunker.chunk_document(ocr_results['text'], chunk_type_enum)
        
        # Add chunk information to results
        ocr_results['chunks'] = {
            'total_chunks': len(chunks),
            'chunk_type': chunk_type,
            'chunks': [{
                'content': chunk.content,
                'size': len(chunk.content),
                'word_count': chunk.word_count,
                'chunk_id': chunk.chunk_id,
                'metadata': chunk.metadata
            } for chunk in chunks],
            'statistics': chunker.get_chunk_statistics(chunks)
        }
        
        return ocr_results
    
    def extract_training_examples(self, file_path: str, 
                                 min_examples: int = 1000) -> Dict[str, any]:
        """
        Extract training examples from a processed document
        
        Args:
            file_path: Path to document
            min_examples: Minimum number of examples to generate
            
        Returns:
            Dictionary with training examples and metadata
        """
        if not self.enable_advanced_features:
            logger.warning("⚠️ Training example extraction requires advanced features")
            return {'error': 'Advanced features not available'}
        
        logger.info(f"🎯 Extracting training examples from: {os.path.basename(file_path)}")
        
        # Parse document structure
        file_ext = Path(file_path).suffix.lower()
        if file_ext == '.docx':
            parsed_doc = self.advanced_parser.parse_large_docx(file_path)
        elif file_ext == '.pdf':
            parsed_doc = self.advanced_parser.parse_large_pdf(file_path)
        else:
            # Fall back to OCR for images
            ocr_results = self.process_image(file_path)
            return {
                'warning': 'Limited training data from OCR text only',
                'ocr_text': ocr_results.get('text', ''),
                'basic_examples': self._create_basic_examples(ocr_results.get('text', ''))
            }
        
        # Generate comprehensive training data
        training_data = self.training_generator.generate_comprehensive_training_data(
            parsed_doc, target_count=min_examples
        )
        
        # Export in multiple formats
        output_dir = f"output/training_data/{Path(file_path).stem}"
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        exported_files = self.training_generator.export_training_data(
            training_data, output_dir, format_type='ollama'
        )
        
        return {
            'training_data': training_data,
            'exported_files': exported_files,
            'statistics': {
                'total_examples': sum(len(examples) for examples in training_data.values()),
                'categories': len(training_data),
                'source_document': file_path,
                'processing_metadata': parsed_doc.metadata
            }
        }
    
    def _create_ai_chunks(self, text_file: str, output_dir: str) -> Dict[str, any]:
        """Create AI-optimized chunks from extracted text"""
        
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Create multiple chunk types for different use cases
        chunk_results = {}
        
        chunk_configs = [
            ('training_chunks', ChunkType.SEMANTIC, 512),
            ('context_chunks', ChunkType.STRUCTURAL, 1024), 
            ('sliding_chunks', ChunkType.SLIDING_WINDOW, 256)
        ]
        
        for name, chunk_type, max_size in chunk_configs:
            chunker = IntelligentTextChunker(max_chunk_size=max_size)
            chunks = chunker.chunk_document(text, chunk_type)
            
            # Save chunks to files
            chunk_dir = Path(output_dir) / name
            chunk_dir.mkdir(exist_ok=True)
            
            chunk_files = []
            for i, chunk in enumerate(chunks):
                chunk_file = chunk_dir / f"chunk_{i:04d}.txt"
                with open(chunk_file, 'w', encoding='utf-8') as f:
                    f.write(chunk.content)
                chunk_files.append(str(chunk_file))
            
            chunk_results[name] = {
                'chunk_type': chunk_type.value,
                'total_chunks': len(chunks),
                'max_size': max_size,
                'files': chunk_files,
                'statistics': chunker.get_chunk_statistics(chunks)
            }
        
        return chunk_results
    
    def _create_basic_examples(self, text: str) -> List[Dict[str, str]]:
        """Create basic training examples from raw OCR text"""
        examples = []
        
        # Look for dictionary-style patterns in OCR text
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # Look for common separators
            for sep in ['–', '—', ' - ', '  ', '\t']:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2:
                        source = parts[0].strip()
                        target = parts[1].strip()
                        
                        if len(source) > 1 and len(target) > 2:
                            examples.append({
                                'input': f"What does '{source}' mean?",
                                'output': target,
                                'source': 'ocr_extraction'
                            })
                    break
        
        return examples

# Integration with existing app.py
def integrate_with_flask_app():
    """
    Example of how to integrate enhanced OCR processor with existing Flask app
    """
    
    integration_code = '''
# Add to app.py imports:
from src.ocr.enhanced_ocr_processor import EnhancedOCRProcessor

# Replace OCRProcessor initialization with:
enhanced_ocr_processor = EnhancedOCRProcessor(
    use_google_vision=bool(os.getenv('GOOGLE_APPLICATION_CREDENTIALS')),
    enable_advanced_features=True
)

# Add new route for large document processing:
@app.route('/process_large_document', methods=['POST'])
def process_large_document():
    """Process large documents with advanced features"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save uploaded file
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    try:
        # Process with enhanced features
        results = enhanced_ocr_processor.process_large_document(
            file_path, 
            generate_training_data=True,
            chunk_for_ai=True
        )
        
        return jsonify({
            'status': 'success',
            'results': results,
            'message': 'Large document processed successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add route for training data extraction:
@app.route('/extract_training_data', methods=['POST'])
def extract_training_data():
    """Extract training data from uploaded document"""
    # Similar implementation for training data extraction
    pass
    '''
    
    return integration_code

if __name__ == "__main__":
    # Demo usage
    processor = EnhancedOCRProcessor(enable_advanced_features=True)
    
    print("🚀 Enhanced OCR Processor Demo")
    print("Features available:", processor.enable_advanced_features)
    
    if processor.enable_advanced_features:
        print("\n📚 Large document processing: READY")
        print("🎯 Training data generation: READY") 
        print("🔪 Intelligent chunking: READY")
        print("📊 Advanced analytics: READY")
    else:
        print("\n📄 Standard OCR processing only")
    
    print("\nIntegration code:")
    print(integrate_with_flask_app())