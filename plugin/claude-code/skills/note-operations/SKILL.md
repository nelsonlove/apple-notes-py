---
name: note-operations
description: Use when the user asks to find, read, create, or search their Apple Notes. Also use when they mention "notes", "Apple Notes", or ask about note content, folders, or organization.
---

# Apple Notes Operations

## Available MCP Tools

### Reading
- **list_notes** — List notes with metadata. Params: `folder`, `limit`, `sort_by` (modified/created), `order` (asc/desc)
- **get_note** — Get full note content. Params: `title` (exact match) or `id` (primary key)
- **list_folders** — List all folders with note counts
- **search_notes** — Search by text, semantic similarity, or hybrid. Params: `query`, `mode` (text/semantic/hybrid), `limit`

### Writing
- **create_note** — Create a note with Markdown body. Params: `title`, `body`
- **move_note** — Move to a different folder. Params: `title`, `folder`
- **delete_note** — Move to Recently Deleted (30-day recovery). Params: `title`

### Export
- **export_note** — Return note as Markdown with YAML frontmatter. Params: `title` or `id`

## CLI Alternative

All operations are also available via the `apple-notes` CLI with `--json` for structured output:

```bash
apple-notes --json list --folder "Notes" --limit 10
apple-notes --json get "My Note"
apple-notes --json search "query" --mode hybrid
apple-notes create "Title" --body "# Content" --dry-run
```

## Usage Patterns

**Finding a note by topic:** Use `search_notes` with hybrid mode first. If semantic search is unavailable, it falls back to text automatically.

**Browsing a folder:** Use `list_notes` with the `folder` parameter. Use `limit` to avoid overwhelming output.

**Reading note content:** Use `get_note` — returns decoded plaintext content, not raw protobuf.

**Creating notes:** Pass Markdown in the `body` param — it's converted to HTML automatically. No need to write HTML.

**Bulk operations:** For working through many notes (triage, audit), use `list_notes` with sort/order to work through them systematically. Use the `/notes-triage` command for guided cleanup.
