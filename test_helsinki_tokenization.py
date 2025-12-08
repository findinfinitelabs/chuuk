#!/usr/bin/env python3

from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator

def test_helsinki_tokenization():
    print('🚀 Testing Helsinki tokenization...')
    translator = HelsinkiChuukeseTranslator()
    
    print('📥 Setting up models...')
    setup_success = translator.setup_models()
    
    if not setup_success:
        print('❌ Model setup failed')
        return False
    
    # Load and prepare small dataset
    translator.load_dictionary_data()
    translator.training_data = translator.training_data[:5]  # Very small subset
    
    datasets = translator.prepare_training_dataset()
    train_dataset = datasets['chuukese_to_english']
    
    print('Testing tokenization function...')
    tokenizer = translator.tokenizer
    
    # Get sample data
    sample = train_dataset[0]
    input_text = sample['input_text']
    target_text = sample['target_text'].replace('\t', ' ').strip()  # Clean target
    
    print(f'Input: "{input_text}"')
    print(f'Target: "{target_text}"')
    
    # Test tokenization
    try:
        # Test batch tokenization like in training
        batch_inputs = [input_text]
        batch_targets = [target_text]
        
        input_tokens = tokenizer(
            batch_inputs,
            max_length=128,
            truncation=True,
            padding='max_length',
            return_tensors=None
        )
        print('✅ Input tokenization successful')
        
        target_tokens = tokenizer(
            text_target=batch_targets,
            max_length=128,
            truncation=True,
            padding='max_length',
            return_tensors=None
        )
        print('✅ Target tokenization successful')
        print(f'Input tokens shape: {len(input_tokens["input_ids"])}')
        print(f'Target tokens shape: {len(target_tokens["input_ids"])}')
        
        return True
        
    except Exception as e:
        print(f'❌ Tokenization failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_helsinki_tokenization()