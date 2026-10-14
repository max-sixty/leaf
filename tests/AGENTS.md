# Testing leaf

Root `AGENTS.md`'s **Stage** says what a test here protects and when to rewrite or
delete one. Agents wrote most of this suite, and many of its tests assert the shape the
code had when they were written rather than behavior a user depends on.

Prove each contract at the lowest boundary that preserves it, and keep a browser test
only where it proves boundaries working together. Before adding cases or steps, choose
the smallest set that exposes distinct plausible failures beyond existing coverage. Keep
a broad sweep only when its extra samples catch a failure that representative states
miss; an investigation's sampling grid is not a regression requirement.

Measure the suite's cost in CPU time. Each run pays it, and the runner time CI bills
follows from it. A test's time beyond its CPU is waiting, and extra workers fill that
wait only while CPU is spare, so remove a fixed delay rather than relying on
parallelism to absorb it. Each CI `test` job's summary says where its CPU and time
went; `leaf-dev suite-profile` prints the same from the job's `pytest-results-*`
artifact. When a browser test is slow, or fails on timing or geometry outside its
contract, repair its setup or move its contract to a lower boundary.

Each helper's docstring owns its contract, and code cites sections here by heading.
Message delivery has one shared journey in `leaf_dev.thread_journey`;
`leaf_dev.thread_snapshots` owns the thread appearance gate built on it.

Linux browser tests use `tests/fonts.conf` and the `fonts-dejavu` package, which must be
installed before `wt setup`; macOS uses its native fonts.

## A failure is evidence about the test too

Before fixing a failing test, name the user-facing behavior its failure caught. If it
caught none, because what the user sees and does is intact and the test broke only on
the shape it read, simplify the test to the behavior it protects, move it to a lower
boundary, or delete it, rather than updating it to the new shape. A test that unrelated
changes keep breaking (`git log -L` shows its history) is the strongest candidate.

A failure that comes and goes on the same code is a defect. Find whether the product
races, so a user could hit it, or the test's setup does (**State races are
arrangements, not probabilities**), and fix that cause.

## Run what the change needs

The host supplies `wt`, `uv`, `jq` 1.6 or newer, Node 22.18 or newer, and the pnpm
version `package.json` pins. `wt setup` installs the browsers, their Linux
dependencies, the example assets and the Node dependencies; `uv run` syncs Python.
Worktrunk starts setup in the background when it creates a worktree; run `wt setup`
before testing to wait for it and see failures. A plain clone starts it with
`wt hook post-start project:setup`.

```sh
wt setup
uv run pytest tests/browser/test_render_widgets.py -q -n0 -k board   # the tests a change needs
pnpm run test:runtime                 # tests/runtime/, under Node
uv run pytest tests                  # broad selection; the landing gate runs it (root AGENTS.md, "Working on the repository")
uv run pytest --lf --lfnf=none -x -n0
uv run pytest --regtest-reset -n0 <node-id>
```

A test's directory under `tests/` is its tier: which boundary it crosses and when CI
runs it (`TIERS` in `conftest.py`):

- **`model/`**: nothing outside pytest, such as projection, admission, page files and
  the CLI run in process. Every run.
- **`process/`**: a real server or subprocess. Every run.
- **`smoke/`**: the browser journeys both landing gates keep. Every run.
- **`browser/`**: a browser, its pages and gestures. Each push to main.
- **`journeys/`**: tests over their directory's time budget, such as restarts, corpus
  sweeps, multi-page journeys and the site build tests. The daily run and manual
  dispatch only.

A test in `model/` or `process/` takes under three seconds on CI's runner, and one in
`browser/` under eight (`BUDGETS` in `leaf_dev/suite_profile.py`). Put a new test in
the directory of the boundary it crosses, or in `journeys/` when it is over budget or
needs the external network, which it also marks `network`. Each `test` job's summary
lists tests over budget, and tend's weekly pass moves them or speeds them up. To move a
test to an earlier tier, make it cheaper. The user chose directory tiers (2026-10-11)
so that the landing gates stop growing with every test.

