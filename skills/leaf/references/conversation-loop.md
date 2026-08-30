# Conversation handoff

Read this before handing a page to the user or marking work in progress. The
main skill routes waiting, delivered events, threads, and ending to phase-specific
references.

## Status and handoff

Before a handoff, run:

```bash
leaf status <page> waiting "<what you want back>"
```

The detail names the concrete answer or decision, not the fact that you are
waiting. For an informational page with no concrete ask, leave it empty; the
banner then invites the reader to select text to comment. Follow the main
skill's "Return to the user" rule for every chat message.

While the next move is yours the page is `working`. Name the local subject when
the detail is about one open comment thread or page widget:

```bash
leaf status <page> working "reading the reconnect traces" --on <thread-id>
leaf status <page> working "checking the rollout" --on <widget-id>
```

The line stands beside its subject, so a question or card in hand reads
differently from one nobody has looked at even when no conversation exists. A
thread claim ends with your next reply there. A widget claim survives unrelated
revisions; when a stamped version completes that work, say so on the stamp:

```bash
leaf version stamp <page> --text "…" --completes <widget-id>
```

Repeat `--completes` when the version completes more than one active widget
claim. Stamping accepts only widget ids with standing work. `status --on`
refuses a widget whose active registry declaration provides no `x-work` seat;
use the page-wide detail for work with no safe local line. The local line is the
banner's own claim at a second seat, and one status command writes both.

A `working` claim is believed while the turn that wrote it is open. The page is
told when that turn ends, so a claim nothing has renewed within a couple of
minutes of the ending stops being believed, and the banner reports the silence
instead of the work; a claim nobody renews at all ages out after about a
quarter of an hour. Each local line carries the same reading at its own subject,
so one delegate still reporting keeps the banner green while another's line
goes quiet beside the work it names.

Renewing it is therefore part of the work and goes with it: a delegate outlives
the turn that started it, and no part of this session can write the claim once
the turn has ended. Give the delegate the launcher path, the page path, the
subject id, and the command above to run as it starts — soon enough to land
inside that couple of minutes — and again whenever what it is doing changes.
