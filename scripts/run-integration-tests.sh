#!/bin/bash
# Run integration tests against real Ollama instance
#
# Usage:
#   ./scripts/run-integration-tests.sh                    # Uses default office-pc
#   OLLAMA_API_BASE=http://localhost:11434 ./scripts/run-integration-tests.sh

set -e

OLLAMA_HOST="${OLLAMA_API_BASE:-http://office-pc:11434}"

echo "=== Ollama Integration Tests ==="
echo ""
echo "Ollama API: $OLLAMA_HOST"
echo ""

# Check if Ollama is reachable
echo "Checking Ollama connectivity..."
if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo "✅ Ollama is reachable"
else
    echo "❌ Cannot reach Ollama at $OLLAMA_HOST"
    echo ""
    echo "Make sure:"
    echo "  1. Ollama is running: ollama serve"
    echo "  2. Model is pulled: ollama pull nomic-embed-text"
    echo "  3. Network allows connections to $OLLAMA_HOST"
    exit 1
fi

# Check if model is available
echo ""
echo "Checking for nomic-embed-text model..."
MODELS=$(curl -s "$OLLAMA_HOST/api/tags" | python3 -c "import sys, json; data=json.load(sys.stdin); print(' '.join(m['name'] for m in data.get('models', [])))")

if echo "$MODELS" | grep -q "nomic-embed-text"; then
    echo "✅ nomic-embed-text model is available"
else
    echo "❌ nomic-embed-text model not found"
    echo "   Available models: $MODELS"
    echo ""
    echo "Pull the model with: ollama pull nomic-embed-text"
    exit 1
fi

echo ""
echo "Running integration tests..."
echo ""

# Run tests
OLLAMA_API_BASE="$OLLAMA_HOST" pytest tests/test_ollama_integration.py tests/test_semantic_search_e2e.py -v --tb=short

echo ""
echo "=== Integration tests complete ==="
