# Testing leaf

The suite proves the boundary between an authored page, the browser runtime, the
event log, and a returning reader. Most failures in that boundary are not hard to
assert once they are visible. The difficult part is arranging the test so that a
green result could only have come from the behavior named by the test.

This file owns those testing mechanics. The repository-level `CLAUDE.md` owns
environment setup, suite inventory, and the normal run. The runtime's
`CLAUDE.md` and `interact.py` own the product protocols. Keep their implementation
rules there; state here only what a test must observe or control.

## Run the narrowest useful surface

The repository guide's "The suite" section owns setup and test commands. During
development, select the owning file or one named case and use `-n 0` so the trace
and process tree stay local. Before landing a browser-facing change, run its
complete browser file and the repository's normal suite.

## Put each assertion at the boundary that owns it

The `test_interact_*.py` modules exercise authored markup, the registry, the event
log, CLI commands, vendoring, publishing, export, and server lifetime. The
`test_render_*.py` modules drive the browser runtime and the render gate.
File-side fixtures live in `interact_support.py`. Browser process and page
fixtures live in `render_harness.py`; reusable browser cases are grouped by
interaction, layout, navigation, and widget behavior in `render_cases_*.py`.
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
whether a reading needs a box.

A reading of text or attributes may cross into the comment panel, and several do:
a widget an agent sent in a reply is a widget, and `UNREACHABLE_WORDS`,
`SILENT_WORDS` and `UNDECLARED_ATTRS` answer for it. A reading of geometry may not,
because the gate never opens the panel and a shut one has no boxes at all. Most
stop there by construction — at `.lf-chrome`, or by starting from `main` — and
`TINY_BOXES` and `CLIPPED_CONTROLS` stop at `checkVisibility()`.

`TRAPPED_MARGINS` is the exception, and it is a box reading wearing a computed
style reading's clothes: inside `display: none` an element's own `display` is still
`block` and its padding and margins still resolve, so it reads the panel and gets
plausible numbers. They are not the panel's numbers. A size container query does
not match in there, so a rule that switches a slot between two forms is stuck on
one of them, and a percentage margin comes back unresolved. It therefore tags each
finding with which document it is in, and the gate takes the page's half.

What the layer does with a box is the suite's — `TRAPPED_MARGINS` states why at
the line that splits it. So the suite opens the panel, where such a widget has a
box at last, and puts the product's own readings to it: `TINY_BOXES` and
`CLIPPED_CONTROLS` over the open panel, and `TRAPPED_MARGINS`'s layer half. Each
asserts its population first, and a planted fault is scoped to `.lf-chrome`, so a
clean result cannot come from a reading that never arrived.

A reading that asks what keeps a box from being seen should not be a second answer
to a question the product already answers. `shownBand` is the layer's own reading
of the band a box shows, and it names all three ways a box draws nothing past its
edge: overflow, paint containment, and `content-visibility`. `version check
--render` imports it so the band a handover is refused against and the band the
page paints to are one reading, and its comment records that the two copies before
it disagreed twice. `RING_FAULTS` is a third consumer of it rather than a third
copy of it, and it asks the window on the same terms as any other box: a fixed
subtree is laid out against the window, and everything else reaches it through
`body`, which is this page's scroller.

A ring is also only drawn for a press. `element.focus()` sets `:focus` and not
`:focus-visible`, so a control focused from script wears no ring at all, and every
reading of one comes back empty — the same empty that a control whose ring is
perfectly fine comes back with. Reach it with a real `Tab`, or focus it and press
`Tab` then `Shift+Tab` back onto it, and asserting the ring is there comes before
asserting anything about its shape.

The failure that makes this worth stating is a quiet one. A reading blind to one
mechanism does not report that it is blind — it returns the same clean result it
returns when nothing is wrong — so a green corpus is not evidence of a clean
corpus. Assert a gate's reach the way its population is asserted:
`test_the_ring_reading_names_every_way_a_box_can_draw_nothing_past_its_edge` puts
one displacement under three parents differing only in how they clip, with a
control case that has to report nothing.

