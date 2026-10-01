# Testing leaf

A test here is evidence about behavior a user depends on. Under root `AGENTS.md`'s
**Stage**, the suite does not constrain new code: rewriting or deleting an overfit
test is an ordinary part of a change, and the commit says which behavior moved.

Prove each contract at the lowest boundary that preserves it, and keep a browser test
only where it proves boundaries working together. When a high-level browser test is
slow, or fails on timing or geometry outside its contract, repair its arrangement or
move its contract to the lower boundary.

Each helper's docstring owns its contract, and code cites sections here by heading.

## Run the narrowest useful surface

The host supplies `wt`, `uv`, `jq` 1.6 or newer, Node 22 or newer, and Docker for the
complete website boundary only. `wt setup` installs Playwright's Chromium headless
shell, WebKit, and Chrome, the example assets, and the npm trees; `uv run` syncs
Python.

```sh
wt setup
uv run pytest tests                  # everyday gate; no network after setup
npm run test:runtime                 # the gate's other half: tests/runtime/, under Node
uv run pytest tests/test_render_widgets.py -q -n0 -k board   # one case, kept local
uv run pytest --lf --lfnf=none -x -n0
uv run pytest --regtest-reset -n0 <node-id>
```

Mark a test `nightly` when a pull request can land without it, including any test that
needs the network; expense alone does not make a test nightly. Broad discovery skips
nightly tests, and an explicit file, node id, `-k`, `-m`, or `--lf` runs what it
names. Both landing gates pass `--nightly-changed-since`, which adds the nightly tests
whose own lines the change edits.

A change lands only on a green landing gate. Every other nightly test is CI's to
report: the `test` job in `ci.yaml` runs the complete suite once main moves, and
`tend-ci-fix` answers what it fails. So before handing over a browser-facing change,
run the everyday gate and the few browser tests that hold the behavior you changed,
named by node id or `-k`. Don't run `--run-nightly`, `-m nightly`, or a whole browser
file locally: each takes minutes to over an hour and slows every other session on the
machine. To learn what main fails, read that job's run, and reproduce a failure it
names by node id.

CLI output and agent-facing text are regtest recordings in
`tests/_regtest_outputs/`, normalized for temporary paths and generated identities but
never for instruction text. Review the affected recordings when changing interaction
guidance, and after an intentional change reset only the affected test and read the
diff.

GitHub Actions on Ubuntu 24.04 is the Linux authority. Use the candidate's and base
SHA's workflow runs for Linux-specific evidence; a local container is not that runner.

Subprocess tests invoke leaf through `LEAF_COMMAND`, and `bin/leaf` only where the
launcher itself is the subject.

## Put each assertion at the boundary that owns it

File-side fixtures live in `interact_support.py`, browser fixtures in
`render_harness.py`, reusable browser cases in `render_cases_*.py`.
`tests/runtime/*.test.mjs` holds what one runtime module decides on its own, in the
document `tests/runtime/dom.mjs` puts up; `build/browser/application.test.mjs` owns
the publisher's composition of those folds. Both build served threads and workflows
with `served.mjs` from what `served_records.py` folds through the server: a record
that carries every field the server sends, with only the fields a case is about
changed, or a whole reading where the case rests on how the server relates them.
`fixtures/pages/` holds full-page regressions under `examples/AGENTS.md`'s rules.

A fold whose result rests on a platform primitive that differs between Node and
Chrome, such as `Intl.Segmenter`, is a browser fact: its test stays in the browser
suite however little DOM it touches. Ask both engines rather than reading the module.

A property caused by a particular page belongs in `render_version`, because `version
check --render` must report it to that page's author. A property identical for every
valid page, such as how the layer restores browser state (`arrival_findings`), belongs
in the suite. The render gate never opens the thread panel, so the suite opens it and
puts the gate's geometry readings to it, asserting each population and planting a
fault there first.

A render-gate test calls `render_version`, not one of its probes. Where the product already answers a reading's question, such as `shownBand` for the
band a box shows, consume that answer instead of copying it: `root_overflow` for
whether the page scrolls sideways, `draft_key` for where a draft is stored, and
`event_log.read_events` for what the log holds. Page-side code reaches a runtime
module through `window.__lfRuntimeImport`; a bare `/runtime/…` import loads a second
instance that shares none of the page's module state.

