#!/usr/bin/env python3

from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
import torch

def debug_tokenization():
    print('🔍 Debugging tokenization issue...')
    translator = HelsinkiChuukeseTranslator()
    
    # Setup models
    translator.setup_models()
    translator.load_dictionary_data()
    translator.training_data = translator.training_data[:5]  # Very small sample
    
    # Prepare dataset
    datasets = translator.prepare_training_dataset()
    train_dataset = datasets['chuukese_to_english']
    
    print('Raw dataset:')
    for i in range(len(train_dataset)):
        example = train_dataset[i]
        print(f'{i}: Input: "{example["input_text"][:50]}..." Target: "{example["target_text"][:50]}..."')
    
    # Test the tokenization function manually
    tokenizer = translator.tokenizer
    
    def tokenize_function(examples):
        print(f'\\nTokenizing batch with {len(examples["input_text"])} examples')
        
        inputs = examples["input_text"] 
        targets = examples["target_text"]
        
        print('Input types:', [type(x) for x in inputs])
        print('Target types:', [type(x) for x in targets])
        
        # Tokenize inputs
        try:
            model_inputs = tokenizer(
                inputs,
                max_length=128,
                truncation=True,
                padding="max_length",
                return_tensors=None
            )
            print('✅ Input tokenization successful')
        except Exception as e:
            print(f'❌ Input tokenization failed: {e}')
            print('Input data:', inputs)
            return None
        
        # Tokenize targets 
        try:
            labels = tokenizer(
                text_target=targets,
                max_length=128,
                truncation=True,
                padding="max_length",
                return_tensors=None
            )
            print('✅ Target tokenization successful')
        except Exception as e:
            print(f'❌ Target tokenization failed: {e}')
            print('Target data:', targets)
            return None
        
        # Use the tokenized targets as labels
        model_inputs["labels"] = labels["input_ids"]
        
        print('Final output keys:', list(model_inputs.keys()))
        print('Shapes:', {k: len(v) if isinstance(v, list) else 'unknown' for k, v in model_inputs.items()})
        
        return model_inputs
    
    # Test with the actual dataset
    try:
        print('\\n🧪 Testing tokenization with map function...')
        tokenized_dataset = train_dataset.map(tokenize_function, batched=True, batch_size=2)
        print('✅ Map function completed successfully!')
    except Exception as e:
        print(f'❌ Map function failed: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_tokenization()