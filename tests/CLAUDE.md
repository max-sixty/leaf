# Testing leaf

The suite proves the boundary between an authored page, the browser runtime, the
event log, and a returning reader. Most failures in that boundary are easy to
assert once they are visible. The difficult part is arranging the test so that a
green result could only have come from the behavior named by the test.

This file owns test setup, suite structure, and testing mechanics.
`skills/leaf/assets/CLAUDE.md` and the code-adjacent contracts routed by
`/developing-leaf` own the product protocols. Keep implementation rules there;
state here only what a test must observe or control. Each section below is a
rule, the helper that carries it, and the test that pins it, so a heading is an
address other files can point at.

## Run the narrowest useful surface

A new development host fetches the pinned catalog images and installs the browser
binaries and website dependencies with the repository setup alias. `uv run`
synchronizes the Python environment, including pre-commit:

```sh
wt setup
```

The host supplies `wt`, `uv`, `jq` 1.6 or newer, and Node 22 or newer. The
ordinary and nightly suites run directly on the host. Docker is needed only for
the complete website boundary.

The everyday suite needs no network after setup. It runs one shipped page through the
browser gate and the shared chrome contracts whose regressions must block a pull request:

```sh
uv run pytest tests
```

The `test_render_*.py` modules and `test_site.py` are marked nightly;
`test_chrome_contracts.py` holds the small browser surface in the everyday gate. Broad
discovery skips nightly tests. An explicit file, node id, `-k`, `-m`, or `--lf`
selection runs what it names. During development, select the owning file or one named
case and use `-n 0` so the trace and process tree stay local:

```sh
uv run pytest tests/test_render_widgets.py -q -n0 -k board
uv run pytest --lf --lfnf=none -x -n0
```

Formatted CLI output lives in `tests/_regtest_outputs/`. After an intentional
change, reset only the affected test, then inspect the recorded diff before committing:

TODO(2026-09-12): Move more stable multiline CLI output contracts from partial
string assertions to regtest snapshots.

```sh
uv run pytest --regtest-reset -n0 <node-id>
```

Before handing over a browser-facing change, run its complete browser file and
the everyday suite. If the change affects behavior covered by nightly tests, run
the smallest local nightly selection that covers it too. `wt merge` runs pre-commit
and the everyday suite after rebasing. Pull requests run pre-commit, the everyday
suite, and the website-worker checks. Main runs the ordinary gate and then, once it
is green, the complete suite in one job; `publish-site` runs the website checks
before deploying a relevant main change. Main holds one complete-suite slot and the
newest commit takes the next turn, so a busy main gets the complete suite on its tip
rather than on every commit, and the daily schedule covers a quiet one:

```sh
uv run pytest tests --run-nightly
```

GitHub Actions is the Linux authority. It runs the commands above directly on
Ubuntu 24.04; a local container is not the same runner, and on Apple silicon it
must either emulate the CPU or substitute Chromium for installed Chrome. Use the
host suite for development feedback and the candidate and base-SHA workflow runs
for Linux-specific evidence.

The developer environment comes from the one `pyproject.toml` and `uv.lock` at
the repo root, which is also the payload project: `uv sync` installs `leaf`
from this checkout editable, dev group included, so a test importing `leaf`
gets the checkout directly.

Subprocess tests use `LEAF_COMMAND` from `conftest.py`. A test invokes `bin/leaf` only
where the launcher itself is the subject: the installed payload's copy, and the shim's
own uv dispatch. `install_payload()` copies tracked and unignored candidate files,
including unstaged additions.

Because candidate payloads include untracked files, `interact_support.py` refuses
a nonignored `--basetemp` inside the checkout. Pytest's default under `$TMPDIR` is
already isolated across concurrent runs.

## Put each assertion at the boundary that owns it

The `test_interact_*.py` modules exercise authored markup, the registry, the
event log, CLI commands, vendoring, publishing, export, and server lifetime. The
`test_render_*.py` modules drive the browser runtime and the render gate.
Full-page navigation and comparison regressions live in `fixtures/pages/`, outside
the published examples. Their companions follow `examples/CLAUDE.md`; the page and
corpus sweeps include them. File-side fixtures live in `interact_support.py`. Browser process and page
fixtures live in `render_harness.py`; reusable browser cases are grouped by
interaction, layout, navigation, and widget behavior in `render_cases_*.py`.
Both fixture modules use `TemporaryPageServer`, the same process-owned server as
an unclaimed `scripts/preview.py`. Test modules import support from its owning
module directly. `test_site.py` reads the
built site through its served URLs. Product documentation tests compare the docs
with the shipped vocabulary and command surface: a shown command the click tree
has not got, an `x-` key the guide omits, a table that has drifted from the
registry it was generated from.

The authored-source render gate runs every public example, regression page, and
developer gallery independently. The broad Axe baseline uses the feature gallery at
both widths and color schemes. The exported corpus's 420px Axe pass reads the specialist
package pages in their non-live form; focused tests read live chrome surfaces. Standalone
export runs once on generated `examples/corpus.html`, revealing its outer tabs before
inspecting the whole payload composition. File-to-browser anchor parity uses four unlike
authored pages that contain file passages. A source gets its own case only when its
content is the cause under test.

That comparison is the whole of what a test over prose can prove. An assertion
that some sentence stands in a file a model reads fails only when somebody
rewrites that sentence, so it catches an edit, and whether the edit was right is
a question for review either way. Derive one side of a prose assertion from the
machine, or leave the wording to review.

