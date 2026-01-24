---
name: llm-ollama-integration
description: Ollama LLM integration for Chuukese translation and text generation. Use when working with local LLM models, creating custom modelfiles, or implementing hybrid translation approaches combining Helsinki-NLP with LLMs.
---

# LLM Ollama Integration

## Overview

Integration of Ollama local LLMs for Chuukese translation assistance, dictionary enrichment, and hybrid translation approaches that combine rule-based methods with language models.

## Architecture

```text
chuuk/
├── src/
│   └── translation/
│       ├── helsinki_translator_v2.py  # Primary translator
│       ├── hybrid_translator.py       # Combines models
│       └── ollama_client.py           # Ollama API client
├── ollama-modelfile/
│   └── chuukese-translator.modelfile
├── Dockerfile.ollama
└── ollama-entrypoint.sh
```

## Ollama Client

### Basic Client Implementation

```python
"""Ollama client for LLM integration."""
import requests
import json
from typing import Optional, Generator
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Ollama connection configuration."""
    host: str = "http://localhost:11434"
    model: str = "llama3.2"
    timeout: int = 120


class OllamaClient:
    """Client for Ollama API."""
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self.base_url = self.config.host
    
    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/version",
                timeout=5
            )
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def list_models(self) -> list:
        """List available models."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            response.raise_for_status()
            return response.json().get('models', [])
        except requests.RequestException as e:
            print(f"Error listing models: {e}")
            return []
    
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        stream: bool = False
    ) -> str:
        """Generate text completion."""
        model = model or self.config.model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            if stream:
                return self._process_stream(response)
            else:
                return response.json().get('response', '')
        
        except requests.RequestException as e:
            print(f"Generation error: {e}")
            return ''
    
    def _process_stream(self, response) -> Generator[str, None, None]:
        """Process streaming response."""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if 'response' in data:
                    yield data['response']
    
    def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Chat completion with message history."""
        model = model or self.config.model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json().get('message', {}).get('content', '')
        
        except requests.RequestException as e:
            print(f"Chat error: {e}")
            return ''
    
    def embeddings(self, text: str, model: str = "nomic-embed-text") -> list:
        """Generate text embeddings."""
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            return response.json().get('embedding', [])
        except requests.RequestException as e:
            print(f"Embedding error: {e}")
            return []
```

## Chuukese Modelfile

### Custom Model for Translation

```modelfile
# chuukese-translator.modelfile
# Custom Chuukese translation model

FROM llama3.2

# Model parameters
PARAMETER temperature 0.3
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
PARAMETER stop "<|end|>"
PARAMETER stop "###"

# System prompt
SYSTEM """You are an expert translator specializing in Chuukese (Trukese), 
a Micronesian language spoken in Chuuk State, Federated States of Micronesia.

Your knowledge includes:
- Chuukese grammar and syntax
- Common Chuukese vocabulary and idioms
- Biblical and religious terminology in Chuukese
- Cultural context of translations

When translating:
1. Preserve the meaning and tone of the original text
2. Use appropriate Chuukese orthography
3. Handle proper nouns carefully (names, places)
4. Provide literal translations when exact equivalents don't exist
5. Note any cultural context when relevant

Format your responses as:
Translation: [translated text]
Notes: [any relevant notes about the translation]
"""

# Example translations for few-shot learning
TEMPLATE """{{ if .System }}<|system|>
{{ .System }}<|end|>
{{ end }}{{ if .Prompt }}<|user|>
{{ .Prompt }}<|end|>
<|assistant|>
{{ end }}{{ .Response }}<|end|>
"""
```

### Loading Custom Model

```bash
# Create model from modelfile
ollama create chuukese-translator -f ollama-modelfile/chuukese-translator.modelfile

# Test the model
ollama run chuukese-translator "Translate to English: Ewe Kot a kamour Adamu."

# List models to verify
ollama list
```

## Translation Prompts

### Chuukese to English

