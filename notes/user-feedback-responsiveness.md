# Feedback responsiveness evaluation

The delivery and activity lifecycle is implemented. Its owners are
[session lifetime](../src/leaf/session-lifetime.md),
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
# --case working sends the release ask while the user's own turn runs.
uv run leaf-dev journey claude-code [--case working]
uv run leaf-dev journey codex-app-server [--case working]
uv run leaf-dev journey codex-queue [--case working]
uv run leaf-dev journey pi [--case working]
uv run leaf-dev journey website-adapter
uv run leaf-dev journey-chart
# Where each reply's time went, waiting and working, by harness.
uv run leaf-dev journey-chart --replies [--since ISO]
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
times the comments of its later steps and attributes each reply's time to Leaf, the
harness and the model (`dev/leaf_dev/reply_phases.py`). Each run
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
on the save route (below).

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
- **The stamp route.** The stamp publishes the revision first. The state read
  that follows checks the same source again, since the server's record that a
  source passed its check lives in that process only. A stamp in place checks
  before taking the page lock and holds it only to confirm and publish
  (`publishing.py`, its header), so a tab read during that check takes the save
  route instead; the stamp then checks again outside the lock and names the
  revision the read activated. A stamp with `--replace` writes and checks the
  source under the lock, so the tab's read waits for its whole check.

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

The table's stamp route is a stamp that checked under the lock, which a stamp in
place no longer does. A script standing in for the tab measured it on each
arm's served corpus: save, start `leaf page stamp`, poll `/api/state` every
250 ms until it names the new revision, then fetch that revision's document.
With the first poll fixed 500 ms after the save, when the merge base's stamp
held the lock, the state answer came a median 2.25 s after the save and the
document's last byte 2.98 s on the merge base `f00911ed1`, and 1.19 s and 1.93 s
once the stamp checked outside the lock: eight alternating runs at load 17–33.
With the first poll at a random phase both arms took the save route, at a median
0.75 s and 0.77 s to the state answer. At load 20–46 the browser benchmark could
not tell the arms apart (2.7–3.1 s medians, spreads over 2 s), and neither route
has been read again at load 4–7.

One change would bring the rest of the stamp route under 1 s and drop the work a
stamp repeats after the page's own activation:

- **Record that a source passed its check.** A revision could carry the identity
  of the Leaf that checked it, so any process can treat an unchanged source as
  checked, as the server's own memory does (`revisioning.py`, its header). The
  digest of the revision's inputs alone isn't enough: it covers neither the Leaf
  that checked it nor the data contracts its samples read, so it would pass a
  source a newer Leaf refuses. Leaf has no identity for its Python checker yet;
  `runtime_selection.ServingRuntime.identity` covers the browser runtime alone.
  The same record would let a stamp with `--replace` spare the state read after
  it a second check, and a stamp that follows the server's activation skip its
  second check, about 450 ms of work beside the tab's document fetch and patch.

### A small page change's reply

Each harness journey asks for a small page change, naming a release for the agent
to record on the board, as the session's first comment. The ask reaches the harness
in one of two cases (`--case`), each journey running one in a session of its own so
both start from the same page and context: **waiting**, idle until Leaf's watch or
hook wakes it, or **working** on the user's own turn, during a 25 s shell command,
where the harness takes it at that command's tool boundary. Each reply is timed on
the page server's clock from the comment's admission to the reply's. That time is
the benchmark, and the harness's record of the session attributes it to where it
went, each moment once (`dev/leaf_dev/reply_phases.py`):