A property caused by a particular page belongs in `render_version`, because
`version check --render` must report it to the page's author. A property that is
identical for every valid page belongs in the suite instead; `arrival_findings`
is one, since changing the authored page cannot repair how the layer restores
browser state.

The same line runs through the render gate's own readings, and what decides it
is whether a reading needs a box. A reading of text or attributes may cross into
the thread panel (`unreachableWords`, `silentWords`, `undeclaredAttrs`). A
reading of geometry may not, because the gate never opens the panel and a shut
one has no boxes: most stop at `.lf-chrome` or start from `main`, and
`tinyBoxes` and `clippedControls` stop at `checkVisibility()`. `trappedMargins`
reads computed style inside `display: none`, where paddings still resolve but
container queries do not match, so it tags each finding with its document and
the gate takes the page's half. The suite opens the panel and puts the same
readings to it, asserting each population first and planting its fault under
`.lf-chrome`, so a clean result cannot come from a reading that never arrived.

A reading that asks what keeps a box from being seen must not be a second answer
to a question the product already answers. `shownBand` is the layer's own
reading of the band a box shows, naming overflow, paint containment, and
`content-visibility`; `version check --render` and `RINGS_DRAWN` both consume it
rather than copying it.

A focus ring is drawn only in keyboard modality: `element.focus()` alone sets
`:focus` and not `:focus-visible`. A direct specimen first presses `Tab`, then
focuses its exact sequential stop and requires it to retain `:focus-visible`.
The reading must find a ring on that stop, its ancestor, or the exact semantic
carrier the test links to it before asserting anything about the ring's shape.
A separate fast sweep reaches every stop in the selected pages' ordinary Tab
orders, and a planted test reaches the banner and thread list through their real
keys before taking the ring away. Which box wears the ring is a separate
question from which holds focus: a decision may
wrap the control reached, a joined option group may stand for the pick that gave
up focus, and an anchored element may have no focus of its own. The reading
therefore sweeps every box painting a ring and asks the paint, never
`getComputedStyle(activeElement)` and never a selector. A thread is the distinct
large-composite case: the current panel card repaints its existing border and surface,
while an unbordered inline card reserves symmetric resting room around its content and
draws the same quiet edge inside that room. Their tests compare that paint with a
resting state while checking the card's visible placement and unchanged focused
geometry, including a later sibling that must not carry an old divider inside its edge.
The band has two carriers: `--here-ring`, the outline
nearly every rule draws, and `--here-shadow`, the same band cast as a shadow by
the two boxes that cannot spend an outline on it — the anchored response bar and
the target hint the keyboard is browsing. A shadow ring is the layer's spread with
no offsets and no blur, and its outset is that spread, where an outline's is its
width and offset. Each rule names the ring it draws in `--lf-here-ring`, so
the population the floor divides by is read off the page's composed stylesheets,
one question per carrier: does the value name the layer's token.
`test_the_ring_reading_names_every_way_a_box_can_draw_nothing_past_its_edge`
plants one outset ring under three clipping parents with a control case that
must report nothing,
`test_the_ring_reading_sees_and_measures_a_ring_cast_as_a_shadow` puts the three
shadows the layer draws that are not the band in front of the reading and then
stands the band on the window's foot, and
`test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` fails
on any rule with no causal specimen and any required surface that does not open. A ring
is credited when a box painting the layer's band also carries a name; a name
whose ring a later rule took away is not credited — which is what keeps the
response bar's own controls off `pressable`, the floor rule whose outline the bar
removes — and a ring painted with no name is its own finding. Nothing reads
`@media` or `@supports`: the reading is taken on screen.

Each focused specimen also asks whether the reader can see where the keyboard
is. Four answers count: the platform's own ring (`outline-style: auto`), the
layer's here ring on the stop or an ancestor drawing for it, the element mark's
own ink at the indicated weight, and the band the anchored response bar casts as
a shadow — the sweep's own reading of it, so the two halves of the file agree on
what one is. Colours are resolved through a swatch rather than compared as
written, since a `color-mix` and a plain token spell one colour two ways. Any
outline an element wears for a reason other than focus silently costs it the
ring it would otherwise have had.

An opening key sequence states its starting point. `blur()` retains the previous
sequential focus navigation position; `document.body.focus()` resets it.

A reach case answers for the shapes it is written over, and a ring has two,
outset and inset. `ring_faults`'s cover check steps past the ring's own band
(`grow + w`) to ask whether a control stands behind something; a one-pixel step
clears an outward ring and lands inside an inset one.
`test_the_ring_reading_sees_a_neighbour_paint_over_a_ring_drawn_inside_its_box`
is the plant over the inset shape.

The same stepped-in point answers the order the other way about. An outline is
painted by its control, so a box the control stands in front of cannot stand over
the ring around it, and the sample outside the control's box lands on one of those
whenever a control floats over content its own holder scrolls — the panel's edge
grip does, at every width. The reading ranks the nearest box holding the neighbour
that is present at that point and is not itself holding the control; a z-index
named on the way up stops the walk, since it lifts the box past the holder being
ranked. Position lifts a box the same way without naming one, so where the ranked
holder is static the answer is the control's own layer instead: one that names a
z-index stands clear of the layer a lifted neighbour paints in, and one that names
none shares it.
`test_the_ring_reading_passes_over_a_neighbour_the_control_paints_across` plants
the same band under each order against the grip, which names one, and
`test_the_ring_reading_sees_a_neighbour_lifted_out_of_the_flow_it_was_ranked_in`
against a control that does not.

