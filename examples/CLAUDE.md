# The examples

Each top-level authored HTML file is both a complete user page and an integration
fixture. The website publishes those pages with the same vendored layer. Synthetic
feature scenarios have one home: `developer/feature-gallery.html`. Extend that
omnibus page instead of adding another developer page. Every core Leaf feature must
be directly exercisable there. A change that adds or materially changes a core
feature adds or updates its focused specimen in the same change; coverage in a
public example does not substitute for the developer surface. A focused specimen
names the real control or gesture, seeds the state it needs, and tells the
developer what result to inspect. For injected chrome whose state comes from
outside one document, name that condition and exercise it in the gallery's browser
test. The gallery uses the same companion version, log, and data conventions as an
example, but the website does not publish it. `corpus.html` and `corpus.data.json`
are generated from both sets; edit the source page and regenerate the corpus
instead of patching either output (`test_corpus_is_generated_from_the_examples`
holds the two to their sources).

## Every widget and idiom in the vocabulary stands here

The nightly run uses this corpus in two ways. Page-sensitive contracts run every
public example, the feature gallery, and the generated corpus: each renders in both
palettes, passes axe, and exports with its scripts gone. Authored-content sweeps
quote every source passage and resolve anchors written from every source file.
Shared runtime mechanisms use causal representatives instead of repeating the same
gesture over every page, and each representative has a non-vacuity floor naming the
reason it stands there. A widget that stands in no source page is one the
whole-page contracts have never seen, and its own green tests read as coverage.

`test_every_widget_in_the_vocabulary_stands_in_a_corpus_source` is the floor. It
reads the widget list off the registry and the package list off `layer.json`
(`SHIPPED_PACKAGES`), so the next widget joins the corpus by being declared and a
widget that moves into a bundled package stays under the floor.
`test_every_idiom_in_the_catalog_stands_in_a_corpus_source` holds the catalog's
other half: an idiom is a CSS selector, so the test puts every idiom key to Chrome,
matched against the authored markup rather than the upgraded page, which also
keeps each key a working selector.

