#!/bin/bash
# Update MyMemex Website
# Rebuilds Astro site and deploys to SMB share
# Located at: mymemex/website/ (part of main repo)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Set SMB_PATH to your deployment target, e.g.:
# /run/user/1000/gvfs/smb-share:server=YOUR_SERVER,share=YOUR_SHARE/mymemex.joywareapps.com
SMB_PATH="${MYMEMEX_WEBSITE_DEPLOY_PATH:-}"
if [ -z "$SMB_PATH" ]; then
    echo "Error: MYMEMEX_WEBSITE_DEPLOY_PATH is not set." >&2
    echo "Set it to the SMB or local path to deploy to, e.g.:" >&2
    echo "  export MYMEMEX_WEBSITE_DEPLOY_PATH=/path/to/webroot" >&2
    exit 1
fi

echo "🔨 Building MyMemex website..."
echo "   Repo: $REPO_ROOT"
echo "   Website: $SCRIPT_DIR"
cd "$SCRIPT_DIR"
npm run build

echo "📦 Deploying to SMB share..."
# Use rsync with --no-perms to avoid SMB permission issues
if command -v rsync &> /dev/null; then
    # --exclude .well-known to preserve SSL/server config
    rsync -av --no-perms --no-owner --no-group --delete \
        --exclude '.well-known' \
        "${SCRIPT_DIR}/dist/" "$SMB_PATH/"
else
    # Fallback to cp if rsync not available
    echo "⚠️  rsync not found, using cp (slower)"
    rm -rf "${SMB_PATH:?}"/*
    cp -r "${SCRIPT_DIR}/dist/." "$SMB_PATH/"
fi

echo "✅ Website deployed to https://mymemex.io/"
echo ""
echo "Files deployed:"
ls -la "$SMB_PATH" | head -10
