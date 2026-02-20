#!/bin/bash
# Fast Deploy MyMemex Demo
# Restarts the container with the latest code, skipping seeding.

set -e

# Ensure snap binaries are in path
export PATH=$PATH:/snap/bin

echo "⚡ Starting MyMemex Fast Deployment..."

# 1. Get latest code
echo "📥 Fetching latest code..."
git fetch origin
git checkout demo-version
git reset --hard origin/demo-version
git pull origin demo-version
chmod +x scripts/*.sh

# 2. Build image (will use cache if dependencies haven't changed)
echo "🛠️ Rebuilding Docker image..."
docker build -t mymemex:demo .

# 3. Stop and remove existing container
echo "🛑 Replacing existing container..."
docker stop mymemex 2>/dev/null || true
docker rm mymemex 2>/dev/null || true

# 4. Start container in demo mode
ENV_FILE_ARG=""
if [ -f ".env" ]; then
    ENV_FILE_ARG="--env-file .env"
fi

echo "🚢 Starting container in demo mode on port 8001..."
docker run -d \
  --name mymemex \
  -p 8001:8000 \
  --user root \
  $ENV_FILE_ARG \
  -e DEMO_MODE=true \
  -v "$(pwd)/config:/app/config:ro" \
  -v "$(pwd)/data:/var/lib/mymemex" \
  --restart unless-stopped \
  mymemex:demo

echo "✅ Fast deployment complete!"
echo "📍 http://localhost:8001/ui/"
