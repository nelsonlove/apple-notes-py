# apple-notes-py

Python library, CLI, and MCP server for Apple Notes on macOS.

## Features

- Read notes, folders, and content via direct SQLite access + protobuf decoding
- Create, delete, and move notes via JXA (JavaScript for Automation)
- Search with text, semantic (sentence-transformers), or hybrid (RRF fusion) modes
- Export notes to Markdown with YAML front-matter
- Import Markdown files as Apple Notes
- Optional semantic search index via LanceDB
- Structured JSON output with `--json`
- `--dry-run` on all write operations

## Installation

```bash
pip install apple-notes-py  # or: pipx install apple-notes-py
pip install 'apple-notes-py[search]'  # for semantic search
```

Requires macOS with Full Disk Access enabled for the terminal. Python 3.12+.

## CLI

```bash
apple-notes --help
apple-notes list
apple-notes list --folder "My Folder" --limit 10
apple-notes get "Some Note Title"
apple-notes get --by-id 1234
apple-notes folders
apple-notes create "My Note" --body "Hello **world**"
apple-notes create "My Note" --body-file draft.md
apple-notes delete "Old Note" --dry-run
apple-notes move "My Note" "Archive"
apple-notes search "query"
apple-notes search "query" --mode text
apple-notes search "query" --mode semantic --limit 5
apple-notes export "Some Note Title" -o note.md
apple-notes export --folder "My Folder" -o ./out/
apple-notes export --all -o ./out/
apple-notes import note.md
apple-notes import ./notes-dir/
apple-notes index
apple-notes index --force
apple-notes index --status
apple-notes --json list
```

## Python API

```python
from apple_notes.client import NotesClient

client = NotesClient()
notes = client.list_notes(folder="My Folder", limit=10)
note = client.get_note(title="Some Note Title")
folders = client.list_folders()
client.create_note("Title", "Markdown body")
client.delete_note("Old Note")
client.move_note("My Note", "Archive")
results = client.search("query", mode="hybrid", limit=20)
md = client.export_note(title="Some Note Title")
count = client.build_index(force=True)
```

## Development

```bash
git clone https://github.com/nelsonlove/apple-notes-py.git
cd apple-notes-py
uv sync --extra search --extra dev
uv run pytest
uv run apple-notes --help
```

## License

MIT
