---
name: llm-ollama-integration
description: How the Chuuk Dictionary integrates Ollama for the Chuukese-translator custom LLM — `ChuukeseLLMTrainer`, the `chuukese-translator` modelfile, container/runtime wiring, and the translate endpoint integration. Use when changing LLM behavior, updating the modelfile, debugging Ollama connectivity, or modifying the LLM training pipeline.
---

# Ollama LLM Integration

We run Ollama as a sidecar container app, expose `llama3.2:3b`, and build a custom `chuukese-translator` model on top of it using dictionary data. The Flask backend talks to it over HTTP.

## Components

| Piece | Path |
|---|---|
| Python wrapper | [`src/translation/llm_trainer.py`](../../../src/translation/llm_trainer.py#L14) |
| Hybrid orchestrator (programmatic only) | [`src/translation/hybrid_translator.py`](../../../src/translation/hybrid_translator.py#L15) |
| Modelfile | [`ollama-modelfile/chuukese-translator.modelfile`](../../../ollama-modelfile/chuukese-translator.modelfile) |
| Container image | [`Dockerfile.ollama`](../../../Dockerfile.ollama) |
| Container entrypoint | [`ollama-entrypoint.sh`](../../../ollama-entrypoint.sh) |

There is **no** `src/translation/ollama_client.py` — older docs mention it; ignore them.

## Wrapper API

```python
from src.translation.llm_trainer import ChuukeseLLMTrainer

llm = ChuukeseLLMTrainer()           # uses OLLAMA_BASE_URL or http://localhost:11434
llm.check_ollama_installation()      # GET /api/version, returns bool
llm.pull_base_model()                # ollama pull llama3.2:3b
training = llm.extract_training_data()  # builds prompts from DictionaryDB
llm.create_modelfile(training)       # writes Modelfile and runs `ollama create`
llm.translate_text(text, direction=...) # direction: 'auto' | 'chk_to_en' | 'en_to_chk'
```

Key constants on the class: `model_name = "llama3.2:3b"`, `custom_model_name = "chuukese-translator"`. Don't rename either without also updating the modelfile, the container entrypoint, and the deploy script.

`translate_text` builds direction-specific prompts that constrain output to the translation only (with stop sequences `["\n\n", "Chuukese:", "English:", ...]`) and uses low temperature (`0.1`). When you tweak prompt format here, also re-evaluate the modelfile examples — they reinforce the same shape.

## Modelfile

[`ollama-modelfile/chuukese-translator.modelfile`](../../../ollama-modelfile/chuukese-translator.modelfile) is a Llama-3 templated modelfile pinned to a specific blob SHA. The `SYSTEM` block contains a few-shot training set of Chuukese ↔ English Q&A pairs. To regenerate:

```bash
# 1. Pull a fresh base
ollama pull llama3.2:3b
# 2. Run the wrapper to generate a new Modelfile from current DB content
python -c "from src.translation.llm_trainer import ChuukeseLLMTrainer as L; t = L(); t.create_modelfile(t.extract_training_data())"
# 3. Build the custom model
ollama create chuukese-translator -f Modelfile
```

The committed modelfile's `FROM` line points at a local blob path — that's expected; rebuild on each environment.

## Container wiring

[`Dockerfile.ollama`](../../../Dockerfile.ollama) is a `python:3.11-slim` image that installs Ollama via the official installer. A build arg `PREPULL_LLM=true` warms the image with `llama3.2:3b` baked in (see [Dockerfile.ollama](../../../Dockerfile.ollama#L17)). Default is `false` — model is pulled at first start.

The entrypoint [`ollama-entrypoint.sh`](../../../ollama-entrypoint.sh) starts `ollama serve` and pulls/creates the custom model if missing.

In Azure Container Apps, the Ollama app is deployed as a **separate container app** (`chuuk-ollama`) with internal ingress, min=max=1 replica (see [`deploy-chuuk.sh`](../../../deploy-chuuk.sh#L220)). The main app reaches it via the private FQDN passed in as `OLLAMA_BASE_URL` ([deploy-chuuk.sh](../../../deploy-chuuk.sh#L227)).

## Backend integration

The translate endpoint at [app.py](../../../app.py#L1538) calls `ChuukeseLLMTrainer.translate_text(...)` alongside Helsinki and Google. There is **no** `/api/translate/hybrid` and **no** `/api/llm/status` endpoint — both were proposed in old docs but never landed. Engine availability is reflected in the `/api/translate` response shape (`{ ollama: { available: bool, translation: str } }`).

For the full three-engine flow + correction loop, see the [translation-orchestration-and-feedback](../translation-orchestration-and-feedback/SKILL.md) skill.

## Environment variables

| Var | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Where Ollama HTTP is | `http://localhost:11434` |
| `OLLAMA_MODEL_NAME` | (rarely needed) override base model | `llama3.2:3b` |

In dev, just `brew install ollama && ollama serve && ollama pull llama3.2:3b`. The wrapper handles the custom model build the first time `translate_text` runs (lazy).

## Debugging checklist

1. Is `ollama serve` running? `curl $OLLAMA_BASE_URL/api/version`.
2. Is the custom model built? `ollama list | grep chuukese-translator`.
3. Inside the container app, is the internal FQDN reachable from the main app? Hit `OLLAMA_BASE_URL/api/version` from a debug shell.
4. Cold-start latency on first translate is large (~10s); subsequent calls are fast. Don't add aggressive client timeouts.

## Pitfalls

- The modelfile's `FROM` path is local to the build machine. Don't commit a different machine's blob path expecting it to work elsewhere — always rebuild.
- The base model `llama3.2:3b` is small enough to run on Azure Container Apps with 2 CPU / 4 GiB. Larger Llama variants will OOM the current sizing.
- `ollama pull` on first container start adds ~30s to cold boot. `PREPULL_LLM=true` at build time avoids this at the cost of a much larger image — choose based on deployment cadence.
- Don't try to fine-tune the LLM with the dictionary data via Ollama — that's not what `extract_training_data` does. It builds *few-shot prompts* baked into the modelfile, not weight updates. For real fine-tuning, use the Helsinki path (see [production-retraining-orchestration](../production-retraining-orchestration/SKILL.md)).
