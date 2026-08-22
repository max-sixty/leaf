# Notes on nearby projects

Maintainer notes rather than a published page. Each section was read from that project's
own materials on the date it names, and nothing here is checked by CI, so it dates from
that day and will drift. The landscape was last swept on 2026-08-21.

Anything that hands an agent's work to a person in a browser answers three questions:
what the document is made of, where it lives, and how the reader's reply gets back to the
agent. Leaf's answers are authored HTML, a directory on your machine, and a
host-specific wait inside the session: background completion in Claude Code, an exact
unified-exec session kept inside the active turn in Codex.

## Plannotator

Read on 2026-08-21, from the repository and its own docs.
[Plannotator](https://github.com/backnotprop/plannotator) is a local, browser-based
review surface for coding agents, wired into nine of them through their own hooks. When
the agent proposes a plan, renders HTML, or finishes writing code, the work opens in a
browser, the reader marks it up, and the annotations go back to the session as
structured feedback. Apache-2.0 and MIT, started December 2025, 7.9k stars. It is the
nearest neighbour leaf has on the loop, and it reached the hosts leaf hasn't. Its frame
is narrower: what it opens is a plan, a document, or a diff, where a leaf page is
whatever shape the work needs — a board the reader drags, a dashboard ticking over while
a job runs.

|             | Plannotator                                                                                                                                                                 | leaf                                                                                                                  |
| ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Document    | Whatever the agent already produced, opened for markup: a plan caught at the plan hook, a markdown file or folder, a fetched URL, an HTML file rendered as-is, a diff, a PR | Authored HTML against a widget vocabulary, published as numbered versions, each with a changelog note to step back to |
| Home        | A temporary server the `plannotator` binary runs on your machine, opened in your browser; plans, drafts and history under `~/.plannotator/`                                 | A page directory on your machine, served where your session reached it, behind a key                                  |
| Return path | Each harness's own hooks; plan mode blocks on the review, and the annotations return to the session as structured feedback                                                  | Comments, drags and picks appended to an event log, returned to the session by its own `leaf wait`                    |
| Reach       | Claude Code, Codex, Copilot CLI, Gemini CLI, OpenCode, Kiro, Droid, Amp, Pi                                                                                                 | Claude Code and Codex                                                                                                 |

The return path is the same bargain, bought host by host. Plan mode needs no command at
all: each harness's plan hook opens the review surface and the agent blocks on it, which
is exactly the constraint every project here runs into. Plannotator paid for it nine
times — a plan hook on Claude Code, an experimental `Stop` hook on Codex, automatic hook
configuration on Gemini CLI from v0.36.0, plugin managers or hand-written config for the
rest — behind one installer that detects what is on the machine and writes each host's
hooks, skills and slash commands. That is the honest answer to what leaf's own reach
would cost.

What opens in the browser is the difference. Plannotator reviews what the agent produced
anyway — the plan it was about to print, the diff it just wrote, a markdown file, a
fetched URL, an HTML file rendered as-is under `--render-html`. leaf's agent writes a
page for the page's sake, against a vocabulary. Neither is free: because Plannotator
takes the artifact as it finds it, it has no vocabulary to check, so the quality of an
HTML artifact is the model's problem, and the answer is a companion skill library —
[`effective-html`](https://github.com/plannotator/effective-html), six skills for
wireframes, prototypes, plans and diagrams, 1.7k stars of its own. That is the
lavish-axi bet at a larger scale: guidance the agent reads, where leaf writes
declarations the lint and the render gate read.

The split over what survives a revision is the same one, and sharper. Plannotator keeps
version history with diffs between plan revisions and a read-only archive of past plan
decisions, so nothing is lost — but each invocation is its own review. A comment does
not re-anchor into the next revision, and a decision the reader made does not replay
onto it. leaf's whole design is that the log outranks the document, which is what a
thread crossing versions and a dragged card surviving v4 both rest on.

Two things it has that leaf has nothing for. It is a diff reviewer as much as a document
surface — uncommitted changes, GitHub PRs, GitLab MRs, a GitButler workspace by stack or
branch layer, Jujutsu and Perforce — with AI reviews that post their comments onto the
diff for a human to triage. And it can hand a plan to someone else: small markdown
compressed into the URL fragment, larger shares as AES-256-GCM ciphertext on a
self-hostable paste service on the PrivateBin model, with a hosted Workspaces product as
the stated direction for teams. A leaf page reaches one reader on one machine.

## lavish-axi

Read on 2026-08-12, from the repository rather than a site.
[lavish-axi](https://github.com/kunchenguid/lavish-axi) opens an agent-written HTML file
in a local browser chrome, lets the reader annotate elements and text selections, and
returns what they queued through a long poll the agent runs. Its premise is the one
leaf starts from: "HTML is the new markdown", and the loop on such a file otherwise
falls back to "screenshots and long responses for 'tell me what to change'". Of the
projects here it answers the three questions most nearly the way leaf does, so the
differences are further in.

|             | lavish-axi                                                                                                                              | leaf                                                                                                                            |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Document    | One HTML file the agent overwrites, watched on disk and live-reloaded; no design system injected, so it renders the same opened directly | Authored HTML against a widget vocabulary, published as numbered versions, each with a changelog note to step back to           |
| Home        | The file where it already sits, served by a detached local server on loopback                                                             | A page directory on your machine, served where your session reached it, behind a key                                            |
| Return path | A blocking `lavish-axi poll` the agent leaves in the foreground                                                                           | A background task that wakes Claude Code; an exact unified-exec wait Codex polls inside the active turn                         |
| Reach       | Any agent that can run a CLI, through `npx -y`, with SessionStart hooks for four hosts and Agent Plugin registration for three clients    | Claude Code and Codex                                                                                                           |

Both projects arrived at the same constraint on the return path. Lavish's skill tells the
agent to keep the poll in the foreground, and allows a background one "only through a
harness-native tracked background-job facility whose completion result is guaranteed to
resume or notify the same agent", ruling out `nohup`, `&` and `disown` by name. That is
leaf's bargain written as a rule for the agent to follow; leaf spends its host coupling
on being that facility, and its hooks hold the session to the loop. One requirement,
enforced in two places, and the reach row is what each of them paid for it.

The deeper split is what survives a revision. In lavish nothing on the page outlives the
send: an annotation is captured, queued as a pill, and delivered as a prompt, and the
artifact carries no marks afterward. The file the agent rewrites is the whole of the
document's state, and `artifact_revision` is an internal counter scoping load tokens and
layout warnings rather than a version a reader can step back through. Leaf's log outranks
the document, so comments stay anchored across versions, the agent's reply lands in the
margin beside the passage it answers, and a dragged card or a pick replays onto every
later version.

The anchors follow from that. Lavish captures a `{selector, path, offset}` boundary at
each end of the selection, plus the text collapsed to single spaces, which is enough to
hand the agent a target in source it wrote moments ago. It never resolves one again: a
reload drops a text card rather than restore it, because that "could point the annotation
at different text". Leaf has to find the same passage in every later version to keep the
mark painted and the thread attached, so it stores `{node, start, end}` segments, reads
them the same way from the file and from the DOM, and confirms an occurrence by its
context rather than by document order. Neither anchor is doing the other's job.

They also disagree about whether the page has a vocabulary. Lavish injects no design
system on purpose, so an artifact opened through the CLI and one opened straight from the
filesystem draw identically; `lavish-axi design` and seven playbooks (`diagram`, `table`,
`comparison`, `plan`, `code`, `input`, `slides`) are guidance the agent reads, and
interactivity comes from native controls plus `data-lavish-action`,
`data-lavish-question` and `window.lavish.queuePrompt()`. Leaf goes the other way: 28
bundled tags in a registry a project or a user overlays, whose declarations drive the
lint, the render check, export and replay together. Freehand buys any page the agent can
imagine; a vocabulary buys a page the machine can check and replay.

Each has capabilities the other hasn't. Lavish turns every rendered Mermaid diagram into
an editable Excalidraw whiteboard whose scene and edit summary go back to the agent, and
it inlines local assets into a standalone export, or publishes that to a third-party
host. Leaf has versions and the changelog, threads the agent answers in place, replayed
state, `report` for a page that ticks over as work finishes, and a lint that refuses a
page whose ids moved or whose rewrite didn't retract what rested on it.

Layout checking is the one that looks like a gap and mostly isn't. Lavish measures the
live DOM in the reader's browser after fonts and finite animations settle — page
overflow, controls outside the viewport, text clipped by a clipping ancestor, text drawn
over — suppresses everything explicable, and files what survives in an inbox with a
lifecycle, where the reader batches a repair into one tagged prompt.
`version check --render` already fails a version on most of that class, and does it as a
gate before the URL goes out rather than as an inbox after. What the vocabulary can't
reach is content- and reader-dependent: leaf draws each version at one viewport
(`RENDER_VIEWPORT`, 1200x900) in both colour schemes, so nothing a phone reader sees is
ever rendered. The width is the gap, not the detector.

Two smaller differences worth recording. Lavish is an npm package whose chrome bundles
React, Excalidraw, mermaid and Tailwind through esbuild, delivered on demand by `npx -y`;
leaf has no build step, one `uv` script and one ES module, installed by the host from the
repository. And their URLs differ in kind: a lavish session key is `sha256` of the file
path truncated, an identifier rather than a secret, with the loopback bind as the
boundary, while leaf mints `secrets.token_urlsafe(16)`, because a leaf server binds every
interface when the session was reached over SSH.

## Workbench

Read on 2026-07-31. [Workbench](https://workbench.md/) is a hosted, multiplayer markdown
workspace: a doc at
its own private link that agents and people edit together, with comments anchored to exact
text, suggestion mode, a board agents claim cards off, live cursors, and an append-only
activity feed. Its premise is that the document is the interface — "it's all markdown
underneath", and "the doc is the API".

|              | Workbench                                                                                                                | leaf                                                                                                                                                                          |
| ------------ | ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Document     | Markdown with fenced components — board, chat, sheet, chart, custom widget — edited in place, with named versions to restore from | Authored HTML, any structure the page needs, changed by the agent publishing a new version — each with a changelog note to step back to — or by the user working an affordance it offers |
| Home         | Hosted, at a private link                                                                                                  | A directory on your machine, served where your session reached it, behind a key                                                                                                     |
| Return path  | An HTTP long-poll the agent holds open                                                                                     | A background task that wakes Claude Code; an exact unified-exec wait Codex polls inside the active turn                                                                             |
| Reach        | Anything that speaks HTTP                                                                                                  | Claude Code and Codex                                                                                                                                                               |
| Built for    | A team of agents and people coordinating                                                                                   | One session presenting to one person                                                                                                                                                            |

The two return paths are closer than the hosting difference suggests. An agent watches a
Workbench doc by holding an HTTP long-poll open: `GET /api/docs/DOC_ID/events?since=SEQ&wait=55`,
which "returns the moment an event lands past `since`". Leaf's `wait` tails the
page directory on disk and exits on the first event the agent hasn't seen. Different
transport, same bargain: one call that blocks until the user does something. Leaf
acknowledges the event separately, only after a complete, untruncated wait result enters
model context.
Workbench also offers webhooks and a supervised watcher, for wake-ups that outlive the
agent's process.

What the HTTP surface gives Workbench is reach: "any agent that can fetch a URL can work
here — no SDK, no plugin", which covers Claude, Codex, Cursor and curl alike. Leaf's
coupling to the agent host is the opposite bet, and what it gets in return is arrival in
model context: on Claude Code a finished background wait wakes or joins the session; on
Codex the agent keeps the handover turn active and polls the exact wait session. Either
can take "skip that one" into account before the next decision. It costs a host-specific
loop, and Leaf runs on those two hosts and no others.

## html-effectiveness

Read on 2026-07-31.
[html-effectiveness](https://github.com/anthropics/html-effectiveness) is a gallery of
standalone HTML examples — code review, status reports, slide decks, diagrams, small
editing UIs — each "a self-contained `.html` page (no build step, no dependencies)". It
shares leaf's premise that a page carries more than a wall of terminal text, and it
closes the loop through the reader: the editing UIs hold their state client-side and
"always end with an export button that turns whatever you did in the UI back into
something you can paste into the agent or commit". Leaf replaces that paste with a
live return path.

## CopilotKit

Read on 2026-08-20, from the repository and its own docs.
[CopilotKit](https://github.com/CopilotKit/CopilotKit) is the frontend stack for
agent-native applications: SDKs for React, Angular, Vue and React Native, a runtime you
mount in your own app server, and sixteen documented backend integrations, LangGraph and
the Claude Agent SDK among them. It is also the home of
[AG-UI](https://github.com/ag-ui-protocol/ag-ui), the event protocol those integrations
speak — 28 typed events streamed over SSE and validated with Zod. Thirty packages in the
monorepo and a Python SDK, MIT, 36.9k stars, over 1,400 commits in the thirty days
before this read. The line they draw between the MIT packages and the commercial
Enterprise Intelligence Platform is durable data: whatever needs a database sits on the
platform's side.

It is the furthest project here from leaf, and the one that shares the most terminology
with it: both call what they do generative UI, and both mean the agent decides what
appears. The three questions don't decompose the same way, because CopilotKit has no
document. What it hands the reader is an application someone built and deployed, and
what the agent contributes is which of that application's components appear and what
data fills them. So the table wants two rows the others didn't need: who the agent is,
and who is reading.

|             | CopilotKit                                                                                                                                                                                                   | leaf                                                                                                                  |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Document    | Components the developer wrote and registered ahead of time; the agent chooses which of them render and fills their props. Freehand HTML exists too, sandboxed in an iframe inside a chat message            | Authored HTML against a widget vocabulary, published as numbered versions, each with a changelog note to step back to |
| Home        | The application, wherever you deploy it; the runtime mounts in your own app server (Next.js, Express, Hono, Bun, Deno, Workers)                                                                              | A page directory on your machine, served where your session reached it, behind a key                                  |
| Return path | A chat message, a press on a rendered component, an answer to a paused tool call, or a write to shared state, streamed over AG-UI to the agent your runtime called                                           | Comments, drags and picks appended to an event log, returned to the session by its own `leaf wait`                    |
| The agent   | One your runtime calls: LangGraph, Mastra or CrewAI that you deploy, the built-in loop over the Vercel AI SDK, a Claude Agent SDK process, or a Claude Managed Agent whose loop and workspace Anthropic runs | The coding session already at your terminal                                                                           |
| The reader  | Your users, as many at once as the app has; threads last as far as the runner you configure — memory by default, SQLite locally, durable on the commercial platform                                          | The one person that session is working with, until the session ends                                                   |
| Reach       | React, Angular, Vue and React Native; Slack and Teams as managed channels, with SDK adapters for Discord, WhatsApp and Telegram                                                                              | Claude Code and Codex                                                                                                 |

CopilotKit's docs sort six generative-UI primitives along one axis. Controlled is where
the developer wrote the component and the agent picks which one and what data goes in
it; declarative is where the agent emits a schema composed against a catalog the
developer registered; open-ended is where the UI comes from somewhere else entirely, an
MCP server, and the app sandboxes it. leaf is declarative in that scheme, with prose
freehand and widgets from the catalog, at the scale of a page rather than a card, and
with the catalog open to the same agent that writes the page.

That makes the two catalogs close enough to read side by side. CopilotKit's is
`createCatalog(definitions, renderers)`: a Zod schema and a description per component, a
React or Lit renderer for each, and TypeScript checking that the two halves match.
leaf's registry is a JSON Schema per `lf-` tag, with theme rules and an optional ES
module beside it. Both check the agent's use of the vocabulary before it reaches a
screen — Zod on the tool arguments, `version check` on the markup. What differs is when
the vocabulary is written, and by whom. A CopilotKit catalog is part of the application,
written by its developer before the agent ever runs, and the agent's contribution is the
component tree and the data filling it. leaf's agent writes the page from scratch every
time, and extends the vocabulary from inside the same session when the shipped one falls
short: `leaf customize widget lf-callout` is a command meant for the agent's hands.

At the open end, Open Generative UI is leaf's premise scoped to a chat message. The
agent generates HTML, CSS and JavaScript, and the runtime streams it into a sandboxed
iframe as it arrives — styles, then markup, then scripts — where it may pull Chart.js or
D3 off a CDN and call back through host functions the app exposed. The two projects
trust that page from opposite ends. CopilotKit treats generated UI as unsafe, puts an
origin boundary around it, and then lets it reach the network. leaf treats the page as
yours, gives it the whole window, and vendors every asset into the page directory under
one CSP that `version check` requires, so a published page cannot phone home. Which
posture is right follows from who is reading: a user of someone's product, or the person
whose own session wrote the page.

The channel back is where the two are least alike. A CopilotKit user can type in the
chat, press a component the agent rendered, answer a paused tool call, or write shared
state, and none of those says which part of the screen they are about. Someone who wants
to say "this paragraph is wrong" has the chat box, and the agent works out which
paragraph. leaf's anchors exist for that sentence: a selection becomes
`{node, start, end}` segments confirmed by context in every later version, so the mark
stays painted on the passage and the agent's reply lands in the margin beside it.
Questions running the other way are closer than they look. `useHumanInTheLoop` pauses a
run on a tool call until the user answers, and `useInterrupt` does the same from inside
a LangGraph node; leaf's `x-awaits` widgets ask the same kind of question, and
`leaf wait` carries the answer back. The difference is what the pause holds open.
CopilotKit suspends a graph node and resumes it with the reply; leaf's session has
simply not taken its next turn.

Shared state is the other near-collision. CopilotKit keeps one state object per agent
that both sides write: the agent emits a snapshot and then RFC 6902 patches as it works,
the UI subscribes with `useAgent` and writes back with `setState`, and a middleware can
pipe a tool argument into a state key as the model generates it, so a draft assembles on
screen a token at a time. leaf has no state object. The version's markup states the
initial condition, the log records every transition, and the standing state is the fold
over it — which is the whole reason an `applyAction` must state an absolute placement
rather than a mutation. CopilotKit streams down to the token, where a leaf page changes
a version at a time and `leaf report` is what lets a dashboard tick over between
versions. leaf keeps a decision across a rewrite: a card the reader moved is still where
they moved it after the agent publishes v4, and taking that back costs the author the
word `restated`. CopilotKit has nothing equivalent because it has nothing to rewrite —
the components are fixed before the run, and state is the only thing that moves.

Both have to say how anyone knows the agent's UI came out right, and they answer at
different layers. leaf gates the version: `version check` reads the markup against the
registry, and `--render` loads it in a real browser in both colour schemes and fails it
for overflow, an unusable widget box, a relative replay, an attribute no entry declares.
CopilotKit checks the boundary and then watches the stream — Zod on every tool argument,
and the Inspector, a debug overlay inside the running app showing AG-UI events, threads,
state and registered frontend tools as they happen. Its corpus is a matrix rather than a
gallery: a showcase cell is one integration × feature pair, the probe measuring a
feature is required to be byte-identical across every backend, and the only sanctioned
per-backend variation is a recorded-model fixture. leaf's examples prove the vocabulary
renders; CopilotKit's cells prove sixteen backends behave alike.

Both ship skills to coding agents, pointing opposite ways.
`npx copilotkit@latest skills install` drops fifteen skills into a project to teach
Claude Code, Codex or Cursor how to set up, build with, debug and upgrade CopilotKit,
with an MCP server beside them for live doc search; there the coding agent is the
builder. leaf is a skill, and the coding agent is the product's user rather than its
builder.

There is one shape where the two get close, and Claude Managed Agents is the sharpest
version of it. `@ag-ui/claude-managed-agents` maps a CopilotKit thread onto a hosted
Claude session, so the agent works in an Anthropic-run container with bash, files and
code execution, and the app deploys no agent at all. CopilotKit's cookbook builds
exactly that, from Anthropic's own quickstart, and
`init --framework claude-sdk-typescript` scaffolds the self-hosted variant against the
Claude Agent SDK. What reaches the browser is still a component the developer wrote: the
cookbook's agent calls `show_growth_projection` with five numbers, and `useRenderTool`
mounts a chart out of `GrowthProjection.tsx`. Changing the agent changes who runs the
loop, not who writes the page, and the reader still has a chat box rather than a passage
to mark. What the combination gets you is an application you deploy and users open; what
it doesn't is the session already at your terminal, a page directory on your disk, or a
comment anchored to a passage. Nothing in leaf runs the other way — it serves one page
to one session, and has no notion of an application at all.

## When leaf is the wrong choice

- **More than one person, or agents coordinating with each other.** A leaf page is
  one session presenting to one person. The log tells the agent from the user and no
  further: two people commenting are one voice, there are no live cursors, and nothing
  merges concurrent edits.
- **An agent that is only an HTTP client.** The loop is a command the agent runs and gets
  back into model context, so an agent that cannot run one cannot drive it — and the
  hooks that hold a session to the loop exist only in the two hosts.
- **An agent your product runs.** leaf's agent is the coding session at your terminal, and
  the page it serves goes down with that session. Where the agent is a service your
  application calls for users who never see a terminal, none of the loop applies; that is
  what CopilotKit and AG-UI are for.
- **An artifact that has to last.** The server and the wait go down with the session. The
  page directory stays on disk and `version export` makes a standalone copy, but
  nothing is live past the session, and a document a team will edit for months belongs
  in the repository.
- **Editing the document yourself.** The user works the affordances the page offers —
  comment, drag a card, pick an option, rewrite a draft, accept a proposed change — and
  prose the page didn't offer for change is the agent's until it publishes the next
  version. Where you would rather just fix the sentence, that round trip is the wrong
  shape.

## Not covered here

Five projects is not the landscape. These are the ones a fuller note would have to reach,
roughly in order of how badly the omission dates this one:

- **Claude Code Artifacts** (June 2026) — first-party, same medium, versioned pages that
  update in place, and the docs state there is no reply path: the user presses "Copy
  as prompt" and pastes into the terminal. The sharpest comparison available.
- **crit** — a local single Go binary, bound to loopback, no config or login; the agent
  launches it and blocks on the review rather than serving a page and watching it.
- **reviewable-html-workbench** — a Claude Code and Codex plugin running nearly this loop,
  down to the agent replying in-thread in the browser.
- **MCP Apps** — the official MCP UI extension since January 2026, built on the earlier
  community MCP-UI: a tool declares a `ui://` resource, the host renders it in a sandboxed
  iframe, and the UI pushes structured context back into the turn. ChatGPT, Claude, Goose
  and VS Code have all shipped it, and OpenAI's Apps SDK is the same idea at consumer
  scale, with its own component library and inline/fullscreen presentations.
- **Agent control layers** — Paseo, Nimbalyst, Agentastic, OpenWork and the like: GUIs
  that wrap the harness itself, with worktree management, diff review, preview URLs and,
  in Nimbalyst's case, editors for markdown, diagrams, spreadsheets and slides. They
  replace the terminal, where leaf sits beside it.
- **Human-in-the-loop inboxes** — LangChain's Agent Inbox and `humanInTheLoopMiddleware`,
  HumanLayer routing approvals to Slack or email. Approve, edit, reject or respond, on a
  paused tool call. leaf's asks are the same act on a page instead of in a queue.
- **Declarative UI formats** — the family A2UI belongs to, and the most crowded corner of
  this ground:

  - **json-render** (Vercel Labs, Apache-2.0, 16k stars since January 2026) — the volume
    leader. Its catalog declares three kinds where A2UI's declares one: `components`,
    `actions` and `functions`. The spec is a small language rather than a tree, with
    `$bindState` for two-way binding, `$cond` for visibility, `$computed`, `$template` for
    interpolation, `watch` + `setState` for cascades, and `checks` for validation — so
    behaviour lives in the spec where leaf puts it in a module beside the entry. Renderers
    for React, Vue, Svelte, Solid, React Native, Ink, Remotion, react-pdf, react-email,
    react-three-fiber and Next.js routes; a skill per renderer; and an example that renders
    hand-authored specs with no model in the loop.
  - **OpenUI** (Thesys, MIT, 8.4k stars) — argues the bottleneck is the notation rather
    than the renderer, and replaces JSON with OpenUI Lang, claiming far fewer tokens and
    near-zero malformed output. Its C1 product is an OpenAI-compatible endpoint that
    returns UI instead of text.
  - **Open-JSON-UI** — OpenAI's standardization of its own internal declarative schema.
  - **Hashbrown** (Angular and React) — a progressive JSON parser, so a partial tree
    renders while the model is still writing it.
  - **TODO** (2026-08-21): each of those four is a bullet where a section belongs — read
    them from their own materials the way the sections above were, and settle the
    integration question while doing it. Two directions are open and they are not one
    decision. leaf could render one of these specs inside a widget, which is a fenced
    widget and nothing more. Or leaf's vocabulary could be published as one of their
    catalogs, which asks what survives the trip: `x-state`, the passage keys and the width
    model have no counterpart in a catalog of components, actions and functions, so the
    answer settles how much of leaf is the vocabulary and how much is the loop around it.

- **In-app annotators** — InstantCode, Agentation, pi-annotate, Vibe Annotations: click an
  element in your running app, leave a note, and the agent gets the DOM path back. The
  same gesture as a leaf comment, aimed at software rather than at a document.
- **`gh pr review`** — the incumbent, and what most people actually use.

Two lists index this ground and are worth re-reading rather than re-deriving:
[awesome-generative-ui](https://github.com/narrowin/awesome-generative-ui) for the UI
formats, [awesome-cli-coding-agents](https://github.com/bradAGI/awesome-cli-coding-agents)
for the harnesses and what wraps them.
