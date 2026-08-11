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

## A round trip is not over when its response lands

The runtime answers a post by polling, so what the page does about a send arrives with
that poll rather than with the post. The press sweep learned this the expensive way: two
matching frames read the page from before the press had an effect, and it caught its own
regression on about half of the runs written to prove it caught it. Watch the trip rather
than timing it. The runtime posts and reads state back over the network, so one watcher
sees both halves and no widget declares anything; a hold sized to `POLL_MS` states a
number the runtime is free to change, still guesses on a loaded machine, and charges every
press two seconds for a trip that takes ten milliseconds.
`wait_for_load_state("networkidle")` is not the wait either: with no navigation to answer
for, it returns at once.

Watch it from outside the page. `Traffic` counts on the browser's own `request`,
`response` and `requestfailed` events, which is where a test belongs — the same five
numbers used to come from an init script wrapping `window.fetch` on every page of every
run, behind no flag, which is permanent surgery on the runtime under test to learn what
the browser was already saying. It also made the suite carry a second copy of a primitive
it already used, since `page.route` is the same interception the other way round. A failed
trip counts where a response would, or a wait outlives a request that is never coming back.

`open_page` hangs that watcher on every page: a test that had to ask for the counter first
is a test that asserted straight through the trip instead, and counting costs a page
nothing. `round_trip(page)` is the page's own sends coming back, which is what to wait on before
reading the event log — a widget settles a decision in front of the user before the
server has taken it, so the page reading done is not the log holding it. Polling the log
instead only ever asks after the send it names, and a stray one from the widget that was
supposed to stay quiet passes straight through it.

A file the test writes is the same trip the other way round, and `expect`'s own timeout is
the hold in disguise. A declared status, a bumped heartbeat, an appended event: none of
them announce themselves, so the page learns of each when its next poll asks, and an
assertion made straight after the write spends a whole poll interval of whatever budget
`expect` was given — 1.8 to 2.3 of the default five, measured, and every time, because
each assertion returns just after a poll lands. `told(page)` is that wait watched instead:
a poll counted out after the write went looking for it, and its answer is the page being
told. A wait's own timeout is the net under a hang rather than a budget for the work, so
once the wait is right the number is left alone: raising it buys back a margin while
hiding what is being bought, and lowering it — ten seconds for a version turnover where
the default gives thirty — makes the outcome a question about the machine.

## A wait consumes a fact the system states

A page that has not started moving is as still as one that finished, so a wait that
infers completion from stillness — two frames agreeing, a stretch with no change —
returns early exactly when the machine is loaded enough to fit its first samples in
ahead of the effect. `panel_settled` settled that way on a transition that had not
begun: a transition's first ticked frame still computes its start value, so the sample
at injection and the one on the next frame both read the margin the page already had.
The press sweep drew the same wrong inference from two matching frames before it
learned to watch the trip (above).

So a wait asks for what the system declares — an element existing,
`document.body.getAnimations()` emptying, a request coming back, a resize reaching its
listeners. Where stillness is itself the assertion, an observed edge precedes it: the
press sweep measures "nothing moved" only after `round_trip` has watched the response
land, so the quiet it reads is after the effect. And a timing flake reproduces by
emulating the poller's own schedule in the page — `wait_for_function` runs its predicate
once at injection, then once per animation frame — which makes the failure a rate to
measure rather than a rerun to hope for.

An edge is not the same fact as arrival, and a gesture that moves the page twice is where
they come apart. Clicking a quote scrolls instantly to bring the passage's box on screen,
then smoothly to centre the painted range, and `scrollend` fires for each: the first is a
statement the browser makes, and it is 232 pixels short of where the click was aimed. The
fact worth waiting on is the destination — the mark reaching the middle, which is what
`scrollToThread` computed — because a glide that approaches it passes through no earlier
position that could be mistaken for it.

Where nothing will happen there is nothing to consume, and polling has no end. An absence
holds a window instead, long enough that the thing would have happened, with the length
derived from the mechanism rather than picked: a manually launched server must outlive
the grace a session watcher would have shut it down after, so the window is
`ORPHAN_GRACE_SECS` plus room to act. A window too short fails the other way round from
everything above — it passes vacuously rather than flaking — which is why nearly every
absence here holds none at all. A POST the test aborted cannot reach the log, and a
decision the page never took cannot be in it; those assert straight after the edge that
proves the gesture was handled.

## Nothing of the suite runs inside the page

The tests drive the runtime; they do not join it. What the suite knows about a page's
traffic it gets from the browser — `request`, `response` and `requestfailed` to watch,
`page.route` to stop or delay — and a page that a product path opens for itself is reached
the same way, through `primed`. Nothing is injected to make a wait possible, so what the
tests exercise is the runtime a user gets rather than one wearing the suite's hooks.

That was not always so, and what went is worth knowing when a wait looks unnecessary. An
init script wrapped `window.fetch` on every page to count trips, and `LEAF_TEST_LOAD=1`
added a second wrapper holding each `/api/state` answer back three and a half seconds,
alongside a CPU throttle slowing the page's own JS twentyfold — a machine slow in the two
ways a busy one is, run on purpose. Two tests had gone red on an ordinary busy run and that
sweep found seven more standing on the same margin. `resized` and `open_page`'s
upgrade-stamp wait are both its finds: `set_viewport_size` returns on a fact about the
browser rather than about the page, and the gallery, the heaviest page here, had not
finished upgrading when the banner appeared.

The waits stand; the instrument is gone. So a wait that is missing now passes on every
machine quick enough to hide it, and the next fault of that shape arrives by luck on a
genuinely busy one rather than on demand. That is what a clean runtime cost, and it is paid
for by the waits above being right — a wait consumes a fact the system states, and there is
no longer anything behind that rule to catch a wait that doesn't.