`RING_FAULTS` has gone blind once more since, in what it reads rather than in
what it walks, and silently. Its excuse for a control standing behind something
has to step past the ring's own band to ask the question, which is `grow + w`;
written as one pixel it cleared an outward ring and landed inside an inset one,
so every covered inset ring answered that the control was behind the same thing —
and the panel's list draws nothing but inset rings. A reach case for the cover
half already stood, and it could not have caught this: it plants over a ring
drawn outside its control, where any step in clears the band.
`test_the_ring_reading_sees_a_neighbour_paint_over_a_ring_drawn_inside_its_box`
is the same plant over the other shape. A reach case answers for the shapes it
is written over, and a ring has two.

Prefer the public route through the product. A CLI test should invoke the command
or the same command function used by the entry point. A browser test should serve a
vendored page and use its HTTP API. A render-gate test should call
`leaf_interact.rendering.render_version`, not reproduce one of its probes. Test a helper directly
only when the helper itself carries a contract that would otherwise be hard to
diagnose, such as the traffic wait reaching its deadline.

Re-vendor before trusting a result that depends on runtime, theme, registry, or
widget changes. A page directory owns the layer copied into it by `page init`; it
does not read the checkout's current assets. A green render against a stale page is
a statement about that stale copy.

## Fixtures own the world they create

Every test runs under `isolated_session`. It moves only the XDG config and state
directories leaf reads, supplies a synthetic Claude Code session id, and claims
pages under the current pytest worker's pid. This keeps the developer's overlay,
session record, pages, and event history out of the test. Do not replace it by
moving `HOME`; uv's cache and unrelated developer state are not part of leaf's
isolation boundary.

The one subject that must take uv's cache into its world is what the launcher
resolves. A test of where `bin/leaf` looks for a dependency asks the host's index
for every one of them, so it needs the network the nightly run holds. It also
needs a cache directory of its own (`UV_CACHE_DIR`): a wheel already in the
developer's cache answers before any index is consulted, so the run would prove
nothing.

Use `sessionless` when the subject is a command launched outside any host session.
Use `codex_env` when constructing a real Codex process ancestry; it removes the
Claude identity that would otherwise win host detection. A test should declare
those conditions through fixtures rather than deleting environment variables in
its body.

### A process the suite starts ends with the run

Server ownership has two layers:

- `spawn` owns every child process started directly by a test and terminates any
  survivor during teardown.
- `_no_page_outlives_its_test` releases the suite's held leases, searches the
  temporary page and state roots, and stops every live leaf server it finds.

The search is intentional. A cleanup list catches only the server a test remembered
to register; the fixture exists for the forgotten one as well. A page server is
spawned into its own process session, so a local `Popen` handle is not a general
substitute for `leaf server stop`. The synthetic session claim is the final owner
when a worker itself is killed and fixture teardown cannot run.

A standing server is the explicit exception. It declines session ownership by
definition, and tests of standing lifetime must stop it themselves. Keep that
exception narrow and short-lived. If the test does not need standing lifetime, use
the ordinary served-page fixtures.

The sweep's roots are the run's own: the test's `tmp_path` and the state home
`isolated_session` returns. An autouse fixture that needs the isolated home takes it
from that fixture; the environment is wrong at both of its ends. Autouse fixtures set
up outermost first — a `pytest_plugins` module's before the conftest's — and tear
down in reverse, so a sweep with no dependency on the isolation reads `state_home()`
before it is applied at setup and after `monkeypatch` has undone it at teardown. Read
at setup, it answered with the developer's `~/.local/state/leaf`, and every page
server they had standing there was stopped half a second after each start whenever
any suite ran on the machine, with no run reporting it.
`test_a_run_ends_only_the_servers_it_started` runs a nested suite against a planted
home and requires the planted page untouched and the run's own leftover stopped.

### Reloading is not resetting

Fixtures also own browser storage boundaries. Reloading a page is not resetting it:
panel state and drafts live in `localStorage`, while reading position lives in
`sessionStorage`. Clear both when a test means a first visit. Conversely, two pages
are not two tabs for a single reader unless they share a browser context.
`Browser.new_page` creates an independent context; `one_reader` supplies one context
for the tests whose subject is shared tab state.

