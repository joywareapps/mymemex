# Rename Plan: Librarian → MyMemex

**Date:** 2026-02-18
**Status:** Planning complete, awaiting DNS configuration

---

## Overview

Rename the project from "Librarian" to "MyMemex" across all touchpoints.

---

## Phase 1: GitHub & Code (Do First)

### 1.1 GitHub Repository
- [ ] Rename repo: `librarian` → `mymemex` (GitHub Settings → Rename)
- [ ] Update repo description
- [ ] Update repo topics/tags
- [ ] Update social preview image

### 1.2 pyproject.toml
- [ ] Change `name = "mymemex"`
- [ ] Update description
- [ ] Update URLs (homepage, repository, issues)
- [ ] Update author info if needed

### 1.3 Package/Module Names
- [ ] Consider: Keep `src/librarian/` or rename to `src/mymemex/`?
  - **Option A:** Keep internal module as `librarian`, only change external branding
  - **Option B:** Full rename to `mymemex` (more work, cleaner long-term)
- [ ] Update all imports if renaming modules

### 1.4 CLI Command
- [ ] Change `librarian` → `mymemex` in `__main__.py`
- [ ] Update help text
- [ ] Update man page if exists

### 1.5 Docker
- [ ] Update `ghcr.io/joywareapps/mymemex` in:
  - [ ] docker-compose.yml
  - [ ] docker-compose.full.yml
  - [ ] .github/workflows/docker.yml
- [ ] Update container_name in compose files

### 1.6 GitHub Actions
- [ ] Update workflow to publish to new image name
- [ ] Test on next release

---

## Phase 2: Documentation

### 2.1 README.md
- [ ] Update title: "MyMemex - Your AI Document Memory"
- [ ] Update description
- [ ] Update installation instructions
- [ ] Update CLI examples (`librarian` → `mymemex`)
- [ ] Update Docker examples
- [ ] Update links to new domain

### 2.2 docs/
- [ ] INSTALLATION.md — Update all references
- [ ] MILESTONES.md — Update project name
- [ ] M10-DEPLOYMENT-OPTIONS.md — Update references
- [ ] Any other docs with "Librarian"

### 2.3 Config Files
- [ ] config/config.example.yaml — Update comments
- [ ] .env.example — Update comments

### 2.4 MCP Server
- [ ] Update server name in MCP config
- [ ] Update resource URIs if needed
- [ ] Update tool descriptions

---

## Phase 3: Website (After DNS Configured)

### 3.1 DNS Setup
- [ ] Configure mymemex.io → GitHub Pages
- [ ] Set up CNAME in repo
- [ ] Wait for DNS propagation
- [ ] Enable HTTPS

### 3.2 Website Content
- [ ] Update `website/src/pages/index.astro`
  - [ ] Title: "MyMemex"
  - [ ] Tagline: "Your AI Document Memory"
  - [ ] Description
  - [ ] Logo/favicon
- [ ] Update all pages with new branding
- [ ] Update navigation
- [ ] Update footer links
- [ ] Update meta tags for SEO

### 3.3 Website Assets
- [ ] Create new logo
- [ ] Create new favicon
- [ ] Update Open Graph images
- [ ] Update any screenshots

### 3.4 Deploy
- [ ] Build and deploy to new domain
- [ ] Test all pages
- [ ] Verify HTTPS

---

## Phase 4: External Integrations

### 4.1 OpenClaw Skill
- [ ] Update skill name
- [ ] Update MCP server connection
- [ ] Update documentation

### 4.2 Package Registries
- [ ] Reserve PyPI package name `mymemex`
- [ ] Publish first version after rename

---

## Phase 5: Communications

### 5.1 Social/Community
- [ ] Update GitHub profile bio if mentioned
- [ ] Update any social media links
- [ ] Plan announcement post/blog

### 5.2 Existing Users
- [ ] Add migration guide if needed
- [ ] Update Docker pull instructions
- [ ] Update pip install instructions

---

## Files to Update (Quick Reference)

```
# High Priority
pyproject.toml
README.md
src/librarian/__main__.py
docker-compose.yml
docker-compose.full.yml
.github/workflows/docker.yml

# Documentation
docs/INSTALLATION.md
docs/MILESTONES.md
PROJECT_STATUS.md
TODO.md

# Config
config/config.example.yaml
.env.example

# Website (Phase 3)
website/src/pages/*.astro
website/src/layouts/*.astro
```

---

## Renaming Strategy

### Option A: Soft Rebrand (Recommended for now)
- Keep internal module name `librarian`
- Change external branding: CLI, docs, website, Docker
- Less breaking changes
- Can do full rename later

### Option B: Full Rename
- Rename everything including `src/librarian/` → `src/mymemex/`
- More work but cleaner
- Breaking change for anyone importing the library

---

## Timeline

| Phase | When | Duration |
|-------|------|----------|
| Phase 1: Code | Now | 1-2 hours |
| Phase 2: Docs | After Phase 1 | 1 hour |
| Phase 3: Website | After DNS ready | 2-3 hours |
| Phase 4: External | After website live | 1 hour |
| Phase 5: Comms | After everything works | Ongoing |

---

## Rollback Plan

If something breaks:
1. Revert GitHub repo name (works for 30 days)
2. Keep old Docker image tags
3. Keep old PyPI package as alias

---

## Notes

- GitHub redirects old repo URL to new one automatically
- Docker images need to be republished under new name
- PyPI needs new package registration
- DNS changes can take 24-48 hours

---

*Created: 2026-02-18*
*Status: Ready to execute after DNS configuration*
