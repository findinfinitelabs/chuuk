from transformers import pipeline

# Test the base Helsinki model for English to multilingual
print('Testing base Helsinki-NLP opus-mt-en-mul model...')
model = pipeline('translation', model='Helsinki-NLP/opus-mt-en-mul')

test_text = 'hello'
print(f'Testing: {test_text}')

# Check what the model produces without specifying target language
result = model(test_text)
print(f'Default result: {result[0]["translation_text"]}')

# The model might need a target language prefix
# Let's try some common language codes
test_langs = ['es', 'fr', 'de', 'id', 'tl']  # Spanish, French, German, Indonesian, Tagalog

for lang in test_langs:
    try:
        result = model(f'>>{lang}<< {test_text}')
        translation = result[0]['translation_text']
        print(f'{lang}: {translation}')
    except Exception as e:
        print(f'{lang}: Error - {e}')

# Test the English->Chuukese model with words from the training data
print('\n--- Testing English→Chuukese model with training data words ---')
try:
    finetuned_model = pipeline('translation', model='models/helsinki-chuukese_english_to_chuukese/finetuned')

    test_words = [
        'appease',
        'cool down',
        'reconcile',
        'thin',
        'dollar',
        'fly'
    ]

    print('Testing English→Chuukese model with training data words:')
    for word in test_words:
        try:
            result = finetuned_model(word, max_length=128, num_beams=4, do_sample=False, early_stopping=True)
            translation = result[0]['translation_text']
            print(f'EN: "{word}" -> CHK: "{translation}"')
        except Exception as e:
            print(f'EN: "{word}" -> Error: {e}')
except Exception as e:
    print(f'Model loading error: {e}')