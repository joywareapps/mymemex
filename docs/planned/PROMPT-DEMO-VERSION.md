# Prompt: Implement Demo Version

**Branch:** `demo-version`
**Target:** Deploy a public demo at demo.mymemex.io

---

## Objective

Create a read-only demo version of MyMemex that lets users explore the interface without self-hosting.

---

## Changes Required

### 1. Environment-Based Demo Mode

Add environment variable `DEMO_MODE=true` that:

**Disables uploads:**
- Hide upload button in Web UI nav
- Hide upload page (`/ui/upload`)
- Return 403 for any `/api/v1/documents/upload` requests
- Show banner on all pages: "You're exploring the demo. [Get your own instance →](https://github.com/joywareapps/mymemex)"

**Disables destructive operations:**
- Disable document deletion API
- Disable tag deletion API
- Disable config changes via admin panel
- Disable backup restore
- Disable MCP token generation

**Read-only admin:**
- Admin settings can be viewed but not saved
- Show "Demo mode - settings cannot be changed" message
- Watch folders visible but cannot be added/removed

### 2. Implementation Details

**Backend (`src/mymemex/app.py` or new middleware):**

```python
from starlette.middleware.base import BaseHTTPMiddleware

class DemoModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if os.environ.get("DEMO_MODE") == "true":
            # Block write operations
            if request.method in ("POST", "PATCH", "DELETE"):
                if is_write_operation(request.url.path):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Demo mode: write operations are disabled"}
                    )
        return await call_next(request)
```

**Blocked endpoints in demo mode:**
- `POST /api/v1/documents/upload`
- `DELETE /api/v1/documents/{id}`
- `DELETE /api/v1/tags/{id}`
- `PATCH /api/v1/admin/config`
- `POST /api/v1/admin/watch-folders`
- `DELETE /api/v1/admin/watch-folders/{id}`
- `POST /api/v1/admin/backup/run`
- `POST /api/v1/admin/backup/restore`
- `POST /api/v1/admin/mcp/tokens`
- `DELETE /api/v1/admin/mcp/tokens/{id}`
- `POST /api/v1/admin/users`
- `DELETE /api/v1/admin/users/{id}`
- `POST /api/v1/admin/queue/tasks/{id}/cancel`
- `POST /api/v1/admin/queue/retry-all`

**Frontend (`src/mymemex/web/templates/base.html`):**

```html
{% if demo_mode %}
<div class="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2 text-center">
  <span class="text-amber-400 text-sm">
    ⚠️ Demo mode — You're exploring a read-only instance.
    <a href="https://github.com/joywareapps/mymemex" class="underline hover:text-amber-300">
      Get your own instance →
    </a>
  </span>
</div>
{% endif %}
```

**Hide upload in nav:**
```html
{% if not demo_mode %}
<a href="/ui/upload" class="...">Upload</a>
{% endif %}
```

**Pass demo_mode to templates:**
- Add `demo_mode` to template context in `web/router.py`
- Read from `os.environ.get("DEMO_MODE")`

### 3. Docker Configuration

Add to `docker-compose.demo.yml`:

```yaml
services:
  mymemex-demo:
    image: ghcr.io/joywareapps/mymemex:demo
    environment:
      - DEMO_MODE=true
      - DATABASE_PATH=/app/data/demo.db
    volumes:
      - demo_data:/app/data
    # No watch directories - pre-populated only

volumes:
  demo_data:
```

### 4. Sample Data Seeding

Create `scripts/seed_demo_data.py` that generates synthetic documents on first run:

**Document types to generate:**
- 10 invoices (various vendors, amounts, dates)
- 5 receipts (groceries, restaurants, online purchases)
- 5 tax documents (showing extraction capabilities)
- 3 contracts/agreements
- 5 correspondence (letters, emails)
- 2 personal notes

**Use Faker library:**
```python
from faker import Faker
from reportlab.pdfgen import canvas
# or fpdf2
```

**Each document should:**
- Have realistic content (Faker-generated names, addresses, amounts)
- Be watermarked: "SAMPLE DATA - DEMO" (subtle footer)
- Cover different years (2020-2025) for date range queries
- Have different categories for filter testing
- Include various people names for person-tagging demo

### 5. Demo Reset (Optional)

Add cron job or scheduled task to reset demo database periodically:

```bash
# Reset demo every 6 hours
0 */6 * * * cp /app/data/demo_seed.db /app/data/demo.db && systemctl restart mymemex-demo
```

---

## Files to Create/Modify

**New files:**
- `src/mymemex/middleware/demo_mode.py` — Demo mode middleware
- `scripts/seed_demo_data.py` — Generate synthetic documents
- `docker-compose.demo.yml` — Demo deployment config
- `docs/DEPLOYMENT-DEMO.md` — Demo deployment instructions

**Modified files:**
- `src/mymemex/app.py` — Add demo middleware
- `src/mymemex/web/router.py` — Pass demo_mode to templates
- `src/mymemex/web/templates/base.html` — Banner + hide upload
- `src/mymemex/web/templates/upload.html` — Redirect or message
- `pyproject.toml` — Add faker, fpdf2 dependencies (optional group)

---

## Success Criteria

- [ ] `DEMO_MODE=true` blocks all write operations via API
- [ ] Upload button hidden in UI
- [ ] Demo banner shows on all pages
- [ ] Admin panel shows "demo mode" message, settings read-only
- [ ] Sample documents pre-loaded and searchable
- [ ] Search, filters, tags, document viewing all work
- [ ] Clear indication that this is a demo (watermarks, banners)

---

## Deployment

After implementation:

1. Build demo image: `docker build -t ghcr.io/joywareapps/mymemex:demo .`
2. Push to GHCR
3. Deploy to demo.mymemex.io with demo database
4. Set up periodic reset

---

## Notes

- This is a **read-only demo**, not a multi-tenant sandbox
- No real user data should ever be in the demo instance
- Consider rate limiting to prevent abuse
- MCP access should be disabled in demo mode
