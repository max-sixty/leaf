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

## Known gaps

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
