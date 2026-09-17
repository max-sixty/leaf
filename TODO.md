# TODO

Items are ordered by priority. Each names the result. When an item needs active
investigation detail, keep it in a linked note. Completed work and rejected alternatives
remain in git history.

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

## Architecture simplification

- **#1 — Keep the semantic application root thin.** Let the application publisher own
  ordering, adoption, and publication while pure Ask, conversation, projection, and widget
  models retain their own modules. Do not replace DOM authority with one module containing
  every domain rule.

- **#2 — Replace manual presentation choreography with epoch presenters.** Have each
  presenter consume one immutable semantic epoch and report completion to the presentation
  coordinator. Remove hand-maintained renderer ordering and repeated conversation passes.

- **#3 — Make revision activation one explicit transaction.** Bound document fetch,
  reconciliation, widget capture, semantic adoption, and reader continuity behind one
  input and result. Give every stateful captured widget a stable identity.

- **#4 — Prove Python and browser semantic parity.** Let the server provide the complete
  accepted projection and keep the browser fold to explicit pending-event deltas. Run one
  shared corpus of Ask, conversation, retirement, and rollback cases against both
  implementations.

- **#5 — Separate the pure margin model from stateful presentation.** Produce the complete
  cluster and Page Map reading as immutable data, then let retained-control presentation
  and placement consume it independently.

- **#6 — Separate Codex delivery protocol, durable state, and process supervision.** Keep
  App Server message interpretation, the queue and receipt ledger, and adapter process and
  lease management in distinct layers if hosted-agent delivery remains a product priority.

- **#7 — Test model rules without rebuilding whole browser journeys.** Keep browser tests
  for focus, selection, pointer identity, layout, accessibility, and synchronous
  presentation. Cover pure folds and cross-runtime parity with compact model fixtures, and
  express runtime dependency policy in a small declarative layer manifest.

- **#8 — Decentralize keyboard feature knowledge when another change proves the need.** If
  a feature declaring commands locally must still modify the page keyboard coordinator,
  have feature owners contribute explicit capabilities at boot and leave the dispatcher
  generic.

## Platform and dependency cutover

The 2026-09-16 survey of what Leaf could hand to a dependency found the browser defect
record concentrated in margin placement, geometry timing, and the keyboard register, which
no library owns; a component library would have covered about 13 of the last 175 fixes. The
direction chosen: keep Lit, and replace hand-built behavior with settled libraries and
browser features one at a time as each proves out. The evidence, the candidates
considered and not added, and the Leaf choices worth reconsidering are in
[the survey note](notes/dependency-survey.md).

Effort is S (under two days), M (two to ten), or L (weeks). Saving is lines deleted,
measured unless marked est., plus the defect class removed. Confidence is how likely the
swap works as described without a spike, weighing adopter evidence and Baseline status.
Effort and confidence are estimates from the survey, not measurements. Each table is
ordered by confidence, then effort.

### JavaScript

| Change | Effort | Saving | Confidence | Risk |
|---|---|---|---|---|
| Order the cascade with `@layer` (theme, chrome, package, page) and one z-index scale. `chrome.css` has a `lf-reset` layer and `theme.css` one anonymous layer; the rest is specificity contests. | S | 50 `!important`, 46 `z-index`; the cascade defect class | High | Package themes and page CSS need a declared layer too |
| Use one positioning system: move the three CSS-anchored chrome menus in `chrome.css` onto Floating UI, which the margin projection and composing surface already use with virtual references and `size` and `hide` middleware. | S | ~10 CSS rules; a second positioning model | High | Floating UI must stay lazy at startup |
| Take the auxiliary-modality Tab wrap and the tabindex lending in `runtime/focus.js` from focus-trap or tabbable. | S | <100 | High | The lending to non-stops is Leaf policy the library must not fight |
| `light-dark()` for the 28-line dark token block in `theme.css`, which already sets `color-scheme: light dark`. | S | 28 | High | Each token states both values in one declaration, so a light-only token has to name its dark value |
| `closedby` (Chrome 134) for the light-dismiss policy `runtime/auxiliary-modality.js` and `runtime/native-layers.js` handle by hand; `@starting-style` with `transition-behavior: allow-discrete` for the `transitionend` tracking in `runtime/margin-entries.js` and `runtime/conversation/thread-card.js`. | S | ~100 to 200 est.; part of the dialog and Escape class | Med-High | `closedby` is Chromium-only |
| Typecheck the runtime with `tsc --checkJs`. `scripts/browser/tsconfig.json` already sets `allowJs`, `strict`, and `noEmit` and includes only its own `*.ts`; adding `checkJs` and the runtime's `*.js` to `include` checks the 42,000 lines as they ship, with no emit and no build. JSDoc annotations raise the coverage over time. | M | none deleted; part of the state-sync and repaint class (17 fixes) | Med-High | The first run's error volume; annotations needed for full value |
| Same-document View Transitions for version travel and margin motion. `theme.css:1997` already styles the root transition group and no runtime module calls `startViewTransition`; the FLIP helper in `runtime/motion.js` and the exit listeners above are what a transition replaces. | M | ~150 est. | Med | Baseline since October 2025, but no UI library depends on it |
| Make the page scroll normally: `html` as the scroller with fixed chrome, instead of `body` as the scroll container. Thirty fixes trace to scroll restoration, resize, and measuring before paint, and every library and browser feature assumes the normal setup. The reason for the current choice is not recorded; spike the switch and count which of those tests break. | M | part of the scroll and layout class (30 fixes) | Low-Med | Fixed chrome, print, and export may depend on the body scroller |
| Spike a morph with exclusions for the version patch (detail below). | M | 325 pairing lines in `runtime/dom-children.js` plus the pairs map every patch maintains | Low-Med | Must prove retention of opened `<details>`, tokenizer spans, lent tab stops, and widget-built children |
| Invoker commands (`command`, `commandfor`, Chrome 135) for the eight runtime modules that call `showModal` or the popover methods. | S-M | ~50 to 100 est. | Low | Chromium-only, no adopters |
| `focusgroup` (Chrome 150) for the list and toolbar arrow-key walks the keyboard register drives. | M | ~100 to 200 est. | Low | Chromium-only, no adopters |
| Navigation API for version travel history: three `history` and `popstate` sites, `runtime/navigation.js` at 197 lines. | M | small | Low | Gain only if intercept replaces the activation choreography |
| TanStack Hotkeys for the parsing, sequence timing, and cheat-sheet formatting slice of the keyboard register (detail below). | M | ~200 to 400 est. of 6,100 | Low | Alpha, 715 stars, no scope stack; the register's core stays either way |

