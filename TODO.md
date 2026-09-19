# TODO

Items are ordered by priority. Each names the result. When an item needs active
investigation detail, keep it in a linked note. Completed work and rejected alternatives
remain in git history. An item decided against leaves rather than staying with its
reasoning attached: a dependency, platform, or storage choice goes to the Rejected table
in [the survey note](notes/dependency-survey.md) as one line and the number that decided
it, and anything else goes to git history.

## Now

- **Establish the first agent-usability baseline.** Build the cold-authoring,
  reading-parity, and resume fixtures described in
  [the evaluation plan](notes/agent-usability-evals.md#first-executable-slice), then use
  their failures to choose any new reading interface.

- **Give conversations a clear, stable reading hierarchy.** Retain the current thread
  context while scrolling, disclose search and filters together with the active query,
  keep agent activity beside the comment it belongs to, and preserve selection and reply
  editing. Verify populated short and long threads in light and dark at wide and narrow
  widths. Keep document prose calm and the working chrome compact rather than decorative.

- **Prototype region-aware annotation placement.** Compare a pinned marker card with a
  sparse left-comment layout across one ordinary document and one workspace. Keep complete
  history and search in Threads, use the existing Page Map dialog on narrow pages, and
  never leave both margin presentations visible at once.

- **Audit visual coherence across complete reader journeys.** Compare an ordinary
  document, a workspace, a dense table or board, and a populated conversation against the
  intended editorial and technical aesthetic. Fix repeated system-level gaps in type,
  spacing, framing, control hierarchy, and responsive behavior; avoid playful consumer-app
  ornament.

- **Weigh the focus ring once, for every keyboard target.** The 2px accent ring
  (`--here-ring` in `skills/leaf/assets/theme.css`) may be too strong on a large target:
  a walked-to thread card or inline thread wears it inset over the quiet ground, and the
  perimeter reads heavier there than around a button. The card was given the ring so that
  a keyboard arrival looks the same everywhere, so whatever weight wins applies to every
  target that wears it; do not soften it on the card alone.

## Make Leaf feel like a game

`skills/leaf/SKILL.md` states the contract: the reader sees what the page wants of them
without reading it first, every state offers a move, and a move shows its result at
once. This is about what a page asks of a reader, not about ornament — the visual
coherence audit above still rules out consumer-app decoration, and the two agree that a
reader should never have to work out what to do next.

- **Play each shipped example through as a sequence of moves.** At every state a reader
  can reach in `review-a-plan`, `triage-board`, `pr-walkthrough` and `ship-review`, ask
  what the page wants next and whether a move is visible that does it. Record the dead
  ends: a state that offers nothing, a move whose result is not visible, and a page whose
  objective only appears after reading. The phone survey's first item is one such dead
  end — a touch reader cannot target an element at all.

- **Give a page one reading of how far the reader has got.** The banner's `Asks 0/1` is
  the only score Leaf keeps, so a page carrying a board, several Asks and a version to
  approve has no single answer to "how much of this is still mine". Decide what counts
  toward that reading before adding a second counter beside the first.

- **Show the plan as well as the step.** App Server's plan updates and Claude Code's task
  list both say how far along the work is, and Leaf keeps only the current step. A short
  checklist in the status disclosure would let a reader see progress without asking.

- **Find a specific first task for the public home page.** A visitor's first move is the
  tutorial level, and the current page starts with the comment-and-revise loop: a visitor
  asks Leaf guide to edit their private copy. Replace that interim prompt only after
  testing a task a new visitor would actually bring; avoid canned choices that
  manufacture work for the guide.

- **Measure a pending count in the favicon.** Prototype the count at 16px and keep it
  only if it remains legible beside the existing status treatment.

## Agent activity on the page

The reader should always be able to tell what the agent is doing and whether it is still
doing it. [The responsiveness note](notes/reader-feedback-responsiveness.md) holds the
ordering contract these items extend.

- **Measure whether agents keep the banner current.** Run the agent evals the
  responsiveness note describes against the current guidance: a delivery, a multi-step
  task, and a task long enough to delegate. Score whether a status write precedes each
  step and whether the reader's new input is claimed before the work continues.

- **Observe Claude Code's tool steps as App Server observes Codex's.** A `PreToolUse` hook
  could record the current step for pages the session holds, so the banner stays current
  when the agent does not write. The existing hook's `uv run` takes about 0.2 s even for a
  session holding no page (measured 2026-09-17), which every tool call in every session
  would pay, so the hook needs a check that exits at once for such a session. The row and
  disclosure already divide the two readings the way Codex's stream now uses, so a hook
  would write `observed` and change no wording.

- **Teach the hosted website agent to declare its steps.** Its banner sentence comes from
  the tool steps App Server watches, so the reader gets the step verbatim — `Running
  /bin/zsh -lc '$LEAF delivery claim … && rg --files …'` — which is the whole argument for
  the agent saying it in its own words. A "declare each step before you start it"
  paragraph in `worker/server.py` wrote four good sentences and cost the turn its reply
  (2026-09-17), so any wording has to leave the turn's response operations exactly as they
  were, and `verify_site.py local` is the check that says whether it did.

- **Decide the banner's pick when several subject claims stand.** The guidance now has
  the coordinator write one sentence covering its workers, which leaves this to the
  threads and widgets that legitimately hold claims at once: with a reader move
  outstanding the fold takes the claim with the highest log floor rather than the newest
  write (`activity.py`), so which one the banner names is close to arbitrary. Either
  choose deliberately or list the standing claims in the status disclosure with their
  subjects and ages.

- **Settle what a margin entry's colour says about whose turn it is.** A thread reading
  is now blue while `awaitsReader` holds and green while the agent is working on it, and
  those two colours were chosen one at a time. Decide the scheme as one thing: whether
  the reader's turn deserves a hue of its own rather than the accent's, and whether a
  thread on nobody should say so at all. The third surface is the Threads panel's On you
  facet chip, which declares an `lf-needs` class (`conversation/narrowing.js`) that no
  stylesheet reads — a hook left for the colour this decision would give it.

- **Decide whether a later agent turn should hide an earlier agent question.** With no
  structural Ask, `_thread_awaits_reader` reads only the latest spoken turn, so a thread
  whose root is an agent comment and whose latest spoken turn is an agent reply carrying
  no `awaits` reads as on nobody, however plainly the root asked. A structural Ask
  deliberately survives a later plain turn; the comment-is-a-question rule does not.
  Either make the two agree or say why they should differ. This decides the banner's
  count and the panel's On you filter as well as the margin, so it is one change in
  `events.py`'s projection rather than a second reading beside it. No page in the corpus
  stands that shape today, so seeding one is the first step and the evidence the
  decision needs. The nearest thread, the feature gallery's `bg-resolved-text`, is both
  answered and resolved, and `resolved` clears only on an explicit `unresolve`, so it is
  not a shortcut to one.

- **Decide whether delegated work may hold a reader move open across turns.** The Stop
  hook refuses to end a turn over an acknowledged move with no answer, so a coordinator
  replies with what it started before its worker runs. A live worker claim on the move's
  subject could count as handling instead, leaving one reply when the work finishes.

## Architecture simplification

The 2026-09-13 to 09-17 Lit application arc closed #1 and #3, which git history now
carries. A 2026-09-18 survey measured what remains and added #25 to #27; its evidence is
the `leaf-simplification` page directory in the state home. Ids here share one space with
the workspace research below, which reaches #23, so a new item starts above that.

- **#4 — Delete the browser's second derivation of the server's semantics.** The server
  already folds the Ask inventory, winner and retraction resolution, and each thread's
  `awaits_reader`, and ships all three on `/api/state`; the browser discards them and
  derives them again in `scripts/browser/application.ts` — `deriveAsks` across lines 342 to
  517, `deriveThreadReaderObligations` 528 to 582, the ask predicates between them, plus a
  re-fold of the `actions` and `desired` id lists the wire carries for exactly that purpose.
  Roughly 750 lines, arrived in #746. The two copies of the `when` predicate already
  disagree, Python testing presence and TypeScript testing non-null, so an attribute
  recorded as `null` reads differently on each side. Nothing on either side compares them.
  Keep the pending-attempt ledger and the DOM-captured authored baseline, which are the
  browser's real work. Restore the ~35 lines of page-ask serialization
  `served_state/document.py` computes and drops, and delete the ask payload
  `served_state/conversation.py` ships that nothing reads. A shared parity corpus follows
  this rather than preceding it: built first, it would police an implementation that is
  about to go.

- **#25 — Give the Worker one App Server client instead of two.** `worker/server.py`
  imports 16 symbols from `leaf.codex`, three of them private, and then re-implements the
  connection lifecycle `AppServerClient` owns: the `initialize`/`initialized`/`thread/resume`
  prologue three times across the two files, `_send` twice, and the reconnect backoff four
  times — already drifted, `min(failures, 5)` against `min(self.failures - 1, 5)`. One
  subscription class with a delivery-source hook deletes 550 to 650 lines. Both carriers
  are live and tested, so this is a restructure rather than a deletion of dead code.

- **#5 — Separate the pure margin model from stateful presentation.** Produce the complete
  cluster and Page Map reading as immutable data, then let retained-control presentation
  and placement consume it independently. `margin-projection.js` is 3,072 lines in one
  factory; roughly 650 would move and what it deletes directly is small. The return is that
  the model becomes testable without Chrome, which `test_render_margin.py` currently spends
  6,351 lines on, and that an entry's identity and focus standing stop living on
  `dataset.lfMarginEntry*` across the 77 sites that write them onto nodes and read them
  back.

- **#6 — Separate Codex delivery protocol, durable state, and process supervision.** Keep
  App Server message interpretation, the queue and receipt ledger, and adapter process and
  lease management in distinct layers if hosted-agent delivery remains a product priority.

- **#7 — Test model rules without rebuilding whole browser journeys.** Keep browser tests
  for focus, selection, pointer identity, layout, accessibility, and synchronous
  presentation. Cover pure folds with compact model fixtures. The declarative layer
  manifest landed in #753. `tests/` is 137,643 lines against 106,577 of implementation, and
  1,372 of the 2,315 tests are browser render tests across 88,868 lines. Of those, 296
  across 13,263 lines drive no input, read no geometry and assert on no focus — they load a
  page to read state back, and are what a model fixture would replace. No pure test covers
  `projection.py`, `asks.py` or `conversation.py`. This follows #5 and #4 rather than
  leading them: what makes the folds reachable without a browser is giving them a home off
  the DOM.

- **#8 — Decentralize keyboard feature knowledge.** Have feature owners contribute explicit
  capabilities at boot and leave the dispatcher generic. The condition this item waited on
  is met: `createPageKeys` takes 53 named capabilities and `leaf.js` mirrors all 53, so a
  core command costs one line in each of three files, while a package widget already
  registers through `keys()` and costs none. Eleven of the 53 are scopes a feature declared
  locally and `page.js` names again. It moves about 900 lines and deletes about 170,
  including the `rung()` ladder whose own guard stands down for the layer stack.

- **#27 — Admit every event through one door.** Six of the nine `append_event` callers
  check no contract: `cmd_comment`, `cmd_reply`, `cmd_edit` and `cmd_resolve` in
  `conversation.py`, the `pickup` in `session.py`, and the `note` in `publishing.py`. Of
  the three that do check, `cmd_report` reaches `event_contracts.py` and `cmd_receipt`
  uses a validator `requests.py` defines itself, so the rules are in two homes as well as
  the gate being in three — `event_endpoint.accept_event` for browser events and
  `service.append_event` for widget kinds, with the CLI going through neither.
  `event_log` stamps an id and a timestamp and checks no schema, so whatever a caller
  hands it lands in the log. Validate once at the edge: one admission door the CLI writers
  share, not a validator added per caller.

## Platform and dependency cutover

The 2026-09-16 survey of what Leaf could hand to a dependency found the browser defect
record concentrated in margin placement, geometry timing, and the keyboard register, which
no library owns; a component library would have covered 15 to 20 of the last 175 fixes. The
direction chosen: keep Lit, and replace hand-built behavior with settled libraries and
browser features one at a time as each proves out. The evidence, the rejected
candidates, and the Leaf choices worth reconsidering are in
[the survey note](notes/dependency-survey.md).

Effort is S (under two days), M (two to ten), or L (weeks). Saving is lines deleted,
measured unless marked est., plus the defect class removed. A measured figure is the size
of the region a library would take over, not what it deletes: the landed swaps (#753)
deleted 56 of a measured 130 for psutil, 6 of 262 for unidiff, 3 of ~100 for watchfiles,
and 78 of ~180 for dependency-cruiser, because the refusals, contracts, and definitions
around a mechanism stay. A deletion well under the scored figure can still be worth
taking for the kind of code it removes: psutil's 56 lines were two platform doors of
hand-laid `proc_pidinfo` and `sysctl` struct layouts through ctypes. Confidence is how likely the
swap works as described without a spike, weighing adopter evidence and Baseline status.
Effort and confidence are estimates unless the row cites a measurement. Each table is
ordered by confidence, then effort.

### JavaScript

| Change | Effort | Saving | Confidence | Risk |
|---|---|---|---|---|
| Order the cascade with `@layer` (theme, package, page). Needs the chrome isolated from page CSS first — a shadow root, or Leaf wrapping page styles in `@scope … to (.lf-chrome)` — because a page's unlayered `<style>` otherwise outranks the chrome: tried 2026-09-16 and backed out when one page rule moved 53 chrome boxes. | M | ~50 `!important` and the specificity contests | Low-Med | Every rung assignment re-decides a tuned contest, and only the suite finds which |
| Invoker commands (`command`, `commandfor`, Chrome 135) for the eight runtime modules that call `showModal` or the popover methods, so the control that opens a surface declares the opening. Today `keyboard/layer-stack.js` learns of a pointer-opened surface from the `showModal` and `showPopover` patches and the `beforetoggle` listeners, so the entry carries no origin to restore; an invoker could hand it one. | S-M | ~50 to 100 est. | Low-Med | Chromium-only, so below Chrome 135 the button does nothing unless the module keeps its handler |

### Both

| Change | Effort | Saving | Confidence | Risk |
|---|---|---|---|---|
| Bind one loopback port per MCP page with a wildcard-port `frame_domains`, removing MCP multiplexing under `/p/<capability>` as one of the two callers of the route-scoping regexes in `http.py`; the 69 rooted URL literals under `assets/` and `packages/` go relative. | M | ~75 of 155 | Low-Med | The wildcard needs an MCP-host check; leaf.page's example roots keep the mechanism |

## General reader continuity

- **#11 — [Let newer navigation win over revision
  restoration](notes/workspace-followups.md#item-11).** Use navigation intent to prevent
  an old reading capture from overwriting input made during revision activation. The
  race belongs to version travel generally; independent pane scrollports only exposed
  more instances of it.

## Workspace follow-ups

The workspace research after [PR #455](https://github.com/max-sixty/leaf/pull/455)
produced the following backlog. IDs match the research discussion, not GitHub issues.
The [research briefs](notes/workspace-followups.md) retain evidence, completion
criteria, dependencies, and Sol/Astra assignments. Items are ordered within each group.

Continue with the remaining composition verification.
Keep the current primitives; let those uses establish demand for more. Defer the
authoring evaluation until Leaf's shape is stable enough for the comparison to last.

### Composition verification

- **#14 — [Verify the complete keyboard and accessibility
  route](notes/workspace-followups.md#item-14).** Exercise the workspace as one keyboard
  task, including reading, pane furniture, local comments and Threads.

### Authoring and product boundary

- **#19 — [Measure what Leaf saves an authoring
  agent](notes/workspace-followups.md#item-19).** Run a small blind authoring comparison
  against plain HTML, including the cost of the subsequent feedback cycle. Extend the
  existing agent-usability evaluation plan with this comparison.

- **#20 — [Teach the few compositions that earn their
  place](notes/workspace-followups.md#item-20).** Put tested document, configuration and
  queue/detail recipes into the existing package guidance.

- **#22 — [Verify workspaces at the experimental MCP
  boundary](notes/workspace-followups.md#item-22).** Check the same workspace in a full
  iframe, a constrained host and the existing snapshot/browser handoff.

- **#23 — [Find out whether people return to a
  workspace](notes/workspace-followups.md#item-23).** Run repeated real tasks to decide
  how much persistence and workspace customization Leaf should own. Requires Max to
  choose and participate in real recurring tasks.

## Reading on a phone

Leaf's focus is desktop, and a phone reader now gets a working page: since b0e78287 the
runtime starts in WebKit, and selecting text, commenting, replying, answering an option
and moving a board card all work at 393px, with no shipped example scrolling sideways.
The items below are what a survey of `review-a-plan`, `triage-board`, `pr-walkthrough`
and `ship-review` found missing in an emulated iPhone. Emulation does not show iOS's own
selection callout, the software keyboard, Safari's collapsing toolbars, or a real
long-press or pinch, so settle anything that depends on those on a device first. The
thread panel's touch grip has its own item under Later.

- **Let a touch reader comment on an element, not only on selected text.** The routes to
  an element target are Alt-click, the `s` key, and a "Respond to…" button that appears
  on keyboard focus alone (`skills/leaf/assets/runtime/chrome.css`), while the shortcut
  bar that teaches `s` is hidden at a coarse pointer — which also removes the only
  pointer route to the command list. Tapping a board card, a diagram, a diff line or a
  disclosure therefore does nothing. Decide what a phone reader may target before
  choosing the affordance; the `s` target picker behind the ⋯ menu would reach the same
  targets the keyboard does.

- **Show a phone reader that a passage has a thread.** Margin markers and pickup receipts
  are hidden below 900px (`runtime/margin-projection.js`'s `hide` fallback,
  `assets/theme.css`), so a comment beside a task is invisible, although tapping the text
  still opens it and Threads still lists it. The reaction row already moves into the text
  flow when the margin has no room; the same reflow for markers would keep the page
  honest about what it holds.

- **Make a delivered document declare its viewport.** `references/page-authoring.md` puts
  `<meta name="viewport">` in the authoring template and nothing checks for it, so a page
  authored without one lays out at 980px on a phone and none of the runtime's
  coarse-pointer or narrow-width rules apply. Supplying it at delivery, beside the
  encoding, CSP, theme and stylesheets a delivery already adds, would make the phone
  layout a property of the runtime rather than of the author's memory.

- **Find out whether the interactive-reply crash reaches real hardware.** In emulated
  iPhone WebKit, opening a thread's interactive reply
  (`runtime/conversation/messages.js`) crashes the page process every time between 393px
  and 540px and never at 560px or wider, while Chromium at the same size is unaffected.
  The panel focuses the message and scrolls it into view smoothly twice, and the crash
  lands about eight frames later; reduced motion does not prevent it, so the smooth
  scroll may not be the cause. Reproduce it on a device before choosing a fix.

- **Finish the phone polish the same survey listed.** Placeholders and badges name keys a
  phone cannot press (`Comment… · c` and `Reply · ⌘⏎` from `runtime/composing/input.js`,
  and the `1 2 3` badges a pick control paints); a disabled "Approve version" keeps its
  reason in a hover tooltip (`runtime/banner.js`); `pr-walkthrough` opens a 1026px
  diagram in a 295px box, and its diffs open with soft wrap off, cutting code at about 30
  columns; and the diff "+", the thread "Add reaction" and `<summary>` rows sit under the
  44px touch minimum. Each is small alone, and together they decide whether a phone
  reader can finish what the page asks.

## Later

- **Prefer a release tag when Leaf adopts named versions.** When the running payload's
  commit has an exact Git tag, report that tag as its version and keep the commit hash as
  the fallback for untagged builds.

- **Let readers disable character bindings.** One route filter with a complete persistence
  and accessibility contract. Commands, non-character routes, and visible controls stay
  available.

- **Open visual-review targets beside Leaf through the host.** Coordinate the exact case
  URL in a real browser pane and report mutable-preview staleness, without treating
  arbitrary iframes as live evidence.

- **Add a foreground path for other agent hosts.** Document a blocking `leaf wait` flow for
  any host that can run a command, then define a shared host adapter only if another
  integration needs it.

- **Give the touch grip room of its own, then fit more thread cards.** At a coarse pointer
  the panel's 44px resize grip lies over the list with nothing reserving its space, so
  whether its focus ring lands on a button is luck. A full-height gutter would contradict
  a local handle, and spacing alone cannot fit a third card — the reply box and
  Send/Resolve row every card carries already exceed a third of the list. Collapse a card
  to a single Reply affordance until the reader enters it.

- **Make the experimental direct MCP bundle fail loud on an evaluation-order fault.**
  Esbuild hoists cross-module `let`/`const` into `var`s in
  `scripts/mcp-app/direct-build.mjs`, so a fault the ordinary page throws reads `undefined`
  in that experimental bundle. Give its probe a reading that sees the fault, or preserve
  the dead zone.

Parked until something triggers them:

- **A proper diff for suggested replacements**, if a before-and-after view in Threads and
  inline conversations reviews nontrivial edits better than the plain replacement.
- **Expanded inspection for visual review**, if focused workspaces turn out not to cover
  the real tasks; package-owned until a second interactive object proves the lifecycle.
- **Author-facing "tabbed section" vocabulary**, if a real page exposes an ambiguity that
  root and embedded placement cannot resolve.
- **Disclosed masks in visual-review evidence**, once repeated reviews establish the
  smallest disclosure and export contract.
- **Typed motion evidence**, once Leaf core has durable video, poster, caption, transcript,
  and chapter handling.
