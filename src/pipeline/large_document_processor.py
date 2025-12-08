#!/usr/bin/env python3
"""
Large Document Processing Pipeline
==================================

Complete pipeline for processing large documents (200+ pages) with
intelligent chunking, structure preservation, and AI training data generation.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# Import our custom modules
from ..ocr.advanced_document_parser import AdvancedDocumentParser, ParsedDocument
from ..training.ai_training_generator import AITrainingDataGenerator
from ..database.dictionary_db import DictionaryDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessingConfig:
    """Configuration for document processing pipeline"""
    chunk_size_pages: int = 50  # Process in chunks to manage memory
    parallel_workers: int = 4
    preserve_formatting: bool = True
    generate_training_data: bool = True
    target_training_examples: int = 10000
    min_confidence: float = 0.7
    output_formats: List[str] = None
    
    def __post_init__(self):
        if self.output_formats is None:
            self.output_formats = ['jsonl', 'ollama']

class LargeDocumentProcessor:
    """
    Complete pipeline for processing large structured documents
    """
    
    def __init__(self, config: ProcessingConfig = None):
        self.config = config or ProcessingConfig()
        self.document_parser = AdvancedDocumentParser(preserve_formatting=self.config.preserve_formatting)
        self.training_generator = AITrainingDataGenerator(min_confidence=self.config.min_confidence)
        self.db = DictionaryDB()
        
    def process_large_document(self, input_file: str, output_dir: str) -> Dict[str, any]:
        """
        Complete processing pipeline for large documents
        
        Args:
            input_file: Path to input document (DOCX or PDF)
            output_dir: Output directory for all results
            
        Returns:
            Dictionary with processing results and file paths
        """
        start_time = time.time()
        input_path = Path(input_file)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        logger.info(f"🚀 Starting large document processing pipeline")
        logger.info(f"📁 Input: {input_file}")
        logger.info(f"📁 Output: {output_dir}")
        logger.info(f"⚙️ Config: {self.config}")
        
        results = {
            'input_file': input_file,
            'output_directory': output_dir,
            'processing_start': start_time,
            'stages': {}
        }
        
        try:
            # Stage 1: Parse document structure
            logger.info("📖 Stage 1: Parsing document structure...")
            stage_start = time.time()
            
            if input_path.suffix.lower() == '.docx':
                parsed_doc = self.document_parser.parse_large_docx(input_file)
            elif input_path.suffix.lower() == '.pdf':
                parsed_doc = self.document_parser.parse_large_pdf(input_file)
            else:
                raise ValueError(f"Unsupported file format: {input_path.suffix}")
            
            stage_duration = time.time() - stage_start
            results['stages']['parsing'] = {
                'duration_seconds': stage_duration,
                'paragraphs_processed': parsed_doc.total_paragraphs,
                'pages_processed': parsed_doc.total_pages,
                'structure_nodes': len(parsed_doc.structure_tree)
            }
            
            logger.info(f"✅ Parsing complete: {stage_duration:.1f}s")
            
            # Stage 2: Export document structure
            logger.info("💾 Stage 2: Exporting document structure...")
            stage_start = time.time()
            
            structure_file = output_path / f"{input_path.stem}_structure.json"
            self.document_parser.export_structure_json(parsed_doc, str(structure_file))
            
            # Save raw extracted text
            text_file = output_path / f"{input_path.stem}_extracted_text.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(parsed_doc.raw_text)
            
            stage_duration = time.time() - stage_start
            results['stages']['export_structure'] = {
                'duration_seconds': stage_duration,
                'structure_file': str(structure_file),
                'text_file': str(text_file),
                'text_length_chars': len(parsed_doc.raw_text)
            }
            
            # Stage 3: Generate AI training data
            if self.config.generate_training_data:
                logger.info("🎯 Stage 3: Generating AI training data...")
                stage_start = time.time()
                
                training_data = self.training_generator.generate_comprehensive_training_data(
                    parsed_doc, 
                    target_count=self.config.target_training_examples
                )
                
                # Export training data in multiple formats
                training_dir = output_path / "training_data"
                training_files = {}
                
                for format_type in self.config.output_formats:
                    format_files = self.training_generator.export_training_data(
                        training_data, 
                        str(training_dir), 
                        format_type=format_type
                    )
                    training_files[format_type] = format_files
                
                stage_duration = time.time() - stage_start
                total_examples = sum(len(examples) for examples in training_data.values())
                
                results['stages']['training_data'] = {
                    'duration_seconds': stage_duration,
                    'total_examples': total_examples,
                    'categories': len(training_data),
                    'formats_exported': self.config.output_formats,
                    'training_files': training_files,
                    'category_breakdown': {cat: len(examples) for cat, examples in training_data.items()}
                }
            
            # Stage 4: Extract and index dictionary entries
            logger.info("📚 Stage 4: Extracting dictionary entries...")
            stage_start = time.time()
            
            dictionary_entries = self._extract_dictionary_entries(parsed_doc)
            
            # Save to CSV for database import
            csv_file = output_path / f"{input_path.stem}_dictionary.csv"
            self._save_dictionary_csv(dictionary_entries, csv_file)
            
            # Optionally import to database
            imported_count = 0
            if dictionary_entries:
                imported_count = self._import_to_database(dictionary_entries)
            
            stage_duration = time.time() - stage_start
            results['stages']['dictionary_extraction'] = {
                'duration_seconds': stage_duration,
                'entries_extracted': len(dictionary_entries),
                'csv_file': str(csv_file),
                'imported_to_database': imported_count
            }
            
            # Stage 5: Generate processing report
            logger.info("📊 Stage 5: Generating processing report...")
            stage_start = time.time()
            
            report_file = output_path / f"{input_path.stem}_processing_report.json"
            self._generate_processing_report(results, parsed_doc, report_file)
            
            stage_duration = time.time() - stage_start
            results['stages']['report_generation'] = {
                'duration_seconds': stage_duration,
                'report_file': str(report_file)
            }
            
            # Calculate total processing time
            total_duration = time.time() - start_time
            results['total_duration_seconds'] = total_duration
            results['processing_end'] = time.time()
            
            logger.info(f"🎉 Pipeline complete! Total time: {total_duration:.1f}s")
            logger.info(f"📁 Results saved to: {output_dir}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {str(e)}")
            results['error'] = str(e)
            results['total_duration_seconds'] = time.time() - start_time
            raise
    
    def process_multiple_documents(self, input_files: List[str], output_base_dir: str) -> Dict[str, any]:
        """
        Process multiple documents in parallel
        
        Args:
            input_files: List of paths to input documents
            output_base_dir: Base output directory
            
        Returns:
            Dictionary with results for each document
        """
        output_base = Path(output_base_dir)
        output_base.mkdir(exist_ok=True)
        
        logger.info(f"🔄 Processing {len(input_files)} documents in parallel")
        
        results = {
            'total_documents': len(input_files),
            'processing_start': time.time(),
            'documents': {}
        }
        
        def process_single_doc(file_path: str) -> Tuple[str, Dict]:
            try:
                file_name = Path(file_path).stem
                doc_output_dir = output_base / file_name
                
                doc_result = self.process_large_document(file_path, str(doc_output_dir))
                return file_path, {'status': 'success', 'result': doc_result}
            except Exception as e:
                return file_path, {'status': 'error', 'error': str(e)}
        
        # Process documents in parallel
        with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
            futures = {executor.submit(process_single_doc, file_path): file_path 
                      for file_path in input_files}
            
            for future in as_completed(futures):
                file_path, result = future.result()
                results['documents'][file_path] = result
                
                if result['status'] == 'success':
                    logger.info(f"✅ Completed: {Path(file_path).name}")
                else:
                    logger.error(f"❌ Failed: {Path(file_path).name} - {result['error']}")
        
        results['processing_end'] = time.time()
        results['total_duration'] = results['processing_end'] - results['processing_start']
        
        # Generate summary report
        summary_file = output_base / "processing_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        
        success_count = sum(1 for r in results['documents'].values() if r['status'] == 'success')
        logger.info(f"🏁 Batch processing complete: {success_count}/{len(input_files)} successful")
        
        return results
    
    def _extract_dictionary_entries(self, parsed_doc: ParsedDocument) -> List[Dict[str, str]]:
        """Extract dictionary entries from parsed document"""
        entries = []
        entry_num = 1
        
        for node in parsed_doc.structure_tree:
            text = node.text.strip()
            
            # Look for dictionary-style entries
            separators = ['–', '—', ' - ', '  ', '\t']
            for sep in separators:
                if sep in text and not self._is_page_marker(text):
                    parts = text.split(sep, 1)
                    if len(parts) == 2:
                        chuukese = parts[0].strip()
                        english = parts[1].strip()
                        
                        # Validate entry
                        if (len(chuukese) > 1 and len(english) > 2 and 
                            len(chuukese.split()) <= 5 and
                            not chuukese.isdigit()):
                            
                            entries.append({
                                'Entry #': entry_num,
                                'Pseudo-Page': node.page_number,
                                'Chuukese Word / Form': chuukese,
                                'Part of Speech': '',  # Could extract from formatting
                                'English Definition': english,
                                'Examples': '',
                                'Notes': f'Extracted from page {node.page_number}'
                            })
                            entry_num += 1
                    break
        
        logger.info(f"📖 Extracted {len(entries)} dictionary entries")
        return entries
    
    def _is_page_marker(self, text: str) -> bool:
        """Check if text is a page marker"""
        import re
        patterns = [
            r'^page\s+\d+', r'^\d+$', r'^p\.\s*\d+',
            r'chapter\s+\d+', r'section\s+\d+'
        ]
        text_lower = text.lower().strip()
        return any(re.match(pattern, text_lower) for pattern in patterns)
    
    def _save_dictionary_csv(self, entries: List[Dict[str, str]], output_file: str):
        """Save dictionary entries to CSV file"""
        if not entries:
            return
        
        import csv
        
        fieldnames = ['Entry #', 'Pseudo-Page', 'Chuukese Word / Form', 
                     'Part of Speech', 'English Definition', 'Examples', 'Notes']
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entries)
        
        logger.info(f"💾 Dictionary CSV saved: {output_file}")
    
    def _import_to_database(self, entries: List[Dict[str, str]]) -> int:
        """Import dictionary entries to database"""
        try:
            imported = 0
            for entry in entries:
                # Convert to database format
                db_entry = {
                    'chuukese_word': entry['Chuukese Word / Form'],
                    'english_translation': entry['English Definition'],
                    'part_of_speech': entry.get('Part of Speech', ''),
                    'examples': entry.get('Examples', ''),
                    'notes': entry.get('Notes', ''),
                    'page_number': entry.get('Pseudo-Page', 1),
                    'source': 'large_document_processor'
                }
                
                # Check for duplicates before inserting
                existing = self.db.dictionary_collection.find_one({
                    'chuukese_word': db_entry['chuukese_word'],
                    'english_translation': db_entry['english_translation']
                })
                
                if not existing:
                    self.db.dictionary_collection.insert_one(db_entry)
                    imported += 1
            
            logger.info(f"📚 Imported {imported} new dictionary entries to database")
            return imported
            
        except Exception as e:
            logger.error(f"❌ Database import failed: {e}")
            return 0
    
    def _generate_processing_report(self, results: Dict, parsed_doc: ParsedDocument, output_file: str):
        """Generate comprehensive processing report"""
        report = {
            'processing_summary': results,
            'document_analysis': {
                'total_pages': parsed_doc.total_pages,
                'total_paragraphs': parsed_doc.total_paragraphs,
                'text_length_chars': len(parsed_doc.raw_text),
                'text_length_words': len(parsed_doc.raw_text.split()),
                'structure_levels': len(set(node.level for node in parsed_doc.structure_tree)),
                'avg_words_per_paragraph': len(parsed_doc.raw_text.split()) / max(parsed_doc.total_paragraphs, 1)
            },
            'quality_metrics': {
                'pages_per_hour': parsed_doc.total_pages / (results['total_duration_seconds'] / 3600),
                'paragraphs_per_second': parsed_doc.total_paragraphs / results['total_duration_seconds'],
                'structure_complexity': len(parsed_doc.structure_tree) / max(parsed_doc.total_paragraphs, 1)
            },
            'recommendations': self._generate_recommendations(parsed_doc, results)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"📊 Processing report saved: {output_file}")
    
    def _generate_recommendations(self, parsed_doc: ParsedDocument, results: Dict) -> List[str]:
        """Generate recommendations based on processing results"""
        recommendations = []
        
        # Document size recommendations
        if parsed_doc.total_pages > 200:
            recommendations.append("Consider processing in smaller chunks for better memory efficiency")
        
        # Training data quality
        if 'training_data' in results['stages']:
            total_examples = results['stages']['training_data']['total_examples']
            if total_examples < 1000:
                recommendations.append("Low training data yield - consider improving dictionary entry detection patterns")
            elif total_examples > 20000:
                recommendations.append("High training data volume - consider data quality filtering")
        
        # Structure complexity
        structure_ratio = len(parsed_doc.structure_tree) / max(parsed_doc.total_paragraphs, 1)
        if structure_ratio < 0.1:
            recommendations.append("Low structure detection - document may need custom parsing patterns")
        
        # Processing speed
        if 'parsing' in results['stages']:
            pages_per_second = parsed_doc.total_pages / results['stages']['parsing']['duration_seconds']
            if pages_per_second < 0.5:
                recommendations.append("Slow processing speed - consider parallel processing or simpler parsing")
        
        return recommendations

# CLI interface
def main():
    """Command line interface for large document processing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Large Document Processing Pipeline')
    parser.add_argument('input', help='Input document file or directory')
    parser.add_argument('--output-dir', default='output', help='Output directory')
    parser.add_argument('--chunk-size', type=int, default=50, help='Page chunk size')
    parser.add_argument('--workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--target-examples', type=int, default=10000, help='Target training examples')
    parser.add_argument('--formats', nargs='+', choices=['jsonl', 'csv', 'huggingface', 'ollama'],
                       default=['jsonl', 'ollama'], help='Output formats')
    parser.add_argument('--no-training', action='store_true', help='Skip training data generation')
    parser.add_argument('--batch', action='store_true', help='Process multiple files in input directory')
    
    args = parser.parse_args()
    
    # Create configuration
    config = ProcessingConfig(
        chunk_size_pages=args.chunk_size,
        parallel_workers=args.workers,
        generate_training_data=not args.no_training,
        target_training_examples=args.target_examples,
        output_formats=args.formats
    )
    
    # Initialize processor
    processor = LargeDocumentProcessor(config)
    
    input_path = Path(args.input)
    
    try:
        if args.batch and input_path.is_dir():
            # Batch processing
            supported_extensions = ['.docx', '.pdf']
            input_files = [
                str(f) for f in input_path.rglob('*') 
                if f.suffix.lower() in supported_extensions and f.is_file()
            ]
            
            if not input_files:
                logger.error("No supported documents found in directory")
                return
            
            logger.info(f"Found {len(input_files)} documents to process")
            results = processor.process_multiple_documents(input_files, args.output_dir)
            
        else:
            # Single file processing
            if not input_path.is_file():
                logger.error(f"File not found: {input_path}")
                return
            
            results = processor.process_large_document(str(input_path), args.output_dir)
        
        logger.info("🎉 Processing pipeline completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        raise

if __name__ == "__main__":
    main()