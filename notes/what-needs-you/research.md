# What needs you: research notes

Research behind [the proposal page](page.html), gathered 2026-09-29. Preview the page with:

```sh
uv run leaf-dev preview --source notes/what-needs-you/page.html --slot what-needs-you --user
```

## Empirical: how threads and Asks are actually used (55 real pages, 169 threads, Jul–Sep 2026)

- 164 of 169 threads opened by the user; the 5 agent-opened threads never got a reply.
- 58% of threads are exactly user message + one agent reply. Median agent first reply 62 s.
- Only ~3% of agent thread messages ask the user anything (9 of 279). `awaits` used on 5%
  of agent messages since it shipped; of those 11, only 5 end in a "?"; it goes stale
  (a completion report marked awaits sat "On you" 19 days), gets answered sideways, in an
  Ask, or in the terminal.
- 224 user messages in total; 9 are connectivity probes ("test", "do you see this?").
- User message kinds (215, hand-classified; primary / present anywhere in the message):
  question to agent 74/94, instruction/request 55/90, decision/answer to agent proposal
  or Ask 36/37, critique/correction/confusion 25/32, FYI 11/15, ack/thanks 11/11,
  deferral/TODO 3/11. 32% bundle kinds (e.g. decision + new
  request + deferral). 37 carry slash commands (21 `/dispatch`).
- Endings: user resolved 101 (60%), agent resolved 8, open with agent last + no awaits
  ("neither") 57, open awaits 2. Before user resolves, the last message was an agent reply
  102 times: answers ~52, finished results ~34, *promises / in progress ("Building now…",
  "Dispatched…") 18*. 73% of resolves are sweeps (within 3 min of another on the page).
  Median resolve 19.5 min after the agent message.
- The user explicitly asked whether resolving after a promise is safe: "confirm that when I
  resolve a thread, [it] doesn't discard the work, and can reopen the thread to tell me when
  the work has finished". I.e. Resolve is used as "handed off / off my list", not "done".
- Two cases of request + resolve within 9 s with no reply ever ("maybe we add a TODO…",
  "ensure we're clear about this in our CLAUDE.md") — resolve settled the obligation.
- 57 "neither" threads: median age 28 days; 44 on pages the user never resolved anything on
  (read-and-leave), ~31 are results, ~28 answers, ~9 promises of later work.
- Asks: 117 on real pages; of 104 on pages the user touched: 77 answered, 11 retired by
  agent, 16 still open. Median ~5 h to answer, in bursts. Asks drain.
