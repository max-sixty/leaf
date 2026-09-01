# The examples

Each authored HTML file is both a complete page and an integration fixture. The
website publishes those pages with the same vendored layer. `corpus.html` and
`corpus.data.json` are generated internal views; edit the individual example and
regenerate the corpus instead of patching either output.

## Every widget and idiom in the vocabulary stands here

The nightly run uses this corpus in two ways. Page-sensitive contracts run every
fixture, including the generated corpus: each renders in both palettes,
passes axe, and exports with its scripts gone. Authored-content sweeps quote every
source passage and resolve anchors written from every source file; the corpus
generation check proves those sources are what the derived view carries. Shared
runtime mechanisms use causal representatives instead of repeating the same gesture
over every page, and each representative has a non-vacuity floor naming the reason it
stands there. So a widget that stands in no source example is one the whole-page
contracts have never seen. That gap is easy to miss, because the widget's own tests
are green — the missing coverage reads as coverage.

It happened to `lf-shot` and `lf-specimen`: both were outside the corpus from the
day they were written. A specimen stood on two `docs/` pages, and the sweeps do
not read `docs/`, so the sweep that reads both palettes never reached one, and
nothing could say whether a specimen's gutter was painted in the dark palette
until a fixture was written for it by hand
(`test_the_specimen_gutter_is_painted_in_both_schemes`).
`test_every_widget_in_the_vocabulary_stands_in_an_example` is the floor now: it
reads the widget list off the registry, so the next widget joins the corpus by
being declared. Which registry is the other half of that question, and it is read
off `layer.json` (`SHIPPED_PACKAGES`) rather than written into the test. A floor
that names its own packages stops covering the next one: `lf-diagram` and
`lf-diff` moved into the `diagram` and `diff` packages and would have dropped out
of every sweep in silence, and `pr-review`'s two widgets had never been under one
at all.

Idioms — the catalog's other half — sit under the same floor, and holding them
there takes a second test. An idiom is declared as a CSS selector rather than as
a tag name, so whether the corpus holds one is a question for a layout engine
rather than for a regex. `test_every_idiom_in_the_catalog_stands_in_an_example`
therefore puts every idiom key to Chrome, matched against the authored markup.
The authored markup, not the upgraded page: a `<table>` a module builds
demonstrates nothing about the shape an author is being pointed at. Asking Chrome
at all is also what keeps each key a working selector —
`pre > code.language-*` read perfectly well and matched nothing, for as long as
nothing asked.

The floor only guarantees the widget appears; which of its shapes appear is a
judgement. An `lf-options` group takes its form from what its options hold, its
arity from `multiple`, whether it is joined into one control from `choose` and
`settled`, and whether it asks its question on itself from `label` — axes that
vary independently, so a rule written against one combination governs the rest
without saying so. No example held a titled `multiple` group (a card form, in the
days the forms were three). So when the empty box that says a slot is untaken was
suppressed — as though drawing it were the list form's business alone — every
example stayed green, and a titled group asking "which of these" gave the reader
nothing to count. Where an attribute or a content shape changes what a reader
sees, a page here shows that shape.

## Standing here is not the same as having been looked at

The floor guarantees a shape is *rendered*. It never guarantees anyone *judged*
what was rendered, and the two are easy to confuse because a corpus that holds
the shape reads like a corpus that has checked it.

`label` is the case that separates them. It arrived with its corpus shape in the
same commit: a `choose` group carrying a question, on `design-decision.html`,
joined into one control and drawn on every nightly run in both palettes and in
print. The joined control gave that question none of the inset it gives every
other cell, so it sat on the frame a full address column left of the words it was
a question about, with dead ground under the hairline below it. The page was
green for three days. Nothing in the loop looked at a composed page and judged
spacing, and `corpus.html` — the heaviest page a UI sweep tours — showed the same
group.

So a coverage gap and a judging gap want different answers, and only one of them
is this file's. The settled form's question ordering was genuinely absent from
the corpus and a page fixed it. The spacing was not absent; it was unexamined,
and what closed it was a test that reads every cell of a joined control plus
using the page. Note where that test is not: a reading in the render gate had to
find the control by fingerprint, and a board column and a framed `<details>` wear
the same one, so the gate would have failed correct pages to catch leaf's own
theme. When a sweep finds something here, ask which of the two let it through
before adding a page: a page that only re-renders a shape nobody judges buys
nothing.

Use `corpus.html` when measuring runtime cost across the composed surface. A small
fixture can establish a cause, but it cannot stand in for the composed surface.

## An example is one stamped version, plus any log and data it ships beside it

`examples/layer.json` names the package selections shared by the corpus. Preview,
lint, and site tooling all read that list, so the pages exercise the same vendored
layer the website serves. Every bundled package belongs in it, whether or not a
page uses that package today: the list is what the corpus floors read to decide
which vocabulary they cover.

