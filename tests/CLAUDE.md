# The tests

Each of these was learned by getting it wrong, and most of the failures were a test that
passed while proving nothing.

## They are integration tests in a real browser

`test_render.py` drives the shipped examples through Chrome (`channel="chrome"`, so no
download). Assert what a static lint can't reach. A synthetic
`dispatchEvent(new MouseEvent("click"))` skips the mousedown and so sails straight past a
whole class of bug the runtime is built around — use real mouse input (`page.mouse`,
`locator.click()`) when the gesture is the point. Assert the outcome with `expect(...)`,
never a bare `is_hidden()` or `count()`: every gesture that sends is a round trip, and a
plain read taken right after one passes on a fast run and fails on a slow one, which is
worse than failing outright.

A render invariant belongs in `render_version` rather than in a test. That function is
what `version check --render` runs at handover, and `test_example_renders` drives it over
the examples, so the gate a user's page passes and the suite the examples pass are one
implementation and cannot drift.

## A synthetic drag presses on a whole pixel

`select` is how a test drags a selection, and the floor it takes on the press is what it is
for: a fractional start point loses the selection outright wherever it and its own floor
fall either side of a glyph's caret boundary — the drag runs, the mouseup lands,
`getSelection()` is empty. Coordinates out of `bounding_box()` and range rects are
fractional, so any drag written by hand can reach it. It reads as the widget under the
pointer refusing the gesture, and it is neither that nor Playwright's interpolation: plain
prose in a bare document does it.

## The everyday run asks nothing of the network

The browser is the machine's own and the page it opens is on disk, so the suite needs nothing of the network —
except where a test drives `bin/leaf` on a subcommand that opens Chrome. The launcher supplies Playwright to
those from outside the script's lock (`uv run --with playwright`), and an unlocked requirement has no recorded
resolution to install from, so uv asks pypi for one every time its cached answer has gone stale. With pypi
unreachable the tests that run the shim's own `--render` or `version export` fail on its exit status, and a suite
of six hundred passing browser tests reports as broken. Those carry `pytest.mark.nightly` and an everyday run
skips them; CI and `wt merge` pass `--run-nightly`. A new test that shells out to the launcher's browser path
wants the mark too.

Prove a run offline by giving uv an index that isn't there —
`UV_FROZEN=1 UV_DEFAULT_INDEX=http://127.0.0.1:1/simple`. The dead URL is also the key uv caches under, so nothing
already fetched can answer in its place, and `UV_FROZEN` keeps that same dead URL from re-resolving `uv.lock`.
Blocking the route instead — a dead `HTTPS_PROXY` — leaves the key alone, so an entry still inside pypi's
ten-minute cache header answers without asking and the run passes though it was never offline.

## A round trip is not over when its response lands

The runtime answers a post by polling, so what the page does about a send arrives with that
poll rather than with the post. The press sweep learned this the expensive way: two matching
frames read the page from before the press had an effect, and it caught its own regression on
about half of the runs written to prove it caught it. Watch the trip rather than timing it. A
hold sized to `POLL_MS` states a number the runtime is free to change, still guesses on a loaded
machine, and charges every press two seconds for a trip that takes ten milliseconds;
`wait_for_load_state("networkidle")` is not the wait either, since with no navigation to answer
for it returns at once.

Watch it from outside the page. `Traffic` counts on the browser's own `request`, `response` and
`requestfailed` events, where the same five numbers used to come from an init script wrapping
`window.fetch` on every page of every run — permanent surgery on the runtime under test to learn
what the browser was already saying. `open_page` hangs that watcher on every page, since a test
that had to ask for the counter first is a test that asserted straight through the trip instead.
`round_trip(page)` is the page's own sends coming back, which is what to wait on before reading
the event log: a widget settles a decision in front of the user before the server has taken it, so
the page reading done is not the log holding it. Polling the log instead only ever asks after the
send it names, and a stray one from the widget that was supposed to stay quiet passes through it.

A file the test writes is the same trip the other way round, and `expect`'s own timeout is the hold
in disguise. A declared status, a bumped heartbeat, an appended event: none announce themselves, so
the page learns of each when its next poll asks, and an assertion made straight after the write
spends a whole poll interval of whatever budget `expect` was given — 1.8 to 2.3 of the default five,
measured, and every time. `told(page)` is that wait watched instead. A wait's own timeout is the net
under a hang rather than a budget for the work, so once the wait is right the number is left alone.

## A wait consumes a fact the system states

