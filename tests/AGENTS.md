# Testing leaf

The suite proves the boundary between an authored page, the browser runtime, the
event log, and a returning reader. Most failures in that boundary are easy to
assert once they are visible. The difficult part is arranging the test so that a
green result could only have come from the behavior named by the test.

This file owns test setup, suite structure, and testing mechanics.
`skills/leaf/assets/AGENTS.md` and the code-adjacent contracts routed by
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

`tests/runtime/` is the same gate's other half, run by Node rather than pytest. It holds
the shipped runtime's folds, imported into the document object model
`tests/runtime/dom.mjs` puts up:

```sh
npm run test:runtime
```

A test is nightly when a pull request can land without it: the broad browser corpus in
most `test_render_*.py` modules, and the published site in `test_site.py`. The everyday
gate keeps `test_chrome_contracts.py`, `test_render_mcp.py`,
`test_render_application_boundary.py`, and `test_render_semantic_news.py`, so the
`test_render_` prefix does not say which run a file belongs to. A test does not become
nightly because it is expensive. Broad discovery skips nightly tests.
An explicit file, node id, `-k`, `-m`, or `--lf` selection runs what it names. During
development, select the owning file or one named case and use `-n 0` so the trace and
process tree stay local:

```sh
uv run pytest tests/test_render_widgets.py -q -n0 -k board
uv run pytest --lf --lfnf=none -x -n0
```

Formatted CLI output lives in `tests/_regtest_outputs/`. After an intentional
change, reset only the affected test, then inspect the recorded diff:

```sh
uv run pytest --regtest-reset -n0 <node-id>
```

Agent-facing interaction specimens record complete outputs at their delivery
boundaries. Review the affected specimens when changing interaction guidance:

| File | Boundary |
| --- | --- |
| `test_interact_contract.py` | event handling and browser POST through delivery |
| `test_interact_session.py` | hooks, watcher recovery, reply/version/receipt lifecycles, summary suggestions |
| `test_interact_layer.py` | command help and reply selection errors |
| `test_interact_mcp.py` | stdio tool descriptions and metadata |
| `test_website_server.py` | hosted agent start messages and serialized tool output |

Specimens normalize temporary paths and generated identities, not instruction
text. Multiline prompts use literal YAML blocks to preserve their line breaks.

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
the published examples. Their companions follow `examples/AGENTS.md`; the page and
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

`tests/runtime/*.test.mjs` holds what a runtime module decides on its own: a value
folded from values, a tree question answered from the tree. The division from
`test_render_*.py` is the one `model_folds.py` draws on the Python side — the subject
decides, not the machinery — with one boundary that is particular to running outside
Chrome. An engine supplies more than paint, and where a fold rests on a primitive whose
implementation differs, the fold is a browser fact: `text-alignment.js` reads
`Intl.Segmenter`, which parts differently on dotted identifiers under Node and Chrome,
so its test stays in the browser suite however little DOM it touches. Ask both engines
rather than reading the module. `tests/runtime/dom.mjs` owns that world: the document
object model these imports land in, and the map from the `/runtime/…` and `/vendor/…`
specifiers a served page answers to the files under `skills/leaf/assets/`.

`scripts/browser/application.test.mjs` also reaches runtime folds, and the subject is
what separates them: it tests the publisher, which composes `foldProjection`,
`foldThreads`, `foldWidgetStates` and the pending model into one reading, so a claim
about that composition belongs there. A claim about what one of those modules decides
belongs here, where it is imported the way a page imports it.

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

Focus evidence starts in keyboard modality: press `Tab`, focus the exact
sequential stop, and require `:focus-visible`. `element.focus()` alone is not
sufficient. Reset sequential navigation with `document.body.focus()` when an
opening key sequence needs a fresh starting point; `blur()` retains the old one.

A ring can belong to the stop, an ancestor, or a semantic carrier linked to the
stop. Inspect the actual paint rather than assuming the focused box draws it.
`RINGS_DRAWN` and `ring_faults` own the shared reading. Focus tests cover:

- native `outline-style: auto`, the layer's outline and shadow bands, and the
  element mark's own focus ink;
- every stylesheet rule naming a band through `--lf-here-ring`, with a causal
  specimen for each rule and every required surface opened;
- both inset and outset rings, clipping, and overlapping neighbors under their
  actual paint order;
- comparison with the resting state, including unchanged focused geometry and
  no stale divider on a later thread sibling.

Resolve colors through a swatch so equivalent CSS expressions compare equally.
A credited ring must be painted and named; a declaration removed by a later rule
is not coverage. Read the rendered styles rather than attempting to interpret
`@media` or `@supports` in the test. Focus-ring probe tests in
`test_render_gate.py` plant faults and clean controls for these cases.

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

