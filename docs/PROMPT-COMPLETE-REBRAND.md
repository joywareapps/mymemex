# Prompt: Complete MyMemex Rebrand - CLI, Module, and Docs

## Task

Complete the rebranding of MyMemex by updating:
1. CLI command name (`librarian` → `mymemex`)
2. Python module name (`src/librarian/` → `src/mymemex/`)
3. All remaining documentation

---

## Context

The project has been rebranded from "Librarian" to "MyMemex". External-facing parts (GitHub repo, README, website, Docker) are already updated. Now we need to update internal code and documentation.

**Project location:** `/home/gorano/code/mymemex`

**Completed rebrand:**
- ✅ GitHub repo: `joywareapps/mymemex`
- ✅ Website: mymemex.io
- ✅ README.md
- ✅ pyproject.toml (name = "mymemex")
- ✅ docker-compose.yml

**Still needs updating:**
- ❌ CLI command (`librarian serve`, `librarian mcp serve`, etc.)
- ❌ Module directory (`src/librarian/`)
- ❌ Documentation files

---

## Part 1: CLI Command Rename

### Files to Update

**Primary:**
- `src/librarian/__main__.py` — Main CLI entry point
- `src/librarian/cli/` — Any CLI-related modules

**Search for:**
```bash
grep -r "librarian" src/librarian/__main__.py
grep -r "librarian" src/librarian/cli/
```

**Changes needed:**
1. Update CLI app name from `"librarian"` to `"mymemex"`
2. Update help text that mentions "librarian"
3. Update any example commands in docstrings

**Example in `__main__.py`:**
```python
# OLD
app = typer.Typer(name="librarian", help="Sovereign document intelligence")

# NEW
app = typer.Typer(name="mymemex", help="Your AI Document Memory")
```

---

## Part 2: Module Rename

### Move Directory

```bash
# Move the module directory
mv src/librarian src/mymemex

# Remove old __pycache__
find src/mymemex -type d -name __pycache__ -exec rm -rf {} +
```

### Update All Imports

**Files to update:**
- All Python files in `src/mymemex/`
- All test files in `tests/`
- `pyproject.toml` (package discovery)

**Search pattern:**
```python
# Find all imports to update
grep -r "from librarian" src/ tests/
grep -r "import librarian" src/ tests/
```

**Replace pattern:**
```python
# OLD
from librarian.storage.database import Database
from librarian.processing.pipeline import Pipeline
import librarian.config

# NEW
from mymemex.storage.database import Database
from mymemex.processing.pipeline import Pipeline
import mymemex.config
```

**Update pyproject.toml:**
```toml
# OLD
[tool.setuptools.packages.find]
where = ["src"]

# NEW (if needed - specify explicitly)
[tool.setuptools.packages.find]
where = ["src"]
namespaces = false
```

### Run Tests After Rename

```bash
# After changes, verify everything works
cd /home/gorano/code/mymemex
pytest tests/ -v

# Try the CLI
python -m mymemex --help
```

---

## Part 3: Documentation Updates

### Files to Update

**Priority 1 - Main docs:**
- `docs/INSTALLATION.md`
- `docs/MILESTONES.md`
- `PROJECT_STATUS.md`
- `TODO.md`

**Priority 2 - Other docs:**
- `docs/DEPLOYMENT.md`
- `docs/DEPLOYMENT-CHECKLIST.md`
- `config/config.example.yaml` (comments)
- Any `.md` files in `docs/`

### Search and Replace Patterns

**Search for:**
```bash
grep -r "librarian" docs/
grep -r "Librarian" docs/
grep -r "LIBRARIAN" docs/
grep -r "joywareapps/librarian" docs/
```

**Replace:**
1. `librarian` → `mymemex` (in commands, filenames, code)
2. `Librarian` → `MyMemex` (in prose, titles)
3. `LIBRARIAN` → `MYMEMEX` (in env vars, if any)
4. `joywareapps/librarian` → `joywareapps/mymemex` (GitHub links)
5. `ghcr.io/joywareapps/librarian` → `ghcr.io/joywareapps/mymemex` (Docker)

