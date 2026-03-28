#!/bin/bash
# Deploy MyMemex Private (Personal Instance)
# Uses docker-compose.private.yml + .env in the repo directory.
#
# Required .env variables:
#   LIBRARY_PATH   — host path containing inbox/ and archive/ subdirs
#                    (mounted at the same path inside the container)
#   PRIVATE_HTTP_PORT — host port (default 8002)
#
# Example .env:
#   LIBRARY_PATH=/path/to/your/library
#   PRIVATE_HTTP_PORT=8002
#   MYMEMEX_LLM__PROVIDER=ollama
#   MYMEMEX_LLM__API_BASE=http://192.168.x.x:11434
#   MYMEMEX_LLM__MODEL=gemma3:12b
#   MYMEMEX_LLM__TIMEOUT=300

set -e
export PATH=$PATH:/snap/bin

echo "🚀 Starting MyMemex Private deployment..."

echo "📥 Fetching latest code from main branch..."
git fetch origin
git checkout main
git reset --hard origin/main
git pull origin main
chmod +x scripts/*.sh

# Ensure inbox/archive dirs exist under LIBRARY_PATH
if [ -f ".env" ]; then
    LIBRARY_PATH_VAL=$(grep -E '^LIBRARY_PATH=' .env | cut -d= -f2- | tr -d '"'"'" | sed 's|~|'"$HOME"'|')
    if [ -n "$LIBRARY_PATH_VAL" ]; then
        mkdir -p "$LIBRARY_PATH_VAL/inbox" "$LIBRARY_PATH_VAL/archive"
        echo "📁 Ensured $LIBRARY_PATH_VAL/inbox and $LIBRARY_PATH_VAL/archive exist"
    fi
fi

echo "🛠️  Building image..."
docker compose -f docker-compose.private.yml build

echo "🛑 Stopping existing container..."
docker compose -f docker-compose.private.yml down

echo "🚢 Starting container..."
docker compose -f docker-compose.private.yml up -d

echo "✅ Deployment complete!"
echo "📍 Access at: http://localhost:${PRIVATE_HTTP_PORT:-8002}/ui/"
echo "📄 Logs: docker compose -f docker-compose.private.yml logs -f"
