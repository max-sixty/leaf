# The tests

Each of these norms was learned by getting it wrong, and most of the failures
were a test that passed while proving nothing.

## They are integration tests in a real browser

`test_render.py` drives the shipped examples through Playwright's pinned Chromium
headless shell. Assert what a static lint can't reach. Use real mouse input
(`page.mouse`, `locator.click()`) when the gesture is the point: a
synthetic `dispatchEvent(new MouseEvent("click"))` skips the mousedown, and the
runtime is built around what happens on mousedown, so the synthetic click sails
past a whole class of bug. Assert the outcome with `expect(...)`, never a bare
`is_hidden()` or `count()`: every gesture that sends is a round trip, and a plain
read taken right after one passes on a fast run and fails on a slow one — which
is worse than failing outright.

A render invariant belongs in `render_version`, not in a test. That function is
what `version check --render` runs at handover, and `test_example_renders` drives
it over the examples, so the gate a user's page passes and the suite the examples
pass share one implementation. The end-to-end render-check tests cover its installed
Chrome launch path separately.

Which of the two a reading belongs to follows from whose fault its findings are.
The gate reads a version, and everything it reports is something the page's
author wrote and can change. A reading whose answer is the same under every
version is about the layer instead, and an agent running the gate at handover
would be paying for a verdict on code it neither wrote nor can fix. That reading
lives here, swept over the corpus like any other. `arrival_findings` is the one
that does: what a page does for a reader who left the comment panel open or a
board standing is the restore's answer, and no markup changes it.

## A synthetic drag presses on a whole pixel

`select` is the helper a test drags a selection with, and the reason it exists is
that it floors the press coordinates to whole pixels. Start a drag on a
fractional point and the selection can be lost outright: wherever the point and
its floor fall on opposite sides of a glyph's caret boundary, the drag runs, the
mouseup lands, and `getSelection()` comes back empty. Coordinates out of
`bounding_box()` and range rects are fractional, so any drag written by hand can
hit this. The failure reads as the widget under the pointer refusing the gesture,
and it is neither that nor Playwright's interpolation — plain prose in a bare
document does it.

## The everyday run opens one browser

`test_render.py` and `test_site.py` carry a module-wide `pytest.mark.nightly`, which
`tests/conftest.py` deselects unless `--run-nightly` is passed. The everyday run covers
the static lint, server, vendoring, and product pages, plus one `ship-review` render
through the real gate. Its worker is the only one that launches Chromium. Which run to
reach for when is under "The suite" in the repo's CLAUDE.md.

The suite browser is the headless shell that matches the Playwright version in
`uv.lock`, and the page it opens is on disk. Two tests also drive `bin/leaf` on a
subcommand that opens installed Chrome. The launcher supplies Playwright to those
subcommands from outside the script's lock (`uv run --with playwright`), and an
unlocked requirement has no recorded resolution to install from, so uv asks pypi for
one every time its cached answer goes stale. Those tests therefore need the network
available to the nightly run.

To prove a run works offline, give uv an index that isn't there —
`UV_FROZEN=1 UV_DEFAULT_INDEX=http://127.0.0.1:1/simple`. The index URL is also
the key uv caches under, so pointing it at a dead URL means nothing already
fetched can answer in its place; `UV_FROZEN` keeps that same dead URL from
re-resolving `uv.lock`. Blocking the route instead — say, a dead `HTTPS_PROXY` —
leaves the cache key alone, so an entry still inside pypi's ten-minute cache
header answers without asking, and the run passes though it was never offline.

## A process the suite starts ends with the run

No cleanup the suite itself runs can be the guarantee. A page's server is spawned
into a session of its own — that is what lets it outlive the command that starts
it — so when a run is killed, neither a `finally` block nor the process is
reached, and the server stays behind, serving a pytest tmp directory until the
machine restarts. Three were doing exactly that when these fixtures were written,
the oldest four hours old. And the kills were not out of the blue: a wait ends on
a comment or on the leaf ending, the helper that was to post that comment gave up
after ten seconds, and `cmd_wait` then held until somebody killed the run.
Whatever a test arranges in order to end a blocking call has to end it on the
failing path too, or the failure arrives as a hang.

