# Page checkpoints and ending

## Stamp checkpoints

When the page reaches a checkpoint worth naming, stamp the exact current source
with a brief changelog:

```bash
leaf version stamp <page> --text "<what changed>"
```

Leaf assigns the next public version number and maps it to that exact revision.
A browser at the live root follows new revisions; a browser pinned to
`/versions/vN.html` stays on the revision mapped by that stamp.

## Sign-off and ending

A `done` event approves the work but does not end the page. Keep the page working
and watched while doing what approval unblocked.

To finish, handle every event in the complete delivered batch and make sure every
acknowledged thread that awaits your answer has one. A finished record, including
a quick page that became one, ends on a stamped final revision that honors
standing Asks and reports. An unstamped quick page can go idle directly.
Idling ends the interaction but does not delete the page directory.

Then run:

```bash
leaf status <page> idle
```

`idle` is the explicit end of the agent side and refuses pending events or an
answered-by-reader thread still awaiting you. It removes the page from the watch;
the last idle page ends the waiter. It is not a server stop: `references/serving-pages.md`,
"Page lifetime", says which servers end with the session, and a standing page is
not idled because one session's work on it is over.
