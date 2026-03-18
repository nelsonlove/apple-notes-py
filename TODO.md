# apple-notes-py — TODO

## JXA write operations
- [ ] `update_note(title, body_html)` — update body of existing note (missing from jxa.py)
- [ ] `create_note(..., folder=, account=)` — target specific account/folder on create
- [ ] `create_folder(name, account=)` — create a new folder

These capabilities existed in the `nudge` repo (now `apple-notes-sync`, archived) via raw AppleScript.
Implement as JXA in jxa.py for consistency with existing create/delete/move.

## CLI
- [ ] Batch delete tool (multiple notes at once)
- [ ] Note update/append command
- [ ] Folder create/delete commands
- [ ] Auto-rebuild semantic index on stale detection

## MCP
- [ ] `update_note` tool (blocked on JXA above)
- [ ] `create_folder` tool