For complete, valid browser fixtures, use `leaf_page(title, body, head="")`. It
supplies the same language, charset, CSP, theme, module, and main-content shell to
every specimen. Keep raw documents only when source structure is the subject: lint
fixtures, malformed markup, tokenizer input, line-number assertions, or a document
whose missing boundary is the condition under test. A shared shell must not repair
the malformed case a test is meant to present.

The browser fixture `serve` is the normal owner of a specimen. It runs `page init`
to vendor the current layer, writes the document as v1, copies example media, adds
the publishing note and any requested comments, then serves the directory with the
real HTTP handler and page key. Handed an example's path rather than its markup it
also lays in the log that example ships, and sets the cursor past it: a page is
what its markup and its standing log make together, and a thread — or a widget a
message carries — exists nowhere else. Pass the markup where the log would be
noise for the subject, and say which in a comment. Reach its page directory through `serve.page_dir`
when a test needs to publish v2 or inspect the log; do not construct a parallel
directory whose relationship to the served URL is implicit. `page_dir` in
`interact_support.py` owns command-level files without starting a browser. Keeping
those roles separate makes it clear whether a failure belongs to the file/CLI
boundary or to the served runtime.

## Drive the browser a reader gets

The browser suite uses Playwright's pinned Chromium headless shell and real HTML.
Use `locator.click()`, `page.keyboard`, and `page.mouse` when the gesture matters.
A synthetic `dispatchEvent` can skip the pointer sequence the runtime listens to
and prove only that a handler works when called under an impossible event history.

Use `select` for selection drags. It floors the starting coordinates to a whole
pixel because a fractional point can straddle a glyph's caret boundary and leave an
otherwise valid drag with an empty selection. Preserve the end coordinate: changing
its precision can move the selected character.

`locator.click()` scrolls its target into view first, so a baseline read before one
is a reading of the page the test arranged and not of the page the press finds. A
test that scrolls a region away and then presses something in it measures the
driver's scroll, not the product's: it reported a panel moving 2455px to 0 for a
press that moved nothing. Where the subject is what a press does to a scroll
position, put the element on screen first — `scroll_into_view_if_needed()` says so
out loud — and read the baseline after that.

Nothing should be injected into the page merely to make ordinary observation easier.
Traffic comes from Playwright's request, response, and request-failure events. Network
conditions come from `page.route`. `watched` listens to the browser's error surfaces.
`primed` lets a render or export call create its own page while the test attaches
those external controls before navigation. These mechanisms exercise the runtime a
reader receives.

An init script is justified only when the fact cannot survive long enough to cross
the Playwright boundary. Two cases earn it: recording a sequence frame by frame, and
capturing an instant between one DOM write and the next rendering turn. The injected
code records evidence; it does not decide when the test is complete. Completion still
comes from a browser or product fact visible outside the page.

## A page is ready when it says what has finished

Open ordinary browser pages through `open_page`. It installs `Traffic` and `watched`
before navigation, waits for the load event, and then waits on `BOTH_STAMPS`:

- `data-lf-upgraded="1"` says widget upgrade and anchor preparation finished.
- `data-lf-applied` says a replay pass applied the event log.
- `data-lf-presented="1"` says any deliberately shown waiting surface completed its
  minimum presentation.

These are independent facts. The document can finish upgrading before its first
state response arrives, and an applied state can still sit behind a waiting surface.
Network quiet does not imply either one. A browser action sent before replay has
landed may be ignored without a later assertion revealing that the keypress itself
was lost.

Use the shared `BOTH_STAMPS` predicate for manual navigations as well. Do not copy a
partial readiness expression into a test. The `upgraded=False` escape in `open_page`
is only for a test whose subject is the interval before those stamps; it waits for the
banner module to exist and must make its later readiness explicit.

`watched` must be installed before navigation. It collects console errors and
`pageerror`, and installs `leaf_interact.rendering.WINDOW_ERRORS` so browser `error` events without
an exception, including ResizeObserver delivery failures, reach the same error list.
That script is shared with `render_version`; the suite and the handover gate must not
disagree about which browser error channels count.

