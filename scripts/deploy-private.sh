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

# Resolve absolute path for the document library root (contains inbox/ and archive/ subdirs)
LIB_HOST_PATH=$(eval echo "${LIBRARY_PATH:-~/Documents}")
ABS_LIB_PATH=$(readlink -f "$LIB_HOST_PATH")

# Ensure inbox and archive subdirectories exist
mkdir -p "$ABS_LIB_PATH/inbox" "$ABS_LIB_PATH/archive"

docker run -d \
  --name mymemex-private \
  -p 8002:8000 \
  -p 8003:8001 \
  --user root \
  --env-file .env \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/data:/var/lib/mymemex" \
  -v "$ABS_LIB_PATH:/documents" \
  --restart unless-stopped \
  mymemex:latest

echo "✅ Deployment complete!"
echo "📍 Access at: http://localhost:8002/ui/"
echo "📄 Logs: docker logs -f mymemex-private"
