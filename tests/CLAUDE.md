# Testing leaf

The suite proves the boundary between an authored page, the browser runtime, the
event log, and a returning reader. Most failures in that boundary are not hard to
assert once they are visible. The difficult part is arranging the test so that a
green result could only have come from the behavior named by the test.

This file owns the laws a test author needs before choosing a mechanism, and the
map to the helpers that carry each one. How a helper works — what it waits on, why
it reads what it reads, the failure that made it worth writing — is its docstring's,
so read the helper before copying its pattern. The runtime's `CLAUDE.md` and
`skills/leaf/references/internals/` own the product protocols. Keep implementation
rules there; state here only what a test must observe or control.

## Run the narrowest useful surface

A new cloud container needs the pinned environment and both browsers before the
suite can run:

```sh
uv sync --frozen
uv run playwright install chromium --only-shell
uv run playwright install chrome
uv tool install pre-commit
```

A container without IPv6 cannot run the two tests that bind the stated-host
wildcard `::`; run those from a workstation.

The everyday suite needs no network after setup and runs one shipped page through
the browser gate:

```sh
uv run pytest tests
```

The `test_render_*.py` modules and `test_site.py` are marked nightly. Broad
discovery skips them. An explicit file, node id, `-k`, `-m`, or `--lf` selection
runs what it names. During development, select the owning file or one named case
and use `-n 0` so the trace and process tree stay local:

```sh
uv run pytest tests/test_render_widgets.py -q -n0 -k board
uv run pytest --lf --lfnf=none -x -n0
```

Before handing over a browser-facing change, run its complete browser file and
the everyday suite. `wt merge` runs pre-commit and the everyday suite after
rebasing. CI adds `--run-nightly` after main moves.

`scripts/linux-suite.sh` supplies the pinned headless shell, installed Chrome,
and CI fonts. It accepts pytest arguments and needs a Docker daemon that can run
`linux/amd64`.

The developer environment comes from the one `pyproject.toml` and `uv.lock` at
the repo root, which is also the payload project: `uv sync` installs `leaf`
from this checkout editable, dev group included. So a test importing `leaf`
gets the checkout directly, and nothing puts a directory on the import path.

A test that runs leaf as a process of its own has two addresses and they answer
different questions: `LEAF_COMMAND` in `conftest.py` is what a command's behavior
is tested through, and `PLUGIN_ROOT / "bin" / "leaf"` is what a host runs; the
comment on `LEAF_COMMAND` says which subject takes which. `shipped_payload()` and
`install_payload()` in `interact_support.py` are the tree a completed change would
ship, read from git rather than the filesystem.

## Put each assertion at the boundary that owns it

The `test_interact_*.py` modules exercise authored markup, the registry, the event
log, CLI commands, vendoring, publishing, export, and server lifetime. The
`test_render_*.py` modules drive the browser runtime and the render gate.
File-side fixtures live in `interact_support.py`. Browser process and page
fixtures live in `render_harness.py`; reusable browser cases are grouped by
interaction, layout, navigation, and widget behavior in `render_cases_*.py`.
Both fixture modules use `TemporaryPageServer`, the same process-owned server as
`scripts/preview.py --automation`.
`render_support.py` reexports that surface for the test modules rather than
owning another copy. `test_site.py` reads the built site through its served URLs.
Product documentation tests compare the docs with the shipped vocabulary and
command surface: a shown command the click tree has not got, an `x-` key the guide
omits, a table that has drifted from the registry it was generated from.

That comparison is the whole of what a test over prose can prove. An assertion that
some sentence stands in a file a model reads — a skill, a reference, package
guidance, a paragraph of the docs — fails only when somebody rewrites that sentence.
So what it catches is an edit, and whether the edit was right is a question for
review either way. Every later rewrite then arrives as a test to work around. Derive
one side of a prose assertion from the machine, or leave the wording to review.

The distinction matters most around `render_version`. A property caused by a
particular page belongs in that gate, because `version check --render` must report
it to the page's author. A property that is identical for every valid page belongs
in the suite instead. `arrival_findings`, for example, tests the layer's behavior
when a reader returns with browser state already present; changing the authored
page cannot repair that behavior.

