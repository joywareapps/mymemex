# Deployment Specification for Librarian

**Date:** 2026-02-15
**Status:** Planning

---

## Deployment Models

### Model 1: All-in-One Docker Compose (Recommended)

Single `docker-compose up` deploys everything locally.

```yaml
# docker-compose.yml
version: '3.8'

services:
  librarian:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - /mnt/nas/documents:/documents:ro  # Your document archive
    environment:
      - LIBRARIAN_CONFIG=/app/config/config.yaml
      - OLLAMA_HOST=ollama:11434
    depends_on:
      - ollama
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"  # Optional: for external access
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]  # GPU acceleration if available
    restart: unless-stopped

  # Optional: Web UI (if separate from main service)
  # web:
  #   build: ./web
  #   ports:
  #     - "3000:3000"
  #   depends_on:
  #     - librarian

volumes:
  ollama_data:
```

---

### Model 2: External Ollama Server

For NAS/mini-PC where Ollama can't run (ARM, limited RAM, etc.).

```yaml
# docker-compose.yml (minimal)
version: '3.8'

services:
  librarian:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - /mnt/nas/documents:/documents:ro
    environment:
      - LIBRARIAN_CONFIG=/app/config/config.yaml
      - OLLAMA_HOST=${OLLAMA_HOST:-http://your-server:11434}
    restart: unless-stopped
    # No Ollama service - connects to external server
```

**Use when:**
- Target machine can't run Ollama (ARM, limited RAM)
- You have a more powerful machine for LLM inference
- Multiple Librarian instances share one Ollama server

---

### Model 3: Full Stack with PostgreSQL

For production deployments with pgvector.

```yaml
version: '3.8'

services:
  librarian:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - /mnt/nas/documents:/documents:ro
    environment:
      - LIBRARIAN_CONFIG=/app/config/config.yaml
      - OLLAMA_HOST=ollama:11434
      - DATABASE_URL=postgresql://librarian:${DB_PASSWORD}@postgres:5432/librarian
    depends_on:
      - postgres
      - ollama
    restart: unless-stopped

  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=librarian
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=librarian
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped

volumes:
  postgres_data:
  ollama_data:
```

---

## Model Pull Scripts

### `scripts/pull-models.sh`

```bash
#!/bin/bash
# Pull required Ollama models for Librarian
# Usage: ./scripts/pull-models.sh [ollama_host]

OLLAMA_HOST="${1:-http://localhost:11434}"
MODELS=(
  "nomic-embed-text:latest"     # Embeddings
  "llama3.2:3b"                  # Query agent (lightweight)
  "llama3.2:latest"              # Query agent (full)
)

echo "Pulling models from $OLLAMA_HOST..."

for model in "${MODELS[@]}"; do
  echo "Pulling $model..."
  curl -X POST "$OLLAMA_HOST/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$model\"}" \
    --no-buffer
  echo ""
done

echo "✅ All models pulled!"
echo ""
echo "Installed models:"
curl -s "$OLLAMA_HOST/api/tags" | jq -r '.models[].name'
```

### `scripts/pull-models-advanced.sh`

```bash
#!/bin/bash
# Pull models with options for different modes

set -e

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODE="${1:-standard}"  # standard, minimal, advanced

case $MODE in
  minimal)
    # Minimum viable models (under 4GB total)
    MODELS=(
      "nomic-embed-text:latest"
      "llama3.2:1b"
    )
    ;;
  standard)
    # Recommended for 16GB RAM
    MODELS=(
      "nomic-embed-text:latest"
      "llama3.2:3b"
    )
    ;;
  advanced)
    # For machines with 32GB+ RAM
    MODELS=(
      "nomic-embed-text:latest"
      "llama3.2:latest"
      "mistral:latest"
      "deepseek-coder:6.7b"  # For code documents
    )
    ;;
  *)
    echo "Usage: $0 [minimal|standard|advanced]"
    exit 1
    ;;
esac

echo "🤖 Pulling $MODE model set from $OLLAMA_HOST"
echo "Models: ${MODELS[*]}"
echo ""

for model in "${MODELS[@]}"; do
  echo "📥 Pulling $model..."
  ollama pull "$model" 2>&1 || curl -X POST "$OLLAMA_HOST/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$model\"}" \
    --no-buffer
  echo ""
done

echo "✅ Done! Disk usage:"
du -sh ~/.ollama 2>/dev/null || echo "(external Ollama server)"
```

---

## Configuration Wizard

### First-Run Wizard Flow

