# TODO

- **Widget-part keyboard addresses.** The `g` chord currently names only core lists.
  If it grows addresses for widget parts such as board grips or draft editors, the
  registry should declare them with an `x-` key. Existing groups already expose their
  options through focused digit bindings, so no change is needed yet.

- **A focus indicator that is not an outline, and the control the fold never reaches.**
  Two halves of one gap, measured together and left because neither known mechanism
  closes it.

  The ring sweep
  (`test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus`)
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

- **Let the Living Margin carry short anchored conversations.** Its current markers
  answer “what is happening here?”, while the Asks tray answers “what still needs me?”
  and the Comments panel holds complete conversation history. A marker could reveal a
  short thread on hover or focus, pin it on click, and offer `Reply`, `Resolve`, and
  `Open conversation` from the pinned card. Longer threads could show the root and
  latest reply followed by `Open thread (N)`. This would make the margin the quick path
  for local discussion without asking it to absorb search, detached comments, history,
  or long-form replies.

- **Prototype a LessWrong-like left comment margin as an alternate presentation.** It
  would expose more comment text at a glance than the right-side semantic map, but it
  also competes with the Leaves/Asks tray, privileges comments over changes and
  decisions, and needs collision rules when several comments meet one passage. Try it
  only where the margin is wide and sparse, cluster overflow, and collapse it to the
  existing mobile Map sheet. Do not show left comment cards and right map markers as
  permanent simultaneous rails.

- **Keep narrow-page navigation legible as the margin evolves.** `Map` is currently the
  only header control created by the narrow breakpoint; it replaces the hidden rail,
  while the other controls merely reorder or appear because page state calls for them.
  Preserve that one-for-one relationship if the margin gains conversations or another
  presentation, rather than accumulating width-only destinations in the header.

- **Card density in the comment panel.** Halving the thread card's padding and margins
  frees 570px of a 4,612px list — half of what folding the reply box bought — while
  hiding nothing and overturning no contract. It is a change to how every card looks, so
  it wants a look rather than a measurement: fold plus density is 5.8 screens and four
  whole cards per screen, against the current 6.7 and three.

- **Folding the panel's reply boxes.** Tried on this
  branch and taken back out. Measured on a 24-thread page: folding every box but the one
  being written on takes the list from 5,723px to 4,612px — 8.3 screens to 6.7, and two
  whole cards per screen to three — but nothing closes a box again, so the saving decays
  with use: 4,751px after opening three, 4,890px after six, 5,029px after nine, i.e. 19%
  down to 12%. Against that, the panel's narrowings already take the same list to 4.5
  screens (waiting-on-you) or 2.2 (a find) without it. It also introduced three of the
  five ways the list can move under a gesture. With panel reflow now held in place, this
  is a plain length question with no defect attached. The removed work is on this
  branch's history at `54246d51`, `63664054`, `c98914ac`, `a1db012f`.

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

- **Install outside packages by name.** Let `leaf package install SOURCE` place an
  outside package in a user-owned store and make the same `--package NAME` form select
  it. Package names should resolve to directories before composition, so bundled and
  installed packages keep one contract. Let dogfooding determine what installation
  needs for source identity, updates, pinning, and trust rather than adding those
  policies to the first shortcut.

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
