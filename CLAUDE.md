# apple-notes-py

Python library, CLI, and MCP server for Apple Notes on macOS.

## Architecture

```
apple_notes/
  client.py      ← NotesClient: unified API (the single entry point)
  models.py      ← Data classes: Note, Folder, SearchResult
  db.py          ← SQLite read access to NoteStore.sqlite
  jxa.py         ← JXA subprocess calls for write operations
  decode.py      ← Protobuf decoding of note content blobs
  search.py      ← LanceDB semantic search (optional dependency)
  convert.py     ← HTML/Markdown conversion
  cli.py         ← Click CLI (calls NotesClient)
  mcp_server.py  ← MCP server (calls NotesClient)
plugin/
  claude-code/   ← Claude Code plugin (calls CLI --json)
```

Dependency direction: `plugin → CLI → NotesClient → db/jxa/decode/search`

## Development

```bash
uv run pytest                          # run tests
uv run apple-notes --help              # run CLI
uv sync --extra search --extra dev     # full install into .venv
```

## CLI conventions

- `apple-notes --json <command>` for structured JSON output
- Envelope: `{"status": "ok", "data": ...}` or `{"status": "error", "error": {...}}`
- `--dry-run` on all write operations
- No interactive prompts in `--json` mode

## Key constraints

- `NotesClient` is the only public API — all external consumers use it
- Methods return data classes (`Note`, `Folder`, `SearchResult`), never dicts
- JXA writes are lazy-imported to avoid osascript overhead on read-only paths
- Search dependencies (`lancedb`, `sentence-transformers`) are optional
