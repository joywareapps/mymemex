#!/usr/bin/env bash
# reset_db.sh — Delete local dev databases (SQLite + ChromaDB).
# Usage: ./scripts/reset_db.sh [--yes]

set -euo pipefail

DB_PATH="${MYMEMEX_DATABASE__PATH:-./data/mymemex.db}"
CHROMA_PATH="$(dirname "$DB_PATH")/chromadb"

if [[ "${1:-}" != "--yes" ]]; then
    echo "This will permanently delete:"
    echo "  SQLite:   $DB_PATH"
    echo "  ChromaDB: $CHROMA_PATH"
    echo ""
    read -r -p "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

if [[ -f "$DB_PATH" ]]; then
    rm -f "$DB_PATH"
    echo "Deleted: $DB_PATH"
else
    echo "Not found (skipped): $DB_PATH"
fi

if [[ -d "$CHROMA_PATH" ]]; then
    rm -rf "$CHROMA_PATH"
    echo "Deleted: $CHROMA_PATH"
else
    echo "Not found (skipped): $CHROMA_PATH"
fi

echo ""
echo "Done. Run 'mymemex serve' to recreate the database."
