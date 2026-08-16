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

## An example is one version with an empty log

`restated`, `overruled` and `resolves` each name something the log holds — an action to
retract, a standing report to answer, a comment to close — so a page published as v1 with
nothing behind it cannot earn one, and `version check` refuses all three here. That is
the whole of what the corpus can't reach.

## The media an example names sits beside it

A `lf-shot` needs bytes a single file can't hold. `examples/media/` carries them,
content-addressed exactly as `leaf page media` names them in a page directory, and
every place that builds a page directory out of an example lays them in it: `serve` and
`test_an_installed_payload_passes_its_real_browser_gate` in `test_render.py`,
`test_examples_pass_check`, `export_examples` in `scripts/site.py`, and
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
