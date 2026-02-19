# Deployment Checklist

## ✅ Completed

- [x] M1-M4 implementation (32 files, 43 tests)
- [x] Local validation (all tests passed)
- [x] Docker files created (Dockerfile, docker-compose.yml)
- [x] Deployment guide written (DEPLOYMENT.md)
- [x] Code ready to commit

## 🚀 Next Steps

### 1. Commit and Push
```bash
cd ~/code/mymemex
git add Dockerfile docker-compose.yml DEPLOYMENT.md
git commit -m "Add Docker deployment configuration and production guide"
git push origin main
```

### 2. Deploy to ThinkCentre M720q

**Option A: Manual deployment**
```bash
# On ThinkCentre
git clone https://github.com/joywareapps/mymemex.git
cd mymemex
cp config/config.example.yaml config/config.yaml
nano config/config.yaml  # Add your document paths

# Mount NAS documents if needed
# Edit docker-compose.yml to add volume mounts

docker-compose up -d
```

**Option B: Automated deployment (later)**
- Set up GitHub Actions to build Docker image
- Push to GitHub Container Registry
- Auto-deploy to ThinkCentre via SSH

### 3. Configure Document Watching

Edit `config/config.yaml`:
```yaml
watch:
  directories:
    - /mnt/nas/documents  # Your NAS path
  file_patterns:
    - "*.pdf"
    - "*.png"
    - "*.jpg"
```

Update `docker-compose.yml` volumes:
```yaml
volumes:
  - /mnt/nas/documents:/mnt/nas/documents:ro
```

### 4. Test Deployment

```bash
# Check container is running
docker-compose ps

# Check logs
docker-compose logs -f mymemex

# Test API
curl http://localhost:8000/health

# Check documents are being watched
curl http://localhost:8000/api/v1/documents
```

### 5. Set Up Reverse Proxy (Optional)

For external access, use Nginx:
```nginx
server {
    listen 80;
    server_name mymemex.joywareapps.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 6. Enable HTTPS (Production)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d mymemex.joywareapps.com

# Auto-renewal
sudo systemctl enable certbot.timer
```

## 📊 Monitoring

- Health endpoint: http://thinkcentre:8000/health
- API docs: http://thinkcentre:8000/docs
- Container stats: `docker stats mymemex`

## 🔄 Updates

To update the deployment:
```bash
cd ~/code/mymemex
git pull
docker-compose build
docker-compose up -d
```

## 🎯 Future Enhancements

- [ ] M5: OCR integration (Tesseract for scanned documents)
- [ ] M6: Ollama embeddings (add to docker-compose.yml)
- [ ] M7: RAG query interface
- [ ] M8: Auto-classification and tagging
- [ ] M9: Filing suggestions
- [ ] Backup automation (cron job for SQLite backups)
- [ ] Monitoring (Prometheus/Grafana or Uptime Kuma)