- **Leaf's share**: delivery, until the harness puts the comment in the agent's
  context; the time each `leaf` command records in the page it acts on
  (`leaf_command`, from its launcher's start to its exit); and Leaf's hooks, where
  the harness times them.
- **Harness busy first**: in the working case, the user's command running until the
  boundary. That wait belongs to the work the user started, so the working budget
  counts the reply after the boundary.
- **Harness**: the harness's own work between a tool's result and its next request.
- **Model**: for each request, the **wait** for the stream's first output, then its
  **generation**, reasoning included, until the response's last tool call.
- **Other tools**: the agent's own reads and edits.

Each harness's record gives a different part of that exactly:

| Harness          | Exact                                                                                                                                                               | Inferred or missing                                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Claude Code      | Its debug log times each request, its first byte, and each of Leaf's hooks; the transcript times each tool call and result and gives each response's output tokens. | Thinking is redacted, so generation is not split into thinking and the visible output; the tokens give its rate.                           |
| Pi               | The first stream event of each response and its output tokens, heard on Pi's stdout.                                                                                | No request time: Pi's dispatch, and the prompt hook Leaf's extension runs at each turn boundary, fall in the wait. Reasoning is hidden.    |
| Codex App Server | Each tool item, each response's token usage, and each of Leaf's hooks with its duration.                                                                            | No request or stream start, and reasoning is hidden, so the model's time is unsplit; it includes the wait, the reasoning and the dispatch. |

`uv run leaf-dev journey-chart --replies --since 2026-10-22T13:43-07:00` tabulates
the batch: three journeys per harness and case on this Mac between 13:43 and 14:12 PT
on 2026-10-22, at `cef6a5bc2` with this note's change, the comments posted over HTTP
and the load average between 21 and 29 on 18 cores. Each column's parts add up to its
whole reply: seconds, mean over the runs, with each part's share of the whole.
The batch has no `codex-queue` runs, so its Codex columns time only the experimental
App Server route, not the queue route the desktop app and IDE use.

| Seconds, mean (share)      | Claude Code, waiting | Claude Code, working | Codex App Server, waiting | Codex App Server, working |          Pi, waiting |          Pi, working |
| -------------------------- | -------------------: | -------------------: | ------------------------: | ------------------------: | -------------------: | -------------------: |
| Whole reply (range)        | **29.5** (16.3–36.2) | **45.7** (41.7–50.2) |      **19.4** (14.5–22.1) |      **44.3** (39.2–48.7) | **26.8** (24.9–28.9) | **54.4** (49.7–59.3) |
| After the boundary (range) | **29.5** (16.3–36.2) | **20.9** (17.0–25.4) |      **19.4** (14.5–22.1) |      **19.5** (14.6–23.8) | **26.8** (24.9–28.9) | **29.4** (24.6–34.2) |
| Harness busy first         |               0 (0%) |           24.8 (54%) |                    0 (0%) |                24.8 (56%) |               0 (0%) |           25.0 (46%) |
| Delivery                   |             0.4 (1%) |             0.3 (1%) |                  0.1 (1%) |                    0 (0%) |             0.5 (2%) |             0.2 (0%) |
| Leaf's commands            |            3.0 (10%) |             0.5 (1%) |                  0.4 (2%) |                  0.7 (2%) |             0.9 (3%) |             1.0 (2%) |
| Leaf's hooks               |             1.6 (5%) |             1.2 (3%) |                  1.0 (5%) |                  1.3 (3%) |            not timed |            not timed |
| Harness                    |             0.1 (0%) |             0.1 (0%) |                         — |                         — |                    — |                    — |
| Model: wait                |            3.5 (12%) |             2.9 (6%) |                         — |                         — |             2.2 (8%) |             2.3 (4%) |
| Model: generation          |           20.8 (70%) |           15.1 (33%) |                         — |                         — |           23.1 (86%) |           25.7 (47%) |
| Model, unsplit             |                    — |                    — |                17.8 (92%) |                17.4 (39%) |                    — |                    — |
| Other tools                |             0.3 (1%) |             0.8 (2%) |                    0 (0%) |                  0.1 (0%) |             0.1 (0%) |             0.1 (0%) |
| Leaf's share               |            4.9 (17%) |             2.0 (4%) |                  1.6 (8%) |                  2.0 (4%) |             1.4 (5%) |             1.2 (2%) |
| Model calls                |                  3–7 |                  3–5 |                         4 |                       3–4 |                  7–8 |                  7–9 |
| Output tokens              |            1224–2996 |            1338–1980 |                  588–1071 |                   591–902 |              823–941 |              743–962 |

The model took 82–92% of every waiting reply, and most of that is generation. On
Claude Code each request waited 0.5–1.3 s for its first byte, and then generated at
80–170 tokens a second, so a call's time follows its output: 130–925 tokens a call,
nearly all of it thinking, since the visible output is a short command or edit.
Forty-seven earlier Claude Code waiting replies, kept as evidence from 2026-10-21 and
22 and timed from the same debug log, split the same way: of 28.4 s on average,
generation took 67%, the wait 19%, Leaf's hooks and the harness 6%, and Leaf's
commands and the agent's tools 7%, over 4.6 calls.

Leaf's own share was 1.2–4.9 s on average:

- **Leaf's hooks**, 1.0–1.6 s a reply on Claude Code and Codex, 3–5% of it. Claude
  Code runs Leaf's PostToolBatch hook after every batch of tool calls and its
  PreToolUse hook before every `leaf` command; Codex runs its PostToolUse hook after
  every tool call. Each took 120–620 ms at this load, and a claimed session's
  PostToolBatch hook runs Leaf whole, past the launcher's gate. A `leaf` command
  that matches more than one of the PreToolUse registrations' `if` patterns, as
  `L=…/bin/leaf; $L thread reply` does, runs the hook once per match, in parallel.
- **Leaf's commands**, 0.3–1.2 s, except where Claude Code ran
  `leaf page check --render` before replying, which took 8.1 s in one of three
  waiting replies here and 7.5–12.8 s in 6 of the 47 earlier. A call that reads
  the saved screen follows it.
- **Delivery**, 0.1–0.5 s.

Codex's other cost Leaf decides is a refused reply. In one of its three waiting
replies here, and at some step of 16 of 58 Codex journeys kept on this Mac since
2026-10-20, the agent wrote `tone="success"` on a board column. It had read
`page instructions` and the registry entry for the column, and neither then listed
the layer's tones. The reply was refused, and the agent edited and replied again, one
more call. Since #3690 and #3718, `page instructions` names the words each declared
attribute takes ("`tone` takes one of: `ok`, `warn`, `danger`"), and the vendored
schema gives them as its `enum`.

Proposed budgets for a small page change, in seconds:

| Number       | Waiting    | Working                       |
| ------------ | ---------- | ----------------------------- |
| Leaf's share | under 2 s  | under 2 s                     |
| Whole reply  | under 15 s | under 15 s after the boundary |

The quickest replies show 15 s is reachable on today's models: Claude Code's
quickest waiting reply took 16.3 s and Codex's 14.5 s, and Claude Code's quickest
working reply 17.0 s after the boundary. Each mean misses it, by 4–15 s. The model's time
varies widely from run to run, so a change is read from the part it moves, measured
directly, and from the whole reply over enough runs to see past that spread. Leaf's
share rises with the host's load, as each `leaf` command and hook starts a fresh
process: an earlier batch at a load average near 27 read 1.0–3.7 s.

## Proposed improvements

- **Delegated work in the panel's status on Codex and Pi:** on Claude Code, a
  session record still `busy` after the turn ends keeps the status reading Working,
  "in the background" (#3370, `activity.claimant_turn`). Codex and Pi publish no
  such record, so there the status stops reading Working while the coordinator's
  workers still run. The
  [Thread plan](threads.md#independent-jobs-delegation-and-continuation) owns the
  broader model of delegated jobs.
  Declined for Codex: reading Codex's state database (`$CODEX_HOME/state_5.sqlite`)
  for the threads a task spawned, so the status read "in the background" until they
  ended. [#3854](https://github.com/max-sixty/leaf/pull/3854), unmerged, holds the
  code. The case was rare: 7 of 3,035 turn endings on one Mac had a spawned turn
  still running a minute later. The database is not a published interface, and a
  Codex migration (one looks under way) would switch the feature off silently while
  its test, which builds the schema by hand, kept passing. Codex's public transcript
  names spawned threads but missed 6 of 259.
- **A shorter reply:** the parts of "A small page change's reply" Leaf decides are
  its hooks, about 0.2 s at each tool boundary on Claude Code and Codex; and the 8 s of
  `page check --render` where an agent runs it before replying. Measure each change
  by the part it moves and by the whole reply over enough journeys.
- **The hosted opening's cost:** whether the hosted agent's opening line delays its
  answer needs runs without one, such as an arm whose `CODEX_INSTRUCTIONS` drop the
  acknowledgement.
- **Cheap claims:** test a typed harness operation against the CLI path before adding
  another interface. The [Codex brief](codex-integration.md#typed-operations) owns
  that experiment.

Move a validated rule into its existing owner and retire the corresponding part
of this brief. Keep transport evidence, work selection and settlement distinct.