```python
def create_chk_to_en_prompt(text: str, context: str = "") -> str:
    """Create prompt for Chuukese to English translation."""
    prompt = f"""Translate the following Chuukese text to English.

Chuukese text: {text}
"""
    if context:
        prompt += f"\nContext: {context}"
    
    prompt += "\n\nProvide the English translation:"
    return prompt
```

### English to Chuukese

```python
def create_en_to_chk_prompt(text: str, context: str = "") -> str:
    """Create prompt for English to Chuukese translation."""
    prompt = f"""Translate the following English text to Chuukese (Trukese).

Use standard Chuukese orthography with these conventions:
- Long vowels doubled (aa, ee, ii, oo, uu)
- Use 'ch' for the affricate sound
- Use 'ng' for the velar nasal
- Use 'w' after back vowels

English text: {text}
"""
    if context:
        prompt += f"\nContext: {context}"
    
    prompt += "\n\nProvide the Chuukese translation:"
    return prompt
```

### Translation with Dictionary Context

```python
def create_dictionary_enhanced_prompt(
    text: str,
    direction: str,
    dictionary_entries: list
) -> str:
    """Create prompt with dictionary entries for context."""
    entries_text = "\n".join([
        f"- {e['chuukese_word']}: {e['english_definition']}"
        for e in dictionary_entries[:10]  # Limit context size
    ])
    
    if direction == 'chk_to_en':
        prompt = f"""Translate Chuukese to English.

Reference dictionary entries:
{entries_text}

Chuukese text: {text}

English translation:"""
    else:
        prompt = f"""Translate English to Chuukese.

Reference dictionary entries:
{entries_text}

English text: {text}

Chuukese translation:"""
    
    return prompt
```

## Hybrid Translator

### Combining Helsinki-NLP with LLM

