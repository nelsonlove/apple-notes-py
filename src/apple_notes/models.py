"""Data classes for Apple Notes objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Note:
    """A single Apple Note."""

    pk: int
    title: str
    folder: str
    modified_at: str
    created_at: str = ""
    id: str = ""
    snippet: str = ""
    account: str = ""
    uuid: str = ""
    locked: bool = False
    pinned: bool = False
    checklist: bool = False
    content: str | None = None


@dataclass
class Folder:
    """An Apple Notes folder."""

    pk: int
    title: str
    account: str = ""
    note_count: int = 0


@dataclass
class SearchResult:
    """A note returned from a search query."""

    pk: int
    title: str
    folder: str
    score: float = 0.0
    snippet: str = ""
    modified_at: str = ""
