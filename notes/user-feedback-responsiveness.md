# Feedback responsiveness evaluation

The delivery and activity lifecycle is implemented. Its owners are
[session lifetime](../skills/leaf/scripts/leaf/session-lifetime.md),
[conversation loop](../skills/leaf/references/conversation-loop.md), and the
application publication described in [AGENTS.md](../AGENTS.md). This note holds
remaining evaluation work and proposed improvements; it does not define a second
lifecycle contract.

The browser paints a gesture's semantic result before its POST completes. Transports
record queue acceptance and turn entry; the agent selects work through a claim;
durable replies and revisions settle the exact input. Delivery evidence does not
prove external work succeeded, and page activity does not imply work on every message.

## Evaluation

None of these is a gate. Read the outputs as well as the pass counts.

```bash
# Timed journeys, one harness at a time; each run adds a sample to journey.jsonl.
uv run leaf-dev journey claude-code [--hooks-module]
uv run leaf-dev journey codex-app-server
uv run leaf-dev journey pi
uv run leaf-dev journey website-adapter
uv run leaf-dev journey-chart
# Each reply's whole time and Leaf's share, waiting and working, by harness.
uv run leaf-dev journey-chart --replies
# In-tab feedback.
uv run leaf-dev bench-latency --tree --runs 3
# Status evaluations.
uv run leaf-dev eval plan-shows-multi-step-work plan-skips-quick-work \
  parent-keeps-leaf-responsive 'parent-keeps-leaf-responsive/known-answer' \
  'parent-keeps-leaf-responsive/no-subagents' --harness claude-code --repeat 3
uv run leaf-dev eval plan-shows-multi-step-work parent-keeps-leaf-responsive \
  --harness codex --repeat 2
uv run leaf-dev eval 'document/idle' 'document/mid-turn' \
  --harness claude-code --repeat 2 -j 1
uv run leaf-dev eval 'parent-keeps-leaf-responsive/during-work' \
  --harness claude-code -j 1
uv run leaf-dev eval website-replies 'website-replies/follow-up' \
  --harness codex --repeat 2 -j 1
```

For actionable input, the claim should precede substantive source reads, edits,
tests and delegation. A queued pointer may first read its immutable delivery to
resolve the address. A claim on an update that settled after the agent read it
is refused, so a settled update never reads Working. Both claims,
`leaf task start` and a progress reply, check that the update is still owed
while holding the log lock they append under (`todos.todo_error`,
`thread._resolve_obligation`). During delegation, retain the original work and
the newer queued count while the observer can still prove the delegate is live.

Read deterministic sequence and state at their owners: projection tests for
sent/queued/opened/active/stale/settled evidence; real gestures for local results;
agent traces for claim ordering. `leaf-dev journey` is the vertical test: it times a
real request on any harness from the page's own log, and on each harness target also
times the comments of its later steps and splits each reply into Leaf's share, the
harness's other work and the model calls (`dev/leaf_dev/reply_phases.py`). Each run
keeps its sample in `$XDG_STATE_HOME/leaf-dev/journey.jsonl` on its machine.

## Latency targets and readings

The targets are proposed budgets. The readings are this Mac's runs on 2026-10-20,
on main at `e5113c687` with this note's change, with the load average between 6
and 12 on 18 cores: `bench-latency --tree --runs 3` for the paint rows, and for the
rest two journeys per harness with the comments posted over HTTP, ranges covering
every comment of every step. The journey reads pickup but not the receipt before
it, so the receipt row has no reading of its own; an idle session's pickup bounds
it.

