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

The repository guide owns setup and the everyday and complete-suite commands.
During development, select the owning file or one named case. Both browser modules
are marked at module scope, so include `--run-nightly`; use `-n 0` while debugging
so the trace and process tree stay local. Before landing a browser-facing change,
run its complete browser file and the repository's normal suite.

## Put each assertion at the boundary that owns it

`test_interact.py` exercises authored markup, the registry, the event log, CLI
commands, vendoring, publishing, export, and server lifetime. `test_render.py`
drives the browser runtime and the render gate. `test_site.py` reads the built site
through its served URLs. Product documentation tests compare the docs with the
shipped vocabulary and command surface.

The distinction matters most around `render_version`. A property caused by a
particular page belongs in that gate, because `version check --render` must report
it to the page's author. A property that is identical for every valid page belongs
in the suite instead. `arrival_findings`, for example, tests the layer's behavior
when a reader returns with browser state already present; changing the authored
page cannot repair that behavior.

Prefer the public route through the product. A CLI test should invoke the command
or the same command function used by the entry point. A browser test should serve a
vendored page and use its HTTP API. A render-gate test should call
`interact.render_version`, not reproduce one of its probes. Test a helper directly
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
`test_interact.py` owns command-level files without starting a browser. Keeping
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
`pageerror`, and installs `interact.WINDOW_ERRORS` so browser `error` events without
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

Read the event log only after `round_trip`. Polling the file until one expected event
appears can miss an extra send, and it cannot distinguish an unresolved request from
a settled one. Read browser state after the trip when the returned state is part of
the assertion. `round_trip` proves delivery; it does not claim every rendered effect
of the response has completed.

After changing a file behind a live page, call `told` before reading the page. Letting
`expect` absorb the next polling interval hides which mechanism supplied the wait and
spends its timeout budget on transport rather than on the assertion.

For layout, animation, and navigation, identify the final fact precisely.
`panel_settled` waits for the requested panel class and then for the body's finite
animations to empty. `resized` waits for the resize event to reach listeners; a new
viewport size says only that the browser resized, not that page layout handled it.
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

The canonical probes are `interact.UNDECLARED_ATTRS` for attributes a module writes
into the author's namespace without a record declaration, and
`interact.RELATIVE_REPLAYS` for an action whose second application changes state.
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
