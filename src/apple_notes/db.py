"""SQLite read-only access to the Apple Notes database."""

import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = "~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"

# Apple CoreData epoch offset (Jan 1 2001 → Unix epoch)
_COREDATA_EPOCH = 978307200


class NotesDB:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(Path(db_path or DEFAULT_DB_PATH).expanduser())
        self._validate()

    def _validate(self):
        path = Path(self.db_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Notes database not found at: {self.db_path}\n"
                "Ensure you have granted Full Disk Access in System Settings."
            )
        mode = os.stat(self.db_path).st_mode
        if not (mode & stat.S_IRUSR):
            raise PermissionError(
                f"No read permission for: {self.db_path}\n"
                "Check Full Disk Access in System Settings."
            )

    def _query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            with closing(conn.cursor()) as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]

    def get_all_notes(self, folder: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """List notes with metadata (no content blob)."""
        sql = f"""
        SELECT
            'x-coredata://' || zmd.z_uuid || '/ICNote/p' || note.z_pk AS id,
            note.z_pk AS pk,
            note.ztitle1 AS title,
            folder.ztitle2 AS folder,
            datetime(note.zmodificationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS modifiedAt,
            note.zsnippet AS snippet,
            acc.zname AS account,
            note.zidentifier AS uuid,
            (note.zispasswordprotected = 1) AS locked,
            (note.zispinned = 1) AS pinned,
            (note.zhaschecklist = 1) AS checklist
        FROM ziccloudsyncingobject AS note
        INNER JOIN ziccloudsyncingobject AS folder ON note.zfolder = folder.z_pk
        LEFT JOIN ziccloudsyncingobject AS acc ON note.zaccount4 = acc.z_pk
        LEFT JOIN z_metadata AS zmd ON 1=1
        WHERE
            note.ztitle1 IS NOT NULL
            AND note.zmodificationdate1 IS NOT NULL
            AND note.z_pk IS NOT NULL
            AND note.zmarkedfordeletion != 1
            AND folder.zmarkedfordeletion != 1
            {"AND folder.ztitle2 = ?" if folder else ""}
        ORDER BY note.zmodificationdate1 DESC
        {"LIMIT ?" if limit else ""}
        """
        params: tuple = ()
        if folder:
            params += (folder,)
        if limit:
            params += (limit,)
        return self._query(sql, params)

    def get_note_by_title(self, title: str) -> dict[str, Any] | None:
        """Get a single note by exact title, including content blob."""
        sql = f"""
        SELECT
            'x-coredata://' || zmd.z_uuid || '/ICNote/p' || note.z_pk AS id,
            note.z_pk AS pk,
            note.ztitle1 AS title,
            folder.ztitle2 AS folder,
            datetime(note.zmodificationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS modifiedAt,
            datetime(note.zcreationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS createdAt,
            note.zsnippet AS snippet,
            notedata.zdata AS content,
            acc.zname AS account,
            note.zidentifier AS uuid,
            (note.zispasswordprotected = 1) AS locked,
            (note.zispinned = 1) AS pinned
        FROM ziccloudsyncingobject AS note
        INNER JOIN ziccloudsyncingobject AS folder ON note.zfolder = folder.z_pk
        LEFT JOIN ziccloudsyncingobject AS acc ON note.zaccount4 = acc.z_pk
        LEFT JOIN zicnotedata AS notedata ON note.znotedata = notedata.z_pk
        LEFT JOIN z_metadata AS zmd ON 1=1
        WHERE
            note.ztitle1 = ?
            AND note.zmarkedfordeletion != 1
            AND folder.zmarkedfordeletion != 1
        LIMIT 1
        """
        rows = self._query(sql, (title,))
        return rows[0] if rows else None

    def get_note_by_pk(self, pk: int) -> dict[str, Any] | None:
        """Get a single note by primary key, including content blob."""
        sql = f"""
        SELECT
            'x-coredata://' || zmd.z_uuid || '/ICNote/p' || note.z_pk AS id,
            note.z_pk AS pk,
            note.ztitle1 AS title,
            folder.ztitle2 AS folder,
            datetime(note.zmodificationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS modifiedAt,
            datetime(note.zcreationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS createdAt,
            note.zsnippet AS snippet,
            notedata.zdata AS content,
            acc.zname AS account,
            note.zidentifier AS uuid,
            (note.zispasswordprotected = 1) AS locked,
            (note.zispinned = 1) AS pinned
        FROM ziccloudsyncingobject AS note
        INNER JOIN ziccloudsyncingobject AS folder ON note.zfolder = folder.z_pk
        LEFT JOIN ziccloudsyncingobject AS acc ON note.zaccount4 = acc.z_pk
        LEFT JOIN zicnotedata AS notedata ON note.znotedata = notedata.z_pk
        LEFT JOIN z_metadata AS zmd ON 1=1
        WHERE
            note.z_pk = ?
            AND note.zmarkedfordeletion != 1
            AND folder.zmarkedfordeletion != 1
        LIMIT 1
        """
        rows = self._query(sql, (pk,))
        return rows[0] if rows else None

    def get_folders(self) -> list[dict[str, Any]]:
        """List all non-deleted folders."""
        sql = """
        SELECT DISTINCT
            folder.z_pk AS pk,
            folder.ztitle2 AS title,
            acc.zname AS account,
            COUNT(note.z_pk) AS note_count
        FROM ziccloudsyncingobject AS folder
        LEFT JOIN ziccloudsyncingobject AS note
            ON note.zfolder = folder.z_pk
            AND note.ztitle1 IS NOT NULL
            AND note.zmarkedfordeletion != 1
        LEFT JOIN ziccloudsyncingobject AS acc
            ON folder.zaccount3 = acc.z_pk
        WHERE
            folder.ztitle2 IS NOT NULL
            AND folder.zmarkedfordeletion != 1
            AND folder.zserverrecorddata IS NOT NULL
            AND COALESCE(folder.zfoldertype, 0) != 1
        GROUP BY folder.z_pk, folder.ztitle2, acc.zname
        ORDER BY folder.ztitle2
        """
        return self._query(sql)

    def search_notes(self, query_text: str) -> list[dict[str, Any]]:
        """Text search across title, snippet, and raw content blob."""
        sql = f"""
        SELECT
            'x-coredata://' || zmd.z_uuid || '/ICNote/p' || note.z_pk AS id,
            note.z_pk AS pk,
            note.ztitle1 AS title,
            folder.ztitle2 AS folder,
            datetime(note.zmodificationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS modifiedAt,
            note.zsnippet AS snippet,
            notedata.zdata AS content,
            acc.zname AS account,
            CASE
                WHEN note.ztitle1 LIKE ? THEN 3
                WHEN note.zsnippet LIKE ? THEN 2
                WHEN notedata.zdata LIKE ? THEN 1
                ELSE 0
            END AS relevance
        FROM ziccloudsyncingobject AS note
        INNER JOIN ziccloudsyncingobject AS folder ON note.zfolder = folder.z_pk
        LEFT JOIN ziccloudsyncingobject AS acc ON note.zaccount4 = acc.z_pk
        LEFT JOIN zicnotedata AS notedata ON note.znotedata = notedata.z_pk
        LEFT JOIN z_metadata AS zmd ON 1=1
        WHERE
            note.zmarkedfordeletion != 1
            AND folder.zmarkedfordeletion != 1
            AND (note.ztitle1 LIKE ? OR note.zsnippet LIKE ? OR notedata.zdata LIKE ?)
        ORDER BY relevance DESC, note.zmodificationdate1 DESC
        """
        pattern = f"%{query_text}%"
        return self._query(sql, (pattern,) * 6)

    def get_all_notes_with_content(self) -> list[dict[str, Any]]:
        """Bulk read of all notes with content blobs — used for indexing."""
        sql = f"""
        SELECT
            note.z_pk AS pk,
            note.ztitle1 AS title,
            folder.ztitle2 AS folder,
            datetime(note.zmodificationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS modifiedAt,
            datetime(note.zcreationdate1 + {_COREDATA_EPOCH}, 'unixepoch') AS createdAt,
            notedata.zdata AS content,
            (note.zispasswordprotected = 1) AS locked
        FROM ziccloudsyncingobject AS note
        INNER JOIN ziccloudsyncingobject AS folder ON note.zfolder = folder.z_pk
        LEFT JOIN zicnotedata AS notedata ON note.znotedata = notedata.z_pk
        WHERE
            note.ztitle1 IS NOT NULL
            AND note.zmodificationdate1 IS NOT NULL
            AND note.zmarkedfordeletion != 1
            AND folder.zmarkedfordeletion != 1
            AND note.zispasswordprotected != 1
        ORDER BY note.zmodificationdate1 DESC
        """
        return self._query(sql)
