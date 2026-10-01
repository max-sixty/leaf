# Testing leaf

A test here is evidence about behavior a user depends on. The suite does not constrain
new code (root `AGENTS.md`, **Stage**): rewrite or delete an overfit test as part of
the change, and say in the commit which behavior moved.

Prove each contract at the lowest boundary that preserves it, and keep a browser test
only where it proves boundaries working together. When a browser test is slow, or fails
on timing or geometry outside its contract, repair its arrangement or move its contract
down. Each helper's docstring owns its contract. Code cites the sections below by
heading, so a renamed heading needs its citers updated.

## Running tests

The host supplies `wt`, `uv`, `jq` 1.6 or newer, Node 22 or newer, and Docker for the
complete website boundary only. `wt setup` installs Playwright's Chromium headless
shell, WebKit, and Chrome, the example assets, and the npm trees; `uv run` syncs
Python.

```sh
wt setup
uv run pytest tests                  # everyday gate; no network after setup
npm run test:runtime                 # the gate's other half: tests/runtime/, under Node
uv run pytest tests --run-nightly    # everything
uv run pytest tests/test_render_widgets.py -q -n0 -k board   # one case, kept local
uv run pytest --lf --lfnf=none -x -n0
uv run pytest --regtest-reset -n0 <node-id>
```

Mark a test `nightly` when a pull request can land without it, including any test that
needs the network; expense alone does not make a test nightly. Broad discovery skips
nightly tests; an explicit file, node id, `-k`, `-m`, or `--lf` runs what it names, and
both landing gates add the nightly tests in the files a change touches
(`--nightly-changed-since`).

Before handing over a browser-facing change, run its whole browser file, the everyday
gate, and the smallest nightly selection covering it. Run a new or changed browser test
through `uv run leaf-dev flake NODEID`, which runs concurrent copies; a serial rerun
samples only an idle machine. A failure naming a fixed path in the checkout, such as an
export under `.tmp/`, is the copies racing there.

CLI output and agent-facing text are regtest recordings in `tests/_regtest_outputs/`,
normalized for temporary paths and generated identities but never for instruction
text. After an intentional change, reset only the affected test and read the diff.

GitHub Actions on Ubuntu 24.04 is the Linux authority: compare the candidate's and the
base's workflow runs, not a local container. Subprocess tests invoke leaf through
`LEAF_COMMAND`, and `bin/leaf` only where the launcher itself is the subject.

## Test placement

- `interact_support.py` holds file-side fixtures, `render_harness.py` browser fixtures,
  and `render_cases_*.py` reusable browser cases.
- `tests/runtime/*.test.mjs` holds what one runtime module decides on its own, in the
  document `tests/runtime/dom.mjs` puts up; `build/browser/application.test.mjs` holds
  the publisher's composition of those folds. Both build served threads and workflows
  with `served.mjs` from what `served_records.py` folds through the server.
- `fixtures/pages/` holds full-page regressions under `examples/AGENTS.md`'s rules.

A fold that rests on a primitive Node and Chrome implement differently, such as
`Intl.Segmenter`, stays in the browser suite.

A property caused by a particular page belongs in `render_version`, because `page check
--render` reports it to that page's author. A property identical for every valid page,
such as how the layer restores browser state (`arrival_findings`), belongs in the
suite. A render-gate test calls `render_version`, not one of its probes.

Where the product already answers a question, consume its answer: `shownBand` for the
band a box shows, `root_overflow` for sideways scroll, `draft_key` for where a draft is
stored, `event_log.read_events` for what the log holds. Page-side code reaches a runtime
module through `window.__lfRuntimeImport`; a bare `/runtime/…` import loads a second
instance that shares none of the page's state.

A corpus source gets its own case only when its content is the cause under test. Put a
probe's independent faults on one composed page beside clean controls and call the
gate once. A reading the layer makes from declarations runs on a widget that declares
them, passed to `serve` as `layer_registry` and `layer_widgets`.

A test over prose compares it with something the machine states: a shown command
against the click tree, an `x-` key against the guide, a table against its registry.
Wording with no machine side is left to review.

## Fixtures

Every test runs under `isolated_session`, which moves only the XDG state home and claims
pages under the worker's pid; do not move `HOME`. Declare other process conditions
through fixtures (`sessionless`, `codex_env`) rather than editing the environment in a
test body.

Choose the page fixture by boundary: `serve` for a complete page over real HTTP,
`page_dir` for command-level files, `ModelPage` and `model_folds.py` for markup and a
log handed straight to admission or `browser_state`. Build markup with `leaf_page`, and
write a raw document only when source structure is the subject. `initialized_page`
lends one prepared page per composition shape, with runtime and vendor hard-linked in;
a test of initialization runs `page init` itself.

