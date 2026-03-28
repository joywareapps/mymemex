"""Admin config view/edit endpoints."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/config")
async def get_config(request: Request):
    """Return current configuration as JSON."""
    config = request.app.state.config
    return config.model_dump()


@router.patch("/config")
async def update_config(updates: dict, request: Request):
    """Merge config updates and persist to config.yaml."""
    config = request.app.state.config

    # Find config file path
    config_path = None
    env_path = os.environ.get("MYMEMEX_CONFIG")
    if env_path:
        config_path = Path(env_path)
    else:
        for loc in [
            Path.cwd() / "mymemex.yaml",
            Path.cwd() / "config" / "config.yaml",
            Path.home() / ".config" / "mymemex" / "config.yaml",
        ]:
            if loc.exists():
                config_path = loc
                break

    if config_path is None:
        config_path = Path.cwd() / "mymemex.yaml"

    # Load existing YAML or start fresh
    if config_path.exists():
        with open(config_path) as f:
            existing = yaml.safe_load(f) or {}
    else:
        existing = {}

    # Deep merge
    _deep_merge(existing, updates)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(existing, f, default_flow_style=False)
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Config file is read-only: {config_path}")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

    return {"status": "saved", "path": str(config_path)}


@router.post("/restart")
async def restart_server():
    """Restart the server process."""
    import sys
    import threading

    def _restart():
        import time
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_restart, daemon=True).start()
    return {"status": "restarting"}


@router.post("/config/test-llm")
async def test_llm(data: dict, request: Request):
    """Test LLM connectivity using the provided (unsaved) config."""
    from ...config import LLMConfig
    from ...intelligence.llm_client import create_llm_client, NoneClient

    # Merge submitted llm section over current config
    current = request.app.state.config.llm.model_dump()
    current.update(data.get("llm", data))  # accept {llm: {...}} or flat llm dict
    try:
        llm_config = LLMConfig.model_validate(current)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid LLM config: {e}")

    if llm_config.provider in (None, "none"):
        raise HTTPException(status_code=422, detail="No LLM provider configured")

    try:
        client = create_llm_client(llm_config)
        if isinstance(client.inner if hasattr(client, "inner") else client, NoneClient):
            raise HTTPException(status_code=422, detail="No LLM provider configured")
        response = await client.generate("Reply with exactly one word: OK")
        return {"ok": True, "response": response.strip()}
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/config/validate")
async def validate_config(data: dict):
    """Validate a config dict without saving."""
    from ...config import AppConfig

    try:
        AppConfig.model_validate(data)
        return {"valid": True}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/config/ocr-languages")
async def get_ocr_languages():
    """Return Tesseract language codes installed in this environment."""
    try:
        import pytesseract
        langs = pytesseract.get_languages(config=None)
        # Exclude non-language entries (osd = orientation/script detection)
        langs = sorted(l for l in langs if l not in ("osd", "equ"))
        return {"languages": langs}
    except Exception as e:
        return {"languages": [], "error": str(e)}


def _deep_merge(base: dict, updates: dict) -> None:
    """Recursively merge updates into base dict in-place."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
