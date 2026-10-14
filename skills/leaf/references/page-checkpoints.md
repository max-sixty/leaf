# Page checkpoints and ending

## Pre-handover review

The main skill's "Review and stamp a record" step says when a page takes this review.
It adds the browser render check, in both colour schemes, to the markup check every
activation runs:

```bash
leaf page check <page> --render
```

Fix every failure; a screenshot is no substitute. The command prints one JSON object
with the exit `status`, the browser that ran, the screens it saved, and each finding
with its `code`, the element it names as `at`, its `severity` (`error` or `advice`) and
its `text`.

A clean check saves screens at desktop, widest-window and phone widths, up to eight down
the page at each width, plus one just before each layout change, such as a sidebar
stacking. Inspect the end of a longer page yourself. Look in every screen for illegible
labels in drawings, lone tiles, pins covering headings, and a summary that comes too
late on a phone, and fix what the page controls.

Then give a subagent only the user's request and the saved screens, and have it report
anything it can't follow, has to guess, or has to picture from a description. Give it
none of your notes: the user hasn't seen them either. Fix what it finds. In your own
read-through, check that headings state findings, claims have evidence, decisions have
controls, and every line of prose is needed, and draw anything the page explains only
in words when a picture would show it.

For a page with contents, start at the top at desktop and phone widths and jump to a
later section without first scrolling to find the navigation. Follow the page's links
with pointer and keyboard, and check that each destination leaves the user oriented.

For a page with asks, the check also saves the window at each of the first eight asks
as `m` reaches it from the top (`conversation-loop.md`, "The On lists"). At each,
confirm that the question, premise, alternatives and evidence are visible together,
that the numbers shown match the actions offered, and that the next `m` reaches the next
item on the user's On me list.

If you can't see the rendered page, review the words, evidence and choices from the
active HTML and `leaf page state <page>`, and report the visual and keyboard review as
not done. When the check's `browser` field is `unavailable`, report the render check as
unfinished, along with the run of the page's code if it needed one.

## Stamp checkpoints

Stamp a record at each checkpoint the user would name, such as sign-off or the end of
the conversation, and wherever a reference requires a stamped version, as taking in an
answer to a page ask does (`authoring-revisions.md`). Answering a message is not a
checkpoint.

```bash
leaf page stamp <page> --text "<what changed>"
```

The stamp gives the current source the next public version number. A browser at the
page's root follows new revisions; one open at `/versions/vN.html` stays on that
version.

## Sign-off and ending

To finish, handle every event in the delivered batch and write the answer each
acknowledged update's `answer` names (`event-batches.md`). A finished record ends on a
stamped final version that honours open asks and the reports still in force; an
unstamped quick page can go idle directly. Then run:

```bash
leaf status <page> idle
```

`idle` ends the agent's side of the page, and refuses while events are pending or an
update still owes its answer. It takes the page off the watch, and idling the last
watched page ends the watcher. It doesn't stop the server or delete the page
(`serving-pages.md`, "Page lifetime"). Don't idle a persistent page because one
session's work on it is done.
