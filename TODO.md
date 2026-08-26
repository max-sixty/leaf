# TODO

- **Widget-part keyboard addresses.** The `g` chord currently names only core lists.
  If it grows addresses for widget parts such as board grips or draft editors, the
  registry should declare them with an `x-` key. Existing groups already expose their
  options through focused digit bindings, so no change is needed yet.

- **Contrast inside the comment panel.** A thread's `<time>` reads at 2.9:1 in light
  and 3.29:1 in dark against the panel's card, both under AA's 4.5:1 at its 11.5px
  size. `--muted-2` is a deliberate tier below `--muted`, worn by the banner's dot, a
  detached quote, a detached link and the diff's gutter, so raising it is a decision
  about that tier rather than about the clock. Nothing has ever measured it:
  `test_examples_have_no_serious_wcag_a_or_aa_violations` reads every example with the
  panel shut, so no chrome inside the panel has been through axe at all. Whichever way
  the tier goes, that sweep wants an arm with the panel open. Run by hand over a page of
  twenty-four threads in both schemes, the clock is the only serious finding the open
  panel produces — the head, the find row, the run headings and the thread controls are
  clean — so the arm can go in the moment the tier is decided.

- **A focus indicator that is not an outline, and the control the fold never reaches.**
  Two halves of one gap, measured together and left because neither known mechanism
  closes it.

  The ring sweep (`test_every_control_a_shipped_page_can_tab_to_shows_its_whole_ring`)
  measures an outline, so a control indicating focus another way is counted as ringless
  and skipped — the runtime's own textareas take `outline: none` and draw a 2px spread
  `box-shadow` (`.lf-ui textarea:focus`). Widening the sweep to read a shadow's spread is
  a few lines; two things have to be got right while doing it, both of which caught me:
  drawn and grown are separate questions (an inset ring is a ring and grows by nothing,
  so reading one as the other counts every inset ring as none), and the computed shadow
  colour serialises as `color(srgb …)`, whose numbers carry no unit and so do not
  disturb a `px` scan.

  Widened, it reports one live fault on `gallery` and on `ship-review`: tabbing to a page
  textarea near the fold leaves its shadow ring ~1.5px below body's clip. Measured, the
  box ends at 899px in a 900px viewport with `scroll-padding-bottom: 5px` declared on the
  scroller and 2,520px of scroll still available. Nothing scrolled: Chrome decides
  whether a scroll is needed from the border box alone, so a control resting a pixel
  inside the fold is already visible and the region's reservation is never spent.
  `scroll-margin` on the control is the other half of that CSS mechanism and is the
  obvious answer — it does not work either, measured. So the fix is neither of the two
  properties built for this, and finding what it is wants its own sitting rather than a
  guess at the end of another change.

- **Card density in the comment panel.** Halving the thread card's padding and margins
  frees 570px of a 4,612px list — half of what folding the reply box bought — while
  hiding nothing and overturning no contract. It is a change to how every card looks, so
  it wants a look rather than a measurement: fold plus density is 5.8 screens and four
  whole cards per screen, against the current 6.7 and three.

- **The panel cannot hold the reader's spot across a reflow.** Every writer of the thread
  list's geometry can move content between the browser's scroll anchor and the spot the
  reader is aiming at, and the browser's own anchoring provably declines to cover it:
  measured, it contributes 0px for a change *inside* the viewport at every scroll
  position, compensating only for changes above the anchor node it picks at the top of
  the visible region. So the constraint is where in the viewport a change lands, not how
  much scroll remains — a claim this repo got wrong once already.

  Two consequences are live today, both older than any of this:
  - A reply arriving between a press's mousedown and its mouseup moves the list 108px and
    the mouseup's target becomes `.lf-threads`. A `Resolve` pressed at that moment never
    happens, silently.
  - `foldOut` animates a resolving card's removal over ~1s, and the pointer's coordinate
    is wrong for the whole of it — a card top measured running 691 → 439 → 399, ending
    three cards away from what was under the pointer.

  The fix is one primitive rather than a rule per writer: `renderThreads` is already the
  single writer of the list, so every mutation can pick a reference (the card under the
  pointer when the pointer is over `.lf-threads`, else the focused card, else the topmost
  visible card), record its `top`, mutate, and add the delta back to `scrollTop`. Two
  honest limits: it cannot absorb shrinkage above a reference already at `scrollTop 0`,
  and `foldOut`'s animated reflow needs the correction per frame or should become a
  discrete removal under the same hold.

- **Folding the panel's reply boxes, if the spot-hold primitive lands.** Tried on this
  branch and taken back out. Measured on a 24-thread page: folding every box but the one
  being written on takes the list from 5,723px to 4,612px — 8.3 screens to 6.7, and two
  whole cards per screen to three — but nothing closes a box again, so the saving decays
  with use: 4,751px after opening three, 4,890px after six, 5,029px after nine, i.e. 19%
  down to 12%. Against that, the panel's narrowings already take the same list to 4.5
  screens (waiting-on-you) or 2.2 (a find) without it. It also introduced three of the
  five ways the list can move under a gesture, which is what sent this to the note above.
  Worth revisiting only once that primitive exists, and then it is a plain length
  question with no defect attached. The removed work is on this branch's history at
  `54246d51`, `63664054`, `c98914ac`, `a1db012f`.

- **Focus lost from a reply box someone else settles.** Tab 1 is typing in thread A's
  reply box; tab 2, or the agent, resolves A. Tab 1's `document.activeElement` ends as
  `<body>`, so the next Space scrolls the page behind the panel. The words survive in the
  draft store. `renderThreads`' `standingIn` guard exists to prevent exactly this and
  misses because `foldOut` blurs the box and sets `inert` before `standingIn` is read.
  Pre-existing; a card standing open is where a reader now meets it.

- **A send in flight steals the box the reader opened while waiting.** `landTyping` after
  a composer send lands the reader in the new thread's reply box, and its only guard is
  `pageSelection()`. Hold the POST and open a reply on another thread while it is in the
  wire: when the send lands, focus jumps out of the box being typed in. A reply box the
  reader opened during the flight is the same kind of later gesture a selection is, and
  is not asked about. Pre-existing; the fold makes its consequence visible, since an
  empty box left behind then folds away.

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
  the canonical claim record, and the three hooks — but written per host rather
  than against a named contract, so a third host is a rewrite rather than an
  implementation.
  Plannotator bought nine hosts one hook at a time behind an installer that detects
  what is on the machine (`notes/comparisons.md`), so the price is known and payable.
  The cheaper half is a foreground mode: `leaf wait` is already a plain command, and a
  documented path that blocks the turn and does without the hooks would reach any agent
  that can run one, at the cost of a turn sitting open. AG-UI is not the lever here —
  it standardises agent-to-UI streaming for a client-initiated run, where leaf's need
  is a harness waking an already-running session.