Only leaf's own reaper reaches such a process: a claimed page's server stops once
the claimant pid is gone. So the run claims its pages as a session of its own,
keyed to the worker's pid (`isolated_session`), and a server any test causes leaf
to spawn goes down when its worker does, killed or not. That is also why a test
about a command run from outside a host session has to say so explicitly —
`sessionless`, or `codex_env` for one run under Codex — rather than relying on
there being no session identity around.

The fixtures then handle the ordinary end of a test: `_no_page_outlives_its_test`
stops any page still being served, and `spawn` ends a process the test started
itself. A new test wants those rather than a `finally`, which runs on a failure
but not on a kill. The sweep searches for pages rather than reading a list the
tests append to, because the serve nobody remembered is the one it is there for.

A standing serve declines the claim, so it has no reaper at all — and in the
tests that cover standing serves, that is the arrangement under test, not a gap
in the fixtures. Those tests are the one place a killed run can still strand a
server; they hold one up for a second or two and stop it as they end.

## A round trip is not over when its response lands

The runtime answers a post by polling, so what the page does about a send arrives
with the next poll, not with the post's own response. The press sweep learned
this the expensive way: its two "matching" frames read the page from before the
press had any effect, and the sweep caught its own regression on about half of
the runs written to prove it caught it. Watch the trip rather than timing it. A
hold sized to `POLL_MS` states a number the runtime is free to change, still
guesses on a loaded machine, and charges every press two seconds for a trip
that takes ten milliseconds. `wait_for_load_state("networkidle")` is not the wait
either: with no navigation to answer for, it returns at once.

Watch the trip from outside the page. `Traffic` counts the browser's own
`request`, `response` and `requestfailed` events — the same five numbers used to
come from an init script wrapping `window.fetch` on every page of every run,
which was permanent surgery on the runtime under test to learn what the browser
was already saying. `open_page` hangs that watcher on every page it opens,
because a test that had to ask for the counter first is, in practice, a test that
asserted straight through the trip instead. `round_trip(page)` waits for the
page's own sends to come back, and that is the wait to take before reading the
event log: a widget settles a decision in front of the user before the server has
taken it, so the page looking done is not the log holding the event. Polling the
log instead only ever asks after the send the test names — a stray send, from a
widget that was supposed to stay quiet, passes straight through such a poll.

A file the test writes is the same trip run the other way, and there `expect`'s
own timeout becomes the hold in disguise. A declared status, a changed wait lease,
an appended event: none of them announce themselves, so the page learns of each
when its next poll asks. An assertion made straight after the write therefore
spends a whole poll interval out of whatever budget `expect` was given — 1.8 to
2.3 seconds of the default five, measured, and every time. `told(page)` watches
that wait instead. And a wait's own timeout is the net under a hang, not a budget
for the work, so once the wait is right, the number is left alone.

## A wait consumes a fact the system states

A page that has not started moving is as still as one that finished. So a wait
that infers completion from stillness — two frames agreeing, a stretch with no
change — returns early exactly when the machine is loaded enough to fit its first
samples in ahead of the effect. `panel_settled` once "settled" that way on a
transition that had not begun: a transition's first ticked frame still computes
its start value, so the sample taken at injection and the one on the next frame
both read the margin the page already had.

So a wait asks for a fact the system declares: an element existing,
`document.body.getAnimations()` emptying, a request coming back, a resize
reaching its listeners. Where stillness is itself the assertion, an observed edge
comes first — the press sweep measures "nothing moved" only after `round_trip`
has watched the response land. Its geometry then crosses one rendered frame,
waits for finite animations to end, and crosses the ending frame. An elapsed
quiet window cannot stand for that sequence: under parallel load, one animation
frame can take the whole window, so a predicate returns before that frame's
layout paints. A timing flake can be reproduced by emulating the poller's own
schedule in the page: `wait_for_function` runs its predicate once at injection
and then once per animation frame, which turns the failure into a rate to measure
rather than a rerun to hope for.

An edge is not the same fact as arrival, and a gesture that moves the page twice
is where the two come apart. Clicking a quote scrolls instantly to bring the
passage's box on screen, then smoothly to centre the painted range, and
`scrollend` fires for each of the two scrolls — so the first `scrollend` is a
genuine statement from the browser, and it is 232 pixels short of where the click
was aimed. The fact worth waiting on is the destination itself: the mark reaching
the middle, which is the position `scrollToThread` computed. A glide approaching
that position passes through no earlier position that could be mistaken for it.

