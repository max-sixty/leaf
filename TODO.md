# TODO

- **Widget-part keyboard addresses.** The `g` chord currently names only core lists.
  If it grows addresses for widget parts such as board grips or draft editors, the
  registry should declare them with an `x-` key. Existing groups already expose their
  options through focused digit bindings, so no change is needed yet.

- **Favicon pending count.** Whether a 16px tab icon can carry a readable pending count
  remains unmeasured.

- **Escape in a reply box.** A report said Escape left the reply box and closed the
  comments panel in one press. The behavior did not reproduce in either palette: the
  key line said "back to thread," the panel stayed open, the draft survived, and focus
  returned to the thread. Revisit only with the exact page and text box where it occurs.

- **Handing design comments to a leaf checkout.** A session outside a leaf checkout
  uses the installed plugin layer, so a fix on `main` reaches its page only in a later
  session after re-vendoring. Today the comment is dispatched to a leaf session by
  hand. If this recurs, evaluate carrying the comment anchor and page URL in the
  dispatch and allowing that page to re-vendor from a named checkout.

- **Deferred design-mode additions.** Each needs evidence before implementation:

  - Generate a crop from the replayed page if a design comment is misread without a
    screenshot.
  - Stamp widget tags on comment events only if a consumer must read the log without a
    page; the tag is otherwise one join from the version file.
  - Add a panel inventory only when a page becomes long enough that its items are hard
    to find by scrolling.
