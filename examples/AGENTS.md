# The examples

Each top-level HTML file here is both a complete user page and an integration fixture,
and the website publishes it with the same layer. The active cards in
`docs/examples.html` decide which pages the catalog lists, and in what groups and order.

## Catalog pages

A catalog page is a real user task, such as a board, a short proposal or a draft, that
shows a distinct Leaf capability on the first visit. Keep it focused; exhaustive
vocabulary coverage belongs in the feature gallery and the package pages.
Its `<title>` and `<meta name="description">`, unique to it, make its link card and
catalog caption. Each page writes its own sentences around the gestures it shares with
other pages (`skills/leaf/references/authoring-evidence.md`, "Interactive and visual
evidence").

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

`corpus.html` and its companions are ignored snapshots composed from the public
examples, developer pages and regression fixtures. Preview, probe, benchmarks and the
combined-page tests generate them on demand, and `leaf-dev corpus` builds one
explicitly. Running corpus previews follow source edits as individual previews do, so
edit the source pages, with no regeneration step before committing. Measure runtime
cost on the corpus; a small fixture can establish a cause but not the cost.

The suite fails when the shipped vocabulary, optional bundled packages included, has a
widget, idiom, declared attribute or enum value that no corpus page shows. Where an
attribute or content shape changes what a
user sees, a page shows that shape. `restated`, `overruled` and `resolves` are exempt,
since each needs a seeded log a later version contradicts.

A shape in the corpus has been rendered, not reviewed. When a sweep finds a defect, an
absent shape needs a fixture, and a present but unexamined one needs a look or a
`/ui-sweep` pass.

## Companions

An example's markup is its current version. Beside it may sit:

- `<stem>.page/`, copied to the page's `page/` when the example has its own
  declarations, modules or styles;
- `versions/<stem>.vN.html`, earlier versions, read in filename order;
- `<stem>.jsonl`, seeded events for what markup can't describe: a thread, a user
  decision, or a widget in a message. Each line is an event as its writer would send
  it, which the page admits through the append door, so leave out what admission
  derives, such as an action's `meaning`;
- `<stem>.data.json`, each page-owned data source's current value (`example_data.py`
  says how to give it).

`prepare_page` in `dev/leaf_dev/page_fixtures.py` builds a page directory from an
example.

To run `leaf page check` on an example, check the page directory a plain preview
builds, since the command takes a page directory and not the `.html` (a bare
`page init` plus a copy misses the `.page/` companion and its packages). Start
`uv run leaf-dev preview <example> --slot chk` as a long-running command, then run
`bin/leaf page check .tmp/previews/chk` and stop the preview.

Capture a seeded anchor with `leaf thread create --quote` against the file, since a
hand-written `{section, quote, suffix}` detaches silently when its sentence changes.
A widget that shows live time, such as an `lf-atlas-worker` row saying how long since
its worker reported, needs a seed so the corpus sweeps see it, and a fixture that sets
its own timestamps to pin what it says.

## Media

The images an `lf-shot` or a seeded message shows live under `examples/media/` in
`max-sixty/leaf-assets`, named by content as `leaf page media` names them, and every
builder of a page directory copies them in. `uv run leaf-dev publish-media FILE...`
adds media, moves the pin and prints the `/media/` path a page uses; commit the pin,
not the image.

Draw a before/after pair rather than capturing it: both images at one height, at twice
the width the shot gets on the page, with the palette of the pairs already published.
Keep a mock's generator in scratch. A generator of images that show Leaf itself, such
as `leaf-dev record-demo`, is tracked, because a change to Leaf can make those images
stale.
