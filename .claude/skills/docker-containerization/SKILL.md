---
name: docker-containerization
description: Reality of the Chuuk Dictionary container builds — multi-stage Flask + React app image and a separate Ollama sidecar image. No docker-compose is used. Use when modifying the Dockerfiles, debugging build failures, or adding system dependencies.
---

# Docker Containerization

Two Dockerfiles, no `docker-compose`. Production builds run in ACR (see the [azure-container-deployment](../azure-container-deployment/SKILL.md) skill); local builds are useful for smoke-testing only.

## Main app: [`Dockerfile`](../../../Dockerfile)

Multi-stage build:

1. **Frontend stage** — `node:18-slim`. `npm ci` from `frontend/package*.json`, then `npm run build` → `frontend/dist`.
2. **Runtime stage** — `python:3.11-slim`. Installs Tesseract (`tesseract-ocr-eng` only), `poppler-utils`, build toolchain. Installs Python deps. Copies `models/` (the Helsinki fine-tuned weights). `COPY . .` for app code. `COPY --from=frontend-builder /app/frontend/dist ./frontend/dist`.

Final command:
```
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 300 \
  --access-logfile - --error-logfile - app:app
```

The container runs as the **default user** (root in `python:3.11-slim`). There is **no** `HEALTHCHECK` and **no** dedicated non-root user. If you want either, add them — current state is "no".

The build context is the entire repo (`COPY . .`), filtered by [`.dockerignore`](../../../.dockerignore). Anything not excluded ships into the image — be deliberate when adding large fixtures.

## Ollama sidecar: [`Dockerfile.ollama`](../../../Dockerfile.ollama)

`python:3.11-slim` (not the official `ollama/ollama` base) plus the upstream installer:

```
RUN curl -fsSL https://ollama.com/install.sh | sh
```

Build arg `PREPULL_LLM=false` (default). When `true`, the image bakes in `llama3.2:3b` ([Dockerfile.ollama](../../../Dockerfile.ollama#L17)) — much larger image, faster cold start.

Entrypoint is [`ollama-entrypoint.sh`](../../../ollama-entrypoint.sh) which runs `ollama serve` and ensures the `chuukese-translator` custom model exists.

## System dependencies (and why they're there)

| Package | Reason |
|---|---|
| `tesseract-ocr` + `tesseract-ocr-eng` | OCR ([src/ocr/ocr_processor.py](../../../src/ocr/ocr_processor.py#L42)) |
| `poppler-utils` | `pdf2image` rasterization for PDF OCR |
| `gcc`, `g++`, `python3-dev` | Building wheels for `pymongo`/`numpy` extensions |

Tesseract data packs other than English are **not** installed — Chuukese is handled by post-processing at the OCR layer.

## Local build & run (for smoke testing)

```bash
# Build (slow on M-series due to amd64 cross — prefer ACR)
docker build -t chuuk-dictionary-app .
docker build -t chuuk-ollama -f Dockerfile.ollama .

# Run
docker run --rm -p 8000:8000 \
  -e COSMOS_MONGO_CONNECTION_STRING="$COSMOS_MONGO_CONNECTION_STRING" \
  -e FLASK_SECRET_KEY=dev-only \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  chuuk-dictionary-app

docker run --rm -p 11434:11434 chuuk-ollama
```

For full-stack local dev, use [`dev-start.sh`](../../../dev-start.sh) (Vite + Flask side-by-side, no containers).

## .dockerignore

Excludes `.venv/`, `node_modules/`, `tests/`, `.git/`, `uploads/`, `output/`, `training_data/`, plus the usual cache/byte-code patterns. **Note**: `models/` is *not* excluded — they're intentionally baked in.

## Common modifications

### Adding a system package
Add the line to the `apt-get install -y \\` block in [Dockerfile](../../../Dockerfile#L13). Combine with existing packages to keep one layer.

### Adding a Python package
Add it to [requirements.txt](../../../requirements.txt). Don't `pip install` in a new RUN line — that fragments the image.

### Adding a frontend dependency
`cd frontend && npm install <pkg>`. The build stage will pick it up via `npm ci`.

### Adding a Tesseract language
```
RUN apt-get update && apt-get install -y tesseract-ocr-<lang> && rm -rf /var/lib/apt/lists/*
```
Place it inside the existing system-deps block.

## Pitfalls

- `node:18-slim` is the current frontend base. Frontend builds fine on it; bumping to `node:20`/`node:22` is safe but verify Vite 7 + React 19 still build cleanly.
- The frontend stage's `WORKDIR /app/frontend` and the runtime stage's `WORKDIR /app` mean the `COPY --from=frontend-builder /app/frontend/dist ./frontend/dist` path is **stage-local** to the source side — don't shorten it.
- `pip install --root-user-action=ignore` is set because the runtime user is root; that flag is not "ignored" — it suppresses pip's warning. If you switch to a non-root user, drop the flag.
- `--workers 2 --timeout 300` is tuned for OCR/translate latency. Reducing the timeout will cut off long publication-processing SSE streams (see [publication-ocr-processing-workflow](../publication-ocr-processing-workflow/SKILL.md)).
- The `CMD` is plain JSON-array exec form. Don't switch to shell form unless you really want PID 1 semantics changed.