A corpus source gets its own case only when its content is the cause under test. Put
a probe's independent faults on one composed page beside clean controls, assert the
populations, then call the public gate once. A reading the layer makes from
declarations runs on a widget that declares them, passed to `serve` as
`layer_registry` and `layer_widgets`, rather than borrowing a shipped tag.

A test over prose compares it with something the machine states: a shown command
against the click tree, an `x-` key against the guide, a table against its registry.
Leave wording with no machine side to review.

Focus evidence starts in keyboard modality: press `Tab` to the exact stop and require
`:focus-visible`, or `:focus` on the runtime's text field (`leaf-text`), a host that
delegates focus and so never matches `:focus-visible` in Chrome; `element.focus()` alone
is not that evidence.
`RELEASE_FOCUS` (`render_harness.py`) resets the sequential starting point; `blur()` keeps
it; `document.body.focus()` does nothing, since body holds no stop. Read
a ring's actual paint through `RINGS_DRAWN` and `ring_faults`, because an ancestor or
linked carrier may draw it.

## Fixtures own the world they create

Every test runs under `isolated_session`, which moves only the XDG state home and
claims pages under the worker's pid; do not move `HOME`. Declare other process
conditions through fixtures (`sessionless`, `codex_env`) rather than editing the
environment in a test body.

Choose the page fixture by boundary: `serve` for a complete page over real HTTP,
`page_dir` for command-level files, `ModelPage` and `model_folds.py` for markup and a
log put straight to admission or `browser_state`. Build fixture markup with
`leaf_page`, and write a raw document only when source structure is the subject.
`initialized_page` lends one prepared page per composition shape, with runtime and
vendor hard-linked into it; a test of initialization crosses `page init` itself.

### A process the suite starts ends with the run

Take each resource from its owner: a child process from `spawn`, a page server from
`_no_page_outlives_its_test`, a preview from `preview_slot` and `start_preview`, an
in-process HTTP server from `running_http_server`, a Unix socket directory from
`socket_dir`. `test_the_resources_a_fixture_owns_are_taken_from_that_fixture` enforces
this. A test of a standing server stops it explicitly, and a `Popen` handle alone does
not own a detached server's tree. A cleanup fixture takes the state home from
`isolated_session`'s value and sweeps only it and `tmp_path`.

### Reloading is not resetting

Panel state and drafts live in `localStorage`, reading position in `sessionStorage`;
clear both for a first visit. Each `Browser.new_page` is its own context, so two tabs
of one user share `one_user`.

## Drive the browser a user gets

Drag selections with `select`; a synthetic `dispatchEvent` skips the event
sequence the runtime listens to. `locator.click()` scrolls its target into view, so where the
subject is a press's effect on scroll, scroll it into view first and read the baseline
after.

