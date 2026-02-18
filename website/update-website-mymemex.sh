#!/bin/bash
# Deploy MyMemex Website
# Rebuilds Astro site and deploys to mymemex.io

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMB_PATH="/run/user/1000/gvfs/smb-share:server=server-tiny-1,share=mymemex-htdocs/mymemex.io"

echo "🔨 Building MyMemex website..."
echo "   Repo: $SCRIPT_DIR"
cd "$SCRIPT_DIR"
npm run build

echo "📦 Deploying to mymemex.io..."
if command -v rsync &> /dev/null; then
    rsync -av --no-perms --no-owner --no-group --delete \
        "${SCRIPT_DIR}/dist/" "$SMB_PATH/"
else
    echo "⚠️  rsync not found, using cp"
    rm -rf "${SMB_PATH:?}"/*
    cp -r "${SCRIPT_DIR}/dist/." "$SMB_PATH/"
fi

echo "✅ Website deployed to https://mymemex.io/"
echo ""
echo "Files deployed:"
ls -la "$SMB_PATH" | head -10
