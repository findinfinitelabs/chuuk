---
name: helsinki-nlp-model-training
description: Fine-tune Helsinki-NLP OPUS-MT models for Chuukese translation with custom training data, evaluation, and deployment. Use when training, evaluating, fine-tuning, or deploying translation models for Chuukese-English translation.
---

# Helsinki-NLP Model Training

## Overview

Train and fine-tune Helsinki-NLP OPUS-MT models for Chuukese-English translation. These models are specifically designed for translation tasks and perform better than general LLMs for low-resource languages like Chuukese.

**Base Models**:

- `Helsinki-NLP/opus-mt-mul-en` (Multilingual → English)
- `Helsinki-NLP/opus-mt-en-mul` (English → Multilingual)

## Capabilities

- **Fine-tuning**: Adapt base models to Chuukese-specific data
- **Bidirectional Training**: Support for both Chuukese→English and English→Chuukese
- **Training Data Preparation**: Format dictionary and parallel corpus data
- **Model Evaluation**: BLEU, chrF scoring on test sets
- **Local Deployment**: Run models locally without API calls
- **GPU/CPU Support**: Automatic device detection and optimization

## Model Architecture

```text
Helsinki-NLP OPUS-MT Architecture:
┌─────────────────────────────────────────────────┐
│  MarianMT (Marian Neural Machine Translation)   │
├─────────────────────────────────────────────────┤
│  Encoder: 6 Transformer layers                  │
│  Decoder: 6 Transformer layers                  │
│  Attention heads: 8                             │
│  Hidden size: 512                               │
│  Vocabulary: SentencePiece tokenizer            │
└─────────────────────────────────────────────────┘
```

## Directory Structure

```text
models/
├── helsinki-chuukese_chuukese_to_english/
│   ├── finetuned/
│   │   ├── config.json
│   │   ├── pytorch_model.bin
│   │   ├── tokenizer_config.json
│   │   ├── source.spm
│   │   └── target.spm
│   └── training_logs/
├── helsinki-chuukese_english_to_chuukese/
│   ├── finetuned/
│   └── training_logs/
└── test-helsinki_chuukese_to_english/
```

## Training Data Preparation

### 1. Data Format

```python
# Training data structure
training_pairs = [
    {"source": "chomong", "target": "to help, assist"},
    {"source": "Kopwe pwan chomong", "target": "We will help"},
    {"source": "ngang", "target": "fish"},
]

# Export to TSV format
def export_training_data(pairs, output_path, direction="chk_to_en"):
    """Export training pairs to TSV format for transformers."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for pair in pairs:
            if direction == "chk_to_en":
                f.write(f"{pair['source']}\t{pair['target']}\n")
            else:
                f.write(f"{pair['target']}\t{pair['source']}\n")
```

### 2. Data Sources

```python
# Combine multiple data sources
from src.database.dictionary_db import DictionaryDB

def prepare_training_data():
    """Prepare comprehensive training dataset."""
    db = DictionaryDB()
    
    training_pairs = []
    
    # 1. Dictionary entries
    entries = db.dictionary.find({'is_base_word': True})
    for entry in entries:
        training_pairs.append({
            'source': entry['chuukese_word'],
            'target': entry['english_definition'],
            'confidence': 0.9
        })
    
    # 2. Phrases
    phrases = db.phrases.find({'confidence_score': {'$gte': 0.7}})
    for phrase in phrases:
        training_pairs.append({
            'source': phrase['chuukese_phrase'],
            'target': phrase['english_translation'],
            'confidence': phrase.get('confidence_score', 0.8)
        })
    
    # 3. Bible parallel verses (highest quality)
    from src.utils.nwt_epub_parser import NWTEpubParser
    # ... extract parallel verses
    
    return training_pairs
```

### 3. Data Splitting

```python
from sklearn.model_selection import train_test_split

def split_training_data(pairs, test_size=0.1, val_size=0.1):
    """Split data into train/val/test sets."""
    train, test = train_test_split(pairs, test_size=test_size, random_state=42)
    train, val = train_test_split(train, test_size=val_size/(1-test_size), random_state=42)
    
    return {
        'train': train,
        'val': val,
        'test': test
    }
```

