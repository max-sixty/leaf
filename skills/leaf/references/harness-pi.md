# Pi handoff and wait loop

Leaf on Pi is a highly experimental trial.

## Launcher

Leaf's Pi extension sets `$LEAF` to the launcher and puts it on `PATH`, so `leaf` works
in every shell command.

## Serve the page

```bash
leaf server start <page>
```

It prints a JSON object whose `url` is the page's keyed URL, and returns. Follow
`conversation-loop.md`, "Status and handoff". `serving-pages.md` covers the address and
what to do when the user can't reach the URL.

## Wait loop

Once you have handed the page over, end the run and start no `leaf wait`. Leaf's
extension watches every page this session holds and puts each delivery in your
context: in a new run if Pi is idle, or after your current tool calls if a run is
going. It acknowledges what it puts there, so `acknowledge` is null and you run no
acknowledgement command. Input it couldn't confirm, such as a large delivery, arrives
as a pointer instead: read every part with the `leaf delivery read <id>` it names
before working or replying, then follow its confirmation instruction.

To take over a page this session didn't serve, run `leaf page claim <page>`; the
extension starts watching it when the run ends. If a run ends without answering a
delivered update, the next prompt brings it back. Under `pi --print` the session ends
with its run, and nothing brings later input back to it.