### Processes and servers

Take each resource from its owner: a child process from `spawn`, a page server from
`_no_page_outlives_its_test`, a preview from `preview_slot` and `start_preview`, an
in-process HTTP server from `running_http_server`, a Unix socket directory from
`socket_dir` (`test_the_resources_a_fixture_owns_are_taken_from_that_fixture`). A test
of a standing server stops it explicitly, since a `Popen` handle does not own a
detached server's tree. The cleanup sweep reads only `isolated_session`'s state home
and `tmp_path`, never the developer's.

### Browser storage

Panel state and drafts live in `localStorage` and reading position in
`sessionStorage`, so a reload keeps them; clear both for a first visit. Each
`Browser.new_page` is its own context; two tabs of one user share `one_user`.

## Driving the browser

Drag selections with `select`; a synthetic `dispatchEvent` skips the event sequence
the runtime listens to. `locator.click()` scrolls its target into view, so where a
press's effect on scroll is the subject, scroll first and read the baseline after.

Focus evidence starts in keyboard modality: press `Tab` to the stop and require
`:focus-visible`, or `:focus` on `leaf-text`, which never matches `:focus-visible` in
Chrome. `element.focus()` is not that evidence. `RELEASE_FOCUS` resets the sequential
starting point; `blur()` keeps it, and `document.body.focus()` does nothing. Read a
ring's paint through `RINGS_DRAWN` and `ring_faults`, since an ancestor may draw it.

Inject nothing to make observation easier: traffic comes from the runtime's own
ledger, network conditions from `page.route`, errors from the browser fixture. An init
script may record a sequence or an instant ("Frames, sequences, and instants"), and
completion still comes from a fact visible outside the page. A gate test whose page is
meant to be faulty hands over `browser.unwatched`, since `render_version` reports that
page's errors itself.

### Browser errors

The `browser` fixture instruments every page and fails the test on any problem left at
the end; do not install a second collector or filter it. Consume an expected fault
where it is caused with `consume_browser_errors`, or `reported_browser_errors` when its
report arrives in parts. For a recurring fault, close the page first and then consume.

The collector also fails:

- a DOM write that changes nothing (`write_watch.js`). Fix the writer
  (`runtime/keeps.js`). A write that restates for a reason of its own joins `EXPECTED`
  in `write_watch.js` with that reason, and a test that reads the page by changing and
  restoring it does so inside `lfUnwatched`.
- a layout shift the "Stability" rule in `skills/leaf/assets/AGENTS.md` forbids
  (`shift_watch.js`). Playwright's clicks, keys, and viewport resizes are input; a
  script's `click()`, a `value` set by script, and the server's news are not.
  `known_shifts.py` lists the tests whose pages still shift, each a defect waiting on
  its fix, and nightly tests are not watched yet (`known_shifts.watches_shifts`).

`test_widget_quality.py` runs `package check --render`'s widget quality report over
the base layer and every bundled package. `known_widget_findings.py` lists today's
findings: an unlisted finding fails, and so does a listed one that no longer occurs.

## Page readiness

Open pages through `open_page`, and call `wait_until_ready` (`leaf.render_checks`)
after any manual navigation. It waits on the runtime's one readiness reading
(`pageReadiness`), whose stages are independent: network quiet implies none of them,
and a key pressed before replay can be lost silently. Never combine the stamps
yourself or wait for a deferred widget by name. Call `displayed` before a pre-runtime
measurement.

## Waits

Elapsed time, matching samples, a fixed count of animation frames, and network quiet
all describe a page that has not started an effect as well as one that has finished it.
Wait on a fact the system states, and count frames (`one_frame`) only where one
rendering update is itself the claim. A computed style under a transition reports the
animated value, so ask `getAnimations()` where the subject may be in transit.
`page.evaluate` takes no timeout: state readiness synchronously in the page and poll it
with `wait_for_probe`; pure-Python polls use `interact_support.wait_for`. A new wait
fixes its deadline when it begins and names the missing evidence on timeout.

To assert that a mechanism with a grace period did not act, wait out that product
constant plus scheduling room; nothing else states the absence.

### Transient states

Use `expect(...)` for a state that becomes stable. For a transient one, read once after
the causal edge has completed: an auto-retrying assertion returns on the first matching
frame even if the gesture goes on to another result. The edge helpers in
`render_harness.py`:

- `sending` encloses a gesture whose own event the next read needs;
- `round_trip` waits for delivery of everything sent, not for its application;
- `told` waits until the page has applied what the server holds now; call it after
  changing a file behind a live page;
- `nudge` gives the page a reason to read; `ticked` waits for its next tick;
- `undo` presses `z` once it is offered and waits for the withdrawal's trip;
- `rendered` (`leaf.render_checks`) waits for every repaint the input so far queued;
- `panel_settled`, `edge_settled`, `resized`, and `scroll_settled` each end one kind of
  motion; before `scroll_settled`, observe that the gesture started its scroll.

