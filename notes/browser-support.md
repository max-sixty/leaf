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

## Known gaps

### Native focus and scrolling inside samples

- **Impact: functional; Leaf-owned navigation is contained.** An opaque
  sandboxed frame with an opaque origin denies parent DOM, storage, and cookie access,
  but does not confine native focus and reveal operations. Leaf’s own code observes
  input ownership and uses document-local reveals. Authored scripts retain native
  browser APIs; no page-content restriction is required for that runtime contract.
- **Owners:** focus admission and layer returns in `runtime/focus.js`, native
  openings and the canonical modal reading in `runtime/keyboard/layer-stack.js`,
  document-local reveal in `runtime/landing-scroll.js`, and the editor adapter in
  `runtime/composing/text-field.js`.
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
  standing modal roots during close, inert prevents these transfers before they
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
  scroll. These are engine checks, not installed Safari or mobile-browser checks.

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

- **Impact: functional; support decision open.** Reordering retained content
  calls `moveBefore` without a capability check. On an engine without that API,
  the reorder throws `TypeError: parent.moveBefore is not a function`. This is
  more than a layout difference. A page that has not reached that operation may
  still render; Leaf currently has no explanatory startup refusal.
- **Owner:** [`order` in `dom-children.js`](../skills/leaf/assets/runtime/dom-children.js),
  shared by authored revisions and renderer child reconciliation.
- **Browser support, checked 2026-10-08:** Chrome/Edge 133+ and Firefox 144+
  support the API. Safari, including iOS Safari, is listed as unsupported in
  [MDN's compatibility data](https://developer.mozilla.org/en-US/docs/Web/API/Element/moveBefore#browser_compatibility).
  The [WebKit implementation tracker](https://bugs.webkit.org/show_bug.cgi?id=281223)
  remains open.
- **Observed:** Playwright 1.63.0's WebKit 26.6 lacks the API, and a connected
  reorder through Leaf's `setChildren` throws and fails to reorder. The Codex
  browser pane tested on the same date reports Chrome 155 and exposes the API;
  it is distinct from the WebKit test browser.
- **Reason for the dependency:** native moves preserve embedded iframe documents
  and focus. Removing and reinserting the same node can reset that browser state,
  so an `insertBefore` fallback cannot provide the same guarantee. See the
  [API's state-preservation contract](https://developer.mozilla.org/en-US/docs/Web/API/Element/moveBefore#description).
- **Next decision:** retain the native capability requirement with a clear
  explanation in unsupported browsers, or redesign content placement to preserve
  state without it. Requiring the capability is the current recommendation;
  a blanket Safari exclusion has not been approved or implemented.

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