Launcher dependency-resolution tests use their own `UV_CACHE_DIR` so a cached
wheel cannot bypass the package index under test. These tests need the network
available to the nightly run.

Use `sessionless` when the subject is a command launched outside any host
session. Use `codex_env` when constructing a real Codex process ancestry; it
removes the Claude identity that would otherwise win host detection. Declare
those conditions through fixtures rather than deleting environment variables in
a test body.

### A process the suite starts ends with the run

The run restores SIGINT handling so children have the same interrupt behavior
whether pytest was launched in the foreground or as a background shell job.
Resource ownership is explicit:

| Resource | Fixture owner |
| --- | --- |
| Child process | `spawn`, which ends survivors and their process groups when given a new session |
| Page server | `_no_page_outlives_its_test`, which releases held leases and sweeps the test's temporary page and isolated state roots |
| Preview slot | `preview_slot`, which places pages under `LEAF_PREVIEWS_ROOT` in `tmp_path` and retires detached watchers through `preview.retire_preview` |
| In-process HTTP server | `interact_support.running_http_server`, which closes the socket and joins its serving thread within a deadline |
| Unix socket directory | `socket_dir`, which uses a short system-temporary path to fit `sun_path` |

Tests of standing servers stop them explicitly: that lifetime does not depend on
session claims. Other page servers use the synthetic session claim as their
final owner if a worker dies before teardown. A `Popen` handle alone does not
own a detached server's process tree.

`test_the_resources_a_fixture_owns_are_taken_from_that_fixture` checks that tests
use these owners. Its exceptions name the file and reason.

An autouse cleanup fixture takes the isolated home from `isolated_session`, not
from `state_home()` at setup or teardown: fixture ordering can expose the
developer's environment there. Sweep only that home and the test's `tmp_path`.
`test_a_run_ends_only_the_servers_it_started` proves that cleanup stops the run's
leftover server and leaves an unrelated planted server alone.

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

Choose the fixture by the boundary under test:

- `serve` initializes and serves a complete page through real HTTP routes. With
  markup, it publishes one version; with an example path, it includes companion
  versions, data, log, and referenced media, and returns the newest immutable
  version URL. `serve.page_dir` exposes the directory for later writes.
- `serve(example, seed_log=False)` omits the conversation log while still copying
  its referenced media, so the test can append those events itself.
- `page_dir` in `interact_support.py` supplies command-level files without a
  browser.
- `ModelPage` puts authored markup and the standing log to
  `event_contracts.admitted_event` without a page directory.
- `model_folds.py` supplies the same kind of input to `browser_state`. Both model
  helpers compose vocabulary through `model_layer`. File-backed admission,
  outstanding-reader obligations, and rendered behavior use the fuller fixtures.

`initialized_page` lends one prepared page per composition shape. The next loan
restores changed files and removes additions. Runtime and vendor files are
hard-linked immutable inputs; other files are private copies. Never write
through a layer hard link: re-vendoring replaces files, and the fixture rejects
an in-place mutation by name. Tests of initialization or composition cross
`page init` themselves or request their own shape.

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
- The page-arrived probe says the page has stopped arriving: an owner may put work after
  presentation deliberately — a widget's progressive upgrade, the gallery's contained
  documents — and it declares that work to the runtime, so a fixture carrying one is not
  ready the moment it presents. Never wait for a fixture's own deferred widget by name;
  the page already states it, and a wait written at one test leaves the next one racing.

These are independent facts. Network quiet implies neither. A browser action
sent before replay has landed may be ignored without a later assertion revealing
that the keypress itself was lost. Use the shared `BOTH_STAMPS` predicate for
manual navigations as well; the `upgraded=False` escape in `open_page` is only
for a test whose subject is the interval before those stamps, waits for the
banner module to exist, and must make its later readiness explicit.

For a pre-runtime measurement, call `displayed` first. It waits for first
contentful paint; element visibility can force layout before a render-blocking
stylesheet arrives and therefore measure the unstyled document.

The `browser` fixture installs error collection, route interception, and the
`Traffic` ledger before navigation. Create pages through that fixture or a
context it owns. `watched` returns the existing collector; do not install a
second one or add instrumentation inside a Playwright event handler.

The collector combines console warnings/errors, `pageerror`, and window errors
through `leaf.render_checks.install_window_errors`, shared with the render gate.
`navigate` retries a complete navigation after a ResizeObserver-loop notice;
a recurring notice fails. The fixture checks collected problems after the
journey, then closes its remaining contexts. Leave ordinary cleanup to it so
closing a page cannot truncate its own error reading.

