#!/bin/bash
set -e

echo "Starting Ollama service..."

# Start Ollama server
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:11434/ > /dev/null 2>&1; then
        echo "Ollama is ready!"
        break
    fi
    echo "Waiting for Ollama... ($i/30)"
    sleep 2
done

# Create the custom Chuukese translator model from the modelfile
if [ -f "/app/ollama-modelfile/chuukese-translator.modelfile" ]; then
    echo "Creating custom Chuukese translator model..."
    ollama create chuukese-translator -f /app/ollama-modelfile/chuukese-translator.modelfile || {
        echo "Warning: Failed to create custom model, but Ollama is running"
    }
else
    echo "Warning: Modelfile not found, only base model available"
fi

echo "Ollama service is running!"

# Keep the container running
wait $OLLAMA_PID
