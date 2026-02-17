# Test Fixtures

This directory contains test files that are not committed to the repository.

## OCR Test Document

`ocr-test-document.pdf` - A real-world scanned PDF for OCR integration testing.

### How to add test fixtures:

1. Copy your PDF here:
   ```bash
   cp /path/to/your/scanned.pdf tests/fixtures/ocr-test-document.pdf
   ```

2. Run OCR integration tests:
   ```bash
   # Install Tesseract first
   sudo apt-get install tesseract-ocr

   # Run tests
   pytest tests/test_ocr_integration.py -v
   ```

### Why fixtures aren't committed:

- Large binary files bloat the repository
- Copyright/privacy concerns with real documents
- Developers can use their own test files

If you need a sample scanned PDF, you can:
- Scan a document yourself
- Use the synthetic `sample_pdf_scanned` fixture (always available)
- Find public domain scanned documents online
