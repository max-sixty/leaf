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
resolve the address. A settled retry should not briefly appear active. During
delegation, retain the original work and the newer queued count while the observer
can still prove the delegate is live.

Read deterministic sequence and state at their owners: projection tests for
sent/queued/opened/active/stale/settled evidence; real gestures for local results;
agent traces for claim ordering. `leaf-dev journey` is the vertical test: it times a
real request on any harness from the page's own log, and on each harness target also
times the comments of its later steps and splits the agent's work on each into
delivery, model and tool phases. Each run keeps its sample in
`$XDG_STATE_HOME/leaf-dev/journey.jsonl` on its machine.

## Latency targets and readings

The targets are proposed budgets. The readings are this Mac's runs on 2026-10-20,
on main at `e5113c687` with this note's change, with the load average between 6
and 12 on 18 cores: `bench-latency --tree --runs 3` for the paint rows, and for the
rest two journeys per harness with the comments posted over HTTP, ranges covering
every comment of every step. The journey reads pickup but not the receipt before
it, so the receipt row has no reading of its own; an idle session's pickup bounds
it.

| Transition                                          | Target                                      | Reading on 2026-10-20                                                              |
| --------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------- |
| Gesture to local result                             | Same rendering turn; under 100 ms           | triage board 10–44 ms; corpus 72–132 ms, comment median 105 ms                     |
| Acceptance to visible receipt                       | Next state application; under 1 s           | not read apart from pickup                                                         |
| Turn entry to visible pickup, idle session          | Without waiting for model output; under 1 s | 0.1–0.8 s on every harness                                                         |
| Input in model context to accepted claim            | Before substantive work; under 2 s          | first command; 3.3 s (Pi) to 5.8–10.5 s (Claude Code) after the comment; see below |
| Status or result write to browser paint             | Next state application; under 1 s           | status 16–76 ms, reply 87–183 ms; revision 262–277 ms, corpus 1.06–1.89 s          |
| Comment admission to thread title                   | under 2 s                                   | Claude Code 1.2–2.7 s, Pi 2.0–2.7 s, Codex App Server 3.1–5.7 s                    |
| Comment admission to reply, for a small page change | under 7 s                                   | Claude Code 23–36 s, Codex App Server 21–23 s, Pi 30–42 s                          |

The claim row counts from the comment's admission, so it includes the agent's first
model call. On Claude Code and Pi the claim, a progress reply, is the turn's first
command, ahead of any read or edit. On Codex App Server the agent posts no progress
reply; the page reads Working from the harness's stream 2 s after the comment and
names each command as it runs.

Two paint readings miss: the corpus's comment paints in a median 105 ms, and a
revision of the corpus, a page far larger than a user's, paints in 1.06–1.89 s.
Codex App Server titles in 3.1–5.7 s against 2 s, where the others are near it.

The reply target is out of reach for any harness, and Leaf's part of the time is
small. In the release step, delivery and tool calls together took 0.3–2.6 s; the
model took the other 21–40 s, over five to ten calls, to read the page, edit it,
check it and reply. Leaf can shorten a reply only by needing fewer model calls.
`SKILL.md` and `conversation-loop.md` ask the agent to run `leaf page check` before
it replies about a revision, and Claude Code did, as a call of its own. The reply
command checks saved edits for errors but does not report the advice findings or
run the browser check that `page check` does.

A comment sent during a shell command is picked up at the turn's next tool boundary:
about 25 s later in the journey, when its command ends (36–39 s on Codex App
Server), and answered within 11 s after that.

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
- **The reply budget:** decide whether the 7 s reply target should count Leaf's
  share alone (delivery and tool time) or the whole reply, and if the whole reply,
  which model calls a small page change should need. One call to cut: have
  `leaf response reply` report what `leaf page check` would, and drop the
  instruction to run the check first.
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
- **Claim admission:** check whether the claim door can atomically require an
  outstanding subject, avoiding an active flash for a retry that was settled in
  the meantime. Reproduce the race before changing admission.

Move a validated rule into its existing owner and retire the corresponding part
of this brief. Keep transport evidence, work selection and settlement distinct.
