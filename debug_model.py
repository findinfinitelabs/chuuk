from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os

# Test the tokenizer and model directly
model_path = 'models/helsinki-chuukese_english_to_chuukese/finetuned'
print(f'Loading tokenizer and model from: {model_path}')

try:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path)

    print('Tokenizer and model loaded successfully')

    # Test tokenization
    test_text = 'hello'
    print(f'Tokenizing: {test_text}')
    inputs = tokenizer(test_text, return_tensors='pt')
    print(f'Input IDs: {inputs["input_ids"]}')
    print(f'Attention mask: {inputs["attention_mask"]}')

    # Test generation
    print('Generating translation...')
    outputs = model.generate(**inputs, max_length=128)
    print(f'Output IDs: {outputs}')

    # Decode
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f'Decoded result: {repr(decoded)}')

    # Also test the working model
    print('\n--- Testing working Chuukese→English model ---')
    working_path = 'models/helsinki-chuukese_chuukese_to_english/finetuned'
    working_tokenizer = AutoTokenizer.from_pretrained(working_path)
    working_model = AutoModelForSeq2SeqLM.from_pretrained(working_path)

    print('Working model loaded')
    working_inputs = working_tokenizer('mwomw', return_tensors='pt')
    working_outputs = working_model.generate(**working_inputs, max_length=128)
    working_decoded = working_tokenizer.decode(working_outputs[0], skip_special_tokens=True)
    print(f'Chuukese "mwomw" → English: {repr(working_decoded)}')

except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()