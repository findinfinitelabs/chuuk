#!/usr/bin/env python3
"""
Advanced Translation Model Options for Chuukese Dictionary
===========================================================

This module provides multiple translation model backends optimized for 
low-resource languages like Chuukese, with performance comparisons and 
recommendations.
"""

import os
import json
import time
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

# Optional imports - install as needed
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from azure.ai.translation.text import TextTranslationClient, TranslatorCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelType(Enum):
    OLLAMA_LLAMA = "ollama_llama"
    HELSINKI_OPUS = "helsinki_opus" 
    MICROSOFT_CUSTOM = "microsoft_custom"
    MBART_MULTILINGUAL = "mbart_multilingual"
    NLLB_META = "nllb_meta"

@dataclass
class ModelConfig:
    name: str
    type: ModelType
    description: str
    best_for: List[str]
    requirements: List[str]
    local: bool
    size_mb: int
    speed_score: int  # 1-10, 10=fastest
    accuracy_score: int  # 1-10, 10=most accurate for low-resource
    setup_difficulty: int  # 1-10, 10=hardest

class TranslationModelManager:
    """
    Manages multiple translation model backends for optimal Chuukese translation
    """
    
    def __init__(self):
        self.models = self._initialize_model_configs()
        self.active_model = None
        
    def _initialize_model_configs(self) -> Dict[str, ModelConfig]:
        """Initialize all available model configurations"""
        return {
            "ollama_llama": ModelConfig(
                name="Llama 3.2 (via Ollama)",
                type=ModelType.OLLAMA_LLAMA,
                description="General-purpose LLM, good for context but not specialized for translation",
                best_for=["Conversational context", "General language understanding"],
                requirements=["ollama", "2GB RAM"],
                local=True,
                size_mb=2000,
                speed_score=7,
                accuracy_score=6,
                setup_difficulty=3
            ),
            
            "helsinki_opus": ModelConfig(
                name="Helsinki-NLP OPUS-MT (🏆 RECOMMENDED)",
                type=ModelType.HELSINKI_OPUS,
                description="Specialized translation models trained on OPUS corpus, excellent for multilingual pairs",
                best_for=["Direct translation", "Low-resource languages", "Academic accuracy"],
                requirements=["transformers", "torch", "4GB RAM"],
                local=True,
                size_mb=1200,
                speed_score=8,
                accuracy_score=9,
                setup_difficulty=4
            ),
            
            "microsoft_custom": ModelConfig(
                name="Azure Custom Translator",
                type=ModelType.MICROSOFT_CUSTOM,
                description="Enterprise-grade custom translation service, can train on your specific data",
                best_for=["Production deployment", "Custom domain training", "High accuracy"],
                requirements=["Azure subscription", "Custom Translator service"],
                local=False,
                size_mb=0,  # Cloud service
                speed_score=6,
                accuracy_score=10,
                setup_difficulty=7
            ),
            
            "nllb_meta": ModelConfig(
                name="Meta NLLB-200 (🚀 MULTILINGUAL CHAMPION)",
                type=ModelType.NLLB_META,
                description="Supports 200+ languages including many low-resource ones",
                best_for=["Wide language support", "Low-resource languages", "Research quality"],
                requirements=["transformers", "torch", "8GB RAM"],
                local=True,
                size_mb=4800,
                speed_score=5,
                accuracy_score=9,
                setup_difficulty=5
            ),
            
            "mbart_multilingual": ModelConfig(
                name="Facebook mBART-50",
                type=ModelType.MBART_MULTILINGUAL,
                description="Multilingual denoising pre-trained model, good for fine-tuning",
                best_for=["Fine-tuning on custom data", "Research", "Multilingual tasks"],
                requirements=["transformers", "torch", "6GB RAM"],
                local=True,
                size_mb=2400,
                speed_score=6,
                accuracy_score=8,
                setup_difficulty=6
            )
        }
    
    def get_recommendation_for_chuukese(self) -> Tuple[str, str]:
        """
        Get the best model recommendation specifically for Chuukese translation
        """
        # Priority ranking for Chuukese (low-resource Oceanic language)
        recommendations = [
            ("helsinki_opus", "Best balance of accuracy, speed, and local deployment"),
            ("nllb_meta", "If you have sufficient RAM and want maximum language support"),
            ("microsoft_custom", "If you need production-grade results and don't mind cloud dependency"),
            ("ollama_llama", "If you prefer the current setup but expect lower translation accuracy")
        ]
        
        return recommendations[0]
    
    def check_system_requirements(self) -> Dict[str, bool]:
        """Check which models can run on current system"""
        status = {}
        
        # Check available libraries
        status['ollama'] = OLLAMA_AVAILABLE
        status['transformers'] = TRANSFORMERS_AVAILABLE  
        status['azure'] = AZURE_AVAILABLE
        
        # Check system resources
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024**3)
            status['sufficient_ram'] = ram_gb >= 4
        except ImportError:
            status['sufficient_ram'] = True  # Assume sufficient if can't check
            
        return status
    
    def install_helsinki_opus(self) -> bool:
        """
        Install and set up Helsinki-NLP OPUS model for multilingual translation
        """
        if not TRANSFORMERS_AVAILABLE:
            logger.error("Transformers library required. Install with: pip install transformers torch")
            return False
            
        try:
            logger.info("🚀 Setting up Helsinki-NLP OPUS translation model...")
            
            # This model supports many languages including some Oceanic ones
            model_name = "Helsinki-NLP/opus-mt-mul-en"
            
            logger.info(f"📥 Downloading {model_name}...")
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            
            logger.info("✅ Helsinki-NLP OPUS model ready!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to install Helsinki model: {e}")
            return False
    
    def install_nllb_model(self) -> bool:
        """
        Install Meta's NLLB-200 model for extensive multilingual support
        """
        if not TRANSFORMERS_AVAILABLE:
            logger.error("Transformers library required. Install with: pip install transformers torch")
            return False
            
        try:
            logger.info("🚀 Setting up Meta NLLB-200 translation model...")
            
            # NLLB supports 200+ languages including many Pacific languages
            model_name = "facebook/nllb-200-distilled-600M"
            
            logger.info(f"📥 Downloading {model_name} (this may take a while)...")
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            
            logger.info("✅ NLLB-200 model ready!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to install NLLB model: {e}")
            return False
    
    def compare_models(self) -> str:
        """Generate a comparison report of all models"""
        report = """
🏆 TRANSLATION MODEL COMPARISON FOR CHUUKESE
==============================================

📊 PERFORMANCE MATRIX:
Model                    | Local | Size  | Speed | Accuracy | Difficulty
Helsinki-NLP OPUS       | ✅    | 1.2GB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐    | ⭐⭐⭐⭐
Meta NLLB-200          | ✅    | 4.8GB | ⭐⭐⭐  | ⭐⭐⭐⭐⭐    | ⭐⭐⭐⭐⭐
Azure Custom Translator| ❌    | Cloud | ⭐⭐⭐  | ⭐⭐⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐⭐⭐
Llama 3.2 (Current)    | ✅    | 2.0GB | ⭐⭐⭐⭐ | ⭐⭐⭐     | ⭐⭐⭐
Facebook mBART-50      | ✅    | 2.4GB | ⭐⭐⭐  | ⭐⭐⭐⭐     | ⭐⭐⭐⭐⭐⭐

🎯 RECOMMENDATION FOR CHUUKESE:
1. 🥇 Helsinki-NLP OPUS: Best overall choice
   - Specifically designed for translation
   - Good support for low-resource languages  
   - Moderate resource requirements
   - Local and private

2. 🥈 Meta NLLB-200: If you have enough RAM
   - Supports 200+ languages including Pacific languages
   - Excellent for multilingual contexts
   - Requires more resources

3. 🥉 Current Ollama Setup: Keep as fallback
   - Good for general language tasks
   - Less accurate for pure translation
   - Easy to use

💡 NEXT STEPS:
Run this script to switch to the recommended model:
python translation_models.py --setup helsinki

Or for maximum language support:
python translation_models.py --setup nllb
"""
        return report

