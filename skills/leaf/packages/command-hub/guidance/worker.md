# Command Hub worker

Use the assigned launcher for every Leaf write. Start by moving your agent row
and task:

```bash
LEAF_AGENT="$WORKER" "$LEAF" report "$PAGE" "$ROW" state state=working doing="<current activity>"
LEAF_AGENT="$WORKER" "$LEAF" report "$PAGE" "$TASK" status status=active
```

If `report` fails, return its exact error through the host task and run no other
Leaf command. Report the row whenever the activity changes and often enough that
silence means something: the page calls out a working row that goes quiet for the
working grace, about a quarter of an hour. Both `state` and
`doing` are required on an agent report.

- A blocker moves the agent and task to `blocked`, with the immediate blocker in
  `doing`.
- A completed handoff moves the task to `review` and the agent to `waiting`.
- The coordinator records `done` only after review or landing.

For a routed user comment, reply under your assigned identity, then report any
resulting state change:

```bash
LEAF_AGENT="$WORKER" "$LEAF" reply "$PAGE" --to "$THREAD" --for "$EVENT" <<'EOF'
The reconnect drops the queue, so the retry sends against a closed socket.

- the handler clears `pending` before it awaits the write
- nothing re-reads the queue after the socket reopens
EOF
```

These reports and replies to events the coordinator routes to you are your only
Leaf commands; `leaf wait`, status, versions, and the rest of the page are the
coordinator's.
