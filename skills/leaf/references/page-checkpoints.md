# Page checkpoints and ending

## Stamp checkpoints

Stamp a record again at a checkpoint the user would name, such as sign-off or the
end of the conversation, and wherever a reference requires a stamped version, as
taking in an answer to a page ask does (`references/authoring-revisions.md`). Each
stamp records the exact current source with a brief changelog, after the render check
and reading the main skill's "Review and stamp a record" step asks of a record. An
answered message is not a checkpoint.

```bash
leaf page stamp <page> --text "<what changed>"
```

Leaf assigns the next public version number and maps it to that exact revision.
A browser at the live root follows new revisions; a browser pinned to
`/versions/vN.html` stays on the revision mapped by that stamp.

## Sign-off and ending

To finish, handle every event in the complete delivered batch and write the answer
each acknowledged update's `answer` names (`references/event-batches.md`). A
finished record, including a quick page that became one, ends on a stamped final
revision that honors standing asks and reports. An unstamped quick page can go idle directly.
Idling ends the interaction but does not delete the page directory.

Then run:

```bash
leaf status <page> idle
```

`idle` is the explicit end of the agent side and refuses pending events or an
acknowledged update still owed its answer. It removes the page from the watch, and
idling the last watched page ends the watcher. It is not a server stop:
`references/serving-pages.md`, "Page lifetime", says which servers end with the
session, and a standing page is not idled because one session's work on it is over.
