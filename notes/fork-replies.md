# Answering thread messages from a fork

The goal, the user's on 2026-10-31: when the user asks a question or continues a
thread, and the answer needs no tool calls, the reply arrives fast enough that they
stay in the thread, whether the agent's session is idle or busy. Today the median
first reply takes 17 s when the session is idle and 21 s when it is busy, and the real
answer 48 s and 100 s ([waits on real pages](leaf-run-sessions.md#waits-on-real-pages)).

This note holds what Claude Code lets a hooks module fork, measured, and a design
that is not built yet. The main thread is the session's own conversation, as against
the forks and subagents made from it.

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

## Design

**A fork answers a thread's waiting messages.** Leaf answers a thread with one reply,
which settles every message it holds; the newest message carries the thread's answer
(`delivery.current_responses`). So when the user sends a message in a thread on a page
a Claude Code session holds, the hooks module forks the conversation with
`$.model.fork` for the thread's unanswered messages together, passing them and the
thread as Leaf would deliver them. Code decides which threads a fork takes: those
whose unanswered messages are all still undelivered, none handed into a turn or
started by the main thread. A thread the main thread already owes stays with it. A
message that arrives while a fork runs drops that fork's answer and starts a fork for
the thread with both. Each fork starts from the main thread's latest request, and the
thread's earlier messages, earlier forks' replies included, come from the page log, so
a follow-up sees the exchange before it even where the main thread hasn't yet.

**The fork decides.** Whether a message can be answered without tools is a judgment
only the model can make, so every eligible thread goes to a fork, which answers
`{"reply": …}` or `{"hand_over": …}`. It hands over requests for work, questions that
need a look at files or command output, and anything whose answer depends on the work
the main thread is doing now, and it promises no work. The fork can't see the tool
call now running, so its prompt names it: the module sees each `tool.call` the main
thread makes. Forks for different threads run side by side, rather than one at a time
as the clerk's do (`forking` in `hooks/claude-code.ts`).

**Leaf holds the messages while the fork decides.** The fork lane is the module's
follower process while it holds a lease, as the watch holds the wait lease
(`leases.take_wait_lease`); the pages follower, made to wake as a message is admitted
instead of polling every 2 s, would hold it and print each thread to fork. While the
lane is live, a message a fork may take isn't deliverable to the main thread until the
fork replies or hands it over, or until a bound longer than a first fork's 13.9 s,
counted from that fork's start, passes. The condition would go in
`delivery.deliverable`, which the hook carry (`hook_transport.read_plans`), the watch
and the nudges after it read, and the same check would go in the nudge at admission,
`presence.nudge_unwatched`, which runs without it. The decision has to come at
admission: the watch wakes the session the moment a message arrives
(`session.watch_between_turns`), so a hold taken once the follower has seen the
message comes too late. The hooks, the watch and the server each read `deliverable` in
their own processes, so a hand-over is recorded where the watch's reading stamps it,
beside the page or among its inputs, and the watch wakes on it at once rather than at
its next revival check. A fork that fails (`api-error`,
`empty-reply`, `aborted`, or `nothing-to-fork` after `/clear`) hands over at once, and
a hand-over nudges a session no watch follows, since the nudge at admission held back.
A session without the module, and every other harness, delivers as today. The page
shows the messages Queued for Claude until the reply.

**The reply is the agent's.** Leaf posts the fork's text with
`thread.post_reply(page, {"responds": id}, text, settlement=Receipt(only_if_unclaimed=True), claimed_session=…)`,
as `fail_answer` does, so it reads as the session's reply and settles the thread. It
writes nothing once a turn has picked the message up or it no longer owes an answer,
and it raises `ReceiptRefused` once another session claims the page, which the poster
drops. `Receipt`'s docstring, "A harness's failure receipt", would then describe one of
its two uses.

**The main thread learns at its next step.** A message settled before delivery still
reaches the main thread at its next prompt or tool boundary, with the reply in the
thread's digest, and never wakes an idle session (`session.wake_inputs`). A line in
the clerk's queue (`clerk.QUEUED`) says the reply came from a fork of the
conversation, so the main thread neither repeats it nor reads it as words it doesn't
remember. A tool-less fork's conversation is the main thread's context plus that one
exchange, so the main thread needs no reference to it.

The design reuses the clerk's two-step exchange (`leaf hook --fork`: Python writes the
prompt, the module forks, Python reads the answer), the delivery's thread digest,
`post_reply`, the delivery of settled input, and the clerk's queue. It adds the hold,
the lane's lease, the hand-over record, a follower that wakes on admission, and the
fork's prompt and answer schema.

**Forks with tools come later.** A forked subagent (`$.agent.spawn`) could answer
questions that need a look at files, with its writes denied at `tool.call`. That is
where a fork kept for a whole thread pays off: it keeps its own reads and caches its
own tail, where a tool-less fork pays the main thread's last request uncached on every
message, and the line to the main thread would name its transcript.

## Costs and limits

- From send to reply about 5–7 s for a 200–300-token answer at 200–275k context while
  the main thread's cache entry lives: the fork's 4.5–6 s above, plus the two `leaf`
  processes, 0.12–0.62 s each under load
  ([Leaf's share](user-feedback-responsiveness.md#a-small-page-changes-reply)). After
  an hour idle, or just after a resume, the first fork writes the whole context:
  13.9 s and 227k tokens at 274k.
- While the main thread's cache entry lives, each fork reads the context from it and
  pays the main thread's last request uncached, 14–19k tokens in the runs above.
- A handed-over message reaches the main thread one fork decision later. An idle
  session wakes that much later; a busy one notices only if a tool boundary falls
  inside that wait. A wedged fork loop holds each message for the whole bound.
- The fork answers from the main thread's last request, with the same model and
  effort, and has no tools.
- Claude Code only. The Leaf side is harness-neutral: Codex App Server has
  `thread/fork`, and Pi's extension could resend its session (`clerk.py`).

## Before it is on by default

Replay recorded thread messages at their arrival through the fork's prompt, as the
clerk's replays did (`~/.tmp/leaf.agent-channels/replay/`), and compare each with the
main thread's later reply: answered and right, answered and wrong, or handed over. A
wrong answer costs the most, since the user may act on it. A replay of a message that
arrived mid-turn shows the fork the last request without the response being acted on,
as `$.model.fork` does. Then time whole replies with `leaf-dev journey claude-code`,
with and without `--case working`.

Open: whether a fork that hands over a request for work posts a line saying the work
will follow, which commits the main thread to it; and whether Escape aborts a fork the
follower's loop makes, since `$.model.fork` resolves `aborted` when the turn whose hook
forked is interrupted, and the follower starts from `turn.start`, `tool.call` and
`turn.complete` hooks. Nobody has measured it.