## Training Implementation

### HelsinkiChuukeseTranslator Class

```python
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Trainer,
    TrainingArguments,
    DataCollatorForSeq2Seq
)
from datasets import Dataset

class HelsinkiChuukeseTranslator:
    """Helsinki-NLP based Chuukese translator with fine-tuning support."""
    
    def __init__(self,
                 base_model: str = "Helsinki-NLP/opus-mt-mul-en",
                 reverse_model: str = "Helsinki-NLP/opus-mt-en-mul"):
        self.base_model = base_model
        self.reverse_model = reverse_model
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Local fine-tuned model paths
        self.local_chk_to_en = "models/helsinki-chuukese_chuukese_to_english/finetuned"
        self.local_en_to_chk = "models/helsinki-chuukese_english_to_chuukese/finetuned"
        
        self.tokenizer = None
        self.model = None
        
    def setup_models(self, direction: str = "chk_to_en") -> bool:
        """Load models, preferring fine-tuned versions."""
        try:
            if direction == "chk_to_en":
                model_path = self.local_chk_to_en if os.path.exists(self.local_chk_to_en) else self.base_model
            else:
                model_path = self.local_en_to_chk if os.path.exists(self.local_en_to_chk) else self.reverse_model
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(self.device)
            
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False
    
    def translate(self, text: str, direction: str = "chk_to_en") -> str:
        """Translate text using loaded model."""
        if self.model is None:
            self.setup_models(direction)
        
        inputs = self.tokenizer(text, return_tensors="pt", padding=True).to(self.device)
        
        outputs = self.model.generate(
            **inputs,
            max_length=256,
            num_beams=5,
            early_stopping=True
        )
        
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
```

### Fine-Tuning Script

```python
def fine_tune_model(
    training_data: list,
    direction: str = "chk_to_en",
    epochs: int = 10,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    output_dir: str = None
):
    """
    Fine-tune Helsinki-NLP model on Chuukese data.
    
    Args:
        training_data: List of {'source': str, 'target': str} pairs
        direction: 'chk_to_en' or 'en_to_chk'
        epochs: Number of training epochs
        batch_size: Training batch size
        learning_rate: Learning rate
        output_dir: Directory to save fine-tuned model
    """
    # Select base model
    if direction == "chk_to_en":
        base_model = "Helsinki-NLP/opus-mt-mul-en"
        output_dir = output_dir or "models/helsinki-chuukese_chuukese_to_english/finetuned"
    else:
        base_model = "Helsinki-NLP/opus-mt-en-mul"
        output_dir = output_dir or "models/helsinki-chuukese_english_to_chuukese/finetuned"
    
    # Load tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSeq2SeqLM.from_pretrained(base_model)
    
    # Prepare dataset
    def preprocess_function(examples):
        inputs = examples['source']
        targets = examples['target']
        
        model_inputs = tokenizer(inputs, max_length=128, truncation=True, padding='max_length')
        
        with tokenizer.as_target_tokenizer():
            labels = tokenizer(targets, max_length=128, truncation=True, padding='max_length')
        
        model_inputs['labels'] = labels['input_ids']
        return model_inputs
    
    # Create HuggingFace Dataset
    dataset = Dataset.from_dict({
        'source': [p['source'] for p in training_data],
        'target': [p['target'] for p in training_data]
    })
    
    tokenized_dataset = dataset.map(preprocess_function, batched=True)
    
    # Split into train/val
    split = tokenized_dataset.train_test_split(test_size=0.1)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        logging_dir=f"{output_dir}/logs",
        logging_steps=100,
        fp16=torch.cuda.is_available(),  # Use mixed precision on GPU
        gradient_accumulation_steps=4,
        warmup_ratio=0.1,
    )
    
    # Data collator
    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=split['train'],
        eval_dataset=split['test'],
        data_collator=data_collator,
    )
    
    # Train
    trainer.train()
    
    # Save model and tokenizer
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"✅ Model saved to {output_dir}")
    
    return trainer
```