The floor guarantees the widget appears; which of its shapes appear is a judgment.
Where an attribute or a content shape changes what a reader sees (an `lf-options`
group's form, arity, joining, and `label` vary independently), a page here shows
that shape, because a rule written against one combination governs the rest
without saying so.

## Standing here is not the same as having been looked at

The floor guarantees a shape is rendered. It never guarantees anyone judged what
was rendered. When a sweep finds something, ask which gap let it through before
adding a page: a shape absent from the corpus wants a fixture; a shape present but
unexamined wants a reading (a test over every cell of a joined control, or the
`/ui-sweep`), and a page that only re-renders a shape nobody judges buys nothing.
A gate reading that would have to find a control by fingerprint fails correct
pages to catch leaf's own theme, so that reading belongs in the suite, not
`render_version`.

Use `corpus.html` when measuring runtime cost across the composed surface. A small
fixture can establish a cause, but it cannot stand in for the composed surface.

## An example is its stamped versions, plus any log and data it ships beside it

`examples/layer.json` names the package selections shared by the corpus. Preview,
lint, and site tooling all read that list, so the pages exercise the same vendored
layer the website serves. Every bundled package belongs in it, whether or not a
page uses that package today: the list is what the corpus floors read to decide
which vocabulary they cover.

An example's markup is its current version. A page fixture that was revised ships
each earlier version in its sibling `versions/` directory as `<stem>.vN.html`.
`example_versions` in `scripts/example_data.py` is the one reader of that list, in
filename order, and each builder walks it oldest first through the real `version
stamp`: `scripts/preview.py`, `publish_pages` in `scripts/site.py`, `serve` in
`tests/render_harness.py`, and `test_page_fixtures_pass_check`, which lints every
version rather than only the current one. Prior versions live under `versions/`
so top-level `*.html` discovery never reads a version as a page fixture, and the
authored-content sweeps (above all the one holding two examples to twelve
consecutive shared words) never read a revision against its own earlier draft.

Three orderings hold. The seed goes in after the first stamp and before any later
one, so a revised example reads the way it happened: the version, what the reader
said about it, then the version that answered them. The cursor goes to the end
after the last stamp, or the closing note arrives as unread news. The current
version is written into the page before the data operations, because the data
door validates a source against the page's markup and the current version is the
one that has to bind it.

`log-retention` is the revising example. Its second version rewrites one paragraph
around a sentence the reader quoted, adds a paragraph and a step, and leaves the
rest alone, so the comparison marks three blocks and both threads stay attached.
`restated` and `overruled` are reachable and no example uses them; each needs a
decision or report standing in the seeded log that the next version contradicts.
Write one when there is a page it makes sense on, not to fill the slot.

A thread is the one thing no markup describes, so an example that wants to show
one ships its events as `<stem>.jsonl` beside the page. Every place that builds a
page directory out of an example lays the log in: `scripts/preview.py`,
`publish_pages`, `test_page_fixtures_pass_check`, and `serve` in
`tests/render_support.py`. `serve` seeds when handed an example rather than
markup, and sets the cursor past the seed as `preview.py` does. The anchor sweep
opts out, because it writes its own anchors and compares the whole painted mark
against exactly those. `ship-review.jsonl` is the one such log today, and it
reaches the browser on the published site through the session running in the
reader's own tab, since published pages are served rather than exported.

External data is the other companion state. An example that binds a widget input
to a source ships `<stem>.data.json`, mapping each page-owned source id to its
complete current value. A reserved `$captures` object instead maps a source id to
`file` and optional `format`, `label`, or `lines`; the file is a sibling of the
example. The format defaults to `text`, where `lines` may select an inclusive
range; a large unified diff stays in its `.patch` source and is captured with
`"format": "unified-diff"`. Builders apply captures first and then current values
through `leaf data capture` and `leaf data set`, so binding, contract validation,
revisioning, live preview, browser sweeps, and the static site all exercise the
real doors. `scripts/corpus.py` composes those companions into
`corpus.data.json` and rebases each selected `snapshot` to that capture's revision
in the combined data log, so each source page owns only its local snapshot
numbers.

Wherever the page is served, the cursor is set to the end of the seeded log. A
seed is history, not news; a cursor at zero hands the next agent session a
question the same log already answers, and the loop guard nags about it each
time.

When a seeded event needs an anchor, capture it with `leaf comment --quote`
against the file; do not write the `{section, quote, suffix}` out by hand. A
hand-written anchor is a second capture with nothing holding it to the first, and
it rots silently: rewrite the sentence and the thread stands detached with no
error anywhere. `test_a_shipped_log_opens_its_example_on_a_live_thread` reads the
shipped anchor back through the browser and names that failure. The corpus's own
anchor sweep cannot catch it, because that sweep writes its own anchors.

`resolves` is reachable and no example uses it, deliberately: the attribute goes
in the markup, and `scripts/corpus.py` embeds each example's authored content into
a corpus whose own directory has no seed, so `version check` would refuse the
corpus over an id naming no comment in its log. Seeding a log costs the example
nothing; hanging markup off that log couples the markup to every page built from
it.

A widget with a live half (an `lf-agent` row rendering how long since its worker
was heard from) is invisible to the corpus sweeps until a seed puts a report in
the log. The seed makes the rendering visible; what the rendering says is pinned
in fixtures that mint their own timestamps
(`test_a_rosters_row_says_when_the_log_last_heard_from_that_worker`,
`test_a_worker_that_has_never_reported_dates_from_its_version`), because a seed's
`ts` is a fixed instant and the line renders against now. The next widget with a
live half owes both halves.

A seed is also the only way a widget reaches the corpus in a message, since an
event's `markup` renders in the panel and nowhere else. `ship-review.jsonl`
carries the shape: an agent question with a `multiple` group, the reader ticking
two of the three and not yet pressing Done, so the group is both decided and still
asking. The same log carries a screenshot in a message, which is the one place
`.lf-media-open` — and the `media` ring on it — stands in the corpus at all; it
hangs off an existing message rather than a new one, because the panel's thread
lengths and its waiting-on-you count are both read by fixtures.
`test_a_shipped_log_opens_its_example_on_a_live_thread` opens the panel and asks
that each widget the log carries is drawn, that a widget the registry says awaits
an answer has a control to answer with, and that the decided state differs from
the same page under the same log with the decisions removed.

A hand-written seed is markup no gate reads: `version check` asks it only for
ids colliding with the version's, and `leaf reply` never sees a file written into
the repository. `test_every_seeded_fragment_passes_the_door_it_never_came_through`
posts each seeded fragment through that real door rather than through a copied
list of checks. Render-gate readings assume a widget stands in the document
unless written otherwise; a widget in a message is inside the panel's `.lf-ui`,
and a shut panel has no boxes, so a reading that walks text nodes must bound its
chrome question at the widget (`uiInside`).

## A page's connective prose is its own

The gesture vocabulary repeats, and is meant to: every board takes a drag, every
group takes a pick. The sentence around the gesture must not repeat, because a
page that borrows another page's sentence describes its own work in another
page's words. The rule lives in `references/authoring-evidence.md` under
"Interactive and visual evidence"; what lives here is the check.
`test_no_example_writes_another_example_s_sentences` holds the corpus to at most
twelve consecutive shared words, five clear of the longest real overlap, so a
single borrowed clause can still pass and remains a judgment for review.

## The media an example names sits beside it

An `lf-shot` needs image bytes a single file cannot hold. `examples/media/`
carries them, content-addressed exactly as `leaf page media` names them in a page
directory, and every place that builds a page directory out of an example lays
them in: `serve` and `test_an_installed_payload_passes_its_real_browser_gate` in
the browser test modules, `test_page_fixtures_pass_check`, `publish_pages` in
`scripts/site.py`, and `scripts/preview.py`. A publisher that forgets fails
loudly, because `version check` refuses a `/media/` reference the directory
cannot answer.

A seeded message names its media the other way: a pasted screenshot lives in the
message's Markdown, where the parsed reading that harvests attributes cannot see
it, so a builder that reads only the markup serves the page with a broken image
and no error until a console sweep reads one. `serve` reads the log's references
too, and the publishers that copy `examples/media/` whole already covered it.
`ship-review.jsonl` carries the shape.

A before/after pair is drawn rather than captured, since what it shows is a
fiction the example needs. Draw both images at one height, because they share one
grid cell and the shorter would sit in blank space. The frame scales an image to
its own width, so draw the file at twice the width the shot will get where it
stands, measured from the layout rather than carried over. The state rail has its
own band above the image, so the mock can use its whole canvas. Take the palette
from the pair already here.

The script that draws a mock belongs in scratch, not in `scripts/`. A mock depicts
a console that does not exist, so nothing can make it false and nothing will re-run
its generator. `scripts/record-demo.py` stays because the stills it draws depict
leaf itself, so a change to leaf can make them stale and the generator has to
stay around to re-run.

## Previewing a page fixture

Run `scripts/preview.py [page]` to create a fresh vendored page, copy its
companion log, data, and media, and serve it at a local URL. Add `--export` to
write the rendered page as a standalone review file. Use `page init` and the
normal server commands for an authored page outside this corpus.