A page that has not started moving is as still as one that finished, so a wait that infers completion
from stillness — two frames agreeing, a stretch with no change — returns early exactly when the machine
is loaded enough to fit its first samples in ahead of the effect. `panel_settled` settled that way on a
transition that had not begun: a transition's first ticked frame still computes its start value, so the
sample at injection and the one on the next frame both read the margin the page already had.

So a wait asks for what the system declares — an element existing, `document.body.getAnimations()`
emptying, a request coming back, a resize reaching its listeners. Where stillness is itself the
assertion, an observed edge precedes it: the press sweep measures "nothing moved" only after
`round_trip` has watched the response land. And a timing flake reproduces by emulating the poller's own
schedule in the page — `wait_for_function` runs its predicate once at injection, then once per animation
frame — which makes the failure a rate to measure rather than a rerun to hope for.

An edge is not the same fact as arrival, and a gesture that moves the page twice is where they come
apart. Clicking a quote scrolls instantly to bring the passage's box on screen, then smoothly to centre
the painted range, and `scrollend` fires for each: the first is a statement the browser makes, and it is
232 pixels short of where the click was aimed. The fact worth waiting on is the destination — the mark
reaching the middle, which is what `scrollToThread` computed — because a glide that approaches it passes
through no earlier position that could be mistaken for it.

Where nothing will happen there is nothing to consume, and polling has no end. An absence holds a window
instead, its length derived from the mechanism rather than picked: a manually launched server must
outlive the grace a session watcher would have shut it down after, so the window is `ORPHAN_GRACE_SECS`
plus room to act. A window too short fails the other way round from everything above — it passes
vacuously rather than flaking — which is why nearly every absence here holds none at all, asserting
straight after the edge that proves the gesture was handled.

## A state the page passes through is not a state to poll for

`expect` re-asks until the page matches, so what it reports is the first frame that matched and never
the frame the gesture settled on. Where the page transits the asserted state on its way somewhere else,
that is a gate which passes whichever way the gesture was going to go. Every mousedown clears the
comment button before its own mouseup decides it again (`standDown`), so the key line reads "comment on
the page" in the middle of every drag — and a check that the runtime refused a drag over chrome passed
identically on a drag it accepted.

What to read instead is the mechanism's own last step, which is the section above applied where the fact
is a settled state rather than an arrival. The button is decided on a `setTimeout` queued from the
mouseup and the line repaints on the frame after that, so a timeout queued once the drag has returned
runs behind the runtime's, and one frame behind that is the answer this drag left. Consume the step,
then read once.

## Nothing of the suite runs inside the page

The tests drive the runtime; they do not join it. What the suite knows about a page's traffic it gets
from the browser — `request`, `response` and `requestfailed` to watch, `page.route` to stop or delay —
and a page that a product path opens for itself is reached the same way, through `primed`. Nothing is
injected to make a wait possible, so what the tests exercise is the runtime a user gets rather than one
wearing the suite's hooks.

That was not always so, and what went is worth knowing when a wait looks unnecessary. An init script
wrapped `window.fetch` to count trips, and `LEAF_TEST_LOAD=1` added a second wrapper holding each
`/api/state` answer back three and a half seconds, alongside a CPU throttle slowing the page's own JS
twentyfold. Two tests had gone red on an ordinary busy run and that sweep found seven more standing on
the same margin — `resized` and `open_page`'s upgrade-stamp wait among them, since `set_viewport_size`
returns on a fact about the browser rather than about the page. The waits stand; the instrument is gone.
So a wait that is missing now passes on every machine quick enough to hide it, and the next fault of that
shape arrives by luck on a genuinely busy one rather than on demand.

The luck came, and it found the front door. `open_page` waited for the document's stamp and not the log's,
so the page it handed over had heard nothing the log says. This machine closes that gap inside
`networkidle`; a dockerised Linux runner did not, and three tests lost a keypress into a page with nothing
yet to answer it. All three were presses, since a press is the read with no second chance — `expect`
re-asks for five seconds, a keystroke is gone. So `open_page` waits for `lf-applied` as well.

## A race this machine won't lose is stated rather than run for

Two picks a moment apart reached the log reversed on a CI runner, twice, and neither this machine nor
`scripts/linux-suite.sh` reproduced it in two dozen runs: the window is one request's flight, and a machine
quick enough closes it before the next click. Running for it again is a rate to hope for, not a gate.