Prefer the public route through the product. A CLI test invokes the command or
the same command function the entry point uses. A browser test serves a
vendored page and uses its HTTP API. A render-gate test calls
`leaf.render_gate.version.render_version`, not one of its probes. Test a helper
directly only when the helper itself carries a contract that would otherwise be
hard to diagnose, such as the traffic wait reaching its deadline.

A probe's independent faults belong on one composed page when its findings attribute
each fault separately. Put clean controls beside them and assert the relevant populations
before calling the public gate, then compare its complete result where the fixture owns
every expected finding. Do not start a fresh browser gate merely to vary one declaration
or stylesheet rule that the same reading can distinguish by owner, role, or surface.

A reading the layer makes from declarations belongs on a widget that declares
them, not on whichever shipped entry currently does. `serve` takes
`layer_registry` and `layer_widgets` for that: a project-package entry and its
module, written as a `render_cases_*` constant. Borrowing a shipped tag goes red
the day the default package stops declaring what the reading needs.
`PAGE_PACKAGES` puts the `diagram` and `diff` declarations in `page_dir`'s
registry for readings that borrow those tags.

Re-vendor before trusting a result that depends on runtime, theme, registry, or
widget changes. A page directory owns the layer copied into it by `page init`;
a green render against a stale page is a statement about that stale copy.

## Fixtures own the world they create

Every test runs under `isolated_session`. It moves only the XDG state
directory Leaf reads, supplies a synthetic Claude Code session id, and claims
pages under the current pytest worker's pid. Do not replace it by moving `HOME`;
uv's cache and unrelated developer state are not part of leaf's isolation
boundary.

The one subject that must take uv's cache into its world is what the launcher
resolves. A test of where `bin/leaf` looks for a dependency asks the host's
index for every one of them, so it needs the network the nightly run holds, and
a cache directory of its own (`UV_CACHE_DIR`), since a wheel already in the
developer's cache answers before any index is consulted.

Use `sessionless` when the subject is a command launched outside any host
session. Use `codex_env` when constructing a real Codex process ancestry; it
removes the Claude identity that would otherwise win host detection. Declare
those conditions through fixtures rather than deleting environment variables in
a test body.

### A process the suite starts ends with the run

The run catches SIGINT itself, so every child starts at the default disposition
a terminal gives. A run launched as a shell's background job inherits SIGINT set
to SIG_IGN and passes it to everything it spawns, and a test that interrupts its
own child would otherwise pass or fail on how the run was launched rather than
on the code.

Server ownership has two layers:

- `spawn` owns every child process started directly by a test and ends any
  survivor during teardown — the group, for a child given a session of its own,
  because such a child's own children join that group and the handle the test
  keeps names only the launcher.
- `_no_page_outlives_its_test` releases the suite's held leases, searches the
  temporary page and state roots, and stops every live leaf server it finds.
- `preview_slot` sets `LEAF_PREVIEWS_ROOT` under `tmp_path`, so a preview test's
  pages are in the roots that sweep walks rather than in the checkout's shared
  `.tmp/previews`. It then retires each slot's watcher through
  `preview.retire_preview`, because a watcher is detached into a session of its
  own: neither the sweep nor `spawn` reaches one, and retiring it waits for its
  lease rather than pulling its page out from under it.

The search is intentional: a cleanup list catches only the server a test
remembered to register. A page server is spawned into its own process session,
so a local `Popen` handle is not a general substitute for `leaf server stop`.
The synthetic session claim is the final owner when a worker itself is killed
and fixture teardown cannot run.

In-process HTTP fixtures use `interact_support.running_http_server`, which owns
the serving thread, socket close, and bounded join.

A standing server is the explicit exception. It declines session ownership by
definition, and tests of standing lifetime must stop it themselves. Keep that
exception narrow and short-lived.

A Unix socket is the one file that cannot live under those roots: `sun_path` is 104
bytes and pytest has spent most of them before a test's own files begin. `socket_dir`
owns that exception — a short directory under the system temporary root, removed when
the test ends — so a test never names `/tmp` itself.

A fixture cannot stop a test making its own, so
`test_the_resources_a_fixture_owns_are_taken_from_that_fixture` reads the suite for
the calls these fixtures exist in place of — starting a process, launching a browser,
making a socket directory — and names the owner of each. An exception is a line in
that list saying which file holds it and why.

The sweep's roots are the run's own: the test's `tmp_path` and the state home
`isolated_session` returns. An autouse fixture that needs the isolated home takes
it from that fixture, never from `state_home()` read at setup or teardown, where
the environment is the developer's. Autouse fixtures set up outermost first (a
`pytest_plugins` module's before the conftest's) and tear down in reverse.
`test_a_run_ends_only_the_servers_it_started` runs a nested suite against a
planted home and requires the planted page untouched and the run's own leftover
stopped.

### Reloading is not resetting

Panel state and drafts live in `localStorage`, while reading position lives in
`sessionStorage`. Clear both when a test means a first visit. Two pages are not
two tabs for a single reader unless they share a browser context:
`Browser.new_page` creates an independent context; `one_reader` supplies one
context for the tests whose subject is shared tab state.