A destination stated as a region rather than a position is the same mistake in a
weaker disguise. "Some part of the change is inside the window" is as true where
the walk starts as where it is going, and the ask the boxless-travel test walks
to sits a few dozen pixels below the fold — so the predicate went true on the
focus move that precedes the glide, and the test passed with the travel bug put
back. It had been passing that way under the suite's own parallel run while
failing the same bug when run alone, which is the shape of a test measuring the
machine's load rather than the product's behaviour: the reading it took was
whichever transient it was quick enough to catch. The scroll stopping is the
fact to wait on; where it stopped is the assertion.

Where nothing will happen, there is no fact to consume and polling has no end. An
assertion of absence holds a window instead, and the window's length is derived
from the mechanism rather than picked: a manually launched server must outlive
the grace period after which a session watcher would have shut it down, so that
window is `ORPHAN_GRACE_SECS` plus room to act. A window too short fails the
opposite way from everything above — it passes vacuously rather than flaking —
which is why nearly every absence assertion here holds no window at all,
asserting straight after the edge that proves the gesture was handled.

## A state the page passes through is not a state to poll for

`expect` re-asks until the page matches, so what it reports is the first frame
that matched — never the frame the gesture settled on. Where the page passes
through the asserted state on its way somewhere else, the assertion is a gate
that passes whichever way the gesture was going to go. Every mousedown clears the
comment button before its own mouseup decides it again (`standDown`), so the key
line reads "comment on the page" in the middle of every drag — and a check that
the runtime refused a drag over chrome passed identically on a drag it accepted.

What to read instead is the mechanism's own last step — the section above,
applied where the fact is a settled state rather than an arrival. The button is
decided on a `setTimeout` queued from the mouseup, and the key line repaints on
the frame after that. So a timeout the test queues once the drag has returned
runs behind the runtime's timeout, and one frame behind that is the answer this
drag actually left. Consume the step, then read once.

## Nothing of the suite runs inside the page

The tests drive the runtime; they do not join it. What the suite knows about a
page's traffic, it gets from the browser — `request`, `response` and
`requestfailed` to watch, `page.route` to stop or delay a request — and a page
that a product path opens for itself is reached the same way, through `primed`.
Nothing is injected into the page to make a wait possible, so what the tests
exercise is the runtime a user gets, not one wearing the suite's hooks.

That was not always so, and what was removed is worth knowing about whenever a
wait looks unnecessary. An init script once wrapped `window.fetch` to count
trips, and `LEAF_TEST_LOAD=1` added a second wrapper that held each `/api/state`
answer back three and a half seconds, alongside a CPU throttle slowing the page's
own JS twentyfold. Two tests had gone red on an ordinary busy run, and that
slowed-down sweep found seven more standing on the same margin — `resized` and
`open_page`'s upgrade-stamp wait among them, since `set_viewport_size` returns on
a fact about the browser rather than about the page. The waits found that way
still stand; the instrument is gone. So a wait that is missing today passes on
every machine quick enough to hide the gap, and the next fault of that shape
arrives by luck, on a genuinely busy machine, rather than on demand.

The luck came, and it found the front door. `open_page` waited for the document's
stamp and not the log's, so the page it handed over had heard nothing the
log says. Network quiet happened to close that gap on this machine; a dockerised
Linux runner did not, and three tests lost a keypress into a page that had
nothing yet to answer it. All three were presses, because a press is the read
with no second chance — `expect` re-asks for five seconds, but a keystroke is
simply gone. So navigation waits for the load event, which says the resources
shaping the page have arrived, and `open_page` waits for `lf-applied`, which says
the log has — two stated facts replacing a quiet window for state readiness.

## A race this machine won't lose is stated rather than run for

Two picks a moment apart reached the log in reversed order on a CI runner,
twice — and neither this machine nor `scripts/linux-suite.sh` reproduced it in
two dozen runs. The race window is one request's flight, and a machine quick
enough closes it before the next click. Running the race again is a rate to hope
for, not a gate.