`page.route` holds the window open instead. A handler that keeps its route and returns leaves that request
in the wire — the server has not taken it and cannot — so the gesture after it is made under exactly the
condition the runner supplied, and `route.continue_()` later releases it. What that buys is a fact the page
states on every run rather than on a loaded one: with the send queue gone, the second gesture's request goes
out over the held first, and `Traffic.sends` says so before anything has to be timed. The outcome asserted
after the release is not the gate — `test_a_send_waits_for_the_send_before_it` reads the log's order too,
but that order is the coin the runner tossed.

Releasing the hold is the handler's too, wherever the hold is there to order something. `held[0]` from out
here reaches for a request that may not have been made: the suggestion module is asked for behind the
registry's own round trip while the room the layout states needs no network at all, so a loaded runner laid
the page out with the request still to come and the reach was an `IndexError` rather than a failure with a
name. A handler that waits for the fact the hold is about and then continues states the ordering whenever the
request arrives (`test_the_room_is_measured_after_a_late_rail`). Where the release is unconditional instead,
what precedes the reach is `Traffic` counting the request out.

A refusal states the other timing a busy machine supplies: where the send race needs one request held in the
wire, a page that has not heard the log needs the first `/api/state` stopped, so replay lands on the 2s retry
past both the upgrade stamp and networkidle (`test_a_page_the_suite_opens_has_read_the_log`). Refusals are
cheap enough to run over everything, which is worth doing when the fix is at the front door rather than in
one test: refuse the first poll of every page `open_page` makes, throw it away afterwards, and the suite says
how far the fault reached — twenty-two tests failed without the log's stamp waited for and passed with it,
where the runner had named three. The front door was not the only door, either: `open_page` grew the log's
stamp and the nine other places a test navigates for itself did not, each having the predicate spelled out by
hand, which is what one `BOTH_STAMPS` is now for.

## A test cannot assert over noise it makes itself

`page.route` stops a request from outside the page, and what the browser then says about that request
comes back to the test in the same list its own assertions read. A poll refused with `route.abort()`'s
default reason is a failed load, and Chrome writes "Failed to load resource: net::ERR_FAILED" to the
console for it — which `open_page` collects, where it sits indistinguishable from the page having broken.
How many of those entries a test reads back is then the machine's answer rather than its own: a run that
reaches its last assertion inside a 2s poll interval refuses nothing, while a loaded run refuses a poll
per tick and hears about each in time to fail on it. So the test written to instrument a slow machine was
the one that failed on a slow machine, naming the runtime for its own instrument.

`refuse` cancels the request instead, which the console has nothing to say about, so `errors == []` says
what it looks like it says however many polls a run refuses. Where the failed request is the subject
rather than the instrument — a send the server never takes — the abort stays plain and the entry it
leaves is asserted.

## A sequence and an instant are the readings out here cannot take

A motion is the first, and both ways of reading one from outside read states. A held frame (`HOLD_MOTION`) is one state stopped
where the assertions can reach it; a geometry read before and after is two. Each frame can be right on its own
while the sequence they belong to is wrong, and that gap has exactly one shape: a frame that puts back what the
frames before it took.

It is reachable rather than hypothetical, because a Web Animations effect stops applying at the end of its own
interval. Between that instant and whatever the `finished` handler does, the element is its unanimated self
again, full height and full opacity. Today the removal wins, in a microtask ahead of the paint; nothing in the
code says so, and one frame's slip is the whole of the distance between a fold and a fold that flashes the
thread back before it goes. So the fold is watched frame by frame at real speed
(`test_the_fold_never_paints_a_frame_that_undoes_the_last`), and that is the one check here that samples from
inside the page: what painted, in order, is not a fact the browser reports from out here. The wait still isn't
the sampler's — the node leaving the list is the browser's own statement — so what the injection buys is the
record and not the wait.

The same reading is what a recording of a motion owes. Frames of the first GIF of this fold were stepped by
`currentTime` and one was taken at exactly the duration, already past the animation's own interval: it recorded
the thread springing back to full size, a frame the product never paints. Every still was correct, the sequence
was a lie, and nothing between the frames and the reader looked at them in order.

The other is an instant. A reading taken through the browser is a round trip and the rendering step the page
was in does not wait for it: the room a wide widget spends is restated and the page stamped done in the same
block, and the layout observer restates it again on the very next frame whatever that block did — so a page
read after the stamp is right either way, and the test written to hold that line passed with the line deleted.
A `MutationObserver` on the stamp is a microtask off its own write and so lands ahead of that frame, which is
where the reading is taken now (`test_the_room_is_measured_after_a_late_rail`). The injection buys the record
again; the wait is still the stamp's.