`navigate` handles the one browser notice that needs confirmation. A
ResizeObserver-loop notice raised during handover is repeated with a complete second
navigation; a recurring notice is a failure, while a one-off platform notice is not.
Other errors remain strict, and any error raised after handover remains in the list.
Tests should assert `errors == []` after the behavior they drive, not just after load.

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
`getAnimations()` where a reading's subject may be in transit. What made this worth
saying was a page where every subject was: under `reduced_motion="reduce"` the
theme's guard shortened transitions rather than removing them, and
`transition-property` is `all`, so every property that changed on any element was a
property in transit for two frames. That is fixed in the theme, which is why no
reading here carries such a wait — a wait in front of a reading whose subject never
moves is a mechanism that cannot fail and cannot help.

### A state the page passes through is not a state to poll for

Use Playwright's `expect(...)` for a state that will become stable and remain true.
Use an ordinary read only after the causal edge is known to have completed. Do not use
an auto-retrying assertion for a transient state: it returns on the first matching
frame, even if the gesture continues to a different result.

The main causal helpers are:

- `Traffic` observes the page's lifetime request traffic from outside the runtime.
  It tracks event attempts separately from physical requests and includes reloads.
- `round_trip(page)` waits until every event attempt sent by that page has a
  definitive outcome: an accepted or final refusal response, or a state response
  containing the attempt. A request failure alone is not final because the page may
  retry the same attempt.
- `told(page)` records the current state-request count, then waits for a later poll to
  receive an answer. Use it after the test writes a version, event, status, or lease
  that the browser learns through polling.
- `undo(page)` first waits until the key line offers undo, presses `z`, observes the
  new send enter the wire, and waits for its round trip. A visible changed widget is
  not enough: undo can be refused while the preceding gesture is still unresolved.
- `key_line(page)` reads what the key line says, once, after the repaint's own frame.
  `paintHere` coalesces to a `requestAnimationFrame`, so a read taken in the same
  round-trip as the press that caused it is a read of the frame before.

The key line is the sharpest case of the rule above, because a second mechanism will
supply its answer late. Every state poll repaints it, so an auto-retrying assertion on
what it says goes green on whichever poll lands inside its budget — which is the poll's
answer, not the writer's. A word that is supposed to turn over within the press is
therefore read once, through `key_line`, and never waited for. The bug-back is what
says which one a test has: with the runtime's disclosure watch removed, an
`expect(...).to_contain_text(..., timeout=1500)` on the word still passed, and the
same assertion read once failed.

