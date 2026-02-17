#!/bin/bash
# Update Librarian Website
# Rebuilds Astro site and deploys to SMB share
# Located at: librarian/website/ (part of main repo)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SMB_PATH="/run/user/1000/gvfs/smb-share:server=server-tiny-1,share=librarian-htdocs/librarian.joywareapps.com"

echo "🔨 Building Librarian website..."
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

echo "✅ Website deployed to https://librarian.joywareapps.com/"
echo ""
echo "Files deployed:"
ls -la "$SMB_PATH" | head -10
