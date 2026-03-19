"""Tests for apple_notes.models dataclasses."""

from dataclasses import asdict

from apple_notes.models import Folder, Note, SearchResult


class TestNote:
    def test_required_fields(self):
        note = Note(pk=1, title="Hello", folder="Notes", modified_at="2026-01-01")
        assert note.pk == 1
        assert note.title == "Hello"
        assert note.folder == "Notes"
        assert note.modified_at == "2026-01-01"

    def test_defaults(self):
        note = Note(pk=1, title="Hello", folder="Notes", modified_at="2026-01-01")
        assert note.created_at == ""
        assert note.id == ""
        assert note.snippet == ""
        assert note.account == ""
        assert note.uuid == ""
        assert note.locked is False
        assert note.pinned is False
        assert note.checklist is False
        assert note.content is None

    def test_all_fields(self):
        note = Note(
            pk=42,
            title="Full Note",
            folder="Work",
            modified_at="2026-03-19",
            created_at="2026-01-01",
            id="abc123",
            snippet="preview text",
            account="iCloud",
            uuid="uuid-1234",
            locked=True,
            pinned=True,
            checklist=True,
            content="# Hello\nWorld",
        )
        assert note.pk == 42
        assert note.locked is True
        assert note.content == "# Hello\nWorld"

    def test_asdict(self):
        note = Note(pk=1, title="Test", folder="F", modified_at="2026-01-01")
        d = asdict(note)
        assert isinstance(d, dict)
        assert d["pk"] == 1
        assert d["title"] == "Test"
        assert d["content"] is None
        assert "locked" in d


class TestFolder:
    def test_required_fields(self):
        folder = Folder(pk=1, title="Notes")
        assert folder.pk == 1
        assert folder.title == "Notes"

    def test_defaults(self):
        folder = Folder(pk=1, title="Notes")
        assert folder.account == ""
        assert folder.note_count == 0

    def test_all_fields(self):
        folder = Folder(pk=5, title="Work", account="iCloud", note_count=42)
        assert folder.note_count == 42
        assert folder.account == "iCloud"

    def test_asdict(self):
        folder = Folder(pk=1, title="Notes", account="iCloud", note_count=10)
        d = asdict(folder)
        assert d == {"pk": 1, "title": "Notes", "account": "iCloud", "note_count": 10}


class TestSearchResult:
    def test_required_fields(self):
        sr = SearchResult(pk=1, title="Match", folder="Notes")
        assert sr.pk == 1
        assert sr.title == "Match"
        assert sr.folder == "Notes"

    def test_defaults(self):
        sr = SearchResult(pk=1, title="Match", folder="Notes")
        assert sr.score == 0.0
        assert sr.snippet == ""
        assert sr.modified_at == ""

    def test_all_fields(self):
        sr = SearchResult(
            pk=7, title="Result", folder="Archive",
            score=0.95, snippet="...match...", modified_at="2026-03-19",
        )
        assert sr.score == 0.95
        assert sr.snippet == "...match..."

    def test_asdict(self):
        sr = SearchResult(pk=1, title="X", folder="F", score=0.5)
        d = asdict(sr)
        assert d["score"] == 0.5
        assert "modified_at" in d