### Python

| Change | Effort | Saving | Confidence | Risk |
|---|---|---|---|---|
| Run one user-level daemon on SQLite, starlette, and asyncio (detail below). | L | ~3,100; Windows; push instead of 50 ms polling | Med | Loses per-page process isolation and the grep-able JSONL log per page; tests that reach into `http.server` internals rework |

### Both

| Change | Effort | Saving | Confidence | Risk |
|---|---|---|---|---|
| Let the browser own anchoring (detail below). | M | 824 Python lines plus consumers; the byte-exact parity class | Med-High | One headless page load per `leaf comment`, about a second, unless the daemon keeps a browser warm |
| Bind one loopback port per MCP page with a wildcard-port `frame_domains`, removing MCP multiplexing under `/p/<capability>` as one of the two callers of the route-scoping regexes in `http.py`; the 69 rooted URL literals under `assets/` and `packages/` go relative. | M | ~75 of 155 | Low-Med | The wildcard needs an MCP-host check; leaf.page's example roots keep the mechanism |
| Move the server to TypeScript (detail below). | L | 12,900 mirrored Python lines collapse; two native wheels | Low | Forfeits the pytest suite and render harness; node is not guaranteed on Codex hosts; not incremental |

### Detail

- **Morph spike.** `runtime/dom-children.js` diffs authored source against authored source
  and writes the live tree through a pair table, so a reader's open `<details>`, tokenizer
  spans, lent tab stops, and module-built children survive a revision. idiomorph diffs the
  live tree instead, and its `beforeNodeRemoved` and `beforeAttributeUpdated` callbacks can
  refuse those four classes. Measure whether a morph plus the existing jsdiff change marks
  reproduces the patch's retention across the corpus before replacing the pairing.

- **TanStack Hotkeys.** `@tanstack/lit-hotkeys` 0.11 (alpha, June 2026) parses
  template-string bindings with a platform `Mod`, runs vim-style sequences with a timeout,
  tracks held keys, formats bindings for a cheat sheet, scopes a binding to a `target`
  element, and detects conflicts at registration. It has no scope stack, priority, or
  Escape unwinding, which `runtime/keyboard/dispatch.js` owns. Keep focus-ancestry scopes
  and `aria-keyshortcuts` reflection in Leaf. Wait for a stable release.

- **Daemon.** starlette, sse-starlette, uvicorn, and pydantic are already installed through
  `mcp`. Deleted: the detached-server handshake, flock leases, pid probing, stat polling,
  torn-line repair, and most of `http.py`'s dispatch. Examples ship `.jsonl` companions,
  which would become an import format.

- **Browser-owned anchoring.** The browser already posts quote, prefix, suffix, and
  section; `leaf comment` and the MCP snapshot resolve through the runtime in a Playwright
  page instead of `passages.py` and `anchor_capture.py`. The server's independent check of
  browser-supplied anchors protects nothing on localhost.

- **TypeScript server.** Every Python dependency has a node equivalent, and the anchoring
  and projection code would exist once. Do the daemon, anchoring, and CSP items first; each
  shrinks what this would port.

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
  commit has an exact Git tag, report that tag as its version and retain the commit hash
  as the fallback for untagged builds.
