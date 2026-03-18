"""Apple Notes MCP server — JSON-RPC stdio transport.

Wraps NotesClient over the Model Context Protocol, exposing tools for
listing, reading, searching, creating, exporting, deleting, and moving notes.
"""

import json
import signal
import sys
from dataclasses import asdict

from .client import NotesClient

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

_client = NotesClient()

TOOLS = [
    {
        "name": "list_notes",
        "description": "List notes from Apple Notes with metadata (no content). Supports filtering by folder and sorting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Filter by folder name"},
                "limit": {"type": "integer", "description": "Max notes to return"},
                "sort_by": {"type": "string", "enum": ["modified", "created"], "description": "Sort field (default: modified)"},
                "order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order (default: desc)"},
            },
        },
    },
    {
        "name": "get_note",
        "description": "Get a single note by title or ID, with decoded text content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "id": {"type": "integer", "description": "Note primary key (pk)"},
            },
        },
    },
    {
        "name": "list_folders",
        "description": "List all folders in Apple Notes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_note",
        "description": "Create a new note in Apple Notes. Body is markdown, converted to HTML automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "body": {"type": "string", "description": "Note body in markdown"},
            },
            "required": ["title", "body"],
        },
    },
    {
        "name": "search_notes",
        "description": "Search notes by text, semantic similarity, or hybrid. Falls back to text if semantic is unavailable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "mode": {"type": "string", "enum": ["text", "semantic", "hybrid"], "description": "Search mode (default: text)"},
                "limit": {"type": "integer", "description": "Max results (default: 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "export_note",
        "description": "Export a note as markdown with YAML frontmatter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "id": {"type": "integer", "description": "Note primary key (pk)"},
            },
        },
    },
    {
        "name": "delete_note",
        "description": "Delete a note from Apple Notes (moves to Recently Deleted).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "move_note",
        "description": "Move a note to a different folder in Apple Notes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Exact note title"},
                "folder": {"type": "string", "description": "Destination folder name"},
            },
            "required": ["title", "folder"],
        },
    },
]


def _send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def _handle_tool(tool: str, args: dict) -> str:
    if tool == "list_notes":
        notes = _client.list_notes(
            folder=args.get("folder"),
            limit=args.get("limit"),
            sort_by=args.get("sort_by", "modified"),
            order=args.get("order", "desc"),
        )
        return json.dumps([asdict(n) for n in notes], default=str)

    elif tool == "get_note":
        note = _client.get_note(title=args.get("title"), pk=args.get("id"))
        if note is None:
            raise ValueError("Note not found")
        return json.dumps(asdict(note), default=str)

    elif tool == "list_folders":
        folders = _client.list_folders()
        return json.dumps([asdict(f) for f in folders], default=str)

    elif tool == "create_note":
        _client.create_note(args["title"], args["body"])
        return f"Created note: {args['title']}"

    elif tool == "search_notes":
        results = _client.search(
            args["query"],
            mode=args.get("mode", "text"),
            limit=args.get("limit", 20),
        )
        return json.dumps([asdict(r) for r in results], default=str)

    elif tool == "export_note":
        md = _client.export_note(title=args.get("title"), pk=args.get("id"))
        if md is None:
            raise ValueError("Note not found")
        return md

    elif tool == "delete_note":
        _client.delete_note(args["title"])
        return f"Deleted note: {args['title']}"

    elif tool == "move_note":
        _client.move_note(args["title"], args["folder"])
        return f"Moved note '{args['title']}' to folder '{args['folder']}'"

    else:
        raise ValueError(f"Unknown tool: {tool}")


def _handle(msg):
    method = msg.get("method", "")
    msg_id = msg.get("id")

    if method == "initialize":
        _send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "apple-notes", "version": "1.0.0"},
            },
        })
    elif method == "notifications/initialized":
        pass  # no response needed
    elif method == "tools/list":
        _send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        })
    elif method == "tools/call":
        params = msg.get("params", {})
        tool = params.get("name")
        args = params.get("arguments", {})
        try:
            result_text = _handle_tool(tool, args)
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            })
        except Exception as e:
            _send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "isError": True,
                },
            })


def main():
    """Run the MCP server on stdin/stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            _handle(json.loads(line))
        except Exception:
            pass


if __name__ == "__main__":
    main()