The same line runs through the render gate's own readings, and what decides it is
whether a reading needs a box. A reading of text or attributes may cross into the
thread panel, and several do: a widget an agent sent in a reply is a widget, and
`unreachableWords`, `silentWords` and `undeclaredAttrs` answer for it. A reading of
geometry may not, because the gate never opens the panel and a shut one has no boxes
at all; `trappedMargins` (`render-checks/framing.js`) says at the line that splits
it why the suite takes the layer's half. The suite opens the panel, where such a
widget has a box at last, and puts the product's own readings to it — `tinyBoxes`,
`clippedControls`, and that layer half. Each asserts its population first, and a
planted fault is scoped to `.lf-chrome`, so a clean result cannot come from a
reading that never arrived.

A reading that asks what keeps a box from being seen should not be a second answer
to a question the product already answers: `shownBand` is the layer's own reading,
`version check --render` imports it, and `RINGS_DRAWN` (`render_cases_layout.py`)
is a third consumer of it rather than a third copy. The comment on `RINGS_DRAWN`
carries the ring reading's whole contract — which box wears a ring, what counts as
the reader seeing the keyboard, how a reading proves it is not blind.

A reading blind to one mechanism does not report that it is blind — it returns the
same clean result it returns when nothing is wrong — so a green corpus is not
evidence of a clean corpus. Assert a gate's reach the way its population is
asserted: a planted fault of each shape the reading is written over, and a control
case that has to report nothing.

Prefer the public route through the product. A CLI test should invoke the command
or the same command function used by the entry point. A browser test should serve a
vendored page and use its HTTP API. A render-gate test should call
`leaf.render_gate.version.render_version`, not reproduce one of its probes. Test a
helper directly only when the helper itself carries a contract that would otherwise
be hard to diagnose, such as the traffic wait reaching its deadline.

A reading the layer makes from declarations belongs on a widget that declares them,
not on whichever shipped entry currently happens to. `serve` takes `layer_registry`
and `layer_widgets` for that: a project-package entry and its module, written as a
`render_cases_*` constant and reachable from any test module. Borrowing a shipped tag
reads the same for as long as the default package carries the declaration and goes
red the day it stops, with nothing about the reading having changed. A tag can also
leave the default package without leaving the product: `PAGE_PACKAGES` is what still
puts the `diagram` and `diff` packages' declarations in `page_dir`'s registry for
the readings that borrow them.

Re-vendor before trusting a result that depends on runtime, theme, registry, or
widget changes. A page directory owns the layer copied into it by `page init`; it
does not read the checkout's current assets. A green render against a stale page is
a statement about that stale copy.

## Fixtures own the world they create

Every test runs under `isolated_session`, which moves only the XDG config and state
directories leaf reads, supplies a synthetic Claude Code session id, and claims
pages under the current pytest worker's pid; its docstring says why `HOME` is not
moved. A test should declare its other conditions through fixtures rather than
deleting environment variables in its body: `sessionless` for a command launched
outside any host session, `codex_env` for a real Codex process ancestry.

A process the suite starts ends with the run. `spawn` owns every child process
started directly by a test, and `_no_page_outlives_its_test` releases the suite's
held leases and stops every live leaf server under the run's own roots — the sweep
exists for the server a test forgot to register. A standing server is the explicit
exception: it declines session ownership by definition, and a test of standing
lifetime must stop it itself. Keep that exception narrow and short-lived.

Reloading a page is not resetting it: panel state and drafts live in
`localStorage`, while reading position lives in `sessionStorage`. Clear both when a
test means a first visit. Conversely, two pages are not two tabs for a single reader
unless they share a browser context; `Browser.new_page` creates an independent
context, and `one_reader` supplies a shared one for the tests whose subject is
shared tab state. The static product-site session is the deliberate exception for
semantic page state: it has no Python authority, so its illustrative gestures last
for the current load and reset on reload. Do not make browser storage a durable
event log for that exhibit.

