# Notes on nearby projects

Maintainer notes rather than a published page. Each section was read from that project's
own materials on the date it names, and nothing here is checked by CI, so it dates from
that day and will drift. The landscape was last swept on 2026-08-21.

Anything that hands an agent's work to a person in a browser answers three questions:
what the document is made of, where it lives, and how the reader's reply gets back to the
agent. leaf's answers are authored HTML, a directory on your machine, and a
host-specific wait inside the session: background completion in Claude Code, an exact
unified-exec session kept inside the active turn in Codex.

The note serves three ends: not building, worse, what already exists; keeping the ideas
the neighbours have had; and finding the ground they leave open. Behind the third is a
bet on the bitter lesson. Most of this landscape constrains the agent to what its
authors trusted a model to do at design time, and those ceilings hold as models improve.
leaf's side of each comparison should be primitives that get better as the agent does —
the document, the log, the open vocabulary — rather than a library that caps it.

## Explainer animation

Read on 2026-08-29 from the projects' documentation, repositories and published
packages. Remotion and Manim render video; Markdy and Elucim describe explanations
that run in the browser. The second group is nearer to a leaf package, while the first
is useful when the intended artifact is a marketing video.

| Project | Authoring model | Relevance to leaf |
| ------- | --------------- | ----------------- |
| [Remotion](https://www.remotion.dev/) | React components evaluated by frame, with a Studio preview and a render pipeline. It has first-party [agent skills](https://www.remotion.dev/docs/ai/skills) and active releases. | The broadest production option for branded video, captions and mixed media. Its application and render stack is too heavy for an embedded leaf widget. |
| [Manim Community](https://docs.manim.community/en/stable/) | Python scenes made from mathematical objects and transformations, rendered to video. | The strongest external option for mathematical and algorithmic explanations. Its scene code and rendered output do not supply a live browser explanation. |
| [Markdy](https://markdy.com/docs/) | A browser DSL with semantic nodes, groups, flows and beats; the runtime handles layout, edge routing and motion. It can import Mermaid. | The closest match to animated diagrams as code. The project began in April 2026 and is still moving quickly. On 2026-08-29, `@markdy/cli@1.1.1` failed to install because its declared `@markdy/compat` dependency was absent from npm. It is a design reference to retest, rather than a dependency to adopt now. |
| [Elucim](https://elucim.com/) | JSON or YAML scenes with SVG and mathematical primitives, explicit timelines and state machines, designed for agent generation. | The closest broad model for 3Blue1Brown-style concept explanations. The project began in March 2026 and still has a very small community, so it is also a design reference. |

All four separate semantic states from the motion between them. A leaf experiment can
keep its state vocabulary small and leave autoplay, controls and export as playback
policy. Remotion or Manim can produce standalone marketing videos; an embedded package
should remain closer to the Markdy and Elucim authoring models until one of them matures
enough to vendor.

## Claude Code Artifacts

Read on 2026-08-22, from Claude Code's own documentation.
[Artifacts](https://code.claude.com/docs/en/artifacts) publish a page from your session
to a URL on claude.ai: Claude writes an HTML or Markdown file in your project, publishes
it, and updates it in place as the session continues. It is first-party, it is the same
medium, and as of a run of recent releases it has the same loop. Of everything in this
note it is the closest thing to leaf that exists, and the only one whose existence
narrows what leaf can claim to be for.

|                | Claude Code Artifacts                                                                                                                                        | leaf                                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| Document       | One self-contained HTML or Markdown page, no backend and no routes, written by a built-in design skill that reads your project's design tokens               | Authored HTML against a widget vocabulary, published as numbered versions, each with a changelog note to step back to |
| Home           | Anthropic's infrastructure, served to the viewer from a sandboxed `*.claudeusercontent.com` origin, under your organization's retention policy and audit log | A page directory on your machine, served where your session reached it, behind a key                                  |
| Return path    | A comment thread on the page; `@claude` or the thread's Claude control activates it, and the session that published the page is watching                     | Comments, drags and picks appended to an event log, returned to the session by its own `leaf wait`                    |
| After a revise | Each publish is a version, and the publisher picks which version viewers see                                                                                 | Every action replays onto every version published after the one it was made on                                        |
| Reach          | Claude Code CLI, the desktop app, and Claude Tag — signed into claude.ai, on the Anthropic API, on Pro, Max, Team or Enterprise                              | Claude Code and Codex, on any machine, with no account                                                                |

Start with the correction, because this note had the entry wrong. Until this read,
Artifacts sat in the list below as a bullet saying the docs state there is no reply path
and the reader presses "Copy as prompt" and pastes into the terminal. That was true when
it was written and is not true now, and the direction of the error is the one a stale
sweep produces: it flattered leaf. Three shipped changes closed it. From v2.1.221 an
artifact shared inside your organization takes comment threads, and Claude reads them on
request. From v2.1.228 it does not need the request: "After your session publishes an
artifact, Claude Code watches that artifact for comments for as long as the session
runs", a comment sent to Claude "reaches your session right away", and `/tasks` lists
each watched artifact as a live-updates task. Your permission mode decides whether the
reply goes out without asking you, and the whole thing stops after sixty sent comments
on one artifact in an hour.

So the return path leaf spent its host coupling to buy is now first-party, and it cost
the agent nothing: no hook, no command left running, no `wait` in the foreground.
Against that, what leaf's coupling still buys is where the page lives, and the
conditions on each side are the real comparison. An artifact needs a claude.ai sign-in,
the Anthropic API rather than Bedrock, Vertex or Foundry, and a Pro, Max, Team or
Enterprise plan; comments need Team or Enterprise on top, because only an org-shared
artifact takes them, and a publicly shared one refuses them outright. leaf needs a
shell.

Where the page lives is the split everything else follows from. An artifact is stored on
Anthropic-operated infrastructure: an owner toggles the feature for the organization,
another toggle governs connector calls, a third governs public links, retention is a
policy with separate periods for private and shared pages, every publish and share and
delete lands in the audit log as a `claude_artifact_*` event, and the Compliance API can
list, fetch and delete across the org. That is a set of properties leaf does not have
and should not build, and it is also why an artifact outlives the session that made it
while a leaf server dies with its own. Read from the other side, a leaf page directory
is on your disk, governed by nobody's admin settings, reachable with no account, and
gone when you delete the directory.

The page itself is freehand, and that is the lavish-axi bet made first-party. A design
skill gives the page a palette and a layout, and looks for a design system in your
project first — design tokens in `CLAUDE.md` outrank its own choices, and your prompt
outranks both. Guidance the agent reads, in other words, where leaf writes declarations
the machine reads. Nothing gates an artifact before the link goes out: there is no
registry to check markup against, no render pass in two colour schemes, nothing that
refuses a page whose widget box is unusable or whose ids moved. The constraints that do
exist are the host's and they are strict — one page, no backend, no relative links, 16
MiB, and a CSP that blocks every external script, stylesheet, font, image, `fetch`, XHR
and WebSocket, with Google Fonts the one exception. leaf arrives at nearly the same CSP
from the opposite direction, by vendoring every asset into the page directory and having
`version check` require it.

What survives a revision is where the two designs actually differ, and it is the same
difference this note draws against Plannotator and lavish-axi. Artifacts have versions:
each publish is one, and the Share control chooses which version viewers see. That is a
publisher's control over what is shown, not a reader's history to step back through, and
nothing carries a reader's state across a republish. The docs' own triage-board example
is the tell — cards dragged across Now, Next, Later and Cut, and a "Copy as prompt"
button to get the ordering back — because the ordering cannot survive the next publish
any other way. leaf's log outranking the document is exactly this: the drag is an event,
it replays onto v4, and taking it back costs the author the word `restated`.

The other half of that is the anchor, and here the docs stop short of an answer. They
describe "a thread on the page" and never say whether a thread attaches to a selection,
an element, or the page as a whole, so whether an artifact comment can point at a
paragraph — and whether it still points there after a republish — is not settled by
reading them. leaf's `{node, start, end}` segments exist for that sentence and are
confirmed by context in every later version.

One capability runs the other way, with no counterpart in leaf at all. An artifact can
call MCP connectors when someone opens it, and the calls go through the viewer's own
claude.ai account rather than the publisher's: each viewer approves access first, two
people can see different data from the same dashboard, and a control with a side effect
acts as whoever pressed it. That is a live page for readers who are not you, and it is
the precise inverse of leaf's posture, where a published page vendors everything and
cannot phone home. Neither is the better answer; they answer to different readers.

What is left, then, is narrower than it was and still real. Artifacts took the medium
and the loop, and did it without asking the agent to run anything. leaf keeps three
things they have not: a vocabulary the machine checks before the link goes out, a
reader's decisions that survive the author rewriting the page under them, and a page
that is a directory on your own disk. Those are worth stating plainly rather than
defending, because the first question anyone in this landscape should now ask leaf is
why not just publish an artifact.

## Plannotator

Read on 2026-08-21, from the repository and its own docs.
[Plannotator](https://github.com/backnotprop/plannotator) is a local, browser-based
review surface for coding agents, wired into nine of them through their own hooks. When
the agent proposes a plan, renders HTML, or finishes writing code, the work opens in a
browser, the reader marks it up, and the annotations go back to the session as
structured feedback. Apache-2.0 and MIT, started December 2025, 7.9k stars. Outside
Anthropic it is the nearest neighbour leaf has on the loop, and it reached the hosts
leaf hasn't. Its frame
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
layout warnings rather than a version a reader can step back through. leaf's log outranks
the document, so comments stay anchored across versions, the agent's reply lands in the
margin beside the passage it answers, and a dragged card or a pick replays onto every
later version.

The anchors follow from that. Lavish captures a `{selector, path, offset}` boundary at
each end of the selection, plus the text collapsed to single spaces, which is enough to
hand the agent a target in source it wrote moments ago. It never resolves one again: a
reload drops a text card rather than restore it, because that "could point the annotation
at different text". leaf has to find the same passage in every later version to keep the
mark painted and the thread attached, so it stores `{node, start, end}` segments, reads
them the same way from the file and from the DOM, and confirms an occurrence by its
context rather than by document order. Neither anchor is doing the other's job.

They also disagree about whether the page has a vocabulary. Lavish injects no design
system on purpose, so an artifact opened through the CLI and one opened straight from the
filesystem draw identically; `lavish-axi design` and seven playbooks (`diagram`, `table`,
`comparison`, `plan`, `code`, `input`, `slides`) are guidance the agent reads, and
interactivity comes from native controls plus `data-lavish-action`,
`data-lavish-question` and `window.lavish.queuePrompt()`. leaf goes the other way: 28
shipped tags in a registry a project or a user overlays, whose declarations drive the
lint, the render check, export and replay together. Freehand buys any page the agent can
imagine; a vocabulary buys a page the machine can check and replay.

Each has capabilities the other hasn't. Lavish turns every rendered Mermaid diagram into
an editable Excalidraw whiteboard whose scene and edit summary go back to the agent, and
it inlines local assets into a standalone export, or publishes that to a third-party
host. leaf has versions and the changelog, threads the agent answers in place, replayed
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
which "returns the moment an event lands past `since`". leaf's `wait` tails the
page directory on disk and exits on the first event the agent hasn't seen. Different
transport, same bargain: one call that blocks until the user does something. leaf
acknowledges the event separately, only after a complete, untruncated wait result enters
model context.
Workbench also offers webhooks and a supervised watcher, for wake-ups that outlive the
agent's process.

What the HTTP surface gives Workbench is reach: "any agent that can fetch a URL can work
here — no SDK, no plugin", which covers Claude, Codex, Cursor and curl alike. leaf's
coupling to the agent host is the opposite bet, and what it gets in return is arrival in
model context: on Claude Code a finished background wait wakes or joins the session; on
Codex the agent keeps the handover turn active and polls the exact wait session. Either
can take "skip that one" into account before the next decision. It costs a host-specific
loop, and leaf runs on those two hosts and no others.

## html-effectiveness

Read on 2026-07-31.
[html-effectiveness](https://github.com/anthropics/html-effectiveness) is a gallery of
standalone HTML examples — code review, status reports, slide decks, diagrams, small
editing UIs — each "a self-contained `.html` page (no build step, no dependencies)". It
shares leaf's premise that a page carries more than a wall of terminal text, and it
closes the loop through the reader: the editing UIs hold their state client-side and
"always end with an export button that turns whatever you did in the UI back into
something you can paste into the agent or commit". leaf replaces that paste with a
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
time, and can extend a package's vocabulary from inside the same session when the
shipped one falls short.

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

## herdr

Read on 2026-08-23, from the repository and its own docs.
[herdr](https://github.com/herdrdev/herdr) is a terminal multiplexer that knows which of
its panes are running coding agents. It keeps tmux's model, where a background server owns
the workspaces, tabs and panes and clients detach from it and reattach. On top of that
each pane's agent has a state, `idle`, `working`, `blocked` or `done`, which rolls up from
the pane to its tab and workspace, so the sidebar says which agent is waiting on you.
Apache-2.0, started March 2026, 31.7k stars. It has no document and no browser surface, so
this note's first question has no answer here. It is in the note because the user and the
agents rearrange one live structure between them, which is the relationship leaf builds
around a document.

|                      | herdr                                                                                                                                                                           | leaf                                                                                                             |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Shared structure     | Workspaces, tabs, panes and the splits between them, owned by a server that outlives any client                                                                                 | The page: authored HTML published as numbered versions, each with a changelog note to step back to               |
| Home                 | A background server on your machine, drawn by a TUI you detach from and reattach to                                                                                             | A page directory on your machine, served where your session reached it, behind a key                             |
| The agent's controls | The socket API and the CLI that wraps it: `pane.split`, `pane.move`, `pane.zoom`, `tab.create`, `layout.export` and `layout.apply`, `agent.start`, `agent.prompt`, `agent.wait` | Publishing a version, and answering a thread in the margin beside the passage it belongs to                      |
| The user's controls  | Mouse and keys on the same objects: click a pane, tab or workspace, drag a split border, right-click for a menu, run a prefix-mode command                                      | The affordances the page offers: comment, drag a card, pick an option, rewrite a draft, accept a proposed change |
| Waiting              | `agent.wait` until another agent reaches `blocked` or `done`, or a `pane.agent_status_changed` subscription on the socket                                                       | `leaf wait` on the page's event log, returned into the session by its host                                       |
| Reach                | Anything that runs in a terminal, with shipped detection manifests for Claude Code, Codex, Cursor, Gemini, OpenCode, Grok and the rest                                          | Claude Code and Codex                                                                                            |

Nothing in that structure belongs to one side. An agent creates a tab and splits a pane
through the socket, the user drags the same border with a mouse, and either can rename,
zoom, move or close what the other made. `layout.export` and `layout.apply` hand a whole
arrangement back and forth as data. The state behind the sidebar does not work that way.
An agent's `idle`, `working` or `blocked` flows one direction, from the process into the
display, and how herdr decides it depends on the agent: an installed integration's
lifecycle hooks are authoritative while they report, and otherwise herdr matches the live
bottom of the screen against per-agent TOML rules, and marks `blocked` only on a visible
approval, question or permission prompt.

A herdr arrangement has no past. A pane the agent moved is moved, and there is no earlier
layout for the move to disagree with. leaf's page has versions, so the same joint control
raises a question herdr never has to answer: what becomes of the card the reader dragged
when the agent publishes a rewrite of that board. The log outranking the document is the
answer to it — a surviving action replays onto the later version, and `version check`
refuses a rewrite that silently cancels a decision unless the author marks it `restated`.
Sharing control over a live arrangement is nearly free; over a document that keeps its
past it costs a reconciliation design.

The two route a person's attention at different scales. herdr answers which of your
sessions needs you, and published plugins forward that signal to a phone when an agent
goes `blocked`. leaf's banner counts the open decisions inside one page and its keyboard walk
steps through them, for a reader who already has the page open. A leaf session is an agent
at a terminal, so it is the kind of thing that sits in a herdr pane, and the page it
serves is content herdr has no opinion about.

## Declarative UI formats

Read on 2026-08-22 from each project's own repository, and A2UI on 2026-08-23 from
its specification (v0.9.1 current, v1.0 a candidate).
[json-render](https://github.com/vercel-labs/json-render) (Vercel Labs, Apache-2.0, 16k
stars since January 2026), [OpenUI](https://github.com/thesysdev/openui) (Thesys, MIT,
8.4k), [Hashbrown](https://github.com/liveloveapp/hashbrown) (LiveLoveApp, MIT, 719) and
[A2UI](https://github.com/a2ui-project/a2ui) (started at Google, Apache-2.0, 16.2k, spec
at [a2ui.org](https://a2ui.org/)) are the crowded corner of this ground. Each answers one
question: how a model can emit a user interface without emitting arbitrary code. The
answer they share is a catalog. A developer declares the components a model may use
before the model runs; the model composes within them; the renderer refuses anything
else.

|             | What the agent emits                                                                                                         | Who writes the vocabulary                                 | Where the reader's press goes                                                       | Reach                                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| json-render | A flat spec: a `root` id and an `elements` map of `{type, props, children}`, with `$state`, `$cond`, `$template` expressions | The app's developer, in Zod, before the model runs        | A named action to the app's handler, or `setState` into the spec's own state model  | A dozen renderers, from React and Vue to PDF, email, video, 3D and the terminal                          |
| OpenUI      | OpenUI Lang: `submitBtn = Button("Submit", "submit:signup", "primary")`, positional args in the component's Zod key order    | The app's developer, in Zod, before the model runs        | An action string the app resolves                                                   | React first, with Vue and Svelte bindings, a CDN bundle, and a LangGraph adapter that streams over AG-UI |
| Hashbrown   | Nothing over the wire: the model names exposed components and their props, and the framework mounts them as they stream      | The app's developer, in TypeScript, via `exposeComponent` | The component's own handler, in the app                                             | Angular and React                                                                                        |
| A2UI        | A stream of JSON messages — `createSurface`, then `updateComponents` and `updateDataModel` — building a component tree bound to a per-surface data model | The platform's developers, in JSON Schema catalogs named by `catalogId`, before the model runs | An `action` message named by its component, with context read out of the data model | Renderers mapping one tree onto web components, Flutter, React or SwiftUI; CopilotKit ships `a2ui-renderer` |
| leaf        | HTML against the widget registry, published as a numbered version                                                            | The agent, in session; `leaf package init PACKAGE` creates the unit it edits | An action appended to the event log, replayed onto every version published after it | Claude Code and Codex                                                                                    |

The column that separates them from leaf is the second one. A catalog is part of an
application, fixed before the run, and the model's contribution is the tree and the data
in it. leaf's agent writes the page from nothing each time, and extends the vocabulary
from inside the session when the shipped one falls short. That difference is downstream
of the loop: a catalog exists to make a model's output safe for someone else's users,
where a leaf page is written for the one person the session is already working with.

json-render is the most complete of them. Its catalog declares three
kinds where A2UI's declares one — `components`, `actions` and `functions` — and
`catalog.prompt()` generates the model's instructions from that same catalog, so the
guardrail and the prompt cannot drift apart. The spec is a flat map keyed by element id
rather than a nested tree, which is what makes a half-arrived stream patchable:
`createSpecStreamCompiler` takes chunks and returns the spec so far. Around that sit
twenty-eight packages — the renderers, devtools with a stream tap and an element picker,
adapters for Redux, Zustand, Jotai and XState, a YAML wire format — and twenty-six skills
teaching coding agents to use them. Its `no-ai` example renders hand-authored specs
with no model in the loop at all, which is the clearest statement of what the project
thinks it is: a rendering layer that happens to be safe for a model to write.

Its expression language is where it diverges from leaf furthest. `$state` reads a JSON
Pointer into a state model, `$cond` picks a branch, `$template` interpolates, `$computed`
calls a registered function, `$bindState` binds two ways, `watch` fires an action when a
value changes, and `setState` writes back. Behaviour lives in the spec. leaf puts it in a
module beside the registry entry, which is why `version check` can read a page and say
what it will do, and why a leaf action is a fact appended to a log rather than a write to
a store. That store is the real collision: it is exactly the second copy of the reader's
state that leaf's design refuses, and a leaf page holding one would have two answers to
where a dragged card is.

OpenUI makes the opposite bet from every JSON project here, its own vendor's earlier C1
format included: that the bottleneck is the notation. OpenUI Lang writes a component as a
function call with positional arguments in the component's Zod key order, and lets an
identifier stand for a subtree, so `submitBtn = Button("Submit", "submit:signup",
"primary")` is one line where JSON is six. The repository measures it — seven scenarios,
tiktoken on the GPT-5 encoder, 4,800 tokens against json-render's 10,180 and C1's 9,948,
methodology in `benchmarks/` — which is more than most claims in this landscape carry. The
price is that a spec cannot be read without its catalog, positions meaning nothing on their
own. leaf pays the reverse price deliberately. HTML is the verbose end of every one of
those rows, and the verbosity buys the thing the whole loop rests on: the page is the
document, quotable and diffable and exportable, and legible to a person with no renderer.

Hashbrown is the odd one out: it has no wire format at all. Components are exposed in
TypeScript — `exposeComponent(Component, {description, name, props, children})`, where
`children` is either `'any'` or a list of other exposed components — and the model names
one. What it has instead is Skillet, a Zod-shaped schema language in which
`s.streaming.string()` marks a value safe to render half-written, and a streaming JSON
parser that mounts a component while the model is still writing its props. That is the
axis leaf is weakest on: a leaf page changes a version at a time, `leaf report` is what
lets a dashboard tick over between them, and nothing in leaf paints a sentence as it
arrives. It is also the axis leaf's design makes expensive, since a version is published
whole and a comment anchors into it.

A2UI is the corner's named standard: started at Google, now in a neutral
`a2ui-project` org with a versioned specification, where the other three are each one
vendor's product. Four message kinds — `createSurface`, `updateComponents`,
`updateDataModel`, `deleteSurface` — stream a component tree bound to a per-surface
data model, and the v1.0 candidate adds typed function calls in both directions. Input
components bind two ways, and the reader's press returns as an `action` message whose
name the component chose, with context read out of the data model. The component set is
deliberately outside the protocol: catalogs are JSON Schema documents named by
`catalogId`, a renderer names the ones it supports at the handshake, and one tree is
meant to land as web components, Flutter widgets, React components or SwiftUI views.
The openness is between platforms rather than in session — a catalog is still fixed
before the model runs, and nothing extends one from inside. On state the spec is
explicit that the surface's local data model is "the single source of truth", which is
json-render's `$state` as doctrine, and the specification has no versions, no replay,
no undo, and nothing that anchors a remark to a component or a passage. As an interface
it standardizes the live tree, which leaf doesn't keep, and says nothing about the log.

Against A2UI in particular, two of the differences are decisions rather than accidents.
The catalog is a capability boundary: it exists so a model never ships executable
content into the application it is drawn in, because the reader is someone else's user.
leaf declines that boundary on purpose — the reader is the person whose session wrote
the page, so the page gets the whole window, and the registry is a contract the gates
read rather than a fence the agent is kept behind; leaf's CSP guards against a page
phoning home, not against the agent. The tree is the second decision. An abstract tree
can be forced valid at generation, by constrained decoding against the catalog's
schema, and can land on toolkits HTML never reaches; leaf accepts checking after the
markup exists, in `version check`, to keep the artifact a document. Both trades follow
from who is reading, and both are the introduction's bet in miniature: a catalog's
ceiling is fixed at design time, while fluency in HTML rises with every model.

Open-JSON-UI is the remaining name this corner is described with, and it is a name
with documentation and no specification. The documentation is real and easy to find: a
page in CopilotKit's docs, a row in AG-UI's spec comparison, a paragraph in
`CopilotKit/generative-ui`, and the personal blogs, glossaries and cheat-sheets that
cite those. What no search reached was anything to implement against. There is no
repository of that name on GitHub, under `openai/` or any other owner; nothing under it
on npm; no spec document; nothing on OpenAI's own domains; and, in CopilotKit's
monorepo, no code — where A2UI has an `a2ui-renderer` package and takes `a2ui: {}` on
the runtime, Open-JSON-UI has the page. A GitHub code search for the string returns four
hundred-odd hits and every one of them is prose. The page itself reads like it: two JSON
examples that are different shapes from each other, and a comparison table that cites
nothing.

The vendor agrees. The comment on the redirect that took the page out of the sidebar
reads `AI-slop placeholder pulled from nav until properly authored; file stays on disk
for rewrite`. The page is still up, though, and that is the part worth writing down. The
redirect names one exact path, `/generative-ui/open-json-ui`, where these docs serve
every page under each integration's prefix as well — so the bare URL 307s to the index
while `/pydantic-ai/generative-ui/open-json-ui` and a dozen siblings answer 200 with the
placeholder. A page its own publisher has disowned is what a search for this name finds,
which is how a spec that was never written keeps arriving as a peer of the others.

The description itself is worth taking apart, because half of it checks out. What
OpenAI publishes in this space is a sample: `openai/openai-structured-outputs-samples`
carries a `generative-ui` demo whose `components-definition.ts` names `card`, `header`,
`container`, `carousel` and `item` by hand, compiles them into a `generate_ui` tool's
JSON Schema with `$ref` recursion and `additionalProperties: false`, and maps each to a
React component in `components.tsx`. That is a declarative generative UI, it is
OpenAI's, and it is the same catalog shape as the projects above. It is also a
demo app in a samples repository, which never uses this name and asks nobody to adopt
its schema. So "OpenAI's" has a referent and "declarative Generative UI" describes it;
"open standardization" names an act that no one performed, and "internal" claims
knowledge of something private and unfalsifiable. The distance between a sample and a
standard is the whole of the claim.

Whether leaf should integrate with any of this has three directions — render their
specs, publish leaf's vocabulary as one of their catalogs, or adopt one of their
interfaces in leaf's place — and reading them answered all three.

Rendering one of these specs inside a leaf widget is mechanically the easiest thing in this
note: it is the shape `lf-diagram` already has, a vendored bundle and a module beside a
registry entry. What it costs is the reading stack. `version check` reads markup against
the registry, so everything inside the widget would be opaque to it; the passage reading
would need a fence around the whole box, so nothing inside could be quoted, anchored or
diffed; and the spec's state model would stand beside the log as a second answer to what
the reader decided. A page whose content lived inside such a widget would be a leaf page
with leaf switched off.

Publishing leaf's vocabulary as one of their catalogs fails from the other end. The tags
and their JSON Schemas map onto `components` with Zod props well enough. What does not
travel is every key that makes the vocabulary leaf's: `x-state` names a verb, its record
form and its fold unit so replay and undo can work over a log a catalog has no counterpart
for; `x-parent` and `x-retired-when` describe a settlement the log adjudicates; the passage
keys bound what a file's reading may claim about a page; `x-awaits` feeds the banner's
count and the walk through open decisions. Strip those and what ships is twenty-eight tags of
styled HTML, which is a stylesheet. So the question settles: leaf is mostly the loop, and
the vocabulary is what the loop is written in terms of rather than something that stands
on its own.

Adoption outright — one of their interfaces in leaf's place — splits along this note's
three questions. The document runs backwards: what an agent emits in any of them is
legible only through the catalog and a renderer, and a leaf page is written in what
their web renderers themselves emit — HTML and custom elements, checked by JSON Schema —
so at that layer leaf already speaks the older, wider standard. Where the UI lives,
they have no answer
to give: a surface or a spec is a message inside an application's session, not a
directory with an address on your disk. And the return path in every one of them
describes a live run — an action into a running agent, a mutable store, nothing that
outlives the session — where what the log holds is exactly what survives one. W3C Web
Annotation is the one published standard that does cover leaf's ground: a comment
anchor's `{quote, prefix, suffix}` is its TextQuoteSelector, whose first field it
spells `exact`. Taking that spelling is the cheapest adoption on this page, and still
not worth it: the standard names the fields and stops there. It specifies no way of
finding the passage again, so leaf writes its own — unique-context confirmation, and
detachment rather than a fallback to ordinals — and a shared field name would
advertise a matcher that isn't shared.

The door worth watching is none of those, and it is not a format. `@json-render/mcp`
serves a spec as an MCP App — the server returns a UI resource, the host renders it in a
sandboxed iframe, and `callServerTool` carries the press back — so one catalog reaches
Claude, ChatGPT, Cursor, VS Code, Goose and Postman without a hook written for any of them.
That is leaf's reach problem solved by the host instead of by the notation. What it does
not carry is the page: an MCP App is an iframe inside one chat message, in the host's
window, so there are no versions, no directory, and no reader who closed the conversation
and came back to it the next day. MCP Apps is already on this note's list of what a fuller
one would reach, and this is the angle a fuller entry would have to take: not another way
to describe a UI, but the one route by which a page could reach a host that has never
heard of it. What would change the answer is named in the extension's own deferrals: app
registrations must not outlive a session, a closed app's tool calls must error, and state
persistence and external URLs are put off to future extensions — so an app there today is
as mortal as the chat message holding it. External URLs or persistence landing, or a
terminal host shipping an Apps surface, is the signal to stop watching and prototype; even
then the route adds new hosts rather than retiring the two hooked ones.

## When leaf is the wrong choice

- **More than one person, or agents coordinating with each other.** A leaf page is
  one session presenting to one person. The log tells the agent from the user and no
  further: two people commenting are one voice, there are no live cursors, and nothing
  merges concurrent edits. An artifact shared inside an organization takes comments from
  everyone it is shared with, and Workbench is built for the multiplayer case outright.
- **An agent that is only an HTTP client.** The loop is a command the agent runs and gets
  back into model context, so an agent that cannot run one cannot drive it — and the
  hooks that hold a session to the loop exist only in the two hosts.
- **An agent your product runs.** leaf's agent is the coding session at your terminal, and
  the page it serves goes down with that session. Where the agent is a service your
  application calls for users who never see a terminal, none of the loop applies; that is
  what CopilotKit and AG-UI are for.
- **A page that has to outlive the session.** The server and the wait go down with it.
  The page directory stays on disk and `version export` makes a standalone copy, but
  nothing is live afterwards. A Claude Code artifact is hosted and outlives the session
  that published it; a document a team will edit for months belongs in the repository.
- **Editing the document yourself.** The user works the affordances the page offers —
  comment, drag a card, pick an option, rewrite a draft, accept a proposed change — and
  prose the page didn't offer for change is the agent's until it publishes the next
  version. Where you would rather just fix the sentence, that round trip is the wrong
  shape.

## Not covered here

The entries above are not the landscape. These are the ones a fuller note would have to
reach, roughly in order of how badly the omission dates this one:

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
  paused tool call. leaf's decisions are the same act on a page instead of in a queue.
- **In-app annotators** — InstantCode, Agentation, pi-annotate, Vibe Annotations: click an
  element in your running app, leave a note, and the agent gets the DOM path back. The
  same gesture as a leaf comment, aimed at software rather than at a document.
- **`gh pr review`** — the incumbent, and what most people actually use.

Two lists index this ground and are worth re-reading rather than re-deriving:
[awesome-generative-ui](https://github.com/narrowin/awesome-generative-ui) for the UI
formats, [awesome-cli-coding-agents](https://github.com/bradAGI/awesome-cli-coding-agents)
for the harnesses and what wraps them.