An example's markup is the source stamped as v1, and nothing ever revises it.
That puts `restated` and `overruled` out of reach: each answers something only a
later revision does — `restated` retracts a decision, `overruled` keeps a
revision's own state over a report — and there is no later revision here.
`version check` refuses both.

The log is a different matter: it was empty by default, not by nature. A thread
is the one thing no markup describes, so an example that wants to show one ships
its events as `<stem>.jsonl` beside the page, the way an example that wants a
screenshot ships the image bytes beside it. Every place that builds a page
directory out of an example lays the log in: `scripts/preview.py`,
`publish_pages` in `scripts/site.py`, `test_examples_pass_check`, and `serve` in
`tests/render_support.py`. That last one is the browser corpus, and it laid an example's
media in while leaving its log out — so the corpus sweeps read every example as a
page with nothing standing on it, which is not a page anybody is served. `serve`
seeds when it is handed an example rather than markup, and sets the cursor past
the seed as `preview.py` does. One sweep opts out and says why: the anchor sweep
writes its own anchors and compares the whole painted mark against exactly
those, so a seeded thread's mark would read there as text the page never named.
`ship-review.jsonl` is the one such log today, and a reader meets it on
<https://leaf.page/examples/ship-review/> as much as under
`scripts/preview.py ship-review` — the published pages are served rather than
exported, so the log reaches the browser there through the session running in the
reader's own tab.

External data is the other companion state. An example that binds a widget input to a
source ships `<stem>.data.json`, mapping each page-owned source id to its complete
current value. A reserved `$captures` object instead maps a source id to `file` and
optional `format`, `label`, or `lines`; the file is a sibling of the example. The
format defaults to `text`, where `lines` may select an inclusive range. Builders apply
captures first and then current values through `leaf data capture` and `leaf data set`,
so binding, contract validation, revisioning, live preview, browser sweeps, and the
static site all exercise the real doors. `scripts/corpus.py` composes those companions
into `corpus.data.json`; edit the individual example's files and regenerate rather
than patching the corpus copies. A selected snapshot number must stay valid both in
its own page and in corpus composition, so the first capture in the first contributing
example owns snapshot `1`; grow this fixture convention only when another capture
actually needs to compose.

A large unified diff stays in its `.patch` source file. Capture it with
`"format": "unified-diff"`; the public capture door validates and splits it into the
file manifest, so the raw patch remains the human-auditable fixture while the browser
receives only its manifest until a file opens.

Wherever the page is served, the cursor is set to the end of the seeded log. A
seed is history, not news. Leave the cursor at zero and every preview hands the
next agent session a question to answer that the same log already answers two
lines further down, with the loop guard rightly nagging about it each time. The
demo would spend its first move undoing itself.

When a seeded event needs an anchor, capture it with `leaf comment --quote`
against the file; don't write the `{section, quote, suffix}` out by hand. A
hand-written anchor is a second capture with nothing holding it to the first,
which is the failure the repo's norm "the file's reading never claims more than
the page's" is about — and this instance rots silently: rewrite the sentence the
quote points at, and the quote resolves to nothing, the thread stands there
detached, and no error appears anywhere.
`test_a_shipped_log_opens_its_example_on_a_live_thread` reads the shipped anchor
back through the browser and names that failure when it happens. The corpus's own
anchor sweep can't catch it, because that sweep writes its own anchors.

`resolves` is reachable now that a comment can stand in a shipped log, and no
example uses it, deliberately. The attribute would have to go in the markup, and
the markup travels further than the log: `scripts/corpus.py` embeds each
example's `<main>` verbatim, the corpus's own directory has no seed, and
`version check` would refuse the corpus over an id naming no comment in *its*
log. Seeding a log costs the example nothing; hanging markup off that log couples
the markup to every page built from it.

A seed reaches one thing further than a thread, and stops one short of the rest.
Some widgets have a live half — a rendering that only exists once the log holds
something — and without a seed the corpus sweeps never see it. An `lf-agent` row
renders how long since that worker was last heard from, so on a page with no
reports, every sweep passes over a roster that has never once said the thing it
is for. That is `lf-shot`'s gap arrived at from the other side: the widget stands
in an example, and the corpus still reads only its static half. A seeded report
is what puts the live line on the page. What the seed cannot do is hold a clock
still: its `ts` is a fixed instant and the line renders against now, so the words
drift with the calendar — fine for a thread, where "3d ago" is colour, and
useless as an assertion. So the seed makes the rendering visible, and what the
rendering says is pinned in fixtures that mint their own timestamps
(`test_a_rosters_row_says_when_the_log_last_heard_from_that_worker`,
`test_a_worker_that_has_never_reported_dates_from_its_version`). The next widget
with a live half owes both halves: the seed and the fixture.