Inject nothing to make observation easier. Traffic comes from the runtime's own
ledger, network conditions from `page.route`, errors from the browser fixture. An init
script is justified only to record a sequence or an instant (see "Distinguish a frame,
a sequence, and an instant"), and completion still comes from a fact visible outside
the page. A page the product opens for itself is the product's: `render_version`
reports its errors as findings, so a gate test whose page is meant to be faulty hands
over `browser.unwatched`.

### Consume a browser error where it is caused

The `browser` fixture instruments every page it makes and fails the test on any
problem left at the end; do not install a second collector. Consume an expected fault
at its causal point with `consume_browser_errors`, or `reported_browser_errors` when
its report arrives in parts. For a recurring fault, close the page first and then
consume. Otherwise close a page only when closing is part of the journey. Filtering
the collector is not an assertion.

A DOM write that changes nothing is one of those problems (`write_watch.js`): a value
restated where it already stands, or a place one script takes away and puts back. Fix
the writer (`runtime/keeps.js`). A write that restates for a reason of its own, as a
vendored component or a focus borrow does, joins `EXPECTED` in `write_watch.js` with
that reason. A test that reads the page by changing it and putting it back does so
inside `lfUnwatched`.

A layout shift the "Stability" rule in `skills/leaf/assets/AGENTS.md` forbids is one
of those problems (`shift_watch.js`): a box that moves on screen without input, and
typing that carries the field it types in, so every test in the broad selection checks
both. Surveyed nightly tests opt in with `watch_shifts`; the rest await a fresh survey
after the widget prepaint fixes (`known_faults.watches_shifts`). The watcher still
exempts first presentation, whose remaining defects the widget quality check records
in `known_widget_findings.py`. Playwright's clicks and keys are input, as is a
viewport resize; a script's `click()`, a `value` written by script, and the server's
news are not, even in the half second after a click, so a test delivers news whenever
its story does. Fix what moved rather than consuming
the report. `known_faults.py` names the tests whose pages still shift without input,
each with the region its known shift moves: a defect waiting on its fix, whose entry
goes when it is fixed.

Typed words leaving the screen without a key or press, which the "Words stay where
they were typed" rule forbids, is one too (`words_watch.js`), in every test, nightly
included. A key that typed is editing rather than putting away, and a scroll, a
resize, a script, and the server's news are none of them, so a test that closes a box
must do it the way a user does. `known_faults.py` names the tests whose pages still lose
words, each a defect waiting on its fix.

Leaf's own widgets are held to the widget quality report `package check --render`
gives a package's author (`leaf/render_gate/widget_quality.py`):
`test_widget_quality.py` runs it over the base layer and every bundled package.
`known_widget_findings.py` lists today's findings by package, tag and check, each a
defect waiting on its fix. A finding it does not list fails the test, and so does an
entry that no longer occurs, so fixing a widget deletes its entry and the list only
shrinks.

## A page is ready when it says what has finished

Open pages through `open_page`, and call `wait_until_ready` (`leaf.render_checks`)
after any manual navigation. It waits on the runtime's one readiness reading
(`pageReadiness`): upgrade, replay, an `/api/state` answer the caller holds
presented whole, current presentation, deferred arrivals, and settled rendering, in
that order. `told` holds the answer the server gives now and asks only through the
`state` stage, so it also answers behind a page held mid-gesture. They are independent facts, network quiet implies
none of them, and a key pressed before replay can be lost silently. Never combine the
stamps yourself, and never wait for a fixture's deferred widget by name; the arrived
stage covers work an owner declares after presentation. Call `displayed` before a
pre-runtime measurement.

## A wait consumes a fact the system states

Elapsed time, matching samples, a fixed count of animation frames, and network quiet
all describe a page that has not started an effect as well as one that has finished
it. Wait on a fact the system states instead; count frames (`one_frame` in
`leaf.render_checks`) only where one rendering update is itself the claim. A computed style under a transition
reports the animated value, so ask `getAnimations()` where the subject may be in
transit. `page.evaluate` takes no timeout; state readiness synchronously in the page
and poll it with `wait_for_probe`.

An absence that rests on a mechanism acting only after a grace period holds a window
derived from that product constant plus scheduling room.

A new wait fixes its deadline when it begins and names the missing evidence on
timeout. Pure-Python state polls use `interact_support.wait_for`.

### A state the page passes through is not a state to poll for

Use `expect(...)` for a state that becomes stable and stays true. For a transient one,
read once after the causal edge has completed; an auto-retrying assertion returns on
the first matching frame even if the gesture goes on to another result. The edge
helpers in `render_harness.py`:

- `sending` encloses a gesture whose own event the next read needs;
- `round_trip` waits for delivery of everything sent, not for its application;
- `told` waits until the page has applied what the server holds now;
- `nudge` gives the page a reason to read; `ticked` waits for its next tick;
- `undo` presses `z` once it is offered and waits for the withdrawal's trip;
- `rendered` (`leaf.render_checks`) waits for every repaint the input so far queued,
  and `shortcut_bar_text` reads the bar once after it;
- `panel_settled`, `edge_settled`, `resized`, and `scroll_settled` end one kind of
  motion.

Choose a completion fact the gesture changes. An empty highlight registration or an
optimistic `pending:` card satisfies an assertion early; wait for painted ranges
(`wait_for_pending_mark`) or an admitted comment's durable identity. Read the event
log after `round_trip`, and a gesture's own event through `sending`. Where applying
the response is the subject, wait for `data-lf-applied`, which counts actions,
reports, and undos; observe a comment, reply, or reaction by its paint. After changing
a file behind a live page, call `told` before reading it.

Wait for `rendered` between repeated presses a repaint could answer; where waiting
changes the outcome, run the gesture both ways and assert they agree. Before
`scroll_settled`, observe that the gesture started its scroll.

## State races are arrangements, not probabilities

If a race appears only under load, order it with `page.route` rather than repeating
the test. `leaf-dev flake` (`dev/AGENTS.md`) reproduces it and prints every failing
copy's message, which differs run to run and names the mechanism; the same run then
confirms the route holds. Register the route before the gesture it catches, or through `primed` or
`held_events` for the first navigation; raw and `browser.unwatched` pages are not
armed for later routes. Where the driver loses a fact, such as the Page for a tab
Chromium opened, observe the browser's record (`opened_tab`).

- A handler that returns without resolving holds the request before the server. Call
  `holding` before reading its list, since the ledger counts a send before the handler
  runs. Release it mid-journey only when later behavior is asserted; context closure
  cancels the rest, and a teardown release could reach a stopped server.
- `route.fetch()` lets the server answer and withholds the response. The news stream
  still names the append, so arm listeners before the fetch, and call
  `page.unroute_all(behavior="wait")` before teardown even when the test fails.
- `refuse` cancels without a console error; use a plain abort only when the error is
  the subject. A standing refusal of `**/api/state*` keeps producing retries, and
  `CutOff` holds state reads across a stale-state journey.

Assert the ordering the route created, such as `Traffic.sends` before release, and for
a stale state prove both the page's view and the server's newer one. Name an event
from what the appending door returned (`append_event`, a model command, a CLI write's printed record); the
log's tail may be a `read` an open page appended.

### A test cannot assert over noise it makes itself

Instrumentation must not pollute the channel it asserts is quiet, which is why
`refuse` uses the `aborted` reason. Assert a deliberate HTTP error through the
collector's status-and-URL entry. Wrap a deliberate server interruption in
`restarting`, and assert any diagnostic under test inside that block.

## Distinguish a frame, a sequence, and an instant

A test must cross the transition that could reveal the fault; two reads within one
final state say nothing about the motion between them.

- A frame is one held state. `HOLD_MOTION` pauses animations and `__lfHeld` lists what
  is still held; step or release each after the assertion.
- A sequence is ordered evidence across frames, recorded inside the page only when
  intermediate order is the contract.
- An instant exists within one rendering turn, such as layout when a stamp changes; a
  page-side observer captures it and the stamp marks completion.

Measure a node the layer
rebuilds in one page-side call that resolves and reads it; a detached node reads as
zeros. A movement test covers a press and arriving news, with a pixel diff for
borders, outlines, and shadows.

## Make a green test non-vacuous

Name the single product change that would make each assertion fail, and arrange the
fixture so that change reaches the measured surface. An assertion that nothing moved
straddles a transition that would move without the rule. Check what a lower layer
already guarantees: a send queue that drops a second POST hides whether the widget
refused it.

The corpus has these matrices. Return state is anchored on a first visit
(`arrival_findings`); semantic replay is anchored on a static authored state, applying
standing actions or reports twice and checking the visible state and idempotence; a
scroll's writes (`scroll_writes`, read by `scroll_followers`) fail where a place is
written on every step; a page left alone (`at_rest`) fails anything it does; a
surface's round trips fail where one leaves a different `page_state` than the first,
or `live_counts` climb on every trip; a resize fails where a width says something
other than it said on the way out; and a box the user types in fails where sending
every scroller to either end and back loses its words. The last four read a
`still_page`, whose reduced motion and stopped clock leave only what the test did.
All of them run on every corpus page, so a new widget or page joins without a case of
its own; a new surface joins the round trips by its keys, and a new box the typed
boxes by its route. Run generated-markup probes (`undeclaredAttrs`,
`relativeReplays`) through
`leaf.render_checks.evaluate_probe` on fixtures that can trigger them.

### An absence needs a control and a settled frame

An absence asserted before the runtime's deferred step passes on the frame before the
decision. Anchor it after the positive edge that would have caused the forbidden
behavior, read once, and name a control that first produces the presence.

### A sweep that walks controls by index must prove it pressed them

Pin the identities or count a sweep walks, before and after any reload, and assert a
loop's declaration set is nonempty with every expected kind reached. Avoid a
conditional assertion whose condition can vanish with the behavior.

## Fail with the evidence needed to act

Pair `capture_output=True` with `check=True` only when the exception is unpacked. A
test that needs the streams asserts the return code and puts stdout and stderr in the
message. Assert output by meaning: use `spoken` for the registry-backed reading,
and match the attribute carrying a claim.
