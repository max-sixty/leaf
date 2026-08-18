# The examples

## Every widget and idiom in the vocabulary stands here

`examples/` is the whole corpus of eight sweeps in `test_render.py`: a page renders in
both palettes, holds still under a press, passes axe, gives up every passage to a quote,
answers an anchor written from its own file, and exports with its scripts gone. A widget
no example holds is a widget none of the eight has ever read inside a whole page, and the
gap reads as coverage, because the widget's own tests are green.

`lf-shot` and `lf-specimen` were outside the corpus from the day each was written — a
specimen stood on two `docs/` pages, which the sweeps do not read — so the sweep that
reads both palettes never reached one, and nothing could say a specimen's gutter was
painted in the dark palette until a fixture was written by hand for it
(`test_the_specimen_gutter_is_painted_in_both_schemes`).
`test_every_widget_in_the_vocabulary_stands_in_an_example` is the floor, read off the
registry, so the next widget joins the corpus by being declared.

The catalog's other half stands under the same floor and takes a second test to hold it
there. An idiom is declared as a selector rather than as a tag, so whether the corpus
holds one is a question for a layout engine rather than for a regex, and
`test_every_idiom_in_the_catalog_stands_in_an_example` puts every key to Chrome over the
authored markup — the authored markup and not the upgraded page, since a `<table>` a
module builds demonstrates nothing about the shape an author is being pointed at. Asking
at all is what keeps a key a selector: `pre > code.language-*` read perfectly well and
matched nothing, for as long as nothing asked.

The floor is the widget; the shapes it takes are a judgement. A `lf-options` group takes
its form from what its options hold and its arity from `multiple`, independently, so a
rule written for one form governs the other three combinations without saying so. No
example held a titled `multiple` group (a card form, in the days the forms were three).
The empty box saying a slot is untaken was then suppressed as though drawing it were the
list form's business, every example stayed green, and a titled group asking "which of
these" gave the reader nothing to count. Where an attribute or a content shape changes
what a reader sees, a page here shows it.

## An example is one version, and the log it ships beside it

The markup is v1 and nothing revises it, so `restated` and `overruled` stay out of reach:
each answers something a later version does — a decision to retract, a report to
overrule — and there is no later version here. `version check` refuses both.

The log is a different matter, and it was empty by default rather than by nature. A
thread is the one thing no markup describes, so an example that wants to show one ships
its events as `<stem>.jsonl` beside it, the way one that wants a screenshot ships the
bytes beside it, and every place that builds a page directory out of an example lays it
in: `scripts/preview.py`, `publish_pages` in `scripts/site.py`, and
`test_examples_pass_check`. `ship-review.jsonl` is the one today, and it is what a
reader meets on <https://leaf.page/examples/ship-review/> as much as under
`scripts/preview.py ship-review` — the published pages are served rather than exported,
so the log reaches the browser there through the session in its own tab.

Wherever the page is served, the cursor goes to the end of the seed with it. A seed is
history, not news: leave the cursor at zero and every preview hands the next agent
session a question to answer that the same log answers two lines further down, with the
loop guard rightly nagging about it each time. The demo would spend its first move
undoing itself.

Capture an anchor with `leaf comment --quote` against the file; don't write the
`{section, quote, suffix}` out by hand. Two captures with nothing holding them together
is the failure the repo's "the file's reading never claims more than the page's" is
about, and this one rots silently — a rewritten sentence leaves the quote resolving to
nothing and the thread standing there detached, with no error anywhere.
`test_a_shipped_log_opens_its_example_on_a_live_thread` reads the shipped anchor back
through the browser and names that when it happens; the corpus's own anchor sweep can't,
since it writes its own anchors.

`resolves` is reachable now that a comment can stand in the log, and nothing uses it.
The attribute would have to go in the markup, `scripts/gallery.py` embeds each example's
`<main>` verbatim, and the gallery's own directory has no seed to answer it — so
`version check` would refuse the gallery over an id naming no comment in *its* log.
Seeding a log costs the example nothing; hanging markup off that log couples it to
every page built from it.

## A page's connective prose is its own

The gesture vocabulary repeats and is meant to — every board takes a drag, every group
takes a pick — and the sentence around it does not, because a page that borrows one
describes its own work in another page's words. This is where that shows, the corpus
being the one place a reader sees them side by side. The rule itself is SKILL.md's
("announce interactivity in prose"), since it governs every page and not only these;
what lives here is the check.

A batch of them arrived in a single commit, and the cause was upstream of the corpus:
that same SKILL.md entry quoted two model sentences, and both reached shipped examples
word for word. `test_no_example_writes_another_example_s_sentences` holds the corpus at
twelve words, which is five more than any two examples share today — seven, and nothing
at all at eight. It is loose enough to let a single borrowed clause through, which is a
judgement no word count makes.

## The media an example names sits beside it

A `lf-shot` needs bytes a single file can't hold. `examples/media/` carries them,
content-addressed exactly as `leaf page media` names them in a page directory, and
every place that builds a page directory out of an example lays them in it: `serve` and
`test_an_installed_payload_passes_its_real_browser_gate` in `test_render.py`,
`test_examples_pass_check`, `publish_pages` in `scripts/site.py`, and
`scripts/preview.py`. A publisher that forgets fails loudly — `version check` refuses a
`/media/` reference the directory can't answer.

A pair is drawn rather than captured, since what it shows is a fiction the example needs.
Both images share one grid cell, so the box is the taller of them and a pair drawn at two
heights sits the shorter one in blank space. The frame scales an image to its own width,
so a file is drawn at twice the width the shot gets where it stands — for the JWT pair,
the ~494px the option card leaves once the `.facts` rail has taken its share, a width to
measure rather than a number to carry over. `.lf-shotcap` is absolute at the frame's
top-left, so a mock whose own title starts at the top edge publishes with BEFORE painted
across it. The palette comes off the pair already here.

The drawing script belongs in scratch, not `scripts/`. `scripts/record-demo.py` earns its
place because the stills it draws depict leaf, and a theme change once left the landing
page arguing for a product whose picture showed the previous one. A mock depicts a
console that doesn't exist, so nothing here can make it false and nothing would ever
re-run its generator.
