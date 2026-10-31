# Testing leaf

This suite protects shipped Leaf behavior. Tests of developer tools belong in
`dev/tests/` (`dev/AGENTS.md`, "Tests"). A product test may still use `leaf_dev` to
build or serve its fixture, since what a test proves decides where it belongs, not what
it imports. A check
that holds a product schema's consumers to it, eval fixtures included, lives here,
because a change to the schema is what breaks it. PR CI time is scarce: add coverage
there only for consequential product failures that should block landing, however quick
the check.

Root `AGENTS.md`'s **Stage** says what a test here protects and when to rewrite or
delete one. Agents wrote most of this suite, and many of its tests assert the shape the
code had when they were written rather than behavior a user depends on.

Prove each contract at the lowest boundary that preserves it, and keep a browser test
only where it proves boundaries working together. Add only the cases that expose
distinct plausible failures beyond existing coverage; an investigation's sampling grid
is not a regression requirement.

The suite's cost is CPU time, which every run pays and CI bills. Extra workers fill a
test's waiting only while CPU is spare, so remove a fixed delay rather than relying on
parallelism. Each CI `test` job's summary says where its CPU and time went, and
`leaf-dev suite-profile` reads the same from the job's `pytest-results-*`
artifact. When a browser test is slow, or fails on timing or geometry outside its
contract, repair its setup or move its contract to a lower boundary.

Each helper's docstring owns its contract, and code cites the sections below by heading.
Message delivery has one shared journey, `leaf_dev.thread_journey`.

## Failing tests

Before fixing a failing test, name the user-facing behavior its failure caught. If it
caught none, because the test broke only on the shape it read, simplify it to the
behavior it protects, move it to a lower boundary, or delete it. A test that unrelated
changes keep breaking (`git log -L`) is the strongest candidate. A failing browser
test leaves a picture of each page it held in `.tmp/test-results/screens/`, which CI
uploads; look at it before reading the cause off the assertion alone.

A failure that comes and goes on the same code is a defect. Find whether the product
races, so a user could hit it, or the test's setup does ("Races"), and fix that cause.

## Run what the change needs

The host supplies `wt`, `uv`, `jq` 1.6 or newer, Node 22.18 or newer, and the pnpm
version `package.json` pins. `wt setup` installs the browsers, their Linux
libraries and fonts, the example assets and the Node dependencies, and waits for the
preparation Worktrunk starts in a new worktree; run it before testing. `uv run` syncs
Python. Tend agents run tests directly in their prepared environment, since setup's
system packages need privileges the sandbox lacks.

