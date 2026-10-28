# A feed of ready-to-approve actions

This note hands over an open design question: how Leaf could offer a feed of
actions an agent has already prepared, which the user approves, edits, dismisses
or discusses. The page beside it (`page.html`) puts the two decisions below to the
user and has a live sample of a made-up morning feed. Serve it with
`uv run leaf-dev preview --source notes/feeds/page.html --user`. Delete the note
once a feed lands and its contract moves into a reference, or once the user drops
the idea.

## The idea

Nicolas Bustamante's
[post](https://x.com/nicbstme/status/2109505834439033107) (12 October 2026) argues
that most people won't prompt their way into agent work, but they already know how
to scroll a feed and act on what they find. So the system should bring each next
useful action to them with the work done: an email already drafted, an update
ready to send. The user approves, edits, dismisses, or opens a chat to go deeper.
He also proposes sponsored cards to fund the agents, which this note sets aside: a
card the agent didn't write for the user breaks SOUL.md's "The user directs the
work".

## Every verb on a card already exists

A card is one decision with its evidence beside it, which is what an item framed
by an `lf-ask` already is (`references/authoring-on-me.md`).

| Feed card      | Leaf today                                                             |
| -------------- | ---------------------------------------------------------------------- |
| The work, done | Evidence inside an `lf-ask`: a table, a chart, a diff                  |
| Approve        | An `lf-options` pick, a suggestion's Accept, or Approve version        |
| Edit           | `lf-draft`, text the user rewrites in place, with its history recorded |
| Dismiss        | A "Not now" option or a reject, recorded as an outcome                 |
| Jump into chat | Discuss on the On view's card, or a comment on the draft's exact words |
| The feed       | The On view and `m`, which walk On me in page order, for one page only |

LangChain's [Agent Inbox](https://github.com/langchain-ai/agent-inbox) uses the
same four verbs (`HumanInterruptConfig`: accept, edit, respond, ignore), and
`notes/comparisons.md` already lists it as a human-input queue.

## What Leaf lacks

- **Nothing creates cards unprompted.** Every page answers a request, and no Leaf
  code starts an agent on a schedule. Scheduling belongs to the OS (launchd, cron)
  or the harness, not to Leaf.
- **The wake on a press exists, on Claude Code only.** When a page's claimant is a
  background job whose worker has retired, a press resumes the job with
  `claude --bg --resume` (`resume_claude_code_job` in `harness.py`, called from
  `ClaudeCodeHarness.nudge`, which `presence.nudge_unwatched` calls on admission).
  So a card approved hours later reaches the agent that wrote it. Codex and Pi
  have no equivalent.
- **No list spans pages.** All pages shows each live page's agent status. A page's
  row (`server_rows.py`) carries `{title, session_cwd, activity}`, whose counts
  are updates the agent owes; nothing from On me. `presence.other_leaves` keeps
  only rows whose server is live and whose page isn't closed, so a page with no
  server drops out.

## The decisions

**Which feed to try first.** The two options compose: a page from A would be one
source in B's list.

- **A. A "Today" page owned by one background session** (recommended first). A
  launchd job resumes one standing Claude Code session each morning. It checks
  the sources the user names and writes a card for each action, and the user's
  press resumes it to carry the action out. It needs a brief, a launchd plist and
  a page, with no change to Leaf's core, so it tests whether a pushed feed is
  worth reading before anything is built for it. One session holds every
  source's context, and cards from the user's other sessions don't reach it.
  Resuming a job that a worker still hosts starts a copy
  (`resume_claude_code_job`'s docstring), so the launchd job must message the
  live session instead.
- **B. On me across every page.** Each page's row publishes its `on_user` queue
  (`served_state/queues.py`), and All pages becomes one list of every page's
  items: simple ones answered in place, the rest opening their page at the item.
  This designs for S15 "Many pages" in `notes/what-needs-you/research.md`, which
  the user meets already without a feed, and any session or job that writes a
  page feeds it. It needs a row that outlives its server, an answer route to
  another page's server, and a rule for clearing stale items: the research counted
  58 threads left waiting in September, median age 28 days.

A treats the experience as the open question; B is the durable architecture
whatever A finds, since it makes the feed a view over items rather than a new
kind of record.

**Whether offers become cards.** Agents end replies with offers such as "say the
word and I'll open the PR", and the research found those go unanswered: no agent
thread message posed two explicit questions, and multi-part asks arrived as prose
offers. A change to `references/conversation-loop.md` could make each offer an
item with Do it and Not now, scored with `evals/` before and after. Over-asking is
the risk, which the same research found destroys the signal.

## A feed should drain

Social feeds are tuned to keep the user scrolling; SOUL.md asks Leaf to preserve
the user's attention, and the research says an empty list should mean nothing is
left to decide. So each card should expire to a recorded "not now" rather than
pile up, as [ChatGPT Pulse](https://www.eweek.com/news/openai-chatgpt-pulse/)
expires its morning cards after a day.

An approval should carry out the wording on screen when the user pressed, and
nothing binds the two today. An `lf-draft` records each `edit` of its body and
`lf-options` records only the option chosen, as separate events, so an edit made
after Send but before the agent acts leaves the approved wording unnamed. A feed
needs its approval to name the text it approves.

Related open work:
[issue #4058](https://github.com/max-sixty/leaf/issues/4058),
"Explore independent jobs", asks who owns and
continues a job's result; a feed's background pass is one such job.
