# Answering thread messages from a fork

The goal, the user's on 2026-10-31: when the user asks a question or continues a
thread, and the answer needs no tool calls, the reply arrives fast enough that they
stay in the thread, whether the agent's session is idle or busy. Today the median
first reply takes 17 s when the session is idle and 21 s when it is busy, and the real
answer 48 s and 100 s ([waits on real pages](leaf-run-sessions.md#waits-on-real-pages)).

The `forked-replies` branch builds it: `src/leaf/forks.py` holds the states a thread
moves through, the hold and the reply, and `hooks/claude-code.ts` (`forkReply`) makes
the fork. This note holds the research behind it: what Claude Code lets a hooks module
fork, measured, and how well the fork judges what to answer. The main thread is the
session's own conversation, as against the forks and subagents made from it.

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
thread's model, system prompt, tools and effort, since any difference misses the
cache: a `claude -p --resume --fork-session` fork at `--effort low` read none of it
(2026-10-24).

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
- The fork answers from the main thread's last request, with the same model and
  effort, and has no tools. A forked subagent (`$.agent.spawn`) could also answer
  questions that need a look at files, with its writes denied at `tool.call`, and
  would keep a transcript the main thread could be pointed at.
- Claude Code only. The Leaf side is harness-neutral: Codex App Server has
  `thread/fork`, and Pi's extension could resend its session (`clerk.py`).

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
