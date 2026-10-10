# Codex watcher task

A Codex watcher keeps a Leaf wait active after the page's task ends its turn. It
forwards each complete batch into that task through a background follow-up. It needs
a harness that offers both task creation and background follow-ups, and it adds a
visible task to the user's sidebar.

Create one watcher per page in the same saved project. Give it the exact page task id,
page path, resolved Leaf launcher, and the path of `references/event-batches.md`,
whose "Delivery and acknowledgement" section says how a wait ends. Its job is:

1. Confirm that `send_message_to_thread` is available before claiming the page. If it is
   missing, finish with that reason and do not run `leaf wait`.
2. Run `leaf page claim <page>`, then `leaf wait <page>` in unified exec. Retain the command's session id and
   poll it with empty `write_stdin` calls and long yields. Keep the watcher turn active
   while the page is live.
3. Once the complete output arrives, send one background follow-up to the page task. Put
   this instruction before the wait output:

   ```text
   This Leaf batch was forwarded by a watcher task, which ran the wait and
   acknowledges it once this follow-up is accepted. Handle every event, and run no
   `leaf wait` yourself. A page and event seq already handled is a retry, even when
   a later delivery also contains newer events.
   ```

   Append the complete wait output verbatim. If the send fails or its outcome is
   uncertain, acknowledge nothing and resend the same follow-up. For lost or
   truncated output, reread the delivery before forwarding it.
4. After the harness accepts the follow-up, run `leaf wait --ack <delivery-id>` in
   unified exec. Retain and poll that command's session id. A batch on stdout is
   the next delivery; return to step 3. Follow any ending diagnostic. The watcher
   does not author, reply, resolve, stamp, change status, or handle an event itself.

Wait for the watcher to claim the page, title it `Leaf watcher — <page name>`, and confirm
that `leaf page state <page>` reports `listening: true` before ending the page task's
turn. The explicit claim transfers ownership to the watcher, so the page task's Stop
hook stands down. Status updates, replies, and versions do not reclaim the page. Setting
the page idle ends the watcher's next wait.

When a forwarded batch reaches the page task, follow its instruction.
