# Answering thread messages from a fork

The goal, the user's on 2026-10-31: when the user asks a question or continues a
thread, and the answer needs no tool calls, the reply arrives fast enough that they
stay in the thread, whether the agent's session is idle or busy. Today the median
first reply takes 17 s when the session is idle and 21 s when it is busy, and the real
answer 48 s and 100 s ([waits on real pages](leaf-run-sessions.md#waits-on-real-pages)).

On main, `src/leaf/forks.py` holds the states a thread moves through, the hold and the
working line a fork posts, and `hooks/claude-code.ts` (`forkReply`) makes the fork. This
note holds the research behind it: what Claude Code lets a hooks module fork, measured,
and how well the fork judges what to answer. The main thread is the session's own
conversation, as against the forks and subagents made from it.

On 2026-11-05 the user took answering out of this fork. A `$.model.fork` fork can't
call tools, so it now posts only the agent's working line and hands every message to
the session, and the message reads On it from the moment the hold starts. Answering
moves to a fork that can act ("A fork that takes the work"), and the line's fork now
also judges whether one could take the work. The measurements below are of the fork
that answered.

## What a hooks module can fork

A probe module, loaded with `claude -p --plugin-dir`, forked the conversation from its
own code while the main thread's foreground Bash command ran (Claude Code 2.1.316,
Opus 5.5, 2026-10-31; the scripts are in `.tmp/fork-probe/` of the `forked-replies`
worktree, which may be gone). Each fork was asked a side question the conversation
could answer. The main turn finished normally in every run.

`$.model.fork({ prompt })` sends the main thread's last request again with `prompt`
after it, denies every tool call, and returns the reply's text whole. Leaf's clerk
already calls it at each turn's end (`src/leaf/clerk.py`).

| Session                   | Context | Forks | Time to answer         | Output tokens | Cache read / written / uncached             |
| ------------------------- | ------: | ----: | ---------------------- | ------------: | ------------------------------------------- |
| Fresh                     |     44k |     1 | 1.9 s                  |            32 | 43.8k / 0.2k / 0.2k                         |
| Fresh, after reading code |    225k |     3 | 5.6–6.0 s              |       204–302 | 206k / under 0.4k / 19k                     |
| Resumed copy              |    274k |     3 | 13.9 s, then 4.5–4.8 s |       210–228 | first 33k / 227k / 14k, then 260k / 0 / 14k |

The main thread's last request, mid-turn, predates the response being acted on, so a
fork doesn't see the tool call now running: at 225k all three forks said the running
command hadn't started. At a turn's end the fork does see the turn's final reply; in
one run it quoted an invented word the reply had just given.

A fork reads the main thread's cache up to the breakpoint before its last request and
pays that request's new part uncached each time. The main thread writes one-hour
cache entries (`ephemeral_1h` in every run), so a session idle for longer than that,
or just resumed, makes its first fork write the whole context, as the resumed copy's
first fork did; the forks after it read that fork's entry. The fork keeps the main
thread's model, system prompt and tools. Its effort can differ without missing the
cache: since Claude Code 2.1.318 `$.model.fork` takes one, and a fork at low in a
session at xhigh read the whole conversation from the cache (2026-11-04,
`src/leaf/clerk.py`), though a `claude -p --resume --fork-session` fork at
`--effort low` had read none of it (2026-10-24). Both forks now run at low, each
module recording its own measurement (`src/leaf/clerk.py`, `src/leaf/forks.py`).

`$.agent.spawn({ prompt, subagentType: "fork" })` starts a background subagent with
the main thread's current transcript and all its tools. It started within 40 ms of the
call and answered in 3.7–8.6 s over four runs at 44k–274k (the first run's result
survives only in its transcript, `agent-a4e7eb29990913a44.jsonl`), reading the context from
the cache, its time following its output (197–739 tokens). Its transcript stays at
`<session>/subagents/agent-<id>.jsonl`, which `$.session.messages({ agentId })` reads.
Under `claude -p` the main thread got no notification when it finished; the module
hears its answer at `turn.complete`, carrying its `agentId`.

`$.session.append` of a user row, made while the command ran, reached the main thread
with the command's result in its next request. In that one run the main thread
reported the row and treated its question as answered.

## Costs and limits

- From send to reply, on recorded thread messages (below): under the shipped prompt
  a median 12 s for a reply and 6 s for a hand-over; the first prompt's replies took
  17 s. Most of it is output, a median 829 tokens, 77% of them thinking at the
  session's xhigh effort. Short side answers of 200–300 tokens took 4.5–6 s (above).
  Reading the context from cache or writing it cold changed the time little. The
  follower's look and two `leaf` processes add 0.12–0.62 s each under load
  ([Leaf's share](user-feedback-responsiveness.md#a-small-page-changes-reply)).
- While the main thread's cache entry lives, each fork reads the context from it and
  pays the main thread's last request uncached, 14–19k tokens in the runs above.
- A handed-over message reaches the main thread one fork decision later. An idle
  session wakes that much later; a busy one notices only if a tool boundary falls
  inside that wait.
- The fork answers from the main thread's last request, with the same model, and
  has no tools. A forked subagent (`$.agent.spawn`) could also answer questions
  that need a look at files, with its writes denied at `tool.call`, and would keep
  a transcript the main thread could be pointed at.
- Claude Code only. The Leaf side is harness-neutral: Codex App Server has
  `thread/fork`, and Pi's extension could resend its session (`clerk.py`).
- `$.model.fork` has nothing to fork until the main thread sends a request: in a new
  process, after `/clear` (its doc comment), and, as observed below, after a
  compaction or Claude Code's away summary. A forked subagent starts from the
  transcript instead, so it would cover those.

## How well the fork judges

Thread messages replayed at the moment each arrived: a copy of the session's transcript
cut there, resumed under `claude -p` with every tool denied, given the prompt
`forks.reply_prompt` builds from the page log cut at the message. Each case was
labelled from what the session did next before any fork ran. The first set holds 25
messages from 15 sessions (Oct 20–30), 15 idle and 10 mid-turn; the fresh set 15 from
15 other sessions (mostly Oct 10–19), 9 idle and 6 mid-turn. By those labels only 8 of
the 40 were answerable from the conversation alone, though the fork rightly answered
several more whose answer the conversation already held, where the session looked
anyway.

| Prompt and cases                      | Answered right | Answered wrong | Handed over right | Handed over, could have answered |
| ------------------------------------- | -------------- | -------------- | ----------------- | -------------------------------- |
| first wording, first set (25)         | 10             | 4              | 10                | 1                                |
| shipped wording, first set (15 rerun) | 6              | 0              | 6                 | 3                                |
| shipped wording, fresh set (15)       | 7              | 1              | 7                 | 0                                |

No reply promised work. The first wording's four wrong answers:

- Three worked an answer out instead of finding it: the rule "answer only when the
  conversation holds everything the answer needs" let the fork count quoted code,
  page text and its own earlier explanations as everything, and state inferences as
  facts. One invented that CI finds Chrome through `CHROME_BIN`; one said a theme
  reached the panel only partly where the session checked and found it reached both;
  one swapped the pointer and touch figures for a card's controls.
- One explained a decision the user had just made on the page's open ask. A reply
  settles the thread and a settled message wakes no idle session, so the decision
  would have gone unrecorded.

The shipped wording hands over when the fork would have to work the answer out for a
case the session never looked at, and when the user answers or decides something the
session asked. It was written after those four and rerun on 15 of the first set, so
that row is in-sample; it costs three hand-overs the session would have answered from
its conversation. The fresh set is out of sample: one wrong answer in eight replies
(95% interval about 0.3–53%), so the replays show the wording isn't unsafe without
pinning its error rate down. That wrong answer repeated a survey's claim in the
conversation ("notes aren't deleted when their design lands"), which the session then
checked against git history and found mostly false; a clause handing over "when the
user questions a claim the conversation makes" would have caught it and the earlier
theme case, and is untested.

Under the shipped wording a reply took a median 12 s on the fresh set (5–18 s) and a
hand-over 6 s (4–10 s). Every replay wrote the context cold. The replays cost $126.

The replay differs from a live fork: it resumes a transcript copy rather than resending
the session's exact last request, without plugins, MCP servers or hooks, writes the
whole context cold, rebuilds page data from today's page directory, and assumes xhigh
effort. Each case ran once, and one agent labelled and scored them all. The scripts and
per-case records are in `~/.tmp/leaf.forked-replies/replay/` on the machine that ran
them.

## Forks on real pages

From 1 to 5 November, 58 thread messages on 26 pages (`leaf-dev response-times`, whose
`fork_*` and `delivered` rows read this). Forks ran on 40: they answered 6, with the
agent's first words a median 10.6 s after sending; handed 27 to the session, a median
3.2 s after sending; and failed on 7. The session's own first words on those 27 came a
median 35 s after sending, 140 s at p90, and the thread showed nothing from the agent
until then. The session opened 26 of them with a line, and each time the fork's reason
(`why` in its `fork_reply` record) had already named the same work, such as "needs a
new survey of real pages' event counts" against the session's "Surveying real pages'
log lengths and growth".

All 7 failures were `nothing-to-fork`, which Claude Code 2.1.318 returns when it holds
no main-thread request to resend. Each came after the session had sent none for 1.8 to
23 hours, and after one of these since its last: a compaction (3), Claude Code's away
summary (2), or a restart of Claude Code (1 shown by a version change, 1 presumed). A
fork after 5.9 idle hours with none of them succeeded. Each of those sessions was idle,
so the hand-over's nudge woke it in about 2 s, and a failure cost only the answer a fork
might have given.

From 6 to 9 November, under the fork that only writes the line, 19 thread messages on
5 pages: 9 got the line, the 7 of them `response-times` times a median 2.4 s after
sending (1.9–5.3 s); 1 failed `nothing-to-fork`; 1 got an answer from a session still
running the module it started with on 4 November; and 8, all on one session, got no
line. That session's pages follower had run since 4 November from its worktree's
checkout, which moved past two protocol bumps (41 to 42 on 5 November, 43 on 8
November), while the session's hooks ran the checkout's newer Leaf, which reads the
follower's lane lease, written at 41, as no one's (`leases.lease_speaks_here`; checked
on 9 November). Twice the follower, still at 41, held a message and listed it, and the
fork's step, under the newer Leaf, found it not held and asked no fork, so the hold ran
out with no line ("no answer within 30 s"). One came while the session ran a 70 s
foreground poll, and the user saw the agent's first words after 64 s. Nothing recorded
why the other 6 had no fork. The follower now ends once the session's hooks would run
another Leaf than its own, and the module starts it again (`hooks.cmd_pages`); the
page now notes whether admission held each message and whether its lane was up
(`fork_hold`), and each fork Leaf asks for (`fork_asked`), which `leaf-dev timeline`
reads.

A message no fork answered reads Delivered until the session's first model call ends, a
median 14 s and 41 s at p90. In 12 of 14 idle sessions that call posted the one-line
reply `conversation-loop.md` asks for first, so the wait is the thinking before it:
0.5–6k output tokens at xhigh, about 95 a second. On a busy session a message first
waits for the next tool boundary, a median 16 s and 99 s at p90; the longest were
foreground commands (a `sleep 280`, benchmark scripts). The hold made 6 of 26 busy
hand-overs miss a boundary, adding 42 s across all of them.

## A fork that takes the work

A design being built in steps: a fork that can act takes a thread message whose work
is independent of the main thread's, owns it until it answers, and then tells the
main thread what it did. The main thread stays in charge: it hears of each fork, and
can steer or stop it.

### What the session did with the hand-overs

What the session did next with the 27 hand-overs above:

| What the message needed                                                         | Messages | Could a fork take it?                                     |
| ------------------------------------------------------------------------------- | -------: | --------------------------------------------------------- |
| a `/dispatch` to a session of its own                                           |        4 | yes: the work runs elsewhere by construction              |
| a quick look: a config's history, a GitHub doc, why a rule was never added      |        3 | yes, with read-only tools                                 |
| research or a measurement taking the session minutes                            |        6 | read-only, but long enough to need its own progress lines |
| recording a decision the user made on the session's question, then acting on it |        7 | no: it changes the session's plan                         |
| work on the session's own tree, page or PRs                                     |        7 | no: it races the session's edits                          |

So a fork with the session's tools, kept off what the session is changing, could have
taken 7 to 13 of the 27.

### What Claude Code gives the module

Probes in interactive Claude Code 2.1.318 on 2026-11-05, with a module that spawned a
fork from a slash command (`$.agent.spawn({ prompt, subagentType: "fork", name })`):

- The fork's first turn starts within 10–16 ms. It has the session's transcript,
  model and tools, and runs beside the main thread, idle or busy.
- Its shell commands run in the main session's environment (`CLAUDE_CODE_SESSION_ID`
  and `CLAUDE_PID` are the session's), so a `leaf` command it runs acts for the
  session, as any subagent's does (`harness.ClaudeCodeHarness`).
- Every hook but the one that spawned it sees its turns and tool calls with its
  `agentId`, so another plugin's module can deny one of its calls (`tool.call`
  returning `deny`, which the fork reads and works around) or rewrite it. The plugin
  that spawned it can't: in 2.1.322 Claude Code skipped all of Leaf's `tool.call`
  hooks for a fork Leaf spawned from the pages follower, logging "tool.call skipped:
  re-entry (the plugin's own code raised it; origin leaf)", while its
  `turn.complete` hook ran, and so did `hooks.json`'s command hooks, PreToolUse and
  PostToolBatch, whose payloads name the fork (`agent_id`) and whose PreToolUse can
  rewrite the call (`updatedInput`).
- `$.session.send({ to: { agentId } })` reaches it as a coordinator's message at its
  next tool boundary, and it acts on it.
- The main thread learns nothing of it: its transcript gets no row for the spawn, and
  the fork's first completion sends it no notification and wakes no idle session. The
  main thread finds it by name with ListAgents, and a SendMessage to that name resumes
  it; that resumed run's completion does notify the main thread and starts a turn.
- The fork can message the main thread itself: its SendMessage to `main` arrived as
  an `<agent-message from="…">` and started a turn on the idle main session 60 ms
  later (2026-11-07). The module's `$.session.send` to its own session id fails as
  "no live session"; Leaf's prototype tells the main thread through the clerk's
  queued lines instead, which wait for its next tool boundary or prompt.

### The design

The user's model, 2026-11-10: forks handle the questions and small tasks they can;
significant work becomes an obligation the agent owes, which the main thread
prioritizes; and the main thread coordinates, running work bigger than a message in
subagents. Each thread message goes one of three ways:

| The message                                                               | Where it goes                                  | Of the 27 hand-overs above |
| ------------------------------------------------------------------------- | ---------------------------------------------- | -------------------------: |
| a question or small task a fork can finish: a lookup, a dispatch          | a working fork answers it                      |                       7–13 |
| significant work: the session's tree, page or PRs, or research of minutes | an obligation, which the main thread schedules |                       7–13 |
| needed now: the user's answer to the session's own question, or steering  | the main thread, at once                       |                          7 |

Research taking minutes sits on the line: a fork can do it, but it is long enough to
need progress lines of its own, so whether it is small or significant is the fork's
call on the message. Input the main thread needs now can't wait as an obligation,
since it changes the work the obligation would queue behind.

- **Deciding.** The fork that writes the working line, which reads the message
  against the conversation in about 3 s, sorts it. Today it judges two ways, `take`
  where the work needs nothing the session is changing (its files and branch, the
  page's source, its pull requests), settles none of its open questions, and waits
  on nothing it is running, and `hand_over` otherwise; step 4 splits `hand_over`
  into an obligation and needed now. A working fork may still find the work bigger
  than it looked and make it an obligation.
- **Doing.** On a small task the module spawns a fork of the session with the thread
  as Leaf would deliver it. The fork works with the session's tools in a turn of its
  own and answers with its own `leaf thread reply`.
- **Owning.** The fork holds the thread as any turn holds what it picked up. Its
  take is a pickup in the page log naming the fork's turn, with the receipt. The
  turn whose pickup of a thread's waiting messages is newest holds the thread,
  whether it is the main thread's or a fork's, and every reader of received input
  asks one function which turn that is (`forks.holding_turns`). A fork's turn may
  act only on the messages it holds or no turn holds, and one rule checks each of
  its writes as it is made (`forks.refuse_unheld`): its pickups (its take, its tool
  boundary and its acknowledgement of a pointer), its replies and its starts. For
  that rule an answered message is held by the turn whose pickup of it is newest, so
  a fork may repeat its own answer but not answer again a message the main thread
  took over and answered. The
  turn closes as the fork's run ends, and lapses when unrenewed for the working
  grace, as a main turn's stamp does. The main thread picks up a message a fork's
  turn holds only once that turn has closed or lapsed, and that pickup takes the
  thread over, so the fork's later pickup, reply or start on it is refused. While
  the fork's turn runs, the message reads as work in hand, the main thread is
  neither handed it nor reminded of it, and a further message in the thread goes to
  the fork at its next tool boundary.
- **Acting as itself.** Leaf ties work to the turn it runs in: a pickup or start names
  a turn, and lapses when that turn ends. A fork runs in the session's environment,
  so Leaf keeps a turn per agent of the session (`state.AGENT_TURNS`) rather than one
  per session. Leaf's PreToolUse hook adds the agent's id after the `leaf` that
  begins each `leaf` command of an agent the session has run a turn for, open or
  ended (`leaf --agent-id`), so a fork's starts and answer name its turn, and its
  tool boundaries (its PostToolBatch, which names it) carry the thread's further
  messages, as the main thread's do. A `leaf` command runs as one of three actors:
  the main thread, when it names no agent; an agent with an open turn, in that turn;
  or an agent whose turn has ended, whose replies, starts and acknowledgements are
  refused rather than made as the main thread's. The mark follows the agent rather
  than its turn, so a fork resumed or running late after its turn ended is still
  refused. A subagent the session ran no turn for, such as one of the main thread's
  own workers, goes unmarked and acts as the main thread. A known agent's Bash call
  that runs `leaf` anywhere but as its first word, as `cd x && leaf …` does, is
  denied with the instruction to run each `leaf` command on its own, since it would
  act as the main thread's and a mark spliced into it could land in quoted text.
- **Obligations.** A significant task becomes a to-do on its thread that the agent
  owes until it ends it, as a session's `leaf thread reply --todo` opens today. A
  working fork opens one with the same command when the work proves bigger, and the
  to-do stays the session's after the fork's turn ends. Who opens it for a message
  the line fork sorts as significant, which has no working fork, is step 4's design.
- **Telling the main thread.** As the fork's run ends, the module tells Leaf, which
  judges each thread by the messages the fork's turn picked up, and Leaf's clerk
  queues a line for the main thread saying which way it went: the fork answered; it
  answered and opened a to-do, named with its text, which the main thread now owes
  and schedules; or it gave the thread back or failed, and the main thread owes the
  answer, with the fork's answer reference. The line says the thread owes nothing
  only where nothing waits in it and no to-do on it is open, and it waits for the
  main thread's next tool boundary or prompt. The proposal is the fork's own
  SendMessage to `main`, which wakes an idle session at once and can say what the
  fork did beyond those outcomes, so the session neither redoes nor contradicts it.
- **Follow-ups.** A later message in a thread a fork answered goes to the same fork,
  resumed by name, rather than to a new fork, so a flurry of messages in one thread
  makes one worker. Leaf's message to it lists what the main thread did on the page
  since the fork's run, which the fork's transcript lacks, and the fork can
  SendMessage the main thread to ask about it. (Proposed; the user's choice is
  open.)
- **The main thread as coordinator.** Told by name as each fork takes a thread, the
  main thread can steer it or stop it with SendMessage, or take the thread over. It
  takes obligations in the order it judges and runs those bigger than a message in
  subagents, as the shipped skill's "Stay responsive" already asks. A fork never
  changes the session's files or plan.

Landing steps 1 to 3 on `main` needs a protocol bump: a Leaf at protocol 43 doesn't
know that a fork's pickup holds the message, and picks the message up again for the
main thread while the fork works.

### Steps

1. **The judgment** (built): the working-line fork answers `{"line", "work"}`; Leaf
   records `work` in the page's diagnostics (`fork_reply`) and still hands every
   thread over, and `fork-reply/*` scores the judgment against each case's label.
   Real pages then show how often a fork would take a message, and what the session
   did with those.
2. **Doing and joining** (a prototype, only with `LEAF_FORK_WORK=on` in Claude
   Code's environment): the taken state (`forks.TAKEN`), the fork spawned on `take`,
   follow-ups passed to it, its answer posted at the join, and the clerk's lines to
   the main thread. `leaf-dev journey claude-code --fork-work` runs it live: on
   2026-11-05 the question "What did I ask you to do with this page?" had the fork's
   line 2.1 s after sending and the working fork's answer at 6.9 s, after 4.6 s of
   work, while the session stayed idle; the session's next turn took the message in,
   settled, and didn't answer it again. The two requests in the run, judged
   `hand_over`, went to the session as before. On 2026-11-09 the same run had the
   line at 2.0 s and the working fork's answer at 5.1 s, with no tool call.

   A review of the prototype found its ownership record the wrong primitive. TAKEN
   says who has a message outside the log, and only `forks._held` and
   `delivery.deliverable` read it. Every other reader of received input reads the
   log: once a receipt for later input moves the cursor past a taken message, the
   main session's next prompt records a pickup for it as an acknowledged update it
   owes (`hook_transport.pick_up_acknowledged`), which ends the hold, fences out the
   fork's answer and tells the session to answer the message itself. The follower's
   cache doesn't see TAKEN change either, and a TAKEN entry outlives a fork that a
   module reload, a failed join or an exit lost. Each could be patched, but each
   patch would teach one more reader about a second record of who holds a message.

3. **A turn per agent** (built, behind the same flag): the fork's ownership is in
   the log. Leaf keeps a turn per agent the session runs beside its main thread
   (`state.AGENT_TURNS`). The take, under the hold's fence, opens one for the fork
   and records that turn's pickup of the thread, with the receipt and the answer
   reference of a delivery frozen for it; the module spawns the fork with that
   delivery, then tells Leaf which agent runs the turn (`forks.started`). While the
   turn runs, the activity fold reads the pickup and the fork's starts as work in
   hand; the main thread's Stop hook, watch and prompt neither hold its turn over the
   message, remind it nor take it in again (`activity.agent_holds`); and its
   deliveries leave out what the fork holds (`forks.held_inputs`). The fork's
   pickups, replies and starts are each checked as they are written against which
   turn holds the thread (`forks.refuse_unheld`), so a fork that lost its thread to
   the main thread can neither take it back with a late acknowledgement, nor answer
   it, nor start on it. The turn is believed only while renewed within the working
   grace, as a main turn's stamp is.

   Leaf's own PreToolUse hook puts the agent's id after the `leaf` that begins each
   command of an agent the session has run a turn for (`hooks.agent_command`,
   `leaf --agent-id`), so a permission rule allowing `leaf` commands still matches
   it. The fork's `leaf thread reply` then posts as the agent's from its turn. The
   hook marks an agent whose turn has ended too, so its reply, start or
   acknowledgement is refused rather than made as the main thread's. The fork's
   PostToolBatch, which every other subagent's still skips, renews its turn and
   hands it the thread's further messages (`hook_transport.carry_agent_turn`).

   As the run of a fork it spawned ends, the module tells Leaf (`forks.ended`), which
   closes the fork's turn and judges each thread by the messages the turn picked up.
   An answered thread is done. A fork can also answer with a to-do
   (`leaf thread reply --todo`), which is the session's and stays open after the
   fork's turn ends, while the fork's start on it lapses with the turn; the main
   thread hears that the fork answered and opened it, by its text, and now owes it. A
   thread the turn still holds is the main thread's to answer, with the fork's answer
   reference, and one another turn picked up since is that turn's. `TAKEN`, the
   posted-for-it answer, the module's deny and its `$.session.send` of follow-ups are
   gone.

   The turn opens at the take rather than at the fork's `turn.start`, so the hold
   passes to the fork's pickup in one transaction under the page's lock, with no moment
   in which neither holds the message. The module was to mark the fork's commands
   itself, but Claude Code runs none of a plugin's `tool.call` hooks for an agent the
   plugin spawned (above): the first live run on 2026-11-10 had the fork's reply go in
   unmarked, as the main thread's. In the second, Claude Code applied the PreToolUse
   hook's `updatedInput` ("modified tool input keys: [command, description]" in its
   debug log). Each run's "What did I ask you to do with this page?" had the line
   at 4.0 s and 3.2 s, the fork's pickup in its own turn in the same instant, its
   own `leaf thread reply` answer at 9.9 s and 9.6 s, and its turn ended 9.2 s after
   it started, all while the session stayed idle. Its next turn didn't answer the
   message again. That was on a host at load 8 to 20. The journey's
   `fork-follow-up` step then sent a further message 0.1 s after a fork took a
   question it had to look up in the page's source: the fork's first tool boundary,
   5 s later, picked it up in the fork's turn, and the fork answered it 17.0 s after
   it was sent, with the main session idle throughout.

   The protocol bump that landing these steps needs (above) belongs in the change
   that lands them, not on this branch, where main's protocol baseline would keep
   conflicting with it. Codex confirmed the misreading by running the merge base's
   `read_plans` and `pick_up_acknowledged` against a fork's pickup: they reminded the
   main thread of the message and recorded a main-thread pickup while the fork worked.

4. **Sorting, obligations and follow-ups**: the line fork sorts three ways; a
   significant message becomes a to-do on its thread; a fork tells the main thread
   what it did; a thread's further messages go to the fork that answered it; and
   the shipped instructions say what forks and the main thread each do, scored with
   `evals/` before and after.

5. **Measuring it**: an outcome eval comparing a fork's answers with the session's on
   replayed hand-overs, and the decision and coherence evals below, before forks that
   act become the default.

Evals are viable at three levels, each on the harness `fork_eval.py` already has:

- Decision (take or hand over): the constructed cases' `work` labels, plus a replay
  set of the 33 recorded forks above, labelled by what the session did next.
- Outcome: for taken cases, a judge compares the fork's answer with the answer the
  session actually gave. Replays need the session's tools on the repository at the
  session's commit; lookups that read GitHub or the web drift between runs.
- Coherence: two-message cases (related messages in two threads, a message during
  a decision) scored on how many workers ran and whether their answers agree; and
  the main session resumed after the fork's clerk line, judged on whether it redoes
  or contradicts the fork's work. This needs a second resumed agent for each case.

The replays in "How well the fork judges" cost about $2.30 a run without tools; with
tools and a second agent, expect a comparison over 40 cases and two arms to cost a few
hundred dollars.
