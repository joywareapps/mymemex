# Prompt: Rebuild Website with MyMemex Branding

## Task

Update the Librarian website to rebrand as **MyMemex** and deploy to `mymemex.io`.

---

## Files to Update

### 1. Layout (src/layouts/Layout.astro)

**Changes needed:**

```diff
- const { title, description = "Librarian - Your Sovereign Document Intelligence Platform" } = Astro.props;
+ const { title, description = "MyMemex - Your AI Document Memory" } = Astro.props;
```

**Navigation logo** — Change book icon to brain/memory icon:

```astro
<!-- OLD: Book icon -->
<svg class="w-8 h-8 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
  <path d="M8 7h8"></path>
  <path d="M8 11h8"></path>
  <path d="M8 15h4"></path>
</svg>

<!-- NEW: Brain/memory icon (or use neuron/network icon) -->
<svg class="w-8 h-8 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="12" r="3"></circle>
  <path d="M12 1v4"></path>
  <path d="M12 19v4"></path>
  <path d="M1 12h4"></path>
  <path d="M19 12h4"></path>
  <path d="M4.22 4.22l2.83 2.83"></path>
  <path d="M16.95 16.95l2.83 2.83"></path>
  <path d="M4.22 19.78l2.83-2.83"></path>
  <path d="M16.95 7.05l2.83-2.83"></path>
</svg>
```

**Brand name in nav:**
```diff
- <span class="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">Librarian</span>
+ <span class="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">MyMemex</span>
```

**GitHub link:**
```diff
- <a href="https://github.com/joywareapps/librarian" ...>
+ <a href="https://github.com/joywareapps/mymemex" ...>
```

**Footer:**
```diff
- <span>Librarian</span>
+ <span>MyMemex</span>
```

---

### 2. Homepage (src/pages/index.astro)

**Hero section:**

```diff
- <h1>Librarian</h1>
- <p>Your Sovereign Document Intelligence Platform</p>
+ <h1>MyMemex</h1>
+ <p>Your AI Document Memory</p>
```

**Taglines to use:**
- "Remember everything, find anything"
- "Your personal AI document memory"
- "The memex, reborn for AI"

**Feature descriptions:**
- Replace "Librarian" with "MyMemex" throughout
- Update GitHub links to `joywareapps/mymemex`
- Update Docker image references to `ghcr.io/joywareapps/mymemex`

---

### 3. Features Page (src/pages/features.astro)

- Replace all "Librarian" → "MyMemex"
- Update code examples:
  ```diff
  - pip install librarian[all]
  + pip install mymemex[all]
  
  - librarian serve
  + mymemex serve
  
  - docker pull ghcr.io/joywareapps/librarian
  + docker pull ghcr.io/joywareapps/mymemex
  ```

---

### 4. Architecture Page (src/pages/architecture.astro)

- Replace "Librarian" → "MyMemex"
- Update diagram references if any
- Update GitHub links

---

### 5. Roadmap Page (src/pages/roadmap.astro)

- Replace "Librarian" → "MyMemex"
- Already updated for M10 complete
- Update GitHub links

---

### 6. Favicon (src/assets/favicon.svg)

Create new favicon with memory/brain theme:

```svg
<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="16" cy="16" r="14" stroke="#10b981" stroke-width="2"/>
  <circle cx="16" cy="16" r="4" fill="#10b981"/>
  <line x1="16" y1="2" x2="16" y2="8" stroke="#10b981" stroke-width="2"/>
  <line x1="16" y1="24" x2="16" y2="30" stroke="#10b981" stroke-width="2"/>
  <line x1="2" y1="16" x2="8" y2="16" stroke="#10b981" stroke-width="2"/>
  <line x1="24" y1="16" x2="30" y2="16" stroke="#10b981" stroke-width="2"/>
</svg>
```

---

### 7. Update Deploy Script

Create new `update-website-mymemex.sh`:

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMB_PATH="/run/user/1000/gvfs/smb-share:server=server-tiny-1,share=mymemex-htdocs/mymemex.io"

echo "🔨 Building MyMemex website..."
cd "$SCRIPT_DIR"
npm run build

echo "📦 Deploying to mymemex.io..."
rsync -av --no-perms --no-owner --no-group --delete \
    "${SCRIPT_DIR}/dist/" "$SMB_PATH/"

echo "✅ Website deployed to https://mymemex.io/"
```

---

## Brand Guidelines

### Colors (Keep existing)
- Primary: Emerald (`#10b981`, `emerald-400/500`)
- Secondary: Cyan (`cyan-400/500`)
- Background: Slate (`slate-950`, `slate-900`)

### Typography (Keep existing)
- Headings: Bold, gradient text
- Body: `text-slate-400`

### Icon Theme
- Brain/neuron/memory icons
- Network/connection imagery
- Suggests intelligence + retrieval

### Tone
- Personal: "Your" and "My" in messaging
- Technical but accessible
- Privacy-first, self-hosted emphasized

---

## Content Updates

### Hero Section
```
# MyMemex
Your AI Document Memory

Remember everything. Find anything.

- Self-hosted document intelligence
- AI-powered search & extraction  
- Works with Claude & AI assistants
- Your data stays private
```

### Quick Start (Updated)
```bash
# Docker
docker run -d -p 8000:8000 ghcr.io/joywareapps/mymemex

# pip
pip install mymemex[all]
mymemex serve

# MCP for Claude Desktop
# Add to claude_desktop_config.json
```

### GitHub Links
- Main: `https://github.com/joywareapps/mymemex`
- Issues: `https://github.com/joywareapps/mymemex/issues`
- Releases: `https://github.com/joywareapps/mymemex/releases`

---

## Deployment

After changes are made:

```bash
cd ~/code/librarian/website
npm run build
./update-website-mymemex.sh
```

---

## Checklist

- [ ] Layout.astro - branding, logo, links
- [ ] index.astro - hero, features, CTA
- [ ] features.astro - all references
- [ ] architecture.astro - all references
- [ ] roadmap.astro - all references
- [ ] favicon.svg - new icon
- [ ] Create update-website-mymemex.sh
- [ ] Build and test locally
- [ ] Deploy to mymemex.io
- [ ] Verify HTTPS works
- [ ] Test all pages
- [ ] Update GitHub repo description

---

*Created: 2026-02-18*
*Status: Ready for execution*
