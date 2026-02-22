"""JXA subprocess calls for Apple Notes write operations."""

import json
import subprocess


def _run_jxa(script: str) -> str:
    """Execute a JXA script via osascript and return stdout."""
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"JXA error: {result.stderr.strip()}")
    return result.stdout.strip()


def create_note(title: str, body_html: str) -> None:
    """Create a new note in Apple Notes.

    Args:
        title: Note title (plain text).
        body_html: Note body as HTML string.
    """
    # JSON-encode strings to safely embed them in JavaScript,
    # avoiding any injection through quotes or special chars.
    safe_title = json.dumps(title)
    safe_body = json.dumps(body_html)

    script = f"""
    const app = Application('Notes');
    app.make({{new: 'note', withProperties: {{
        name: {safe_title},
        body: {safe_body}
    }}}});
    """
    _run_jxa(script)
