# Codex watcher task

A Codex watcher task keeps a `leaf wait` running after the page's task ends its turn,
and forwards each batch into that task as a background follow-up. It needs a harness
that offers task creation and background follow-ups, and it adds a visible task to the
user's sidebar.

Create one watcher per page in the same saved project. Give it the page task's exact
id, the page path, the resolved Leaf launcher, and the path of `event-batches.md`,
whose "Delivery and acknowledgement" section says how a wait ends. Its job is:

1. Check that `send_message_to_thread` is available. If it isn't, finish with that
   reason and don't run `leaf wait`.
2. Run `leaf page claim <page> --manual-delivery`, then `leaf wait <page>` in unified exec. Keep the
   command's session id and poll it with empty `write_stdin` calls and long yields,
   keeping the watcher's turn running while the page is live.
3. When the complete output arrives, send one background follow-up to the page task,
   with this instruction before the wait output:

   ```text
   This Leaf batch was forwarded by a watcher task, which ran the wait and
   acknowledges it once this follow-up is accepted. Handle every event, and run no
   `leaf wait` yourself. A page and event seq already handled is a retry, even when
   a later delivery also contains newer events.
   ```

   Append the complete wait output verbatim. If the send fails or its result is
   uncertain, acknowledge nothing and send the same follow-up again. If the output was
   lost or cut off, read the delivery again before forwarding it.

4. Once the harness accepts the follow-up, run
   `leaf delivery ack <delivery-id> && leaf wait` in unified exec and poll it the
   same way. A batch on stdout is the next delivery; go
   back to step 3. Follow any message that ends the wait. The watcher never replies,
   stamps, changes status or handles an event itself.

Before ending the page task's turn, wait until the watcher has claimed the page, title
the watcher task `Leaf watcher — <page name>`, and check that `leaf page state <page>`
reports `listening: true`. The page task's status declarations, replies and new
versions don't take the page back; its own `leaf server start` or `leaf page claim`
does.
Setting the page idle ends the watcher's next wait.

When a forwarded batch reaches the page task, follow its instruction.
