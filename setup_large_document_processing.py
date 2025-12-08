#!/usr/bin/env python3
"""
Large Document Processing Setup and Demo
========================================

Complete setup and demonstration of large document processing capabilities
for processing 285-page dictionary with AI training data generation.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List

def main():
    """Main setup and demo function"""
    print("🚀 Chuuk Dictionary Large Document Processing Setup")
    print("=" * 60)
    
    # Check if we're in the right directory
    cwd = Path.cwd()
    if not (cwd / "src").exists():
        print("❌ Please run this script from the project root directory")
        sys.exit(1)
    
    print(f"📁 Working directory: {cwd}")
    
    # Add src to Python path for imports
    src_path = str(cwd / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    # Check dependencies
    print("\n📦 Checking dependencies...")
    missing_deps = check_dependencies()
    
    if missing_deps:
        print(f"❌ Missing dependencies: {', '.join(missing_deps)}")
        print("💡 Install with: pip install -r requirements.txt")
        
        install_choice = input("🔧 Would you like to install missing dependencies now? (y/n): ")
        if install_choice.lower() == 'y':
            install_dependencies()
        else:
            print("⚠️ Some features may not work without all dependencies")
    else:
        print("✅ All dependencies are installed")
    
    # Setup directories
    print("\n📁 Setting up directories...")
    setup_directories()
    
    # Demonstrate capabilities
    print("\n🎯 Demonstrating large document processing capabilities...")
    demo_capabilities()
    
    # Show usage examples
    print("\n📚 Usage examples for your 285-page document:")
    show_usage_examples()
    
    print("\n🎉 Setup complete! Your system is ready for large document processing.")

def check_dependencies() -> List[str]:
    """Check which dependencies are missing"""
    required_packages = [
        'docx',      # python-docx
        'fitz',      # PyMuPDF
        'PIL',       # Pillow
        'transformers',
        'torch',
        'pandas',
        'numpy',
        'requests'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    return missing

def install_dependencies():
    """Install missing dependencies"""
    import subprocess
    
    print("📦 Installing dependencies...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True, capture_output=True, text=True)
        print("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation failed: {e}")
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)

def setup_directories():
    """Create necessary directories"""
    directories = [
        "output",
        "output/large_documents",
        "output/training_data", 
        "output/chunks",
        "output/reports",
        "logs/processing",
        "models/custom"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created: {dir_path}")

def demo_capabilities():
    """Demonstrate the large document processing capabilities"""
    
    print("\n🔍 Available Processing Capabilities:")
    print("-" * 40)
    
    capabilities = [
        {
            'name': 'Advanced Document Parser',
            'description': 'Parses 285-page documents with structure preservation',
            'features': [
                '✅ DOCX and PDF support',
                '✅ Hierarchical structure detection',
                '✅ Formatting preservation',
                '✅ Page-by-page processing',
                '✅ Memory-efficient chunking'
            ]
        },
        {
            'name': 'AI Training Data Generator', 
            'description': 'Generates 10,000+ training examples automatically',
            'features': [
                '✅ Dictionary pair extraction',
                '✅ Contextual definitions',
                '✅ Multiple training formats (JSONL, Ollama)',
                '✅ Quality filtering and balancing',
                '✅ Semantic chunking'
            ]
        },
        {
            'name': 'Large Document Processor',
            'description': 'Complete pipeline for processing large documents',
            'features': [
                '✅ Parallel processing support',
                '✅ Progress tracking and logging',
                '✅ Automatic database integration',
                '✅ Comprehensive reporting',
                '✅ Error recovery and resumption'
            ]
        },
        {
            'name': 'Intelligent Text Chunker',
            'description': 'Smart chunking that preserves meaning',
            'features': [
                '✅ Semantic boundary detection',
                '✅ Structure-aware splitting',
                '✅ Configurable overlap',
                '✅ Multi-language support',
                '✅ Optimized for AI training'
            ]
        }
    ]
    
    for cap in capabilities:
        print(f"\n🧩 {cap['name']}")
        print(f"   {cap['description']}")
        for feature in cap['features']:
            print(f"   {feature}")

def show_usage_examples():
    """Show usage examples for the 285-page document"""
    
    examples = [
        {
            'title': 'Process a single large DOCX document',
            'command': 'python -m src.pipeline.large_document_processor your_285_page_document.docx --output-dir output/processed_document',
            'description': 'Complete processing with structure analysis, training data generation, and database import'
        },
        {
            'title': 'Generate AI training data only',
            'command': 'python -m src.training.ai_training_generator document_structure.json --target-count 15000 --format ollama',
            'description': 'Generate 15,000 training examples in Ollama format for fine-tuning'
        },
        {
            'title': 'Smart text chunking for memory efficiency',
            'command': 'python -m src.utils.intelligent_chunker large_document.txt --chunk-type semantic --max-size 1024',
            'description': 'Break document into semantic chunks while preserving meaning'
        },
        {
            'title': 'Advanced structure parsing',
            'command': 'python -m src.ocr.advanced_document_parser document.docx --export-json --create-training-data',
            'description': 'Parse document structure and export detailed analysis'
        },
        {
            'title': 'Batch process multiple documents',
            'command': 'python -m src.pipeline.large_document_processor documents_folder/ --batch --workers 4',
            'description': 'Process multiple documents in parallel'
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['title']}")
        print(f"   Command: {example['command']}")
        print(f"   Purpose: {example['description']}")
    
    print(f"\n💡 For your 285-page document specifically:")
    print(f"   1. First run the large document processor to get full analysis")
    print(f"   2. The system will automatically generate 10,000+ training examples")
    print(f"   3. Training data will be exported in multiple formats (JSONL, Ollama)")
    print(f"   4. Dictionary entries will be extracted and imported to database")
    print(f"   5. You'll get comprehensive reports and structure analysis")

def create_sample_config():
    """Create a sample configuration file"""
    config = {
        "processing_config": {
            "chunk_size_pages": 25,
            "parallel_workers": 4,
            "preserve_formatting": True,
            "generate_training_data": True,
            "target_training_examples": 15000,
            "min_confidence": 0.75,
            "output_formats": ["jsonl", "ollama", "huggingface"]
        },
        "chunking_config": {
            "max_chunk_size": 1024,
            "min_chunk_size": 100,
            "overlap_ratio": 0.15,
            "preserve_sentences": True,
            "preserve_paragraphs": True,
            "chunk_strategy": "semantic"
        },
        "training_config": {
            "include_contextual_definitions": True,
            "include_structural_learning": True,
            "include_pattern_recognition": True,
            "balance_dataset": True,
            "quality_filter": True
        },
        "output_config": {
            "save_raw_text": True,
            "save_structure_json": True,
            "save_training_data": True,
            "save_processing_report": True,
            "import_to_database": True
        }
    }
    
    config_file = Path("config/large_document_processing.json")
    config_file.parent.mkdir(exist_ok=True)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"⚙️ Sample configuration saved to: {config_file}")

def run_quick_demo():
    """Run a quick demonstration with a sample text"""
    
    print("\n🎬 Running quick demonstration...")
    
    # Create sample document content
    sample_text = """
    CHUUKESE DICTIONARY SAMPLE
    
    Chapter 1: Common Words
    
    ááfengen – very good, excellent
    This word is used to express high quality or satisfaction.
    Example: Ááfengen ei chon. (This food is very good.)
    
    ngang – fish
    A common word for fish in general.
    Example: Ngang me mwo kii? (What kind of fish is this?)
    
    ran – water  
    Essential word for water.
    Example: Ua ran non kich. (There is water in the well.)
    
    Chapter 2: Action Words
    
    kúún – to go
    Basic verb for movement.
    Example: Ua kúún ngang. (He/she went fishing.)
    
    chomong – to help, assist
    Important social concept.
    Example: Chomong nge? (Can you help?)
    """
    
    # Save sample to file
    sample_file = Path("output/sample_document.txt")
    with open(sample_file, 'w', encoding='utf-8') as f:
        f.write(sample_text)
    
    print(f"📄 Created sample document: {sample_file}")
    
    # Try to import and use our modules
    try:
        from src.utils.intelligent_chunker import IntelligentTextChunker, ChunkType
        from src.training.ai_training_generator import AITrainingDataGenerator
        
        # Demo chunking
        print("\n🔪 Demonstrating intelligent chunking...")
        chunker = IntelligentTextChunker(max_chunk_size=200, min_chunk_size=50)
        chunks = chunker.chunk_document(sample_text, ChunkType.SEMANTIC)
        
        print(f"✅ Created {len(chunks)} semantic chunks")
        for i, chunk in enumerate(chunks[:3]):  # Show first 3
            print(f"   Chunk {i+1}: {len(chunk.content)} chars - '{chunk.content[:50]}...'")
        
        # Demo training data generation (would need ParsedDocument object for full demo)
        print("\n🎯 Training data generation capabilities ready")
        generator = AITrainingDataGenerator()
        print(f"✅ Generator initialized with {len(generator.separator_patterns)} pattern types")
        
        print("\n🎉 Quick demo completed successfully!")
        
    except ImportError as e:
        print(f"⚠️ Could not run full demo due to missing imports: {e}")
        print("💡 This is normal if dependencies aren't fully installed yet")

if __name__ == "__main__":
    main()
    
    # Ask if user wants to see a quick demo
    demo_choice = input("\n🎬 Would you like to see a quick demonstration? (y/n): ")
    if demo_choice.lower() == 'y':
        run_quick_demo()
    
    # Create sample config
    config_choice = input("\n⚙️ Create sample configuration file? (y/n): ")
    if config_choice.lower() == 'y':
        create_sample_config()
    
    print("\n📋 Next steps:")
    print("   1. Place your 285-page document in the project folder")
    print("   2. Run: python -m src.pipeline.large_document_processor your_document.docx")
    print("   3. Wait for processing to complete (may take 10-30 minutes)")
    print("   4. Check the output directory for results")
    print("   5. Use the generated training data with your AI models")
    print("\n🔧 Need help? Check the documentation or run with --help flag")