A subject whose tests cross different boundaries has a module of the same name in each
directory, such as `browser/test_render_margin.py` and `journeys/test_render_margin.py`.
The module holding most of them keeps the helpers, and the others import from it; a
module fixture they share is declared with `name=` and imported as `<name>_fixture`.
`model/` and `process/` run in the same tier, so a subject's tests of both kinds stay in
one module.

Broad discovery skips `browser/` and `journeys/`; `--run-main` adds `browser/` and
`--run-nightly` runs every tier. An explicit directory, file, node id, `-k`, `-m` or
`--lf` runs what it names. Both landing gates pass `--changed-since`, which adds the
later-tier tests whose own source the change edits (`pytest_collection_modifyitems` in
`conftest.py` says what that misses). Tests marked `network` run only when named or
under `--run-nightly`.

### Without external network access

Setup needs the network. After it, `UV_OFFLINE=1` keeps uv on the setup cache; it
doesn't restrict Python or the browsers, and the suite still needs loopback sockets.
To run every tier except the tests that download from external services:

```sh
UV_OFFLINE=1 uv run pytest tests --run-nightly -m 'not network'
```

The same compute limits apply offline: for focused checks, name node ids or use `-k`.

### Selecting checks

Before handing over, run the tests that hold the behavior you changed, in any tier,
by node id or `-k`; find them by reading which tests exercise the changed code. Run
`pnpm run test:runtime` too when the change reaches the runtime.

A change lands through a gate that runs the broad selection: a pull request's `test`
job or `wt merge`'s pre-merge. A failure there that the change causes is the gate doing
its job; fix it and push. A failure the change doesn't cause, such as one main's latest
run also shows (confirm by running it on main by node id), blocks nothing and calls
for no rerun: name it in the pull request as inherited and land. The user chose this (2026-10-13), so `test` is
not a required check on `main`; they want it required again once the suite improves.
`wt merge` refuses on any failure, so such a change lands through a pull request.

CI reports the rest. The `test` job in `ci.yaml` runs the `main` tier once main moves
and every tier daily, and `tend-ci-fix` answers either failing. The user accepted
(2026-10-04) that a pull request can land green and break a test it never ran, and
that main stays red until `tend-ci-fix` repairs it, so a red main is no reason to
widen a change or its tests. Main runs one push suite at a time; a newer commit
replaces the run still waiting, which GitHub shows as cancelled. That is intended. To learn what main fails, read that job's run and
reproduce a failure by node id. `tend-ci-fix` sees only that run, so a failure only
macOS reproduces is left to a local session: check that no session, worktree or open
pull request already covers it, then start one (for example with `/dispatch`).

CLI output and agent-facing text are regtest recordings in each tier's
`_regtest_outputs/`, normalized for temporary paths and generated ids but never for
instruction text. After an intentional change, reset only the affected test and read
the diff.

GitHub Actions on Ubuntu 24.04 is the Linux authority: use the candidate's and base's
workflow runs for Linux evidence, not a local container. The pull request's `test` job
also runs the site build, the Worker dry-run deploy and `verify-site website-worker`;
use local Docker only to reproduce a concrete Worker or container failure.

Subprocess tests invoke leaf through `LEAF_COMMAND`, and `bin/leaf` only where the
launcher itself is the subject.

## Put each assertion at the boundary that owns it

Each test module's docstring names its subject. Put a new test in the module whose
docstring names the behavior it protects, not the one the change happened to open, and
start a module where none does.

