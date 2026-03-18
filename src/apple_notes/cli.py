"""Click CLI for Apple Notes — thin layer over NotesClient."""

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

import click

from .client import NotesClient


@click.group()
@click.option("--db-path", default=None, envvar="NOTES_DB_PATH",
              help="Path to NoteStore.sqlite (defaults to system location).")
@click.option("--json", "as_json", is_flag=True, envvar="APPLE_NOTES_OUTPUT",
              help="Output as JSON (structured envelope).")
@click.pass_context
def cli(ctx, db_path, as_json):
    """Read, create, and search Apple Notes from the command line."""
    ctx.ensure_object(dict)
    ctx.obj["client"] = NotesClient(db_path)
    ctx.obj["json"] = as_json


def _client(ctx) -> NotesClient:
    return ctx.obj["client"]


def _output_json(ctx) -> bool:
    return ctx.obj["json"]


def _emit(ctx, data):
    """Emit structured JSON envelope: {"status": "ok", "data": ...}."""
    click.echo(json.dumps({"status": "ok", "data": data}, indent=2, default=str))


def _emit_error(code: str, message: str, suggestion: str = ""):
    """Emit structured JSON error envelope."""
    err = {"code": code, "message": message}
    if suggestion:
        err["suggestion"] = suggestion
    click.echo(json.dumps({"status": "error", "error": err}, indent=2), err=True)
    sys.exit(1)


# ── list ─────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--folder", default=None, help="Filter by folder name.")
@click.option("--limit", default=None, type=int, help="Max notes to return.")
@click.pass_context
def list_notes(ctx, folder, limit):
    """List notes with metadata."""
    client = _client(ctx)
    notes = client.list_notes(folder=folder, limit=limit)

    if _output_json(ctx):
        _emit(ctx, [asdict(n) for n in notes])
        return

    if not notes:
        click.echo("No notes found.")
        return

    for n in notes:
        pin = "*" if n.pinned else " "
        lock = "[locked]" if n.locked else ""
        click.echo(f" {pin} {n.title:<50} {n.folder:<20} {n.modified_at} {lock}")


# ── get ──────────────────────────────────────────────────────────────────

@cli.command("get")
@click.argument("title", required=False)
@click.option("--by-id", type=int, default=None, help="Look up by primary key instead of title.")
@click.pass_context
def get_note(ctx, title, by_id):
    """Get full note content by title or ID."""
    client = _client(ctx)

    if not title and by_id is None:
        raise click.UsageError("Provide a TITLE or --by-id.")

    note = client.get_note(title=title, pk=by_id)
    if not note:
        if _output_json(ctx):
            _emit_error("not_found", "Note not found")
        else:
            click.echo("Note not found.", err=True)
        sys.exit(1)

    if _output_json(ctx):
        _emit(ctx, asdict(note))
        return

    click.echo(f"Title:    {note.title}")
    click.echo(f"Folder:   {note.folder}")
    click.echo(f"Modified: {note.modified_at}")
    click.echo(f"Created:  {note.created_at}")
    click.echo()
    click.echo(note.content or "")


# ── folders ──────────────────────────────────────────────────────────────

@cli.command("folders")
@click.pass_context
def list_folders(ctx):
    """List all folders."""
    client = _client(ctx)
    folders = client.list_folders()

    if _output_json(ctx):
        _emit(ctx, [asdict(f) for f in folders])
        return

    if not folders:
        click.echo("No folders found.")
        return

    for f in folders:
        acct = f"({f.account})" if f.account else ""
        click.echo(f"  {f.title:<30} {f.note_count:>4} notes  {acct}")


# ── create ───────────────────────────────────────────────────────────────

@cli.command("create")
@click.argument("title")
@click.option("--body", default=None, help="Note body text (Markdown).")
@click.option("--body-file", type=click.Path(exists=True), default=None,
              help="Read body from a file.")
@click.option("--dry-run", is_flag=True, help="Show what would be created without doing it.")
@click.pass_context
def create_note_cmd(ctx, title, body, body_file, dry_run):
    """Create a new note (body is Markdown)."""
    if body_file:
        body = Path(body_file).read_text(encoding="utf-8")
    if not body:
        raise click.UsageError("Provide --body or --body-file.")

    if dry_run:
        if _output_json(ctx):
            _emit(ctx, {"action": "create", "title": title, "body_length": len(body)})
        else:
            click.echo(f"Would create note: {title} ({len(body)} chars)")
        return

    client = _client(ctx)
    client.create_note(title, body)

    if _output_json(ctx):
        _emit(ctx, {"created": title})
    else:
        click.echo(f"Created note: {title}")


# ── delete ───────────────────────────────────────────────────────────────

@cli.command("delete")
@click.argument("title")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without doing it.")
@click.pass_context
def delete_note_cmd(ctx, title, dry_run):
    """Move a note to Recently Deleted."""
    if dry_run:
        if _output_json(ctx):
            _emit(ctx, {"action": "delete", "title": title})
        else:
            click.echo(f"Would delete note: {title}")
        return

    client = _client(ctx)
    client.delete_note(title)

    if _output_json(ctx):
        _emit(ctx, {"deleted": title})
    else:
        click.echo(f"Deleted note: {title}")


# ── move ─────────────────────────────────────────────────────────────────

