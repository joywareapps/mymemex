#!/usr/bin/env bash
# Deploy MyMemex Demo
# Uses an isolated Docker named volume — never touches real data.
set -e

export PATH=$PATH:/snap/bin

DEMO_VOLUME="mymemex-demo-data"
DEMO_DB_PATH="/var/lib/mymemex/demo.db"

echo "🚀 Starting MyMemex Demo deployment..."

echo "📥 Fetching latest code from demo-version branch..."
git fetch origin
git checkout demo-version
git reset --hard origin/demo-version
chmod +x scripts/deploy-demo.sh

echo "🛑 Stopping existing demo container..."
docker stop mymemex-demo 2>/dev/null || true
docker rm mymemex-demo 2>/dev/null || true
# Also clean up any old container named 'mymemex' that used real data
docker stop mymemex 2>/dev/null || true
docker rm mymemex 2>/dev/null || true

echo "🛠️ Building demo image..."
docker build -t mymemex:demo .

echo "🌱 Seeding demo documents into isolated volume (${DEMO_VOLUME})..."
# NOTE: Uses a named Docker volume only — never mounts ./data or real paths
docker run --rm \
  --user root \
  -v "${DEMO_VOLUME}:/var/lib/mymemex" \
  -e MYMEMEX_DATABASE__PATH="${DEMO_DB_PATH}" \
  -e MYMEMEX_LLM__PROVIDER=none \
  -e MYMEMEX_AI__SEMANTIC_SEARCH_ENABLED=false \
  mymemex:demo \
  python3 scripts/seed_demo_data.py

echo "🚢 Starting demo container on port 8001..."
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

echo "✅ Demo deployment complete!"
echo "📍 Access at: http://localhost:8001/ui/"
echo "📄 Logs: docker logs -f mymemex-demo"