`leaf_page(title, body, head="")` is the complete, valid specimen. `serve` is the
normal owner of one in the browser: it publishes the document (or every version an
example ships, with the example's media, data, and log) as a fresh page directory
and serves it through the real HTTP handler; reach its directory through
`serve.page_dir` rather than constructing a parallel one whose relationship to the
served URL is implicit. `page_dir` in `interact_support.py` is the same for tests
that need no browser. Tests of initialization, re-vendoring, or a custom overlay
still cross the real `page init` boundary.

## Drive the browser a reader gets

The browser suite uses Playwright's pinned Chromium headless shell and real HTML.
Use `locator.click()`, `page.keyboard`, and `page.mouse` when the gesture matters.
A synthetic `dispatchEvent` can skip the pointer sequence the runtime listens to
and prove only that a handler works when called under an impossible event history.
Use `select` and `hold_selection` for selection drags.

`locator.click()` scrolls its target into view first, so a baseline read before one
is a reading of the page the test arranged and not of the page the press finds. A
test that scrolls a region away and then presses something in it measures the
driver's scroll, not the product's: it reported a panel moving 2455px to 0 for a
press that moved nothing. Where the subject is what a press does to a scroll
position, put the element on screen first — `scroll_into_view_if_needed()` says so
out loud — and read the baseline after that.

Nothing should be injected into the page merely to make ordinary observation easier.
Traffic is read off the delivery ledger the runtime itself paints on the root element
(`data-lf-traffic`, runtime/traffic.js). Network conditions come from `page.route`.
`watched` listens to the browser's error surfaces. `primed` lets a render or export
call create its own page while the test attaches those external controls before
navigation. These mechanisms exercise the runtime a reader receives.

An init script is justified only when the fact cannot survive long enough to cross
the Playwright boundary. Two cases earn it: recording a sequence frame by frame, and
capturing an instant between one DOM write and the next rendering turn. The injected
code records evidence; it does not decide when the test is complete. Completion still
comes from a browser or product fact visible outside the page.

## A page is ready when it says what has finished

Open ordinary browser pages through `open_page`. It installs `Traffic` and `watched`
before navigation, waits for the load event, and then waits on `BOTH_STAMPS`:

- `data-lf-upgraded="1"` says widget upgrade finished.
- `data-lf-applied` says a replay pass applied the event log.
- `data-lf-presented="1"` says the authoritative projection or offline fallback is
  safe for recorded interaction. The anchor pass and anchored composer begin here;
  authored HTML may have painted earlier.

These are independent facts. The document and first state read run together, and the
state answer remains unapplied until upgrade finishes. Network quiet does not imply
either one. A browser action sent before replay has landed may be ignored without a
later assertion revealing that the keypress itself was lost.

Use the shared `BOTH_STAMPS` predicate for manual navigations as well. Do not copy a
partial readiness expression into a test. The `upgraded=False` escape in `open_page`
is only for a test whose subject is the interval before those stamps.

`watched` must be installed before navigation; it and `render_version` share one
error channel, so the suite and the handover gate cannot disagree about which
browser errors count. Tests should assert `errors == []` after the behavior they
drive, not just after load.

## A wait consumes a fact the system states

A reliable wait consumes a fact stated by the system. It does not infer completion
from elapsed time, two matching samples, or a quiet network. A page that has not
started an effect is indistinguishable from one that finished if the only evidence is
stillness.

A computed style is one of those facts and it is not always a resting one. What the
platform reports for a property under a running transition is the animated value,
which early in one is the value the property is leaving — so a reading taken of a
control the gesture just changed can be a true answer about the wrong moment, and
steady enough while it lasts that two matching samples both land inside it. Ask
`getAnimations()` where a reading's subject may be in transit.

A wait states its end as well as its fact. `page.evaluate` takes no timeout in any
binding, so a promise awaited inside it is a wait nothing bounds: it spends the
job's whole step rather than failing in thirty seconds naming its test. State
synchronous readiness inside the page and poll it from outside, the way
`wait_for_probe` does; a shipped probe's ordinary browser lifecycle is always a
synchronous fact observed from outside the page.

### A state the page passes through is not a state to poll for

Use Playwright's `expect(...)` for a state that will become stable and remain true.
Use an ordinary read only after the causal edge is known to have completed. Do not use
an auto-retrying assertion for a transient state: it returns on the first matching
frame, even if the gesture continues to a different result.

The causal helpers, each with its mechanism in its docstring:

- `Traffic` reads the runtime's delivery ledger; `round_trip(page)` waits until
  every event attempt the page sent has a definitive outcome; `sending(page, what)`
  encloses a gesture whose own event the assertion behind it reads.
- `told(page)` waits until the page has applied the reading the server holds now,
  after the test writes a version, event, status, or lease behind a live page.
- `nudge(page_dir)` gives the page a reason to read without changing what it shows;
  `ticked(page)` waits for the page's next local re-application.
- `undo(page)` takes the last gesture back from the moment the key line offers to.
- `key_line(page)` reads what the key line says, once, after the repaint's own frame.
- `panel_settled`, `edge_settled`, `reservations_taken`, `margins_laid_out`, and
  `resized` each name the final fact of a layout or motion precisely; `moving` says
  when finite motion has ended.
- `wait_for_pending_mark` waits on what an anchor pass painted, never on the
  highlight registry holding a name — every pass registers every name, empty ranges
  included.

A surface that reads the same before and after the press cannot be its own wait.
`expect(...).to_have_text(...)` is satisfied by the frame the press has not reached
yet, and a measurement taken behind it then compares a reading with itself and
passes. When a surface does not itself change, a test whose subject is what a press
does *within* it waits on some other fact of that press, and its bug-back is run more
than once: a wait that is sometimes real looks exactly like a wait that is.

A retrying assertion that a paint has *not* happened is the same trap wearing the
other sign, and it is worse, because retrying is what usually rescues a reader from
it. A positive assertion polls until the frame arrives; a negative one is satisfied
by the first poll, and the first poll is before the frame. Wait on a positive fact
the same frame writes and read the absence behind it. Bug-back with a probe that
paints the mark the assertion denies, not by reverting the change: reverting usually
stops the mark being painted at all, which is a red for the wrong reason.

The key line is the sharpest case of that rule, because a second mechanism will
supply its answer late: every state application repaints it, the heartbeat's every
two seconds included, so an auto-retrying assertion on what it says goes green on
whichever tick lands inside its budget. A word that is supposed to turn over within
the press is read once, through `key_line`, and never waited for.

Read the event log only after `round_trip`, and read the event a gesture just made
through `sending`: the runtime posts behind the press or click the driver has already
returned from, so a trip waited on without `sending` can be over before the gesture's
own post exists, and the read behind it asserts over an event nobody made. Polling
the file until one expected event appears is not the alternative: it can miss an
extra send, and it cannot distinguish an unresolved request from a settled one.

Absence usually has no completion event of its own. Anchor it after the positive edge
that would have caused the forbidden behavior, then read once. If the mechanism is a
watcher or lease that acts only after a grace period, the test must hold a window
derived from that product constant plus scheduling room. Do not invent a generic
sleep for absence assertions.

When a wait times out, its message must say what evidence was missing, and its
deadline is fixed when the wait begins, so a page that keeps producing events cannot
keep a false fact alive. `_until` is the pattern: it prints the starting and final
ledger readings. New causal helpers need the same failure output and the same
bounded-progress property.

## State races are arrangements, not probabilities

If a race appears only on a loaded machine, make the ordering explicit with
`page.route`; do not repeat the test until the machine happens to lose it. Register
the route before the gesture whose request it must catch. For initial navigation,
attach it through `primed` so no request is already in flight, and use `held_events`
to hold event requests from navigation onward, including the first POST; `open_page`
arms interception on every page it makes so a route registered later still catches
its request (`arm_interception`).

That rule is about the page. A fact the driver loses on its way out of the browser
is not a page state any route can arrange, and it has no second channel to be read
through: `opened_tab` makes the press again because Chromium made the tab every time
and Playwright reported none of the lost ones. Reach for a repeat only with that
evidence in hand — the browser's own record showing the subject did its part — and
say so where the repeat is written.

A handler that appends a route to `held` has established only that the browser made
the request. Before indexing `held`, wait for the corresponding `Traffic` edge, a
request event, or another fact named by the handler. Some resources are requested
only after registry or state work, so layout becoming visible does not prove the
request exists.

Keep the three route operations distinct:

- Returning from a handler without resolving the route holds the request before the
  server receives it.
- `route.fetch()` lets the server answer but still withholds the response from the
  page. The log may therefore advance while the browser remains behind — behind, not
  deaf: the stream names the append within its look and the page reads at once, so
  a listener for what that read sets off (the next send of an ordered outbox, say)
  is armed before the `fetch`, never after it. Where one read has to carry the
  append and something appended after it, hold the reads (`CutOff`) until both are
  on disk.
- `refuse(route)` cancels a request without manufacturing a console error, so a test
  does not later assert over noise it made itself.

A route on `**/api/state*` still makes the page deaf: state reaches the page through
that request and through the answer to a post of its own, and through nothing else.
The route leaves the news stream alone, so the page goes on hearing that the server
has news. A read that failed is asked again two seconds later, and again, for as long
as the route stands.

Every hold has a release path. If the verdict depends on a response remaining lost,
make the assertion first, then continue or fulfill the route, wait for the handler to
finish, remove the route, and only then close the page. A route handler is a live
browser resource even after product state no longer depends on it; abandoning one can
hang context teardown after every assertion passed. Put release and `unroute` in
cleanup that also runs when the assertion fails. When a handler calls `route.fetch()`,
use `page.unroute_all(behavior="wait")` (or the context equivalent) before teardown:
the fetched response body belongs to that page or context, so ordinary close can
dispose it while a handler is still reading it and surface the callback's failure from
the next Playwright call.

The assertion should name the ordering the route created. For a serialized-send test,
hold the first POST, make the second gesture, and inspect `Traffic.sends` before
release. The final log order is useful too, but by itself it lets the scheduler choose
the test's premise. For a stale-state test, withhold the exact state response that
would otherwise reconcile the page and prove both the page's stale view and the
server's newer view before release.

### A repeated gesture has to let the repaint it causes land

Pressing the same key twice inside one round-trip is not a reader pressing it twice.
Work coalesced into a `requestAnimationFrame` runs between a person's two presses and
between none of a test's, so a fault that the repaint itself causes is invisible to
exactly the rhythm a suite presses at — and reads as correct rather than as flaky.
So a walk, or any repeated press a repaint could answer, waits a frame between
presses and says why. Where waiting is what changes the outcome, the contrast is the
assertion rather than a threshold:
`test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted` runs one walk
both ways and holds the two to being the same walk, because a count of lost stops has
no honest threshold.

## Distinguish a frame, a sequence, and an instant

Most visual behavior can be tested from stable states before and after a gesture. The
test must cross the transition that could reveal the fault. Geometry measured twice
within one final state proves nothing about motion between those reads.

A frame is one held state. `HOLD_MOTION` pauses animations so a short-lived midpoint
can remain available while Playwright inspects it; its comment says what
`window.__lfHeld` holds and how a held motion is stepped or released. A gesture on
the way to the one under test still has to reach its end state under that hold, and
the harness helper for the gesture owns it — `panel_settled` and `edge_settled`
finish the shell carry rather than waiting out a clock the test has stopped. Every
workspace gesture starts that same carry, so a test holding motion that opens a
panel or a tray by hand needs the same, or it reads a page parked mid-carry.

A sequence is ordered evidence across frames. A fold can have correct start, midpoint,
and final values yet flash its unanimated state for one frame when the effect expires.
`test_the_fold_never_paints_a_frame_that_undoes_the_last` records every painted frame
inside the page because the browser exposes no durable outside event for that ordering.
The node leaving the list remains the external completion fact. Use this pattern only
when intermediate order is the contract; do not turn every transition test into a
sampler.

An instant is a state that exists within one rendering turn. In
`test_the_room_is_measured_after_a_late_rail`, a `MutationObserver` records layout when
the upgrade stamp changes, before the next frame can restate the room. A Playwright
evaluation issued after the stamp would read the later corrected state and let the
line under test disappear. Again, the injected observer captures the instant; the
stamp is the completion fact.

Do not substitute frame counts or quiet windows for these distinctions. Under load,
the first animation frame may arrive after the whole quiet window, and a pair of equal
samples can both precede the transition. Ask whether the claim concerns the settled
state, one frame, the order of frames, or the exact turn of a write, then choose the
smallest observation that can preserve it.

The movement tests ask both paths that can shift a target:

- press a control and compare the rest of its line;
- let news arrive and compare all persistent chrome controls.

A pixel diff is required for borders, outlines, and shadows that can paint
outside unchanged rectangles. Box comparisons alone cannot see those changes.

## Make a green test non-vacuous

For each assertion, state the causal contrast: what single product change would make
it fail? Arrange the fixture so that change reaches the measured surface. A test that
cannot answer this is not yet evidence.

Reintroduce a new defect and run the intended gate before accepting it. For an existing
gate touched by a refactor, repeat the bug-back if the direction or representation of
the failure changed. Bounds and geometry tests are especially prone to staying green
after the fault moves to another edge.

### An absence needs a control and a settled frame

A web-first assertion succeeds on its first satisfying poll, so `to_be_hidden` on
something the runtime has not yet decided to show passes on the frame before the
decision. The runtime raises chrome from deferred steps — `updateFab` runs inside the
mouseup handler's `setTimeout` — so the assertion has to come after the turn the
handler used, either by draining that queue or by waiting on a fact the decision
writes.

The wait is not enough on its own. An absence is also what a page that never had the
behaviour produces, so a test asserting one names a control that must first produce
the presence: the same gesture where it is supposed to work. The fab test for a
selection inside a message passed with its whole fix reverted until it had both.

### A sweep that walks controls by index must prove it pressed them

Sweeps must prove they exercised their specimens. If controls are discovered by index,
pin the expected identities or count before and after reload so a shorter list cannot
silently skip work. If a test iterates registry declarations, assert that the target
declaration set is nonempty and that every expected kind was reached. Avoid conditional
assertions whose condition can disappear with the behavior under test.

An assertion that nothing moved must straddle a transition that would move without the
rule. Moving a pick from one card to another can preserve total reserved space even if
the reservation rule is gone. Moving from no pick to one pick exposes the missing
space. The same principle applies to panel room, palette changes, reload restoration,
and version replay: choose an anchor and a single-factor neighbor whose difference is
the product rule being tested.

Check what a lower layer already guarantees. If the send queue prevents a second
physical POST, counting held routes cannot prove that the widget itself rejected a
second gesture. Inspect the later log or visible outcome where the widget's decision
would survive after the queue drains. A test is vacuous when some unrelated mechanism
makes its assertion true under both the good and bad implementation.

The corpus has two important causal matrices. A first visit is the anchor for return
state: `arrival_findings` reloads a page with the panel open, a tray standing,
or design mode on and reports motion or failure that the first visit did not have. A
static authored state is the anchor for semantic replay: apply standing actions or
reports, reapply them, and verify both the visible state and idempotence. Keep those
matrices declaration-driven so a new widget or event verb joins through the registry
rather than a test-side name list.

Generated markup needs its own gates because the source lint cannot see what a module
writes. Render tests check upgraded widget size and accessibility, undeclared author-
namespace attributes, registry-declared record forms, and relative replays. When a
widget changes the DOM, make sure the relevant render probe can fail with that change
reintroduced; a source-only assertion cannot cover a generated attribute or a replay
that moves on its second application. The canonical named probes are
`undeclaredAttrs` and `relativeReplays`, invoked through
`leaf.render_checks.evaluate_probe` rather than maintained as test-side variants;
their fixtures must include at least one widget and verb that can trigger the
finding, or a clean result only says the probe received an empty population.

## Fail with the evidence needed to act

Do not combine `capture_output=True` with `check=True` unless the raised exception is
unpacked and reported. Capturing a child process's streams removes them from pytest's
normal failure output. When a test needs the streams for assertions, run without
`check=True`, assert the return code explicitly, and include both stdout and stderr in
the assertion message. When it does not need them, let the subprocess inherit pytest's
captured streams.

The same rule applies to helper failures. An assertion should name the URL, version,
widget, event, or traffic counters that distinguish causes. `open_page` enriches HTTP
failures with status and URL because the browser's generic console message is not
actionable. `round_trip` reports both ends of its wait. A fixture cleanup failure should
name the server or process it could not stop.

At the end of a browser journey, assert the collected error list after all gestures,
polls, reloads, and route releases, then close the page or let its owning context close
it. Do not clear errors merely to make a later phase easier to read; if an earlier fault
is intentionally induced, assert and remove that exact expected entry at the point it
occurs.

Finally, assert durable output as meaning rather than formatter layout. Prettier may
reflow prose and tags. Collapse whitespace when testing what a page says, use
`spoken` when the registry-backed reading is already available, and match the attribute
that carries a markup claim rather than a complete serialized tag. Reserve exact source
and line assertions for tests whose subject is source structure or a diagnostic
location.
