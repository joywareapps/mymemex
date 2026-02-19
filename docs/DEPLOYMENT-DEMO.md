# MyMemex Demo Deployment

This guide explains how to deploy the read-only demo version of MyMemex at `demo.mymemex.io`.

## 1. Build Demo Image

```bash
docker build -t ghcr.io/joywareapps/mymemex:demo .
```

## 2. Prepare Demo Database

Run the seed script to generate synthetic data and create the initial database:

```bash
# Install demo dependencies
pip install ".[demo]"

# Run seed script
export MYMEMEX_DATABASE__PATH=./data/demo_seed.db
python scripts/seed_demo_data.py
```

## 3. Deployment with Docker Compose

Create `docker-compose.yml` on the production server:

```yaml
services:
  mymemex-demo:
    image: ghcr.io/joywareapps/mymemex:demo
    container_name: mymemex-demo
    ports:
      - "8000:8000"
    environment:
      - DEMO_MODE=true
      - MYMEMEX_DATABASE__PATH=/app/data/demo.db
      - MYMEMEX_AI__SEMANTIC_SEARCH_ENABLED=false # Optional: enable if Ollama available
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

## 4. Automated Reset

To keep the demo clean, set up a cron job to reset the database every 6 hours:

```bash
# crontab -e
0 */6 * * * cp /path/to/data/demo_seed.db /path/to/data/demo.db && docker restart mymemex-demo
```

## 5. Security Notes

- `DEMO_MODE=true` blocks all write operations (POST, PATCH, DELETE) via the API middleware.
- The upload page is hidden from the navigation.
- A banner is displayed on all pages indicating the read-only state.
- MCP access should be restricted or disabled in the reverse proxy configuration.