```sh
uv run pytest tests/browser/widgets/test_boards.py -q -n0 -k lifecycle
pnpm run test:runtime                 # tests/runtime/, under Node
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
  sweeps, multi-page journeys and the site build. The daily run and manual dispatch.

A test in `model/` or `process/` takes under three seconds on CI's runner, and one in
`browser/` under eight (`BUDGETS` in `leaf_dev/commands/suite_profile.py`). Put a new test in
the directory of the boundary it crosses, or in `journeys/` when it is over budget or
needs the external network, which it also marks `network`. To move a test to an earlier
tier, make it cheaper.

A subject whose tests cross different boundaries has a module of the same name in each
directory, such as `browser/test_render_aim.py` and `journeys/test_render_aim.py`, and
the module holding most of them keeps the helpers. `model/` and `process/` share a tier,
so a subject's tests of both kinds stay in
one module.
A subject too large for one module is a package with a module per behavior, such as
`browser/margin/`.

Broad discovery skips `browser/` and `journeys/`; `--run-main` adds `browser/` and
`--run-nightly` runs every tier. An explicit directory, file, node id, `-k`, `-m` or
`--lf` runs what it names. Both landing gates pass `--changed-since`, which adds the
later-tier tests whose own source the change edits (`pytest_collection_modifyitems` in
`conftest.py` says what that misses). Tests marked `network` run only when named or
under `--run-nightly`.

### Without external network access

After setup, `UV_OFFLINE=1` keeps uv on its cache; the suite still needs loopback
sockets. This runs every tier except the tests that download from external services:

```sh
UV_OFFLINE=1 uv run pytest tests --run-nightly -m 'not network'
```

### Selecting checks

Find the tests that hold the behavior you changed, in any tier, and run them by node
id or `-k`. Search for consumers of the changed API, selector or shared primitive,
including tests whose files the change leaves untouched. Exercise its transitions as
well as its resting states: a shared row can fit each occupant and still resize when
one replaces another. Keep the selection focused on the plausible failures the change
introduces, within the local limits in root `AGENTS.md`.

When an intentional behavior change replaces an expectation, update the affected
tests in that change, preserving the user guarantees they still protect. The PR gate
selects later-tier tests by edits to their own source, so its passing result alone
does not establish that unchanged consumers still work.

A change lands through a gate that runs the broad selection: a pull request's `test`
job or `wt merge`'s pre-merge. A failure there that the change causes is the gate doing
its job; fix it and push. A failure the change doesn't cause, such as one main's latest
run also shows (confirm by running it on main by node id), blocks nothing and calls
for no rerun: name it in the pull request as inherited, check that it has an owner
(below), and land. For now, by the user's choice, `test` is not a required check on
`main`.
`wt merge` refuses on any failure, so such a change lands through a pull request.

Tend repairs what CI (`ci.yaml`) fails on main: the `test` job on Ubuntu, and
`test-macos`, which runs every tier on macOS in the daily scheduled run and a dispatch.
A failed run opens or updates a `tend-ci-failure` report issue, and triage files a
`tend-ci-cause` issue for each cause and fixes it there.
The user accepted that a pull request can land green and break a test it never ran, so
a red main is no reason to widen a change or its tests. A newer push cancels main's
waiting run, as intended. To learn what main fails, read that job's run and reproduce a
failure by node id.

A failure on main, in that run or only in a local one, needs an owner. Tend owns one
that main's latest run shows, through the open report for that run and the cause issue
or pull request that names it. A failure only a local run shows is beyond it. For a
failure Tend doesn't own, check that no session, worktree
(Codex's under `~/.codex/worktrees` included) or open pull request covers it, then start
a local session for it (for example with `/dispatch`).

CLI output and agent-facing text are regtest recordings in each tier's
`_regtest_outputs/`, normalized for temporary paths and generated ids but never for
instruction text. After an intentional change, reset only the affected test and read
the diff.

GitHub Actions on Ubuntu 24.04 is the Linux authority: use the candidate's and base's
workflow runs for Linux evidence, not a local container. A pull request's `test` job
also runs the website's delivery checks (root `AGENTS.md`, "Working on the repository");
use local Docker only to reproduce a concrete Worker or container failure.

Subprocess tests invoke leaf through `LEAF_COMMAND`, and `bin/leaf` only where the
launcher itself is the subject.

## Put each assertion at the boundary that owns it

Put a new test in the module whose
docstring names the behavior it protects, not the one the change happened to open, and
start a module where none does.

File-side fixtures live in `interact_support.py`, browser fixtures in
`render_harness.py`, and reusable browser cases in `render_cases_*.py`.
`tests/runtime/*.test.mjs` tests what one runtime module decides on its own, in the
document `tests/runtime/dom.mjs` sets up; `framework-application.test.mjs` there tests
how the framework's publisher combines those results. Both build server state with `served.mjs`,
which calls the server's own `served_records.py`. A fixture carries every field the
server sends and changes only the fields the
case is about. `fixtures/pages/` holds full-page regressions under
`examples/AGENTS.md`'s rules, and `fixtures/plain/` ordinary web pages
(`browser/test_plain_pages.py`).
A result that depends on a primitive Node and Chrome implement differently, such as
`Intl.Segmenter`, is tested in the browser.

A property a particular page causes belongs in `render_version`, because
`leaf page check --render` must report it to that page's author. A property identical
for every valid page, such as how the layer restores browser state
(`arrival_findings`), belongs in the suite. A test of a state no authored page reaches,
such as DOM a script changes after load, puts the page in
that state and calls the probe through `leaf.render_checks.evaluate_probe`.

Where the product already answers a question, use its answer: `root_overflow` for
sideways scroll, `draft_key` and `stored_draft`
for drafts, `event_log.read_events` for the log. Read the page through its public
entries (`window.__lfWidgetApi()`, `__lfCheckApi()`, `__lfClientApi()`, and
`__lfOverlayApi()` for overlay geometry); tests can't import private source
paths.

Give a corpus source its own case only when its content is the cause under test. Put a
probe's independent faults on one composed page beside clean controls and call the gate
once. Test a reading made from declarations on a widget that declares them, passed to
`serve` as `layer_registry` and `layer_widgets`.

A test over prose compares it with something the machine states: a shown command
against the click tree, an `x-` key against the guide, a table against its registry.
Leave wording with no machine side to review.

Current location and visible focus are separate (`focus.js` owns their contract):
controls and reading destinations follow the browser's focus visibility, while text
entry keeps its cue. Test with real clicks and keyboard arrivals, require
`:focus`, and compare the paint, including when the focused control has no ring. A
keyboard test reaches its stop with `Tab` or its declared command; `element.focus()`
doesn't prove that route. `RELEASE_FOCUS` (`render_harness.py`) resets where Tab
starts, which `blur()` doesn't. Read a ring's paint through `rings_drawn` and
`ring_faults`, since an ancestor may draw it, and tell which ring it is by the rule the
browser says drew it (`ring_rules`, `render_cases_layout.py`).

## Fixtures

Every test runs under `isolated_session` (its docstring says what it isolates); don't
move `HOME`. Declare other process conditions through fixtures (`sessionless`,
`codex_env`) rather than editing the environment in a test body.

Choose the page fixture by boundary: `serve` for a complete page over real HTTP,
`page_dir` for command-level files, and `ModelPage` with `model_folds.py` for markup and
a log handed straight to admission or `browser_state`. Build markup with `leaf_page`.
`initialized_page` lends one prepared page per composition shape; a test of
initialization runs `page init` itself.

Use the `browser` and `serve` fixtures for browser tests. Each pytest worker shares one
Playwright driver and Chromium, and contexts and page directories keep tests apart.
Start a separate browser or subprocess only when its engine, configuration, process
boundary or lifetime is under test. A higher worker count multiplies this across every
concurrent suite on the host, so it needs a measured benefit.

### One page for the cases that can share it

Opening a page until it is ready takes close to half of a push run's browser time, so
cases of one test that can
share a page run on it as subtests: open the page once, then run each case inside
`with subtests.test(width=width):`. A failing case is
reported by its arguments, and the cases after it still run.
`suite_profile` judges such a test against its budget per case.

Keep a `parametrize` axis for each difference that needs a page of its own: the browser
engine, something the whole document declares, such as `dir` or its layout class, or a
case that writes the page's log, publishes a revision, or changes something the page
holds once, such as the composer, the panel or a draft. A case that consumes a watch's
finding needs its own page too, since a watch reports each finding once per page. Give
each shared-page case its own part of the page, such as its own ids or editor, or undo
what it changed, and order the cases so that none moves content the shift watch reads.

### Processes and servers

A process a test starts ends on every exit from the test, and burns no CPU while it
waits, since many suites share the machine. Take each resource from its owner: a child
process from `spawn`, a
page server from `_no_page_outlives_its_test`, a preview from `preview_slot` and
`start_preview`, an HTTP server from `running_http_server`, a socket directory from
`socket_dir` (`test_the_resources_a_fixture_owns_are_taken_from_that_fixture`).
A test of a persistent server stops it explicitly.

A dead worker runs no teardown, so a process that could outlive it watches the worker: a
page server watches the worker's session claim, and a held process blocks
reading a pipe the worker holds, as `session_process` does. The test releases it by
closing the pipe, which also closes when the worker dies; don't make a process wait
for a file the test has yet to write, or poll in a loop. End a process by closing its
pipe or with SIGTERM, never SIGKILL (`test_no_test_ends_a_process_with_sigkill`). To
check a new held process, make the test fail right after starting it, then confirm with
`pgrep -fl <tmp_path>` that nothing it started still runs.

### Browser storage

Panel state and drafts live in `localStorage` and reading position in `sessionStorage`,
so a reload keeps them;
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
left at the end; don't install a second collector or filter it. Consume an expected
problem where it happens with
`consume_browser_errors`, or `reported_browser_errors` when it arrives in parts, naming
it by its fields (`leaf/findings.py`) or by a
fragment of the console message (`render_harness.is_problem`). For a recurring fault,
close the page first and then consume.

The watches below report problems. Fix what they report rather than consuming it; there
is no per-test
allowance list.

- `write_watch.js` reports a DOM write that changes nothing. Fix the writer with
  `runtime/keeps.js`. A write that must restate, as a vendored component's does, joins
  `EXPECTED` in `write_watch.js` with its reason; a test that reads the page by changing
  it and putting it back does so inside `lfUnwatched`.
- `shift_watch.js` reports a box that moves on screen without input, typing that
  moves its field, and a scroll a gesture makes that carries the control it was made
  on, unless the gesture takes the user somewhere (`browser/AGENTS.md`, "The page holds still under the user's aim").
  It runs on every test except those marked `shifts_unsurveyed`, which opt in per test
  with `watch_shifts`. Playwright's clicks, keys, viewport resizes, and Back and
  Forward are input; a script's `click()`, a value set by script and server news are
  not. It ignores first
  presentation, whose remaining defects `known_widget_findings.py` records. Chrome
  hides a shift for half a second after a click, so a test of a news update's stability
  delivers the news after that.
- `words_watch.js` reports typed words leaving the screen without a key or press
  (`browser/AGENTS.md`, "Typed words survive"). A test that closes a box
  does it the way a user
  does.
- `swap_watch.js` reports a row that grows or shrinks across its line as one occupant
  gives way to another (`browser/AGENTS.md`, "Shared containers determine control
  dimensions"). Fix the occupant so it takes the row's line.

`input_work_watch.js` tells the shift and words watches which input caused a change. It
follows timers, frames, promises and Lit updates but not a native `await`, so code that
commits a visible effect after an `await` loses its input; a fixture that must commit
after one captures the commit callback with `lfInputWork.capture` first. A private
channel between documents, such as a live sample's `MessagePort`, carries input only
where each end sets the port as `lfDocumentPort` on its bootstrap script element before
the first message (`bootstrap.js`, `sample.js`).

`test_widget_quality.py` holds Leaf's own widgets to the report `package check --render`
gives a package's author (`leaf/render_gate/widget_quality.py`).
`known_widget_findings.py` lists today's findings, each a defect awaiting a fix: a new
finding fails the test, and so does an entry that no longer occurs.

## Page readiness

Open pages through `open_page`, and call `wait_until_ready` (`leaf.render_checks`)
after any manual navigation. It waits on the runtime's one readiness signal,
`pageReadiness`; network quiet implies none of its stages, and a key pressed before
replay can be lost silently. Never combine the stamps yourself or wait for a deferred
widget by name. To measure a page before its runtime starts, call `displayed` first.

## Waits

### Functional results do not depend on execution speed

A functional test, fixtures and watches included, gives the same result and still
exercises its situation when the system runs ten times slower. Test performance
separately, under controlled conditions.

Control or advance the clock that decides an age, lease, grace period or timer; a fixed
`Date.now()` doesn't stop timers, animation frames, paint or observer delivery. Bound a
hang with a real deadline that leaves room for slow execution, and on expiry report
which completion is still missing. A time limit must never turn unfinished work into a
pass. To test a race, hold and release the request, callback, frame or lock explicitly,
check that the outcome holds with completion delayed tenfold, and keep a control that
still fails.

Wait for the operation's own completion signal. Elapsed time, matching samples, a fixed
number of frames and network quiet look the same for an effect that hasn't started as
for one that has finished, and a sleep doesn't prove that another process took a lock
(`interact_support.lock_contention` reports that a second taker is waiting). Count
frames (`one_frame` in `leaf.render_checks`) only where
one rendering update is itself the claim. A computed style under a transition reports
the animated value, so check `getAnimations()` where the subject may be moving.
`page.evaluate` takes no timeout: state readiness in the page and poll it with
`wait_for_probe`.

Waits take the suite's deadlines: `STATED_TIMEOUT` on the Python side, with
`interact_support.wait_for` for pure-Python polls, and `SERVED_TIMEOUT_MS`, which
`render_harness` makes every Playwright wait's default, so a wait
names a deadline only when it spans a page handover (`HANDOVER_DEADLINE_MS`).
`test_a_wait_takes_the_suites_deadline` checks both.

### Transient states

Use `expect(...)` for a state that becomes stable. For a transient one, read once after
the step that causes it has finished, because an auto-retrying assertion passes on the
first
matching frame even if the gesture goes on to another result. The helpers in
`render_harness.py`:

- `sending` wraps a gesture whose own event the next read needs;
- `round_trip` waits until everything sent has been delivered, not applied;
- `told` waits until the page has applied what the server holds now; call it after
  changing a file behind a live page;
- `nudge` gives the page a reason to read; `ticked` waits for its next tick;
- `undo` presses `z` once the dispatcher would take it and waits for the undo's round
  trip;
- `rendered` (`leaf.render_checks`) waits for every repaint the input so far queued,
  and `available_commands` reads the dispatcher once after it;
- `panel_settled` and `resized` wait for their motion to end, and
  `scroll_settled` (`leaf_dev.browser`) for a scroll's.

Wait for something the gesture itself changes. An empty highlight or an optimistic
`pending:` card satisfies an assertion too early; wait for painted ranges
(`wait_for_pending_mark`) or the admitted comment's id. Where applying the server's
response is the subject, wait for `data-lf-applied`, which counts only actions,
reports and undos; observe a comment, reply or reaction by its paint. Wait for `rendered` between
repeated presses a repaint could answer, and before `scroll_settled`, check that the
scroll started.

## Races

If a race appears only under load, order it with `page.route` rather than repeating the
test. `leaf-dev flake` reproduces it, prints each failing copy's message, and then
confirms the route holds. Register the
route before the gesture it catches, or through `primed` or `held_events` for the first
navigation; raw and `browser.unwatched` pages aren't set up for later routes. Where
the driver loses a fact, such as the Page for a tab Chromium opened, read the
browser's record (`opened_tab`).

A watch finding that CI reports and this machine doesn't is usually a frame that lands
later on CI's slower runner, after the input window that credits it has closed. Load
alone rarely shows it; a slower CPU does. `--cpu-throttle RATE`, given to pytest or
`leaf-dev flake`, slows every Chromium page the browser fixtures open. Past findings
reproduced at rates from 6 to 20, and one rate can miss a finding another reproduces,
so try more than one. Run the merge base under the same rate to learn whether the
change caused it. A test whose subject is a slow CPU slows its own page
with `leaf_dev.browser.slow_cpu`.

- A route handler that returns without resolving holds the request before the server.
  Call `holding` before reading the list of held requests, since the ledger counts a
  send before the handler runs. Release a held request mid-test only when later
  behavior is asserted; closing the context cancels the rest.
- `route.fetch()` lets the server answer and withholds the response. Freshness reads
  still name the append, so attach listeners before the fetch. Call
  `page.unroute_all(behavior="wait")` after releasing held routes, or
  `behavior="ignoreErrors"` in failure cleanup that may still hold requests.
- `refuse` cancels a request without a console error. A route that keeps refusing
  `**/api/state*` causes endless retries, so use `CutOff` to hold state reads.

Assert the order the route created, such as `Traffic.sends` before release. Name an
event by what the append returned (`append_event`, a model command, a CLI write's
printed record), since the log's last event may be a `read` an open page appended.

### Test-made noise

Instrumentation adds no noise to the channel a test asserts is quiet; `refuse`
uses the `aborted` reason for that. Consume a deliberate HTTP error by the browser's
diagnostic (`http_error_console`), or assert the response's status where the status is
under test. Wrap a deliberate server restart in `restarting`, asserting any
diagnostic inside that block.

## Frames, sequences, and instants

A test must cross the transition that could reveal the fault; two reads of one final
state say nothing about the motion between them.

- A frame is one held state. `HOLD_MOTION` pauses animations and `__lfHeld` lists what
  is paused; step or release each after the assertion.
- A sequence is ordered evidence across frames, recorded in the page only when the
  intermediate order is the contract.
- An instant exists within one rendering turn, such as layout when a stamp changes; a
  page-side observer captures it, and the stamp marks completion.

Measure a node the runtime rebuilds in one page-side call that finds and reads it, since
a
detached node measures as zeros. A movement test covers a press and arriving news, with
a pixel diff for borders, outlines and shadows.

## Make a green test non-vacuous

Name the one product change that would make each assertion fail, and set up the fixture
so that change reaches what is measured. An assertion that nothing moved spans a
transition that would move without the rule. Check what a lower layer already
guarantees: a send queue that drops a second POST hides whether the widget refused it.

`test_page_fixture_renders` (`journeys/test_render_gate.py`) runs every corpus page
through the render gate and the journeys that must leave it as they found it, such as
resting, scrolling, opening and closing each surface, and resizing; its docstring lists
them. A new widget or page is covered there without a case of its own, and a new surface
or typed box joins its journey by its keys or route.

### Absences

An absence asserted before the runtime's deferred step passes on the frame before the
decision. Read it once, after the step that would have caused the forbidden behavior,
and keep a control that first produces it.

### Sweeps over controls

Pin the ids or count a sweep walks, before and after any reload, and assert that the set
is non-empty and every expected kind was reached, rather than an assertion whose
condition can vanish with the behavior.

## Failure messages

Pair `capture_output=True` with `check=True` only when the exception is unpacked; a test
that needs the streams asserts the return code and puts stdout and stderr in the
message. Assert output by meaning: use `spoken` for the registry-backed reading, and
match the attribute that carries a claim.