The product-site pages and examples are complete page directories served through the
website's canonical Leaf adapter. Tests that exercise the public routes wait for both
runtime stamps and assert the publication state; a rendered custom element alone does
not prove that the interaction layer is present.

For complete, valid browser fixtures, use `leaf_page(title, body, head="")`. It
supplies the same language and authored head/body/main shell to every specimen;
delivery adds the encoding, CSP, theme, and runtime module. Keep raw documents only
when source structure is the subject:
lint fixtures, malformed markup, tokenizer input, line-number assertions, or a
document whose missing boundary is the condition under test.

The browser fixture `serve` is the normal owner of a specimen. It runs `page
init` once per worker for the ordinary layer, takes an initialized page of that
shape from `initialized_page`, writes the document as v1, copies the example
media that document
names, adds the publishing note and any requested comments, then serves the
directory with the real HTTP routes and page key at that version's immutable
URL. Handed an example's path rather than its markup it also lays in the
external data and event log the example ships, and sets the cursor past the
log. It lays in the media that log names too, which a message writes in its
Markdown rather than in an attribute, where the parsed reading that answers for
a document cannot see it; the seed is read for content-addressed names, and
they arrive whether or not the call seeds the log, since `seed_log=False` is
how a caller appends those same events itself. Markup is one version; an
example is every version it ships (`example_versions`), stamped oldest first
with the seed between the first note and any later one, and the URL is the
newest. Use `serve(example, seed_log=False)` when only the shipped conversation
would be noise. Reach the page directory through `serve.page_dir` when a test
needs to publish v2 or inspect the log. `page_dir` in `interact_support.py`
owns command-level files without starting a browser and takes its ordinary
initialized layer the same way.

`initialized_page` composes one page per shape and lends it. A test gets that
page moved to the path it asked for, and when the test ends the page goes back
to the pool, where the next loan resets it: every file whose inode, size or
modification time moved is put back from the shape, and everything the test
added is removed. Copying the layer instead cost 146 files a test, which put
2,272 pages and 393,473 directory entries through a nightly run — bytes a hard
link shares, but a directory entry is what a filesystem event watcher counts.

Runtime and vendor files are immutable fixture inputs and are hard links into
the shape; the rest is a private copy. Nothing may write a page's layer in
place — vendoring replaces, and a file written through its link fails the next
loan by name. A page-owned file the reset has never heard of needs no entry
anywhere: it is removed because the shape has not got it.

Tests of initialization, re-vendoring, or a custom overlay still cross the real
`page init` boundary, and a test whose subject is the composition itself passes
`initialized_page` a shape of its own or builds its page without the fixture.

## Drive the browser a reader gets

The browser suite uses Playwright's pinned Chromium headless shell and real
HTML. The `iphone` fixture is Playwright's WebKit in an iPhone-shaped context, the
engine iPhone browsers run on, for the everyday contract that the page starts and
takes a comment there. Use `locator.click()`, `page.keyboard`, and `page.mouse` when the gesture
matters. A synthetic `dispatchEvent` can skip the pointer sequence the runtime
listens to and prove only that a handler works under an impossible event
history.

Use `select` for selection drags. It floors the starting coordinates to a whole
pixel because a fractional point can straddle a glyph's caret boundary and leave
an otherwise valid drag with an empty selection. Preserve the end coordinate.

`locator.click()` scrolls its target into view first, so a baseline read before
one is a reading of the page the test arranged and not of the page the press
finds. Where the subject is what a press does to a scroll position, put the
element on screen first (`scroll_into_view_if_needed()`) and read the baseline
after that.

Nothing should be injected into the page merely to make ordinary observation
easier. Traffic is read off the delivery ledger the runtime itself paints on the root
element (`data-lf-traffic`, `runtime/traffic.js`). Network conditions come from
`page.route`. `watched` listens to the
browser's error surfaces. `primed` lets a render or export call create its own
page while the test attaches those external controls before navigation.

A page the product opens to read for itself is the product's: `render_version`
collects that page's console and `pageerror` and reports them as findings. A gate or
export test whose page is meant to be faulty therefore hands over `browser.unwatched`,
rather than asserting the same errors twice — once against the gate's report and once
against the suite's collector. A product call whose page should be clean takes the
ordinary browser, where an unexpected error fails the test that caused it.

An init script is justified only when the fact cannot survive long enough to
cross the Playwright boundary: recording a sequence frame by frame, or capturing
an instant between one DOM write and the next rendering turn. The injected code
records evidence; completion still comes from a browser or product fact visible
outside the page.

## A page is ready when it says what has finished

Open ordinary browser pages through `open_page`. It navigates, waits for the load
event, and then waits on `BOTH_STAMPS`:

- `data-lf-upgraded="1"` says widget upgrade finished.
- `data-lf-applied` says a replay pass applied the event log.
- `data-lf-presented="1"` says the initial authoritative projection or offline fallback
  crossed the interaction boundary. The anchor pass and anchored composer begin here;
  authored HTML may have painted earlier.
- The current presentation probe says every required renderer for the active semantic
  epoch has settled. A later publication or same-epoch replacement can make it false
  while `data-lf-presented` remains set.

