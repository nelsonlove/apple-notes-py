---
name: note-operations
description: Use when the user asks to find, read, create, or search their Apple Notes. Also use when they mention "notes", "Apple Notes", or ask about note content, folders, or organization.
---

# Apple Notes Operations

Use the `apple-notes` CLI with `--json` for all operations. Run commands via the launcher:

```bash
${CLAUDE_PLUGIN_ROOT}/bin/run apple-notes --json <command>
```

## Commands

### Reading
```bash
apple-notes --json list                           # all notes
apple-notes --json list --folder "Notes" --limit 10
apple-notes --json get "My Note"                  # by title
apple-notes --json get --id 42                    # by primary key
apple-notes --json folders                        # list folders
apple-notes --json search "query"                 # text search
apple-notes --json search "query" --mode hybrid   # semantic search
```

### Writing
```bash
apple-notes create "Title" --body "# Markdown content" --dry-run
apple-notes move "Note Title" --folder "Destination"  --dry-run
apple-notes delete "Note Title" --dry-run
```

Always preview writes with `--dry-run` first.

### Export
```bash
apple-notes --json export "Note Title"            # Markdown + YAML frontmatter
apple-notes export --all --output ./exported/     # bulk export
```

## Output

All `--json` commands return: `{"status": "ok", "data": ...}` or `{"status": "error", "error": {...}}`

## Usage Patterns

**Finding a note:** Use `search` with hybrid mode first. Falls back to text if semantic unavailable.

**Browsing a folder:** Use `list --folder "Name" --limit 10` to avoid overwhelming output.

**Reading content:** `get` returns decoded plaintext content, not raw protobuf.

**Creating notes:** Pass Markdown in `--body` — it's converted to HTML automatically.

**Bulk operations:** Use `list` with `--sort-by modified --order desc` to work through notes systematically. Use `/notes-triage` for guided cleanup.