An empty highlight registration or an optimistic `pending:` card satisfies an
assertion early, so wait for painted ranges (`wait_for_pending_mark`) or an admitted
comment's durable identity. Read the event log after `round_trip`. Where applying the
response is the subject, wait for `data-lf-applied`, which counts actions, reports, and
undos; observe a comment, reply, or reaction by its paint. Wait for `rendered` between
repeated presses a repaint could answer, and where waiting changes the outcome, run the
gesture both ways and assert they agree.

## Races

A race that appears only under load is ordered with `page.route`, not repeated.
`leaf-dev flake` reproduces it and prints every failing copy's message. Register the
route before the gesture it catches, or through `primed` or `held_events` for the
first navigation; raw and `browser.unwatched` pages are not armed for later routes.
Where the driver loses a fact, such as the Page for a tab Chromium opened, read the
browser's record (`opened_tab`).

- A handler that returns without resolving holds the request. Wait with `holding` for
  the list the handler fills, since the ledger counts a send before the handler runs.
  Release a hold only when later behavior is asserted; a release at teardown could
  reach a stopped server.
- `route.fetch()` lets the server answer and withholds the response. The news stream
  still names the append, so arm listeners before the fetch, and call
  `page.unroute_all(behavior="wait")` before teardown even when the test fails.
- `refuse` cancels without a console error; use a plain abort only when the error is
  the subject. A route that keeps refusing `**/api/state*` keeps producing retries, so
  `CutOff` holds state reads across a stale-state journey.

Assert the ordering the route created, such as `Traffic.sends` before release, and for
a stale state prove both the page's view and the server's newer one. Name an
event from what the appending door returned (`append_event`, a model command, a CLI
write's printed record), since the log's tail may be a `read` an open page appended.

### Test-made noise

Instrumentation must not pollute the channel it asserts is quiet; `refuse` uses the
`aborted` reason for that. Assert a deliberate HTTP error through the collector's
status-and-URL entry, and wrap a deliberate server interruption in `restarting`, with
any diagnostic under test asserted inside that block.

## Frames, sequences, and instants

A test must cross the transition that could reveal the fault; two reads within one final
state say nothing about the motion between them.

- A frame is one held state. `HOLD_MOTION` pauses animations and `__lfHeld` lists what
  is still held; step or release each after the assertion.
- A sequence is ordered evidence across frames, recorded inside the page only when the
  intermediate order is the contract.
- An instant exists within one rendering turn, such as layout when a stamp changes; a
  page-side observer captures it and the stamp marks completion.

Measure a node the layer rebuilds in one page-side call that resolves and reads it,
since a detached node reads as zeros. A movement test covers both a press and arriving
news, with a pixel diff for borders, outlines, and shadows.

## Non-vacuous tests

Name the one product change that would make each assertion fail, and arrange the
fixture so that change reaches the measured surface. Reintroduce the defect and run the
test before accepting it: `uv run leaf-dev bugback NODEID...` runs the named tests on a
committed branch with its non-test change reverted. To prove each of several guards,
flip one at a time by hand. Check what a lower layer already guarantees: a send queue
that drops a second POST hides whether the widget refused it.

These matrices run on every corpus page, so a new widget or page joins them without a
case of its own:

- a returning visit (`arrival_findings`): reloaded with each state a user turns on once
  and gets back on every load, such as an open thread panel, the page comes up;
- semantic replay over a static authored state, applied twice: the visible state is
  right and idempotent;
- a scroll (`scroll_writes`, `scroll_followers`): no place is written on every step;
- a page left alone (`at_rest`): it does nothing;
- a surface's round trips, which a new surface joins by its keys: each leaves the
  `page_state` the first did, and `live_counts` do not climb;
- a resize: each width reads as it did on the way out.

Generated-markup probes (`undeclaredAttrs`, `relativeReplays`) run through
`leaf.render_checks.evaluate_probe` on fixtures that can trigger them.

### Absences

An absence asserted before the runtime's deferred step passes on the frame before the
decision. Read it once, after the positive edge that would have caused the forbidden
behavior, and name a control that first produces the presence.

### Sweeps over controls

Pin the identities or count a sweep walks, before and after any reload, and assert a
loop's declaration set is nonempty with every expected kind reached. Avoid a
conditional assertion whose condition can vanish with the behavior.

## Failure messages

Pair `capture_output=True` with `check=True` only when the exception is unpacked; a test
that needs the streams asserts the return code and puts stdout and stderr in the
message. Assert output by meaning: use `spoken` for the registry-backed reading, and
match the attribute carrying a claim.
