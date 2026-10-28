# Notes on nearby projects

This is dated research for maintainers, not a live feature matrix or an adoption
plan. The 2026-10-23 survey refreshes the October 4 project comparison and the
September 22 renderer baseline, and adds major-lab features and newly assessed
projects. Sections outside that survey retain their read dates. Evidence is
primary documentation, releases and source, with earlier limited public-demo
use in Workbench, Sfora, Agentation and Plannotator. The October survey did not
exercise signed-in collaboration, persistence or live agent-host delivery.
Release, preview, current documentation and main-only work are distinguished;
missing evidence does not establish missing capability. Recheck availability
before an integration decision.

The comparison asks what the agent authors, where the work lives, and how user
input returns. Leaf authors HTML with an extensible registered vocabulary. A
page directory holds immutable revisions and an append-only event log; surviving
user decisions carry into later revisions unless explicitly retracted. These
contracts live in [page-storage.md](../src/leaf/page-storage.md)
and [packages.md](../skills/leaf/references/packages.md).

Delivery belongs to the harness adapter. The owning
[Claude Code](../skills/leaf/references/harness-claude-code.md) and
[Codex](../skills/leaf/references/harness-codex.md) contracts define queued input,
idle wakeup and replies; a tool or panel being available does not establish the
whole route. Serving, authentication, lifetimes and offline export belong to
[serving-pages.md](../skills/leaf/references/serving-pages.md).

## Interaction lessons for Leaf, 2026-10-23

**Session continuity and locality.** Leaf's useful comparison is review beside
the agent already doing the work, with local evidence and tools in reach. Valid
file revisions become live without a separate upload, and anchored feedback
returns to the owning session. This can reduce handoff and repeated explanation,
even for prose. It does not make model inference local or inherently faster,
and browser-local controls can respond immediately in hosted products too.
Claude Code Artifacts also updates from the working session and returns comments
subject to its watch contract. Compare the available complete workflow, rather
than assuming that using a native artifact loses session context.