File-side fixtures live in `interact_support.py`, browser fixtures in
`render_harness.py`, and reusable browser cases in `render_cases_*.py`.
`tests/runtime/*.test.mjs` tests what one runtime module decides on its own, in the
document `tests/runtime/dom.mjs` sets up; `build/browser/application.test.mjs` tests
how the publisher combines those results. Both build server state with `served.mjs`,
which calls the server's own `served_records.py`, so there is no generated copy to keep
in sync. A fixture carries every field the server sends and changes only the fields the
case is about. `fixtures/pages/` holds full-page regressions under
`examples/AGENTS.md`'s rules.

A result that depends on a platform primitive Node and Chrome implement differently,
such as `Intl.Segmenter`, is tested in the browser suite, however little DOM it
touches.

A property a particular page causes belongs in `render_version`, because
`leaf page check --render` must report it to that page's author. A property identical
for every valid page, such as how the layer restores browser state
(`arrival_findings`), belongs in the suite. A test of a state no authored page reaches,
such as DOM a script changes after load or the open thread panel, puts the page in
that state and calls the probe through `leaf.render_checks.evaluate_probe`.

Where the product already answers a question, use its answer rather than copying it:
`root_overflow` for whether the page scrolls sideways, `draft_key` and `stored_draft`
for drafts, `event_log.read_events` for the log. Read the page through its public
entries, `window.__lfWidgetApi()`, `window.__lfCheckApi()`, `window.__lfClientApi()`,
and `window.__lfOverlayApi()` for overlay geometry; tests can't import private source
paths.

Give a corpus source its own case only when its content is the cause under test. Put a
probe's independent faults on one composed page beside clean controls and call the gate
once. Test a reading made from declarations on a widget that declares them, passed to
`serve` as `layer_registry` and `layer_widgets`.

A test over prose compares it with something the machine states: a shown command
against the click tree, an `x-` key against the guide, a table against its registry.
Leave wording with no machine side to review.

Focus rings show actual focus whatever the input route. Test the shared ring with real
clicks and keyboard arrivals, require `:focus`, and compare the paint. A keyboard
navigation test reaches its stop with `Tab` or its declared command; `element.focus()`
doesn't prove that route. `RELEASE_FOCUS` (`render_harness.py`) resets where Tab
starts, which `blur()` doesn't. Read a ring's paint through `RINGS_DRAWN` and
`ring_faults`, because an ancestor may draw it.

## Fixtures

Every test runs under `isolated_session`, which moves the XDG state and Codex homes,
clears an inherited App Server endpoint, and claims pages under the worker's pid; don't
move `HOME`. Declare other process conditions through fixtures (`sessionless`,
`codex_env`) rather than editing the environment in a test body.

Choose the page fixture by boundary: `serve` for a complete page over real HTTP,
`page_dir` for command-level files, and `ModelPage` with `model_folds.py` for markup and
a log handed straight to admission or `browser_state`. Build markup with `leaf_page`.
`initialized_page` lends one prepared page per composition shape; a test of
initialization runs `page init` itself.

Use the `browser` and `serve` fixtures for ordinary browser tests. Each pytest worker
shares one Playwright driver and Chromium; contexts and page directories keep tests
apart, and fixture teardown cleans up. Start a separate browser or subprocess only when
its engine, configuration, process boundary or lifetime is under test. Raising the
worker count multiplies all of this across every concurrent suite, so it needs a
measured benefit on the shared host.

### Processes and servers

Many suite runs share one machine, so a process a test leaves running, or one that
burns CPU while it waits, slows all of them. A process a test starts ends on every
exit from the test. Take each resource from its owner: a child process from `spawn`, a
page server from `_no_page_outlives_its_test`, a preview from `preview_slot` and
`start_preview`, an HTTP server from `running_http_server`, a socket directory from
`socket_dir` (`test_the_resources_a_fixture_owns_are_taken_from_that_fixture`).
`spawn`'s teardown ends a child and its process group whether the test passes, fails or
is interrupted. A test of a persistent server stops it explicitly.