`page.route` holds the window open instead. A route handler that keeps the route
and returns leaves that request in the wire — the server has not taken it and
cannot — so the gesture made after it happens under exactly the condition the
runner supplied, and `route.continue_()` releases the request later. What the
hold buys is a fact the page states on every run rather than only on a loaded
one: if the send queue were gone, the second gesture's request would go out over
the held first, and `Traffic.sends` says whether it did before anything has to be
timed. The outcome asserted after the release is not the gate —
`test_a_send_waits_for_the_send_before_it` does read the log's order too, but
that order is the coin the runner tossed.

Releasing the hold is the handler's job too, wherever the hold exists to order
something. Reaching for `held[0]` from outside the handler reaches for a request
that may not have been made yet: the suggestion module is fetched behind the
registry's own round trip, while the room the layout states needs no network at
all — so a loaded runner laid the page out with the request still to come, and
the reach was an `IndexError` rather than a failure with a name. A handler that
waits for the fact the hold is about and then continues states the ordering
whenever the request happens to arrive
(`test_the_room_is_measured_after_a_late_rail`). Where the release is
unconditional instead, `Traffic` counting the request out is what precedes the
reach.

A refusal states the other timing a busy machine supplies. Where the send race
needs one request held in the wire, a page that has not yet heard the log needs
its first `/api/state` stopped, so that replay lands on the 2s retry — after the
upgrade stamp (`test_a_page_the_suite_opens_has_read_the_log`). Refusals are
cheap enough to
run over the whole suite, and that is worth doing when the fix is at the front
door rather than in one test: refuse the first poll of every page `open_page`
makes, throw the change away afterwards, and the suite says how far the fault
reached. Twenty-two tests failed without the log's stamp waited for and passed
with it, where the CI runner had named three. The front door was not the only
door, either: `open_page` grew the log's stamp while the nine other places where
a test navigates for itself did not, each spelling the wait predicate out by
hand — which is what one shared `BOTH_STAMPS` is now for.

## A test cannot assert over noise it makes itself

`page.route` stops a request from outside the page, but what the browser then
says about that request comes back to the test in the same list its own
assertions read. A poll refused with `route.abort()`'s default reason counts as a
failed load, and Chrome writes "Failed to load resource: net::ERR_FAILED" to the
console for it — which `open_page` collects, where it sits indistinguishable from
the page having actually broken. How many of those entries a test reads back is
then the machine's answer, not the test's: a run that reaches its last assertion
inside one 2s poll interval refuses nothing, while a loaded run refuses a poll
per tick and hears about each one in time to fail on it. So the test written to
instrument a slow machine was the one that failed on a slow machine — blaming the
runtime for its own instrument.

`refuse` cancels the request instead, and the console has nothing to say about a
cancellation — so `errors == []` means what it looks like it means, however many
polls a run refuses. Where the failed request is the subject rather than the
instrument — a send the server never takes — the plain abort stays, and the
console entry it leaves is asserted on.

## A sequence and an instant are the readings the suite cannot take from outside

A motion is the first. Both ways of reading a motion from outside the page read
states: a held frame (`HOLD_MOTION`) is one state, stopped where the assertions
can reach it, and a geometry read before-and-after is two states. Each frame can
be right on its own while the sequence they belong to is wrong, and that gap has
exactly one shape — a frame that puts back what the frames before it took away.

That shape is reachable, not hypothetical, because a Web Animations effect stops
applying at the end of its own interval. Between that instant and whatever the
`finished` handler does, the element is its unanimated self again — full height,
full opacity. Today the removal wins that race, in a microtask ahead of the
paint; nothing in the code says so, and one frame's slip is the whole of the
distance between a fold and a fold that flashes the thread back at full size
before it goes. So the fold is watched frame by frame at real speed
(`test_the_fold_never_paints_a_frame_that_undoes_the_last`), and that is the one
check here that samples from inside the page: what painted, and in what order, is
not a fact the browser reports to the outside. The wait is still not the
sampler's — the node leaving the list is the browser's own statement — so what
the injection buys is the record, not the wait.

A recording of a motion owes the same reading. The frames of the first GIF of
this fold were stepped by `currentTime`, and one was taken at exactly the
duration — already past the animation's own interval — so it recorded the thread
springing back to full size, a frame the product never paints. Every still was
correct, the sequence was a lie, and nothing between the frames and the reader
had looked at them in order.

