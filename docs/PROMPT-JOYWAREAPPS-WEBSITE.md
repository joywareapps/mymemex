# Prompt: Create Joyware Apps Organization Website

## Task

Create a professional organization website for Joyware Apps — a personal software development studio focused on creative, from-scratch projects.

---

## Organization Overview

### What is Joyware Apps?

**Nature:**
- Personal/hobby software development
- Creative outlet for building software from scratch
- Some projects involve family collaboration
- Not primarily commercial (but some projects may become commercial in future)

**Philosophy:**
- Build things that matter
- Learn and experiment
- Quality over quantity
- Open source when possible

**Current Projects:**
1. **MyMemex** — Your AI Document Memory
   - Self-hosted document intelligence
   - Open source (AGPL v3)
   - Website: mymemex.io
   - GitHub: github.com/joywareapps/mymemex

**Future Projects:**
- More tools to come
- Focus on developer productivity, personal organization, privacy-first tools

---

## Website Requirements

### URL
- **Production:** https://joywareapps.com/
- **SMB Location:** `smb://server-tiny-1/joywareapps-htdocs/joywareapps.com/`

### Style
- **Clean and professional** but with personality
- **Developer-friendly** vibe
- **Minimalist** — let the projects shine
- **Dark mode** preferred (slate/emerald theme like MyMemex)

### Tech Stack
- **Static HTML/CSS** (simplest option)
- OR **Astro** (if we want reusability/components)
- **Tailwind CSS** for styling (consistent with MyMemex site)
- **No framework dependencies** — fast loading

---

## Content Structure

### 1. Hero Section
```
Joyware Apps
Building software from scratch.

A personal studio for creative, useful, and privacy-first tools.
```

**Optional tagline ideas:**
- "Software crafted with care"
- "From scratch, with purpose"
- "Personal software, polished"
- "Building things that matter"

### 2. About Section

```
## About

Joyware Apps is a personal software development studio — my creative outlet 
for building tools from the ground up.

I create software in my free time, focusing on projects that solve real 
problems. Some are solo endeavors, others involve collaboration with family 
members who share the same passion for technology.

While not primarily commercial, some projects may evolve into products 
available for purchase. But the main goal remains: build useful things 
and learn along the way.

**Philosophy:**
- ✅ Build from scratch — understand every piece
- ✅ Quality over quantity — polish matters
- ✅ Privacy first — your data, your control
- ✅ Open source when possible — give back to community
```

### 3. Projects Section

```
## Projects

### MyMemex
Your AI Document Memory

Self-hosted document intelligence platform. Search your documents with 
natural language, auto-extract structured data, and chat with your archive.

- 🔒 Privacy-first (self-hosted)
- 🤖 Local AI with Ollama
- 💬 Works with Claude via MCP
- 📦 Free & open source (AGPL v3)

[Website] [GitHub] [Get Started]

---

*More projects coming soon...*
```

### 4. Contact/Links Section

```
## Connect

- **GitHub:** github.com/joywareapps
- **Email:** contact@joywareapps.com (or similar)
- **Twitter/X:** @joywareapps (if exists)

*Interested in collaboration or have questions? Reach out!*
```

### 5. Footer

```
© 2026 Joyware Apps
Built with care · Powered by coffee and curiosity
```

---

## Design Guidelines