These are independent facts. Network quiet implies neither. A browser action
sent before replay has landed may be ignored without a later assertion revealing
that the keypress itself was lost. Use the shared `BOTH_STAMPS` predicate for
manual navigations as well; the `upgraded=False` escape in `open_page` is only
for a test whose subject is the interval before those stamps, waits for the
banner module to exist, and must make its later readiness explicit.

A test whose subject is the page before the runtime lands needs the other end of
that distinction, and element visibility does not carry it. A forced layout —
`bounding_box`, and `to_be_visible` with it — answers from the stylesheets that
have arrived, so an element has a box while the render-blocking theme is still in
flight, and the geometry read behind it is the user agent's own. `displayed` waits
on first contentful paint, the browser's record that the head has been applied and
what it composed is on screen. Every pre-runtime measurement takes it first, in
`test_authored_html_paints_while_runtime_startup_is_held`,
`test_a_restored_auxiliary_surface_has_final_geometry_before_runtime_loads`, and
the two site shells: the reading it excludes is the unstyled document, which
differs from the presented page by the whole theme and arrives as a report that
startup moved the shell.

Every page the `browser` fixture makes arrives readable: the problem list `watched`
collects into, the interception arm, and the `Traffic` ledger, installed by
`WatchedBrowser` in the call that makes the page. None of the three can be added
afterwards — an init script has to precede the navigation it instruments, and a
console entry from a page nobody was listening to is gone — so a test that makes a
page cannot end up with one that reports nothing. It used to: 38 test functions made
a page of their own and never asked for the readings, and every one of them was green
about a page whose console, `pageerror` and window `error` channels nothing read.
A page must therefore come from that fixture, or from a context it made.

The fixture ends it too, so a test that has finished with a page leaves it open. It
closes every context after reading what the pages reported, in that order and for
this reason: closing stops event delivery, so a close written at the end of a test
cuts the reading short — its own reading, a step before the fixture takes it.

A close inside a test is a different thing, and it stays: a second tab shut to show
what the first one still holds is the gesture the test is about, and the assertions
after it are what read the close. So the rule is the ending, not the call, and
`test_the_resources_a_fixture_owns_are_taken_from_that_fixture` reads for exactly
that — a close anywhere in a `finally`, or on the line a test ends on, followed down
through the loop or branch it ends inside — on anything the browser fixture handed
over, however it travelled. Its one exception is the page that keeps making the
fault its test is about, where the consume has to follow a close of its own.

For the same reason nothing installs them a second time. `watched` returns the list a
page already has, because a second list would take `lf_errors` with it and leave the
first collecting into a reading no test can consume; and nothing installs them from
inside a Playwright event handler, where a `page.route` leaves the `add_init_script`
after it without effect and says nothing about it.

`watched` collects console warnings, console errors, and `pageerror`, and calls
`leaf.render_checks.install_window_errors` so browser `error` events without an
exception reach the same list. That script is shared with `render_version`; the suite
and the handover gate must not disagree about which browser error channels count.

`navigate` handles the one browser notice that needs confirmation: a
ResizeObserver-loop notice raised during handover is repeated with a complete
second navigation; a recurring notice is a failure, a one-off platform notice is
not. The function-scoped browser fixture rejects every collected problem after the
journey, then closes its remaining contexts. Context closure can cancel an outstanding
request, so it is cleanup rather than part of the health reading. A test that
intentionally produces a known class of problem uses `consume_browser_errors` at the
causal point; every collected entry must match one of its named fragments. Use
`take_browser_errors` only when the test itself asserts the exact list or partitions
every entry. Filtering the collector or leaving expected noise behind is not an
assertion.

A fault the page keeps meeting has no causal point to be consumed at: a route that
answers every `/api/state` with a refusal is met again two seconds later, and a list
read before the next one is a list with a later entry still to come. Consume that
after `page.close()`, which is what settles it; the entries survive the page.

## A wait consumes a fact the system states

A reliable wait consumes a fact stated by the system. It does not infer
completion from elapsed time, two matching samples, or a quiet network. A page
that has not started an effect is indistinguishable from one that finished if
the only evidence is stillness.

A computed style is one of those facts and it is not always a resting one: under
a running transition the platform reports the animated value, which early in the
transition is the value the property is leaving, and steady enough that two
matching samples both land inside it. Ask `getAnimations()` where a reading's
subject may be in transit. The theme's reduced-motion guard removes transitions
rather than shortening them, so no reading here needs such a wait on its own
account.

A wait states its end as well as its fact. `page.evaluate` takes no timeout in
any binding, so a promise awaited inside it is a wait nothing bounds: it spends
the job's whole step, and the share of the suite already handed to that worker
never runs. State synchronous readiness inside the page and poll it with
`wait_for_probe`, whose driver-side wait carries `SERVED_TIMEOUT_MS`;
`render_checks.py` refuses a probe that returns a Promise. A shipped probe's ordinary
browser lifecycle is always a synchronous fact observed from outside the page.

### A state the page passes through is not a state to poll for

Use Playwright's `expect(...)` for a state that will become stable and remain
true. Use an ordinary read only after the causal edge is known to have
completed. Do not use an auto-retrying assertion for a transient state: it
returns on the first matching frame, even if the gesture continues to a
different result.

The causal helpers:

- `Traffic` reads the runtime's own delivery ledger: posts to `/api/event` issued
  and ended, reads of `/api/state` asked and heard, and the outbox's attempts with
  no outcome yet. It counts attempts, so a retry is a second send. The ledger is
  the document's: a navigation starts it over with the page that carries it.