```python
"""Hybrid translator combining multiple approaches."""
from typing import Optional, Dict, Any
from src.translation.helsinki_translator_v2 import HelsinkiChuukeseTranslator
from src.translation.ollama_client import OllamaClient
from src.database.dictionary_db import DictionaryDB


class HybridTranslator:
    """
    Hybrid translation using multiple strategies:
    1. Dictionary lookup for exact matches
    2. Helsinki-NLP for neural translation
    3. Ollama LLM for complex text and refinement
    """
    
    def __init__(self):
        self.db = DictionaryDB()
        self.helsinki = HelsinkiChuukeseTranslator()
        self.ollama = OllamaClient()
        self._helsinki_ready = False
        self._ollama_ready = False
    
    def setup(self):
        """Initialize translation models."""
        try:
            self.helsinki.setup_models()
            self._helsinki_ready = True
        except Exception as e:
            print(f"Helsinki setup error: {e}")
        
        self._ollama_ready = self.ollama.is_available()
    
    def translate(
        self,
        text: str,
        direction: str = 'chk_to_en',
        strategy: str = 'auto'
    ) -> Dict[str, Any]:
        """
        Translate text using specified or automatic strategy.
        
        Args:
            text: Text to translate
            direction: 'chk_to_en' or 'en_to_chk'
            strategy: 'dictionary', 'helsinki', 'llm', 'hybrid', or 'auto'
        
        Returns:
            Dict with translation and metadata
        """
        result = {
            'original': text,
            'direction': direction,
            'translations': [],
            'strategy_used': strategy
        }
        
        if strategy == 'auto':
            strategy = self._select_strategy(text, direction)
            result['strategy_used'] = f'auto:{strategy}'
        
        if strategy == 'dictionary':
            translation = self._dictionary_lookup(text, direction)
            if translation:
                result['translations'].append({
                    'text': translation,
                    'source': 'dictionary',
                    'confidence': 1.0
                })
        
        elif strategy == 'helsinki':
            if self._helsinki_ready:
                translation = self.helsinki.translate(text, direction)
                result['translations'].append({
                    'text': translation,
                    'source': 'helsinki-nlp',
                    'confidence': 0.7
                })
        
        elif strategy == 'llm':
            if self._ollama_ready:
                translation = self._llm_translate(text, direction)
                result['translations'].append({
                    'text': translation,
                    'source': 'ollama-llm',
                    'confidence': 0.6
                })
        
        elif strategy == 'hybrid':
            result['translations'] = self._hybrid_translate(text, direction)
        
        # Select best translation
        if result['translations']:
            result['best'] = max(
                result['translations'],
                key=lambda x: x['confidence']
            )['text']
        else:
            result['best'] = text  # Return original if no translation
            result['error'] = 'No translation available'
        
        return result
    
    def _select_strategy(self, text: str, direction: str) -> str:
        """Select best strategy based on input."""
        words = text.split()
        
        # Single word - try dictionary first
        if len(words) == 1:
            if self._dictionary_lookup(text, direction):
                return 'dictionary'
        
        # Short text - use Helsinki
        if len(words) <= 10 and self._helsinki_ready:
            return 'helsinki'
        
        # Longer text - use hybrid
        if self._ollama_ready and self._helsinki_ready:
            return 'hybrid'
        
        # Fallback
        return 'helsinki' if self._helsinki_ready else 'llm'
    
    def _dictionary_lookup(self, word: str, direction: str) -> Optional[str]:
        """Look up word in dictionary."""
        word_clean = word.strip().lower()
        
        if direction == 'chk_to_en':
            entry = self.db.get_entry(word_clean)
            if entry:
                return entry.get('english_definition')
        else:
            # Search English definitions
            entries = self.db.search_entries(
                word_clean,
                search_field='english_definition',
                limit=1
            )
            if entries:
                return entries[0].get('chuukese_word')
        
        return None
    
    def _llm_translate(self, text: str, direction: str) -> str:
        """Translate using Ollama LLM."""
        # Get relevant dictionary entries for context
        words = text.split()[:5]  # First 5 words
        context_entries = []
        for word in words:
            entries = self.db.search_entries(word, limit=2)
            context_entries.extend(entries)
        
        prompt = create_dictionary_enhanced_prompt(
            text, direction, context_entries
        )
        
        return self.ollama.generate(
            prompt,
            model='chuukese-translator',
            temperature=0.3
        )
    
    def _hybrid_translate(self, text: str, direction: str) -> list:
        """Combine multiple translation methods."""
        translations = []
        
        # Get Helsinki translation
        if self._helsinki_ready:
            helsinki_result = self.helsinki.translate(text, direction)
            translations.append({
                'text': helsinki_result,
                'source': 'helsinki-nlp',
                'confidence': 0.7
            })
        
        # Get LLM refinement
        if self._ollama_ready and translations:
            # Ask LLM to refine Helsinki translation
            refine_prompt = f"""Given this translation attempt:
Original ({direction}): {text}
Translation: {translations[0]['text']}

Please review and provide an improved translation if needed.
If the translation is good, return it unchanged.

Improved translation:"""
            
            refined = self.ollama.generate(
                refine_prompt,
                model='chuukese-translator',
                temperature=0.2
            )
            
            if refined and refined != translations[0]['text']:
                translations.append({
                    'text': refined,
                    'source': 'llm-refined',
                    'confidence': 0.8
                })
        
        return translations
```

## Dictionary Enhancement

### Generating Missing Definitions

```python
def generate_definition(
    client: OllamaClient,
    chuukese_word: str,
    existing_entries: list = None
) -> dict:
    """Generate English definition for Chuukese word."""
    context = ""
    if existing_entries:
        context = "\n".join([
            f"- {e['chuukese_word']}: {e['english_definition']}"
            for e in existing_entries[:5]
        ])
    
    prompt = f"""You are a Chuukese language expert. 
Provide an English definition for this Chuukese word.

{f"Related words for context:{chr(10)}{context}" if context else ""}

Word: {chuukese_word}

Provide:
1. Primary definition
2. Part of speech (noun, verb, adjective, etc.)
3. Example sentence in Chuukese with English translation (if possible)

Format as JSON:
{{"definition": "...", "part_of_speech": "...", "example": {{"chuukese": "...", "english": "..."}}}}
"""
    
    response = client.generate(
        prompt,
        model='chuukese-translator',
        temperature=0.3
    )
    
    # Parse JSON response
    try:
        import json
        # Find JSON in response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except json.JSONDecodeError:
        pass
    
    return {'definition': response, 'part_of_speech': 'unknown'}
```

