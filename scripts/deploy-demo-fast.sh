#!/bin/bash
# Fast Deploy MyMemex Demo
# Restarts the container with the latest code, skipping seeding.
# Uses the same isolated named volume as deploy-demo.sh.

set -e

export PATH=$PATH:/snap/bin

DEMO_VOLUME="mymemex-demo-data"
DEMO_DB_PATH="/var/lib/mymemex/demo.db"

echo "⚡ Starting MyMemex Fast Deployment..."

echo "📥 Fetching latest code..."
git fetch origin
git checkout demo-version
git reset --hard origin/demo-version
chmod +x scripts/*.sh

echo "🛠️ Rebuilding Docker image..."
docker build -t mymemex:demo .

echo "🛑 Replacing existing containers..."
docker stop mymemex-demo 2>/dev/null || true
docker rm mymemex-demo 2>/dev/null || true
docker stop mymemex 2>/dev/null || true
docker rm mymemex 2>/dev/null || true

echo "🚢 Starting container in demo mode on port 8001..."
docker run -d \
  --name mymemex-demo \
  -p 8001:8000 \
  --user root \
  -e DEMO_MODE=true \
  -e MYMEMEX_DATABASE__PATH="${DEMO_DB_PATH}" \
  -e MYMEMEX_LLM__PROVIDER=none \
  -e MYMEMEX_AI__SEMANTIC_SEARCH_ENABLED=false \
  -v "${DEMO_VOLUME}:/var/lib/mymemex" \
  --restart unless-stopped \
  --health-cmd "curl -f http://localhost:8000/health || exit 1" \
  --health-interval 30s \
  --health-timeout 10s \
  --health-retries 3 \
  mymemex:demo

echo "✅ Fast deployment complete!"
echo "📍 Access at: http://localhost:8001/ui/"
echo "📄 Logs: docker logs -f mymemex-demo"