Read the event log only after `round_trip`. Polling the file until one expected event
appears can miss an extra send, and it cannot distinguish an unresolved request from
a settled one. Read browser state after the trip when the returned state is part of
the assertion. `round_trip` proves delivery; it does not claim every rendered effect
of the response has completed. When applying the response is itself the subject, wait
for `data-lf-applied` to cover the expected events before reading the resulting surface
or making a gesture whose liveness depends on that projection. That stamp counts
replayed actions, reports, and undos, and no comment: a comment, a reply, or a
reaction never moves it, so a wait on it for one of those spends the whole timeout.
The fact such an event states is its paint or its card — wait on that
(`test_render_reactions.py`'s `painted` reads the highlight and the seated glyphs).

After changing a file behind a live page, call `told` before reading the page. Letting
`expect` absorb the next polling interval hides which mechanism supplied the wait and
spends its timeout budget on transport rather than on the assertion.

For layout, animation, and navigation, identify the final fact precisely.
`panel_settled` waits for the requested panel class and then for the body's finite
animations to empty. `resized` waits for the resize event to reach listeners; a new
viewport size says only that the browser resized, not that page layout handled it.
An observer or protocol record that outlives a motion is read after `MOVING` says finite
motion has ended; a fixed number of animation frames only guesses when that record will
be delivered under load.
When clicking a quote causes an instant scroll followed by a smooth scroll, the first
`scrollend` is a real edge but not the destination. Wait for the mark to reach the
computed position or for the final scroll to stop, then assert where it stopped.

Absence usually has no completion event of its own. Anchor it after the positive edge
that would have caused the forbidden behavior, then read once. If the mechanism is a
watcher or lease that acts only after a grace period, the test must hold a window
derived from that product constant plus scheduling room. Do not invent a generic
sleep for absence assertions.

When a wait times out, its message must say what evidence was missing. `_until`
includes the starting and final `Traffic` counters, which distinguishes a stuck event
from a page that stopped communicating. Its deadline is fixed when the wait begins:
responses may wake the check, but a busy response stream cannot extend the deadline
and keep a false delivery fact alive forever. New causal helpers need similarly useful
failure output and the same bounded-progress property.

## State races are arrangements, not probabilities

If a race appears only on a loaded machine, make the ordering explicit with
`page.route`; do not repeat the test until the machine happens to lose it. Register
the route before the gesture whose request it must catch. For initial navigation,
attach it through `primed` so no request is already in flight.

A handler that appends a route to `held` has established only that the browser made
the request. Before indexing `held`, wait for the corresponding `Traffic` edge, a
request event, or another fact named by the handler. Some resources are requested
only after registry or state work, so layout becoming visible does not prove the
request exists.

Keep the three route operations distinct:

- Returning from a handler without resolving the route holds the request before the
  server receives it.
- `route.fetch()` lets the server answer but still withholds the response from the
  page. The log may therefore advance while the browser remains behind.
- `refuse(route)` cancels a poll without manufacturing a console error. Use an
  ordinary abort only when the failed request and its browser error are the subject.

Every hold has a release path. If the verdict depends on a response remaining lost,
make the assertion first, then continue or fulfill the route, wait for the handler to
finish, remove the route, and only then close the page. A route handler is a live
browser resource even after product state no longer depends on it; abandoning one can
hang context teardown after every assertion passed. Put release and `unroute` in
cleanup that also runs when the assertion fails.

The assertion should name the ordering the route created. For a serialized-send test,
hold the first POST, make the second gesture, and inspect `Traffic.sends` before
release. The final log order is useful too, but by itself it lets the scheduler choose
the test's premise. For a stale-state test, withhold the exact state response that
would otherwise reconcile the page and prove both the page's stale view and the
server's newer view before release.

### A test cannot assert over noise it makes itself

Instrumentation must not pollute the channel it later asserts is quiet. Chrome reports
a default aborted request as a console load failure. That is why `refuse` uses the
`aborted` cancellation reason for polling conditions. If a test intentionally produces
an HTTP error, assert the enriched status-and-URL entry collected by `open_page`
instead of filtering it out globally.

### A repeated gesture has to let the repaint it causes land

Pressing the same key twice inside one round-trip is not a reader pressing it twice.
Work coalesced into a `requestAnimationFrame` runs between a person's two presses and
between none of a test's, so a fault that the repaint itself causes is invisible to
exactly the rhythm a suite presses at — and reads as correct rather than as flaky.

`renderLine` runs under `paintHere`'s frame and cleared the key line with
`textContent = ""` before putting its More button back. That takes a focused element
out of the document, which blurs it, so a reader who tabbed to More was dropped to
`body` a frame later with the button back on the line looking untouched. Pressed back
to back the walk was whole; at every human speed it was broken, and the button was
never gone to look at nor gone from the DOM to assert on.

So a walk, or any repeated press a repaint could answer, waits a frame between presses
and says why. Where waiting is what changes the outcome, the contrast is the assertion
rather than a threshold: `test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted`
runs one walk both ways and holds the two to being the same walk. A count of lost stops
has no honest threshold, because a page whose tab order is three controls and a wrap
puts the reader on `body` every fourth press as a matter of course.

## Distinguish a frame, a sequence, and an instant

Most visual behavior can be tested from stable states before and after a gesture. The
test must cross the transition that could reveal the fault. Geometry measured twice
within one final state proves nothing about motion between those reads.

A frame is one held state. `HOLD_MOTION` pauses animations so a short-lived midpoint
can remain available while Playwright inspects it. Step or release every held animation
after the assertion so completion handlers run and teardown is not left waiting on a
promise that cannot settle.

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
that moves on its second application.

The canonical probes are `leaf_interact.render_checks.UNDECLARED_ATTRS` for attributes a module writes
into the author's namespace without a record declaration, and
`leaf_interact.render_checks.RELATIVE_REPLAYS` for an action whose second application changes state.
Call the product probes instead of maintaining test-side variants. Their fixtures
must include at least one widget and verb that can trigger the finding; otherwise a
clean result only says the probe received an empty population.

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
