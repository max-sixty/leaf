# Further Codex integration work

Leaf's current companion workflow is documented in
[harness-codex.md](../skills/leaf/references/harness-codex.md).
[Session lifetime, “Watchers”](../skills/leaf/scripts/leaf/session-lifetime.md#watchers)
owns the delivery and connection lifecycle. This note holds open design work.

## Typed operations

Provide model tools for reading page state, replying, declaring work, and
validating authored changes. MCP tools or App Server dynamic tools could call the
same Python functions as the CLI. Keep event admission and reply settlement in
those existing owners.

First test a complete feedback turn with the smallest useful tool set. Compare
it with the CLI path for target-selection errors and unnecessary model work.
The model still decides whether feedback calls for a reply, a revision, or both.

## Delivery-start race

Measured with codex-cli 0.160.0 on 2026-10-19.

`turn/start` on a task whose turn is running steers the input into that turn and
answers with the running turn's id. Nothing in the answer says it steered. When Leaf
started after the other client's answer, that turn's `turn/started` reached Leaf's
socket first. With both starts sent back to back, Leaf's answer came first, the order
Leaf's own start produces, so the order of messages cannot tell the two cases apart.

The race needs no coincidence of milliseconds. A follow-up queued behind a running
turn starts just after that turn completes, and App Server reads idle until it does.
In all three runs, a Leaf start sent right after `turn/completed` read idle on
`thread/resume`, and its `turn/start` joined the user's follow-up turn. The model
received the delivery as a `leaf_delivery` tool output partway through that turn.
The adapter holds a delivery back while a turn runs and checks again at least once a
second (`run_adapter`), so a delivery waiting behind the turn starts inside that gap
some of the time; how often is inferred from the timing, not measured.

Who starts the follow-up depends on where it was queued (measured 2026-10-20):

- **The Codex TUI** keeps a follow-up queued with Tab in its own composer state
  (`queued_user_messages` in `codex-rs/tui/src/chatwidget/input_queue.rs`) and sends
  it with `turn/start` once the turn ends (`maybe_send_next_queued_input`). With the
  TUI on `codex --remote` showing the follow-up queued, `thread/queue/list` on the
  same task returned no items, and the TUI's `turn/start` came 17.5 ms after
  `turn/completed`. So App Server's queue can't tell Leaf that the user is waiting.
- **App Server's queue** holds what a client adds with `thread/queue/add`, as
  `codex queue` does. App Server starts its head about 6 ms after the turn ends (six
  runs; about 0.4 s in the 2026-10-19 run), and removes the item only once its turn
  has started (`QueuedItemService::dispatch_if_idle`), so a reading of the queue,
  then the status, never showed an empty queue on an idle task in that gap.

To recheck the TUI on a later Codex, start a private App Server as the script below
does, run `codex --remote <endpoint>` in a terminal, queue a follow-up with Tab while
a turn runs, and call `thread/queue/list` for the task from a second connection that
initialized with the `experimentalApi` capability.

`TaskConnection._start_delivery` binds whatever turn the start returns to the
delivery. Replaying the measured order against a fake App Server like those in
`tests/model/test_codex_app_server.py`, Leaf posted the joined turn's final answer,
which answered the other prompt, as its reply to the user's comment, and the comment
counted as answered. The comment reached the model, but its reply is text written for
another prompt.

App Server's only atomic start-if-idle is experimental and needs the `experimentalApi`
capability. While a turn ran, `thread/queue/start` refused with "thread already has
an active or pending turn", and App Server ran the queued submission as its own turn
once the running turn ended. A queued submission's input is user input, not a tool
output. Stable `turn/steer` checks an `expectedTurnId`, but no stable request checks
that the task is idle.

Two options were weighed:

- **Queue each delivery.** Send `thread/queue/add` and `thread/queue/start`, and
  adopt the turn that carries the delivery when it starts. App Server orders Leaf's
  deliveries with the user's queued input and never steers one. Leaf would depend on
  an experimental API, the delivery would enter as a user message rather than a tool
  output, and Leaf's submissions would show in the user's queue in Codex. #3357 took
  this option and was reverted: every delivery then became a user message in the
  Codex transcript, the opening line and the envelope's JSON, which is noisy for the
  user, and Max wants Leaf to add to the user's turn only when it must. Against a
  follow-up queued in the TUI it also left a race: a delivery Leaf queued in the
  moments before the TUI sent its follow-up would start first, and the follow-up
  would then steer into Leaf's turn (inferred from the timings above, not run).
- **Keep `turn/start` and define a joined delivery.** Decide which message the
  final answer settles, where that answer appears, and what remains outstanding if
  the turn fails. Since the start's answer cannot say it steered, Leaf would detect
  a join from the turn's items, such as a user message ahead of the delivery. That a
  turn Leaf starts opens with its tool output is not yet measured.

To reproduce, run the script below from the repository root with `steer` for the
queued follow-up or `queue` for the queue's refusal. Each run spends two or three
Codex turns on a copy of the host's login.

```bash
uv run python - steer <<'EOF'
import json, os, shutil, sys, tempfile
from pathlib import Path

from leaf.codex import app_server_connect, app_server_request, private_app_server
from leaf.codex import app_server_turn_start_params as leaf_start
from leaf.delivery import DELIVERY
from leaf_dev.arms import codex_home

ended = set()


def connect(endpoint):
    socket = app_server_connect(endpoint)
    ask(socket, "initialize", {"clientInfo": {"name": "probe", "version": "0"},
                               "capabilities": {"experimentalApi": True}})
    socket.send(json.dumps({"method": "initialized", "params": {}}))
    return socket


def seen(message):
    if message.get("method") == "turn/completed":
        ended.add(message["params"]["turn"]["id"])


def ask(socket, method, params):
    try:
        return app_server_request(socket, method, 1, params, seen)
    except Exception as error:
        return f"refused: {error}"


def wait(socket, turn):
    while turn not in ended:
        seen(json.loads(socket.recv(timeout=120)))


def text(value):
    return [{"type": "text", "text": value}]


home = codex_home(Path(tempfile.mkdtemp()) / "codex")
env = os.environ | {"CODEX_HOME": str(home)}
with private_app_server(shutil.which("codex"), env=env) as endpoint:
    leaf, user = connect(endpoint), connect(endpoint)
    thread = ask(leaf, "thread/start", {"cwd": tempfile.mkdtemp(),
                                        "approvalPolicy": "never",
                                        "sandbox": "read-only"})["thread"]["id"]
    wait(leaf, ask(leaf, "turn/start", {"threadId": thread,
                                        "input": text("Reply: OK")})["turn"]["id"])
    ask(user, "thread/resume", {"threadId": thread})
    running = ask(user, "turn/start", {"threadId": thread, "input": text(
        "Run `sleep 20`, then reply: USER TURN")})["turn"]["id"]
    if sys.argv[1] == "queue":
        ask(leaf, "thread/queue/add", {"threadId": thread, "clientUserMessageId": "x",
                                       "input": text("Reply: LEAF")})
        print("queue/start while a turn runs:",
              ask(leaf, "thread/queue/start", {"threadId": thread}))
    else:
        ask(user, "thread/queue/add", {"threadId": thread, "clientUserMessageId": "y",
                                       "input": text("Reply: USER FOLLOW-UP")})
        wait(leaf, running)  # Leaf's held-back delivery fires as the turn ends.
        status = ask(leaf, "thread/resume", {"threadId": thread, "excludeTurns": True})
        print("Leaf's idle check at turn end:", status["thread"]["status"])
        payload = {"format": DELIVERY.format, "id": "0000beef"}
        started = ask(leaf, "turn/start", leaf_start(thread, payload))["turn"]["id"]
        wait(leaf, started)
        turns = ask(leaf, "thread/read", {"threadId": thread, "includeTurns": True})
        turn = next(t for t in turns["thread"]["turns"] if t["id"] == started)
        print("Leaf's turn/start joined:",
              [(i["type"], i.get("content") or i.get("text") or i.get("name"))
               for i in turn["items"]])
EOF
```

## Evaluate a typed reply body

A typed reply tool would own both the streamed text and the durable reply event only
if App Server streamed its arguments, and 0.160.0 does not. Its schema, experimental
methods included, streams agent messages, plans, reasoning, command and file output,
and file-change patches (`item/fileChange/patchUpdated`). No notification carries a
tool call's arguments while the model writes them, and a dynamic tool call's request
(`DynamicToolCallParams`) receives them complete. A typed reply would
therefore appear only when its call finished, later than today's streamed final
message. Check a later Codex with:

```bash
codex app-server generate-json-schema --experimental --out .tmp/schema
jq -r '.oneOf[].properties.method.enum[0]' .tmp/schema/ServerNotification.json
```

## Broader product choices

These alternatives need a user-facing purpose before implementation:

- Route several threads' responses within one Codex turn. This needs explicit
  response targets and a policy for approvals and input requests.
- Delegate a page to a Leaf-owned child task. This needs context transfer and
  coordinated workspace ownership; persistent pages are one possible use.
- Make Leaf the Codex client. This would add transcript, approval, interruption,
  and reconnect ownership to Leaf's page and feedback responsibilities.
