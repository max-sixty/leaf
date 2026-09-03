# Page checkpoints and ending

Read this before stamping a checkpoint or ending a page.

## Save revisions and stamp checkpoints

Edit `<page>/index.html` directly. Each changed valid save becomes a new immutable
revision and the live root follows it automatically; keep saving while the work
is in motion. If the source is invalid, the last valid revision remains live and
`leaf page state` reports the source diagnostic.

When the page reaches a checkpoint worth naming, stamp the exact current source
with a brief changelog:

```bash
leaf version stamp <page> --text "<what changed>"
```

Leaf assigns the next public version number and maps it to that exact revision.
Do not write `revisions/` yourself. A browser at the live root follows new
revisions; a browser pinned to `/versions/vN.html` stays on the revision mapped by
that stamp. Re-enter the host's wait loop after the batch: `waiting` when the reader
owns the next move, `working` while you continue.

## Sign-off and ending

A `done` event approves the work but does not end the page. Keep the page working
and watched while doing what approval unblocked.

To finish, handle every event in the complete delivered batch and make sure every
acknowledged thread that awaits your answer has one. A finished record, including
a quick page that became one, ends on a stamped final revision that honors
standing decisions and reports. An unstamped quick page can go idle directly.
Idling ends the interaction but does not delete the page directory. Sign-off is
available only on a stamped revision. `leaf transcript <page>` prints record
debt on stderr and the full exchange as Markdown.

Then run:

```bash
leaf status <page> idle
```

`idle` is the explicit end of the agent side and refuses pending events or an
answered-by-reader thread still awaiting you. It removes the page from the watch;
the last idle page ends the waiter. A normal session-lifetime server process
retires when the page has no live claim, while its enabled service remains
available for a selected successor to revive; it needs no separate stop. A
standing page has a different lifetime and must not be idled merely because one
session's work is over.