The other reading is an instant. A reading taken through the browser is a round
trip, and the rendering step the page was in does not wait for it. The room a
wide widget spends is restated and the page stamped done in the same block, and
the layout observer restates the room again on the very next frame whatever that
block did — so a page read any time after the stamp is right either way, and the
test written to hold that line kept passing with the line deleted. A
`MutationObserver` on the stamp runs a microtask after the stamp's own write,
ahead of that next frame, and that is where the reading is taken now
(`test_the_room_is_measured_after_a_late_rail`). The injection buys the record
again; the wait is still the stamp's.

Holding a motion holds whatever its ending drives, and that is the way past a
window too short to drive from outside. The record of a folding thread lives until
`finished` settles, and a paused animation never settles it, so the 220ms a reader
has to reopen a thread mid-fold becomes a state that lasts as long as the
assertions need — which is what
`test_a_thread_reopened_mid_fold_folds_again_when_it_settles` reads, and it steps
the held fold to its end afterwards to read what that ending clears. What the suite
could not drive was the timing; the states either side of it were in reach the whole
time. So before writing a race off as untestable, ask which of its ends can be
stopped.

## A page's source is formatted, so ask what it says

Prettier formats the `.html` under `docs/` and `examples/`, and it re-derives
every line break in a paragraph — it moved half of the corpus's, measured. So a
sentence asserted as a raw substring of a file is a sentence that fails the day
it gets one word longer, somewhere else in the paragraph. Collapse whitespace
before matching, which is what a test about what a page *says* meant anyway; the
page's own reading (`spoken`) gives the same answer where a test already has a
registry to hand.

Markup follows the same rule for the same reason. A whole tag written out as a
literal encodes a formatter's opinion about attribute order and line breaks:
prettier writes a void element as `<link … />` and splits a long one over four
lines. Match the attribute that carries the meaning, or a pattern that admits any
tag around it. What made this expensive once was a literal that lived in
`scripts/site.py` rather than in a test. It silently stopped matching, a generic
path rule took the stylesheet href instead, and every published page linked a
GitHub source view in place of its CSS. The link resolved, so the build's
dead-link check said nothing; what noticed was a palette test reading colours off
the rendered page.

## A sweep that walks controls by index must prove it pressed them

A control list read before the runtime injects its banner is a short list, and a
short list skips silently rather than failing — the vacuous pass, wearing the
same green as the real one. Pin the count of controls across reloads. And check a
new gate by putting each bug back and watching the gate fail: a gate that has
only ever passed has been tested for nothing.

## A test goes vacuous when the code stops being able to fail it

The bug-back above is written for a new gate; the expensive case is an old one. A
test asserts a bound, the code later changes so the bound cannot be crossed, and
the assertion keeps passing while the fault it was named for moves somewhere the
test is no longer looking. Nothing turns red on the way through.

Two tests here went vacuous at once. Both measured a wide widget against the
right edge of the page's box, which was where an over-wide room used to spend
itself. Then the right margin became claimed by whatever stands in it, so the
widget could only ever grow leftward — the assertion became true by construction,
and the same faults sailed through both tests. A room read too wide now runs off
the *left* of the window, which is the worse direction: leftward overflow scrolls
nothing in a left-to-right page, so what went past that edge is gone rather than
merely out of view. A change that alters which way a fault can point owes its
existing tests a bug-back, not only its new ones — and the question to put to
each test is which edge the fault lands on now.

A gate can also be born vacuous, when a layer below it already prevents what the
assertion names. `post` sends one action at a time, so a second gesture made
while the first is held in the wire never reaches `page.route`: counting the held
requests reads one whether or not the widget refuses that second press, and an
assertion saying a press in flight had sent a second one could never have failed
for the reason it gave. What the second press would leave is a line in the log
once the queue drains, which is where a gate on it reads. Before asserting that a
gesture did not travel, ask what would have stopped it anyway.

## An assertion that nothing moved must straddle the change that could move it

