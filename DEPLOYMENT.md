# Librarian Docker Deployment

## Quick Start

### 1. Build and Run (Local)

```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f librarian

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
  path: /var/lib/librarian/librarian.db

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
docker-compose up -d
```

### Option 2: Production Server

#### On ThinkCentre M720q (Home Server)

```bash
# SSH to server
ssh user@thinkcentre

# Clone repository
git clone https://github.com/joywareapps/librarian.git
cd librarian

# Create config
cp config/config.example.yaml config/config.yaml
nano config/config.yaml

# Build and start
docker-compose up -d

# Enable auto-start on boot
docker-compose enable
```

#### With Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name librarian.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Option 3: With Ollama (M6+ - AI Features)

```yaml
# docker-compose.yml - add Ollama service
services:
  librarian:
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

Then update config:
```yaml
llm:
  provider: ollama
  model: llama2
  api_base: http://ollama:11434
```

## Management

### View Logs
```bash
docker-compose logs -f librarian
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
docker-compose exec librarian sqlite3 /var/lib/librarian/librarian.db ".backup /var/lib/librarian/backup.db"
```

### Restore Database
```bash
docker-compose down
cp backup.db /var/lib/docker/volumes/librarian_librarian-data/_data/librarian.db
docker-compose up -d
```

## Troubleshooting

### Check Container Status
```bash
docker-compose ps
docker-compose logs librarian
```

### Access Container Shell
```bash
docker-compose exec librarian /bin/bash
```

### Test Health
```bash
curl http://localhost:8000/health
```

### Check Database
```bash
docker-compose exec librarian sqlite3 /var/lib/librarian/librarian.db ".tables"
```

## Security Considerations

1. **Read-Only Mounts**: Mount document directories as read-only (`:ro`)
2. **Non-Root User**: Container runs as `librarian` user (UID 1000)
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
