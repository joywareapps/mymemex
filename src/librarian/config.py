"""Configuration system with hierarchical loading: defaults -> YAML -> env vars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatchConfig(BaseModel):
    """File watching configuration."""

    directories: list[str] = Field(default_factory=list)
    file_patterns: list[str] = Field(
        default=["*.pdf", "*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif", "*.bmp", "*.webp"]
    )
    ignore_patterns: list[str] = Field(default=["*/.*", "*/.Trash-*", "*/@eaDir/*", "*/#recycle/*"])
    debounce_seconds: float = 2.0
    max_file_size_mb: int = 100


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: Path = Field(default=Path("~/.local/share/librarian/librarian.db"))

    @model_validator(mode="after")
    def expand_path(self) -> DatabaseConfig:
        self.path = self.path.expanduser()
        return self


class ServerConfig(BaseModel):
    """API server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000


class OCRConfig(BaseModel):
    """OCR configuration (for M5, stub for now)."""

    enabled: bool = False
    language: str = "eng"
    dpi: int = 300
    confidence_threshold: float = 0.7


class LLMConfig(BaseModel):
    """LLM configuration (for M6+)."""

    provider: Literal["ollama", "openai", "anthropic", "none"] = "none"
    model: str = ""
    api_base: str = "http://localhost:11434"
    api_key: str | None = None  # For cloud providers (OpenAI, Anthropic)


class AIConfig(BaseModel):
    """AI feature configuration (M6+)."""

    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768
    embedding_batch_size: int = 8
    semantic_search_enabled: bool = False


class ClassificationConfig(BaseModel):
    """Document classification configuration."""

    enabled: bool = True
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tags: int = Field(default=5, ge=1, le=20)
    model: str = ""  # Override LLM model for classification
    prompt_template: str = ""  # Custom classification prompt


class ExtractionConfig(BaseModel):
    """Structured extraction configuration (M9.5)."""

    enabled: bool = True
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    prompt_template: str = ""  # Custom extraction prompt


class IngestionConfig(BaseModel):
    """Document ingestion configuration."""

    max_concurrent: int = Field(default=2, ge=1, le=10)


class MCPSecurityConfig(BaseModel):
    """MCP security boundaries."""

    allowed_parent_paths: list[str] = Field(default_factory=list)
    max_upload_size_mb: int = 5


class MCPConfig(BaseModel):
    """MCP server configuration."""

    enabled: bool = True
    security: MCPSecurityConfig = Field(default_factory=MCPSecurityConfig)


class AppConfig(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LIBRARIAN_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Core settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Component configs
    watch: WatchConfig = Field(default_factory=WatchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> AppConfig:
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.model_validate(data)


def load_config(config_path: Path | None = None) -> AppConfig:
    """
    Load configuration with priority:
    1. Explicit path (if provided)
    2. LIBRARIAN_CONFIG env var
    3. ./librarian.yaml
    4. ./config/config.yaml
    5. ~/.config/librarian/config.yaml
    6. Defaults only
    """
    if config_path:
        return AppConfig.from_yaml(config_path)

    env_path = os.environ.get("LIBRARIAN_CONFIG")
    if env_path:
        return AppConfig.from_yaml(Path(env_path))

    for loc in [
        Path.cwd() / "librarian.yaml",
        Path.cwd() / "config" / "config.yaml",
        Path.home() / ".config" / "librarian" / "config.yaml",
    ]:
        if loc.exists():
            return AppConfig.from_yaml(loc)

    return AppConfig()