```
┌────────────────────────────────────────────────────────────────┐
│                    📚 LIBRARIAN SETUP                           │
│                                                                 │
│  Welcome! Let's configure your document intelligence platform. │
│                                                                 │
│  [1/5] Watch Folders                                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Which folders should Librarian monitor?                   │  │
│  │                                                           │  │
│  │ Path: [/mnt/nas/documents____________________] [+ Add]   │  │
│  │ Path: [/home/user/Downloads__________________] [+ Add]   │  │
│  │                                                           │  │
│  │ [x] Include subdirectories                                │  │
│  │ [ ] Watch for changes (disable for one-time import)       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│                                        [Back] [Next →]          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    🔒 PRIVACY MODE                              │
│                                                                 │
│  [2/5] Processing Mode                                          │
│                                                                 │
│  ○ LOCAL ONLY - No data leaves your machine                     │
│    (Uses Tesseract/PaddleOCR, slower but 100% private)          │
│                                                                 │
│  ○ HYBRID - Local first, cloud fallback                         │
│    (Uses cloud OCR only for difficult documents, asks first)    │
│                                                                 │
│  ● CLOUD ENHANCED - Best accuracy                               │
│    (May send documents to cloud OCR services)                   │
│                                                                 │
│  Sensitive folders (always local):                              │
│  [/mnt/nas/financial________________] [+ Add]                   │
│  [/mnt/nas/medical___________________] [+ Add]                   │
│                                                                 │
│                                        [Back] [Next →]          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    🤖 AI CONFIGURATION                          │
│                                                                 │
│  [3/5] LLM Server                                               │
│                                                                 │
│  ● Built-in Ollama (recommended)                                │
│    [x] Use GPU acceleration (NVIDIA detected)                   │
│    Model: [llama3.2:3b        ▼]                                │
│                                                                 │
│  ○ External Ollama server                                       │
│    URL: [http://192.168.1.100:11434_________]                   │
│                                                                 │
│  ○ No local LLM (API only - requires internet)                  │
│                                                                 │
│  [Test Connection]                                              │
│                                                                 │
│                                        [Back] [Next →]          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    📊 STORAGE                                   │
│                                                                 │
│  [4/5] Database Configuration                                   │
│                                                                 │
│  Metadata Database:                                             │
│  ● SQLite (recommended for personal use)                        │
│    Path: [./data/librarian.db______________]                    │
│                                                                 │
│  ○ PostgreSQL (for multi-user/enterprise)                       │
│    URL: [postgresql://____________________]                     │
│                                                                 │
│  Vector Database:                                               │
│  ● ChromaDB (embedded)                                          │
│    Path: [./data/chroma__________________]                      │
│                                                                 │
│  ○ pgvector (requires PostgreSQL)                               │
│                                                                 │
│                                        [Back] [Next →]          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    ✅ READY TO START                            │
│                                                                 │
│  [5/5] Configuration Summary                                    │
│                                                                 │
│  Watch folders:                                                 │
│    • /mnt/nas/documents (with subdirs)                          │
│    • /home/user/Downloads                                       │
│                                                                 │
│  Privacy: Local-first (cloud fallback for low confidence)       │
│  Sensitive: /mnt/nas/financial, /mnt/nas/medical                │
│                                                                 │
│  LLM: Ollama (local) with llama3.2:3b                           │
│  Embeddings: nomic-embed-text                                   │
│  OCR: PaddleOCR (local)                                         │
│                                                                 │
│  Storage: SQLite + ChromaDB                                     │
│  Data directory: ./data/                                        │
│                                                                 │
│  Estimated RAM usage: ~6GB                                      │
│  Estimated disk for 50k docs: ~15GB                             │
│                                                                 │
│  [ ] Start processing immediately after setup                   │
│  [ ] Start in background on boot                                │
│                                                                 │
│                            [Save & Start] [Save Only] [Cancel]  │
└────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables

```bash
# .env.example

# Core configuration
LIBRARIAN_CONFIG=/app/config/config.yaml
LIBRARIAN_DATA_DIR=/app/data
LIBRARIAN_LOG_LEVEL=INFO

# Ollama (if external)
OLLAMA_HOST=http://ollama:11434

# Database (if PostgreSQL)
DATABASE_URL=postgresql://librarian:password@postgres:5432/librarian

# Cloud OCR (optional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
GOOGLE_APPLICATION_CREDENTIALS=/app/secrets/gcp-key.json

# Security
LIBRARIAN_SECRET_KEY=  # Generate with: openssl rand -hex 32

# Features
LIBRARIAN_ENABLE_CLOUD_OCR=false
LIBRARIAN_AUTO_TAG=true
LIBRARIAN_AUTO_FILE=false
```

---

## Hardware Requirements

### Minimum (Local-only, small archive)
- CPU: 4 cores
- RAM: 8GB
- Storage: 50GB SSD
- Documents: Up to 10,000

### Recommended (Standard use)
- CPU: 8 cores
- RAM: 16GB
- Storage: 200GB SSD
- Documents: Up to 50,000
- GPU: Optional (NVIDIA with 6GB+ VRAM)

### High Performance (Enterprise/large archives)
- CPU: 16+ cores
- RAM: 32GB+
- Storage: 500GB+ NVMe
- Documents: 100,000+
- GPU: NVIDIA with 12GB+ VRAM

---

## Next Steps

1. ✅ Deployment models documented
2. 🔲 Create actual Dockerfile
3. 🔲 Create docker-compose.yml templates
4. 🔲 Implement configuration wizard CLI
5. 🔲 Test on Synology NAS
6. 🔲 Test on mini-PC (Intel NUC, etc.)
7. 🔲 Create installation documentation
