"""Tests for apple_notes.cli — mock NotesClient, verify JSON envelope."""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from apple_notes.cli import cli
from apple_notes.models import Folder, Note, SearchResult

MOCK_PATH = "apple_notes.cli.NotesClient"


def _invoke(*args):
    """Invoke CLI with --json flag and return parsed JSON output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", *args])
    assert result.exit_code == 0, f"CLI exited {result.exit_code}: {result.output}"
    return json.loads(result.output)


def _make_note(**overrides):
    defaults = dict(
        pk=1, title="Test Note", folder="Notes",
        modified_at="2026-01-01", created_at="2026-01-01",
        id="", snippet="", account="iCloud", uuid="",
        locked=False, pinned=False, checklist=False, content=None,
    )
    defaults.update(overrides)
    return Note(**defaults)


def _make_folder(**overrides):
    defaults = dict(pk=1, title="Notes", account="iCloud", note_count=5)
    defaults.update(overrides)
    return Folder(**defaults)


def _make_search_result(**overrides):
    defaults = dict(pk=1, title="Match", folder="Notes", score=0.85, snippet="found it", modified_at="2026-01-01")
    defaults.update(overrides)
    return SearchResult(**defaults)


class TestListCommand:
    @patch(MOCK_PATH)
    def test_list_returns_notes(self, MockClient):
        client = MockClient.return_value
        client.list_notes.return_value = [
            _make_note(pk=1, title="Note A"),
            _make_note(pk=2, title="Note B"),
        ]
        data = _invoke("list")
        assert data["status"] == "ok"
        assert len(data["data"]) == 2
        assert data["data"][0]["title"] == "Note A"
        assert data["data"][1]["title"] == "Note B"

    @patch(MOCK_PATH)
    def test_list_empty(self, MockClient):
        client = MockClient.return_value
        client.list_notes.return_value = []
        data = _invoke("list")
        assert data["status"] == "ok"
        assert data["data"] == []

    @patch(MOCK_PATH)
    def test_list_with_folder_filter(self, MockClient):
        client = MockClient.return_value
        client.list_notes.return_value = [_make_note(folder="Work")]
        data = _invoke("list", "--folder", "Work")
        client.list_notes.assert_called_once_with(folder="Work", limit=None)
        assert data["data"][0]["folder"] == "Work"

    @patch(MOCK_PATH)
    def test_list_with_limit(self, MockClient):
        client = MockClient.return_value
        client.list_notes.return_value = [_make_note()]
        _invoke("list", "--limit", "5")
        client.list_notes.assert_called_once_with(folder=None, limit=5)


class TestGetCommand:
    @patch(MOCK_PATH)
    def test_get_by_title(self, MockClient):
        client = MockClient.return_value
        note = _make_note(title="My Note", content="Hello world")
        client.get_note.return_value = note
        data = _invoke("get", "My Note")
        assert data["status"] == "ok"
        assert data["data"]["title"] == "My Note"
        assert data["data"]["content"] == "Hello world"
        client.get_note.assert_called_once_with(title="My Note", pk=None)

    @patch(MOCK_PATH)
    def test_get_by_id(self, MockClient):
        client = MockClient.return_value
        note = _make_note(pk=42, title="ID Note")
        client.get_note.return_value = note
        data = _invoke("get", "--by-id", "42")
        assert data["data"]["pk"] == 42
        client.get_note.assert_called_once_with(title=None, pk=42)

    @patch(MOCK_PATH)
    def test_get_not_found(self, MockClient):
        client = MockClient.return_value
        client.get_note.return_value = None
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "get", "Missing"])
        assert result.exit_code != 0
        err = json.loads(result.output)
        assert err["status"] == "error"
        assert err["error"]["code"] == "not_found"


class TestFoldersCommand:
    @patch(MOCK_PATH)
    def test_folders_returns_list(self, MockClient):
        client = MockClient.return_value
        client.list_folders.return_value = [
            _make_folder(title="Notes", note_count=10),
            _make_folder(pk=2, title="Archive", note_count=3),
        ]
        data = _invoke("folders")
        assert data["status"] == "ok"
        assert len(data["data"]) == 2
        assert data["data"][0]["title"] == "Notes"
        assert data["data"][0]["note_count"] == 10

    @patch(MOCK_PATH)
    def test_folders_empty(self, MockClient):
        client = MockClient.return_value
        client.list_folders.return_value = []
        data = _invoke("folders")
        assert data["data"] == []


class TestSearchCommand:
    @patch(MOCK_PATH)
    def test_search_returns_results(self, MockClient):
        client = MockClient.return_value
        client.search.return_value = [
            _make_search_result(title="Hit 1", score=0.9),
            _make_search_result(pk=2, title="Hit 2", score=0.7),
        ]
        data = _invoke("search", "test query")
        assert data["status"] == "ok"
        assert len(data["data"]) == 2
        assert data["data"][0]["score"] == 0.9
        client.search.assert_called_once_with("test query", mode="hybrid", limit=20)

    @patch(MOCK_PATH)
    def test_search_empty(self, MockClient):
        client = MockClient.return_value
        client.search.return_value = []
        data = _invoke("search", "nothing")
        assert data["data"] == []

    @patch(MOCK_PATH)
    def test_search_with_mode_and_limit(self, MockClient):
        client = MockClient.return_value
        client.search.return_value = []
        _invoke("search", "q", "--mode", "text", "--limit", "5")
        client.search.assert_called_once_with("q", mode="text", limit=5)