### Colors (Consistent with MyMemex)
- **Background:** `slate-950` (#020617)
- **Text primary:** `slate-100` (#f1f5f9)
- **Text secondary:** `slate-400` (#94a3b8)
- **Accent primary:** `emerald-400` (#34d399)
- **Accent secondary:** `cyan-400` (#22d3ee)
- **Border:** `slate-800` (#1e293b)

### Typography
- **Headings:** Bold, clean sans-serif
- **Body:** Readable, good contrast
- **Code:** Monospace for technical terms

### Layout
- **Single page** (for now)
- **Sections:** Hero → About → Projects → Contact
- **Responsive:** Mobile-first
- **Max width:** 6xl (1152px)

### Visual Elements
- Subtle gradients (emerald to cyan)
- Card-based project display
- Hover effects on links
- Smooth scroll

---

## File Structure

### Option A: Simple HTML
```
joywareapps.com/
├── index.html      # Single page
├── style.css       # Custom styles
└── favicon.ico     # Icon
```

### Option B: Astro (Recommended)
```
joywareapps-website/
├── src/
│   ├── layouts/
│   │   └── Layout.astro
│   └── pages/
│       └── index.astro
├── public/
│   └── favicon.svg
├── astro.config.mjs
├── package.json
└── deploy.sh → smb://server-tiny-1/joywareapps-htdocs/joywareapps.com/
```

---

## Deployment

### SMB Location
```
/run/user/1000/gvfs/smb-share:server=server-tiny-1,share=joywareapps-htdocs/joywareapps.com/
```

### Deploy Script (if using Astro)
```bash
#!/bin/bash
# deploy-joywareapps.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMB_PATH="/run/user/1000/gvfs/smb-share:server=server-tiny-1,share=joywareapps-htdocs/joywareapps.com"

echo "🔨 Building Joyware Apps website..."
cd "$SCRIPT_DIR"
npm run build

echo "📦 Deploying..."
rsync -av --no-perms --no-owner --no-group --delete \
    "${SCRIPT_DIR}/dist/" "$SMB_PATH/"

echo "✅ Deployed to https://joywareapps.com/"
```

---

## Example HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Joyware Apps — Building software from scratch</title>
  <meta name="description" content="Personal software development studio focused on creative, privacy-first tools.">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Custom styles */
    .gradient-text {
      background: linear-gradient(135deg, #34d399 0%, #22d3ee 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  
  <!-- Navigation -->
  <nav class="fixed top-0 w-full bg-slate-950/80 backdrop-blur border-b border-slate-800 z-50">
    <div class="max-w-6xl mx-auto px-6 py-4 flex justify-between items-center">
      <a href="/" class="text-xl font-bold gradient-text">Joyware Apps</a>
      <div class="flex gap-6 text-sm">
        <a href="#about" class="text-slate-400 hover:text-white">About</a>
        <a href="#projects" class="text-slate-400 hover:text-white">Projects</a>
        <a href="#contact" class="text-slate-400 hover:text-white">Contact</a>
      </div>
    </div>
  </nav>

  <!-- Hero -->
  <section class="min-h-screen flex items-center justify-center px-6 pt-20">
    <div class="text-center max-w-3xl">
      <h1 class="text-5xl md:text-7xl font-bold mb-6">
        <span class="gradient-text">Joyware Apps</span>
      </h1>
      <p class="text-2xl text-slate-300 mb-4">Building software from scratch.</p>
      <p class="text-lg text-slate-400">
        A personal studio for creative, useful, and privacy-first tools.
      </p>
    </div>
  </section>

  <!-- About -->
  <section id="about" class="py-20 px-6 border-t border-slate-800">
    <div class="max-w-3xl mx-auto">
      <h2 class="text-3xl font-bold mb-8 text-emerald-400">About</h2>
      <div class="space-y-4 text-slate-300">
        <p>
          Joyware Apps is a personal software development studio — my creative outlet 
          for building tools from the ground up.
        </p>
        <p>
          I create software in my free time, focusing on projects that solve real 
          problems. Some are solo endeavors, others involve collaboration with family 
          members who share the same passion for technology.
        </p>
        <p>
          While not primarily commercial, some projects may evolve into products 
          available for purchase. But the main goal remains: build useful things 
          and learn along the way.
        </p>
      </div>
      
      <div class="mt-10 grid md:grid-cols-2 gap-4">
        <div class="p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
          <div class="text-2xl mb-2">🛠️</div>
          <h3 class="font-semibold mb-1">Build from scratch</h3>
          <p class="text-sm text-slate-400">Understand every piece</p>
        </div>
        <div class="p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
          <div class="text-2xl mb-2">✨</div>
          <h3 class="font-semibold mb-1">Quality over quantity</h3>
          <p class="text-sm text-slate-400">Polish matters</p>
        </div>
        <div class="p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
          <div class="text-2xl mb-2">🔒</div>
          <h3 class="font-semibold mb-1">Privacy first</h3>
          <p class="text-sm text-slate-400">Your data, your control</p>
        </div>
        <div class="p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
          <div class="text-2xl mb-2">❤️</div>
          <h3 class="font-semibold mb-1">Open source</h3>
          <p class="text-sm text-slate-400">Give back to community</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Projects -->
  <section id="projects" class="py-20 px-6 bg-slate-900/30">
    <div class="max-w-4xl mx-auto">
      <h2 class="text-3xl font-bold mb-8 text-emerald-400">Projects</h2>
      
      <!-- MyMemex -->
      <div class="bg-slate-900/50 border border-slate-800 rounded-xl p-8 mb-8">
        <div class="flex items-start justify-between mb-4">
          <div>
            <h3 class="text-2xl font-bold mb-2">MyMemex</h3>
            <p class="text-cyan-400">Your AI Document Memory</p>
          </div>
          <span class="px-3 py-1 bg-emerald-500/20 text-emerald-400 rounded-full text-sm">
            Active
          </span>
        </div>
        
        <p class="text-slate-300 mb-6">
          Self-hosted document intelligence platform. Search your documents with 
          natural language, auto-extract structured data, and chat with your archive 
          via AI assistants like Claude.
        </p>
        
        <div class="flex flex-wrap gap-2 mb-6">
          <span class="px-3 py-1 bg-slate-800 rounded-full text-sm text-slate-300">
            🔒 Privacy-first
          </span>
          <span class="px-3 py-1 bg-slate-800 rounded-full text-sm text-slate-300">
            🤖 Local AI (Ollama)
          </span>
          <span class="px-3 py-1 bg-slate-800 rounded-full text-sm text-slate-300">
            💬 MCP for Claude
          </span>
          <span class="px-3 py-1 bg-slate-800 rounded-full text-sm text-slate-300">
            📦 Open source (AGPL v3)
          </span>
        </div>
        
        <div class="flex gap-4">
          <a href="https://mymemex.io" class="px-4 py-2 bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950 rounded-lg font-semibold hover:from-emerald-400 hover:to-cyan-400 transition-all">
            Website →
          </a>
          <a href="https://github.com/joywareapps/mymemex" class="px-4 py-2 border border-slate-700 rounded-lg text-slate-300 hover:border-slate-600 hover:text-white transition-all">
            GitHub
          </a>
        </div>
      </div>
      
      <!-- Future projects placeholder -->
      <div class="text-center text-slate-500 py-8 border border-dashed border-slate-800 rounded-xl">
        <p class="text-lg mb-2">More projects coming soon...</p>
        <p class="text-sm">Stay tuned!</p>
      </div>
    </div>
  </section>

  <!-- Contact -->
  <section id="contact" class="py-20 px-6 border-t border-slate-800">
    <div class="max-w-3xl mx-auto text-center">
      <h2 class="text-3xl font-bold mb-8 text-emerald-400">Connect</h2>
      <p class="text-slate-400 mb-8">
        Interested in collaboration or have questions? Reach out!
      </p>
      <div class="flex justify-center gap-6">
        <a href="https://github.com/joywareapps" class="flex items-center gap-2 text-slate-300 hover:text-white transition-colors">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
          </svg>
          GitHub
        </a>
        <a href="mailto:contact@joywareapps.com" class="flex items-center gap-2 text-slate-300 hover:text-white transition-colors">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
          </svg>
          Email
        </a>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer class="py-8 px-6 border-t border-slate-800">
    <div class="max-w-6xl mx-auto text-center text-slate-500 text-sm">
      <p>© 2026 Joyware Apps</p>
      <p class="mt-2">Built with care · Powered by coffee and curiosity</p>
    </div>
  </footer>

</body>
</html>
```

---

## Customization Questions

1. **Email:** What email to use? (contact@joywareapps.com?)
2. **Social:** Twitter/X account? LinkedIn? Discord?
3. **Blog:** Want a blog section? (could use Astro's content collections)
4. **Analytics:** Any tracking? (Cloudflare Analytics, Plausible?)
5. **Projects to highlight:** Only MyMemex for now?

---

## Next Steps

1. **Create website folder:**
   ```bash
   mkdir -p ~/code/joywareapps-website
   ```

2. **Choose approach:**
   - **Simple:** Single HTML file (copy example above)
   - **Astro:** Full project with components

3. **Deploy:**
   ```bash
   # If HTML
   cp index.html "/run/user/1000/gvfs/smb-share:server=server-tiny-1,share=joywareapps-htdocs/joywareapps.com/"
   
   # If Astro
   npm run build
   rsync -av dist/ "/run/user/1000/gvfs/..."
   ```

---

*Prompt version: 1.0*
*Created: 2026-02-18*