Close a page within a test when closing is part of the journey, or when it ends
a deliberately recurring fault. Consume a single expected fault at its causal
point with `consume_browser_errors`; every collected entry must match. For a
recurring fault, close the page first, then consume its retained entries. Use
`take_browser_errors` only when asserting or partitioning the complete list.
Filtering the collector or leaving expected noise behind is not an assertion.

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
- `round_trip(page)` waits until every post the page issued has ended and every
  event attempt in its outbox has a definitive outcome. A request failure alone is
  not final because the page may retry the same attempt. A post that skips the
  outbox — a bookkeeping event such as `read`, the page's own `error` report, a
  media upload — is over only when the post is, so a test that holds requests on a
  route releases every one, that report included.
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
- `scroll_settled(page)` waits for the scroller to stop. First observe the fact
  that the gesture issued its scroll; stillness alone also describes a scroll
  that has not begun. The helper counts animation frames to span the pause
  between instant placement and smooth scrolling. `scroller=` and `axis=` select
  a nested scrollport; the helper resets its own record.

- `shortcut_bar_text(page)` reads what the shortcut bar says, once, after the repaint's own
  frame. `repaint` coalesces to a `requestAnimationFrame`, so a read taken in
  the same round-trip as the press is a read of the frame before.
- `ask_actions_hint(digits)` supplies the runtime wording for an Ask's numbered
  routes. Keep shared wording in one helper beside its reading rather than
  copying strings across tests.

Choose a completion fact that the gesture changes. An unchanged surface, an
empty highlight registry entry, or an optimistic thread count can all satisfy
an assertion before the work under test completes.

- Wait on nonempty highlight ranges or `wait_for_pending_mark`, not merely a
  registered highlight name.
- For an admitted comment, wait on its durable identity rather than its
  `pending:` card, or use `sending` when the request has a definitive outcome.
  A retrying request does not finish `round_trip`.
- For paint that must happen in the gesture's own frame, read once after that
  frame. `shortcut_bar_text` provides this boundary; a retrying assertion can
  instead pass on the periodic repaint and hide the missed immediate update.
- For absence, observe the positive fact that would cause the forbidden paint,
  then read once. Plant that paint to prove the assertion can fail; reverting
  the change may remove the path that paints it.

`test_numbered_addresses_show_progress_on_complete_routes_without_moving` and
`test_the_captured_quote_is_prose_a_file_can_hold` exercise unchanged surfaces
and optimistic admission respectively. Repeat a bug-back when a probabilistic
wait could otherwise appear causal.

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

For layout, animation, and navigation, wait for the boundary being measured:

- `panel_settled` observes the requested panel class. The runtime places the
  margin and marks synchronously with the column;
  `test_closing_the_panel_lands_the_margin_where_the_column_lands` proves this.
- `resized` waits for resize listeners and the following rendering update,
  including the document's scrolling area. Wait separately for any ensuing
  motion whose geometry is the subject.
- `moving` ends finite motion before reading a surviving observer or protocol
  record.
- An anchored quote can scroll instantly and then smoothly. Its first
  `scrollend` need not be the destination; inspect the final mark position or
  use `scroll_settled` after observing scroll initiation.

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

Use `held_events` for event holds installed before navigation, or `primed` for
other routes. Pages created through the `browser` fixture are instrumented by
`readable` before navigation, including pre-armed interception for later routes.
Raw or `browser.unwatched` pages do not carry that guarantee.

Before indexing a handler's `held` list, asserting its length, or removing its
route, call `holding`. `Traffic` records a send before Playwright dispatches the
route callback, so its count does not prove the list has received the request.

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

A route on `**/api/state*` leaves the news stream active. Failed state reads
are retried, so a standing refusal can keep producing errors.

A request held before the server receives it can remain held at test end;
context closure cancels it. Release it during the journey only when subsequent
behavior is part of the assertion. Do not add a teardown release that could
resume the request after its server has stopped.

A handler already executing `route.fetch()` needs different cleanup: its
response body belongs to the page. Complete that handler and call
`page.unroute_all(behavior="wait")` before teardown closes the page. Ensure this
cleanup also runs when the assertion fails.

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

Use `restarting` around a deliberate server interruption. It excludes the
transport noise inside that span while keeping the rest of the test's collector
strict. Assert diagnostics that are the subject inside the block that produces
them. `test_a_service_that_goes_away_mid_start_says_only_that_and_comes_back`
checks both the interruption and recovery.

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

Browser error ownership and deliberate faults follow "A page is ready when it
says what has finished" above.

Assert durable output as meaning rather than formatter layout. Collapse
whitespace when testing what a page says, use `spoken` when the registry-backed
reading is already available, and match the attribute that carries a markup
claim rather than a complete serialized tag. Reserve exact source and line
assertions for tests whose subject is source structure or a diagnostic
location.
