"""Unified client for Apple Notes — the single entry point for all operations.

Reads go through SQLite (db.py), writes through JXA (jxa.py), and search
optionally through LanceDB (search.py). All methods return data classes,
never raw dicts.
"""

from __future__ import annotations

from .db import NotesDB
from .decode import decode_note_content, decode_note_to_markdown
from .models import Folder, Note, SearchResult


class NotesClient:
    """Apple Notes client.

    Args:
        db_path: Path to NoteStore.sqlite. Defaults to the system location.
    """

    def __init__(self, db_path: str | None = None):
        self._db = NotesDB(db_path)

    # ── Read operations (SQLite) ─────────────────────────────────────

    def list_notes(
        self,
        folder: str | None = None,
        limit: int | None = None,
        sort_by: str = "modified",
        order: str = "desc",
    ) -> list[Note]:
        """List notes with metadata (no content)."""
        rows = self._db.get_all_notes(
            folder=folder, limit=limit, sort_by=sort_by, order=order,
        )
        return [_row_to_note(r) for r in rows]

    def get_note(
        self,
        *,
        title: str | None = None,
        pk: int | None = None,
    ) -> Note | None:
        """Get a single note with decoded text content."""
        row = self._resolve_note(title=title, pk=pk)
        if row is None:
            return None
        note = _row_to_note(row)
        note.content = decode_note_content(row.get("content"))
        return note

    def list_folders(self) -> list[Folder]:
        """List all non-deleted folders."""
        rows = self._db.get_folders()
        return [
            Folder(
                pk=r["pk"],
                title=r["title"],
                account=r.get("account", "") or "",
                note_count=r.get("note_count", 0),
            )
            for r in rows
        ]

    def search(
        self,
        query: str,
        *,
        mode: str = "text",
        limit: int = 20,
    ) -> list[SearchResult]:
        """Search notes by text, semantic similarity, or hybrid.

        Falls back to text search if semantic search dependencies are
        unavailable.
        """
        if mode in ("semantic", "hybrid"):
            try:
                from .search import SearchIndex

                idx = SearchIndex()
                if mode == "semantic":
                    results = idx.vector_search(query, limit=limit)
                else:
                    results = idx.hybrid_search(query, limit=limit)
                return [
                    SearchResult(
                        pk=r["pk"],
                        title=r["title"],
                        folder=r.get("folder", ""),
                        score=r.get("score", 0.0),
                        modified_at=r.get("modifiedAt", ""),
                    )
                    for r in results
                ]
            except Exception:
                pass  # fall through to text search

        rows = self._db.search_notes(query)[:limit]
        return [
            SearchResult(
                pk=r["pk"],
                title=r["title"],
                folder=r.get("folder", ""),
                score=float(r.get("relevance", 0)),
                snippet=r.get("snippet", "") or "",
                modified_at=r.get("modifiedAt", ""),
            )
            for r in rows
        ]

    # ── Write operations (JXA) ───────────────────────────────────────

    def create_note(self, title: str, body_markdown: str) -> None:
        """Create a new note. Body is Markdown, converted to HTML automatically."""
        from .convert import markdown_to_html
        from .jxa import create_note as jxa_create

        html = markdown_to_html(body_markdown)
        jxa_create(title, html)

    def delete_note(self, title: str) -> None:
        """Move a note to Recently Deleted by title."""
        from .jxa import delete_note as jxa_delete

        jxa_delete(title)

    def move_note(self, title: str, folder: str) -> None:
        """Move a note to a different folder by title."""
        from .jxa import move_note as jxa_move

        jxa_move(title, folder)

    # ── Export ────────────────────────────────────────────────────────

    def export_note(
        self,
        *,
        title: str | None = None,
        pk: int | None = None,
    ) -> str | None:
        """Export a note as Markdown with YAML frontmatter.

        Returns None if the note is not found.
        """
        row = self._resolve_note(title=title, pk=pk)
        if row is None:
            return None

        md_body = decode_note_to_markdown(row.get("content"), skip_title=True)
        fm_lines = [
            "---",
            f'title: "{row.get("title", "")}"',
            f'folder: "{row.get("folder", "")}"',
        ]
        if row.get("createdAt"):
            fm_lines.append(f'created: "{row["createdAt"]}"')
        if row.get("modifiedAt"):
            fm_lines.append(f'modified: "{row["modifiedAt"]}"')
        fm_lines.append("---")

        frontmatter = "\n".join(fm_lines)
        return f"{frontmatter}\n\n{md_body}\n" if md_body else f"{frontmatter}\n"

    def export_notes(
        self,
        *,
        folder: str | None = None,
    ) -> list[tuple[Note, str]]:
        """Export multiple notes as (Note, markdown) pairs.

        Args:
            folder: Filter by folder name. If None, exports all notes.

        Returns:
            List of (Note metadata, markdown string with frontmatter) tuples.
            Locked and empty notes are skipped.
        """
        rows = self._db.get_all_notes_with_content()
        if folder:
            rows = [r for r in rows if r.get("folder") == folder]

        results = []
        for r in rows:
            if r.get("locked"):
                continue
            md_body = decode_note_to_markdown(r.get("content"), skip_title=True)
            if not md_body:
                continue
            note = _row_to_note(r)
            fm_lines = [
                "---",
                f'title: "{r.get("title", "")}"',
                f'folder: "{r.get("folder", "")}"',
            ]
            if r.get("createdAt"):
                fm_lines.append(f'created: "{r["createdAt"]}"')
            if r.get("modifiedAt"):
                fm_lines.append(f'modified: "{r["modifiedAt"]}"')
            fm_lines.append("---")
            frontmatter = "\n".join(fm_lines)
            results.append((note, f"{frontmatter}\n\n{md_body}\n"))
        return results

    # ── Search index management ──────────────────────────────────────

    def build_index(self, *, force: bool = False) -> int:
        """Build or rebuild the semantic search index.

        Returns the number of notes indexed.
        """
        from .search import SearchIndex

        idx = SearchIndex()
        notes = self._db.get_all_notes_with_content()

        decoded = []
        for n in notes:
            text = decode_note_content(n.get("content"))
            if text:
                decoded.append({
                    "pk": n["pk"],
                    "title": n["title"],
                    "folder": n["folder"],
                    "modifiedAt": n["modifiedAt"],
                    "content": text,
                })
        return idx.build(decoded, force=force)

    def index_status(self) -> dict:
        """Return semantic search index stats."""
        from .search import SearchIndex

        return SearchIndex().status()

    # ── Internal ─────────────────────────────────────────────────────

    def _resolve_note(
        self,
        *,
        title: str | None = None,
        pk: int | None = None,
    ) -> dict | None:
        """Fetch a raw note row by title or pk."""
        if pk is not None:
            return self._db.get_note_by_pk(pk)
        if title is not None:
            return self._db.get_note_by_title(title)
        raise ValueError("Provide title or pk")


def _row_to_note(row: dict) -> Note:
    """Convert a raw DB row dict to a Note data class."""
    return Note(
        pk=row["pk"],
        title=row["title"],
        folder=row.get("folder", ""),
        modified_at=row.get("modifiedAt", ""),
        created_at=row.get("createdAt", ""),
        id=row.get("id", ""),
        snippet=row.get("snippet", "") or "",
        account=row.get("account", "") or "",
        uuid=row.get("uuid", "") or "",
        locked=bool(row.get("locked", False)),
        pinned=bool(row.get("pinned", False)),
        checklist=bool(row.get("checklist", False)),
    )
