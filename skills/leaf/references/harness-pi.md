# Pi handoff and wait loop

Leaf on Pi is a highly experimental trial.

## Launcher

Leaf's Pi extension sets `$LEAF` to the launcher and puts it on `PATH`, so `leaf`
runs it in every shell-tool command.

## Serve the page

```bash
leaf server start <page>
```

It prints `{"url": ...}`, the page's keyed URL, on stdout and returns. Hand that
exact URL back. `references/serving-pages.md` owns the key, the address it binds,
and a URL the user cannot reach.

## Wait loop

Leaf's extension watches for you. As each run settles, it watches every page this
session holds until one has new input, then puts the whole delivery in your
context (`references/event-batches.md`, "One envelope on every transport"): in a
new run when Pi is idle, or after your current tool calls when a run is going. So
once the page is handed over, end the run: start no `leaf wait`. Input that
arrives as a run is about to end comes into that run the same way, and keeps it
going.

Once the complete envelope is in context, take its `acknowledge` route
(`leaf delivery ack <id>`) before working or replying, so the user's moves read
**Picked up**. Large input arrives as a `leaf delivery read <id>` pointer; read
the whole envelope before acknowledging it.

To pick up a page this session did not serve, run `leaf page claim <page>`; the
extension watches it from the end of the run.

If a run ends without answering a delivered move, the next prompt carries that
obligation back into context. Under `pi --print` the session ends with its run,
and nothing carries later input back to it.
