FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # For health checks
    curl \
    # For python-magic
    libmagic1 \
    # For pdf2image
    poppler-utils \
    # For OCR (M5)
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    tesseract-ocr-srp \
    tesseract-ocr-hrv \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 mymemex

# Set working directory
WORKDIR /app

# Install system dependencies
# (Already done above)

# Install Python dependencies first (for better caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.34" "pydantic>=2.10" "pydantic-settings>=2.6" "typer>=0.15" "rich>=13.9" "structlog>=25.1" "sqlalchemy>=2.0" "alembic>=1.14" "aiosqlite>=0.20" "watchdog>=6.0" "python-magic>=0.4.27" "xxhash>=3.5" "pymupdf>=1.25" "pillow>=11.0" "pdf2image>=1.17" "ftfy>=6.3" "langdetect>=1.0" "httpx>=0.28" "pyyaml>=6.0" "python-multipart>=0.0.18" "jinja2>=3.1" "croniter>=1.3" "pytesseract>=0.3" "faker>=33.0" "fpdf2>=2.8"

# Copy everything else
COPY --chown=mymemex:mymemex . .

# Final install to register the local package
RUN pip install --no-cache-dir -e "."

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