The [October 22 reply study](user-feedback-responsiveness.md#a-small-page-changes-reply)
illustrates the boundary: three waiting Codex App Server trials averaged 19.4 s
from admitted comment to admitted reply; 17.8 s was an unsplit model bucket
including dispatch, waiting and generation, and 0.1 s was delivery. These were
HTTP inputs on a heavily loaded Mac, not browser-visible or cross-product
measurements. Local files provide control of the record and access to local
tools; remote models still receive whatever the session sends.

**Persistence and meaning.** Plannotator questions, Nimbalyst Wiki, Space Pages
and Claude artifact storage now make durable work an explicit competing
capability. A stored answer alone does not establish what it means after a
rewrite. The useful comparison is an answered interface revised around a
person's decisions, passage comments, unsent drafts and reading position, then
resumed through the supported route after its original session ends. Leaf's
[tasks](../src/leaf/todos.py) already outlive execution attempts; process state,
delivery and a fulfilled obligation are separate facts.

**Views and evidence.** Earlier Workbench and Sfora demos showed alternate views
over the same workspace objects, without establishing server persistence.
Sheets canvas now documents a synchronized interface over canonical spreadsheet
data. Claude Dashboards exposes queries and refresh times. These are concrete
comparisons for inspectable evidence and replaceable views, without requiring a
second source of truth for Leaf's decisions.

**Composition and attention.** Hashbrown separates selecting populated
components from generating their props; OpenAI's native UI streams composition.
A useful comparison includes initial output and several feedback/revision
turns, not just tokens for one HTML document. Crit's scroll fixes and
assistant-ui's composer continuity illustrate why a final screenshot is
insufficient evidence for preserving attention. None of these observations
alone selects a new renderer or changes Leaf's scope.

## Claude Code Artifacts

Read on 2026-10-23 from the [Claude Code artifact contract](https://code.claude.com/docs/en/artifacts)
and [Artifacts help](https://support.claude.com/en/articles/17153992-what-are-artifacts-and-how-do-i-use-them).
Claude Code publishes live pages hosted on claude.ai and updates them from the
publishing session, including a local CLI session. Hosting the page remotely
does not move the working agent into a separate assistant. Editor comments
sent to Claude, including mentions, return to that session and activate a
thread it can answer. Comment reads require v2.1.221+; auto-watch after publishing
requires v2.1.228+ and enabled flags. Permission mode can require approval, plan
mode pauses replies, activations are rate-limited, and watches can expire or
terminate on service failure. Public-only viewers cannot comment. These are
current version-gated contracts, not October launch dates or verified delivery
runs.

The public help now documents personal and shared data persisting between
sessions on paid web/desktop plans, with separate stores and a 20 MB text limit
per artifact. Current artifacts can save before publication; legacy artifacts
have different publication and deletion rules. The broader databases and
viewer-scoped access observed in the September session runtime remain
account-specific observations; they are not needed to establish persistence.
The [custom-artifact tutorial](https://academy.claude.com/tutorials/build-custom-artifacts-with-claude)
states that HTML export loses saved entries, Claude calls and connected-tool
behavior. Running the full artifact elsewhere requires building it as software.

The useful comparison is control over the record, export behavior, revision
semantics and the complete session return path. Neither “stateless artifact”
nor “review disconnected from the coding session” describes the current
published contract. Stored data does not by itself establish preservation of a
prior decision's meaning or passage anchors through arbitrary rewrites.

On [October 8](https://claude.com/resources/articles/dashboards-and-motion),
Docs, Slides and Design left beta on all plans. Dashboards entered paid-plan
beta with connected data, inspectable queries and refresh times; Motion entered
Team/Enterprise beta with editable animation code and MP4 export, rather than
generated video footage. Standalone Design closes December 14, including its
public links and chats/comments. [Duet](https://claude.com/resources/articles/claude-duet),
announced October 21, is a US Pro/Max waitlist research preview for proactive
work between visits using its own VM/browser, not broad availability.

## Other major-lab surfaces

Read on 2026-10-23. The relevant changes concern interface composition, shared
work and ongoing ownership; ordinary model benchmarks are outside this survey.

**OpenAI.** [Intelligent UI](https://openai.com/index/gpt-6-for-everyone/)
began rolling out in Chat on October 7: GPT-6 composes native streamable text,
graphics, controls and charts, with rendering during generation. The announcement
says the models powering Work/Codex are unchanged; it does not claim those
products had no feature changes. No public arbitrary-component extension API
was established. [September 29 release notes](https://help.openai.com/en/articles/6825453-chatgpt-release-notes)
introduced Pages and Codex Cloud; October 16 introduced Slides.
[Space's current contract](https://help.openai.com/en/articles/20001549-getting-started-with-space-in-chatgpt)
describes direct editing, passage comments, page chat, real-time collaboration
and private ChatGPT per collaborator. Page creation/editing is listed for Pro,
Business and Enterprise; Slides is rolling out and Sheets is “coming soon”.
Session-visible tools are not proof of general release or account entitlement.

[Dots](https://openai.com/index/introducing-dots/), announced September 29,
provides always-on agents with cloud computers, plugins and ongoing goals;
[current availability](https://help.openai.com/en/articles/20001530-getting-started-with-your-dot)
is limited by plan, region and workspace eligibility. Local-computer access is
optional and initially off. The October 15
[Sites Enterprise admin preview](https://help.openai.com/en/articles/10128477-chatgpt-enterprise-and-edu-release-notes)
is a distinct hosted application surface with public publishing separately
enabled. These products cover different boundaries; their union is not one
substitute with one availability or preservation contract.

**Google.** [Sheets canvas](https://blog.google/products-and-platforms/products/workspace/sheets-canvas-for-google-sheets-spreadsheets/)
launched August 13 and is an older omission from the comparison. Generated
mini-apps live as spreadsheet tabs; edits in the canvas or sheet synchronize,
and sharing follows the sheet. [September 23 connected apps](https://blog.google/innovation-and-ai/products/gemini-app/new-connected-apps-gemini/)
add services including Airtable, Linear, monday.com, Adobe and Webflow.
Gemini Canvas's generation and [visual app editing](https://blog.google/products-and-platforms/products/gemini/gemini-drop-september-2025/)
date to 2025; [Opal's agent step](https://blog.google/innovation-and-ai/models-and-research/google-labs/opal-agent/)
dates to February 2026. These establish useful baselines, not October launches.
No distinct October Canvas/Opal release was established by this bounded search.

**Microsoft.** The current [SharePoint HTML-page contract](https://support.microsoft.com/en-us/sharepoint/create-edit-publish-html-pages)
supports generated/uploaded HTML and direct text editing, while explicitly
excluding co-authoring, comments, arbitrary outbound API calls, third-party live
data and localStorage. A sandbox permits limited managed libraries. It is a
page distribution route with a narrower feedback loop; the exact rollout date
was not independently established.

## Plannotator

Read on 2026-10-23 from its [repository](https://github.com/backnotprop/plannotator),
releases and [Inbox contract](https://plannotator.ai/docs/reference/inbox/).
Plannotator reviews plans, Markdown, HTML, diffs and repository changes. Review
history and PR comments survive pushes, with changed targets marked Outdated.
Its existing question cards, media review and originating-session Ask AI made
it an ongoing conversation as well as a review window.

[Inbox v0.28.8](https://github.com/backnotprop/plannotator/releases/tag/v0.28.8)
shipped October 7 as a preview. Local project threads hold questions, decisions,
annotated attachments and guided reviews; attachments retain their sent version
and report subsequent changes. [v0.28.14](https://github.com/backnotprop/plannotator/releases/tag/v0.28.14)
lets an agent replace or withdraw an open question by identity: the old card
links to its replacement and stale picks cannot be sent. The current answer
rule is [v0.28.26](https://github.com/backnotprop/plannotator/releases/tag/v0.28.26):
untouched questions stay open and Skip is explicit. That release adds task
cards, persistent reply drafts and automatic insertion into a busy native
agent's turn after five minutes. These are explicit unanswered-question
semantics, not proof of general replay of answered widgets through HTML rewrites.

Delivery differs by host. Claude Code, Pi and OpenCode 2 receive a new turn
when idle; other MCP clients call `wait_for_reply`. [v0.28.24](https://github.com/backnotprop/plannotator/releases/tag/v0.28.24)
adds Send now into running native turns. [v0.28.16](https://github.com/backnotprop/plannotator/releases/tag/v0.28.16)
adds a phone layout and rerouting from an ended session to a live project
session or the next agent. Codex connectivity does not establish idle wakeup.
The October 5 [v0.28.4](https://github.com/backnotprop/plannotator/releases/tag/v0.28.4)
read already found the Claude module in the release, with classic hooks on
unsupported hosts; the current Inbox contract owns the supported routes.

[Multi-file review](https://github.com/backnotprop/plannotator/releases/tag/v0.28.5)
now returns exact paths and rejects obsolete tabs by review identity.
[Media anchors](https://github.com/backnotprop/plannotator/releases/tag/v0.28.7)
can reattach by source, refusing ambiguous duplicates and changed sources.
Those are specific provenance guarantees worth comparing. The separate hosted
[Workspaces](https://plannotator.ai/workspaces) remains private beta/waitlist;
its advertised shared authoring is not a generally available deployment of the
local Inbox. [effective-html](https://github.com/plannotator/effective-html)
remains a composition-instruction reference.

## lavish-axi

Read on 2026-10-23 from its [repository](https://github.com/kunchenguid/lavish-axi)
and releases. Lavish serves agent-authored HTML locally and returns queued
annotations through CLI polling. It injects no design system; this is not a
claim that served files are byte-for-byte unchanged, as the
[v0.1.92 correction](https://github.com/kunchenguid/lavish-axi/releases/tag/lavish-axi-v0.1.92)
makes explicit. Playbooks supply composition guidance, and native controls and
action attributes supply input. Conversation history, revision legends and
reviews survive restart.

The October 4 baseline already included server-acknowledged replies, editing
queued annotations and preservation of drafts whose targets became invalid.
October 6 [v0.1.83](https://github.com/kunchenguid/lavish-axi/releases/tag/lavish-axi-v0.1.83)
adds per-note seen/working/done receipts; October 9
[v0.1.85](https://github.com/kunchenguid/lavish-axi/releases/tag/lavish-axi-v0.1.85)
adds Excalidraw libraries and October 10
[v0.1.86](https://github.com/kunchenguid/lavish-axi/releases/tag/lavish-axi-v0.1.86)
lets artifacts choose their initial annotation mode. These strengthen the local
review loop. Preservation of anchors and decision meaning through a rewrite
still needs a shared interaction test.

Mermaid-to-Excalidraw editing, standalone asset export and live DOM checks remain
useful references. The user's browser can report overflow/clipping for a batched
repair prompt; Leaf's [render gate](../src/leaf/render_gate/version.py) checks
publication across desktop/narrow viewports and layout transitions.

## Sideshow

Read on 2026-10-23 from its [repository](https://github.com/modem-dev/sideshow),
[releases](https://github.com/modem-dev/sideshow/releases), and
[hosted site](https://sideshow.sh/).
Sideshow gives an existing agent a board of posts combining HTML, Markdown,
diagrams, diffs, terminal output, images, JSON, code, and traces. It supplies the
renderers and theme, with HTTP, CLI, MCP, Pi, and Claude Code integration.
Anchored comments, embedding, and Cloudflare screenshot sharing already
existed by July.

The latest public core is
[v0.14.0, September 7](https://github.com/modem-dev/sideshow/releases/tag/v0.14.0),
with no later default-branch work found on October 23; hosted Cloud and other
branches were not assessed. August–September additions include a
[collapsible sidebar and compact live updates](https://github.com/modem-dev/sideshow/releases/tag/v0.13.0),
[Copy as Markdown in a unified Share menu](https://github.com/modem-dev/sideshow/pull/257),
and [Recent Posts Home across sessions](https://github.com/modem-dev/sideshow/pull/260).
The direction is browsing and distributing visual work. The hosted site also
advertises Cloud beta, organizations, invitations, shared boards, and activity
feeds; their operation behind login and introduction dates were not verified.

The [agent guide](https://github.com/modem-dev/sideshow/blob/main/guide/AGENT_HOWTO.md)
requires a watcher or checkpoint drain: stored comments do not themselves wake
an idle agent. The
[HTML bridge](https://github.com/modem-dev/sideshow/blob/main/server/surfacePage.ts)
returns text comments through `sendPrompt()`, while
[visual anchors](https://github.com/modem-dev/sideshow/blob/main/viewer/src/Card.tsx)
use surface coordinates. Neither establishes Leaf's declared decision fold or
semantic passage reattachment across rewrites.

## Workbench

Read on 2026-07-31, 2026-10-04 and 2026-10-23 from [Workbench](https://workbench.md/) and its
[agent API](https://workbench.md/agents.md).
Workbench combines multiplayer Markdown editing, exact-text comments,
suggestions, live cursors, named versions, and interactive fences for boards,
chat, sheets, charts, and status. HTTP, CLI, MCP, webhooks, and event watches
connect agents that run on the user's compute.

The current documentation describes coordination:
atomic claims on Asks, escalation of unclaimed or stale requests, an agent
registry with heartbeats, and account/folder watches spanning documents.
[Activity adapters](https://workbench.md/adapters.md) expose Claude Code, Codex,
and Cursor work. An appointed [chief of staff](https://workbench.md/chief.md)
routes requests across projects, maintains open items and briefs, and gets a
two-minute first-claim window. New appointments use scoped credentials.
The API also documents versioned skills and standalone HTML Agent Pages on an
isolated origin. These are public contracts, not verified signed-in workflows;
a reliable dated changelog/source release was not established, so recent
changes and introduction dates remain unknown. The chief contract requires
managed-session records with an objective, independent completion probe,
expected artifact, cadence and deadline; no supervisor run was observed.

Shared editing has its own revision contract: API writes apply minimal text
diffs. Supplying a document version rejects intervening changes; blind writes
have separate wipe and live-edit guards. Suggestions outside changed spans survive, while
rewritten targets orphan pending suggestions. Its bounded activity feed is
distinct from Leaf's event fold of declared decisions. The comparison now
includes ongoing team coordination as well as collaborative editing; HTTP
access also reaches clients outside Leaf's coding-task adapters.

## Nimbalyst

Read on 2026-10-23. Nimbalyst combines a coding-agent workspace with persistent
knowledge. The September [Crew alpha](https://github.com/nimbalyst/nimbalyst/commit/95628b91b6)
was off by default and supplied teammates with directives, notes, journals,
schedules, notification limits and token budgets.

The baseline's main-only Pages work shipped in
[v0.80.0 on October 5](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.80.0):
typed nested pages, named relations, decided/open sentence markers, citations to
sessions and web sources, editable views, history and restore. It was renamed
Wiki in [v0.80.5](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.80.5).
The October 9 [Wiki beta](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.80.6)
supports plain local project files offline without an account, alongside shared
team storage; the CLI and plugin work without the desktop app.

October adds [Codex CLI support](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.81.1),
[browser-editable drawings, spreadsheets and other views](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.81.2),
[sandboxed interactive HTML](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.81.5)
and [Wiki maintenance tools](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.81.6)
for broken/orphaned/stale pages and recorded decisions/questions.
[v0.82.0 on October 23](https://github.com/nimbalyst/nimbalyst/releases/tag/v0.82.0)
adds static local Wiki export with page URLs, search, backlinks and read-only
embedded views. Person fields and pages marked `export: false` are excluded by
default. This is a released authored knowledge workspace, including upkeep and
publication. Its stored decisions and histories do not establish the semantics
of answered controls or passage anchors through arbitrary rewrites.

## Sfora

Read on 2026-10-23 from [Sfora](https://www.sfora.ai/), its
[agent API](https://www.sfora.ai/agents.md) and
[dated changelog](https://www.sfora.ai/changelog).
Sfora supplies shared projects, cards, posts, documents and chat with stable
Markdown-file paths over HTTP, agent member identities, claim ownership and
events. September's library work added folders, search filters, previews and
reversible trash. The October 6 release adds attachment access through CLI,
MCP and HTTP, including image results, and reports a draft-privacy repair
across API, comments, mentions, previews, inbox and webhooks. October 7 adds a
product manual and repairs first-repository attachment.

The current banner advertises local Markdown operation without an account;
the agent API describes local/self-hosted origins. The manual still begins
with workspace/account creation. Local distribution, introduction date and
installed behavior were not verified, so a blanket hosted-only description is
unwarranted. Shared identity and ownership remain the useful comparison.
Earlier [Boards demo](https://www.sfora.ai/features/boards) use retained cards
across Board → Map, demonstrating alternate views rather than persistence or
signed-in concurrency.

## Agentation

Read on 2026-10-23 from its
[repository](https://github.com/benjitaylor/agentation) and
[v3.1.0 release](https://github.com/benjitaylor/agentation/releases/tag/v3.1.0).
No new default-branch work was found since the September 22 comparison.
Main has 3.1.2 / MCP 1.3.2 version bumps while GitHub Releases lists v3.1.0;
the npm publication was not checked. The September release already added
nested same-origin iframe selection,
Shadow DOM selection, editor integration, richer feedback exports, and
asynchronous Send callbacks.

Agentation embeds precise annotation into an existing application. It is a
reference for selecting rendered targets and connecting feedback to a host,
rather than a document revision or persistent agent-workspace model.

## html-effectiveness

Read on 2026-07-31 from the
[repository](https://github.com/anthropics/html-effectiveness); an October 23
default-branch check still found the May 15 HEAD, with no newer work.
The gallery contained standalone HTML for reviews, reports, slides, diagrams,
and small editing interfaces. Editing state stayed client-side and returned
through an export the user could paste or commit. It is a composition reference;
Leaf supplies the live comment-and-revision loop.

## CopilotKit

Read on 2026-10-23 from [CopilotKit](https://github.com/CopilotKit/CopilotKit)
and [AG-UI](https://github.com/ag-ui-protocol/ag-ui). CopilotKit supplies frontend
SDKs, an application runtime and backend integrations. AG-UI carries typed
events, shared-state snapshots/patches and human-input results. Its
[September 30 1.0 announcement](https://www.copilotkit.ai/blog)
follows the schema freeze already recorded in the September comparison.
[October 21 adapter releases](https://github.com/ag-ui-protocol/ag-ui/releases/tag/release/2026-10-21)
repair persisted approval recovery, retain deferred tool batches and recover
child results. A stable wire schema does not finish durable resumption.

A developer registers components, deploys an application and configures the
agent. Human-input tools can suspend a run and shared-state APIs let both sides
update it. Leaf instead accompanies the user's existing coding task and folds
its authored state and declared events. These are different ownership and
revision models; neither stored state nor transport interrupts alone establishes
passage reattachment or the meaning of decisions through rewritten documents.
Schema-derived authoring instructions and identical integration probes across
backends remain useful mechanisms to compare. CopilotKit's newer document and
agent templates are described under “Newly assessed projects”.

## herdr

Read on 2026-10-23 from its [repository](https://github.com/herdrdev/herdr).
Herdr is a terminal multiplexer whose background server owns workspaces, tabs
and layouts shared by TUI, CLI and socket API. Agent states roll up into its
sidebar. [v0.9.4 on October 13](https://github.com/herdrdev/herdr/releases/tag/v0.9.4)
adds plugin updates and stronger shutdown/session recovery.
[v0.9.5 on October 14](https://github.com/herdrdev/herdr/releases/tag/v0.9.5)
removes Codex turn hooks and returns Codex status to screen detection. Its
integration is not uniformly hook-based. Further shutdown/server fixes on
October 23 main were newer than the stable release.

This is a reference for shared controls and attention across tasks. A process
or terminal's status does not establish who owes a reply or whether a promised
result was delivered.

## Declarative UI formats

Read on 2026-10-23. These projects expose a component vocabulary to a model;
release status and language/transport compatibility are separate questions.

- [json-render](https://github.com/vercel-labs/json-render) represents a flat
  `root`/`elements` tree with cataloged components, actions, functions and local
  bindings. Its experimental Jev composition and TanStack Start renderer
  shipped in [v0.21.0 on September 18](https://github.com/vercel-labs/json-render/releases/tag/v0.21.0).
  October's [v0.21.1](https://github.com/vercel-labs/json-render/releases/tag/v0.21.1)
  and [v0.21.2](https://github.com/vercel-labs/json-render/releases/tag/v0.21.2)
  mainly repair forms, serialization, PDF repeats and registry actions.
- [OpenUI Lang 1.0](https://www.openui.com/docs/openui-lang/whats-new), released
  October 12, adds custom functions, typed actions and stored messages carrying
  context/form values. Root-first programs render progressively; truncation
  before a root renders blank. React supports 1.0 while the migration guide
  still places Vue/Svelte/Angular on 0.4. Its released
  [A2UI adapter](https://www.openui.com/docs/api-reference/a2ui) uses
  1.0-candidate lifecycle envelopes but replaces component JSON with OpenUI
  statements. This protocol variant does not make arbitrary catalogs interchangeable.
- [Hashbrown v0.8](https://github.com/liveloveapp/hashbrown/releases/tag/v0.8.0),
  released October 22 PT, adds typed decisions and UI selection. Application
  code can populate candidate props while a model selects the component, or
  selection can narrow a kit before generation fills props.
  [v0.7](https://github.com/liveloveapp/hashbrown/releases/tag/v0.7.0) adopted
  AG-UI 1.0 and exported UI-kit JSON schemas for agents outside Hashbrown.
  The project's latency claims were not independently measured here.
- [A2UI](https://a2ui.org/roadmap/) remains 0.9.1 stable with 1.0 candidate.
  October's [Python core](https://github.com/a2ui-project/a2ui/releases/tag/python/a2ui-core/v0.4.0)
  and [agent SDK](https://github.com/a2ui-project/a2ui/releases/tag/python/a2ui-agent-sdk/v0.9.0)
  releases add cross-catalog references and split the SDK from agent frameworks.
  Express leaves its experimental package path; Elemental/Atom remain
  experimental. Stale renderer milestones on the roadmap need source checks
  before an integration decision.

Selection among authored components is now a concrete alternative to generating
a whole tree. Shorter notation or stored form context alone does not establish
comment reattachment or how a prior decision constrains a later version.
A Leaf integration would need to expose visible text, anchors and actions
through its existing declarations; otherwise foreign content is opaque to its
checks and log. A registry-to-catalog mapping also needs state verbs, fold
units, settlement and `x-awaits`, not just component props. Authoring and
revision tasks can test that cost before selecting a format.

The August search for “Open-JSON-UI” found no implementable specification; the
September read found CopilotKit redirecting that page to A2UI. OpenAI's
[structured-output sample](https://github.com/openai/openai-structured-outputs-samples/tree/main/generative-ui)
is a component-catalog sample, not a separate standard.

## MCP Apps

Read on 2026-10-23. The
[stable extension](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx)
defines host-rendered `ui://` resources and a server-tool return path.
[SDK 2.0.0](https://github.com/modelcontextprotocol/ext-apps/releases/tag/v2.0.0)
shipped September 8 with API/dependency changes while retaining wire
interoperability; [2.0.3](https://github.com/modelcontextprotocol/ext-apps/releases/tag/v2.0.3)
changed example dependencies, not the library. No newer wire expansion was
identified in this survey.

The [community client matrix](https://modelcontextprotocol.io/extensions/client-matrix)
is a lead for host testing, not proof of a working Leaf journey. Rendering,
CSP, assets, tool calls, reopening and idle-session delivery need separate
checks in the actual host. A tool exposed to this account or a panel entry does
not establish general availability or complete delivery. Leaf's host experiment
and acceptance criteria belong to
[issue #4086](https://github.com/max-sixty/leaf/issues/4086), not a second plan in
this note; work in another checkout is not evidence of a landed integration.
The page directory/event record and the host transport have separate lifetimes.

## When Leaf is the wrong choice

The fit depends on the complete work-and-review loop. Local evidence and active
iteration with the working session are positive reasons to choose Leaf even
for prose. A native surface that preserves the same context and feedback can be
simpler. Format alone does not settle that choice, and the surface must actually
be available in the user's host.

- **Collaborative document editing.** Leaf records input from one principal;
  live co-editing, user identities and concurrent author merges belong to shared
  document/workspace products.
- **An HTTP-only agent.** Leaf's CLI and harness adapters assume a task that can
  run local commands. An HTTP document API reaches other clients directly.
- **An application serving many users.** Leaf accompanies the user's existing
  task; application frameworks provide deployment and an application-owned
  agent runtime.
- **General hosted team collaboration.** leaf.page does persist canonical page
  records and matching responses outside its containers before acknowledging
  writes ([storage owner](../worker/leaf_website/storage.py)). Its limits are
  browser-identity/release scope and running-turn continuity, rather than
  disposable accepted state. The [website design](../docs/website.html) and
  [Worker contract](../worker/README.md#saved-state-and-capacity) define that
  trial boundary; they do not supply team accounts or co-editing.
- **Direct document editing.** A Leaf user comments or uses authored controls;
  unrestricted editing calls for an editor. A one-off answer or a finished
  deck can likewise be simpler in its native surface when no local review or
  recorded decision is needed.

## Newly assessed projects

Read on 2026-10-23. Announcement dates, repository creation and first releases
are different evidence; several entries were earlier leads rather than new projects.

**Open Intelligent UI.** [Announced October 9](https://www.copilotkit.ai/blog/introducing-open-intelligent-ui)
as a public CopilotKit template choosing text, native components or generated
interactive answers. Its [architecture](https://github.com/CopilotKit/OpenIntelligentUI/blob/main/docs/architecture.md)
uses separate answer snapshots: arbitrary iframe state is not automatically
synchronized and there is no cross-call DOM patch API. Backend checkpoint
history is bounded process memory. The announcement reused a March repository.
This is a close composition reference, not evidence of a durable shared document.

**OpenDots.** [Announced October 1](https://www.copilotkit.ai/blog/introducing-opendots)
as an alpha template with nested Pages, direct editing, per-page conversations,
review-before-save, schedules and optional computers. SQLite stores pages and
configuration with revision checks. Conversations depend on CopilotKit
Intelligence; [setup](https://github.com/CopilotKit/OpenDots/blob/main/docs/SETUP.md)
requires hosted Intelligence, a renewable local evaluation or licensed
self-hosting. [Soar's October 22 announcement](https://www.copilotkit.ai/blog/introducing-soar)
is instead a commercial early-access deployment offer for company coworkers.
Neither establishes a service-independent OSS runtime or tested deployment.

**Tambo and Charming.** The [October 1 shutdown notice](https://tambo.co/blog/posts/tambo-is-shutting-down)
says Tambo Cloud API stops after October 31 and hosted data is scheduled for
deletion November 30. Open-source Tambo remains self-hostable. The founder
attributes the pivot to stronger frontend generation, low sustained adoption
and demand for apps made with people's existing agents; that is his account,
not market-wide causal proof. [Charming](https://usecharming.com) offers
collaborative hosting, data and authentication for those apps. Its first-launch
date and signed-in durability were not established. The pivot questions the
value of generation alone without showing that component catalogs have no use.

**fictty.** Its [first public release](https://github.com/brancusi/fictty/releases)
was October 10 PT. JSON UI, stable node IDs and exact text/state readback make
it relevant to agent-readable interfaces and live data. Current main separates
application data from UI and uses revision-checked writes, but the
[October 13 architecture decision](https://github.com/brancusi/fictty/blob/main/docs/design/architecture.md)
moves its target from terminal to GPUI native windows. Latest release v0.2.2
predates that work. Native main is prototype evidence, not a released terminal
capability or a reason to replace Leaf's browser.

**Crit.** An existing February project promoted from the watchlist.
[v0.23.0 on October 16](https://github.com/tomasz-tomczyk/crit/releases/tag/v0.23.0)
adds Mermaid rendered-target comments mapped to source lines, a renderer
registry and search across virtualized diffs. It also reviews Markdown,
static HTML and proxied applications.
[v0.23.1 on October 23](https://github.com/tomasz-tomczyk/crit/releases/tag/v0.23.1)
preserves concurrent comments and avoids scrolling as document threads grow.
These are useful addressing and attention examples, without an assessed general
decision-replay contract.

**Swarmstorm.** [Charrette was renamed October 23](https://github.com/Ovich/swarmstorm/commit/5713e748d570d14f6bb0cdddf5f28d1d678aa198).
Its [source](https://github.com/Ovich/swarmstorm) describes a shared
planning/execution board and aiview companion for local specs, diagrams,
mockups, variants and design decisions. The inspected manifest was 2.4.1 with
no GitHub releases returned. This is a workflow companion, not a new renderer
standard or a newly launched competitor.

## Chopin and Planning with Agents

Read on 2026-10-27 from Maggie Appleton's talk
[Planning with Agents](https://maggieappleton.com/planning-agents), its demo videos,
and GitHub Next's [Chopin write-up](https://githubnext.com/projects/chopin)
(research prototype, published September 2026, by Krzysztof Cieślak and Maggie
Appleton). Chopin itself was not used.

The talk argues that planning as multiple-choice questions in a CLI, ending in a wall
of Markdown to approve, leaves the human unable to judge what they decide. Plans
should be boundary objects built for human understanding: visual, interactive,
social, and grounded in the real codebase. Chopin is a multiplayer planning document
in an MDX editor, with a planner agent in a side chat, embedded diagrams, and
decisions that record who answered and when. That is the closest product framing to
Leaf's we have found: a shared document the agent writes, with decisions recorded in
place. Leaf differs in its append-only log and revisions, and in running beside the
user's own harness rather than hosting the agent. Chopin's write-up reports
multiplayer planning, which Leaf doesn't do (see "When Leaf is the wrong choice").

The talk's four demos each give one decision its own instrument: a shadow scale tuned
on the app's real cards, with each shadow layer drawn as a tile; a card-motion easing
curve to drag; a video player driving its own state diagram; and three retry-logic
branches built and compared by every call site's outcome. Appleton says they were
made "essentially designing all of these examples myself", since agents aren't yet
good at visual explanation.

On the same shadow-scale task, a fresh agent following Leaf's instructions built a
settings form of percentage sliders, while an agent copying her design got the
instrument close in about half an hour. What still pulled that copy down was Leaf's
frame: a required generic control, page CSS skipping controls built with `offer()`,
and the playground's own rail and actions bar. #4478 removes those three obstacles,
and #4479 rewrites the playground author guide around the decision's goals. The
lesson is that Leaf's value is the instrument shaped for the decision with Leaf's
record behind it, and Leaf should stay out of that instrument's way.

## Further comparisons

The following September leads were not deeply refreshed in the October survey;
that is a coverage choice, not a claim of inactivity:

- Local review/document loops: [reviewable-html-workbench](https://github.com/u-ichi/reviewable-html-workbench)
  and [pi-plans](https://github.com/MaxInGaussian/pi-plans).
- Agent control: [Paseo](https://github.com/getpaseo/paseo) and
  [OpenBot](https://github.com/CopilotKit/OpenBot).
- Human-input queues: [Agent Inbox](https://github.com/langchain-ai/agent-inbox)
  and [HumanLayer](https://github.com/humanlayer/humanlayer).
- In-app annotation: [InstantCode](https://github.com/nguyenvanduocit/instantCode),
  [pi-annotate](https://github.com/nicobailon/pi-annotate) and
  [Vibe Annotations](https://github.com/RaphaelRegnier/vibe-annotations).
- Renderers: [proteus](https://github.com/sanskritifarswal/proteus) and
  [decided-ui](https://github.com/pjdurden/decided-ui).

[Mirafold](https://github.com/mirafold/mirafold) was checked October 23: public
beta, native agent engines, persistent sessions and pinned dashboards;
[v0.9.1](https://github.com/mirafold/mirafold/releases/tag/v0.9.1) remains the
September 9 release, with no newer default-branch work found since September 22.
[OpenWork v0.18.60](https://github.com/different-ai/openwork/releases/tag/v0.18.60)
adds desktop scripting, takeover/continue and restored unsaved document editing.
[assistant-ui 0.15.30](https://github.com/assistant-ui/assistant-ui/releases/tag/%40assistant-ui/react%400.15.30)
adds explicit Resume and synchronous composer-state visibility to preserve the
caret. These are continuity mechanisms, not proof of a document revision model.

The [generative UI index](https://github.com/narrowin/awesome-generative-ui) and
[coding-agent index](https://github.com/bradAGI/awesome-cli-coding-agents) remain
search leads rather than evaluated integration candidates.

## Explainer animation

Read on 2026-08-29 from documentation and published packages. This is a separate
package-design lead, not evidence that an animation dependency is ready to adopt.

| Project                                                    | Authoring model observed                                                                                                                     | Relevance to Leaf                                                                                                                                                       |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Remotion](https://www.remotion.dev/)                      | React components evaluated by frame, with a Studio and render pipeline; first-party [agent skills](https://www.remotion.dev/docs/ai/skills). | Standalone branded video, captions and mixed media.                                                                                                                     |
| [Manim Community](https://docs.manim.community/en/stable/) | Python mathematical scenes rendered to video.                                                                                                | Standalone mathematical and algorithmic explanations.                                                                                                                   |
| [Markdy](https://markdy.com/docs/)                         | Browser nodes, groups, flows and beats, with layout and edge routing.                                                                        | An animated-diagram authoring reference. On the read date, `@markdy/cli@1.1.1` could not install because `@markdy/compat` was missing from npm; retest before adoption. |
| [Elucim](https://elucim.com/)                              | JSON or YAML scenes with SVG and mathematical primitives, timelines and state machines.                                                      | A browser explanation model to evaluate on a real authored example.                                                                                                     |

The useful common idea is separating semantic states from motion between them.
A Leaf package experiment can test that model without first building video export,
autoplay policy, or a broad animation framework.

## affectUI

Read on 2026-10-15, with catalog counts refreshed October 23, from the [site](https://www.affectui.com/), its
[`llms.txt`](https://www.affectui.com/llms.txt), the
[license](https://www.affectui.com/license) and the free items'
[repository](https://github.com/flohoeller/affectui). affectUI listed 119
React 19 items for AI products, each one `.tsx` file whose styles sit in a CSS string,
installed through the shadcn CLI or an MCP server. 40 items were MIT; the other 79
were Pro, a one-time purchase of their source. Pro's license excluded a public
repository and "a page builder, design tool or similar product for others", which
rules out porting Pro source into Leaf. Every Pro item's live preview, keyboard map
and motion notes were public.

The CSS ports without React: folds animate `grid-template-rows` from `1fr` to `0fr`,
one easing, `cubic-bezier(0.22, 1, 0.36, 1)`, runs throughout and is nearly the
floating panel's, and each item honors `prefers-reduced-motion`. Colors are hex
values per component rather than shared tokens.

Patterns Leaf lacked on the read date:

- **A plan drawn as a plan.** Agent Plan keeps a run's steps in order in one card,
  done ones ticked and the current one timed, under "Running · 1 of 5". Leaf has
  since drawn the agent's plan (`leaf task plan`) in the floating panel, disclosed
  from its progress at the foot of On <agent>, each goal with its steps done and each
  step's state in place (#3195). Tool Call
  Card has no Leaf counterpart: tool calls belong to the harness's transcript.
- **Answering in a list row.** Agent Inbox and Decision Inbox put Approve and Reject
  in each row, with status and a live clock on the agent's rows. Leaf's floating
  panel's On view already answers inline.
- **Keys and stepping for suggestions.** Inline Diff binds Y and N at the current
  change, steps between changes, and offers Reject all beside Accept all.
- **A tray container.** A white card inside a gray tray, with status and actions on
  the tray and key hints inside the buttons ("Deny Esc").
- **Motion references** for the floating panel's motion pass: Number Ticker for
  counts and Blur Crossfade for content swaps.

Two of its behaviors conflict with Leaf's guarantees. An answered row confirms and
then folds away, carrying the next row under the pointer, where Leaf keeps an
answered item in place until its view closes. And toasts stack in a corner, where
Leaf's notices take the status line's seat.

On 2026-10-20 the user decided Leaf takes nothing further from affectUI: neither the
suggestion keys nor the tray, and no Pro purchase.