| Transition                                 | Target                                      | Reading on 2026-10-20                                                              |
| ------------------------------------------ | ------------------------------------------- | ---------------------------------------------------------------------------------- |
| Gesture to local result                    | Same rendering turn; under 100 ms           | triage board 10–44 ms; corpus 72–132 ms, comment median 105 ms                     |
| Acceptance to visible receipt              | Next state application; under 1 s           | not read apart from pickup                                                         |
| Turn entry to visible pickup, idle session | Without waiting for model output; under 1 s | 0.1–0.8 s on every harness                                                         |
| Input in model context to accepted claim   | Before substantive work; under 2 s          | first command; 3.3 s (Pi) to 5.8–10.5 s (Claude Code) after the comment; see below |
| Status or result write to browser paint    | Next state application; under 1 s           | status 16–76 ms, reply 87–183 ms; revision 262–277 ms, corpus 0.64–1.22 s (below)  |
| Comment admission to thread title          | under 2 s                                   | Claude Code 1.2–2.7 s, Pi 2.0–2.7 s, Codex App Server 1.7–2.6 s                    |

A small page change's reply has budgets of its own, for the whole reply and Leaf's
share of it, with the harness waiting and working ("A small page change's reply",
below).

The claim row counts from the comment's admission, so it includes the agent's first
model call. On Claude Code and Pi the claim, a progress reply, is the turn's first
command, ahead of any read or edit. On Codex App Server the agent posts no progress
reply; the page reads Working from the harness's stream 2 s after the comment and
names each command as it runs.

Two paint readings miss: the corpus's comment paints in a median 105 ms, and a
revision of the corpus, a page far larger than a user's, paints within 1 s only
when the tab finds the save before a stamp locks the page (below).

Every harness titles near the 2 s target, and the model's own answer is most of it:
1.3–2.2 s of a Codex title. Codex App Server titled in 3.0–8.5 s until its page
server started each title's App Server and thread before the comment arrived
(`thread_titles`), and in 1.7–2.6 s since, over two journeys at a load average of 8
to 10.

The hooks-module samples at 00:05 and 00:26 PT on 2026-10-20 show the `ending` step
answered after 140–168 s. In both, the agent wrote a reply whose `--markup` spanned
lines and gave no `--text`; Claude Code hands such a command a socket as its stdin
that never closes, and the reply waited on it until the tool's 120 s timeout. A
command given no text now reads stdin only from a pipe or a file, directly or
through the sandbox's bridge, so that reply is refused at once (`piped_input.py`).

