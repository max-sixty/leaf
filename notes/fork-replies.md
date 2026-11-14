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
moves to a fork that can act ("A fork that takes the work"). The measurements below
are of the fork that answered.

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
thread's model, system prompt and tools. Since Claude Code 2.1.318 `$.model.fork`
takes an effort too, and a fork at low in a session at xhigh read the whole
conversation from the cache where per-message effort reaches the model (2026-11-04,
`src/leaf/clerk.py`), but rewrote it elsewhere, as on Vertex (#5891, #5904). Both
forks now run at the session's effort and ask for a quick answer in their prompts,
each module recording its own measurement (`src/leaf/clerk.py`,
`src/leaf/forks.py`).

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

A design not yet built: a fork that does a self-contained request itself rather than
handing it over. What the session did next with the 27 hand-overs above:

| What the message needed                                                         | Messages | Could a fork take it?                                     |
| ------------------------------------------------------------------------------- | -------: | --------------------------------------------------------- |
| a `/dispatch` to a session of its own                                           |        4 | yes: the work runs elsewhere by construction              |
| a quick look: a config's history, a GitHub doc, why a rule was never added      |        3 | yes, with read-only tools                                 |
| research or a measurement taking the session minutes                            |        6 | read-only, but long enough to need its own progress lines |
| recording a decision the user made on the session's question, then acting on it |        7 | no: it changes the session's plan                         |
| work on the session's own tree, page or PRs                                     |        7 | no: it races the session's edits                          |

So a fork with read-only tools, `leaf thread reply` and `/dispatch` could have taken 7 to
13 of the 27. A forked subagent (`$.agent.spawn({ subagentType: "fork" })`) is the
mechanism: it starts from the current transcript, so it also covers the sessions
`$.model.fork` has nothing to fork in, and the module gates its tool calls at
`tool.call`. Before building on it, a probe should check whether Claude Code tells
the main thread when a subagent the module spawned finishes, since that would wake an
idle session.

Coherence decides the design more than capability does:

- One reader for related messages. Today each held thread gets its own fork, so
  twelve messages across twelve threads would get twelve independent workers. A
  fork that takes work should see every held thread of the session at once and
  decide them together, and a message arriving while it works goes to it
  (`$.session.send` to its agent id) rather than to a new fork.
- The session hears what the fork did. A reply already queues a clerk line; taken
  work needs the same line saying what was done or dispatched and where, so the
  session neither redoes nor contradicts it.
- The fork writes nothing the session is changing: no edits to its tree, page source,
  git state or PRs. Anything that would is handed over, as now.

Evals are viable at three levels, each on the harness `fork_eval.py` already has:

- Decision (reply, take or hand over): constructed cases with a `take` label, plus a
  replay set of the 33 recorded forks above, labelled by what the session did next.
- Outcome: for taken cases, a judge compares the fork's answer with the answer the
  session actually gave. Replays need read-only tools on the repository at the
  session's commit; lookups that read GitHub or the web drift between runs.
- Coherence: two-message cases (related messages in two threads, a message during
  a decision) scored on how many workers ran and whether their answers agree; and
  the main session resumed after the fork's clerk line, judged on whether it redoes
  or contradicts the fork's work. This needs a second resumed agent for each case.

The replays in "How well the fork judges" cost about $2.30 a run without tools; with
tools and a second agent, expect a comparison over 40 cases and two arms to cost a few
hundred dollars.
