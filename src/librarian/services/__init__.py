"""Service layer — shared backend for REST API and MCP tools."""

from .document import DocumentService
from .exceptions import NotFoundError, ServiceError, ServiceUnavailableError
from .ingest import IngestService
from .search import SearchService
from .stats import StatsService
from .tag import TagService

__all__ = [
    "DocumentService",
    "IngestService",
    "SearchService",
    "StatsService",
    "TagService",
    "ServiceError",
    "NotFoundError",
    "ServiceUnavailableError",
]
