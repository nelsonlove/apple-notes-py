"""Click CLI for Apple Notes — thin layer over library modules."""

import json
import re
import sys
from pathlib import Path

import click

from .db import NotesDB
from .decode import decode_note_content, decode_note_to_markdown


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


def _format_frontmatter(note: dict) -> str:
    """Build YAML front-matter block from note metadata."""
    lines = ['---']
    lines.append(f'title: "{note["title"]}"')
    lines.append(f'folder: "{note.get("folder", "")}"')
    if note.get("createdAt"):
        lines.append(f'created: "{note["createdAt"]}"')
    if note.get("modifiedAt"):
        lines.append(f'modified: "{note["modifiedAt"]}"')
    lines.append('---')
    return '\n'.join(lines)


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


def _export_note(note: dict) -> str:
    """Decode a note dict and return Markdown with front-matter."""
    md = decode_note_to_markdown(note.get("content"), skip_title=True)
    fm = _format_frontmatter(note)
    return f"{fm}\n\n{md}\n" if md else f"{fm}\n"


def _export_many(notes: list[dict], out_dir: Path) -> int:
    """Write multiple notes as .md files into out_dir. Returns count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for n in notes:
        if n.get("locked"):
            continue
        md = decode_note_to_markdown(n.get("content"), skip_title=True)
        if not md:
            continue
        fm = _format_frontmatter(n)
        stem = _sanitize_filename(n["title"])
        path = _unique_path(out_dir, stem, ".md")
        path.write_text(f"{fm}\n\n{md}\n", encoding="utf-8")
        count += 1
    return count


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
    db = _get_db(ctx)

    # ── bulk export (folder or all) ─────────────────────────────────
    if folder or export_all:
        if not output:
            raise click.UsageError("Provide -o/--output directory for bulk export.")
        out_dir = Path(output)
        notes = db.get_all_notes_with_content()
        if folder:
            notes = [n for n in notes if n.get("folder") == folder]
        if not notes:
            click.echo("No notes found.", err=True)
            sys.exit(1)
        count = _export_many(notes, out_dir)
        click.echo(f"Exported {count} notes to {out_dir}/")
        return

    # ── single note export ──────────────────────────────────────────
    if by_id is not None:
        note = db.get_note_by_pk(by_id)
    elif title:
        note = db.get_note_by_title(title)
    else:
        raise click.UsageError("Provide a TITLE, --by-id, --folder, or --all.")

    if not note:
        click.echo("Note not found.", err=True)
        sys.exit(1)

    md = _export_note(note)

    if output:
        Path(output).write_text(md, encoding="utf-8")
        click.echo(f"Exported to {output}")
    else:
        click.echo(md)


# ── import ──────────────────────────────────────────────────────────────

@cli.command("import")
@click.argument("path", type=click.Path(exists=True))
def import_notes(path):
    """Import Markdown files as Apple Notes."""
    from .convert import markdown_to_html
    from .jxa import create_note

    target = Path(path)

    if target.is_dir():
        files = sorted(target.glob("*.md"))
        if not files:
            click.echo("No .md files found in directory.", err=True)
            sys.exit(1)
        for f in files:
            _import_one(f, markdown_to_html, create_note)
    elif target.is_file():
        _import_one(target, markdown_to_html, create_note)
    else:
        raise click.UsageError(f"Not a file or directory: {path}")


def _import_one(filepath: Path, md_to_html, create_fn):
    """Read a single .md file and create a note from it."""
    raw = filepath.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    title = meta.get("title") or filepath.stem
    html_body = md_to_html(body)
    create_fn(title, html_body)
    click.echo(f"Imported: {title}")