## A test cannot assert over noise it makes itself

`page.route` stops a request from outside the page, and what the browser then says about
that request comes back to the test in the same list its own assertions read. A poll
refused with `route.abort()`'s default reason is a failed load, and Chrome writes
"Failed to load resource: net::ERR_FAILED" to the console for it — which `open_page`
collects, where it sits indistinguishable from the page having broken. How many of those
entries a test reads back is then the machine's answer rather than its own. A run that
reaches its last assertion inside a 2s poll interval refuses nothing; one that refuses a
poll on the way can still read an empty list, since the entry reaches the test after the
browser writes it. A loaded run refuses a poll per tick and hears about each in time to
fail on it — so the test written to instrument a slow machine was the one that failed on
a slow machine, naming the runtime for its own instrument.

`refuse` cancels the request instead, which the console has nothing to say about, so
`errors == []` says what it looks like it says however many polls a run refuses. Where
the failed request is the subject rather than the instrument — a send the server never
takes — the abort stays plain and the entry it leaves is asserted.

## A motion is a sequence, and every other check here reads a state

Both ways of reading an animation from outside read states. A held frame
(`HOLD_MOTION`) is one state stopped where the assertions can reach it; a geometry
read before and after is two. Each frame can be right on its own while the sequence
they belong to is wrong, and that gap has exactly one shape: a frame that puts back
what the frames before it took.

It is a reachable shape rather than a hypothetical, because a Web Animations effect
stops applying at the end of its own interval. Between that instant and whatever the
`finished` handler does — remove the node, restore the styles — the element is its
unanimated self again, full height and full opacity. Today the removal wins, in a
microtask ahead of the paint; nothing in the code says so, and one frame's slip is
the whole of the distance between a fold and a fold that flashes the thread back
before it goes.

So the fold is watched frame by frame at real speed
(`test_the_fold_never_paints_a_frame_that_undoes_the_last`), and that is the one
check here that samples from inside the page: what painted, in order, is not a fact
the browser reports from out here, where a request or a detached node is. The wait
still isn't the sampler's — the node leaving the list is the browser's own statement
and is what the test waits on — so what the injection buys is the record and not the
wait, which is the line the rule above draws.

The same reading is what a recording of a motion owes, and the first GIF of this fold
is why the rule is written here. Frames were stepped by `currentTime` and one was
taken at exactly the duration, which is already past the animation's own interval: it
recorded the thread springing back to full size, a frame the product never paints.
Every still was correct, the sequence was a lie, and nothing between the frames and
the reader looked at them in order.

## A page's source is formatted, so ask what it says

Prettier formats the `.html` under `docs/` and `examples/`, and it re-derives every line
break in a paragraph — half of the corpus's, measured. So a sentence asserted as a
substring of a file is a sentence that fails the day it gets a word longer, somewhere
else. Collapse whitespace first, which is what a test about what a page *says* meant
anyway; the page's own reading (`spoken`) is the same answer where a test already has a
registry to hand.

Markup is the same rule for the same reason. A whole tag written out as a literal
encodes a formatter's opinion about attribute order and line breaks: prettier writes a
void element `<link … />` and splits a long one over four lines. Match the attribute
that carries the meaning, or a pattern that admits any tag around it. What made this
expensive once was that the literal lived in `scripts/site.py` rather than in a test —
it silently stopped matching, a generic path rule took the stylesheet href instead, and
every published page linked a GitHub source view in place of its CSS. The link resolved,
so the build's dead-link check said nothing; what noticed was a palette test reading
colours off the rendered page.

## A sweep that walks controls by index must prove it pressed them

A list read before the runtime injects its banner is a short list, and a short list skips
silently rather than failing — which is the vacuous pass, wearing the same green as the
real one. Pin the count across reloads, and check a new gate by putting each bug back and
watching it fail; a gate that has only ever passed has been tested for nothing.

## An assertion that nothing moved must straddle the change that could move it

A geometry assertion is worth only as much as the transition it is measured across, and the
transition that comes to hand is often the one that cannot move whatever the rule says. Room
reserved for a pick mark is the case. Moving a pick from one card to another gives the strip
back exactly as fast as it takes it, and in the grid form of the day the row stood as tall as
its tallest cell either way — so "the card is the same box after the pick as before it" held
perfectly with the reservation deleted, and a gate written to catch that deletion passed with
the bug in. Clearing the pick first is what makes the room actually go missing: the
assertion has to run from a group holding no answer to one holding an answer, not from one
answer to another.

So before writing "nothing moved", ask what would move if the rule were gone, and put the
test where that is. It is the same question `page.emulate_media` asks in its own register,
and it is the one the bug-back check above answers for you when the
measurement is too clever to reason about.

## A captured stream nothing reads is a failure that names nothing

`check=True` over `capture_output=True` raises a `CalledProcessError` naming the command
and the exit status, and the streams it captured — the only account of what went wrong —
die with it, because nothing prints them. The demo recording failed that way three times
in one stress run and the cause stayed unconfirmable until the streams came back: two runs
sharing a page directory, with the traceback that said so sitting in `e.stderr` the whole
time.

Pytest already captures a child's output and prints it under the failure, so capture it in
the test only where something reads it, and where something does, assert the status
yourself with both streams in the message. A script the test drives owes the same of every
process it starts, or the test reports a silence the script was told the reason for. The
browser end of this is `open_page`, whose console says only "Failed to load resource".

## Reloading is not resetting

The panel's open state is in `localStorage` and the reading position and drafts are in
`sessionStorage`, all deliberately, so a fresh `goto` restores the state the last gesture
left. Clear both where a test means the page as published — an open panel crowds the
banner enough to absorb a shrinking button, and that alone decided whether a real
regression reproduced.
