#!/usr/bin/env python3
import json
import subprocess

# Load our generated training data
with open('output/processed_document/training_data/training_dictionary_pairs_ollama.jsonl', 'r', encoding='utf-8') as f:
    training_data = [json.loads(line) for line in f]

print(f'📚 Loaded {len(training_data)} training examples')

# Create examples from our data
examples = []
for i, example in enumerate(training_data[:20]):
    if 'input' in example and 'output' in example:
        examples.append(f'Human: {example["input"]}\nAssistant: {example["output"]}')
    elif 'text' in example:
        # Handle completion format
        text = example['text']
        if '### Response:' in text:
            parts = text.split('### Response:')
            prompt = parts[0].replace('### Instruction:', '').strip()
            response = parts[1].strip()
            examples.append(f'Human: {prompt}\nAssistant: {response}')

examples_text = '\n\n'.join(examples[:10])

modelfile_content = f'''FROM llama3.2:3b

PARAMETER temperature 0.2
PARAMETER top_p 0.8
PARAMETER repeat_penalty 1.1

SYSTEM """You are a specialized Chuukese-English translator. You translate between Chuukese and English languages accurately based on dictionary data.

Key capabilities:
- Translate Chuukese words/phrases to English
- Translate English words/phrases to Chuukese  
- Provide definitions and explanations
- Handle Chuukese accent characters properly

Example translations:
{examples_text}

Always respond with just the translation or definition, be concise and accurate."""
'''

# Write the Modelfile
with open('/tmp/Modelfile.chuukese', 'w', encoding='utf-8') as f:
    f.write(modelfile_content)

print('✅ Created improved Modelfile')

# Remove old model and create new one
try:
    subprocess.run(["ollama", "rm", "chuukese-translator"], capture_output=True)
    print("🗑️ Removed old model")
except:
    pass

# Create new model
result = subprocess.run([
    "ollama", "create", "chuukese-translator", "-f", "/tmp/Modelfile.chuukese"
], capture_output=True, text=True, timeout=300)

if result.returncode == 0:
    print("✅ Successfully created improved model: chuukese-translator")
else:
    print(f"❌ Failed to create model: {result.stderr}")