The hosted agent shows two kinds of status. The panel's line read Working 0.3 s
after the website adapter's journey sent its release ask, in a run in Chrome that
titled the ask in 2.2 s and replied with the page change in 16 s. Its words came
next: in `website-replies`, every turn opened with a first-person line addressed
to the user, which showed in the reply 1.1–3.7 s into the turn, and the answer
completed 3.6–14.5 s in (`timings` in each sample's metadata).

Other work has no universal budget. Status should change when the operation
changes, without timer-driven chatter. Update these readings when the kept samples
show a step has changed materially and stayed changed, not after one run.

### A corpus revision's paint

The benchmark saves `index.html` and at once runs `leaf page stamp`. The revision
reaches the tab by one of two routes, depending on which comes first:

- **The save route.** The tab's next freshness read (`LOOK_MS`, 250 ms apart)
  finds the save. The state read that follows activates the source: the server
  checks it and writes the revision. The tab then fetches the revision's document
  and patches it in. An agent's ordinary save takes this route, since `SKILL.md`
  tells it each valid save is live.
- **The stamp route.** The stamp takes the page lock first, about 150 ms after
  the save, once its process has started. The tab's read waits for the stamp's
  whole check under the lock. The state read that follows checks the same source
  again, since the server's record that a source passed its check lives in that
  process only. A stamp right after a save, or one `--from-directory`, can take
  this route.

`uv run leaf-dev bench-latency --page corpus --transition revision` reads both;
`results.json` gives each request's start and end beside the transition's, which
says which route a run took, and `uv run leaf-dev profile corpus revision` gives
the browser's tasks. Fifteen paired runs over three invocations at load 4–7 on 18
cores, on `e440ca191` against its merge base `f38882d51`:

| Route | Merge base  | Head        | Head's parts                                                     |
| ----- | ----------- | ----------- | ---------------------------------------------------------------- |
| Save  | 0.89–1.11 s | 0.64–0.79 s | state read and activation 285–310 ms, document 65, patch 215–255 |
| Stamp | 1.77–2.09 s | 1.11–1.22 s | stamp's lock until 550–640 ms, state read 225–270, patch 230–265 |

On the merge base the state read and its activation took 470–575 ms and the
document 130–160. Work that was repeated or read by no one made up most of the
difference: the check walked the page's containment once per live sample
(`passages.enclosing_ids`), anchor relocation walked both revisions in full
(`SourceReading.decided_passages`), every check judged the recorded data for
advice only `page check` prints (`validation.source.source_advice`), and the
document's delivery copied the whole page once per mark it wrote
(`revision_delivery._spliced`). The user-view report also forced the style and
layout of every hidden tab, about 280 ms 300 ms after each presentation, which
delayed the tab's next read and sent more runs down the stamp route
(`render-checks/layout.js`, `render-checks/words.js`).

The stamp route stays over 1 s. Two changes would bring it under:

- **Record that a source passed its check.** A revision could carry the identity
  of the Leaf that checked it, so any process can treat an unchanged source as
  checked, as the server's own memory does (`revisioning.py`, its header). The
  digest of the revision's inputs alone isn't enough: it covers neither the Leaf
  that checked it nor the data contracts its samples read, so it would pass a
  source a newer Leaf refuses. The same record would let a stamp that follows the
  server's activation skip its own check, about 450 ms under the lock.
- **Check outside the lock.** A stamp could check before taking the lock and hold
  it only to confirm nothing moved and to publish.

### A small page change's reply

Each harness journey asks for the same small page change twice, naming a release
for the agent to record on the board (`journey.CASES`). The release ask reaches a
harness that is **waiting**, idle until Leaf's watch or hook wakes it. The
`mid-turn` ask reaches one that is **working** on the user's own turn, during a
25 s shell command, and the harness takes it at that command's tool boundary.
Each reply is timed on the page server's clock from the comment's admission to the
reply's, and the harness's record of the session splits it
(`dev/leaf_dev/reply_phases.py`):

- **Leaf's share**: delivery, until the harness puts the comment in the agent's
  context, and the tool calls that run `leaf`.
- **Harness busy first**: in the working case, the user's command running until the
  boundary. That wait belongs to the work the user started, so the working budget
  counts the reply after the boundary.
- **Model calls**: each response the harness asked of the model, with the tool calls
  it issued. The agent's other tools, its own reads and edits, took under 0.1 s in
  every reply.

`uv run leaf-dev journey-chart --replies` tabulates the kept samples. These are
three journeys per harness on this Mac between 14:35 and 15:00 PT on 2026-10-20, at
`e4d720ce5` (main at `8df338a36` with the benchmark's change), with the comments
posted over HTTP. Other sessions' suites pushed the load average from 7 to 27 on 18
cores during the batch, which slows each `leaf` command. Codex App Server ran
#3357's delivery: an idle task takes each delivery from App Server's queue as a turn
of its own, and a working one gets a pointer from the tool hook, which the agent
reads and acknowledges with `leaf delivery read` and `leaf delivery ack`. Seconds:

| Harness          | Case    | Whole reply | Leaf's share | Harness busy first | After the boundary | Model calls | Model time |
| ---------------- | ------- | ----------: | -----------: | -----------------: | -----------------: | ----------: | ---------: |
| Claude Code      | waiting |   17.5–32.1 |      3.0–3.2 |                  0 |          17.5–32.1 |         3–6 |  14.4–28.9 |
| Claude Code      | working |   38.6–41.1 |      1.8–2.1 |          24.6–24.8 |          14.0–16.4 |         2–3 |  12.2–14.2 |
| Codex App Server | waiting |   20.3–30.2 |      1.8–3.5 |                  0 |          20.3–30.2 |         4–5 |  18.4–26.6 |
| Codex App Server | working |   44.8–50.4 |      1.2–3.7 |          24.6–25.0 |          20.2–25.8 |           4 |  18.7–22.0 |
| Pi               | waiting |   22.3–27.1 |      1.8–2.9 |                  0 |          22.3–27.1 |         6–7 |  20.4–24.2 |
| Pi               | working |   40.2–42.6 |      1.0–1.7 |          24.8–25.0 |          15.3–17.6 |         5–6 |  13.8–16.6 |

Leaf's share was under 2 s in 10 of the 18 replies. Delivery took 0.38–1.28 s
waiting and 0.19–0.47 s working; on Codex App Server it reads 0 working, since the
pointer arrives with the tool result and its read and acknowledgement count as
commands. The `leaf` commands took 0.8–3.7 s, about 0.5–0.7 s each. An earlier
batch of three journeys per harness, between 14:00 and 14:25 PT at load 6 to 10,
read the same pattern with Leaf's share 0.8–2.9 s, under 2 s in 17 of 18, and
whole replies of the same size, Codex's 2–8 s shorter. In a run before that, Claude Code ran
`leaf page check --render` twice before a waiting reply, 6.3 s each, and its Leaf
share reached 13.8 s; `SKILL.md` asks only for `leaf page check` before replying
about a revision. A call that only names the launcher counts as Leaf's too: in this
batch, Pi's `printf '%s\n' "$LEAF"` and `ls "$LEAF"`, a few milliseconds each.

The model took the rest, at 1.5–6 s a call on Pi and 2–9 s on Claude Code and
Codex. The quickest replies took two calls once the comment was in context: in a
Claude Code working reply, the first call claimed the comment with a progress
reply and made the edit, and the second checked the page and replied. The other
calls went to:

- **Reading Leaf's references.** Pi and Codex read `event-batches.md`,
  `threads.md`, `page-authoring.md` or `authoring-revisions.md` in one to three
  calls of every waiting reply, and Claude Code read the registry in one. Serving
  the page had needed none of them, and the working replies, later in the same
  session, read none.
- **Looking up the widgets.** `leaf page state`, `leaf page instructions` or
  `registry.json` took one or two calls of each waiting reply on Pi and Codex.
- **Checking apart from the reply.** In each of Claude Code's waiting replies the
  check and the reply came in separate calls; in its working replies one command
  ran both. Pi always chained
  `page check && response reply` in one command, and Codex ran the check with its
  edit.
- **Reading the pointer.** On Codex App Server a working reply spent a 3.7–4.8 s
  call on `leaf delivery read` before the work.
- **The user's own next step.** In the working case Pi and Codex ran the user's
  `printf` in a call of its own. That call belongs to the user's task, though it
  falls inside the reply's time.

The two cases differ in more than the harness's state. The waiting ask is each
session's first comment, so it reads the references and builds the record from
nothing, a new column or tile; the working ask, later in the same session, adds a
second release to the record the first one made. Part of the working case's
shorter reply after the boundary comes from that, and the comparison would need
the order reversed, or each case in a fresh session, to separate the two.

Proposed budgets for a small page change:

| Number       | Waiting                                  | Working                             |
| ------------ | ---------------------------------------- | ----------------------------------- |
| Leaf's share | under 2 s                                | under 2 s                           |
| Whole reply  | Leaf's share and two model calls (below) | the same, counted from the boundary |

The two calls: the first claims the comment with a progress reply and reads what
the edit needs; the second edits the page and replies in the same response, the
reply reporting what the check found. At the call times measured here that is
about 6–9 s on Pi and 10–14 s on Claude Code and Codex. A budget in seconds alone
would measure the model's speed, which Leaf doesn't set; the count of calls is what
Leaf's instructions and commands decide. Leaf's share rose with the host's load,
as each `leaf` command starts a fresh process.

## Status evaluations

On 2026-10-20, at `e5113c687` with this note's change, every status evaluation
passed:

| Case                                        | Claude Code | Codex |
| ------------------------------------------- | ----------- | ----- |
| `plan-shows-multi-step-work`                | 3/3         | 2/2   |
| `plan-skips-quick-work`                     | 3/3         |       |
| `parent-keeps-leaf-responsive`              | 3/3         | 2/2   |
| `parent-keeps-leaf-responsive/known-answer` | 3/3         |       |
| `parent-keeps-leaf-responsive/no-subagents` | 3/3         |       |
| `parent-keeps-leaf-responsive/during-work`  | 1/1         |       |
| `document/idle`                             | 2/2         |       |
| `document/mid-turn`                         | 2/2         |       |
| `website-replies`                           |             | 2/2   |
| `website-replies/follow-up`                 |             | 2/2   |

`parent-keeps-leaf-responsive` grades whether the page shows the delegated work
while the workers run (`delegated-work-visible`). Every run took the update in hand
with a progress reply, then left the workers' work on the page before ending its
turn, as working steps in the plan, a `--todo` reply, or both. In `during-work`,
the parent answered all three comments while it repaired the suite, its first
reply 4.5–13.7 s after each comment.
In `document/idle` the first reply came 3.9–5.6 s after each comment; in
`document/mid-turn`, where the comment waits for the turn's next tool boundary,
9.4–14.9 s.

## Proposed improvements

- **Delegated work in the panel's status:** the status stops reading Working while
  the coordinator's workers still run and its watch is live. Over an update still
  started, it reads Working for two minutes after the turn ends, then says the turn
  ended. Once a `--todo` reply has answered the update, it reads listening from the
  turn's end, and its explanation names the open to-do among what waits on the
  agent. The plan still lists the work. Claude Code's session record keeps
  `busy` while background work runs, which `activity.claimant_turn` deliberately
  ignores; reading it would let the status say the work goes on in the background.
  Whether to show that is a product decision. The
  [Thread plan](threads.md#independent-jobs-delegation-and-continuation) owns the
  broader model of delegated jobs.
- **Two model calls for a small change:** the calls "A small page change's reply"
  lists are what a reply would cut. Have serving a page read what replying to its
  comments needs, or give the first delivery the page's widget vocabulary, so the
  first reply reads no reference and looks up no widget. That changes shipped
  instructions or the delivery contract, so score it with `evals/` and read the
  journey's model calls before and after.
- **Separate the cases from the session's history:** the working ask follows the
  waiting one in the same session ("A small page change's reply"). Asking each in
  a fresh session, or the working one first, would leave the harness's state the
  only difference, at the cost of a session per case.
- **Leaf's share on real pages:** `leaf-dev response-times` reads Leaf's share from
  Claude Code's transcript, so a shell command that runs `leaf` among slower work
  counts whole, and Codex and Pi pages get none. If each `leaf` command recorded its
  own duration in the page's diagnostics, as the server records each request's,
  the page would say Leaf's share on every harness.
- **The hosted opening's cost:** whether the hosted agent's opening line delays its
  answer needs runs without one, such as an arm whose `CODEX_INSTRUCTIONS` drop the
  acknowledgement.
- **Explicit stdin:** a command given no text reads stdin only from a pipe or a
  file. That guesses the caller's intent from the descriptor, and refuses a Node
  caller, whose piped stdin is a socket. Reading stdin only when asked (`--text -`,
  `--file -`) would need no guess, at the cost of changing the shipped
  instructions' heredocs and pipelines and scoring that change.
- **Cheap claims:** test a typed harness operation against the CLI path before adding
  another interface. The [Codex brief](codex-integration.md#typed-operations) owns
  that experiment.

Move a validated rule into its existing owner and retire the corresponding part
of this brief. Keep transport evidence, work selection and settlement distinct.
