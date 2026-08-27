# Codex watcher task

A Codex watcher keeps a Leaf wait active after the page's task ends its turn. It
forwards each complete batch into that task through a background follow-up. Creating the
watcher adds a visible task to the user's sidebar, so this path requires the user's
explicit authorization and a host that offers both task creation and background
follow-ups.

Create one watcher per page in the same saved project. Give it the exact page task id,
page path, and resolved Leaf launcher. Its job is:

1. Confirm that `send_message_to_thread` is available before claiming the page. If it is
   missing, finish with that reason and do not run `leaf wait`.
2. Run `leaf wait <page>` in unified exec. Retain the command's session id and
   poll it with empty `write_stdin` calls and long yields. Keep the watcher turn active
   while the page is live.
3. Once the complete output arrives, send one background follow-up to the page task. Put
   this instruction before the wait output:

   ```text
   This Leaf batch was forwarded by a watcher task. Handle every event, but do not run
   `leaf wait` or `leaf ack`: the watcher owns both and acknowledges only after this
   follow-up is accepted. A page and event seq already handled is a retry, even when a
   later delivery also contains newer events.
   ```

   Append the complete wait output verbatim. If the send fails or its outcome is
   uncertain, acknowledge nothing and resend the same follow-up. If the wait output was
   lost or truncated, acknowledge nothing and rerun `leaf wait <page>` with
   enough output capacity. The later batch may also contain newer events because the
   cursor has not moved.
4. After the host accepts the follow-up, run `leaf ack <page> <highest-seq>` in
   unified exec. Retain and poll that command's session id: after advancing the
   cursor, ack stays active as the next wait. A successful ack exits 0 whether that
   wait delivered or the page went idle, so read its output rather than its status:
   a batch on stdout is the next delivery, and an empty stdout with the idle line on
   stderr is where the watcher exits. The watcher does not author, reply, resolve,
   stamp, change status, or handle an event itself.

Wait for the watcher to claim the page, title it `Leaf watcher — <page name>`, and confirm
that `leaf page state <page>` reports `listening: true` before ending the page task's
turn. The named wait transfers the page's claim to the watcher, so the page task's Stop
hook stands down. Status updates, replies, and versions do not reclaim the page. Setting
the page idle ends the watcher's next wait.

When a forwarded batch reaches the page task, follow its instruction. Handle every
event without waiting or acknowledging, and skip any page-and-seq pair already handled
in that task.
