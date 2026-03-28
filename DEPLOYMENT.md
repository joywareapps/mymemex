# MyMemex Docker Deployment

## Quick Start

### 1. Build and Run (Local)

```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f mymemex

# Stop the service
docker-compose down
```

### 2. Access the API

Once running, access the API at:
- **API**: http://localhost:8000
- **Health**: http://localhost:8000/health
- **Docs**: http://localhost:8000/docs
- **OpenAPI**: http://localhost:8000/openapi.json

## Configuration

### 1. Create Configuration File

```bash
cp config/config.example.yaml config/config.yaml
```

### 2. Edit Configuration

```yaml
watch:
  directories:
    - /mnt/nas/documents  # Your document path
  file_patterns:
    - "*.pdf"
    - "*.png"
    - "*.jpg"
    - "*.jpeg"

database:
  path: /var/lib/mymemex/mymemex.db

ocr:
  enabled: true
  language: eng  # or eng+deu for English + German
```

### 3. Mount Document Directories

Edit `docker-compose.yml` to add your document directories:

```yaml
volumes:
  - /path/to/your/documents:/mnt/documents:ro
```

Then update config:
```yaml
watch:
  directories:
    - /mnt/documents
```

## Deployment Options

### Option 1: Local Development

```bash
# Run with Docker Compose
docker compose up -d
```

### Option 2: Private / Personal Instance

The recommended way to run a personal instance with a dedicated document library (inbox + archive) and full AI features.

**Prerequisites:** A `.env` file in the repo root:

```bash
# Required
LIBRARY_PATH=/path/to/your/library     # must contain inbox/ and archive/ subdirs
PRIVATE_HTTP_PORT=8002                  # host port (default 8002)

# Optional — LLM (Ollama)
MYMEMEX_LLM__PROVIDER=ollama
MYMEMEX_LLM__API_BASE=http://192.168.1.x:11434
MYMEMEX_LLM__MODEL=gemma3:12b
MYMEMEX_LLM__TIMEOUT=300
MYMEMEX_AI__SEMANTIC_SEARCH_ENABLED=true
MYMEMEX_AI__EMBEDDING_MODEL=nomic-embed-text
MYMEMEX_AI__EMBEDDING_DIMENSION=768
```

**Deploy:**

```bash
# First deploy (builds image, ensures inbox/archive dirs exist)
bash scripts/deploy-private.sh

# Access
open http://localhost:8002/ui/

# MCP HTTP transport (for Claude Desktop / OpenClaw)
# available on port 8003
```

What it creates:
- Container `mymemex-private` on port 8002 (MCP on 8003)
- `./data/` bind-mounted as the database directory
- `LIBRARY_PATH` mounted as `/documents` (read/write)
- `LIBRARY_PATH/inbox` also mounted as `/app/inbox` for the file watcher

### Option 3: Public Demo Instance

> **Live demo:** https://mymemex.app/ui/ — read-only, no sign-up needed.

Runs a read-only demo with seeded dummy documents, completely isolated from any real data.

```bash
# Full deploy (builds image, seeds demo data, starts container)
bash scripts/deploy-demo.sh

# Fast re-deploy (skip seeding, keep existing demo data)
bash scripts/deploy-demo-fast.sh

# Access
open http://localhost:8001/ui/
```

What it creates:
- Container `mymemex-demo` on port 8001
- Named Docker volume `mymemex-demo-data` (never touches `./data` or `.env`)
- `DEMO_MODE=true` — write operations are blocked in the UI
- LLM disabled (`MYMEMEX_LLM__PROVIDER=none`)
- ~50 seeded demo documents (invoices, contracts, receipts)

### Option 4: Production Server

```bash
# SSH to server
ssh user@yourserver
cd /path/to/mymemex

# Create .env
cp .env.example .env
nano .env

# Build and start
docker compose up -d
```

#### With Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name mymemex.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 5: With Ollama (AI Features)

```yaml
# docker-compose.yml - add Ollama service
services:
  mymemex:
    # ... existing config ...
    environment:
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-models:/root/.ollama
    restart: unless-stopped

volumes:
  ollama-models:
```

Then in `.env`:
```bash
MYMEMEX_LLM__PROVIDER=ollama
MYMEMEX_LLM__MODEL=gemma3:12b
MYMEMEX_LLM__API_BASE=http://ollama:11434
```

## Management

### View Logs
```bash
docker-compose logs -f mymemex
```

### Restart Service
```bash
docker-compose restart
```

### Update
```bash
git pull
docker-compose build
docker-compose up -d
```

### Backup Database
```bash
docker-compose exec mymemex sqlite3 /var/lib/mymemex/mymemex.db ".backup /var/lib/mymemex/backup.db"
```

### Restore Database
```bash
docker-compose down
cp backup.db /var/lib/docker/volumes/mymemex_mymemex-data/_data/mymemex.db
docker-compose up -d
```

## Troubleshooting

### Check Container Status
```bash
docker-compose ps
docker-compose logs mymemex
```

### Access Container Shell
```bash
docker-compose exec mymemex /bin/bash
```

### Test Health
```bash
curl http://localhost:8000/health
```

### Check Database
```bash
docker-compose exec mymemex sqlite3 /var/lib/mymemex/mymemex.db ".tables"
```

## Security Considerations

1. **Read-Only Mounts**: Mount document directories as read-only (`:ro`)
2. **Non-Root User**: Container runs as `mymemex` user (UID 1000)
3. **Network Isolation**: Use Docker networks for service isolation
4. **Reverse Proxy**: Use Nginx/Traefik with HTTPS for production
5. **Firewall**: Restrict port 8000 to localhost if using reverse proxy

## Resource Limits

Default limits (adjust in docker-compose.yml):
- **Memory**: 256MB-1GB
- **CPU**: No limit (adjust as needed)

For heavy OCR workloads:
```yaml
deploy:
  resources:
    limits:
      memory: 2G
```
