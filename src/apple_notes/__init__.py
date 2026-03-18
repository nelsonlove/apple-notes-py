"""Apple Notes — Python library, CLI, and MCP server for Apple Notes."""

from .client import NotesClient
from .models import Folder, Note, SearchResult

__all__ = ["NotesClient", "Note", "Folder", "SearchResult"]