- 46 threads anchored inside Asks: 15 questions before choosing ("what are the tradeoffs?"),
  13 answer the Ask in prose (agent then records the pick by hand: "I've marked the Ask
  with that choice"), 10 ask for more material ("show me sketch") = Ask blocked on agent,
  4 critique the Ask.
- Reactions essentially unused (1 real reaction; `settles` never used).
- Over-asking complaint: "this sort of thing does not need a question!"; partial answers:
  "start with #2 & #3"; "there are a lot of questions here — maybe too many? … doing what
  you can with what I've answered".

**Implication:** the thread "needs you" gap is mostly *unacknowledged results* and *requests
whose fate becomes invisible after Resolve*, not unanswered agent questions. Decisions
already flow to Asks. The seam between threads and Asks is the other gap.

## Scenario catalogue (grounded in the logs) — every proposal must handle these

- **S1 Request → promise → result.** "Make the banner quieter." Agent: "Building now…",
  later "Done — see §3".
- **S2 Question → answer.** "Why does this use a set?" Agent explains.
- **S3 Hand-off resolve.** User posts a request and wants it off their list immediately
  (resolve 9 s later); the agent must still do it and the result must come back.
- **S4 Dispatch.** "/dispatch -- fix this bug": work moves to another session/page; result
  lands elsewhere.
- **S5 Multi-question, partial answer.** Agent (or an Ask cluster) raises 4 questions; user
  answers 2 ("start with #2 & #3"), wants the other 2 to stay visible.
- **S6 Bundle.** "ok, yes, let's have the ring; and add a TODO that it may be too strong" —
  decision + request + deferral in one message.
- **S7 Thread around an Ask.** (a) "what are the tradeoffs?" before choosing; (b) prose answer
  "#1 is fine" that should answer the Ask; (c) "show me a sketch" — the Ask is blocked on
  the agent.
- **S8 Read-and-leave, return later.** 10 results the user skimmed but never acknowledged; they
  come back 3 weeks later, or never.
- **S9 Agent-initiated question in prose.** "Want me to build it on this branch?"
- **S10 Over-asking.** The agent puts something on the user that didn't need them.
- **S11 Sweep.** User clears a page's 12 threads in 3 minutes.
- **S12 Answer in another channel.** The user answered in the terminal.
- **S13 Misunderstanding.** "I thought we agreed to move these up here??" — a result the user
  rejects.
- **S14 Sign-off.** A page whose approval unblocks work: what must be zero before Approve.
- **S15 Many pages.** The user runs several pages/sessions; "what needs me" across them.


## Falsifier measurements (59 pages, 177 threads, as of 2026-09-29)

| Test | Result |
|---|---|
| Total turn: open threads "on you" when the user left after their last event | 30 threads on 24 pages; 35 of 59 pages at zero, max 3 |
| Same, at the end of the log | 58 real threads on 34 pages; median age 28 days, 70% older than two weeks; 33 of those agent messages arrived after the user's last event on the page |
| Real promises among the 18 "resolved right after a promise" | 15 |
| … with a result posted in the same thread afterwards | 0 |
| … with the result visible elsewhere on the page | 6 (version notes, a sibling thread) |
| … whose result went to another session by design | 9 |
| Promise-led agent replies that were the thread's last agent word | 24 of 41 |
| `read` data coverage | since 2026-09-22; 17 pages, 7 days |
| Resolves preceded by a read of the latest agent message | 64 of 64; median gap 0.7 min, none over a day |
| Threads read and then left with no action | 6: 3 results, 1 proposal awaiting a press, 1 promise, 1 design proposal |
| Blocked-Ask rule on the 46 threads anchored in Asks | 32 correct, 13 prose answers (hiding is right there too), 1 wrong |
| … of the 32, the user pressed the Ask after the agent's reply | 22 |
| Reading replay: messages holding more than one loop | ~26% of all user messages |
| Reading replay: debatable readings | ~31%; only 14 of 88 (sample weighted toward mixed messages) change what is on the user's list |
| Agent misreadings already in the log | 2: "consider adding … to our Glossary" parked as tracker #11 (user: "can we do this change now?"); "yes, great on both" answered with "Pick **Yes, start now** on this Ask" |
| Agent thread messages posing ≥2 explicit questions | 0; multi-part asks arrive as prose offers, which go unanswered ("tell me and I'll add it", "say the word and I'll put them up", "say /gpk … and I'll open the PR") |
| Partial answering of Ask sets | 15 of 30 bursts; of 19 leftover Asks, 7 pressed later (median 15 h), 3 retired, 4 answered in prose, 1 inferred, 3 lost with an abandoned page, 1 still live |

Implications:
- Resolve must stop settling owed work, and a request's closing event cannot be tied to its thread: results land in version notes, sibling threads, and other sessions.
- A promise must hand the turn to "agent owes work", never to the user.
- Reading is a sound receipt for results and answers, not for anything that still asks the user something.
- A prose answer needs a path to close its Ask; the agent asked the user to "press the Ask" three times.
- A cross-page list needs reading to clear results (or page-level aging), or it starts at 58 stale items.

## Research digest (three lenses: theory, review/inbox tools, agent harnesses)

### Convergent findings
1. **Three (or four) independent axes.** Whose move (turn / ball-in-court), what is owed to
   whom (commitment ledger), is it finished and who says so (closure), have I seen it
   (read). Gerrit keeps attention set ⟂ unresolved flag; Reviewable keeps "unreplied" ⟂
   "resolved"; Zendesk Pending/On-hold (turn) ⟂ Solved/Closed (lifecycle). Leaf's Resolve
   fuses closure + settles obligations + clears turn + hides — hence "agent forgets → lost".
2. **The performer reports, the customer closes.** Winograd/Flores conversation-for-action
   (request→promise→report completion→declare satisfaction), Camunda delegation
   (delegate `resolveTask` sends it back to owner for review; only owner `complete`s),
   Zendesk Solved→Closed, Bugzilla RESOLVED→VERIFIED, Linear (issues assigned to humans,
   delegated to agents: "an agent cannot be held accountable"). Agent-to-agent protocols
   (A2A, MCP Tasks, FIPA) have no acceptance step — human-facing ones all do.
3. **Two kinds of "needs you": answer vs review.** Devin (Sep 2026: Working/Ready/Blocked/
   Inactive), Claude Code agent view (Ready for review vs Needs input), Jules
   (AWAITING_PLAN_APPROVAL vs AWAITING_USER_FEEDBACK). Leaf's "neither" after an agent
   reply is where *review* goes missing.
4. **Named terminal outcomes; dismiss ≠ done.** WS-HumanTask: Completed / Exited ("no
   longer interested") / Obsolete (skipped); MCP elicitation: accept / decline / cancel
   ("prompt again later"); ServiceNow "No longer required". Leaf's Resolve over "please also
   do X" is a Withdraw nobody chose.
5. **State derived from typed moves, not optional flags.** Linear derives session state from
   the *kind* of the last agent activity (elicitation → awaitingInput, response → complete);
   Intercom Fin classifies on whether the last agent message was an answer or a question;
   12-factor agents: every turn emits `request_human_input` or `done_for_now`. Leaf's
   `--awaits` is an optional modifier whose omission is silent — probably the single biggest
   cause of the thread problem (inference).
6. **Whoever replies declares the next state with the reply** (Zendesk "Submit as …",
   Gerrit reply dialog picks whose turn, Reviewable draft dispositions, GitLab resolve
   checkbox in reply box). Derive by rule, show the reason, allow one-click override
   (Gerrit ~90% accurate by design; GitLab built an attention set and *cancelled* it because
   automatic toggles moved attention without consent).
7. **Split multi-part into separately settled units.** No system models "half answered"
   inside one message; Critique/Gerrit settle per comment, Reviewable per participant,
   AskUserQuestion keys answers per question, OpenAI SDK lets unresolved interruptions remain.
   Free text replying to a structured ask is first-class (Linear select dismissed by free
   text; AskUserQuestion `response`; Agent Inbox `response`) → "superseded by reply".
8. **Zero means nothing undecided, not everything finished.** GTD (inbox→zero by deciding;
   delegated items go to Waiting For, not "done"), Inbox Zero, Masicampo & Baumeister 2011
   (a specific plan removes the open-loop intrusion — only if plans are credible),
   Newport shutdown ritual. Ghibellini & Meier 2025 meta-analysis
   (https://www.nature.com/articles/s41599-025-05000-w): no general memory advantage for
   unfinished tasks (Zeigarnik), but a robust pull to resume them (Ovsiankina, ~67% vs
   50%). Waiting-on-agent is a separate, trusted list, shown grey, not
   counted (GitLab Active/Inactive, Reviewable red/grey/striped counters).
9. **Deferral waits on a condition *or* a clock.** Linear triage snooze (time or new
   activity), Reviewable partial-publish defers until new revision/comment, Superhuman/HEY
   "if no reply by", Front send & snooze, Gerrit 3.9 `attentionSet.readdAfter`
   (https://www.gerritcodereview.com/3.9.html; re-adds the owner after inactivity — the
   item comes back when the other side goes quiet).
10. **Silence rules differ by slot.** Winograd: satisfaction "may be taken for granted if some
   time goes by"; CA: an unanswered question is "officially absent". So: after a completion
   *report*, silence can lapse to accepted (Zendesk 4-day auto-close, Fin "assumed resolved"
   24h — but label it "assumed", Fin's overcounting is a complaint); after a *question*,
   silence is an absence that needs pursuit.
11. **Two acknowledgement markers.** Bangerter & Clark 2003: "uh-huh/yeah" = continue within
   the project (horizontal); "okay/all right" = consent to close the project (vertical).
   Leaf's settling 👍 conflates them. Max's three cases = directive / horizontal / vertical.
12. **Closing is a pre-closing + a pass** (Schegloff & Sacks 1973): proposing closure gives the
   other party a last free slot for "unmentioned mentionables". When the user resolves, the
   agent gets one closing turn ("you also asked for X, which I haven't done — dropping it?").
13. **Graded response relevance** (Stivers & Rossano 2010): required / invited / none. Binary
   `--awaits` too coarse; only required counts toward "needs you" and blocks sign-off.
14. **Let the machine label, the human correct.** The Coordinator (explicit speech-act labels
   typed by users) was rejected in the field; Suchman critiqued it as a disciplinary ledger;
   Winograd conceded explicit structure imposes on unstructured (email-like) work. Cohen et
   al. 2004: "these difficulties are avoided if messages can be automatically annotated by
   intent." The LLM agent already reads every message → it declares "I read this as two
   requests: (a)…, (b)…", user corrects. Google Docs "suggested action items" did this with
   one-click confirm.
15. **Give each open item a next action, not a colour.** Bellotti's Taskmaster (CHI 2003):
   "action balls gave a sense of to-doness but did not help planning … one still had to
   examine the contents". Each row should say *what* the user must decide/check.
16. **Over-asking destroys the signal.** Claude Code users approve 93% of permission prompts;
   Copilot moved to explicit @mention so users can leave thoughts without triggering work;
   OpenHands maps IDLE→AWAITING_USER_INPUT so everything looks like it needs you. The count
   only means something if agents rarely put things on it and confirming costs one key.
17. **Who closes depends on who might vanish.** Support desks close optimistically (Help Scout
   default Closed after reply; customer reply reopens) because requesters vanish; code review
   wants requester close because authors rush. Stack Overflow's requester-only close with no
   timer → 47% of questions never accepted. Leaf has both risks → agent proposes, user
   ratifies cheaply, timer backstops, reply reopens.
18. **Hard close → new linked item** (A2A terminal tasks can't restart; refinement is a new
   task with referenceTaskIds; Zendesk follow-up ticket after Closed). Keeps the user's Done
   decision intact.
19. **Explicit address / batching.** Copilot's @mention; Gerrit/GitHub pending reviews publish
   a batch. Leaf's "a user reply always hands the thread to the agent" cannot express "note
   to self" or "wait until I've finished reviewing".
20. **Bankruptcy and bulk** (Superhuman Get Me To Zero, Autofocus dismissal, BuJo migrate-or-
   drop, GTD weekly review): stale items get a forced, recorded migrate-or-drop decision.
