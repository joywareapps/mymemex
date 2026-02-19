#!/bin/bash
# Deploy MyMemex Demo
# This script updates the demo-version branch and restarts the container in demo mode.

set -e

# Ensure snap binaries are in path
export PATH=$PATH:/snap/bin

echo "🚀 Starting MyMemex Demo deployment..."

# 1. Stop and remove existing container
echo "🛑 Stopping existing container..."
docker stop mymemex 2>/dev/null || true
docker rm mymemex 2>/dev/null || true

# 2. Get latest code
echo "📥 Fetching latest code from demo-version branch..."
git fetch origin
git checkout demo-version
# Reset local changes (like chmod +x mode changes) to allow clean pull
# Note: .env and data/ are gitignored, so they won't be affected by --hard reset
git reset --hard origin/demo-version
git pull origin demo-version
chmod +x scripts/deploy-demo.sh

# 3. Ensure config exists
if [ ! -f "config/config.yaml" ]; then
    echo "⚙️ Creating default config..."
    mkdir -p config
    cp config/config.example.yaml config/config.yaml
    # Set DB path for container environment
    sed -i 's|~/.local/share/mymemex/mymemex.db|/var/lib/mymemex/mymemex.db|g' config/config.yaml
fi

# 4. Build image
echo "🛠️ Rebuilding Docker image..."
docker build -t mymemex:demo .

# 5. Seed demo data
echo "🌱 Seeding demo documents..."
ENV_FILE_ARG=""
if [ -f ".env" ]; then
    ENV_FILE_ARG="--env-file .env"
fi

# We run a one-off container to generate the DB and documents
docker run --rm \
  --user root \
  $ENV_FILE_ARG \
  -v "$(pwd)/config:/app/config:ro" \
  -v "$(pwd)/data:/var/lib/mymemex" \
  -e MYMEMEX_DATABASE__PATH=/var/lib/mymemex/mymemex.db \
  mymemex:demo \
  python3 scripts/seed_demo_data.py

# 6. Start container in demo mode
echo "🚢 Starting container in demo mode on port 8001..."
# Using --user root to handle permissions on the data volume
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

echo "✅ Deployment complete!"
echo "📍 Access at: http://localhost:8001/ui/"
echo "📄 Logs: docker logs -f mymemex"
