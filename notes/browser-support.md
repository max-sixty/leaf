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

Minor visual differences, including a small layout shift confined to one browser,
are acceptable when content remains readable and controls remain usable. Record
them as accepted visual differences; identical rendering is not a requirement.
Lost drafts, broken actions, inaccessible controls, and movement that disrupts a
gesture are functional failures and need a fix or an explicit support decision.
An unsupported API alone does not justify blocking the whole browser: record
what fails and what still works.

## Supported APIs checked

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
  selection. The browser tests in `test_render_navigation.py` check the
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

## Known gaps

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
  [Live samples](../skills/leaf/references/page-authoring.md#live-samples).

- **Observed, 2026-10-13:** Playwright Chromium 153.0.8010.12 rejects an
  opaque sample's pending icon, registry, and state fetches during a second native
  reload before `pagehide`. Its `pageswap` runs before those rejected promises;
  reporting them as startup faults retired the replacement frame. Holding the
  replacement document before commit keeps the old realm alive and its icon fetch
  pending; continuing the document triggers the swap and cancellation. The native
  loader/form/popup/nested-sample/reload journey and this held-destination control
  exercise the compiled kernel.
- **Disposition:** prepaint owns one document fault lifetime. `pageswap` or
  `pagehide` retires it, and `pageshow` restores it for a cached realm. Startup
  fault intake, the sample error port, and runtime error reporting consume that
  lifetime. A canceled `beforeunload` does not retire it. No error-text matching
  or delayed fault reporting participates.
- **Compatibility limit:** [MDN's compatibility data](https://raw.githubusercontent.com/mdn/browser-compat-data/main/api/Window.json)
  lists `pageswap` from Chrome 124, no Firefox support, and partial Safari 18.2
  support because cross-origin navigation omits it
  ([WebKit issue](https://webkit.org/b/306447)). Installed Playwright Chromium 153
  and WebKit 26.6 expose the event; Firefox 155 does not. The Firefox double-reload
  probe failed with native `NS_BINDING_ABORTED` and dynamic-module cancellation;
  it does not establish whether this differs from the source runtime. `pagehide`
  still retires departed documents there, but does not promise Chromium's earlier
  cancellation boundary. Safari's opaque-frame ordering has not been established.

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
- **Recheck:** the installed Chrome reading is available through:

  ```sh
  uv run leaf-dev probe developer/feature-gallery \
    --js '({browser:navigator.userAgent, marginTrim:CSS.supports("margin-trim", "block")})'
  ```

  The browser tests `test_frame_edges_pass_through_whatever_stands_at_them` and
  `test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it` hold the required
  wrapper and row behavior. Parser support alone does not establish it.

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
  The thread list retains the measured allocation of a passively withdrawn root
  while its removal would disturb the reader. It disconnects the former content
  and shows “Thread withdrawn” with Dismiss; counts and navigation reflect current
  threads. Selection stays with that allocation until dismissal, another choice,
  a view change, or safe departure. Complete-list rollback restores native content
  and editors from the same committed reading.
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
  `tests/*/test_render_threads.py`. Compare the rasterizer's same crop with a
  native screenshot in each installed engine when updating SnapDOM.