A geometry assertion is worth only as much as the transition it is measured
across, and the transition that comes to hand is often one that cannot move
anything, whatever the rule says. Room reserved for a pick mark is the case that
taught this. Moving a pick from one card to another gives the reserved strip back
exactly as fast as it takes it, so "the card is the same box after the pick as
before it" held perfectly with the reservation deleted — and the gate written to
catch that deletion passed with the bug in. Clearing the pick first is what makes
the room actually go missing: the assertion has to run from a group holding no
answer to a group holding one, not from one answer to another.

So before writing "nothing moved", ask what would move if the rule were gone, and
put the test across that transition. It is the same question
`page.emulate_media` asks in its own register, and it is the question the
bug-back check above answers for you when the measurement is too clever to reason
about.

## A captured stream nothing reads is a failure that names nothing

`check=True` on top of `capture_output=True` raises a `CalledProcessError` naming
the command and the exit status, while the streams it captured — the only account
of what actually went wrong — die with it, because nothing prints them. The demo
recording failed that way three times in one stress run, and the cause stayed
unconfirmable until the streams came back: two runs were sharing a page
directory, and the traceback that said so had been sitting in `e.stderr` the
whole time. Pytest already captures a child process's output and prints it under
the failure. So capture output in the test only where something reads it — and
where something does, assert the exit status yourself, with both streams in the
assertion message.

A wait that runs out is the same silence, and it is the expensive one.
`round_trip` used to report only the event Playwright had blocked on and nothing
about the page — three times on CI, for a fault its own counters named exactly: a
post that a reload kills mid-flight ends in neither a response nor a
`requestfailed`, so `acked` sat one under `sends` for the rest of that page's
life and every wait after it ran its timeout out. `_until` now carries the
counters from both ends of the wait into the failure message, which is what tells
"one fact stuck while polls keep arriving" from "a page that has stopped talking
at all".

## An error channel nothing reads is a page that passes while reporting a fault

Two channels carried what a page said had gone wrong — `pageerror` for an
uncaught exception, and the console for what the page wrote itself — and a third
channel went unread between them. A window `error` event with no exception behind
it reaches neither, and it is not an exotic case: Chrome reports a ResizeObserver
loop that way. So a page could say, on every single load, that a piece of its
layout was not being delivered — with the whole suite green. A runtime change
that put the layout's own writer inside an observation of the box that writer
resizes did exactly that, and 754 tests had nothing to say about it. Found by
hand, it turned 77 of the 112 render tests it was first put to red the moment the
channel was read. `interact.WINDOW_ERRORS` is what reads the channel now — one
string owned by the product, laid into the page by `watched` here and by
`render_version` there, because a channel read on one side only is the drift
between the suite and `version check --render` in its quietest form. It routes
those events into the console, which every reader already collects, and takes
only the events with no exception behind them, since the rest arrive on
`pageerror` already and one fault should not become two strings.

What is worth keeping from this is that the fault was in the runtime while the
blindness was in the suite. A channel the tests do not read is not a quiet
channel — it is a channel whose contents become someone else's problem, and the
someone else is the reader of the page.

One message on that channel needs a second reading. Chrome can report a
ResizeObserver loop once, under load, on a page whose layout is delivered
whole — while the feedback loop that opened this channel reported it on every
load. A second complete attempt tells the two apart. `render_version` repeats
both schemes and every probe, print included, because confirming only the
navigation would declare a notice raised by a later reading permanent without
ever reading again. `navigate` makes the same distinction for the suite's
ordinary page handover, and only for errors raised inside that handover.
`watched` still records every notice, so a notice raised by a later gesture, or
by a test that drives its own navigation, remains a failure rather than
disappearing into a global filter. Ordinary errors survive both readings, and a
confirmation that does not complete pardons nothing.

## Reloading is not resetting

The panel's open state and every unsent draft live in `localStorage`, and the
reading position lives in `sessionStorage` — all deliberately, so a fresh `goto`
restores the state the last gesture left. Clear both stores where a test means
the page as published: an open panel crowds the banner enough to absorb a
shrinking button, and that alone once decided whether a real regression
reproduced.

A second page is not a second reader unless it is a second context — and for
drafts the trap runs the other way: `Browser.new_page` opens each page in a
context of its own, so two such pages share no storage, and nothing about a draft
reaching another tab can be seen from them. `one_reader` is one context that two
pages open in, which is what makes them tabs.