A seed is also the only way a widget reaches the corpus in a message. Markup can
be two things — a version's content, and an event's `markup` field — and the
second renders in the panel and nowhere else, so no authored page substitutes
for it however many widgets it holds. `ship-review.jsonl` carries the shape:
Claude answers with a question of its own, a `multiple` group whose Done press is
the reader saying the set is whole. What reads it is
`test_a_shipped_log_opens_its_example_on_a_live_thread`, which opens the panel
and asks that each widget the log carries is drawn and, where the registry
declares the element awaits an answer, that the runtime built something inside
it to answer with.

And the seed carries the answer as well as the question, because a decision on
such a widget is folded through a projection of its own (`thread_state`) and
replayed into a tree the panel built, and a corpus holding only the question
reads the untouched half of every one of them — the widget's own gap, one turn
further in. `ship-review.jsonl` has the reader ticking two of the three and not
yet pressing Done, so the group is both decided and still asking. The same test
reads it, against the neighbour that separates a replay from a rendering: the
same page under the same log with the decisions removed. A widget that says the
same either way was never reached, and a drawn widget with a built control says
nothing about whose state is on it.

A hand-written seed is markup no gate reads. `version check` asks it only for ids
colliding with the version's, and `leaf reply` — the door that validates an
agent's `markup` before freezing it in an append-only log — never sees a file
written into the repository. So
`test_every_seeded_fragment_passes_the_door_it_never_came_through` posts each
seeded fragment through that real door rather than through a list of checks
copied out of it, since a second gate spelling out today's list is the one that
goes on not asking whatever the first learns to.

Rendering that shape for the first time reported two faults in the render gate,
both of them the same mistake: a reading assumed a widget stands in the document.
`UNREACHABLE_WORDS` took any `.lf-ui` above a widget's words for the widget's own
chrome, which is true on a page and inside out in a message, so it refused every
question ever asked in a reply. `SILENT_WORDS` asked whether a painted
attribute's quiet word had a box, and a message in a shut panel has no boxes at
all, so it called the panel's state the widget's. Neither could be found by
reading: the gate walks text nodes rather than boxes and had been reading the
panel all along, with the panel shut, on a corpus that never put anything there.

## A page's connective prose is its own

The gesture vocabulary repeats, and is meant to: every board takes a drag, every
group takes a pick. The sentence around the gesture must not repeat, because a
page that borrows another page's sentence describes its own work in another
page's words. The corpus is where the borrowing shows, being the one place a
reader sees the examples side by side. The rule lives in
references/authoring-evidence.md under "Interactive and visual evidence", since
it governs every interactive page and not only these; what lives here is the
check.

A batch of borrowed sentences once arrived in a single commit, and the cause was
upstream of the corpus: the authoring guidance quoted two model sentences, and
both reached shipped examples word for word.
`test_no_example_writes_another_example_s_sentences` holds the corpus to at most
twelve consecutive shared words. Today no two examples share more than seven, and
none share eight, so the cap sits five clear of everything real — loose enough to
let a single borrowed clause through, which is a judgement no word count makes.

## The media an example names sits beside it

An `lf-shot` needs image bytes a single file can't hold. `examples/media/`
carries them, content-addressed exactly as `leaf page media` names them in a page
directory, and every place that builds a page directory out of an example lays
them in: `serve` and `test_an_installed_payload_passes_its_real_browser_gate` in
the browser test modules, `test_examples_pass_check`, `publish_pages` in
`scripts/site.py`, and `scripts/preview.py`. A publisher that forgets fails
loudly, because `version check` refuses a `/media/` reference the directory can't
answer.

A before/after pair is drawn rather than captured, since what it shows is a
fiction the example needs. Both images share one grid cell, so the cell's box is
the taller of the two, and a pair drawn at two heights sits the shorter one in
blank space — draw both at one height. The frame scales an image to its own
width, so draw the file at twice the width the shot will get where it stands; for
the JWT pair that is the ~494px the option card leaves once the `.facts` rail has
taken its share, and it is a width to measure rather than a number to carry over.
`.lf-shotcap` sits absolutely at the frame's top-left, so a mock whose own title
starts at the top edge publishes with BEFORE painted across it — leave that
corner clear. And take the palette from the pair already here.

The script that draws a mock belongs in scratch, not in `scripts/`.
`scripts/record-demo.py` earns its place there because the stills it draws depict
leaf itself, so a change to leaf can make them false — a theme change once left
the landing page arguing for a product whose picture showed the previous theme —
and the generator has to stay around to re-run. A mock depicts a console that
doesn't exist: nothing here can make it false, and nothing would ever re-run its
generator.

## Previewing an example

Run `scripts/preview.py [example]` to create a fresh vendored page, copy its
companion log, data, and media, and serve it at a local URL. Add `--export` to
write the rendered page as a standalone review file. Use `page init` and the
normal server commands for an authored page outside this corpus.
