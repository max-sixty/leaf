"""Where a piece of work stands: the one vocabulary every record and surface reads.

The base record is the obligation (`obligations`): something one side owes the other.
A widget or an agent's message asks the user; an update the user handed over asks the
agent; a to-do is what the agent promised of its own accord. Every obligation, every
update's delivery (`workflows`), every plan step, each thread and the page say where
they stand in the same fields, and no surface reads another vocabulary:

- `next_actor`: whose move it is, `user` or `agent`, or None once nobody owes one.
- `state`: `waiting` on that actor; `running` while the agent is observed at work on
  it; `blocked` while it is owed and nothing is moving it; `done`.
- `reason`: what the state alone leaves out. Under `running`, `replying` while the
  answer streams in. Under `blocked`: `terminal`, the agent's turn waits on the user in
  its own window; `stopped`, the turn that had it was seen to end or was interrupted
  (`interrupted`) before answering; `quiet`, nothing has renewed it within the working
  grace, so nobody can say whether it moves; `undelivered`, no turn has taken it in
  past the pickup grace; `failed`, the harness gave up on it and handed it back.
- `outcome`: how a `done` one ended, `done`, `failed` or `dropped`.
- `seen`, on an update and its delivery: whether a turn of the agent's has taken it in.
  It is the agent's side of what a thread's `unread` is for the user.

The log decides `next_actor`, `done` and `outcome`, so a reading made without the
claim (`work_reading.WorkReading`, which admission reads) says only `waiting` or
`done`. `activity` adds what the claim, the turn and the harness say, and is the one
producer of `running` and `blocked`.

A start (`todos`) is a lease on an item, held by the turn that wrote it. Work that
outlives that turn is whatever else holds the lease: another session that started the
item, or the claimant's background work while its harness reports some. Such a job has
no record of its own. The item it holds reads `running` while the lease is renewed and
`blocked` with reason `quiet` or `stopped` once it lapses, which is what losing sight of
a delegate, a background command or a wait on CI looks like to the user.

A place that holds several records reads the one `leading` picks: the user's move
ahead of the agent's, then by `strength`. The page reads the agent's side of all of
them beside `presence`, whether anyone is there to take input (`activity`).

Each surface words these fields and nothing else (`records/thread/workflow.js`,
`state/activity-words.js`), so a difference a surface wants to show is either one of them or
the agent's own line. The words on screen are more than the four states: a reason has
its own, such as Stopped or Gone quiet.
"""

_STATE_RANK = {"done": 0, "waiting": 1, "blocked": 2, "running": 3}
# What only a nudge from the user moves: an owed update no turn is left to answer.
STRANDED = frozenset({"stopped", "interrupted", "undelivered"})


def on(actor: str | None) -> dict:
    """The standing of something open on `actor`, before anyone is seen at work on it."""
    return {"next_actor": actor, "state": "waiting", "reason": None, "outcome": None}


def ended(outcome: str) -> dict:
    """The standing of something that ended with `outcome`."""
    return {"next_actor": None, "state": "done", "reason": None, "outcome": outcome}


def is_open(record: dict) -> bool:
    return record["state"] != "done"


def answered(record: dict) -> bool:
    """Whether the answer its source takes stands on a record: the user's own answer to
    a question, or the reply to an update. The end the agent recorded on a to-do is
    no such answer. Every served record carries the
    result as `answered` (`served_state.browser`), so the browser and packages read it
    rather than repeat the rule."""
    return (
        record["state"] == "done"
        and record["outcome"] == "done"
        and record["end"] is None
    )


def strength(standing: dict) -> tuple:
    """How strongly one standing speaks among several of the same actor's: work under
    way ahead of work that stopped, ahead of what waits, and of those the one a turn
    has taken in."""
    return (_STATE_RANK[standing["state"]], bool(standing.get("seen")))


def leading(records: list[dict]) -> dict | None:
    """The open record that speaks for a place holding `records`, or None: a question
    on the user, then an update handed back to them, then what the agent owes, an
    update ahead of a to-do, the strongest first and then the newest."""
    return max(
        (record for record in records if record["next_actor"] is not None),
        key=lambda record: (
            record["next_actor"] == "user",
            record["source"]["kind"] != "update"
            if record["next_actor"] == "user"
            else record["source"]["kind"] == "update",
            record["source"]["kind"] == "todo",
            strength(record),
            record.get("seq", 0),
        ),
        default=None,
    )
