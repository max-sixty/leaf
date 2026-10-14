# Page checkpoints and ending

## Pre-handover review

The main skill's "Review and stamp a record" step decides when a page takes this review.
Every source activation already runs the deterministic markup check; this review adds
the browser gate and a reading:

```bash
leaf page check <page> --render
```

It runs the browser gate in both color schemes, including when the host gives you
no separate browser tool. Fix every failure; a screenshot is not a substitute.
It prints one object with the exit `status`, each finding as a record (`code`, the
element it names as `at`, the measured `values`, `severity` of `error` or `advice`,
where it was read, and its `text`), and the browser that ran and the screens it
saved.

A clean check saves labeled screens at desktop, widest-window, and phone widths,
up to eight screens down the page at each width. If the page extends beyond those,
inspect its end separately. It also saves a screen just before each layout
transition, such as a sidebar stacking or tiles wrapping. Read every screen for
illegible or oversized drawing labels, isolated tiles, pins covering headings,
and summaries arriving too late on a phone. Fix problems the page controls, then
check again.

Before handoff, give a subagent only the user's request and the labeled saved
screens. Have it report anything it cannot follow, must guess, or has to picture
from a description; fix those findings. The reader needs none of your research or
notes, since the user has not seen them either. In your own reading, check that
headings state their findings, claims have evidence, decisions have controls,
drawings add information, and visible prose is needed by the user. Draw any subject
the page currently explains only in words when a picture would convey it.

For a page with contents, start at its opening at desktop and phone widths and
jump to a later section without first scrolling through the article to find the
navigation. Follow the page's links and operate its navigation with pointer and keyboard.
At each destination, check that the visible content and focus leave the user
oriented and able to continue; compare equivalent moves across the page's views.

For a page with asks, the check also saves the window at each of the first eight
as `m` reaches it from the top, which is how a user working the page meets each
question (`conversation-loop.md`, "The On lists"). At each arrival, confirm
that the question, shared premise, alternatives, and evidence that distinguishes them
are visible together, the displayed numbers match the available actions, and the next
press of `m` reaches the next item on the user's On me list while the complete page remains
visible.

Without a way to inspect the rendered page, read `leaf page state <page>`'s
`state` and `todos` alongside the active HTML to review the words, evidence, and
available choices. Report the render command's result separately from the visual
and keyboard review you could not perform. If the command cannot launch a browser,
its `browser` says why as `unavailable`: report the render check as unfinished, and,
where the page's code needed a run, that run as well. A text reading does not establish
layout or interaction quality.

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
revision that honors open asks and the reports in force. An unstamped quick page can go idle directly.
Idling ends the interaction but does not delete the page directory.

Then run:

```bash
leaf status <page> idle
```

`idle` is the explicit end of the agent side and refuses pending events or an
acknowledged update still owed its answer. It removes the page from the watch, and
idling the last watched page ends the watcher. It is not a server stop:
`references/serving-pages.md`, "Page lifetime", says which servers end with the
session, and a persistent page is not idled because one session's work on it is over.
