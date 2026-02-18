# M10: Deployment Options & Prerequisites

## Overview

Librarian can be deployed in multiple ways depending on your needs:

| Method | Best For | Complexity | AI Features |
|--------|----------|------------|-------------|
| **pip install** | Development, local use | Low | Needs local Ollama |
| **Docker standalone** | Simple server deployment | Medium | Needs external Ollama |
| **Docker Compose (full stack)** | Production with AI | Medium | Included (Ollama container) |
| **Systemd service** | Bare-metal Linux | Low | Needs local Ollama |

---

## Option 1: pip Install (Local Development)

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | 3.11+ recommended |
| pip | Latest | `pip install -U pip` |
| Tesseract OCR | 4.x+ | Optional, for OCR |
| Poppler utils | Any | For PDF processing |
| libmagic | Any | For MIME type detection |

**System packages (Ubuntu/Debian):**
```bash
sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu \
                 poppler-utils libmagic1
```

**System packages (macOS):**
```bash
brew install tesseract tesseract-lang poppler libmagic
```

### Installation

```bash
pip install librarian[ocr,ai,mcp]
librarian init
librarian serve
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Simple, familiar | Manual dependency management |
| Easy debugging | No isolation from system Python |
| Direct file access | Harder to update cleanly |

---

## Option 2: Docker Standalone

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 20.x+ | Docker Engine or Docker Desktop |
| Docker Compose | 2.x+ | Usually bundled with Docker |

**No system Python or packages needed — everything is in the container.**

### Installation

```bash
git clone https://github.com/joywareapps/librarian.git
cd librarian
cp config/config.example.yaml config/config.yaml
# Edit config.yaml
docker-compose up -d
```

### AI Features

For semantic search/classification/extraction, you need an Ollama instance:

**External Ollama (recommended):**
```yaml
# config.yaml
llm:
  provider: ollama
  model: gemma3:12b
  api_base: http://office-pc:11434  # Your Ollama server

ai:
  embedding_model: nomic-embed-text
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Isolated, reproducible | Separate Ollama needed for AI |
| Easy updates (rebuild) | Volume mount complexity |
| Non-root user in container | Manual config management |

---

## Option 3: Docker Compose Full Stack

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 20.x+ | Docker Engine or Docker Desktop |
| Docker Compose | 2.x+ | For multi-service orchestration |
| ~8GB RAM | Minimum | Ollama + embeddings need memory |
| ~20GB disk | Minimum | For models + vector store |

### Stack Components

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| librarian | Built | Main application | 8000 |
| ollama | ollama/ollama | LLM inference | 11434 |

### Installation

```yaml
# docker-compose.full.yml
services:
  librarian:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config:ro
      - librarian-data:/var/lib/librarian
      - /path/to/documents:/mnt/documents:ro
    environment:
      - LIBRARIAN_CONFIG=/app/config/config.yaml
    depends_on:
      - ollama
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    restart: unless-stopped
    # GPU support (optional)
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]

volumes:
  librarian-data:
  ollama-models:
```

**After startup, pull models:**
```bash
docker-compose exec ollama ollama pull nomic-embed-text
docker-compose exec ollama ollama pull gemma3:12b
```

### Pros & Cons

| Pros | Cons |
|------|------|
| Self-contained | Heavier resource usage |
| AI works out-of-box | GPU setup more complex |
| Single command deploy | Model download time |

---

## Option 4: Systemd Service (Bare Metal)

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Linux | Any systemd distro | Ubuntu, Debian, Fedora, etc. |
| Python | 3.10+ | System Python or pyenv |
| pip dependencies | All | `pip install librarian[ocr,ai,mcp]` |

### Installation

```bash
# Create service user
sudo useradd -r -s /bin/false librarian

# Install
sudo -u librarian pip install --user librarian[ocr,ai,mcp]

# Create service file
sudo nano /etc/systemd/system/librarian.service
```

**Service file:**
```ini
[Unit]
Description=Librarian Document Intelligence
After=network.target

[Service]
Type=simple
User=librarian
WorkingDirectory=/var/lib/librarian
Environment="LIBRARIAN_CONFIG=/etc/librarian/config.yaml"
ExecStart=/home/librarian/.local/bin/librarian serve --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable librarian
sudo systemctl start librarian
```

### Pros & Cons

| Pros | Cons |
|------|------|
| No container overhead | Manual dependency management |
| Native systemd logging | Harder to isolate |
| Simple resource control | Platform-specific |

---

## Comparison Matrix

| Feature | pip | Docker | Docker Compose | Systemd |
|---------|-----|--------|----------------|---------|
| **Ease of setup** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ |
| **Isolation** | ❌ | ✅ | ✅ | ❌ |
| **AI included** | ❌ | ❌ | ✅ | ❌ |
| **Updates** | Manual | Rebuild | Rebuild | Manual |
| **Resource usage** | Low | Medium | Higher | Low |
| **GPU support** | Native | Complex | Documented | Native |
| **适合** | Dev, testing | Simple prod | Full prod | Linux servers |

---

## Current State

### Already Implemented

- ✅ Dockerfile (multi-stage, non-root user)
- ✅ docker-compose.yml (standalone)
- ✅ DEPLOYMENT.md guide
- ✅ Health endpoint (`/health`)

### Missing for M10

| Item | Description | Effort |
|------|-------------|--------|
| docker-compose.full.yml | Full stack with Ollama | Low |
| Systemd service file | Example unit file | Low |
| Backup/restore scripts | SQLite + ChromaDB backup | Medium |
| Update documentation | README, user guide | Medium |
| Pre-built Docker image | GHCR or Docker Hub | Medium |
| Install script | One-line installer | Low |

---

## Recommendations

### For Your Setup (ThinkCentre M720q + Office PC with Ollama)

**Best option: Docker standalone with external Ollama**

Reasons:
1. Your Ollama is already running on `office-pc:11434`
2. ThinkCentre has limited RAM — no need for second Ollama
3. Docker gives isolation and easy updates
4. Simple volume mounts for documents

### For Users Without Dedicated Ollama

**Best option: Docker Compose full stack**

Reasons:
1. Self-contained, everything works
2. Single `docker-compose up -d` to start
3. GPU optional but beneficial

---

## Questions for M10 Implementation

1. **Publish Docker image?** To GHCR (free for public repos) or Docker Hub?
2. **Backup strategy?** Cron script? Built-in backup command?
3. **Update mechanism?** Watchtower? Manual? Script?
4. **Monitoring?** Health endpoint only? Prometheus metrics?
5. **Multi-arch?** Build for arm64 (Raspberry Pi, Apple Silicon)?
