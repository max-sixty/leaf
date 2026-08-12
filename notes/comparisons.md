# Notes on nearby projects

Maintainer notes rather than a published page. Each section was read from that project's
own materials on the date it names, and nothing here is checked by CI, so it dates from
that day and will drift.

Anything that hands an agent's work to a person in a browser answers three questions:
what the document is made of, where it lives, and how the reader's reply gets back to the
agent. Leaf's answers are authored HTML, a directory on your machine, and a
host-specific wait inside the session: background completion in Claude Code, an exact
unified-exec session kept inside the active turn in Codex.

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
`data-lavish-question` and `window.lavish.queuePrompt()`. Leaf goes the other way: 26
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

## When leaf is the wrong choice

- **More than one person, or agents coordinating with each other.** A leaf page is
  one session presenting to one person. The log tells the agent from the user and no
  further: two people commenting are one voice, there are no live cursors, and nothing
  merges concurrent edits.
- **An agent that is only an HTTP client.** The loop is a command the agent runs and gets
  back into model context, so an agent that cannot run one cannot drive it — and the
  hooks that hold a session to the loop exist only in the two hosts.
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

Three projects is not the landscape. A survey on 2026-08-01 named these as the ones a
fuller note would have to reach, roughly in order of how badly the omission dates this
one:

- **Claude Code Artifacts** (June 2026) — first-party, same medium, versioned pages that
  update in place, and the docs state there is no reply path: the user presses "Copy
  as prompt" and pastes into the terminal. The sharpest comparison available.
- **crit** — a local single Go binary, bound to loopback, no config or login; the agent
  launches it and blocks on the review rather than serving a page and watching it.
- **reviewable-html-workbench** — a Claude Code and Codex plugin running nearly this loop,
  down to the agent replying in-thread in the browser.
- **MCP Apps** — the first official MCP extension (January 2026), built on MCP-UI: a tool
  declares a `ui://` resource, the host renders it in a sandboxed iframe, and the UI pushes
  structured context back into the turn.
- **AG-UI** and **A2UI** — wire protocols and event vocabularies you build a UI on top of,
  rather than a surface.
- **`gh pr review`** — the incumbent, and what most people actually use.
