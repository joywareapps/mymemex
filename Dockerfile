FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # For python-magic
    libmagic1 \
    # For pdf2image
    poppler-utils \
    # For OCR (M5)
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 mymemex

# Set working directory
WORKDIR /app

# Install system dependencies
# (Already done above)

# Copy everything first
COPY --chown=mymemex:mymemex . .

# Install package and dependencies
RUN pip install --no-cache-dir ".[dev,ocr,demo]"

# Create data directory
RUN mkdir -p /var/lib/mymemex && chown mymemex:mymemex /var/lib/mymemex

# Switch to non-root user
USER mymemex

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["mymemex", "serve", "--host", "0.0.0.0", "--port", "8000"]
