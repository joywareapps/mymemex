#!/bin/bash
# Deploy MyMemex Private (Personal Instance)
# This script updates the main branch and restarts the container on port 8002.

set -e

# Ensure snap binaries are in path
export PATH=$PATH:/snap/bin

echo "🚀 Starting MyMemex Private deployment..."

# 1. Stop and remove existing container
echo "🛑 Stopping existing container..."
docker stop mymemex-private 2>/dev/null || true
docker rm mymemex-private 2>/dev/null || true

# 2. Get latest code
echo "📥 Fetching latest code from main branch..."
git fetch origin
git checkout main
git reset --hard origin/main
git pull origin main
chmod +x scripts/*.sh

# 3. Build image
echo "🛠️ Rebuilding Docker image..."
docker build -t mymemex:latest .

# 4. Start container
echo "🚢 Starting container on port 8002..."

if [ -f ".env" ]; then
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | xargs)
fi

# Resolve absolute path for documents to avoid Docker error
DOCS_HOST_PATH=$(eval echo "${DOCUMENTS_PATH:-~/Documents}")
ABS_DOCS_PATH=$(readlink -f "$DOCS_HOST_PATH")

# Library path for organized files
LIB_HOST_PATH=$(eval echo "${LIBRARY_PATH:-$ABS_DOCS_PATH}")
ABS_LIB_PATH=$(readlink -f "$LIB_HOST_PATH")

docker run -d \
  --name mymemex-private \
  -p 8002:8000 \
  --user root \
  --env-file .env \
  -v "$(pwd)/config:/app/config:ro" \
  -v "$(pwd)/data:/var/lib/mymemex" \
  -v "$ABS_DOCS_PATH:/app/inbox" \
  -v "$ABS_LIB_PATH:/media/seagate/mymemex" \
  --restart unless-stopped \
  mymemex:latest

echo "✅ Deployment complete!"
echo "📍 Access at: http://localhost:8002/ui/"
echo "📄 Logs: docker logs -f mymemex-private"
