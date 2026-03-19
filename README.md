# apple-notes

CLI and library for reading, creating, and searching Apple Notes.

- **Read** notes, folders, and content via direct SQLite access + protobuf decoding
- **Create** notes via JXA (JavaScript for Automation)
- **Export** notes to Markdown files with YAML front-matter
- **Import** Markdown files into Apple Notes
- **Search** with text, semantic (sentence-transformers), or hybrid (RRF fusion) modes

Requires macOS with Full Disk Access enabled for the terminal.

## Install

```bash
uv venv && uv pip install -e .
```

## Usage

```bash
# List notes
notes list
notes list --folder "73.06 LLM outputs" --limit 10 --json

# Get full note content
notes get "Some Note Title"
notes get --by-id 1234 --format json

# List folders
notes folders
notes folders --json

# Create a note (body is Markdown by default, converted to HTML)
notes create "My Note" --body "Hello **world**"
notes create "My Note" --body-file draft.md
notes create "My Note" --body "<h1>Hi</h1>" --html

# Export notes to Markdown
notes export "Some Note Title"                  # print to stdout
notes export "Some Note Title" -o note.md       # write to file
notes export --by-id 1234 -o note.md            # by primary key
notes export --folder "My Folder" -o ./out/     # all notes in folder
notes export --all -o ./out/                    # every note

# Import Markdown files as notes
notes import note.md                            # single file
notes import ./notes-dir/                       # all .md files in directory

# Build semantic search index
notes index
notes index --force   # rebuild from scratch
notes index --status  # show index stats

# Search
notes search "query"                    # hybrid (vector + FTS, RRF fusion)
notes search "query" --mode text        # SQL LIKE search
notes search "query" --mode semantic    # pure vector similarity
notes search "query" --limit 5 --json
```

## Architecture

Library-first design — all modules return dicts/lists, CLI is a thin formatting layer.

| Module       | Purpose                                            |
|--------------|----------------------------------------------------|
| `db.py`      | SQLite read-only access to NoteStore.sqlite        |
| `decode.py`  | gzip + protobuf content decoding                   |
| `jxa.py`     | JXA subprocess calls for note creation             |
| `search.py`  | LanceDB + sentence-transformers + FTS + RRF fusion |
| `convert.py` | HTML/Markdown conversion                           |
| `cli.py`     | Click CLI                                          |

## Dependencies

Python 3.12+. Key libraries: click, protobuf, lancedb, sentence-transformers, markdownify, markdown.