@cli.command("move")
@click.argument("title")
@click.argument("folder")
@click.option("--dry-run", is_flag=True, help="Show what would be moved without doing it.")
@click.pass_context
def move_note_cmd(ctx, title, folder, dry_run):
    """Move a note to a different folder."""
    if dry_run:
        if _output_json(ctx):
            _emit(ctx, {"action": "move", "title": title, "folder": folder})
        else:
            click.echo(f"Would move '{title}' to '{folder}'")
        return

    client = _client(ctx)
    client.move_note(title, folder)

    if _output_json(ctx):
        _emit(ctx, {"moved": title, "folder": folder})
    else:
        click.echo(f"Moved '{title}' to '{folder}'")


# ── search ───────────────────────────────────────────────────────────────

@cli.command("search")
@click.argument("query")
@click.option("--mode", type=click.Choice(["text", "semantic", "hybrid"]),
              default="hybrid", help="Search mode.")
@click.option("--limit", default=20, type=int, help="Max results.")
@click.pass_context
def search_notes(ctx, query, mode, limit):
    """Search notes by text, semantic similarity, or hybrid."""
    client = _client(ctx)
    results = client.search(query, mode=mode, limit=limit)

    if _output_json(ctx):
        _emit(ctx, [asdict(r) for r in results])
        return

    if not results:
        click.echo("No results found.")
        return

    for r in results:
        score = f"{r.score:.4f}" if r.score else ""
        click.echo(f"  {score:>8}  {r.title:<50} {r.folder}")


# ── index ────────────────────────────────────────────────────────────────

@cli.command("index")
@click.option("--force", is_flag=True, help="Drop and rebuild the index from scratch.")
@click.option("--status", "show_status", is_flag=True, help="Show index stats and exit.")
@click.pass_context
def build_index(ctx, force, show_status):
    """Build or update the semantic search index."""
    client = _client(ctx)

    if show_status:
        info = client.index_status()
        if _output_json(ctx):
            _emit(ctx, info)
        else:
            click.echo(json.dumps(info, indent=2))
        return

    count = client.build_index(force=force)
    if _output_json(ctx):
        _emit(ctx, {"indexed": count})
    else:
        click.echo(f"Indexed {count} notes into LanceDB.")


# ── export ──────────────────────────────────────────────────────────────

@cli.command("export")
@click.argument("title", required=False)
@click.option("--by-id", type=int, default=None, help="Export by primary key.")
@click.option("--folder", default=None, help="Export all notes in a folder.")
@click.option("--all", "export_all", is_flag=True, help="Export every note.")
@click.option("-o", "--output", default=None,
              help="Output file or directory. Omit to print to stdout (single note).")
@click.pass_context
def export_notes(ctx, title, by_id, folder, export_all, output):
    """Export notes as Markdown files with YAML front-matter."""
    client = _client(ctx)

    # ── bulk export (folder or all) ─────────────────────────────────
    if folder or export_all:
        if not output:
            raise click.UsageError("Provide -o/--output directory for bulk export.")
        out_dir = Path(output)
        out_dir.mkdir(parents=True, exist_ok=True)

        exported = client.export_notes(folder=folder)
        if not exported:
            click.echo("No notes found.", err=True)
            sys.exit(1)

        count = 0
        for note, md in exported:
            stem = _sanitize_filename(note.title)
            path = _unique_path(out_dir, stem, ".md")
            path.write_text(md, encoding="utf-8")
            count += 1

        if _output_json(ctx):
            _emit(ctx, {"exported": count, "directory": str(out_dir)})
        else:
            click.echo(f"Exported {count} notes to {out_dir}/")
        return

    # ── single note export ──────────────────────────────────────────
    if not title and by_id is None:
        raise click.UsageError("Provide a TITLE, --by-id, --folder, or --all.")

    md = client.export_note(title=title, pk=by_id)
    if md is None:
        click.echo("Note not found.", err=True)
        sys.exit(1)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        if _output_json(ctx):
            _emit(ctx, {"exported": 1, "file": output})
        else:
            click.echo(f"Exported to {output}")
    else:
        click.echo(md)


# ── import ──────────────────────────────────────────────────────────────

@cli.command("import")
@click.argument("path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show what would be imported without doing it.")
@click.pass_context
def import_notes(ctx, path, dry_run):
    """Import Markdown files as Apple Notes."""
    client = _client(ctx)
    target = Path(path)

    if target.is_dir():
        files = sorted(target.glob("*.md"))
        if not files:
            click.echo("No .md files found in directory.", err=True)
            sys.exit(1)
        for f in files:
            _import_one(f, client, dry_run, ctx)
    elif target.is_file():
        _import_one(target, client, dry_run, ctx)
    else:
        raise click.UsageError(f"Not a file or directory: {path}")


# ── helpers ─────────────────────────────────────────────────────────────

def _sanitize_filename(title: str) -> str:
    """Turn a note title into a safe filename (no extension)."""
    name = re.sub(r'[/:*?"<>|\x00]', '_', title)
    return name.strip('. ')[:200] or 'untitled'


def _unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """Return a path in *directory* that doesn't collide with existing files."""
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML front-matter from body. Returns (metadata dict, body)."""
    if not text.startswith('---'):
        return {}, text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta, parts[2].strip()


def _import_one(filepath: Path, client: NotesClient, dry_run: bool, ctx):
    """Read a single .md file and create a note from it."""
    raw = filepath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    title = meta.get("title") or filepath.stem

    if dry_run:
        if _output_json(ctx):
            _emit(ctx, {"action": "import", "title": title, "dry_run": True})
        else:
            click.echo(f"Would import: {title}")
        return

    client.create_note(title, body)
    if _output_json(ctx):
        _emit(ctx, {"imported": title})
    else:
        click.echo(f"Imported: {title}")
