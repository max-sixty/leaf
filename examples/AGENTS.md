# The examples

Each top-level HTML file here is both a complete user page and an integration fixture,
and the website publishes it with the same vendored layer. The active cards in
`docs/examples.html` decide which pages the catalog lists and previews.

## Catalog pages

A catalog page is a real user task, such as a board, a short proposal or a draft, that
shows a distinct Leaf capability on the first visit. Keep it focused; exhaustive
vocabulary coverage belongs in the feature gallery and the package pages.

Each page has a `<title>` and `<meta name="description">` unlike every other page's;
the site build refuses a page without them and builds the page's link card and catalog
description from them. `docs/examples.html` sets catalog titles, grouping and order.

Each page writes its own sentences around gestures it shares with other pages
(`skills/leaf/references/authoring-evidence.md`, "Interactive and visual evidence"), so
review connective prose for clauses copied from another page.

## Developer pages and regression fixtures

`developer/feature-gallery.html` is the one home of synthetic scenarios for core
features. A change that adds or materially changes a core feature adds or updates its
scenario there, even when a public example already shows it. A scenario names the real
control or gesture, seeds the state it needs, and says what result to inspect. An
optional package's scenarios go on a page for that package.

Full-page regression journeys that don't belong in the showcase live under
`tests/fixtures/pages/`. They join the corpus and the page checks but are not website
routes.

## The corpus

`leaf-dev corpus` generates `corpus.html`, `corpus.data.json`, `corpus.jsonl` and
`corpus.page/` from the public examples, the developer pages and the regression
fixtures. Measure runtime cost on `corpus.html`; a small fixture can establish a cause
but not the cost.

The suite fails when the shipped vocabulary has a widget, idiom, declared attribute or
enum value that no corpus page shows; `layer.json` lists every optional bundled package
so their vocabulary is covered too. Where an attribute or content shape changes what a
user sees, a page shows that shape. `restated`, `overruled` and `resolves` are exempt,
since each needs a seeded log a later version contradicts; add one only when a page has
a real use for it.

A shape in the corpus has been rendered, not reviewed. When a sweep finds a defect, an
absent shape needs a fixture, and a present but unexamined one needs a look or a
`/ui-sweep` pass.

## Companions

An example's markup is its current version. Beside it may sit:

- `<stem>.page/`, copied to the page's `page/` when the example has its own
  declarations, modules or styles;
- `versions/<stem>.vN.html`, earlier versions, read in filename order;
- `<stem>.jsonl`, seeded events for what markup can't describe: a thread, a user
  decision, or a widget in a message;
- `<stem>.data.json`, each page-owned data source's current value, given literally or
  as a `$captures` entry naming a sibling file (`example_data.py`).

`prepare_page` in `dev/leaf_dev/page_fixtures.py` builds a page directory from an
example.

Capture a seeded anchor with `leaf thread open --quote` against the file; a
hand-written `{section, quote, suffix}` detaches silently when its sentence changes. The
suite checks each seeded message the way `leaf thread reply` does.

A widget that shows live time, such as an `lf-atlas-worker` row saying how long since
its worker reported, needs a seed so the corpus sweeps see it, and a fixture that sets
its own timestamps to pin what it says.

## Media

The images an `lf-shot` or a seeded message shows live under `examples/media/` in
`max-sixty/leaf-assets`, named by content as `leaf page media` names them.
`example_media()` (`dev/leaf_dev/page_fixtures.py`) returns the pinned copy, and every
builder of a page directory copies them in. `uv run leaf-dev publish-media FILE...`
adds media, moves the pin and prints the `/media/` path a page uses; commit the pin,
not the image.

Draw a before/after pair rather than capturing it: both images at one height, at twice
the width the shot gets on the page, with the palette of the pairs already published.
Keep a mock's generator in scratch. A generator of images that show Leaf itself, such
as `leaf-dev record-demo`, is tracked, because a change to Leaf can make those images
stale.