def main():
    """Command line interface for model management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Chuukese Translation Model Manager")
    parser.add_argument("--setup", choices=["helsinki", "nllb", "current"], 
                       help="Set up specific translation model")
    parser.add_argument("--compare", action="store_true", 
                       help="Compare all available models")
    parser.add_argument("--check", action="store_true",
                       help="Check system requirements")
    
    args = parser.parse_args()
    
    manager = TranslationModelManager()
    
    if args.compare:
        print(manager.compare_models())
        
    elif args.check:
        status = manager.check_system_requirements()
        print("\n🔍 SYSTEM REQUIREMENTS CHECK:")
        print("=" * 40)
        for requirement, available in status.items():
            status_icon = "✅" if available else "❌"
            print(f"{status_icon} {requirement}: {'Available' if available else 'Missing'}")
        
        # Get recommendation
        recommended_model, reason = manager.get_recommendation_for_chuukese()
        print(f"\n🎯 RECOMMENDED: {manager.models[recommended_model].name}")
        print(f"💡 REASON: {reason}")
        
    elif args.setup == "helsinki":
        print("🚀 Setting up Helsinki-NLP OPUS model...")
        if manager.install_helsinki_opus():
            print("✅ Helsinki-NLP model installed successfully!")
            print("🔄 Update your llm_trainer.py to use this model for better results.")
        else:
            print("❌ Installation failed. Check requirements.")
            
    elif args.setup == "nllb":
        print("🚀 Setting up Meta NLLB-200 model...")
        if manager.install_nllb_model():
            print("✅ NLLB-200 model installed successfully!")
            print("🔄 This model has excellent support for Pacific languages.")
        else:
            print("❌ Installation failed. Check requirements.")
            
    else:
        print(manager.compare_models())

if __name__ == "__main__":
    main()