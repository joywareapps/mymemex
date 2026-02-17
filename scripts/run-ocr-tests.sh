#!/bin/bash
# Run OCR integration tests with visible output and audit logging
#
# Usage:
#   ./scripts/run-ocr-tests.sh              # Run all OCR tests
#   ./scripts/run-ocr-tests.sh --verbose    # Extra verbose output
#
# Prerequisites:
#   sudo apt-get install tesseract-ocr

set -e

cd "$(dirname "$0)/.."

echo "=== OCR Integration Tests ==="
echo ""

# Check Tesseract
if ! command -v tesseract &> /dev/null; then
    echo "❌ Tesseract not installed"
    echo "   Run: sudo apt-get install tesseract-ocr"
    exit 1
fi

echo "Tesseract: $(tesseract --version 2>&1 | head -1)"
echo ""

# Run tests
if [ "$1" = "--verbose" ] || [ "$1" = "-v" ]; then
    pytest tests/test_ocr.py tests/test_ocr_integration.py -v -s --tb=short
else
    pytest tests/test_ocr.py tests/test_ocr_integration.py -v --tb=short
fi

# Show audit log if created
if [ -f "tests/fixtures/ocr-audit.log" ]; then
    echo ""
    echo "=== Audit Log ==="
    cat tests/fixtures/ocr-audit.log
fi
