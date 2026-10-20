# Browser support gaps

Track implemented behavior that differs or fails in current stable Chrome, Edge,
Firefox, or Safari, including their mobile versions and embedded browsers where
Leaf is used. This is a list of known gaps, not a claim that every other feature
has been tested across those browsers.

## Recording and assessing a gap

When adopting an API or discovering a browser difference, record the affected
feature and code owner, browser versions and check date, user-visible effect,
evidence or reproduction, and disposition. Distinguish an observed failure from
published compatibility data and an old test engine from a current browser gap.
Update or remove the entry when the implementation or browser support changes.
`uv run leaf-dev probe SOURCE --firefox` runs a probe or journey in Playwright's
Firefox, the one other engine installed beside the suite's Chromium.

Minor visual differences, including a small layout shift confined to one browser,
are acceptable when content remains readable and controls remain usable. Record
them as accepted visual differences; identical rendering is not a requirement.
Lost drafts, broken actions, inaccessible controls, and movement that disrupts a
gesture are functional failures and need a fix or an explicit support decision.
An unsupported API alone does not justify blocking the whole browser: record
what fails and what still works.

## Supported APIs checked

### Adaptive contents disclosure

- **Owners:** default package `lf-toc.js` and `styles/toc.css`. In-flow contents
  use native `details`/`summary`; margin and print expose the same links by
  opening the native disclosure, then restore the reader's in-flow choice.
- **Observed 2026-10-15:** installed Playwright Chromium 153.0.8010.12,
  Firefox 155 and WebKit 26.6 pass closed/open flow at 390px, Enter and touch
  activation, exposed links in the 1440px margin, focused-link preservation
  when moving into flow, and all links in print. Returning from margin or
  print restores the previous flow choice; a focused link remains exposed.
  The touch summary measures 44px (Firefox 44.03px).
- **Keyboard and evidence:** Chromium and Firefox traverse links with Tab.
  WebKit uses Alt+Tab; its ordinary Tab skips links in the baseline too.
  Rendered captures, DOM role queries and real keyboard routes are recorded in
  `.tmp/ux-research/experiments/68/`; this is an installed-engine check, not a
  current stable-browser survey or native accessibility-tree audit.
- **Disposition:** native open state governs exposed contents; no
  browser-specific fallback is needed for these checked routes.

### Help search result relationships

- **Owner:** `runtime/keyboard/command-reference.js`. The shared input keeps its
  native editor in a shadow tree; `ariaControlsElements` and
  `ariaActiveDescendantElement` connect that editor to Help's result grid and
  selected row in the enclosing document. String identifier references cannot
  cross this shadow boundary.
