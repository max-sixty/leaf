# Notes on nearby projects

This is dated research for maintainers, not a current feature matrix. External
projects were read from their own repositories and documentation between
2026-07-31 and 2026-08-29, then revisited on 2026-09-22. The 2026-10-04 refresh
covers Sideshow, Workbench, Plannotator, lavish-axi, Nimbalyst, Agentation, and
Sfora; other sections retain their stated read dates. Evidence combines source
and documentation reads with limited public-demo gestures in Workbench, Sfora,
Agentation, and Plannotator. It does not include signed-in workspaces or live
agent-host delivery. Released features,
main-branch work newer than a release, and hosted-product claims are
distinguished below. Recheck availability before an integration decision.

The comparison asks what the agent authors, where the work lives, and how user
input returns. Leaf authors HTML with an extensible registered vocabulary. A
page directory holds immutable revisions and an append-only event log; surviving
user decisions carry into later revisions unless explicitly retracted. These
contracts live in [page-storage.md](../skills/leaf/scripts/leaf/page-storage.md)
and [packages.md](../skills/leaf/references/packages.md).

Delivery belongs to the harness adapter: Claude Code's Stop hook watches claimed
pages; ordinary Codex tasks receive queued deliveries; tasks with an accessible
Codex App Server receive delivery turns through that server. Read the owning
[Claude Code](../skills/leaf/references/harness-claude-code.md),
[Codex queue](../skills/leaf/references/harness-codex.md), and
[App Server](../skills/leaf/references/harness-codex-app-server.md) contracts rather
than deriving a handoff from this comparison. Serving, authentication, standing
lifetimes, and offline export belong to
[serving-pages.md](../skills/leaf/references/serving-pages.md).

The research is useful for authoring ideas, existing mechanisms, and product
boundaries. Repeated differences in the sections below refer to this Leaf
baseline rather than restating a feature table for each project.

## Interaction lessons for Leaf, 2026-10-04

