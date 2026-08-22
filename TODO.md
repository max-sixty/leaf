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

- **What reach would cost, and what the contract is.** leaf runs on two hosts because
  the loop needs three things from a harness, and only the third is scarce: run a
  command and get its complete output into model context; hold a session identity and
  lifetime to hang the page's life on; and wait without burning the turn, through a
  harness-native tracked job whose completion resumes or notifies the same agent. leaf
  has all three already — `CLAUDE_PID`, the walk up to a `codex` ancestor,
  `session.json`, and the three hooks — but written per host rather than against a
  named contract, so a third host is a rewrite rather than an implementation.
  Plannotator bought nine hosts one hook at a time behind an installer that detects
  what is on the machine (`notes/comparisons.md`), so the price is known and payable.
  The cheaper half is a foreground mode: `leaf wait` is already a plain command, and a
  documented path that blocks the turn and does without the hooks would reach any agent
  that can run one, at the cost of a turn sitting open. AG-UI is not the lever here —
  it standardises agent-to-UI streaming for a client-initiated run, where leaf's need
  is a harness waking an already-running session.