A dead worker runs no teardown, so a process that would outlive it watches the worker
itself: a page server watches the worker's session claim, and a held process blocks
reading a pipe the worker holds, as `session_process` does. The test releases it by
closing the pipe, which also closes when the worker dies. Don't make a process wait
for a file the test has yet to write, or poll in a loop. End a process by closing its
pipe or with SIGTERM, never SIGKILL (`test_no_test_ends_a_process_with_sigkill`). To
check a new held process, make the test fail right after starting it, then confirm with
`pgrep -fl <tmp_path>` that nothing it started still runs.

### Reloading is not resetting

Panel state and drafts live in `localStorage`, reading position in `sessionStorage`;
clear both for a first visit. Each `Browser.new_page` is its own context, so two tabs of
one user share `one_user`.

## Driving the browser

Drag selections with `select`; a synthetic `dispatchEvent` skips the event sequence the
runtime listens to. `locator.click()` scrolls its target into view, so where a press's
effect on scroll is the subject, scroll first and read the baseline after.

Inject nothing to make observation easier: read traffic from the runtime's own ledger,
set network conditions with `page.route`, and collect errors with the browser fixture.
Use an init script only to record a sequence or an instant ("Frames, sequences, and
instants"). A gate test whose page is meant to be faulty passes `browser.unwatched`,
because `render_version` reports the page's errors as findings.

### Browser errors

The `browser` fixture watches every page it makes and fails the test on any problem
left at the end; don't install a second collector. Each problem is a record
(`leaf/findings.py`). Consume an expected one where it happens with
`consume_browser_errors`, or `reported_browser_errors` when it arrives in parts, naming
it by its fields (`{"code": "failed-load", "status": 400}`) or by a fragment of the
console message (`render_harness.is_problem`). For a recurring fault, close the page
first and then consume. Filtering the collector is not an assertion.

Three watches report problems; a fourth, `input_work_watch.js`, tells them which input
caused a change. Fix what they report rather than consuming it; there is no per-test
allowance list.

- `write_watch.js` reports a DOM write that changes nothing. Fix the writer with
  `runtime/keeps.js`. A write that must restate, as a vendored component's does, joins
  `EXPECTED` in `write_watch.js` with its reason; a test that reads the page by changing
  it and putting it back does so inside `lfUnwatched`.
- `shift_watch.js` reports a box that moves on screen without input, and typing that
  moves its field (`skills/leaf/assets/AGENTS.md`, "Stability"). It runs on every test
  except those in modules marked `shifts_unsurveyed`, which opt in per test with
  `watch_shifts`. Playwright's clicks, keys and viewport resizes are input; a script's
  `click()`, a value set by script and server news are not. It ignores first
  presentation, whose remaining defects `known_widget_findings.py` records. Chrome
  hides a shift for half a second after a click, so a test of a news update's stability
  delivers the news after that.
- `words_watch.js` reports typed words leaving the screen without a key or press
  ("Words stay where they were typed"). A test that closes a box does it the way a user
  does.
- `input_work_watch.js` attributes each change to the input whose work caused it, so
  the shift and words watches can tell a reaction from an unprompted move. It follows
  timers, frames, promises and Lit updates, but not a native `await`: code that commits
  a visible effect after an `await` loses its input. Leaf's draft sends put the words
  away before awaiting delivery for this reason; a test fixture that must commit after
  an `await` captures the commit callback with `lfInputWork.capture` first.

A live sample talks to its parent page over a private `MessagePort`. The watches follow
input across that channel because each end sets the port as `lfDocumentPort` on its
bootstrap script element before the first message (`bootstrap.js`, `sample.js`). A new
private channel between documents does the same; other ports, such as an authored
Worker's, carry no input.

Leaf's own widgets are held to the widget quality report `package check --render` gives
a package's author (`leaf/render_gate/widget_quality.py`): `test_widget_quality.py`
runs it over the base layer and every bundled package. `known_widget_findings.py` lists today's findings,
each a defect awaiting a fix. A new finding fails the test, and so does an entry that
no longer occurs, so fixing a widget deletes its entry.

## A page is ready when it says what has finished

Open pages through `open_page`, and call `wait_until_ready` (`leaf.render_checks`)
after any manual navigation. It waits on the runtime's one readiness signal,
`pageReadiness`; network quiet implies none of its stages, and a key pressed before
replay can be lost silently. Never combine the stamps yourself or wait for a deferred
widget by name. To measure a page before its runtime starts, call `displayed` first.

## Waits

### Functional results do not depend on execution speed

A functional test must give the same result, and still exercise the situation it
claims to cover, when the system runs ten times slower. This applies to fixtures and
watches too. Test performance separately, under controlled conditions.

Control or advance the clock that decides an age, lease, grace period or timer. A
fixed `Date.now()` doesn't stop timers, animation frames, paint or observer delivery;
control the mechanism the assertion depends on. Bound hangs with real deadlines that
leave room for slow execution, and on expiry report which completion is still missing.

Wait for the operation's own completion signal. A sleep doesn't prove that another
process took a lock or finished a scan; `interact_support.lock_contention` reports that
a second taker found the lock held and is waiting. A time limit must never turn
unfinished work into a pass. To test a race, hold and release the request, callback,
frame or lock explicitly, check that the outcome holds with completion delayed tenfold,
and keep a control that still fails. Longer sleeps and more retries don't fix a missing
completion signal.

### Completion comes from the operation

Elapsed time, matching samples, a fixed number of frames and network quiet all look the
same for an effect that hasn't started as for one that has finished. Wait on a fact the
system states instead; count frames (`one_frame` in `leaf.render_checks`) only where
one rendering update is itself the claim. A computed style under a transition reports
the animated value, so check `getAnimations()` where the subject may be moving.
`page.evaluate` takes no timeout: state readiness in the page and poll it with
`wait_for_probe`.

Every Python-side wait takes its deadline from `STATED_TIMEOUT`, and pure-Python polls
use `interact_support.wait_for`. Browser waits use `SERVED_TIMEOUT_MS`, which
`render_harness` makes the default for every Playwright wait and `expect`, so a wait
names a deadline only when it spans a page handover (`HANDOVER_DEADLINE_MS`).
`test_a_wait_takes_the_suites_deadline` checks both. A call with no deadline, such as
`page.evaluate`, is bounded only by the per-test limit in `pyproject.toml`, which ends
the worker after half an hour.

### Transient states

Use `expect(...)` for a state that becomes stable. For a transient one, read once after
the step that causes it has finished: an auto-retrying assertion passes on the first
matching frame even if the gesture goes on to another result. The helpers in
`render_harness.py`:

- `sending` wraps a gesture whose own event the next read needs;
- `round_trip` waits until everything sent has been delivered, not applied;
- `told` waits until the page has applied what the server holds now; call it after
  changing a file behind a live page;
- `nudge` gives the page a reason to read; `ticked` waits for its next tick;
- `undo` presses `z` once it is offered and waits for the undo's round trip;
- `rendered` (`leaf.render_checks`) waits for every repaint the input so far queued,
  and `shortcut_bar_text` reads the bar once after it;
- `panel_settled`, `edge_settled` and `resized` wait for their motion to end, and
  `scroll_settled` (`leaf_dev.browser`) for a scroll's.

Wait for something the gesture itself changes. An empty highlight or an optimistic
`pending:` card satisfies an assertion too early; wait for painted ranges
(`wait_for_pending_mark`) or the admitted comment's id. Where applying the server's
response is the subject, wait for `data-lf-applied`, which counts only actions,
reports and undos; observe a comment, reply or reaction by its paint. Wait for `rendered` between
repeated presses a repaint could answer, and before `scroll_settled`, check that the
scroll started.

## State races are arrangements, not probabilities

If a race appears only under load, order it with `page.route` rather than repeating the
test. `leaf-dev flake` (`dev/AGENTS.md`) reproduces it and prints each failing copy's
message, which names the mechanism, and then confirms the route holds. Register the
route before the gesture it catches, or through `primed` or `held_events` for the first
navigation; raw and `browser.unwatched` pages aren't set up for later routes. Where
the driver loses a fact, such as the Page for a tab Chromium opened, read the
browser's record (`opened_tab`).

- A route handler that returns without resolving holds the request before the server.
  Call `holding` before reading the list of held requests, since the ledger counts a
  send before the handler runs. Release a held request mid-test only when later
  behavior is asserted; closing the context cancels the rest.
- `route.fetch()` lets the server answer and withholds the response. Freshness reads
  still name the append, so attach listeners before the fetch. Call
  `page.unroute_all(behavior="wait")` after releasing held routes; in failure cleanup
  that may still hold requests, use `behavior="ignoreErrors"`, and closing the context
  cancels them.
- `refuse` cancels a request without a console error. A route that keeps refusing
  `**/api/state*` causes endless retries, so use `CutOff` to hold state reads.

Assert the order the route created, such as `Traffic.sends` before release. Name an
event by what the append returned (`append_event`, a model command, a CLI write's
printed record), since the log's last event may be a `read` an open page appended.

### Test-made noise

Instrumentation must not add noise to the channel a test asserts is quiet; `refuse`
uses the `aborted` reason for that. Assert a deliberate HTTP error through the
collector's status-and-URL entry, and wrap a deliberate server restart in
`restarting`, asserting any diagnostic inside that block.

## Frames, sequences, and instants

A test must cross the transition that could reveal the fault; two reads of one final
state say nothing about the motion between them.

- A frame is one held state. `HOLD_MOTION` pauses animations and `__lfHeld` lists what
  is paused; step or release each after the assertion.
- A sequence is ordered evidence across frames, recorded in the page only when the
  intermediate order is the contract.
- An instant exists within one rendering turn, such as layout when a stamp changes; a
  page-side observer captures it, and the stamp marks completion.

Measure a node the runtime rebuilds in one page-side call that finds and reads it; a
detached node measures as zeros. A movement test covers a press and arriving news, with
a pixel diff for borders, outlines and shadows.

## Make a green test non-vacuous

Name the one product change that would make each assertion fail, and set up the fixture
so that change reaches what is measured. An assertion that nothing moved spans a
transition that would move without the rule. Check what a lower layer already
guarantees: a send queue that drops a second POST hides whether the widget refused it.

These checks run on every corpus page, so a new widget or page is covered without a
case of its own:

- `arrival_findings`: state restored on return matches a first visit.
- Replay: applying the actions and reports in force twice to a static authored state
  gives the same visible state.
- `scroll_writes`: no value is written on every scroll step.
- `at_rest`: a page left alone does nothing.
- Round trips: opening and closing a surface leaves the same `reader_state` (content,
  geometry, control values, focus, caret) and doesn't grow `live_counts`. A new
  surface joins by its keys.
- Resize: each width shows what it showed before.
- Typed boxes: scrolling every scroller to either end and back keeps each open box's
  words. A new box joins by its route.

The last four run on a `still_page`, whose reduced motion and fixed date keep age labels
stable. Probes of generated markup (`undeclaredAttrs`, `relativeReplays`) run on
fixtures that can trigger them.

### Absences

An absence asserted before the runtime's deferred step passes on the frame before the
decision. Read it once, after the step that would have caused the forbidden behavior,
and keep a control that first produces it.

### Sweeps over controls

Pin the ids or count a sweep walks, before and after any reload, and assert that the set
is non-empty and every expected kind was reached. Avoid a conditional assertion whose
condition can vanish with the behavior.

## Failure messages

Pair `capture_output=True` with `check=True` only when the exception is unpacked; a test
that needs the streams asserts the return code and puts stdout and stderr in the
message. Assert output by meaning: use `spoken` for the registry-backed reading, and
match the attribute that carries a claim.