**Host integration.** Plannotator's [session bridge](https://github.com/backnotprop/plannotator/blob/main/packages/ai/session-bridge.ts)
separates host readiness, submission, and streaming behind an adapter. Its
[opt-in Claude Code host modification](https://github.com/backnotprop/plannotator/pull/1672)
is newer than the latest binary. If supported host APIs can own idle/wake/turn
execution, Leaf can simplify that orchestration. Durable input, pickup, and
response identity still belong to Leaf. The decisive case is a running turn
ending without reading its offered hook pointer: the existing
[delivery tests](../tests/test_interact_session.py) cover falling back to the
queue without losing that input. An offer or queue acknowledgment is not pickup. I
inspected those tests, without rerunning them. No peer demonstrated a general
same-chat Codex solution; Plannotator's public sharing demo did not exercise a
live bridge.

**Task state.** [Workbench](https://workbench.md/agents.md) separates atomic Ask
claims from Markdown-board claims using optimistic `If-Match` edits. Neither
proves a result; version checks are optional across API writes. Its
[chief contract](https://workbench.md/chief.md) prescribes independent artifact
and completion checks, but no supervisor run was observed. Nimbalyst's
[recovery owner](https://github.com/nimbalyst/nimbalyst/blob/main/packages/runtime/src/ai/server/SessionStateManager.ts)
resets missing running processes to idle. Leaf's [tasks](../skills/leaf/scripts/leaf/tasks.py)
already outlive replies and sessions. Preserve that obligation across execution
attempts, distinguish interrupted/resumable work from a terminal result, and
name consequential changes to the expected result rather than resetting on every edit.

**Flexible pages and workspaces.** Workbench's public demo turned an added
Markdown heading into a board column; [Sfora's demo](https://www.sfora.ai/features/boards)
retained cards across Board → Map. These demonstrate alternate views, not server
persistence. Keep Leaf's authored HTML and declared semantic islands; stable
workspace/task identities and [canonical summaries](../skills/leaf/scripts/leaf/server_rows.py)
should support navigation without making a serving process the obligation's owner.
Opaque widget JSON persistence does not prove that a decision keeps its meaning.

**Page-level threads.** I operated [Agentation's toolbar](https://www.agentation.com/)
and contextual composer, typed a local draft, and dismissed it without sending.
Plannotator's [global composer mode](https://github.com/backnotprop/plannotator/blob/main/packages/ui/components/CommentPopover.tsx)
shares draft machinery. Leaf already has “Comment on the page” in its
[composer owner](../skills/leaf/assets/runtime/thread/panel.js). Improve entry
and continuation there, keeping targeted/global placement distinct while sharing
editing and delivery. Multiple independent global threads and revision-surviving
drafts still need direct interaction proof.

**UI stability.** Lavish's [bounded mobile sheet](https://github.com/kunchenguid/lavish-axi/blob/main/src/chrome.css)
and Plannotator's central placement function offer useful mechanisms. Their
source and browser tests were reviewed, not run. Agentation's toolbar was
desktop-only at 390px. Use Leaf's existing geometry owner, an explicit bounded
mode when space runs out, and first-frame journeys covering nested scroll,
reply expansion, and keyboard arrival. A component library or final screenshot
does not prove the absence of layout churn.

## Claude Code Artifacts

Read on 2026-08-22 and 2026-09-22 from the
[documentation](https://code.claude.com/docs/en/artifacts) and
[changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md).
Artifacts were the closest first-party comparison: Claude authored HTML or
Markdown, published it to Anthropic-hosted infrastructure, and watched comments
sent back to the publishing session.

The September read found a broader runtime than the August documentation:
per-page databases with access rules, viewer-scoped data, stale-publish refusal,
watching several artifacts, and Design canvases. A session's runtime also exposed
self-publishing pages, `sample` requests to Claude, uploads, and presence. The
public documentation still described pages with no backend, so general
availability of these capabilities was unconfirmed. These observations supersede
the earlier conclusion that state could not survive republishing: a database
could retain it.

The read also found that comments required organization sharing on Team or
Enterprise and were unavailable on public links. Anchors used a CSS path with
coordinates or a registered name. The reported comment-delivery failure in
[issue #92618](https://github.com/anthropics/claude-code/issues/92618) was a bug
report, not proof that the whole return path failed.

The useful comparison is local ownership versus hosted collaboration. Artifacts
had organization retention, audit controls, and connector calls under the
viewer's identity. Leaf has a local page directory, requires no viewer account,
checks its vocabulary, and resolves passage anchors across revisions. A hosted
artifact's persistence is therefore not evidence that Leaf alone can preserve
state; Leaf's distinction is the explicit revision-and-event contract.

## Plannotator

Read on 2026-08-21, 2026-09-22, and 2026-10-04 from its
[repository](https://github.com/backnotprop/plannotator) and releases.
Plannotator reviews plans, Markdown, rendered HTML, local diffs, and repository
changes. It retains feedback history and PR comments across pushes, marking
changed targets Outdated. VCS support includes Git, Jujutsu, Perforce and
GitButler; encrypted plan sharing and broad harness support remain useful
references.

Released since the September read: [embedded question cards](https://github.com/backnotprop/plannotator/releases/tag/v0.27.23)
with saved answers, undo, and delivery to the agent; changed questions orphan
previous answers. Review additions include
[before/after image diffs](https://github.com/backnotprop/plannotator/pull/1601),
[file-level GitHub threads](https://github.com/backnotprop/plannotator/pull/1600),
[saved viewed-file progress](https://github.com/backnotprop/plannotator/pull/1632),
and [Bitbucket Cloud PRs](https://github.com/backnotprop/plannotator/pull/1641).

October 3–4 main-branch work is newer than the latest binary,
[v0.27.25](https://github.com/backnotprop/plannotator/releases/tag/v0.27.25):
[Ask AI through the originating session](https://github.com/backnotprop/plannotator/pull/1685),
[nonblocking Pi reviews](https://github.com/backnotprop/plannotator/pull/1670),
[OpenCode2 delivery](https://github.com/backnotprop/plannotator/pull/1671), and an
[opt-in Claude Code modification](https://github.com/backnotprop/plannotator/pull/1672).
Plan revisions update the same tab. This moves review toward an ongoing
conversation with the agent that produced the work.

The separate hosted [Workspaces](https://plannotator.ai/workspaces) product
describes shared Markdown/HTML authoring, passage threads, decisions, Git
history, and API/CLI/MCP access. Its public status is private beta/waitlist;
the read does not establish a general launch.

Question answers now have explicit revision behavior worth comparing with
Leaf's declarations; stored review history alone does not establish replay of
arbitrary widget decisions. The companion
[effective-html](https://github.com/plannotator/effective-html) skills taught
freehand HTML composition. Those instructions are worth comparing with Leaf's
rendered-page checks; it is not a substitute for Leaf's state declarations.

## lavish-axi

Read on 2026-08-12, 2026-09-22, and 2026-10-04 from its
[repository](https://github.com/kunchenguid/lavish-axi).
Lavish serves an agent-authored HTML file locally and returns queued annotations
through a CLI poll. It deliberately injects no design system, so the file
renders consistently inside and outside its review chrome. Playbooks supply
composition instructions; native controls and action attributes supply input.
Conversation history, revision legends, and reviews survive restart.

The October read found
[server-acknowledged replies](https://github.com/kunchenguid/lavish-axi/pull/392)
that clear Working when accepted, and
[editing queued annotations](https://github.com/kunchenguid/lavish-axi/pull/394)
in place. When a replacement invalidates an edited annotation's target, its
draft remains available as unsent feedback. The latest release,
[v0.1.82 on October 4](https://github.com/kunchenguid/lavish-axi/releases/tag/lavish-axi-v0.1.82),
also lets interactive ARIA widgets receive clicks during annotation.
The direction remains local HTML review, with a more complete conversation and
revision loop. Adoption still needs a test of whether anchors and decisions
retain their meaning through an artifact rewrite.

Its Mermaid-to-Excalidraw editing and standalone asset export are useful
capabilities to study. Its live DOM checks also offer a different correction
path: the user's browser reports overflow and clipping, and the user batches a
repair prompt. Leaf checks a publication before handoff. Leaf's
[render gate](../skills/leaf/scripts/leaf/render_gate/version.py) includes desktop
and narrow viewports and sweeps layout transitions.

## Sideshow

Read on 2026-10-04 from its [repository](https://github.com/modem-dev/sideshow),
[releases](https://github.com/modem-dev/sideshow/releases), and
[hosted site](https://sideshow.sh/).
Sideshow gives an existing agent a board of posts combining HTML, Markdown,
diagrams, diffs, terminal output, images, JSON, code, and traces. It supplies the
renderers and theme, with HTTP, CLI, MCP, Pi, and Claude Code integration.
Anchored comments, embedding, and Cloudflare screenshot sharing already
existed by July.

The latest public core is
[v0.14.0, September 7](https://github.com/modem-dev/sideshow/releases/tag/v0.14.0),
with no later merged main work found. August–September additions include a
[collapsible sidebar and compact live updates](https://github.com/modem-dev/sideshow/releases/tag/v0.13.0),
[Copy as Markdown in a unified Share menu](https://github.com/modem-dev/sideshow/pull/257),
and [Recent Posts Home across sessions](https://github.com/modem-dev/sideshow/pull/260).
The direction is browsing and distributing visual work. The hosted site also
advertises Cloud beta, organizations, invitations, shared boards, and activity
feeds; their operation behind login and introduction dates were not verified.

The [agent guide](https://github.com/modem-dev/sideshow/blob/main/guide/AGENT_HOWTO.md)
requires a watcher or checkpoint drain: stored comments do not themselves wake
an idle agent. A [Claude plugin monitor repair](https://github.com/modem-dev/sideshow/pull/243)
remained open. The
[HTML bridge](https://github.com/modem-dev/sideshow/blob/main/server/surfacePage.ts)
returns text comments through `sendPrompt()`, while
[visual anchors](https://github.com/modem-dev/sideshow/blob/main/viewer/src/Card.tsx)
use surface coordinates. Neither establishes Leaf's declared decision fold or
semantic passage reattachment across rewrites.

[Source downloads](https://github.com/modem-dev/sideshow/pull/266),
[wide mode](https://github.com/modem-dev/sideshow/pull/268),
[session archives](https://github.com/modem-dev/sideshow/pull/256), and
[standalone session export](https://github.com/modem-dev/sideshow/pull/227)
were open proposals, not shipped features.

## Workbench

Read on 2026-07-31 and 2026-10-04 from [Workbench](https://workbench.md/) and its
[agent API](https://workbench.md/agents.md).
Workbench combines multiplayer Markdown editing, exact-text comments,
suggestions, live cursors, named versions, and interactive fences for boards,
chat, sheets, charts, and status. HTTP, CLI, MCP, webhooks, and event watches
connect agents that run on the user's compute.

<<<<<<< HEAD
The October documentation describes coordination beyond the July summary:
atomic claims on Asks, escalation of unclaimed or stale requests, an agent
registry with heartbeats, and account/folder watches spanning documents.
[Activity adapters](https://workbench.md/adapters.md) expose Claude Code, Codex,
and Cursor work. An appointed [chief of staff](https://workbench.md/chief.md)
routes requests across projects, maintains open items and briefs, and gets a
two-minute first-claim window. New appointments use scoped credentials.
The API also documents versioned skills and standalone HTML Agent Pages on an
isolated origin. These are public contracts, not verified signed-in workflows;
the linked repository returned 404, so introduction dates were unconfirmed.

Shared editing has its own revision contract: API writes apply minimal text
diffs. Supplying a document version rejects intervening changes; blind writes
have separate wipe and live-edit guards. Suggestions outside changed spans survive, while
rewritten targets orphan pending suggestions. Its bounded activity feed is
distinct from Leaf's event fold of declared decisions. The comparison now
includes ongoing team coordination as well as collaborative editing; HTTP
access also reaches clients outside Leaf's coding-task adapters.

## Nimbalyst

Read on 2026-10-04 from its
[repository](https://github.com/nimbalyst/nimbalyst) and
[v0.79.1 release](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.79.1),
published September 30. Nimbalyst is broadening its coding-agent workspace into
persistent teammates and shared knowledge.

Released [Crew alpha](https://github.com/nimbalyst/nimbalyst/commit/95628b91b6)
is off by default. Teammates have role directives, notes, journals, scheduled
shifts, notification limits, and token budgets. September work also introduced
a [team wiki](https://github.com/nimbalyst/nimbalyst/commit/2cafa8e9ff) and
knowledge graph with citations and structured types.

October 2–4 [Pages work](https://github.com/nimbalyst/nimbalyst/commit/c890f538ab)
on main is newer than that release: nested team/personal pages, typed relations,
and direct agent edits. [Decisions, citations, and editable views](https://github.com/nimbalyst/nimbalyst/commit/567df78ac6)
mark sentences decided or open with attribution and connect evidence to prompts,
answers, comments, or web sources. Embedded views include tables, 2×2
comparisons, decisions, and open questions.

The useful Leaf comparison is the ownership and persistence of work and
decisions, not just document rendering. Nimbalyst supplies a broader agent
workspace. [Android parity work](https://github.com/nimbalyst/nimbalyst/commit/b5a50fa6c3)
adds remote session/worktree creation and synchronized Markdown editing;
the read did not verify a Play Store launch.

## Sfora

Read on 2026-10-04 from [Sfora](https://www.sfora.ai/), its
[agent API](https://www.sfora.ai/agents.md), and
[live changelog](https://www.sfora.ai/changelog).
Sfora is a separate shared workspace for people and agents: projects, cards,
posts, chat, documents, and PRs have stable Markdown-file paths over HTTP.
Agents have their own member identities and API keys. Its claim and event
contracts support asynchronous coordination; humans use the browser or Mac app.

September 7–8 updates made the library a folder-based knowledge base with
search filters, keyboard navigation, file previews, and reversible trash.
The live changelog supplied those dates; the search cache still showed July.
Sfora is relevant to shared project ownership and durable results rather than
Leaf's authored page for one principal. No signed-in workflow was tested.

## Agentation

Read on 2026-10-04 from its
[repository](https://github.com/benjitaylor/agentation) and
[v3.1.0 release](https://github.com/benjitaylor/agentation/releases/tag/v3.1.0).
No new default-branch work was found since the September 22 comparison.
The September release already added nested same-origin iframe selection,
Shadow DOM selection, editor integration, richer feedback exports, and
asynchronous Send callbacks.

Agentation embeds precise annotation into an existing application. It is a
reference for selecting rendered targets and connecting feedback to a host,
rather than a document revision or persistent agent-workspace model.
||||||| 95c3d8ab6
Its shared editing and hosting are a different product boundary from Leaf's
agent-authored page for one principal. HTTP access broadens the set of clients;
Leaf's host adapters place deliveries into the user's existing coding task.
Collaborative document editing remains the relevant comparison, rather than the
mechanism of one blocking poll.
=======
Its shared editing and hosting are a different product boundary from Leaf's
agent-authored page for one principal. HTTP access broadens the set of clients;
Leaf's harness adapters place deliveries into the user's existing coding task.
Collaborative document editing remains the relevant comparison, rather than the
mechanism of one blocking poll.
>>>>>>> origin/main

## html-effectiveness

Read on 2026-07-31 from the
[repository](https://github.com/anthropics/html-effectiveness).
The gallery contained standalone HTML for reviews, reports, slides, diagrams,
and small editing interfaces. Editing state stayed client-side and returned
through an export the user could paste or commit. It is a composition reference;
Leaf supplies the live comment-and-revision loop.

## CopilotKit

Read on 2026-08-20 and 2026-09-22 from
[CopilotKit](https://github.com/CopilotKit/CopilotKit) and
[AG-UI](https://github.com/ag-ui-protocol/ag-ui).
CopilotKit supplied frontend SDKs, an application runtime, and backend agent
integrations. AG-UI transported typed events, shared-state snapshots and patches,
and human-input results. The September read recorded AG-UI's schema-first 1.0
freeze with generated SDKs and a conformance corpus
([PR #2783](https://github.com/ag-ui-protocol/ag-ui/pull/2783)).

The distinction is the application and its users. A developer registers
components, deploys the application, and configures the agent it calls. The model
chooses components and props, emits a tree against a catalog, or generates HTML
inside a sandboxed message. Leaf's author is the user's existing coding task;
it authors the page and can extend a package within the same session.

Human-in-the-loop tools suspend an application run until the user answers.
Shared-state APIs let both sides update an agent state object. Leaf instead
starts with authored markup and folds the event log; its passage comments also
identify the exact text being discussed. The models serve different persistence
and addressing needs, so a shared-state stream is not a replacement for Leaf's
revision contract.

Two practices are worth borrowing: schema-derived authoring instructions, and
integration probes kept identical across backends. Managed-agent adapters change
who runs the agent without changing the developer-owned component model.

## herdr

Read on 2026-08-23, with release movement checked on 2026-09-22, from the
[repository](https://github.com/herdrdev/herdr).
Herdr was a terminal multiplexer with agent-aware panes. A background server
owned workspaces, tabs and layouts; users and agents manipulated the same
objects through the TUI, CLI, or socket API. Agent states rolled up into the
sidebar, with lifecycle hooks preferred over per-agent terminal-text matching.

This is useful evidence for shared controls and attention across tasks. It does
not supply a document, passage comments, or a reconciliation model for decisions
against a rewritten page. Leaf's page activity and outstanding Asks have their
own semantics; an agent's process state does not establish who owes a response.

## Declarative UI formats

Read from project repositories in August and revisited on 2026-09-22. These
projects described how models compose a UI against declared components.

| Project | Authoring and state model observed | Integration question for Leaf |
| ------- | ---------------------------------- | ----------------------------- |
| [json-render](https://github.com/vercel-labs/json-render) | A flat `root` and `elements` spec, with cataloged components, actions and functions; expressions and bindings update a local state model. | Its catalog-derived prompts and streaming compiler are useful mechanisms. A second store of user decisions would need to become part of Leaf's fold. |
| [OpenUI](https://github.com/thesysdev/openui) | OpenUI Lang uses component calls with positional arguments in the catalog's schema order. The September read found OUI-1 and its public [benchmark](https://github.com/thesysdev/generative-ui-bench). | Measure authoring quality and token cost against actual HTML tasks; shorter notation alone does not supply revision, anchoring, or replay. |
| [Hashbrown](https://github.com/liveloveapp/hashbrown) | TypeScript exposes components; streaming schemas identify props safe to render before generation finishes. | Partial rendering is a useful experiment, but Leaf's published passage identities must remain well-defined. |
| [A2UI](https://github.com/a2ui-project/a2ui) | Versioned JSON messages create surfaces and update components and per-surface data. JSON Schema catalogs allow renderers on different toolkits. | Cross-platform rendering is the benefit; a catalog renderer does not itself provide Leaf's durable page and log. |

The September read found json-render v0.21.0 with an experimental
[Jev](https://json-render.dev/docs/jev) choice model. A2UI's 1.0 remained a
candidate on the [roadmap](https://a2ui.org/roadmap/) and added Express and
Elemental inference formats that compile to JSON. These are dated observations,
not present release status.

The formats suggest two experiments: a notation closer to models' existing
fluency, and selection among authored components rather than generation of a
whole tree. Neither answers how a comment follows a rewritten passage or how a
prior user decision constrains a new version.

Integration needs to preserve those semantics. Rendering a foreign spec inside
a widget requires declarations for its visible text, anchors and actions;
otherwise the embedded tree is opaque to Leaf's checks and log. Exporting Leaf's
registry as a catalog likewise needs more than component props: state verbs,
fold units, settlement, and Ask declarations are part of the vocabulary. Replacing
HTML with a protocol is a product change that needs evidence from authoring and
revision tasks, not merely a schema mapping.

The August search for “Open-JSON-UI” found documentation but no implementable
specification. The September read recorded CopilotKit retiring that page and
redirecting it to A2UI. OpenAI's
[structured-output UI sample](https://github.com/openai/openai-structured-outputs-samples/tree/main/generative-ui)
was a sample component catalog; it did not establish a standard under that name.
That is sufficient reason to exclude the name from integration candidates.

## MCP Apps

The September read found Codex UI support and tool-history metadata
([PR #45805](https://github.com/openai/codex/pull/45805)), while Claude Code CLI
support was still requested in
[issue #95149](https://github.com/anthropics/claude-code/issues/95149).
The [stable extension](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx)
described host-rendered `ui://` resources with a server-tool return path. The
[client matrix](https://modelcontextprotocol.io/extensions/client-matrix) is the
place to recheck host support before experimenting.

Leaf has no MCP Apps transport in the current tree. The remaining direct-resource
experiment and its host-specific acceptance criteria belong to
[notes/mcp-apps/PROJECT.md](mcp-apps/PROJECT.md); this comparison does not define a
second rebuilding plan. Inline presentation is a possible host route, while the
page directory and event log remain the durable record.

## When Leaf is the wrong choice

- **Collaborative document editing.** Leaf records input from one principal and
  does not model multiple user identities, live cursors, or concurrent author
  merges. Hosted workspaces address that need.
- **An HTTP-only agent.** Leaf's CLI and harness adapters assume a coding task that
  can run local commands. An HTTP document API has broader client reach.
- **An application serving many users.** Leaf accompanies an existing coding
  task; frameworks such as CopilotKit provide the application and agent runtime.
- **Hosted availability independent of the machine.** A standing Leaf server can
  outlive a session, and an export opens offline, but neither supplies a hosted
  collaboration service. An export has no agent or server behind its actions.
- **Direct document editing.** Leaf's user comments or uses authored controls;
  unrestricted editing of the document calls for an editor rather than an
  agent-mediated revision.

## Further comparisons

The September sweep recorded these adjacent projects. They remain leads for a
focused read, rather than evaluated integration candidates:

- Local review and document loops:
  [crit](https://github.com/tomasz-tomczyk/crit),
  [reviewable-html-workbench](https://github.com/u-ichi/reviewable-html-workbench),
  [Mirafold](https://github.com/mirafold/mirafold),
  [charrette](https://github.com/Ovich/charrette),
  [pi-plans](https://github.com/MaxInGaussian/pi-plans).
- Agent control interfaces:
  [Paseo](https://github.com/getpaseo/paseo),
  [OpenWork](https://github.com/different-ai/openwork), and
  [OpenBot](https://github.com/CopilotKit/OpenBot).
- Human-input queues:
  [Agent Inbox](https://github.com/langchain-ai/agent-inbox) and
  [HumanLayer](https://github.com/humanlayer/humanlayer).
- In-app annotations:
  [InstantCode](https://github.com/nguyenvanduocit/instantCode),
  [pi-annotate](https://github.com/nicobailon/pi-annotate), and
  [Vibe Annotations](https://github.com/RaphaelRegnier/vibe-annotations).
- Other UI renderers:
  [assistant-ui](https://github.com/assistant-ui/assistant-ui),
  [Tambo](https://github.com/tambo-ai/tambo),
  [proteus](https://github.com/sanskritifarswal/proteus), and
  [decided-ui](https://github.com/pjdurden/decided-ui).

The [generative UI index](https://github.com/narrowin/awesome-generative-ui) and
[coding-agent index](https://github.com/bradAGI/awesome-cli-coding-agents) help
scope a fresh survey.

## Explainer animation

Read on 2026-08-29 from documentation and published packages. This is a separate
package-design lead, not evidence that an animation dependency is ready to adopt.

| Project | Authoring model observed | Relevance to Leaf |
| ------- | ------------------------ | ----------------- |
| [Remotion](https://www.remotion.dev/) | React components evaluated by frame, with a Studio and render pipeline; first-party [agent skills](https://www.remotion.dev/docs/ai/skills). | Standalone branded video, captions and mixed media. |
| [Manim Community](https://docs.manim.community/en/stable/) | Python mathematical scenes rendered to video. | Standalone mathematical and algorithmic explanations. |
| [Markdy](https://markdy.com/docs/) | Browser nodes, groups, flows and beats, with layout and edge routing. | An animated-diagram authoring reference. On the read date, `@markdy/cli@1.1.1` could not install because `@markdy/compat` was missing from npm; retest before adoption. |
| [Elucim](https://elucim.com/) | JSON or YAML scenes with SVG and mathematical primitives, timelines and state machines. | A browser explanation model to evaluate on a real authored example. |

The useful common idea is separating semantic states from motion between them.
A Leaf package experiment can test that model without first building video export,
autoplay policy, or a broad animation framework.
