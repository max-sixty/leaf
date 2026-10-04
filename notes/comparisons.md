# Notes on nearby projects

This is dated research for maintainers, not a current feature matrix. External
projects were read from their own repositories and documentation between
2026-07-31 and 2026-08-29, then revisited on 2026-09-22. The sections below
consolidate those reads; external availability and implementation details need a
fresh check before an integration decision.

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

Read on 2026-08-21 and 2026-09-22 from its
[repository](https://github.com/backnotprop/plannotator).
Plannotator reviewed work the agent had already produced: plans, Markdown,
rendered HTML, local diffs, and repository reviews. Harness hooks opened a local
browser review, blocked where necessary, and returned structured annotations.
Its installer supported more coding harnesses than Leaf's adapters.

The September read found an append-only feedback archive and PR comments that
survived pushes, marked Outdated rather than re-anchored. This supersedes the
August description of each invocation as an isolated review. History is useful
without implying replay of arbitrary widget decisions into a rewritten page.

Two capabilities are useful references: review of Git, Jujutsu, Perforce and
GitButler changes, and encrypted sharing of plans. The companion
[effective-html](https://github.com/plannotator/effective-html) skills taught
freehand HTML composition. Those instructions are worth comparing with Leaf's
rendered-page checks; it is not a substitute for Leaf's state declarations.

## lavish-axi

Read on 2026-08-12 and 2026-09-22 from its
[repository](https://github.com/kunchenguid/lavish-axi).
Lavish served an agent-authored HTML file locally and returned queued annotations
through a CLI poll. It deliberately injected no design system, so the file
rendered consistently inside and outside its review chrome. Playbooks supplied
composition instructions; native controls and action attributes supplied input.

The September read found durable conversation history, revision legends, and
reviews that survived restart. Those additions supersede the August claim that
nothing survived a send or reload. The remaining question for any adoption is
whether its anchors and decisions retain their meaning through a rewritten
artifact, rather than whether it stores history at all.

Its Mermaid-to-Excalidraw editing and standalone asset export are useful
capabilities to study. Its live DOM checks also offer a different correction
path: the user's browser reports overflow and clipping, and the user batches a
repair prompt. Leaf checks a publication before handoff. Leaf's current
[render gate](../skills/leaf/scripts/leaf/render_gate/version.py) includes desktop
and narrow viewports and sweeps layout transitions; the old conclusion that
Leaf never renders a phone width no longer holds.

## Workbench

Read on 2026-07-31 from [Workbench](https://workbench.md/).
Workbench presented a hosted Markdown workspace for people and agents editing
together. It offered exact-text comments, suggestions, boards, live cursors,
named versions, and an append-only activity feed. Agents could use HTTP
long-polling, webhooks, or a supervised watcher.

Its shared editing and hosting are a different product boundary from Leaf's
agent-authored page for one principal. HTTP access broadens the set of clients;
Leaf's harness adapters place deliveries into the user's existing coding task.
Collaborative document editing remains the relevant comparison, rather than the
mechanism of one blocking poll.

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
  [Nimbalyst](https://github.com/nimbalyst/nimbalyst),
  [OpenWork](https://github.com/different-ai/openwork), and
  [OpenBot](https://github.com/CopilotKit/OpenBot).
- Human-input queues:
  [Agent Inbox](https://github.com/langchain-ai/agent-inbox) and
  [HumanLayer](https://github.com/humanlayer/humanlayer).
- In-app annotations:
  [Agentation](https://github.com/benjitaylor/agentation),
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