- **Share immutable revision resources by digest.** Two minimal default-layer
  revisions currently store 3,200,741 and 3,200,749 bytes, with 179 identical
  resource digests copied into both bundles. Put captured bytes in a page-local
  `objects/sha256/<digest>` store and let each immutable manifest retain the logical
  path, MIME type, dependency edges, and digest. Publication must write, verify, and
  fsync collision-checked objects before the revision manifest and HTML marker become
  discoverable. Historical HTTP routes, standalone export, and static-site output must
  continue to materialize the revision's logical paths. Prove crash recovery, digest
  collision refusal, revision replacement, repeated media, and a hundred-revision size
  profile before cutting over and deleting the per-revision resource copies.

- **Find a specific first task for the public home page.** The current page starts
  with the comment-and-revise loop: a visitor asks Leaf guide to edit their private copy.
  Replace that interim prompt only after testing a task a new visitor would actually
  bring; avoid canned choices that manufacture work for the guide.

- **Decide whether suggested replacements need a proper diff.** Compare the current
  plain replacement with a before-and-after view in Threads and inline conversations.
  Add the diff only if it makes nontrivial edits easier to review without duplicating
  the quoted passage.

- **Decide whether visual review needs expanded inspection.** Compare an embedded review
  with the same run as a bounded root review. Add expansion only if focused workspaces do
  not cover the real tasks, and keep it package-owned until a second interactive object
  proves the same entry, state-preservation, return, narrow-screen, copy, and print
  lifecycle.

- **2026-09-15 — Reconsider whether “tabbed section” needs explicit vocabulary.** Keep
  `lf-tabs` contextual while root placement and embedded placement fully distinguish
  page navigation from local alternatives. Introduce a separate author-facing term or
  element only if real pages expose an ambiguity that placement cannot resolve.

- **Let readers disable character bindings.** Define one route filter with a complete
  persistence and accessibility contract. Commands, non-character routes, and visible
  controls remain available.

- **Add disclosed masks to visual-review evidence.** Authored case-level focus areas now
  make small changes findable without adding nested review units. Add masks only once
  repeated reviews establish the smallest disclosure and export contract.

- **Open visual-review targets beside Leaf through the host.** Coordinate the exact
  case URL in a real browser pane and report mutable-preview staleness without treating
  arbitrary iframes as live evidence.

- **Add typed motion evidence after the media boundary supports it.** Define durable
  video, poster, caption, transcript, and chapter handling in Leaf core; then let visual
  runs attach motion only to cases whose timing or continuity is under review.

- **Add a foreground path for other agent hosts.** Document a blocking `leaf wait` flow
  for any host that can run a command, then use that experience to define a shared host
  adapter only if another integration needs it.

- **Wake a Claude Code session that holds no watcher.** A page whose watcher never came
  back is invisible from the browser, which is why the Stop hook in
  `hooks/scripts/loop-guard.py` polices the loop. Claude Code binds
  `/tmp/cc-socks/<pid>.sock` per session and publishes its path and a peer key under
  `~/.claude/sessions/`; a server the session spawned also inherits the address and a
  token of its own in `CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN`.
  An auth line followed by a `{"type":"user", ...}` line wakes an idle session, measured
  with the peer key on 2.1.272. Send a pointer to `leaf delivery read <id>` rather than
  the batch, and keep `leaf wait` as the one delivery path. Settle the recipient's terms
  before building: `crossSessionInbound` defaults to `hold`, so a session running bypass
  permissions holds a message from a sender it cannot identify behind an approval dialog,
  and the session's own child token does not exempt it. The text also arrives wrapped as
  a peer message rather than as an envelope Leaf controls. The protocol is internal —
  `peerProtocol: 1`, no CLI — and Codex keeps the existing route either way.

- **Measure a pending count in the favicon.** Prototype the count at 16px and keep it
  only if it remains legible beside the existing status treatment.

- **Give the touch grip room of its own, then fit more thread cards.** At a coarse
  pointer the panel's resize grip is a 44px square laid over the list, and nothing
  reserves that space: cards run under it at every scroll position, so whether its
  focus ring lands on a button is luck. Tightening the cards' spacing moved one Send
  button up onto it and
  `test_coarse_pointer_resize_reach_stays_reachable_without_trapping_scroll` said so,
  which is why e4cd887f was reverted.
  Reserving a full-height gutter would contradict the grip's own design — a local
  handle, not a scroll-blocking wall — so settle what the phone sheet owes it first.
  Spacing alone does not fit a third card either: the card's own content already
  exceeds a third of the list's height, which is the reply box and Send/Resolve row
  every card carries. Collapsing that to a single Reply affordance until the reader
  enters the card is the change that would.

- **Make the experimental direct MCP bundle fail loud on an evaluation-order fault.**
  `scripts/mcp-app/direct-build.mjs` bundles the full runtime for the direct-page
  experiment; it is not the shipped MCP App. Esbuild hoists cross-module `let`/`const`
  into `var`s, so a fault the ordinary page throws reads `undefined` in this experimental
  bundle. Give its direct probe a reading that sees the fault, or preserve the dead zone.