## A page's source is formatted, so ask what it says

Prettier formats the `.html` under `docs/` and `examples/`, and it re-derives every line break in a
paragraph — half of the corpus's, measured. So a sentence asserted as a substring of a file is a sentence
that fails the day it gets a word longer, somewhere else. Collapse whitespace first, which is what a test
about what a page *says* meant anyway; the page's own reading (`spoken`) is the same answer where a test
already has a registry to hand.

Markup is the same rule for the same reason. A whole tag written out as a literal encodes a formatter's
opinion about attribute order and line breaks: prettier writes a void element `<link … />` and splits a
long one over four lines. Match the attribute that carries the meaning, or a pattern that admits any tag
around it. What made this expensive once was that the literal lived in `scripts/site.py` rather than in a
test — it silently stopped matching, a generic path rule took the stylesheet href instead, and every
published page linked a GitHub source view in place of its CSS. The link resolved, so the build's
dead-link check said nothing; what noticed was a palette test reading colours off the rendered page.

## A sweep that walks controls by index must prove it pressed them

A list read before the runtime injects its banner is a short list, and a short list skips silently rather
than failing — which is the vacuous pass, wearing the same green as the real one. Pin the count across
reloads, and check a new gate by putting each bug back and watching it fail; a gate that has only ever
passed has been tested for nothing.

## A test goes vacuous when the code stops being able to fail it

The bug-back above is written for a new gate, and the expensive case is an old one. A test asserts a bound, the
code later makes that bound uncrossable, and the assertion keeps passing while the fault it was named for moves
somewhere it is no longer looking. Nothing turns red on the way through.

Two here did it at once. Both measured a wide widget against the right edge of the page's box, which was where an
over-wide room used to spend itself; once the right margin was claimed by whatever stands in it, the widget could
only ever grow leftward, so the assertion was true by construction and the same faults sailed through both. The
room read too wide now runs off the *left* of the window, which is the worse direction: leftward overflow scrolls
nothing in a page set left to right, so what went past the edge is gone rather than merely out of view. A change
that alters which way a fault can point owes its existing tests a bug-back, not only its new ones — and the
question to put to each is which edge the fault lands on now.

## An assertion that nothing moved must straddle the change that could move it

A geometry assertion is worth only as much as the transition it is measured across, and the transition that
comes to hand is often the one that cannot move whatever the rule says. Room reserved for a pick mark is
the case. Moving a pick from one card to another gives the strip back exactly as fast as it takes it, so
"the card is the same box after the pick as before it" held perfectly with the reservation deleted, and a
gate written to catch that deletion passed with the bug in. Clearing the pick first is what makes the room
actually go missing: the assertion has to run from a group holding no answer to one holding an answer, not
from one answer to another.

So before writing "nothing moved", ask what would move if the rule were gone, and put the test where that
is. It is the same question `page.emulate_media` asks in its own register, and it is the one the bug-back
check above answers for you when the measurement is too clever to reason about.

## A captured stream nothing reads is a failure that names nothing

`check=True` over `capture_output=True` raises a `CalledProcessError` naming the command and the exit status,
and the streams it captured — the only account of what went wrong — die with it, because nothing prints them.
The demo recording failed that way three times in one stress run and the cause stayed unconfirmable until the
streams came back: two runs sharing a page directory, with the traceback that said so sitting in `e.stderr` the
whole time. Pytest already captures a child's output and prints it under the failure, so capture it in the test
only where something reads it, and where something does, assert the status yourself with both streams in the
message.

A wait that runs out is the same silence, and it is the expensive one. `round_trip` used to report the event
Playwright had blocked on and nothing about the page, three times on CI, about a fault its own counters named
exactly: a post a reload kills mid-flight ends in neither a response nor a `requestfailed`, so `acked` sat one
under `sends` for the rest of that page's life and every wait after it ran its timeout out. `_until` carries
the counters from both ends of the wait into the failure now, which is what tells a fact stuck while polls keep
arriving from a page that has stopped talking at all.

## Reloading is not resetting

The panel's open state is in `localStorage` and the reading position and drafts are in `sessionStorage`,
all deliberately, so a fresh `goto` restores the state the last gesture left. Clear both where a test means
the page as published — an open panel crowds the banner enough to absorb a shrinking button, and that alone
decided whether a real regression reproduced.
