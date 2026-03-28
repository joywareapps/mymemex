#!/bin/bash
# Deploy MyMemex Website
# Rebuilds Astro site and deploys to mymemex.io

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Set SMB_PATH to your deployment target, e.g.:
# /run/user/1000/gvfs/smb-share:server=YOUR_SERVER,share=YOUR_SHARE/mymemex.io
SMB_PATH="${MYMEMEX_WEBSITE_DEPLOY_PATH:-}"
if [ -z "$SMB_PATH" ]; then
    echo "Error: MYMEMEX_WEBSITE_DEPLOY_PATH is not set." >&2
    echo "Set it to the SMB or local path to deploy to, e.g.:" >&2
    echo "  export MYMEMEX_WEBSITE_DEPLOY_PATH=/path/to/webroot" >&2
    exit 1
fi

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
