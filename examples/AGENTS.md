# The examples

Each top-level authored HTML file is both a complete user page and an integration
fixture, and the website publishes it with the same vendored layer. The active cards
in `docs/examples.html` decide catalog membership and which previews are generated;
an unlisted page can stay published.

## Catalog pages

Every catalog entry stands as a coherent artifact for a real user task and makes a
distinct Leaf capability apparent on the first visit. Subject novelty, length, or
vocabulary coverage alone does not qualify a page. Keep pages focused; a board,
a short proposal, or a draft is enough. Exhaustive vocabulary coverage belongs to
the feature gallery and the package pages.

Each page's `<title>` and `<meta name="description">` differ from every other
page's. The site build composes the catalog card from them and refuses a page
missing either.

A page's connective prose is its own. Gestures repeat across pages; the sentences
around them do not. The rule lives in `references/authoring-evidence.md`,
"Interactive and visual evidence", and
`test_no_example_writes_another_example_s_sentences` refuses a run of more than twelve
shared words. A shorter borrowed clause is still a review finding.

## Developer pages and regression fixtures

`developer/feature-gallery.html` is the one home of synthetic core feature
scenarios, and every core Leaf feature is directly exercisable there. A change that
adds or materially changes a core feature adds or updates its specimen in the
gallery; coverage in a public example does not substitute. A specimen names the real
control or gesture, seeds the state it needs, and tells the developer what result to
inspect. For injected chrome whose state comes from outside the document, name that
condition and exercise it in the gallery's browser test. An optional package's
specimens go on a focused package page, reusing a worked example where one already
tells that package's story.

Full-page regression journeys that no longer belong in the showcase live under
`tests/fixtures/pages/`. They join the corpus and page checks but are not website
routes. Developer pages and regression fixtures follow the companion conventions
below.

## The corpus

`corpus.html`, `corpus.data.json`, `corpus.jsonl`, and `corpus.page/` are generated
from the sources by `scripts/corpus.py`.

Every widget and idiom in the shipped vocabulary stands in some corpus source, and
the suite refuses one that does not. `examples/layer.json` lists every bundled
package, used or not, because those floors read it to decide what vocabulary they
cover. The floors guarantee a widget appears, not which of its shapes do: where an
attribute or content shape changes what a user sees (an `lf-options` group's form,
arity, joining, and `label` vary independently), a page shows that shape. `restated`,
`overruled`, and `resolves` need a seeded log a later version contradicts or depends
on; add one when a page has a real use for it, not to fill the slot.

A shape that stands in the corpus has been rendered, not judged. When a sweep finds
a defect, ask which gap let it through: an absent shape needs a fixture, and a
present but unexamined one needs a reading or a `/ui-sweep` pass.

Measure runtime cost across the composed surface on `corpus.html`; a small fixture
can establish a cause but not the cost.

## Companions

An example's markup is its current version. Beside it may sit:

- `<stem>.page/`, copied to the page's `page/` when the example owns declarations,
  modules, or styles;
- `versions/<stem>.vN.html`, each earlier version, read in filename order; they sit
  outside the top level so discovery and the prose sweeps never read one as a page;
- `<stem>.jsonl`, seeded events: a thread, a user decision, or a widget in a message,
  which no markup can describe;
- `<stem>.data.json`, each page-owned source id's current value, or a `$captures`
  entry naming a sibling file (`format` defaults to `text`; `unified-diff` reads a
  whole `.patch`).

`prepare_page` in `scripts/page_fixtures.py` is the one builder of a page directory
from an example; its docstring gives the build order.

Capture a seeded anchor with `leaf thread open --quote` against the file. Never
write `{section, quote, suffix}` by hand: a hand-written anchor detaches silently
when its sentence changes. Seeded message markup must pass the door `leaf thread
reply` runs, and the suite posts each fragment through it.

A widget with a live half, such as an `lf-agent` row saying how long since its
worker reported, needs both a seed so the corpus sweeps see it and a fixture that
mints its own timestamps to pin what it says, since a seed's `ts` is a fixed instant.

## Media

`examples/media/` holds the bytes an `lf-shot` or a seeded message names,
content-addressed as `leaf page media` names them. Every builder of a page directory
lays them in: `prepare_page`, and any test that builds a page by hand.

Draw a before/after pair rather than capturing it. Draw both images at one height,
at twice the width the shot gets on the page as measured from the layout, and take
the palette from the pair already here. A mock's generator belongs in scratch, since
nothing can make a depicted console false. A generator for images that depict Leaf
itself, such as `scripts/record-demo.py`, stays in `scripts/` because a change to
Leaf can make them stale.
