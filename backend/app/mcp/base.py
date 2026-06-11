"""Abstract base class for all Model Context Protocol (MCP) document sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class MCPDocument:
    """A document fetched from an MCP source."""
    title: str
    content: str
    source: str         # e.g., "google_drive", "notion", "local"
    document_type: str  # e.g., "policy", "regulation"
    metadata: dict


class MCPSource(ABC):
    """
    Abstract base for all MCP document sources.
    Each integration implements fetch_documents() to return
    a list of MCPDocument instances that will be ingested into ChromaDB.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier string for this source (used in metadata)."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """
        Return True if the necessary credentials/config are available.
        Prevents runtime failures when a source is not configured.
        """
        ...

    @abstractmethod
    def fetch_documents(self) -> list[MCPDocument]:
        """
        Retrieve all available documents from this source.
        Returns an empty list if the source is not configured or unreachable.
        """
        ...