- **Compatibility checked 2026-10-09:** both properties support Chrome/Edge 135+,
  Firefox 136+, and Safari/iOS Safari 16.4+, according to
  [MDN's compatibility data](https://github.com/mdn/browser-compat-data/blob/main/api/Element.json).
  [WAI-ARIA defines element-reference reflection](https://w3c.github.io/aria/#idl-interface).
- **Observed:** Chrome 155's native accessibility tree exposes the named
  combobox, its controlled grid, and the selected row after filtering and Arrow
  navigation. Desktop and touch journeys retain native editor focus and caret
  selection. The browser tests in `navigation/test_command_reference.py` check the
  relationships through the native editor's element-reference properties.
- **Disposition:** adopted without a fallback; no current browser support gap
  was found in the compatibility data. Native accessibility behavior in Firefox
  and Safari has not been exercised here.

### Task group names

- **Owner:** `lf-task.js` in the Command Hub package. `ariaLabelledByElements`
  names each task group from its own visible title without adding identifiers or
  copying the title into a second label.
- **Compatibility checked 2026-10-08:** Chrome/Edge 135+, Firefox 136+, and
  Safari/iOS Safari 16.4+, according to
  [MDN's compatibility data](https://github.com/mdn/browser-compat-data/blob/main/api/Element.json).
  The property is defined by
  [WAI-ARIA's element-reference reflection](https://w3c.github.io/aria/#dom-ariamixin-arialabelledbyelements).
- **Observed:** Chrome 155's native accessibility tree exposes the task names
  and nested group ancestry, including after reports and title revisions.
  Playwright's DOM-based `aria_snapshot` omits names supplied by this property;
  `test_task_hierarchy_is_accessible_through_reports_and_revisions` therefore
  reads Chrome's native accessibility tree. This is a test-tool limitation,
  rather than an observed browser support gap.

### Contents spine lens

- **Owner:** `lf-toc.js` in the default package. The lens, the darker stretch of
  the contents spine marking the part of the document in view, runs its keyframes
  on a `ScrollTimeline` of the page's scroller.
- **Observed 2026-10-10:** installed Firefox 157.0.1 exposes neither
  `ScrollTimeline` nor `animation-timeline: scroll()`; Chrome 155 exposes both.
  The widget used to build no lens without the API, so a Firefox reader's spine
  showed only the current section's filled dot.
- **Disposition:** without the API the same keyframes run as a paused animation
  whose time the widget sets on each scroll's paint, a frame behind the scroll.
  On one page at three scroll positions, Firefox 157 drew the lens within 0.1px
  of Chrome's native timeline.
  `test_the_lens_follows_the_scroll_without_a_scroll_timeline` holds the fallback
  against the native timeline in Chromium with the API removed.

### Shadow-tree startup and draw-mode rules

- **Owner:** `runtime/shadow.js` (`SHADOW_LEADING_CSS`) and
  `styles/components/integration.css`. A declared shadow tree hides its generated
  interface until upgrade, holds transitions until presentation, and shows draw
  mode's crosshair under `main`. Its selectors cannot see the document's stamps, so
  the document states each condition as an inherited custom property
  (`--lf-before-upgrade`, `--lf-before-presentation`, `--lf-draw-mode`) and the
  tree's rules query it with `@container style()`. `:host-context()`, which these
  rules used before, has no Firefox or Safari support.
- **Compatibility checked 2026-10-13:** container style queries on custom
  properties support Chrome/Edge 111+, Firefox 151+, and Safari 18+, according to
  [web.dev's May 2026 platform notes](https://web.dev/blog/web-platform-05-2026).
- **Observed:** Playwright's Chromium 153, Firefox 155 and WebKit 26.6 each hide a
  shadow `.lf-ui` until the upgrade stamp, report `transition-duration: 0s` until
  the presentation stamp, and give a shadow tree under `main` the crosshair in draw
  mode while a tree outside `main` and `[data-lf-runtime]` apparatus keep their own
  cursors. WebKit's `getComputedStyle` keeps reporting the held `0s` for a
  `::before` until its element next restyles; that restyle reads the new duration
  and runs the pseudo-element's transition, so nothing visible differs.
- **Disposition:** adopted without a fallback.

### Folds, composed selections and anchor scopes without a feature check

- **Owners:** widgets that fold with `hidden="until-found"` (`lf-tabs`,
  `lf-options`, `lf-trace-compare`); `runtime/passages.js` (`pageRange`, through
  `Selection.getComposedRanges`); `runtime/css-anchors.js` (`anchor-scope`) and the
  Page Map toggle in `styles/chrome.css` (anchor positioning).
- **Compatibility checked 2026-10-14:** `hidden="until-found"` and `beforematch`
  support Chrome 102+, Firefox 139+ and Safari 26.2+; `getComposedRanges` Chrome
  137+, Firefox 142+ and Safari 17+; `anchor-name` Chrome 125+ and `anchor-scope`
  Chrome 131+, both Firefox 147+ and Safari 26+, according to
  [MDN's compatibility data](https://github.com/mdn/browser-compat-data) 8.1.5.
  It marks Safari's `until-found` partial: find-in-page reveals the match but
  [does not scroll to it correctly](https://webkit.org/b/304174).
- **Observed:** installed Playwright Chromium 153.0.8010.12, Firefox 155 and
  WebKit 26.6 each expose `onbeforematch`, `getComposedRanges`, `anchor-name` and
  `anchor-scope`.
- **Disposition:** adopted without a fallback. An engine without `until-found`
  reads the unknown value as plain `hidden`, which is what the removed check chose.

### The sheen over a line cut short

- **Owner:** `@keyframes lf-sheen` in `styles/components/surfaces.css`, run by the
  floating panel's field (`floating-panel.css`), the thread card's working words
  (`surfaces.css`) and a pending thread title (`chrome.css`). It paints the words in
  ink and dims them with a moving `mask-image` to each box's rest face.
- **Observed 2026-10-15:** the sheen it replaced, a background clipped to the glyphs
  under a transparent fill, hid a cut line's ellipsis in Playwright Firefox 155, and
  the user saw it in Firefox 157: Firefox draws the ellipsis outside the clipped
  background. With the mask, Firefox 155 and Chromium 153 both draw the ellipsis in
  every frame of the pass.
- **Disposition:** adopted without a fallback.

## Known gaps

### Intrinsic block retirement motion

- **Owner:** `runtime/motion.js` (`foldBlock`), used by resolved thread cards and
  block suggestion slots. The browser interpolates the ordinary intrinsic block
  size to zero with `calc-size(auto, size)`; the other block metrics start at their
  underlying CSS values. Neither caller measures or reconstructs the starting box.
- **Checked 2026-10-14:** installed Playwright Chromium 153.0.8010.12 supports
  `calc-size()` and `interpolate-size`; Firefox 155 and WebKit 26.6 expose neither.
  These are installed test engines, not a current stable Firefox/Safari survey.
  [Chrome's documentation](https://developer.chrome.com/docs/css-ui/animate-to-height-auto)
  describes native intrinsic interpolation and its progressive enhancement model.
- **Observed:** card, native details and block-slot probes preserve their exact
  first size, shrink to zero, and restore their ordinary size when canceled in
  Chromium. Retired-slot styling applies padding changes only to the survivor, so
  the outgoing slot starts at its actual pre-decision shape. Inline suggestions
  do not animate. Reduced motion skips the effect, and the shared motion owner
  finishes a running fold when that preference changes.
- **Disposition:** accepted visual difference. Without `calc-size()` the same
  semantic retirement completes immediately, as it does under reduced motion.
  The runtime explicitly declines the animation rather than letting unsupported
  intrinsic-size interpolation jump halfway through a fade. Content, Undo and
  Reopen remain available through their ordinary paths.

### Browser dictation in comment boxes

- **Owner:** `runtime/composing/input.js` and `runtime/composing/dictation.js`.
  Empty comment and reply boxes offer dictation only when the browser exposes
  `SpeechRecognition` or `webkitSpeechRecognition`.
- **Compatibility checked 2026-10-11:** [MDN marks speech recognition as limited
  availability](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition).
  Availability of the interface does not establish microphone permission or
  access to the browser's recognition service.
- **Observed:** installed Chrome 155.0.8059.39 exposes the interface and begins
  listening. A standalone test with synthetic microphone audio ended with
  `no-speech`; successful real transcription remains unverified. The Codex
  embedded browser reported `network` in the user's trial. Deterministic native
  event tests separately cover transcripts, failure recovery and cancellation.
- **Disposition:** progressive enhancement. Browsers without the interface keep
  ordinary typing and Send. A failed attempt stays inside the empty field; words
  already heard remain editable and sendable.

### Native focus and scrolling inside samples

- **Impact: functional; Leaf-owned navigation is contained.** An opaque
  sandboxed frame with an opaque origin denies parent DOM, storage, and cookie access,
  but does not confine native focus and reveal operations. Leaf’s own code observes
  input ownership and uses document-local reveals. Authored scripts retain native
  browser APIs; no page-content restriction is required for that runtime contract.
- **Owners:** focus admission and layer returns in `runtime/focus.js`, native
  openings and the canonical modal reading in `runtime/keyboard/layer-stack.js`,
  document-local reveal in `runtime/landing-scroll.js`, and the editor adapter in
  `runtime/editor-view.js`.
- **Observed, 2026-10-09:** installed Chrome 155 and Playwright Chromium
  153.0.8010.12 allow autonomous SVG focus, `window.focus`, `dialog.showModal`,
  `showPopover`, and nested-frame native focus to take focus from the containing
  page. `scrollIntoViewIfNeeded` can scroll that page without changing focus.
  The Chrome 155 calls ran from message handlers with both user-activation
  readings false. An inert containing iframe did not supply the missing boundary.
- **Observed, 2026-10-10:** a native dialog opening can reveal its containing frame
  even while the child already owns focus. Native dialog close can return focus
  after the parent has reclaimed input, including into another modal that escapes
  ancestor inertness. Temporarily making the opening layer, or the document and
  open modal roots during close, inert prevents these transfers before they
  occur. Leaf then places its own intended arrival without native scrolling.
- **Reproduction:** serve a window sample with a tall body, a focusable SVG
  link, a dialog containing an autofocus input, and a popover containing an
  autofocus input. Focus a button on the containing page, then run each native
  operation from an autonomous child message handler. Read the containing
  page’s active element and scroll position and capture focus events throughout
  the operation. Repeat after child entry, with nested modal dialogs, and with
  the containing page scrolled away while the child retains focus.
- **Platform status:** Chrome described `focus-without-user-activation` as an
  [origin trial in Chrome 149](https://developer.chrome.com/release-notes/149).
  Neither checked engine exposes it in its permissions-policy feature list;
  setting an unsupported policy does not establish a guarantee.
- **Disposition:** Leaf contains its own navigation through its canonical owners.
  This is a cooperative runtime contract, not a security claim that arbitrary
  authored JavaScript cannot call native APIs outside it. No parent focus or
  scroll restoration establishes the guarantee.
- **Editing and engine limits, checked 2026-10-10:** typing into an offscreen
  focused editor reveals its frame in Chrome, including a plain native textarea,
  without any JavaScript focus or reveal call. Leaf's autonomous value and selection
  updates leave parent focus and scroll unchanged. WebKit 26.6 also revealed an
  offscreen editor on focus: CodeMirror disables `preventScroll` on Safari 26+,
  and native contenteditable focus can reveal an inactive retained selection.
  Leaf's editor adapter detaches only its own inactive DOM selection, focuses
  without scrolling, and places the retained selection from editor state. The
  regression passes repeated entry and real editing in Chromium and WebKit 26.6;
  WebKit dialog and popover phase checks also preserve containing-page focus and
  scroll. Playwright Chromium 153.0.8010.12 also invoked CodeMirror's native mobile
  reveal fallback on desktop when a classic horizontal scrollbar reduced
  `visualViewport.height` below `innerHeight`. A focused read-only file editor's
  deferred resize then moved the containing page as its sample became visible.
  The shared editor adapter consumes reveal requests through Leaf's document-local
  scroll owner; the classic-scrollbar regression now keeps the containing page
  still. These are engine checks, not installed Safari or mobile-browser checks.

### Sample document admission and native navigation

- **Owners:** initial admission and private-port lifetime in `runtime/sample.js`,
  the child departure notice in `runtime/bootstrap.js`, and the `Leaf-Document`
  response header in `leaf/http.py`.
- **Observed, 2026-10-10:** Chromium can deliver a parent's self-posted completion
  check before a child window's earlier load announcement. A shared message task
  source does not establish delivery order across these browsing contexts. In
  Chromium, parent resource timing exposes the initial iframe response's
  `Server-Timing` header, but child-initiated reload adds no parent resource entry.
  WebKit's initial iframe entry omits that header even with `Timing-Allow-Origin: *`.
  Chromium's Navigation API exposes no current entry or navigation events inside
  an opaque sample.
- **Disposition:** allocation and Reset admit the child URL with a credentialless
  HEAD and require its server-owned `Leaf-Document` header before ordinary native
  iframe navigation. This checks the document the server offers at admission;
  it cannot prove the later navigation receives the same response. A child's
  `pagehide` cancels private presentation and pending commands while retaining its
  native destination and Reset. A valid Leaf reload reconnects; a non-Leaf document
  stays visible without a private port. The opaque parent cannot classify a later
  failed reload separately from authored departure. The author-facing contract is
  [Live samples](../skills/leaf/references/live-samples.md).

- **Observed, 2026-10-13:** Playwright Chromium 153.0.8010.12 rejects an
  opaque sample's pending icon, registry, and state fetches during a second native
  reload before `pagehide`. Its `pageswap` runs before those rejected promises;
  reporting them as startup faults retired the replacement frame. Holding the
  replacement document before commit keeps the old realm alive and its icon fetch
  pending; continuing the document triggers the swap and cancellation. The native
  loader/form/popup/nested-sample/reload journey and this held-destination control
  exercise the compiled kernel.
- **Observed, 2026-10-19:** stock Firefox 158, driven over WebDriver BiDi, and
  Playwright's Firefox abort a document's in-flight loads as soon as an uncanceled
  `beforeunload` lets a navigation start, and keep the document running until the
  destination answers. A registry, widget module or state body cut off that way
  failed startup or a state read, and the page posted a state body's and a widget
  module's failure to its log as `error` events. Chrome 155 keeps the old
  document's loads until it commits. Removing a loading sample fires the child's
  `pagehide` before its aborted fetches reject, in both engines.
- **Disposition:** prepaint owns one document fault lifetime. An uncanceled
  `beforeunload`, `pageswap` or `pagehide` retires it. The user's next input
  reopens it after a `beforeunload` that left the document in place, as a link
  answered with a download does, and `pageshow` reopens it for a cached realm. A
  canceled `beforeunload` never retires it. Startup fault intake, the sample error
  port, and runtime error reporting consume that lifetime. No error-text matching
  or delayed fault reporting participates.
- **Compatibility limit:** [MDN's compatibility data](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Window.json)
  lists `pageswap` from Chrome 124, no Firefox support, and partial Safari 18.2
  support because cross-origin navigation omits it
  ([WebKit issue](https://webkit.org/b/306447)). Safari's ordering of departure
  and cancellation has not been established.
- **Page cache, 2026-10-19:** neither Chrome 155 nor Firefox 158 keeps a served
  Leaf page in its back/forward cache. The document and the API answers carry
  `Cache-Control: no-store` (Chrome names `MainResourceHasCacheControlNoStore` and
  `JsNetworkRequestReceivedCacheControlNoStoreResource`), and Firefox also refuses
  a page holding a sample. With `no-store` removed by a proxy, Chrome restored a
  page and its sample; the page caught up with the log and recorded gestures, but
  the child had treated its persisted `pagehide` as a departure, leaving the host
  waiting for a next document. The child now ignores a persisted `pagehide`, as
  the host does. Playwright disables both page caches
  (`--disable-back-forward-cache`, `fission.bfcacheInParent`), so the suite hands
  the child a cached round trip's events instead. Safari has not been exercised.

### Back during smooth arrival

- **Owner:** `runtime/history.js`. A working-place checkpoint contains the viewport
  offset alongside focus and selection. Traversal cancels outgoing viewport and
  nested reading-region motion before restoring that checkpoint; nested regions
  retain their current offsets.
- **Observed, 2026-10-10:** Playwright's Chrome for Testing 153.0.8010.12 can lose
  native scroll restoration when Back interrupts a smooth arrival. A primary
  reader departure at 200px returned to 0px on early Back, while Back after the
  same arrival settled returned to 200px. A sibling reader departure at 4013px
  showed the same distinction. An immediate explicit restoration could also be
  overwritten by the outgoing scroll's next compositor update.
- **Disposition:** captured checkpoints restore their own offset after a complete
  rendering update carries cancellation to the browser. Entries without a captured
  checkpoint retain native restoration. The immediate Back regression in
  `test_render_application_boundary.py` exercises a nonzero departure. Current
  stable Chrome, Firefox and Safari have not been exercised for this gap.

### Frame margin trimming

- **Disposition: shared CSS retained.** Leaf trims a frame's content edges through
  bare wrappers, skips generated apparatus, and stops at a declared row boundary.
  Native `margin-trim` cannot replace that mechanism across the checked engines.
- **Owner:** frame-edge rules in
  [`theme.css`](../skills/leaf/assets/theme.css), with readings in
  [`framing.js`](../skills/leaf/scripts/leaf/render-checks/framing.js).
- **Observed, 2026-10-08:** installed Chrome 155 and Playwright WebKit 26.6 accept
  `margin-trim: block`; Playwright Chromium 153.0.8010.12 and Firefox 155 do not.
  Chrome 155 trims block-flow margins but leaves flex and grid item margins intact.
  A zero-height generated child in flow can also prevent it from trimming the
  authored paragraph at the frame's edge. Leaf's shared rules keep the same edge
  policy in those cases. The [CSS Box draft](https://drafts.csswg.org/css-box-4/#margin-trim)
  defines native trimming for block containers.
- **Recheck:** `leaf-dev probe` reads the pinned headless shell; installed Chrome's
  reading is:

  ```sh
  uv run python -c 'from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
      b = p.chromium.launch(channel="chrome")
      print(b.version, b.new_page().evaluate("CSS.supports(\"margin-trim\", \"block\")"))
      b.close()'
  ```

  The browser tests `test_frame_edges_pass_through_whatever_stands_at_them` and
  `test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it` hold the required
  wrapper and row behavior. Parser support alone does not establish it.

### Scroll-state containers

- **Disposition: scroll-state is progressive.** A `container-type` naming
  `scroll-state` is written after the same declaration without it, so an engine
  without scroll-state keeps the size container.
- **Owner:** the table rules in
  [`reading.css`](../skills/leaf/assets/styles/components/reading.css) and the
  granted-room table in [`layouts.css`](../skills/leaf/assets/layouts.css).
- **Observed, 2026-10-14:** Firefox 157 (a user's page) and Playwright's Firefox and
  WebKit 26.6 drop `container-type: inline-size scroll-state` whole, so the table was
  no size container and the 100cqi a caption read measured the window: an `lf-ask`'s
  two-column table laid its rows out 1728px wide in a 720px column and cut off its
  second column. Chrome 155 keeps it. Firefox also never widens a table grid to a
  caption wider than its columns' natural width, so Leaf no longer widens a table's
  columns to its frame in any engine.
- **Recheck:** `test_a_table_of_prose_wraps_inside_its_box_in_every_engine` holds
  the size container in all three engines.

### State-preserving content reordering (review #22)

- **Impact: state preservation; functional fallback implemented.** Retained-node
  reordering uses [`move` in `dom-move.js`](../skills/leaf/assets/runtime/dom-move.js).
  Within one composed root it uses `moveBefore` when available; new nodes,
  cross-root transfers, and engines without the API use `insertBefore` and restore
  the user's focus and caret in the moved node.
- **Consumers:** authored revisions and renderer child reconciliation, board
  placement, the response bar's seats, the vendored Sortable move sites, and
  lit-html’s keyed and child-part insertions. Both vendor adaptations fail if their pinned upstream seams change.
- **Browser support, checked 2026-10-10:** Chrome/Edge 133+ and Firefox 144+
  support the API. Safari, including iOS Safari, is listed as unsupported in
  [MDN's compatibility data](https://developer.mozilla.org/en-US/docs/Web/API/Element/moveBefore#browser_compatibility).
  The [WebKit implementation tracker](https://bugs.webkit.org/show_bug.cgi?id=281223)
  tracks the missing native capability.
- **Observed:** the focused browser test
  `test_retained_moves_keep_native_editor_and_frame_state` exercises retained-node
  ordering and direct placement in Chrome with no focus hold of the caller's. Native
  moves retain focus, caret, typed text, and the embedded iframe document without a
  blur. Disabling the capability exercises ordinary insertion, after which `move`
  puts focus and caret back. Playwright's WebKit 26.6 has no `moveBefore`; a direct
  probe confirms retained nodes reorder and a new fragment arrives through the
  shared primitive.
- **Lit adoption:** `build/browser/build.mjs` routes keyed and child-part moves
  through the shared primitive. The Chrome test above exercises both
  child reconciliation and Lit rendering, with native moves and forced fallback.
- **Stale native `:focus-within`, observed 2026-10-12 in Playwright's Chromium
  153.0.8010.12:** a focused element that `moveBefore` carries into a hidden
  (`display: none`) parent and out again still matches `:focus`, and its new
  ancestors match `:focus-within`, but the element itself no longer matches
  `:focus-within`. A reply editor waiting in `thread/replies.js`'s park between a
  seat and the margin card takes that route. No Leaf style reads it: focus paints
  through `data-lf-focus-within`, which `focus.js` derives from the rendered
  ancestry. A selector for the focused editor uses `:focus`. Reproduce with a
  focused `<input>`, a hidden `<div>` and a visible one, two `moveBefore` calls, and
  `input.matches(":focus-within")`.
- **Fallback limit:** insertion blurs a focused descendant and reloads an iframe.
  `move` restores the focus and caret, but cannot preserve iframe documents. The
  native guarantee for Leaf's retained moves is described in the
  [API's state-preservation contract](https://developer.mozilla.org/en-US/docs/Web/API/Element/moveBefore#description).

To check the installed test engine without downloading a browser:

```sh
uv run python - <<'PY'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.webkit.launch(headless=True)
    page = browser.new_page()
    print(browser.version, page.evaluate('typeof Element.prototype.moveBefore'))
    browser.close()
PY
```

This checks API availability, not preservation behavior or the installed Safari
application. Recheck the affected Leaf journey when resolving this entry.

### Live sample host controls

- **Owner:** `lf-sample.js` and the default theme's sample rules.
- **Observed, 2026-10-10:** Firefox 157 and Playwright's Firefox lay out only a
  table's first caption. The sample's label was the first and its Reset and Full
  view controls a second, so Firefox drew the controls at zero size. A minimal
  table with two captions reproduces it.
- **Disposition:** fixed. A live sample keeps the label as its only caption; the
  controls stand in the cell and the gutter is drawn on the exhibit around the
  frame. Firefox, Chrome and WebKit show the controls above the gutter.

### Area capture rendering

- **Disposition: DOM reconstruction with accepted visual differences.** Capture
  area uses SnapDOM 3.3.0 to render the current DOM into an image. Text and native
  form controls can differ slightly from the screen. Leaf attaches a capture with
  the library's reported missing-image fallback and a notice that an image near the
  area may be missing, since SnapDOM reads resources a margin beyond the crop and does
  not say where the image was; it cannot detect every omitted resource.
- **Owner:** [`region-selector.js`](../skills/leaf/assets/runtime/composing/region-selector.js)
  selects and anchors the crop; [`page-image.js`](../skills/leaf/assets/runtime/composing/page-image.js)
  draws it, and the vendored SnapDOM module owns rendering.
- **Observed, 2026-10-09:** Chrome 155.0.8059.39, Playwright 1.63.0's Firefox
  155.0, and its WebKit 26.6 produced the same 600 × 300 crop dimensions and
  preserved open-shadow styles, inline SVG, a changed input value, page and
  internal scrolling, and a fixed overlay in one synthetic fixture. Each capture
  differed from that engine's screen capture at fewer than 1% of pixels, with
  small text and form-control differences. No capture warnings occurred. These
  isolated renderer checks do not establish complete Leaf support or test the
  installed Safari application. Chrome 155 also captured a live Leaf Mermaid
  diagram; Chromium 153.0.8010.12 passed the anchored upload/send/reload and
  keyboard/touch journeys.
- **Observed touch-input gap, 2026-10-10:** Chromium 153.0.8010.12 can generate
  a fling after a fast selection drag despite `touch-action: none` and prevented
  pointer defaults. Linux then consumes the first confirmation tap to stop it.
  Native input traces reproduce the fling with both dispatched touch events and
  the browser's synthetic gesture controller; consuming the selection's native
  `touchstart` prevents it. The capture controller owns that claim only while
  selection is active and leaves Leaf controls to native activation. The touch
  journey below checks this boundary and immediate first-tap confirmation.
- **Observed resource gap:** an image loaded from another HTTP origin without
  CORS permission remained visible on the page but produced `image-fallback`
  during capture. Leaf attaches it with a notice. A CSS background from the same
  external origin was omitted without a capture warning.
- **Live samples, 2026-10-10:** SnapDOM cannot read a sample's opaque-origin frame
  and drew each one as a placeholder box. Each sample SnapDOM reaches now draws the
  part of its viewport inside the crop, and the parent places that image in the
  frame's box. Chrome 155,
  Playwright's Firefox and WebKit 26.6 all capture two live samples, their host
  controls and the child chrome; WebKit drew a large child image blank until the
  placeholder `<img>` carried `decoding="sync"` into SnapDOM's markup. The reply
  editor's placeholder text is missing from the child image in all three, an
  accepted visual difference. `test_a_region_capture_draws_live_samples_and_survives_removed_links`
  holds the Chrome journey.
- **Upstream observer defect, 2026-10-10:** after a capture, SnapDOM 3.3.0–3.3.3
  counts later mutations up the target's ancestors through `getRootNode().host`. A
  removed `<a>` subtree answers with the link's host string, which SnapDOM uses as a
  WeakMap key, throwing an uncaught page error (Firefox 157 and Chrome 155).
  `build/vendor.mjs` patches that climb to follow only a shadow root's host; drop
  the patch once upstream fixes it.
- **Upstream credentials defect, 2026-10-17:** SnapDOM 3.3.4 sends cookies to a
  resource whose origin equals `location.origin`, the URL's, so a sandboxed sample
  child, whose document origin is opaque, sent them cross-origin and Leaf's
  `Access-Control-Allow-Origin: *` answer refused the child's icon.svg mask in Chrome.
  `build/vendor.mjs` compares with `self.origin`; drop the patch once upstream does.
- **Published limitations:** the upstream
  [3.3.0 limitations](https://github.com/zumerlab/snapdom/blob/b27b35adfae9d9a8993c56b067837014bcef4750/README.md#limitations)
  require readable images, fonts, and stylesheets; cross-origin iframe contents
  become placeholders. Font omission and cross-origin iframe placeholders were
  not exercised in the checks above. Source review found font-fetch failures
  report through the console without a capture warning. The
  [rendering contract](https://github.com/zumerlab/snapdom/blob/b27b35adfae9d9a8993c56b067837014bcef4750/FEATURES.md)
  describes the SVG/`foreignObject` path used here; the experimental native
  canvas engine is not enabled.
- **Recheck:** run
  `test_a_region_capture_keeps_scrolled_shadow_pixels_and_its_comment_anchor`
  and `test_touch_capture_can_cancel_and_reopen_before_attaching` in
  `tests/browser/threads/test_media.py` and `tests/journeys/test_render_threads.py`. Compare the rasterizer's same crop with a
  native screenshot in each installed engine when updating SnapDOM.

### Anchoring from a shadow root to the outer document

- **Disposition: blocks moving the chrome into a shadow root.** Leaf's chrome is a
  light-DOM `div` (`runtime/chrome.js`), and its anchored surfaces (the floating
  card, passage outlines, page-search paint, design hints, margin carriers) name
  anchors on page elements. A spike that moved the chrome into a shadow root left
  each of them at its fallback position.
- **Spec:** the [anchor positioning draft](https://drafts.csswg.org/css-anchor-1/)
  makes anchor names loosely matched tree-scoped names, so an element in a shadow
  tree may anchor to a name declared in an outer tree.
- **Observed, 2026-10-13:** a `position: fixed` element in an open shadow root with
  `position-anchor` naming an `anchor-name` declared in the document stays at its
  static position in Playwright Chromium 153.0.8010.12, installed Chrome
  155.0.8059.40, Firefox 155 and WebKit 26.6, whether the rule is inline or in the
  root's sheet. The same element anchors to a name declared inside its own root,
  and a light-DOM element anchors to the document's name. In Chromium 153, a
  document-level rule that positions the host's `::part()` does anchor, which is
  the only bridge found.
- **Recheck:** set `anchor-name` on a document element, attach a shadow root after
  it, and compare a fixed child's `getBoundingClientRect()` against the anchor in
  each engine.

The reverse direction works: a box in a widget's shadow tree can be named from the
document, and the runtime relies on it (next entry).

### Naming a shadow-tree box from the document

- **Disposition: supported one tree deep; deeper boxes anchor through their host.**
  `runtime/css-anchors.js` (`anchorReading`, `anchorElement`) adds a part spelled as
  the anchor's name, `lf-a7` for `--lf-a7`, to a box inside a widget's shadow tree,
  and a document sheet it owns declares `::part(lf-a7) { anchor-name: --lf-a7 }`, so
  margin rows, target paint and the floating card follow a scroller inside the tree.
  A name the tree itself declares reaches no box outside it.
- **Observed, 2026-10-14:** a fixed chrome box anchored to such a part follows the
  part through the shadow scroller's scroll, and a frame anchored to that scroller
  and cut with `clip-path: inset(0)` cuts it at the scroller's edge, in Playwright
  Chromium 153.0.8010.12, installed Chrome 155, Firefox 155 and WebKit 26.6. A part
  re-exported through a nested host's `exportparts` anchors in Chromium and WebKit
  and stays at its fallback in Firefox 155, so the runtime names no box deeper than
  the first shadow tree; no shipped widget nests one. One `::part(lf-anchor)` rule
  reading every name from `attr(data-lf-anchor type(<custom-ident>))` anchors in
  Chromium 153 and Firefox 155 and leaves the box at its fallback in WebKit 26.6,
  which resolves the same `attr()` outside a `::part()` rule, so the runtime writes
  one rule per name. Words alone in a shadow scroller anchor to the start of what it
  holds the same way, through `::part(lf-a7)::before { content: ""; anchor-name:
--lf-a7 }`, which anchors and follows the scroller's scroll in all three engines.
- **Recheck:** attach a shadow root holding a scroller with a `part`-named child,
  declare `#host::part(name) { anchor-name: --x }` in the document, and compare a
  fixed `position-anchor: --x` box's rectangle with the child's after scrolling the
  inner scroller, in each engine; repeat with the child one host deeper behind
  `exportparts`.

### A stuck sticky anchor in Firefox

- **Disposition: accepted.** Every box that follows scrolled content is anchored
  (`runtime/css-anchors.js`); a script that placed boxes after each scroll and
  scroll-driven layers were removed rather than kept for this case. Revisit if
  readers report marks missing from stuck headers in Firefox.
- **Affected:** a margin row, highlight, aim or floating card whose target stands in
  a sticky box while it is stuck, such as an `lf-diff` file header, a table's
  sticky caption or a sticky `lf-tabs` strip.
- **Observed, 2026-10-14, Firefox 155:** a box anchored to a sticky element, or to
  an element inside one, is placed where the anchor would stand without sticking:
  with its scroller scrolled 300 px, the stuck anchor reads 300 px from the window's
  top and the anchored box 20 px, outside the frame that cuts it, so the mark
  disappears until the header unsticks. A header stuck to the document's top reads
  10 px with its box at -200 px. Chromium 153, Chrome 155 and WebKit
  26.6 place it on the stuck anchor. Writing the stuck position into the inset with
  `max(anchor(--t top), calc(anchor(--scroller top) + inset))` does not help:
  Firefox resolves anchors before applying scroll compensation.
- **Effect:** the mark, pin or card for a stuck target is not drawn, or is drawn
  where the target stood before it stuck; controls stay reachable through Threads
  and the Page Map.
- **Recheck:** in a scroller 220 px tall, a `position: sticky; top: 0` header holding
  an element named `--t`, and a `position: fixed` box with
  `position-anchor: --t; top: anchor(top)` after the scroller; scroll the scroller
  past the header's start and compare the two rectangles' tops.

### An anchor under a fixed box in WebKit

- **Disposition: accepted.** As above, no script or scroll-driven layer answers it.
  Revisit if a page puts marks inside fixed panels for Safari readers, such as a
  contents list or side panel that is `position: fixed` and holds commented or
  highlighted targets.
- **Affected:** a margin row, highlight or floating card whose target stands in a
  `position: fixed` box, while the document is scrolled.
- **Observed, 2026-10-14, WebKit 26.6:** a box anchored to an element inside a
  fixed panel moves with the root scroll as well: with the page scrolled 120 px and
  the panel 40 px, the anchor reads 160 px from the window's top and the anchored
  box 40 px, the root's scroll applied a second time. Chromium 153, Chrome 155 and
  Firefox 155 place it on the anchor. Standing the box in a fixed frame anchored to
  the panel and cut with `clip-path` does not change WebKit's answer.
- **Effect:** in Safari, the mark or row for a target in a fixed panel drifts from
  its target as the page scrolls, and comes back at the top of the page. Leaf's own
  fixed chrome holds no page targets.
- **Recheck:** a `position: fixed; overflow: auto` panel holding an element named
  `--t`, a `position: fixed` box with `position-anchor: --t; top: anchor(top)`
  after it, and a document tall enough to scroll; scroll the document and the panel
  and compare the two rectangles' tops.

### An anchor's transforms in Firefox

- **Disposition: answered for translations.** `anchorBox` (`runtime/css-anchors.js`)
  is where every inset Leaf writes against an anchor is measured from. In an engine
  that leaves transforms out, read once, it takes off how far each translation on
  the anchor or an ancestor moves its box, read from offsets, which leave
  transforms out too. A scale, rotation or CSS zoom moves each point differently and
  stays unanswered. Remove it when Firefox counts transforms. A probe anchored to
  the same name was rejected: read straight after a scroll between it and the
  anchor, it returns where the anchor stood before.
- **Affected:** every box anchored in a table granted room, which `layouts.css`
  translates into place, and in any box a page transforms: margin rows and pins,
  the Alt outline, key chips, the comment box, the thread card, and a code block's
  Copy, whose CSS-only anchor takes the shift on each reveal (`code-copy.js`).
- **Observed, 2026-10-16, Firefox 155:** `anchor()` resolves to the anchor's box
  as laid out, before the `transform`, `translate`, `rotate`, `scale` or
  `offset-path` on it or an ancestor; relative positioning is counted. The spec counts transforms, as
  Chromium 153 and WebKit 26.6 do. At 1728 px a `data-width="wide"` table stood
  translated 300 px from its layout box, so the comment box for its header opened
  over the row headers and the Alt outline stood 300 px left of the table.
- **Recheck:** a box with `translate: 50px 0` named `--t`, and a `position: fixed`
  box with `position-anchor: --t; left: anchor(left)` after it; compare the two
  rectangles' lefts.

### Native reveal bounded to its scroller

- **Disposition: worked around in Leaf.** Leaf reveals an item inside one box
  through `scrollIntoView(node, {within})` in `runtime/landing-scroll.js`, which
  moves only that box and the boxes inside it, in all three engines (Chromium 153,
  Firefox 155, WebKit 26.6, checked 2026-10-14 on a stuck tab strip and a contents
  outline). Revisit if every engine honours `container` and Leaf's walk could
  hand the bounded case to it.
- **Affected:** a tab strip, contents outline or page map list bringing its item
  into view while the page stays where the user reads.
- **Observed, 2026-10-14:** `scrollIntoView({block: "nearest", inline: "nearest",
container: "nearest"})` on a button in a sideways strip whose foot stands 1 px
  below its scroller's band scrolls the strip alone in Chromium 153 and WebKit 26.6,
  and the outer scroller by 2 px as well in Firefox 155, whether the outer scroller
  is the root or a nested box. An earlier check on another page also saw WebKit
  scroll the outer box.
- **Recheck:** a 600 px scroller holding a 300 px `overflow-x: auto` strip of
  twenty 120 px buttons; scroll so the strip's foot is just past the band, call
  the native reveal on the sixteenth button, and read both scroll offsets.

### Reveal of a Tab's arrival

- **Disposition: worked around in Leaf.** Once the browser's own reveal has run,
  `runtime/landing-scroll.js` lands a Tab's arrival the browser left not already
  shown, nearest, reading the same scroll margins and padding. Revisit if both
  engines reveal a partly hidden arrival on both axes.
- **Affected:** Tab onto a control partly past a scroller's edge: a playground's
  radio at its controls pane's foot in Firefox, a link at a wide table's end in
  both engines.
- **Observed, 2026-10-19 (Chromium 153, Firefox 155):** Firefox scrolls a
  sequentially focused element only once less than about a line of its
  margin-inflated box shows in its scroller, on either axis: a 13 px radio 2 to
  6 px past a bounded block's foot or top stayed cut, and one 10 px past was
  centred. Chromium reveals a partly hidden arrival nearest on the block axis, but
  across only once none of it shows: a 69 px link 6 to 62 px past a table's end
  stayed cut, and one wholly past it was centred. Firefox left the same link cut
  at 50 px past and centred it at 56.
- **Recheck:** a 100 px `overflow: auto` box holding a 13 px radio whose foot
  stands 6 px past the box's foot, and a sideways box holding a 69 px link 6 px
  past its end; Tab onto each from the control before it and read the scroll
  offset. `test_tab_onto_a_control_partly_past_a_scrollers_edge_brings_it_in`
  reads Leaf's correction, so it passes whatever the engines do.