- `round_trip(page)` waits until every event attempt sent by that page has a
  definitive outcome. A request failure alone is not final because the page may
  retry the same attempt.
- `sending(page, what)` encloses a gesture whose own event the assertion behind
  it reads: it waits for one further send to enter the wire and then for its
  trip, so the read cannot answer with the event that stood before the gesture.
- `holding(page, held, count, what)` waits until a route's own list has the
  requests the handler put there, for a test that holds the wire open — the ones
  it paused, and the ones it recorded on the way through. The ledger counts a
  send as the runtime makes it, a beat before the driver is handed the request,
  so it is the wrong fact to read that list behind.
- `told(page)` waits until the page has applied the reading the server holds
  now. Use it after the test writes a version, event, status, or lease that the
  browser learns by reading.
- `nudge(page_dir)` gives the page a reason to read, changing nothing it shows,
  for a test that wants the page's next request.
- `ticked(page)` waits for the page's next local re-application, the heartbeat
  that applies a correction an editor deferred.
- `undo(page)` waits until the shortcut bar offers undo, presses `z`, observes the
  new send enter the wire, and waits for its round trip; undo can be refused
  while the preceding gesture is still unresolved.
- `reported_browser_errors(page, *expected)` waits for the complete report one
  fault draws before consuming it. A fault is named by every boundary that
  carried it, and the later words can trail the first by whatever the page does
  between them, so an equality assertion taken on the first word is a race.
- `shortcut_bar_text(page)` reads what the shortcut bar says, once, after the repaint's own
  frame. `repaint` coalesces to a `requestAnimationFrame`, so a read taken in
  the same round-trip as the press is a read of the frame before.

A surface that reads the same before and after the press cannot be its own
wait. `expect(...).to_have_text(...)` is satisfied by the frame the press has
not reached yet, and a measurement taken behind it compares a reading with
itself. When a surface does not itself change, a test whose subject is what a
press does within it waits on some other fact of that press
(`test_numbered_addresses_show_progress_on_complete_routes_without_moving`),
and its bug-back is run more than once, because a wait that is sometimes real
looks exactly like one that is.

A container the runtime keeps whether or not it holds anything is that surface
too. Every anchor pass calls `CSS.highlights.set` for each of its names, empty
ranges included, so wait on what the pass put in it
(`(CSS.highlights.get(name)?.size ?? 0) > 0`, or `wait_for_pending_mark`),
never on the name being there.

A surface the page paints before the server answers is that surface too. A
comment is rendered the turn it is sent, under the `pending:` identity
`conversationForAttempt` gives it, so a `.lf-thread` count reads the same on the
path where the request is refused. Wait on the identity the response replaced it
with (`.lf-thread:not([data-id^="pending:"])`) or enclose the gesture in
`sending`. Where the refusal under test is a request failure the outbox retries
rather than settles, the identity is the only one of the two that answers:
`round_trip` inside `sending` waits out its whole deadline on it
(`test_the_captured_quote_is_prose_a_file_can_hold`).

