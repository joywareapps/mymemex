# MyMemex Rebrand Checklist

**Created:** 2026-02-18
**Status:** In Progress

---

## ✅ Done

- [x] Decide on project name → **MyMemex**
- [x] Purchase domains → mymemex.io, mymemex.app
- [x] Create RENAME-PLAN.md
- [x] Update NAME-BRAINSTORM.md with decision
- [x] Update DOMAIN-AVAILABILITY.md with purchases
- [x] Create website teaser page (index.astro)
- [x] Create Cloudflare Worker for email signup
- [x] Deploy worker to Cloudflare
- [x] Configure Turnstile (site key + secret)
- [x] Redeploy website with real Turnstile key
- [x] Add demo version planning to TODO.md

---

## 🔴 Critical - Do Soon

### 1. GitHub Repository Rename
- [x] Rename repo: `librarian` → `mymemex`
  - Go to: https://github.com/joywareapps/librarian/settings
  - Change repository name to `mymemex`
  - GitHub auto-redirects old URL for 30 days
- [x] Update local git remote:
  ```bash
  cd ~/code/librarian
  git remote set-url origin https://github.com/joywareapps/mymemex.git
  ```
- [x] Rename local folder:
  ```bash
  mv ~/code/librarian ~/code/mymemex
  ```

### 2. Update pyproject.toml
- [x] Change name: `name = "mymemex"`
- [x] Update description
- [x] Update URLs (homepage, repository, issues)

### 3. Update Docker Workflow
- [x] `.github/workflows/docker.yml` — Update image name:
  ```yaml
  image: ghcr.io/joywareapps/mymemex
  ```
  (Auto-resolved via `${{ github.repository }}`)
- [x] Update docker-compose.yml references
- [x] Update docker-compose.full.yml references

### 4. Update README.md
- [ ] Title: "MyMemex - Your AI Document Memory"
- [ ] Update all `librarian` commands to `mymemex`
- [ ] Update Docker examples
- [ ] Update links to new GitHub URL

### 5. Update Other Website Pages
- [ ] features.astro — Replace "Librarian" → "MyMemex"
- [ ] architecture.astro — Replace "Librarian" → "MyMemex"
- [ ] roadmap.astro — Replace "Librarian" → "MyMemex"
- [ ] All GitHub links to `joywareapps/mymemex`

---

## 🟡 Important - Do Before Launch

### 6. CLI Command Rename
- [ ] Update `src/librarian/__main__.py` — Change CLI command
- [ ] Update help text
- [ ] Consider: Keep `librarian` as alias or hard break?

### 7. Module Rename (Optional)
**Decision needed:** Rename `src/librarian/` → `src/mymemex/`?
- **Option A:** Keep as `librarian` internally (less breaking)
- **Option B:** Full rename (cleaner, more work)

If Option B:
- [ ] Rename `src/librarian/` → `src/mymemex/`
- [ ] Update all imports
- [ ] Update pyproject.toml packages

### 8. Licensing Files
- [ ] Update LICENSE with MyMemex name
- [ ] Update COMMERCIAL-LICENSE.md
- [ ] Update SUPPORTERS.md

### 9. Documentation
- [ ] Update docs/INSTALLATION.md
- [ ] Update docs/MILESTONES.md
- [ ] Update PROJECT_STATUS.md
- [ ] Update config.example.yaml comments

### 10. Email Notifications (Mailchannels)
Worker stores emails in KV, but notifications may not work.
- [ ] Add SPF record to mymemex.io:
  ```
  v=spf1 include:relay.mailchannels.net ~all
  ```
- [ ] Add domain lock record:
  ```
  _mailchannels.mymemex.io TXT "v=mc1 cfid=YOUR_CF_ZONE_ID"
  ```
- [ ] Verify NOTIFICATION_EMAIL secret is correct
- [ ] Test email delivery with `wrangler tail`

---

## 🟢 Nice to Have

### 11. Website Improvements
- [ ] Create custom MyMemex favicon (brain/memory icon)
- [ ] Create Open Graph image for social sharing
- [ ] Add meta tags for SEO
- [ ] Remove index-old.astro (cleanup)

### 12. Cloudflare Route
- [ ] Verify worker route is configured:
  - Route: `mymemex.io/api/subscribe*`
  - Worker: `mymemex-subscribe`
- Or add to wrangler.toml and redeploy

### 13. PyPI Package
- [ ] Reserve package name: `pip install mymemex`
- [ ] Update publishing workflow
- [ ] First release under new name

### 14. Social/Community
- [ ] Create Discord server (docs/DISCORD-SETUP.md ready)
- [ ] Update GitHub repo description
- [ ] Update GitHub social preview image
- [ ] Create Twitter/X account? (optional)

---

## 📋 Quick Reference

### Files to Update (Search "Librarian" → "MyMemex")

```
Priority 1 (Critical):
- pyproject.toml
- README.md
- .github/workflows/docker.yml
- docker-compose.yml

Priority 2 (Website):
- website/src/pages/features.astro
- website/src/pages/architecture.astro
- website/src/pages/roadmap.astro

Priority 3 (Docs):
- docs/INSTALLATION.md
- docs/MILESTONES.md
- PROJECT_STATUS.md
- config/config.example.yaml
```

### Commands to Update

```bash
# Old → New
librarian serve      →  mymemex serve
librarian ingest     →  mymemex ingest
librarian mcp serve  →  mymemex mcp serve
pip install librarian → pip install mymemex

# Docker
ghcr.io/joywareapps/librarian → ghcr.io/joywareapps/mymemex
```

---

## Timeline Suggestion

| Phase | Tasks | When |
|-------|-------|------|
| **Phase 1** | Rename GitHub repo, update pyproject.toml, Docker workflow | Now (before more commits) |
| **Phase 2** | Update README, website pages | This week |
| **Phase 3** | Module rename, CLI rename, docs | Before v1.0 |
| **Phase 4** | PyPI, social, community | At launch |

---

## Notes

- GitHub redirects old URLs for 30 days after rename
- Docker images need to be republished under new name
- PyPI requires new package registration
- DNS changes can take 24-48 hours (already done ✅)

---

*Last updated: 2026-02-18 18:15*
