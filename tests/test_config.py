"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from mymemex.config import AppConfig, load_config


def test_default_config():
    """AppConfig should have sane defaults."""
    cfg = AppConfig()
    assert cfg.debug is False
    assert cfg.log_level == "INFO"
    assert cfg.server.host == "0.0.0.0"
    assert cfg.server.port == 8000
    assert cfg.llm.provider == "none"
    assert cfg.ocr.enabled is False


def test_config_from_dict():
    """AppConfig should accept nested dicts."""
    cfg = AppConfig(
        debug=True,
        watch={"debounce_seconds": 5.0},
        database={"path": "/tmp/test.db"},
    )
    assert cfg.debug is True
    assert cfg.watch.debounce_seconds == 5.0
    assert cfg.database.path == Path("/tmp/test.db")


def test_config_from_yaml(tmp_path):
    """Load config from YAML file."""
    yaml_content = """\
debug: true
log_level: DEBUG
watch:
  debounce_seconds: 3.0
database:
  path: /tmp/test.db
server:
  port: 9000
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    cfg = AppConfig.from_yaml(config_file)
    assert cfg.debug is True
    assert cfg.log_level == "DEBUG"
    assert cfg.watch.debounce_seconds == 3.0
    assert cfg.server.port == 9000


def test_config_from_missing_yaml(tmp_path):
    """Missing YAML should return defaults."""
    cfg = AppConfig.from_yaml(tmp_path / "nonexistent.yaml")
    assert cfg.debug is False
    assert cfg.server.port == 8000


def test_load_config_fallback():
    """load_config with no file should return defaults."""
    cfg = load_config()
    assert isinstance(cfg, AppConfig)


def test_database_path_expansion():
    """Database path should expand ~."""
    cfg = AppConfig(database={"path": "~/test.db"})
    assert "~" not in str(cfg.database.path)
    assert cfg.database.path.is_absolute()


def test_watch_default_patterns():
    """Watch config should have default file patterns."""
    cfg = AppConfig()
    assert "*.pdf" in cfg.watch.file_patterns
    assert "*.png" in cfg.watch.file_patterns


def test_watch_default_ignore():
    """Watch config should have Synology-specific ignore patterns."""
    cfg = AppConfig()
    assert "*/@eaDir/*" in cfg.watch.ignore_patterns