## Model Evaluation

```python
import sacrebleu

def evaluate_model(translator, test_pairs: list, direction: str = "chk_to_en"):
    """Evaluate translation model on test set."""
    predictions = []
    references = []
    
    for pair in test_pairs:
        source = pair['source']
        target = pair['target']
        
        prediction = translator.translate(source, direction)
        predictions.append(prediction)
        references.append([target])  # sacrebleu expects list of references
    
    # Calculate BLEU
    bleu = sacrebleu.corpus_bleu(predictions, references)
    
    # Calculate chrF (preferred for low-resource languages)
    chrf = sacrebleu.corpus_chrf(predictions, references)
    
    return {
        'bleu': bleu.score,
        'chrf': chrf.score,
        'num_samples': len(test_pairs),
        'sample_predictions': list(zip(
            [p['source'] for p in test_pairs[:5]],
            [p['target'] for p in test_pairs[:5]],
            predictions[:5]
        ))
    }
```

## GPU vs CPU Training

```python
def get_device_config():
    """Get optimal device configuration for training."""
    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        
        # Adjust batch size based on GPU memory
        if gpu_memory >= 16:
            batch_size = 32
        elif gpu_memory >= 8:
            batch_size = 16
        else:
            batch_size = 8
        
        return {
            'device': device,
            'gpu_name': gpu_name,
            'gpu_memory_gb': gpu_memory,
            'batch_size': batch_size,
            'fp16': True,
            'gradient_accumulation': 2
        }
    else:
        return {
            'device': 'cpu',
            'batch_size': 4,
            'fp16': False,
            'gradient_accumulation': 8
        }
```

## Usage Examples

### Basic Training

```python
# Prepare data
training_data = prepare_training_data()
splits = split_training_data(training_data)

# Train Chuukese → English model
fine_tune_model(
    training_data=splits['train'],
    direction="chk_to_en",
    epochs=10
)

# Train English → Chuukese model
fine_tune_model(
    training_data=splits['train'],
    direction="en_to_chk",
    epochs=10
)
```

### Model Comparison

```python
# Compare base vs fine-tuned
translator = HelsinkiChuukeseTranslator()

# Test with base model
translator.setup_models(use_finetuned=False)
base_results = evaluate_model(translator, splits['test'])

# Test with fine-tuned model
translator.setup_models(use_finetuned=True)
finetuned_results = evaluate_model(translator, splits['test'])

print(f"Base BLEU: {base_results['bleu']:.2f}")
print(f"Fine-tuned BLEU: {finetuned_results['bleu']:.2f}")
print(f"Improvement: {finetuned_results['bleu'] - base_results['bleu']:.2f}")
```

## Best Practices

### Training

1. **Use high-quality data**: Bible verses and validated dictionary entries
2. **Balance dataset**: Mix words, phrases, and sentences
3. **Early stopping**: Monitor validation loss to prevent overfitting
4. **Mixed precision**: Use FP16 on GPU for faster training
5. **Gradient accumulation**: Use for larger effective batch sizes on limited memory

### Evaluation

1. **Use chrF for low-resource languages**: More stable than BLEU
2. **Human evaluation**: Periodic review by native speakers
3. **Back-translation**: Verify round-trip consistency
4. **Cultural validation**: Ensure cultural concepts are preserved

### Deployment

1. **Quantization**: Use 8-bit quantization for faster inference
2. **Caching**: Cache tokenizer and model loading
3. **Batch processing**: Process multiple translations together
4. **Fallback**: Keep base model as fallback if fine-tuned fails

## Dependencies

- `torch>=2.0.0`: PyTorch
- `transformers>=4.57.0`: Hugging Face Transformers
- `datasets>=2.0.0`: Hugging Face Datasets
- `sentencepiece>=0.1.99`: Tokenization
- `sacrebleu>=2.0.0`: Evaluation metrics
- `accelerate>=0.20.0`: Training acceleration