### Specific File Updates

#### INSTALLATION.md
- Update all `pip install librarian` → `pip install mymemex`
- Update all `librarian serve` → `mymemex serve`
- Update Docker image references
- Update GitHub clone URL

#### MILESTONES.md
- Update project name references
- Keep content the same, just branding

#### PROJECT_STATUS.md
- Update title to "MyMemex Project Status"
- Update any commands/URLs

#### config.example.yaml
- Update comments that mention "librarian"
- Update env var names if using `LIBRARIAN_*`

---

## Part 4: Environment Variables

### Check for env var references

```bash
grep -r "LIBRARIAN_" src/ config/ docs/
```

**If found, replace:**
- `LIBRARIAN_CONFIG` → `MYMEMEX_CONFIG`
- `LIBRARIAN_DATA_DIR` → `MYMEMEX_DATA_DIR`
- etc.

**Files to update:**
- `src/mymemex/config/settings.py`
- `config/config.example.yaml`
- `docker-compose.yml`
- `.env.example`

---

## Part 5: Config Files

### Update config paths

**Current:**
```yaml
# ~/.config/librarian/config.yaml
# ~/.local/share/librarian/
```

**Update to:**
```yaml
# ~/.config/mymemex/config.yaml
# ~/.local/share/mymemex/
```

**Files to update:**
- `src/mymemex/config/settings.py` — Default paths
- `docs/INSTALLATION.md` — Path references
- `config/config.example.yaml` — Comments

---

## Verification Steps

After all changes:

### 1. Run Tests
```bash
cd /home/gorano/code/mymemex
pytest tests/ -v
# Should see: 141 tests passing
```

### 2. Test CLI
```bash
# Should work
python -m mymemex --help
python -m mymemex serve --help
python -m mymemex mcp serve --help
```

### 3. Check Imports
```bash
# Should find nothing
grep -r "from librarian" src/
grep -r "import librarian" src/
```

### 4. Check Documentation
```bash
# Should find nothing
grep -r "librarian" docs/
grep -r "Librarian" docs/ | grep -v "MyMemex"
```

---

## Execution Order

1. **Module rename** (move directory, update imports)
2. **CLI command** (update `__main__.py`)
3. **Environment variables** (if any)
4. **Documentation** (all `.md` files)
5. **Config files** (paths, comments)
6. **Run tests** (verify nothing broke)
7. **Commit changes**

---

## Commit Message Template

```
refactor: Complete MyMemex rebrand - CLI, module, docs

Breaking changes:
- Python module: src/librarian/ → src/mymemex/
- CLI command: librarian → mymemex
- All imports updated throughout codebase
- All documentation updated

Users will need to:
- Update imports: from librarian → from mymemex
- Update CLI: mymemex serve (was librarian serve)
- Update config paths: ~/.config/mymemex/ (was ~/.config/librarian/)

Tests: All 141 tests passing
```

---

## Notes

- **Breaking change:** This is a hard break, no aliases
- **Config migration:** Users may need to move `~/.config/librarian/` to `~/.config/mymemex/`
- **Docker:** Already updated in previous commit
- **PyPI:** Not published yet, so no package name conflict

---

## Files Summary

### Will Change Location
- `src/librarian/` → `src/mymemex/`

### Will Be Modified
- `src/mymemex/__main__.py`
- `src/mymemex/**/__init__.py` (all submodules)
- `src/mymemex/**/*.py` (all Python files)
- `tests/**/*.py` (all test files)
- `docs/INSTALLATION.md`
- `docs/MILESTONES.md`
- `docs/DEPLOYMENT.md`
- `PROJECT_STATUS.md`
- `TODO.md`
- `config/config.example.yaml`
- `pyproject.toml` (if package discovery needs update)

### No Changes Needed
- `README.md` ✅ (already updated)
- `website/` ✅ (already updated)
- `docker-compose.yml` ✅ (already updated)
- `.github/workflows/docker.yml` ✅ (already updated)

---

*Prompt version: 1.0*
*Created: 2026-02-18*