A retrying assertion that a paint has not happened is the same trap with the
other sign, and worse: a negative assertion is satisfied by the first poll, and
the first poll is before the frame. Wait on a positive fact the same frame
writes (the shortcut bar's word, through `shortcut_bar_text`) and read the absence behind it.
Bug-back with a probe that paints the mark the assertion denies, not by
reverting the change, which usually stops the mark being painted at all.

The shortcut bar is the sharpest case, because a second mechanism supplies its
answer late: every state application repaints it, the two-second heartbeat
included, so an auto-retrying assertion on what it says goes green on whichever
tick lands inside its budget. A word that is supposed to turn over within the
press is read once, through `shortcut_bar_text`, and never waited for.

Read the event log only after `round_trip`, and read the event a gesture just
made through `sending`; the runtime posts behind the press the driver has
already returned from, so a trip waited on without `sending` can be over before
the gesture's own post exists. Polling the file until one expected event appears
can miss an extra send and cannot distinguish an unresolved request from a
settled one. `round_trip` proves delivery; it does not claim every rendered
effect of the response has completed. When applying the response is the
subject, wait for `data-lf-applied` to cover the expected events. That stamp
counts replayed actions, reports, and undos, and no comment: the fact a comment,
reply, or reaction states is its paint or its card (`test_render_reactions.py`'s
`painted`). After changing a file behind a live page, call `told` before reading
the page.

For layout, animation, and navigation, identify the final fact precisely.
`panel_settled` waits for the requested panel class and nothing past it: the runtime
places the margin and the page's marks against the moved column inside the gesture, so
no frame is left for a read to race, and
`test_closing_the_panel_lands_the_margin_where_the_column_lands` holds that.
`resized` waits for the resize event to reach listeners
and then for one rendering update behind it; the document's own scrolling area is
published in the update after the one the event arrived in. An observer or protocol
record that outlives a motion is read after `moving` says finite motion has ended. An
element-anchored quote can cause an instant document scroll
followed by a smooth scroll, so its first `scrollend` is a real edge but not the
destination; wait for the mark to reach the computed position or for the final
document scroll to stop.

Absence usually has no completion event of its own. Anchor it after the positive
edge that would have caused the forbidden behavior, then read once. If the
mechanism is a watcher or lease that acts only after a grace period, hold a
window derived from that product constant plus scheduling room. Do not invent a
generic sleep for absence assertions.

When a wait times out, its message must say what evidence was missing. `_until`
includes the starting and final `Traffic` readings. Its deadline is fixed when
the wait begins, so a page that repaints its ledger forever cannot extend it. New causal helpers
need the same useful failure output and bounded-progress property.
Pure Python state polls use `interact_support.wait_for`; keep a local loop when
process exit, cancellation, or a deadline shared across transitions is the contract.

## State races are arrangements, not probabilities

If a race appears only on a loaded machine, make the ordering explicit with
`page.route`; do not repeat the test until the machine happens to lose it.
Register the route before the gesture whose request it must catch. For initial
navigation, attach it through `primed` so no request is already in flight.

That rule is about the page. A fact the driver loses on its way out of the
browser is not a page state any route can arrange: `opened_tab` observes the
browser's target list because Playwright can lose the Page for a tab Chromium
opened. Observe the browser's own record rather than repeating the gesture.

Install a hold on the page's first POST before navigation: `held_events`
supplies this for event requests, and `primed` lets a test prepare other routes.
Enabling interception on an already-running page can let that POST reach the
server without a route callback. `open_page` arms each page it makes on a
pattern nothing ever asks for, so a route a test registers later only adds to a
list the browser is already consulting; a page made another way is unarmed.
`held_events` also owns the server fixture ordering: its finalizer releases held
requests before server shutdown rather than resuming them into a closed socket.

A handler that appends a route to `held` has established only that the browser
made the request. Before reading that list — indexing it, asserting its length,
or taking the handler away with `page.unroute`, which leaves a request dispatched
any later to go out unrecorded — wait through `holding`, which is that
sanctioned repeat: the ledger shows the send was made, and the driver call it
repeats is what dispatches the route into this process. Do not wait on the
corresponding `Traffic` edge instead — the ledger counts the send a beat before
the request arrives here, and once it is held nothing repaints, so a wait on the
paint has no second wake-up to catch a route that lands late.

Keep the three route operations distinct:

- Returning from a handler without resolving the route holds the request before
  the server receives it.
- `route.fetch()` lets the server answer but withholds the response from the
  page. The log may advance while the browser remains behind, and the news
  stream still names the append, so a listener for what that read sets off is
  armed before the `fetch`. Where one read has to carry the append and something
  appended after it, hold the reads (`CutOff`) until both are on disk.
- `refuse(route)` cancels a request without manufacturing a console error. Use
  an ordinary abort only when the failed request and its browser error are the
  subject.

A route on `**/api/state*` makes the page deaf but not blind: it leaves the
news stream alone, so a read that failed is asked again two seconds later for
as long as the route stands.

Every hold has a release path. If the verdict depends on a response remaining
lost, make the assertion first, then continue or fulfill the route, wait for the
handler to finish, and remove the route; the fixture closes the page after that.
Put release and `unroute` in cleanup that also runs when the assertion fails. When a handler
calls `route.fetch()`, use `page.unroute_all(behavior="wait")` before teardown,
because the fetched body belongs to that page and ordinary close can dispose it
while a handler is still reading it.

The assertion names the ordering the route created: hold the first POST, make
the second gesture, and inspect `Traffic.sends` before release. The final log
order alone lets the scheduler choose the test's premise. For a stale-state
test, withhold the exact state response that would otherwise reconcile the page
and prove both the page's stale view and the server's newer view before release.

### A test cannot assert over noise it makes itself

Instrumentation must not pollute the channel it later asserts is quiet. Chrome
reports a default aborted request as a console load failure, which is why
`refuse` uses the `aborted` cancellation reason. If a test intentionally
produces an HTTP error, assert the enriched status-and-URL entry collected by
`open_page` instead of filtering it out globally.

A test that stops the page's own server has no way to keep the browser quiet
about it. Bracket the span that makes the noise instead of listing what it says.
`restarting` drops what the page said inside the block, so the fixture's reading
everywhere else remains clean, and a diagnostic the test means to produce is asserted
inside the block that produces it. A filter stated over a whole test's output
takes a new member every time a fetch moves, and it ends up describing the test's
own noise. `test_a_service_that_goes_away_mid_start_says_only_that_and_comes_back`
pins both halves, arranging the interruption rather than waiting for a loaded
machine to produce it.

### A repeated gesture has to let the repaint it causes land

Pressing the same key twice inside one round-trip is not a reader pressing it
twice. Work coalesced into a `requestAnimationFrame` runs between a person's two
presses and between none of a test's, so a fault the repaint itself causes is
invisible at exactly the rhythm a suite presses at. A walk, or any repeated press
a repaint could answer, waits a frame between presses and says why. Where
waiting is what changes the outcome, the contrast is the assertion:
`test_the_walk_reaches_more_and_goes_on_after_the_line_has_repainted` runs one
walk both ways and holds the two to being the same walk, since a count of lost
stops has no honest threshold.

## Distinguish a frame, a sequence, and an instant

Most visual behavior can be tested from stable states before and after a
gesture. The test must cross the transition that could reveal the fault.
Geometry measured twice within one final state proves nothing about motion
between those reads.

A frame is one held state. `HOLD_MOTION` pauses animations so a short-lived
midpoint can remain available while Playwright inspects it. Step or release
every held animation after the assertion so completion handlers run and
teardown is not left waiting. `window.__lfHeld` is what is still held; a motion
the page cancels stays, because a cancelled move is evidence a gesture was taken
back. A gesture on the way to the one under test still has to reach its end
state under that hold, and the harness helper for the gesture owns it:
`edge_settled` finishes a region's arrival slide rather than waiting out a clock the
test has stopped. Opening Threads starts no motion, so `panel_settled` has none to
finish.

A sequence is ordered evidence across frames.
`test_the_fold_never_paints_a_frame_that_undoes_the_last` records every painted
frame inside the page because the browser exposes no durable outside event for
that ordering; the node leaving the list remains the external completion fact.
Use this pattern only when intermediate order is the contract.

An instant is a state that exists within one rendering turn. In
`test_the_room_is_measured_after_a_late_rail`, a `MutationObserver` records
layout when the upgrade stamp changes, before the next frame can restate the
room. The injected observer captures the instant; the stamp is the completion
fact.

Do not substitute frame counts or quiet windows for these distinctions. Ask
whether the claim concerns the settled state, one frame, the order of frames, or
the exact turn of a write, then choose the smallest observation that can
preserve it.

Measure a node the layer rebuilds in one page-side call, resolving it by selector
inside the same evaluation that reads its box. A Playwright locator resolves the
element in one driver call and measures the handle it got in the next, so a paint
landing in between hands back a detached node, whose box reads as all zeros rather
than raising. Drawing marks are the standing case: every paint replaces the whole
drawing layer, and `mark_box` in `test_render_drawing.py` is the reading that
cannot be caught between the two.

The movement tests ask both paths that can shift a target: press a control and
compare the rest of its line, and let news arrive and compare all persistent
chrome controls. A pixel diff is required for borders, outlines, and shadows that
can paint outside unchanged rectangles; box comparisons alone cannot see those
changes.

## Make a green test non-vacuous

For each assertion, state the causal contrast: what single product change would
make it fail? Arrange the fixture so that change reaches the measured surface. A
test that cannot answer this is not yet evidence.

Reintroduce a new defect and run the intended gate before accepting it. For an
existing gate touched by a refactor, repeat the bug-back if the direction or
representation of the failure changed. Bounds and geometry tests are especially
prone to staying green after the fault moves to another edge.

### An absence needs a control and a settled frame

A web-first assertion succeeds on its first satisfying poll, so `to_be_hidden`
on something the runtime has not yet decided to show passes on the frame before
the decision. The runtime raises chrome from deferred steps (`updateFab` runs
inside the mouseup handler's `setTimeout`), so the assertion has to come after
the turn the handler used. The wait is not enough on its own: an absence is also
what a page that never had the behaviour produces, so a test asserting one names
a control that must first produce the presence.

### A sweep that walks controls by index must prove it pressed them

If controls are discovered by index, pin the expected identities or count before
and after reload so a shorter list cannot silently skip work. If a test iterates
registry declarations, assert that the target declaration set is nonempty and
that every expected kind was reached. Avoid conditional assertions whose
condition can disappear with the behavior under test.

An assertion that nothing moved must straddle a transition that would move
without the rule: moving from no pick to one pick exposes a missing reservation
where moving a pick between cards preserves total space. Choose an anchor and a
single-factor neighbor whose difference is the product rule being tested.

Check what a lower layer already guarantees. If the send queue prevents a
second physical POST, counting held routes cannot prove that the widget itself
rejected a second gesture; inspect the later log or visible outcome where the
widget's decision would survive after the queue drains.

The corpus has two causal matrices. A first visit is the anchor for return
state: `arrival_findings` reloads a page with the panel open, a tray standing, or
design mode on and reports motion or failure the first visit did not have. A
static authored state is the anchor for semantic replay: apply standing actions
or reports, reapply them, and verify both the visible state and idempotence.
Keep those matrices declaration-driven so a new widget or event verb joins
through the registry rather than a test-side name list.

Generated markup needs its own gates because the source lint cannot see what a
module writes. The canonical named probes are `undeclaredAttrs` for attributes a
module writes into the author's namespace without a record declaration, and
`relativeReplays` for an action whose second application changes state. Invoke
them through `leaf.render_checks.evaluate_probe` instead of maintaining
test-side variants, and give their fixtures at least one widget and verb that
can trigger the finding.

## Fail with the evidence needed to act

Do not combine `capture_output=True` with `check=True` unless the raised
exception is unpacked and reported. When a test needs the streams for
assertions, run without `check=True`, assert the return code explicitly, and
include both stdout and stderr in the assertion message. When it does not need
them, let the subprocess inherit pytest's captured streams.

An assertion should name the URL, version, widget, event, or traffic counters
that distinguish causes. `open_page` enriches HTTP failures with status and URL;
`round_trip` reports both ends of its wait; a fixture cleanup failure names the
server or process it could not stop.

The `browser` fixture checks collected problems after all gestures, polls, reloads, and
route releases, then closes the remaining contexts. Close a page explicitly only when
the lifecycle or an earlier release matters to the journey. If an earlier fault is
intentionally induced, assert and consume that exact expected entry at the point it
occurs.

Assert durable output as meaning rather than formatter layout. Collapse
whitespace when testing what a page says, use `spoken` when the registry-backed
reading is already available, and match the attribute that carries a markup
claim rather than a complete serialized tag. Reserve exact source and line
assertions for tests whose subject is source structure or a diagnostic
location.
