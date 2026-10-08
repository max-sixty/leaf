Your brief names `LEAF`, `PAGE`, `WORKER`, `ROW`, and `TASK`. Use that launcher
for every Leaf write, under that name. Start by moving your agent row and task:

```bash
LEAF_AGENT="$WORKER" "$LEAF" page report "$PAGE" "$ROW" state value=working text="<current activity>"
LEAF_AGENT="$WORKER" "$LEAF" page report "$PAGE" "$TASK" status value=active
```

If a report fails, return its exact error through the harness task and run no other
Leaf command. Report the row whenever the activity changes and often enough that
silence means something: the page calls out a working row that goes quiet for the
working grace, about a quarter of an hour. Report its state and current activity
together, as `value` and `text` in the command above.

- A blocker moves the agent and task to `blocked`, with the immediate blocker in
  its activity text.
- A completed handoff moves the task to `review` and the agent to `waiting`.
- The coordinator records `done` only after review or landing.

A routed user comment arrives with its captured `answer.ref` as `RESPONSE`. Reply to it under your
name, then report any resulting state change:

```bash
LEAF_AGENT="$WORKER" "$LEAF" response reply "$RESPONSE" <<'EOF'
The reconnect drops the queue, so the retry sends against a closed socket.

- the handler clears `pending` before it awaits the write
- nothing re-reads the queue after the socket reopens
EOF
```

These reports and replies to events the coordinator routes to you are your only
Leaf commands; `leaf wait`, status, versions, and the rest of the page are the
coordinator's.
