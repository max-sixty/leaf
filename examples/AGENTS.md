# The examples

Each top-level HTML file here is both a complete user page and an integration fixture,
and the website publishes it with the same vendored layer. The active cards in
`docs/examples.html` decide which pages the catalog lists and which get previews.

## Catalog pages

A catalog page is a coherent artifact for a real user task that makes a distinct Leaf
capability apparent on the first visit. Keep it focused: a board, a short proposal, or
a draft is enough. Exhaustive vocabulary coverage belongs in the feature gallery and
the package pages.

Each page's `<title>` and `<meta name="description">` differ from every other page's.
The site build makes the catalog card from them and refuses a page missing either
(`dev/leaf_dev/site.py`).

Each page writes its own sentences around the gestures it shares with other pages
(`skills/leaf/references/authoring-evidence.md`, "Interactive and visual evidence").
The suite refuses a run of twelve words two examples share, and a shorter borrowed
clause is still a review finding.

## Developer pages and regression fixtures

`developer/feature-gallery.html` is the one home of synthetic scenarios for core
features. A change that adds or materially changes a core feature adds or updates its
scenario there, even when a public example already shows it. A scenario names the real
control or gesture, seeds the state it needs, and says what result to inspect; for
injected chrome whose state comes from outside the document, the gallery's browser test
exercises that condition. An optional package's scenarios go on a focused package page.

Full-page regression journeys that no longer belong in the showcase live under
`tests/fixtures/pages/`. They join the corpus and the page checks but are not website
routes.

## The corpus

`leaf-dev corpus` generates `corpus.html`, `corpus.data.json`, `corpus.jsonl`, and
`corpus.page/` from the public examples, the developer pages, and the regression
fixtures. Measure runtime cost on `corpus.html`; a small fixture can establish a cause
but not the cost.

The suite refuses a widget or idiom in the shipped vocabulary that no corpus source
holds, and a declared attribute or enum value no example shows. `layer.json` lists
every optional bundled package so those checks cover its vocabulary. Where an attribute
or content shape changes what a user sees (an `lf-options` group's form, arity,
joining, and `label` vary independently), a page shows that shape. `restated`,
`overruled`, and `resolves` are exempt, since each needs a seeded log a later version
contradicts or depends on; add one only when a page has a real use for it.

A shape in the corpus has been rendered, not judged. When a sweep finds a defect, an
absent shape needs a fixture, and a present but unexamined one needs a reading or a
`/ui-sweep` pass.

## Companions

An example's markup is its current version. Beside it may sit:

- `<stem>.page/`, copied to the page's `page/` when the example owns declarations,
  modules, or styles;
- `versions/<stem>.vN.html`, each earlier version, read in filename order;
- `<stem>.jsonl`, seeded events for what markup cannot describe: a thread, a user
  decision, or a widget in a message;
- `<stem>.data.json`, each page-owned data source's current value, given literally
  or as a `$captures` entry naming a sibling file (`example_data.py`).

`prepare_page` in `dev/leaf_dev/page_fixtures.py` builds a page directory from an
example.

Capture a seeded anchor with `leaf thread open --quote` against the file; a
hand-written `{section, quote, suffix}` detaches silently when its sentence changes.
The suite posts each seeded message fragment through the check `leaf thread reply`
runs.

A widget with a live half, such as an `lf-agent` row saying how long since its worker
reported, needs a seed so the corpus sweeps see it, and a fixture that mints its own
timestamps to pin what it says.

## Media

The images an `lf-shot` or a seeded message names live under `examples/media/` in
`max-sixty/leaf-assets`, named by content as `leaf page media` names them.
`example_media()` (`dev/leaf_dev/page_fixtures.py`) returns the pinned copy, and every
builder of a page directory lays them in. `uv run leaf-dev publish-media IMAGE...` adds
images, moves the pin, and prints the `/media/` path each page names; commit the pin,
not the image.

Draw a before/after pair rather than capturing it: both images at one height, at twice
the width the shot gets on the page, in the palette of the pairs already published. A
mock of something outside Leaf, such as a console, never goes stale, so its generator
stays in scratch. A generator for images of Leaf itself, such as `leaf-dev
record-demo`, is tracked, because a change to Leaf makes those images stale.
