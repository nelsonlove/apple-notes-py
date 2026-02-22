"""Click CLI for Apple Notes — thin layer over library modules."""

import json
import sys

import click

from .db import NotesDB
from .decode import decode_note_content


@click.group()
@click.option("--db-path", default=None, envvar="NOTES_DB_PATH",
              help="Path to NoteStore.sqlite (defaults to system location).")
@click.pass_context
def cli(ctx, db_path):
    """Read, create, and search Apple Notes from the command line."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path


def _get_db(ctx) -> NotesDB:
    return NotesDB(ctx.obj["db_path"])


# ── list ─────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--folder", default=None, help="Filter by folder name.")
@click.option("--limit", default=None, type=int, help="Max notes to return.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def list_notes(ctx, folder, limit, as_json):
    """List notes with metadata."""
    db = _get_db(ctx)
    notes = db.get_all_notes(folder=folder, limit=limit)

    if as_json:
        click.echo(json.dumps(notes, indent=2))
        return

    if not notes:
        click.echo("No notes found.")
        return

    for n in notes:
        pin = "*" if n["pinned"] else " "
        lock = "[locked]" if n["locked"] else ""
        click.echo(f" {pin} {n['title']:<50} {n['folder']:<20} {n['modifiedAt']} {lock}")


# ── get ──────────────────────────────────────────────────────────────────

@cli.command("get")
@click.argument("title", required=False)
@click.option("--by-id", type=int, default=None, help="Look up by primary key instead of title.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def get_note(ctx, title, by_id, fmt):
    """Get full note content by title or ID."""
    db = _get_db(ctx)

    if by_id is not None:
        note = db.get_note_by_pk(by_id)
    elif title:
        note = db.get_note_by_title(title)
    else:
        raise click.UsageError("Provide a TITLE or --by-id.")

    if not note:
        click.echo("Note not found.", err=True)
        sys.exit(1)

    text = decode_note_content(note.get("content"))
    note_out = {k: v for k, v in note.items() if k != "content"}
    note_out["content"] = text

    if fmt == "json":
        click.echo(json.dumps(note_out, indent=2))
    else:
        click.echo(f"Title:    {note_out['title']}")
        click.echo(f"Folder:   {note_out['folder']}")
        click.echo(f"Modified: {note_out['modifiedAt']}")
        click.echo(f"Created:  {note_out.get('createdAt', '')}")
        click.echo()
        click.echo(text)


# ── folders ──────────────────────────────────────────────────────────────

@cli.command("folders")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def list_folders(ctx, as_json):
    """List all folders."""
    db = _get_db(ctx)
    folders = db.get_folders()

    if as_json:
        click.echo(json.dumps(folders, indent=2))
        return

    if not folders:
        click.echo("No folders found.")
        return

    for f in folders:
        acct = f"({f['account']})" if f.get("account") else ""
        click.echo(f"  {f['title']:<30} {f['note_count']:>4} notes  {acct}")


# ── create ───────────────────────────────────────────────────────────────

@cli.command("create")
@click.argument("title")
@click.option("--body", default=None, help="Note body text.")
@click.option("--body-file", type=click.Path(exists=True), default=None,
              help="Read body from a file.")
@click.option("--html", "is_html", is_flag=True,
              help="Treat body as HTML (default is Markdown).")
@click.pass_context
def create_note_cmd(ctx, title, body, body_file, is_html):
    """Create a new note via JXA."""
    from .convert import markdown_to_html
    from .jxa import create_note

    if body_file:
        body = open(body_file).read()
    if not body:
        raise click.UsageError("Provide --body or --body-file.")

    if not is_html:
        body = markdown_to_html(body)

    create_note(title, body)
    click.echo(f"Created note: {title}")


# ── search ───────────────────────────────────────────────────────────────

@cli.command("search")
@click.argument("query")
@click.option("--mode", type=click.Choice(["text", "semantic", "hybrid"]),
              default="hybrid", help="Search mode.")
@click.option("--limit", default=20, type=int, help="Max results.")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON.")
@click.pass_context
def search_notes(ctx, query, mode, limit, as_json):
    """Search notes by text, semantic similarity, or hybrid."""
    db = _get_db(ctx)

    if mode == "text":
        results = db.search_notes(query)
        out = []
        for r in results[:limit]:
            out.append({"pk": r["pk"], "title": r["title"], "folder": r["folder"],
                         "snippet": r.get("snippet", ""), "relevance": r.get("relevance", 0)})
        if as_json:
            click.echo(json.dumps(out, indent=2))
        else:
            for r in out:
                click.echo(f"  [{r['relevance']}] {r['title']:<50} {r['folder']}")
        return

    # semantic or hybrid
    from .search import SearchIndex
    idx = SearchIndex()

    if mode == "semantic":
        results = idx.vector_search(query, limit=limit)
    else:
        results = idx.hybrid_search(query, limit=limit)

    if as_json:
        click.echo(json.dumps(results, indent=2))
    else:
        for r in results:
            score = f"{r.get('score', 0):.4f}" if "score" in r else ""
            click.echo(f"  {score:>8}  {r['title']}")


# ── index ────────────────────────────────────────────────────────────────

@cli.command("index")
@click.option("--force", is_flag=True, help="Drop and rebuild the index from scratch.")
@click.option("--status", "show_status", is_flag=True, help="Show index stats and exit.")
@click.pass_context
def build_index(ctx, force, show_status):
    """Build or update the semantic search index."""
    from .search import SearchIndex

    idx = SearchIndex()

    if show_status:
        info = idx.status()
        click.echo(json.dumps(info, indent=2))
        return

    db = _get_db(ctx)
    notes = db.get_all_notes_with_content()
    click.echo(f"Read {len(notes)} notes from database.")

    decoded = []
    for n in notes:
        text = decode_note_content(n.get("content"))
        if text:
            decoded.append({"pk": n["pk"], "title": n["title"], "folder": n["folder"],
                            "modifiedAt": n["modifiedAt"], "content": text})

    click.echo(f"Decoded {len(decoded)} notes with content.")
    count = idx.build(decoded, force=force)
    click.echo(f"Indexed {count} notes into LanceDB.")