### Generating Example Sentences

```python
def generate_example_sentence(
    client: OllamaClient,
    word: str,
    definition: str
) -> dict:
    """Generate example sentence using the word."""
    prompt = f"""Create a simple example sentence using this Chuukese word.

Word: {word}
Definition: {definition}

Provide a sentence in Chuukese and its English translation.
Keep the sentence simple and natural.

Format:
Chuukese: [sentence]
English: [translation]
"""
    
    response = client.generate(
        prompt,
        model='chuukese-translator',
        temperature=0.5
    )
    
    lines = response.strip().split('\n')
    result = {}
    
    for line in lines:
        if line.startswith('Chuukese:'):
            result['chuukese'] = line.replace('Chuukese:', '').strip()
        elif line.startswith('English:'):
            result['english'] = line.replace('English:', '').strip()
    
    return result
```

## Container Deployment

### Docker Compose with Ollama

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      ollama:
        condition: service_healthy
    networks:
      - chuuk-network

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
      - ./ollama-modelfile:/modelfiles:ro
    environment:
      - OLLAMA_HOST=0.0.0.0
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/version"]
      interval: 30s
      timeout: 10s
      retries: 5
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    networks:
      - chuuk-network

volumes:
  ollama-data:

networks:
  chuuk-network:
```

### Azure Container Apps with Ollama Sidecar

```bash
# Deploy Ollama as sidecar container
az containerapp create \
  --name chuuk-dictionary \
  --resource-group chuuk-rg \
  --environment chuuk-env \
  --image myregistry.azurecr.io/chuuk-dictionary:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 3 \
  --cpu 2 \
  --memory 4Gi

# Add Ollama sidecar
az containerapp update \
  --name chuuk-dictionary \
  --resource-group chuuk-rg \
  --container-name ollama \
  --image ollama/ollama:latest \
  --cpu 2 \
  --memory 8Gi
```

## API Endpoints

### Translation with LLM Option

```python
@app.route('/api/translate/hybrid', methods=['POST'])
def hybrid_translate():
    """Translate using hybrid approach."""
    data = request.get_json()
    
    text = data.get('text', '').strip()
    direction = data.get('direction', 'chk_to_en')
    strategy = data.get('strategy', 'auto')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    translator = get_hybrid_translator()
    result = translator.translate(text, direction, strategy)
    
    return jsonify(result)

@app.route('/api/llm/status')
def llm_status():
    """Check Ollama LLM status."""
    client = OllamaClient()
    
    return jsonify({
        'available': client.is_available(),
        'models': client.list_models() if client.is_available() else []
    })
```

## Best Practices

### Performance

1. **Cache model in memory**: Don't reload for each request
2. **Use streaming for long responses**: Better UX for users
3. **Set appropriate timeouts**: LLM can be slow
4. **Batch requests when possible**: Reduce overhead

### Quality

1. **Temperature tuning**: Lower (0.1-0.3) for translation
2. **Provide context**: Dictionary entries improve accuracy
3. **Validate output**: Check for hallucinations
4. **Fallback strategies**: Use Helsinki if LLM fails

### Security

1. **Rate limiting**: Prevent abuse
2. **Input sanitization**: Validate and limit input length
3. **Prompt injection protection**: Sanitize user input in prompts
4. **Resource limits**: CPU/memory constraints

## Dependencies

- Ollama server (local or containerized)
- `requests`: HTTP client for Ollama API
- Base model: `llama3.2` or similar
- Optional: GPU for faster inference
