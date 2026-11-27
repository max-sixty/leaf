# Browser support gaps

Track unresolved browser failures, accepted visual differences, and missing
capabilities that still require a fallback or constrain Leaf's implementation.
Coverage includes Chrome, Edge, Firefox, Safari, their mobile versions and
embedded browsers where Leaf is used. This is a list of known gaps, not a claim
that every other feature has been tested across those browsers.

## Recording and assessing a gap

Keep the current user-visible effect, code owner, dated browser evidence,
disposition, and a regression test or minimal reproduction that can settle a
recheck. A recheck settles nothing unless it fails on the engine the gap was
recorded in, so confirm that before citing a pass as the gap closing, and name
Playwright engines by build as well as version, since two builds can report one
version. Distinguish an installed test engine from a current stable browser,
and observed behavior from published compatibility data. A successful API
adoption needs no entry. Resolved failures leave this list; reasons the current
implementation still needs belong beside its code. Rewrite an entry when its
status changes rather than appending the investigation's chronology.
`uv run leaf-dev probe SOURCE --browser firefox` (or `webkit`) runs a probe or
journey in Playwright's Firefox or WebKit, and `--browser ios` runs a probe in
Safari on an iPhone simulator, whose WebKit can differ from Playwright's desktop
build. `leaf-dev stills --browser` compares a change's states in any of them.

Minor visual differences are acceptable when content remains readable and
controls remain usable. Lost drafts, broken actions, inaccessible controls, and
movement that disrupts a gesture need a fix or an explicit support decision.
An unsupported API alone does not justify blocking the whole browser: record
what fails and what still works.

Record a gap and leave it, rather than correcting it in Leaf's code, unless it
shows on a path users take often or does one of the things above that need a
fix. A correction is a second answer to a question the browser already answers,
so every later change has to keep it working, and someone has to notice when the
engine catches up and delete it. The entry's recheck says when that has
happened. Where engines differ on a feature and another feature does the job the
same way in every engine, use the second.

## Known gaps

### Native select keyboard input in the test engine

On 2026-11-01, Playwright 1.64.1's Chromium headless shell 156.0.8078.4,
build 1248, on macOS 26.5.1 left a focused native select unchanged after
ArrowDown, Space → ArrowDown → Enter, Alt+ArrowDown → ArrowUp → Enter, and
Home → Enter. Keyboard events reached the select without being prevented.
The same sequences behaved alike on a Leaf page and a plain, script-free
select. Typing `t` then Enter changed Page to Ticket in both, providing a
working keyboard route. This observation does not establish a Leaf defect or
the behavior of the host's Chrome or another test-engine build.

Recheck with `leaf_dev.browser.headless_shell`: give a plain select the options
Page, Ticket and Off, focus it, and send those sequences with
`page.keyboard.press`, reading its value after each sequence. Compare the
same actions on the page under review. Native selection remains browser-owned;
there is no Leaf workaround.

### Report metadata in a revealed table

On 2026-10-31, installed Google Chrome 156.0.8078.76, driven headlessly through
Playwright's `chrome` channel at 1280×800, repeatedly crashed its renderer when
the continuing hill-climb report opened Cases & outputs → Overview. The report's
output table includes several `<small>` metadata lines in each Version cell.
Changing only their `display: block` to `display: flow-root` preserved the layout
and allowed repeated visits. The report stylesheet in
`dev/leaf_dev/commands/eval/report.py` keeps that formatting context.

Recheck the populated report produced by `leaf-dev eval report`: override
`.sample-table small { display: block !important; }`, visit another tab, then
open the output index and capture the viewport. Compare the same source and
browser with `display: flow-root`. Inline metadata without line breaks also
survived, but explicit `<br>` breaks did not. Disabling CSS highlights, table
containment, masks or background painting did not repair the observed crash.
This is a bounded report reproduction, not a standalone browser-engine diagnosis
or a claim about other Chrome builds or engines.

### Walking every element of a page of millions in Chromium

The pages Leaf's checks and measurements drive are opened by
`dev/leaf_dev/browser.py`. On 2026-11-15, on macOS 26.5.1, Playwright 1.65.0's
Chromium headless shell 158.0.8127.18, build 1254, and installed Google Chrome
157.0.8103.51, driven headlessly through Playwright's `chrome` channel, crashed
the renderer of a page of 2.96 million elements partway through a run of
back-to-back walks over every element. Playwright reported `Target crashed`,
and the browser's log `V8 process OOM (ExternalEntityTable::AllocateEntry)`. A
script's `for (const el of document.querySelectorAll("*"))` is such a walk, and
crashed on the 24th to 26th. Each `page.query_selector` for a CSS selector is
one too, because Playwright's injected CSS engine walks every element that way
to look inside shadow roots, and crashed between the 22nd and the 32nd. A page
of plain `div` rows built by a script crashed as the page of issue #4781 did,
30 text documents of 4 MB with as many elements. With a forced full garbage
collection after each walk (CDP `HeapProfiler.collectGarbage`), 100 walks
passed, and 60 walks over 1.48 million elements passed without one. The counts
fit one entry for each element a walk wraps, in a V8 pointer table of 2^26
entries whose dead entries only a full collection frees; that mechanism is
inferred from the counts, not read from V8.

Opening #4781's 30 tabs walks only each opened document, and clicking them one
after another crashed neither Chromium nor Playwright's Firefox 159.0, build
1572; Firefox also survived the same journey driven by `page.query_selector`. A
check or measurement that drives a page this size through Playwright selectors
crashes the renderer itself, so it finds controls with `document.querySelector`
inside `page.evaluate` and clicks the returned position with `page.mouse`.
There is no Leaf workaround.

Recheck: in a blank page opened by `leaf_dev.browser.launch("chromium")`, build
2.96 million `div` rows by script and run the script walk above 100 times in a
row, then again with a forced full collection after each walk. The gap stands
while the first run ends in `Target crashed` and the second passes all 100.

### Tab underline travel between anchors

The selected-tab underline in `packages/default/styles/tabs.css` follows its
label with CSS anchors. Playwright Firefox 155.0, build 1543, moved directly to
the new anchor on 2026-10-26, without a transition or `transitionrun` event;
Chromium 153.0.8010.12 interpolated its position and width. Instant selection
is an accepted visual difference: the selected label, panel, keyboard routes
and nested strips remain usable. Recheck by opening `code-comparison` with
`leaf-dev probe --firefox --motion no-preference`, selecting the adjacent tab
with the pointer and inspecting `.lf-tab-selection` across animation frames.
The Chromium behavior and interruption contract are covered by
`test_pointer_tab_underline_moves_without_delaying_the_view` in
`tests/browser/widgets/test_tabs.py`.

### Baseline content-alignment

Option cards laid across align their titles with `align-content: first baseline`
(`packages/default/styles/options.css`). Playwright Chromium 153.0.8010.12 parsed
the value but left grid items' contents at their start on 2026-10-25, while
Playwright Firefox 155.0 shifted each item's contents onto the row's shared
baseline. In Chromium a card whose chips wrap past the state seat's line, such as
the canary card in `examples/alert-review.html`, still sets its title a chip line
lower than its neighbours' (22px there); chips that fit beside the seat stay
aligned in both engines. Table cells' `vertical-align: baseline` aligns them in
Chromium, but Firefox 155.0 then leaves the row short of the shifted contents and
clips them, so it can't stand in. Recheck with the `browser` case of
`test_cards_laid_across_align_their_titles_whatever_chips_open_them` in
`tests/browser/widgets/test_obligations.py`, extended to its `all` row.

Firefox 155.0 holds that shift only through a layout of the whole row. After a
later reflow dirties one card, such as an absolutely positioned child inserted or
its padding changed, it lays the row out again and drops another card's shift,
on 2026-10-26 in a plain grid with no Leaf code as well. A forced layout in the
middle of the options render, between its insertions of key badges and marks,
therefore left a card whose chips wrap a chip line or two below its neighbours on
load, until a resize; `lf-options.js` reads computed style only when a surface
shows an option's consequence for that reason. The test's `firefox_browser` case
catches a render that splits the row's first layout again.

### A recomputed length less a percentage counts as a change in Chromium

Playwright Chromium 158.0.8127.18 (build 1254) counted an inheriting registered
`<length-percentage>` whose value mixes a length with a percentage, such as
`calc(10px - 50%)` or `max(0px, 10px - 50%)`, as changed each time its element
was restyled, the value unchanged, so every restyle of that element restyled its
children too, and children that set the property again a level further. A plain
length, a plain percentage, or the same expression registered `*`, restyled the
element alone. On 2026-11-10, a class on a column page's `main` that changed
nothing restyled 246 elements at 10 sections, and 6 with the room set to a
constant; focus marking `main` as the user landed on a passage did the same.

It holds for a property that doesn't inherit too, where the element also states
a length in container units: on 2026-11-11, with the column's room in
non-inheriting `<length-percentage>` properties and its shell's width in `cqi`, a
`:has()` asked again of `main` as focus moved restyled every element under it:
7,152 elements a move at 1,024 sections, and 1,014 with the room registered `*`.
So the column resolves the lengths in its room in registered `<length>`
properties (`--lf-room-length`, `browser/layouts.css`) and
states the room from them, percentage and all, only in `--lf-free-start` and its
kin, registered `*`. Firefox and WebKit were not checked. Recheck by registering
`--lf-free-start` `<length-percentage>` again:
`test_a_focus_move_near_a_long_pages_end_restyles_what_focus_marks` in
`tests/browser/test_chrome_contracts.py` fails while the gap stands.

### A near-grey colour's hue in relative `oklch()` in Chromium

Playwright Chromium 158.0.8127.18 (build 1254) reads the hue of a low-chroma colour as
`none` in a relative `oklch()`: on 2026-11-14,
`oklch(from #d1d0cc l calc(c * 3.4) h)` computed to `oklch(0.857 0.019 none)` and
painted `rgb(219, 203, 207)`, a pink, where Firefox 159 and WebKit 27.2 kept the hue
(95) and painted `rgb(212, 208, 195)`. The colour's chroma is 0.0055, and a hue of
`none` is drawn at 0. The theme's neutrals are near-grey mixes of the paper and ink
whose chroma is raised (`browser/styles/tokens.css`, at `--lf-paper`), so they scale
the two axes of `oklab()` instead, which holds no hue and paints the same in all three
engines. Recheck by loading that `oklch()` declaration in the engine: the gap stands
while it computes a hue of `none`.

### Sticky boxes' own place

A margin pin's seat is read against the room around its target, with a sticky box
counted at its own place, where it stands before sticking (`stuckShift` in
`browser/runtime/dom/geometry.js`). Only a view timeline reads that place without
writing to the page. Installed Playwright Firefox 157.0, build 1555, had no
`ViewTimeline` on 2026-11-05. Release Firefox 159.0 on macOS builds a `ViewTimeline` the
same day but throws NotSupportedError on reading its `startOffset` or `endOffset`, which
stopped each margin layout pass whose pin passed a sticky box; `stuckShift` now asks for an
offset once and reads nothing further from timelines where it throws. In both, a sticky
box counts where it is drawn. A pass
made while a header inside the target is stuck down the page can then seat the pin
where the header stands once the user scrolls back, and a later unrelated pass moves
the pin with no input. Playwright Chromium 156.0.8078.4 (build 1248) and WebKit 27.2
(build 2370) read the place the same way. Recheck by adding `firefox_browser` to
`test_a_pin_by_a_sticky_header_takes_one_seat_at_every_scroll` in
`tests/browser/margin/test_scrollers.py`.

### Highlight style inheritance

Firefox and shipping Safari have no highlight inheritance (css-pseudo-4, "Cascading
and Per-Element Highlight Styles"). Firefox resolves a `::highlight()` style as it
paints a run of text, only from the rules that match the run's own element
(`nsIFrame::ComputeHighlightSelectionStyle`), and
[bug 1999628](https://bugzilla.mozilla.org/show_bug.cgi?id=1999628) is open for it,
unassigned. On 2026-11-11, Playwright Firefox 159.0 (build 1572) and release Firefox
160.0 on macOS painted nothing from a rule on `:root` or `:host`, in the document or
a shadow tree, and `getComputedStyle(element, "::highlight(name)")` read the
rule's background as transparent on every element below the root. On 2026-11-12,
Safari 26.1 on the iOS simulator answered the same way. Playwright Chromium
158.0.8127.18 (build 1254) and Playwright's WebKit 27.2 (build 2388) painted the rule
on every element below the root and read it there, shadow trees included.

So each highlight rule names the elements holding the words it paints: a
suggestion's rules name its slot and every element in it (`browser/base.css`), a text
document's name its rows (`packages/default/styles/text-document.css`), and the comment
marks name each element the runtime marks as holding marked words
(`browser/runtime/annotations/anchor-paint.js`, `holdWords`). Slotted words
are styled from their light parent: on 2026-11-14 a rule naming the host painted
slotted words in all three Playwright engines, one naming the slot painted them only
in Chromium, and one naming an element between the slot and the shadow root painted
them in Chromium and WebKit but not Firefox. Recheck in Firefox and in iOS Safari
with a page whose only rule is `:root::highlight(m) { background-color: red }` over
a `<p>`'s words; the gap has closed once they paint red. A suggestion's rules could
then name only its slot; the comment marks would still name each element, for its own
tokens and `color-scheme` (the next entry).

### A highlight's `light-dark()` colour in a dark region

An element that inherits a highlight style, rather than matching a rule for it, takes
the colour computed where the rule matched. `light-dark()` computes to one of its
colours on that element (css-color-5), so a rule on `:root` alone paints the root
scheme's half inside a `color-scheme: dark` region: on a light page, marked words in
a dark panel would wear the light violet ink and wash on the panel's dark ground. On
2026-11-14 Playwright Chromium 158.0.8127.18 (build 1254) and WebKit 27.2 (build 2388) painted and read it that way. This is the specification, not an engine gap:
[CSSWG #11011](https://github.com/w3c/csswg-drafts/issues/11011) resolved in January
2025 that a highlight takes `color-scheme` from its originating element, which
reaches only an element a rule matches, and
[CSSWG #13836](https://github.com/w3c/csswg-drafts/issues/13836), to resolve
`light-dark()` at used-value time instead, was discussed in May 2026 without a
resolution, against concerns about breaking pages. The comment marks therefore name
each element holding marked words (`browser/runtime/marks.css`).

Chromium also paints the light half where the element does match the rule, when the
rule names no element (`::highlight(m)`), though `getComputedStyle` reports the dark
half. On 2026-11-14, Chromium 158.0.8127.18 (build 1254) painted the page below red
and read it blue; WebKit 27.2 (build 2388) and Firefox 159.0 (build 1572) painted it
blue. A selector naming an element, as `p::highlight(m)`, `[data-m]::highlight(m)` or
`p > *::highlight(m)`, painted blue in Chromium too. Chromium's own test of
`light-dark()` in a highlight, WPT `css/css-pseudo/highlight-styling-004.html` (added
February 2025), names the element (`p::selection`). A web search on 2026-11-14 found
no Chromium issue for the universal form; none is filed. Leaf writes no highlight rule
that names no element (`browser/AGENTS.md`, "Runtime ownership").

```html
<style>
  .dark {
    color-scheme: dark;
    background: black;
    color: white;
  }
  ::highlight(m) {
    background-color: light-dark(red, blue);
  }
</style>
<p class="dark" id="p">marked words</p>
<script>
  const r = new Range();
  r.selectNodeContents(p);
  CSS.highlights.set("m", new Highlight(r));
</script>
```

Recheck by loading that page in Chromium: the gap has closed once the words paint
blue.

### A highlight that sets no colour in WebKit

Where two highlights cover the same words and the upper one sets only a background,
css-pseudo-4 paints the words in the colour of the highlight below ("Painting the
Highlight"), since the upper one's `color` inherits `currentcolor` from the root's
highlight ("Cascading and Per-Element Highlight Styles"). From a rule naming the words' own element, WebKit paints them in that
element's colour instead. On 2026-11-14, Playwright WebKit 27.2 (build 2388) painted
words red under the page below, and blue with the two rules on `:root`, though red
again once `:root` also set `color: red`; Chromium 158.0.8127.18 (build 1254) and
Firefox 159.0 (build 1572) painted them blue under the page below. Writing
`color: currentcolor` on the upper rule kept them red in WebKit and turned Firefox's red
too. So the hover and current-location marks, which set no colour, paint under the
comment's mark, whose ink stays on top
(`browser/runtime/marks.css`), and
`test_marked_words_are_seen_and_told_apart` reads their words' ink off the drawn page
in WebKit. Recheck by loading the page in WebKit: the gap has closed once the words
paint blue. The two marks could then paint above the comment's again, which nothing
needs today.

```html
<style>
  body {
    color: red;
  }
  [data-m]::highlight(a) {
    background-color: rgba(255, 255, 0, 0.4);
    color: blue;
  }
  [data-m]::highlight(b) {
    background-color: lime;
  }
</style>
<p id="p" data-m>marked words</p>
<script>
  const r = new Range();
  r.selectNodeContents(p);
  CSS.highlights.set("a", new Highlight(r));
  CSS.highlights.set("b", Object.assign(new Highlight(r), { priority: 2 }));
</script>
```

### A mask smaller than an inline box in WebKit

On 2026-11-20, Playwright 1.65.2's WebKit 27.2 on macOS 26.5.1 painted the whole
background of an inline box whose only mask layer was a no-repeat image smaller than
the box, rather than only where the image covers it; an inline-block, Chromium 159
and Firefox 159 painted only the image. The mark after a link that leaves the page is
such a box (`surfaces.css`), and without a correction WebKit drew it as a solid bar
the height of the line. A second mask layer, a transparent gradient, makes WebKit
paint only the image, as USWDS's external-link mark also does.

Recheck: give an inline `<i>` 40px of inline padding, a red background and
`mask: <a black square> center / 10px no-repeat` in a 40px font, and count the red
pixels; 100 is right. Once WebKit draws 100, drop the gradient layer.

### A custom state set's own contents in WebKit

`ElementInternals.states` is `[SameObject]`, but WebKit doesn't keep the set alive
while a script holds only the `ElementInternals`. On 2026-11-20, Playwright 1.65.2's
WebKit 27.2 (build 2388) on macOS 26.5.1 collected it within a few garbage
collections, and `states` then read as a new, empty set: `has` said false for a state
the element still matched with `:state()`. Chromium 159.0.8154.6 (build 1255) and
Firefox 159.0 (build 1572) kept one set. Writes through the new set still reach the
element (deleting the state stopped the match), so only reads go wrong: a write that
skips a state `has` reports absent never deletes it, and in a floating panel's field
`:state(more-above)` stayed on a one-line draft. Holding the set itself keeps it
whole, so the text field holds it (`annotations/composing/text-field.js`, `#states`) and every
read and write goes through that. An element that only adds and deletes needs no such
hold.

Recheck: on an element holding only its `ElementInternals`, add a state, make
garbage for a few event-loop turns, and compare `internals.states.has(name)` with
`matches(":state(name)")`. Once they agree in WebKit, this entry and the comment at
`#states` go.

### Font style in syntax highlights

`lf-text-document` colours its source with CSS custom highlights
(`packages/default/widgets/lf-text-document.js`, `RunColours`), and `::highlight()`
carries only properties that don't change layout (css-highlight-api-1), so a token keeps
its theme colour but not its font style: a comment, italic in a code block, `lf-code`
and a diff, stands upright in a text document. This is the specification, not an engine
gap. On 2026-11-03, Playwright's Chromium 156.0.8078.4 (build 1248), Firefox 157.0
(build 1555) and WebKit 27.2 (build 2370) each painted a `StaticRange` highlight's
colour, ignored its `font-style`, kept that colour under a higher-priority highlight
that set only `background-color`, and painted one in a shadow root; Chromium's printed
PDF kept the colour. Recheck when css-highlight-api allows `font-style`: a highlight
rule setting it on a range of monospace text, read by eye or from a screenshot.

### Intrinsic block retirement motion

`browser/runtime/dom/motion.js` (`foldBlock`) animates block retirement, a decided
block suggestion and a resolved inline thread, with `calc-size()`. Where
intrinsic-size interpolation is missing it folds from the block's measured pixel
height, and where `display` can't be animated it keeps an already-retired slot
drawn with an inline `display` the effect's end removes. Playwright Firefox 155
needed both on 2026-10-25 and folded the same curve as Chromium. On 2026-11-20
Playwright Firefox 159.0 (build 1572) still lacked both `calc-size()` and
`interpolate-size` (`CSS.supports`), while WebKit 27.2 (build 2388) reported
both, so it takes the native path; its folds were not watched.
lf-draft's return from its editor (`packages/default/widgets/lf-draft.js`)
still needs `calc-size()`: its end height is known only after the close lays
out, and reading it then would clamp a reader at the document foot. In Firefox
it returns in one frame, an accepted visual difference.

On 2026-10-25 neither capability was coming to Firefox soon. `calc-size()`
([bug 1896734](https://bugzilla.mozilla.org/show_bug.cgi?id=1896734)) and
`interpolate-size`
([bug 1945962](https://bugzilla.mozilla.org/show_bug.cgi?id=1945962)) were
unassigned; on 2026-09-17 Mozilla called `calc-size()` a "would be nice"
feature for "sometime soon (during the next year perhaps)" with no release
committed, though its [standards position](https://github.com/mozilla/standards-positions/issues/1022)
is positive. Animating `display`
([bug 1834877](https://bugzilla.mozilla.org/show_bug.cgi?id=1834877)) was
unassigned. Interop 2026 [declined](https://github.com/web-platform-tests/interop/issues/1008)
the feature. WebKit implemented `interpolate-size`
([bug 324460](https://bugs.webkit.org/show_bug.cgi?id=324460), fixed
2026-09-18), shipped it in Safari Technology Preview 254 and
[supports](https://github.com/WebKit/standards-positions/issues/348) it.
Recheck those bugs; when Firefox ships both, delete the fallback branch and the
`display` hold. `test_a_decided_change_folds_away_rather_than_vanishing` in
`tests/browser/widgets/test_suggestions.py` and
`test_inline_retirement_is_resolved_before_its_pixels_finish` in
`tests/browser/threads/test_resolving.py` run in both engines.

### Evidence disclosure motion

`packages/diff/styles/disclosure.css` enhances native file and call-tree
closures only where intrinsic-size interpolation and `interactivity` both work.
Other engines close immediately and retain native disclosure behavior, an
accepted visual difference. Playwright Chromium 153.0.8010.12 folded pointer
closures on 2026-10-21; Firefox 155 closed immediately. Firefox's intrinsic
interpolation is not near ("Intrinsic block retirement motion" has the bugs,
checked 2026-10-25). Recheck both capabilities and keyboard access when
changing this enhancement.

### Browser dictation in comment boxes

`browser/runtime/annotations/composing/dictation.js` offers dictation when
`SpeechRecognition` or `webkitSpeechRecognition` exists. Browsers without it
keep typing and Send. Interface availability does not establish microphone
permission or access to the recognition service.
On 2026-10-11, Chrome 155 began listening but synthetic microphone audio ended
with `no-speech`; successful real transcription was unverified. The user's
Codex embedded-browser trial returned `network`. Native event tests cover
transcripts and failure recovery, but do not establish service availability.
Recheck with real speech in the affected browser.

### Find-in-page scrolling to folded content

Widgets fold content with `hidden="until-found"`, which Leaf's own travel reveals
too (`runtime/dom/widget-elements.js`, `reveal`). WebKit's reported gap is that finding a match reveals folded content without
scrolling to the match. [WebKit 304174](https://webkit.org/b/304174) remained
open when checked on 2026-10-22; this is published evidence, not a local Safari
reproduction. Recheck native find-in-page on text inside a closed panel before
removing this entry.

### A `:has()` subject left unrestyled when its match moves out, in Firefox

On Me's card for a choice asked in a thread hides its choices while its own drawing of
the message holds the choice's widget. Keyed on the widget itself, as
`.lf-fp-on-item:has(.lf-fp-asked:not([data-lf-carried]) [data-lf-awaits])`, the rule
failed in Playwright Firefox 159.0 (build 1572) on 2026-11-15: with On Me open on a
choice no thread on the page showed, `m` opened the thread's margin card, which took
the widget out of the card, and the card's choices stayed `display: none` though the
card no longer matched the rule (`card.matches()` read false). The card showed
neither the options nor its choices in 337 of 437 recorded frames, and at each step
of a probe through `m` and Escape. Chromium 158.0.8127.18 (build 1254) restyled at
once. A minimal page in Firefox restyled correctly after moving the matching element
out of the subject, whether moved directly, through a detached parent, into a shadow
root, or with its parent replaced, so something in Leaf's DOM is needed to show it,
not yet isolated.

The rule reads a mark the drawing writes as it gains or loses the widget instead
(`data-lf-holds`, `MessageView.present` in `browser/runtime/records/thread/messages.js`),
which Firefox restyles. To recheck, key the rule in `browser/styles/floating-panel.css`
on `[data-lf-awaits]` again and delete the `data-lf-holds` write: the Firefox arm of
`test_a_thread_choice_s_card_shows_the_choice_once_as_its_thread_opens_and_closes`
(`tests/browser/widgets/test_on_panel.py`) fails while the gap stands, its card
showing no choices after `m`, and the Chromium arm passes.

### An `auto` box under a fold in Firefox

A box with `content-visibility: auto` whose ancestor skips its content, as a
`hidden="until-found"` panel or a shut `<details>` does, should skip nothing itself
until the fold opens, when the browser decides which such boxes are in view. On
2026-11-14 Playwright Firefox 159.0 (build 1572) instead reported every such box
drawn (`contentvisibilityautostatechange` with `skipped: false`) as the fold closed
or the box arrived under it, kept them drawn as the fold opened, and reported the
ones out of view over the following frames. In a 300px scroller holding 50 such
boxes of five 20px rows, under either fold, all 50 reported drawn while folded and
46 reported skipped on opening; with the boxes `content-visibility: visible` while
folded, none reported anything until the fold opened, then 4 drawn and 46 skipped.
Playwright Chromium 158.0.8127.18 (build 1254) reported nothing under a fold either
way, then 17 drawn and 33 skipped.

A text document's runs are `visible` under a fold
(`packages/default/styles/text-document.css`), so a closed tab Firefox opens reads
and colours only the runs in view; with `auto` there, opening a tab of 95,000 lines
on #4781's page held the main thread for 6.6 s rather than 2 s, the page reading and
colouring every line. `test_opening_a_closed_tab_draws_only_the_lines_in_view` in
`tests/browser/widgets/test_code_and_documents.py` fails in Firefox without the rule,
drawing all 32 runs of its document in the first frame after the press. Recheck by
deleting the rule's `content-visibility: visible` and running that test: once its
Firefox arm passes, the rule can go.

### Asking another widget to act before Safari 26.2

Safari ships invoker commands and `CommandEvent` from 26.2, by caniuse's
`wf-invoker-commands` data; current Chrome and Edge, and Firefox from 144, have both.
In an earlier
Safari, a drop, an arrow move or a destination tap on a board card that shows a
question's pick asks the question nothing: `lf-board.js` (`#ask`) throws
`CommandEvent is not defined`, the board lets go of the gesture, the card goes back to
the column its question's pick names, and the page reports the error. An authored
`<button commandfor command="--…">` does nothing there either. Everything else works:
the card stands where the pick puts it and follows a pick made in the question, every
other card moves as before, and the question takes picks from its own options.

Leaf accepts the gap rather than shimming the command: a shim would be a second
implementation of the platform's request, kept until Safari before 26.2 leaves use.
On 2026-11-26 Playwright Chromium reproduced the failure with `CommandEvent` deleted,
and the board took a later grab. The iOS simulator's Safari couldn't confirm it that
day, since a board page never finished upgrading there on main either. Recheck with
`uv run leaf-dev probe PAGE --browser ios` on a page with a shown card, reading
`typeof CommandEvent`: once the simulator's Safari is 26.2 or later, the entry can go.

### A root's touch-action in Firefox

Draw mode states `touch-action: pinch-zoom` on `html` and Capture area
`touch-action: none` (`browser/runtime/chrome.css`), so one finger draws or drags
out an area while two still pan and zoom. On 2026-11-15, on macOS 26.5.1, Playwright
1.65.0's Firefox 159.0 (build 1572) updated every box of the page each time the
root's touch-action changed. On #4781's shape, thirty text documents of 50,000 lines
in side tabs (1.51 million elements), toggling Draw mode's attribute on `html`
alone, with a layout read after each toggle, took 24 ms, and 73 to 94 ms the first
time; the Gecko profiler put the time in `RestyleManager::ProcessRestyledFrames`,
with one element styled. On a page of 900,000 plain rows it took 8 to 12 ms, against
under 1 ms for an attribute no rule reads. Playwright's Chromium 158.0.8127.18
restyles every element it draws when the root's touch-action changes, 691 elements on
a page of 600 paragraphs, though not what `content-visibility` skips, so on #4781's
shape a whole Draw mode toggle took it 30 to 65 ms; the restyle count in
`test_a_page_mode_restyles_only_what_the_pointer_is_over`
(`tests/browser/test_chrome_contracts.py`) holds the root's touch-action through the
page for that reason.

Leaf keeps the rule on the root whenever either mode stands. Stating it only under
`(any-pointer: coarse)` removed the cost on a computer without a touchscreen, but
Firefox on Linux can report no touchscreen while it receives touch events, so
`any-pointer: coarse` doesn't match there
([Mozilla bug 1870900](https://bugzilla.mozilla.org/show_bug.cgi?id=1870900)), and
one finger would pan the page rather than draw. Recheck with Playwright's Firefox on
a page of 900,000 `div` rows and the rule `html[data-x] { touch-action: pinch-zoom; }`:
toggle `data-x` on `html` and read `document.body.getBoundingClientRect()` after each
toggle. The gap stands while a toggle takes several times as long as one of an
attribute no rule reads.

### Native focus and scrolling inside samples

An opaque sample's sandbox isolates DOM and storage, but authored JavaScript's
native focus and reveal calls can still move focus or scroll its containing
page. Leaf contains its own placements through `browser/runtime/dom/focus.js`,
`dom/keyboard/layer-stack.js`, `readings/landing-scroll.js` and `annotations/editor-view.js`; this is a
cooperative runtime contract, not a security boundary for authored scripts.
Chrome 155 and Chromium 153.0.8010.12 allowed autonomous child focus transfers
on 2026-10-09. On 2026-10-10, typing into an already focused offscreen native
editor also revealed its frame without a JavaScript reveal call.
Reproduce by focusing the parent, then invoking native focus or reveal from a
child message handler; separately type into an offscreen focused child editor.

### Percentage scroll margins in Chromium

What Leaf calls near the window (`browser/runtime/dom/geometry.js`, `nearObserver`), which
decides where anchored controls stand in layout and when a live sample's page starts
(`whenNear`), is an IntersectionObserver with `rootMargin: "100%"` and a
`scrollMargin` in pixels. A percentage there misreads in Chromium: on 2026-11-11, on a
Leaf column page with a sample frame about 3,800px down a 900px window, HeadlessChrome
158.0.8127.18 (Playwright 1.65.0) read the frame as intersecting under
`rootMargin: "100% 0px"` with `scrollMargin: "100% 0px"`, though under either alone it
did not and the reported root ended at 1,800px. With `scrollMargin: "600px"` it read the
frame correctly. Playwright Firefox 159.0 read every form correctly but grew the window
by the scroll margin as well as the root margin, so the window reaches 1,500px further
there than in Chromium. Plain test pages, even with the body as an inline-size
container, read the percentage correctly in both. Recheck by observing `#far iframe`
with each option in `uv run leaf-dev probe` of a page that places `<lf-sample id="far">`
under a 400vh spacer, in both engines.

### A selection written during focus in WebKit

Playwright WebKit 26.6 revealed an editor's selection written inside its
`focus` event, before the platform finished its focus steps, although the focus
call prevented scrolling, and the reveal crossed a sample's frame: on
2026-10-25 the containing page scrolled 1,386px to a sample's editor. Chromium
153 kept the page still. `LeafEditorView` in `browser/runtime/annotations/editor-view.js`
writes the caret after native focus returns when its own `focus()` moved focus,
and inside the focus event only for arrivals that bypass it, such as Tab;
whether WebKit reveals those across a frame is unverified. Recheck
`test_sample_editor_focus_preserves_outer_scroll_and_the_caret[webkit_browser]`
in `tests/journeys/test_render_controls.py` with the focus listener writing the
selection on every arrival (`#focusing` never set).

### Selecting words inside a button in WebKit

WebKit begins no text selection inside a form control, whatever its
`user-select`: `HTMLFormControlElement::canStartSelection` is final and returns
false. On 2026-10-30, a `<button>` in a paragraph styled `user-select: text;
-webkit-user-select: text` selected nothing in Playwright WebKit 27.2, build
2370, under a drag, a double click or a triple click inside it, nor with
`appearance: none`, `display: inline` or `contents`, or an inner span of its
own; `user-select: all` selected the whole label at once. Chromium 156.0.8078.4
and Firefox 157.0, build 1555, selected part of the label, a word and the
paragraph. A drag beginning outside still extends into the button in all three.
So a control whose label is the page's own words is a span with a role
(`selectableOffer`, `browser/runtime/lib/controls.js`), and one with a
button's role takes Enter and Space from `browser/runtime/lib/role-button-press.js`,
on a page with Leaf or without it. Recheck with that button and a double click
on one of its words, reading `getSelection().toString()`.

### Sample document admission and native navigation

`browser/runtime/host/sample.js` admits the initial document with a credentialless
HEAD and the server's `Leaf-Document` header. The parent cannot inspect the
opaque child's destination to prove it receives that same response or distinguish
a failed reload from departure to a non-Leaf document. The native destination remains visible;
Reset is the recovery route. The current contract is
[Live samples](../skills/leaf/references/live-samples.md).

Departure fault handling in `browser/runtime/prepaint.js` is checked in
Chromium and Firefox; Safari's ordering of navigation and request cancellation
remains unverified. A press during a slow navigation can report aborted loads
before that navigation commits. Recheck canceled departure and slow navigation
with `tests/journeys/test_render_sample_delivery.py` and
`tests/browser/startup/test_readiness.py` when changing document lifetime.

### A sample's page out of view in Chromium

Chromium renders a sample's page, whose origin is opaque, once as it loads and then
not again while its frame is off screen or in a closed disclosure; its timers keep
running. Work that waits on a rendering, such as an `lf-chart` sized by its first
layout and the widget upgrade that waits for it, waits until the frame shows. Over 5 s
on 2026-11-19, in Chromium 159.0.8154.6 (Playwright 1.65.2, headless), an opaque frame
on screen ran 300 animation frames, one 300 px below the window 1, one in a closed
`<details>` 1, and a same-origin frame off screen 300; a ResizeObserver attached after
the first second delivered nothing in either hidden opaque frame. No Chromium switch
tried lifted it, `--disable-blink-features=RenderingPipelineThrottling` among them.
Firefox renders such a frame anyway: on 2026-11-22, in Playwright's Firefox 159.0, an
opaque frame 300 px below the window ran 600 animation frames in 5 s, where Chromium
159.0.8154.6 ran none. Leaf counts what a sample's page does after loading only while
its frame shows, except that a block's page counts until it arrives or a deadline
passes, since its arrival sets the frame's height (`browser/runtime/host/sample.js`), and
`page check --render` scrolls each frame still waiting into view
(`src/leaf/source/render_checks.py`, `start_near_work`). A sample the reader saw as it started
holds the page's presentation, or the jump that showed it, only while they still see
its frame (`browser/runtime/host/sample.js`). Recheck with
`tests/journeys/startup/test_hosting.py`,
`test_a_chart_in_a_sample_off_screen_waits_for_the_reader_and_a_check_shows_it`,
whose first assertion fails once Chromium draws the chart out of view.

### Page cache

Every Leaf server, locally and on leaf.page, sends `no-cache` for a page's
document and state (`CACHE_CONTROL`, `src/leaf/serving/http.py`), so a browser may keep
the page in its back/forward cache. On 2026-10-20, Chromium 153.0.8010.12 and
installed Firefox 158.0.1 restored a local `release-notes` page on Back and
applied state changes made while away. Firefox loaded a page containing samples
afresh. On 2026-11-08, Playwright's full Chromium 156.0.8078.4 restored
`heat-loss`, served by leaf.page's container server after a choice, on 5 of 5
Backs, keeping the reader's selection; with that server's former `no-store` it
reloaded the page each time (`MainResourceHasCacheControlNoStore`,
`JsNetworkRequestReceivedCacheControlNoStoreResource`). Safari remains
unverified.

Playwright disables back/forward caching in its normal test browsers: launch its
full Chromium (`channel="chromium"`) without `--disable-back-forward-cache`, and
wait for Back's commit, since a restored page fires no `load`. Its Firefox
disables the cache in the docshell, so check Firefox in an installed one.
`test_a_page_cache_round_trip_keeps_the_sample_connected` in
`tests/browser/test_render_sample_delivery.py` checks synthetic lifecycle events,
so it does not prove native cache eligibility. Recheck a real Back traversal
with caching enabled when changing the policy or sample lifetime.

### Frame margin trimming

The frame-edge rules in `browser/base.css` traverse bare wrappers,
skip generated apparatus and stop at declared rows. Native `margin-trim`
cannot replace that behavior across the checked engines: on 2026-10-08,
Chrome 155 trimmed block-flow margins but left flex and grid item margins;
a generated child could prevent trimming the authored paragraph. Playwright
Chromium 153.0.8010.12 and Firefox 155 did not accept the property.
Recheck wrapper and row behavior, not just parser support, against
`test_block_margins_follow_density_frames_and_the_column_on_one_page` and
`test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it` in
`tests/browser/test_render_gate.py`.

### Centring a block in block layout in Firefox

Box Alignment lets `justify-self: center` centre a block-level box in a block
container. On 2026-10-31 Playwright Chromium 156.0.8078.4 and WebKit 27.2 centred a
200px block in a 600px container with it; Firefox 157 left the block at the start.
So `browser/layouts.css` centres an `available` table on the column's axis with a
relative offset and a translate instead. Recheck with that two-box fixture; once
Firefox centres it, the table can take `justify-self: center` and lose the offset
and the translate.

### A pane's body sized by `stretch` in Firefox

A pane's body is a grid item and an inline-size container (elements.css). A grid
item with an `auto` inline margin is sized to fit its content, which containment
counts as empty, so a body an author centred with `margin-inline: auto` and a
`max-inline-size` drew 0px wide inside its padding. `browser/elements.css` gives a
body `inline-size: stretch`, which fills the pane before the margins share what the
`max-inline-size` leaves. On 2026-11-25 Playwright Firefox 159.0 (build 1572)
rejected `stretch` in the inline axis and took `-moz-available`; Playwright Chromium 159.0.8154.6 and WebKit 27.2 took `stretch`.
Recheck with `uv run leaf-dev probe --browser firefox` on a pane whose body has
`margin-inline: auto; max-inline-size: 30rem`; once Firefox centres it without the
prefixed value, the prefixed declaration can go.

### A moved box's place in flow in Firefox's scroll size

Firefox recomputes a block's overflow without laying it out again when a child's
outline or other painted extent changes, as a focus ring does. That recomputation
counts each child moved by a relative offset or a translate at its place in flow as
well as where it is drawn, and the page keeps the larger scroll size until the block
is laid out again. On 2026-11-03, in Playwright Firefox 157.0 (build 1555), a 1680px
block moved 480px back by `left: -480px` or `translate: -480px` from a 720px column
centred in a 1728px window left `document.documentElement.scrollWidth` at 1728 until
a paragraph beside it took an outline, and at 2184 after that, outline removed or
not; the same block placed by `margin-left: -480px` left it at 1728. Playwright
Chromium 156.0.8078.4 kept 1728 throughout. In the user's Firefox 159, closing a
thread card, which rings the paragraph it leaves the user at, left the page
scrolling 456px sideways while breakouts were placed by an offset.

So `browser/layouts.css` places an `available` block by a negative start margin, so
its place in flow is where it is drawn. An `available` table starts at the room's
start the same way, and its relative offset and translate then centre it on the
room's axis. Firefox applies the translate to the table's place in flow, so it counts
the table half its own width before the room's start. A page in the holder's
direction does not scroll that way, but where the page and the holder differ in
direction, as in `<main dir="rtl">` on a left-to-right page, a ring still widens the
page by up to half the table's width (to 2544px for a 1680px table in a 1728px
window). Centring the table without a translate needs its own width in a margin,
which CSS can't express, `justify-self` on a block, which Firefox lacks (above), or
an `available` wrapper the table centres in by `margin-inline: auto`, which would
change how a page writes an available table.

Mozilla's bugs [1801710](https://bugzilla.mozilla.org/show_bug.cgi?id=1801710) and
[1820266](https://bugzilla.mozilla.org/show_bug.cgi?id=1820266) report a relatively
positioned box's place in flow counting toward scroll size on first layout; this
case, right after layout and wrong after a restyle, is not filed. Recheck with that
fixture in Firefox: a 720px `main` centred in the window, holding a paragraph and a
`position: relative; left: -480px; width: calc(100% + 960px)` block. Give the
paragraph an outline and read the root's `scrollWidth`; once it stays at the
window's width, a breakout may move by an offset again. In Leaf,
`test_a_breakout_grows_only_from_a_holder_that_spans_the_column` and
`test_a_table_granted_room_stands_on_the_prose_axis` ring a paragraph beside
breakouts and fail if the page then scrolls sideways.

### A non-inheriting property taken with `inherit` in WebKit

A child or `::after` that takes a registered custom property declared
`inherits: false` with `inherit` keeps its first value in Playwright WebKit 27.2
when only that property changes on its parent; Chromium 158.0.8127.18 and
Firefox 159.0 restyle it (2026-11-12, a parent's `--len` set from 10px to 30px
left a child's and an `::after`'s `height: var(--len)` at 10px). On 2026-10-31
the same engine kept a child's copy of the column's room through a window resize:
an `available` block sized from it stayed 1392px wide at 1200 and 900px wide
windows. So the column's room (`--lf-free-start`, `--lf-free-end`,
`browser/layouts.css`) inherits, and a box outside the column's flow sets it back
to zero. Recheck with a page holding that pair of
rules in `leaf-dev probe --browser webkit`, then with
`test_a_breakout_grows_only_from_a_holder_that_spans_the_column` in
`tests/browser/test_render_pages.py` under `webkit_browser` after making the
column's properties non-inheriting and passing them down with `inherit`.

### State-preserving content reordering

`browser/runtime/dom/dom-move.js` uses `moveBefore` for retained nodes within one
composed root. In engines without it, ordinary insertion restores focus and
caret but still blurs the descendant and reloads an iframe. Playwright WebKit
26.6 lacked the API on 2026-10-10, and WebKit 27.2 (build 2388) still lacked it on
2026-11-20. That day Playwright Firefox 159.0 (build 1572) had it: a focused input
moved with its iframe to another parent kept focus, its caret and the frame's
document, as in Chromium 159.0.8154.6 (build 1255). Recheck native state
preservation before removing the fallback;
`test_retained_moves_keep_native_editor_and_frame_state` in
`tests/browser/controls/test_focus.py` exercises native and forced-fallback paths
in Chromium. API presence alone does not prove preservation.

Chromium 153.0.8010.12 also left a focused node unmatched by its own
`:focus-within` after moves through a hidden parent on 2026-10-12. Leaf's focus
marks follow rendered ancestry; selectors for the focused editor use `:focus`.
Recheck with a focused input moved into a hidden parent and back out.

Chromium 158.0.8127.18 kept `:hover` on a node moved while the pointer was over
it, and on the ancestors it left, on 2026-11-14. The comment box moves this way
between a widget's outlet and its home (`annotations/composing/surface.js`, `seatFab` and
`restoreFab`), so once the user has pointed at the box in an outlet and put it
away, those nodes match `:hover` until the pointer crosses them again. The
effect seen so far is in tooling: `leaf-dev probe` and `stills` wait for the
hover to reach the element under the pointer (`catch_up_hover`) and fail. Whether
a page's `:hover` rule on such an ancestor shows is not assessed. Recorded, not
corrected. Reproduce with `leaf-dev probe pr-walkthrough` and a journey that
presses a diff line's Comment control, hovers `.lf-fab-input`, presses Escape
and moves the pointer to an empty part of the page: the arm fails at `settle`,
and passes with `Element.prototype.moveBefore` deleted first. On a Command Hub
task the same journey left `:hover` on the outlet the box had stood in
(`.atlas-task-threads`) and not on the task around it, on 2026-11-15. Firefox
159.0 (Playwright build 1572) left it on neither that day.

### Clearing a shadow host unloads its frames in WebKit

In Playwright WebKit 26.6 on 2026-10-24, `replaceChildren()` on an element
with a shadow root unloaded every iframe in that shadow tree, leaving it
connected with a null `contentWindow`, even when the host had no children to
remove; `textContent = ""` did the same when it had some. Removing each child
with `remove()` kept the frames, as Chromium 153.0.8010.12 and Firefox 155.0
did for all three. `shadowStage` (`browser/runtime/dom/shadow-stage.js`) removes a host's
light children child by child, the one place a widget clears its host, since a thread
outlet in a stage can hold a frame. Recheck with `test_a_diff_revision_leaves_a_line_thread_where_it_stands`
in `tests/browser/widgets/test_diffs.py`.

### Area capture rendering

`browser/runtime/host/page-image.js` reconstructs the DOM with SnapDOM.
Accepted differences include text wrapping, native form controls and a live
sample editor's missing placeholder text. Other cross-origin frames keep
placeholders. SnapDOM's reported missing images produce an attachment notice,
but omissions of CSS backgrounds and fonts can go unreported. These resource limits were
observed or found in source review on 2026-10-09; a capture is not guaranteed to
contain every resource visible on screen.

When updating SnapDOM, compare the same crop with a native screenshot in each
installed engine. The anchored capture and live-sample journeys in
`tests/journeys/test_render_threads.py` cover Leaf's integration;
`build/vendor.mjs` owns the current vendor adaptations.

### Naming a shadow-tree box from the document

`browser/runtime/dom/css-anchors.js` names boxes through document `::part()` rules.
Boxes deeper than the first shadow tree anchor through their host: Playwright
Firefox 155 failed to anchor through re-exported `exportparts` on 2026-10-14.
WebKit 26.6 failed to resolve a typed `attr()` anchor name inside `::part()`, so
the runtime writes one rule per name.
Recheck a fixed anchored box against a part-named child after scrolling its
shadow scroller, then repeat one host deeper through `exportparts` and with a
name read through `attr()` before lifting those limits.

### Keyboard modality after a click in Firefox

A thread card opened by a click keeps no ring in Firefox however the user then
types, so nothing marks the card the thread keys act on. Playwright Chromium
156.0.8078.4 matched `:focus-visible` on the clicked thread at the next key, Shift
included; Playwright Firefox 157.0 never did, on 2026-11-02. `dom/focus.js`
(`visibleFocus`) follows the browser's answer, and the open card is the only thread
keys reach; a key pressed after scrolling it away lets go of it
(`panel/page-keys/controller.js`).
Recheck with a probe on
`review-a-plan`: click the first margin marker, press Shift, and read whether the
card's `.lf-page-thread` matches `:focus-visible`.

### A keyboard caret in Safari

Safari has no caret browsing, so a keyboard user there can't put the caret on words
that take no focus. `K` (`annotations/preview.js`, `here`) can't read at a caret there, and the
keyboard can't select words to comment on (`browser.caret` in `panel/page-keys/page.js`).
Safari's Tab, as Playwright WebKit runs it, stops only at text fields and elements with
their own `tabindex`, so Leaf's own keys move a keyboard user there: walks, Go-to and
arrows in the panel's lists. A pointer and a finger's hold read every preview.

These reach an age's clock time without a caret, the same in every engine:

- An age an author wrote in the page takes a Go-to hint, which lands on it and shows
  its time (`go-to-sequence.js`, `pageAges`). An age a widget wrote takes none, so
  three in the examples have no keyboard route in Safari: the command hub's atlas
  tree and each of its workers' "Last heard", and the PR walkthrough's brief.
- A row of Threads or of an On list, reached by arrows, names its age's time in the
  preview `K` reads there (`panel/floating-panel.js`, `ageLine`).
- An activity row's target previews its row's time. Safari's Tab reaches the target
  only with Option+Tab or "Press Tab to highlight each item", and Go-to presses it
  rather than landing on it.
- A message a walk lands on (`m`, on a message that asks something) previews when it
  was said.

A message that asks nothing has no keyboard route to its time in Safari: no key
walks a thread's messages, and one would need new keys in the thread's scope for a
path few take. Nor does a plan step's running time, which stands in no row.

On 2026-11-24, in Playwright WebKit 27.2 (build 2388), F7, ArrowRight and
Shift+ArrowRight each left a collapsed caret where a script had put it in a
paragraph's words, while arrows walked it into an age's words in Playwright Chromium
159.0.8154.6 (build 1255) with `--enable-caret-browsing` and Firefox 159.0 (build 1572) with `accessibility.browsewithcaret`. Recheck in WebKit: collapse the selection
in a paragraph's text, press F7 and then ArrowRight, and read whether
`getSelection().focusOffset` moved.

### A control's own arrows after focus leaves it in Chromium and WebKit

A key pressed at a control the user has scrolled away from lets go of it first
(`panel/page-keys/controller.js`), and Chromium and WebKit still apply a radio's, slider's
or select's own arrows at the control the key was aimed at: a radio's ArrowDown
checked the next radio and scrolled the page back to it, a slider's ArrowRight
stepped its value, and a closed select's ArrowDown kept focus and scrolled the page
back to it. Playwright Chromium 156.0.8078.4 did each of these, and Playwright
Firefox 157.0 did none, scrolling the page by the arrow from where focus had gone,
on 2026-11-04. On 2026-11-20, on a plain page whose capturing `keydown` listener
blurs the focused element, Playwright Chromium 159.0.8154.6 (build 1255) and WebKit
27.2 (build 2388) each checked the next radio and left focus on it, stepped the
slider, and left focus on the select, while Firefox 159.0 (build 1572) did none of
these; that page didn't scroll the controls away first. The controller withholds
those arrows in every engine (dom/focus.js, `controlNavigationKeys`), so the arrow that
lets go scrolls nothing. Recheck on a plain page holding two radios of one name, the
first checked and focused, whose capturing `keydown` listener on the document blurs
the focused element: the gap is closed in an engine when ArrowDown leaves the first
radio checked there.

### A stuck sticky box bounces with the page

Firefox on macOS bounced a sticky column with trackpad overscroll on
2026-10-20, and the contents map's stuck track on 2026-11-26. The page-of-parts
column and the contents map's narrowed track, where its sidebar spans the page,
use fixed positioning in `browser/layouts.css` to stay still; other root-sticky
boxes can still bounce. Recheck with a native trackpad fling at the document's
top and end; headless Playwright supplies no overscroll. If engines hold sticky
boxes still, both can return to sticky positioning.

### An anchor inside an SVG foreignObject in Chromium

A fixed box anchored to an HTML element inside an SVG `<foreignObject>` takes
its `anchor()` fallback, so a key chip, aim, mark or margin row there stood at
-9999px, off the window. Playwright Chromium 158.0.8127.18 (build 1254) did so
on 2026-11-12; Firefox 159.0 (build 1572) and WebKit 27.2 (build 2388) placed
the box on the element, and all three placed it on the drawing's `<svg>`.
`anchorElement` in `browser/runtime/dom/css-anchors.js` anchors such an element
through the drawing in every engine, as it does the drawing's own shapes, with
the box's insets measured from the drawing. A scroller inside the drawing's HTML
doesn't move the drawing, so a mark or composer against a target in it stays
where it was placed as that scroller scrolls, until it is placed again;
accepted, since no shipped page scrolls inside a drawing. Recheck with
`test_a_chip_stands_beside_a_link_in_an_svg_drawing_s_html` with the
`foreignObject` step removed from `anchorElement`, or a fixed box whose `left`
is `anchor(--a left, -9999px)` against a button in a `foreignObject`.

### An anchor's transforms in Firefox

Playwright Firefox 157 (build 1555) resolved `anchor()` and `anchor-size()`
against the box layout gave the anchor, leaving out every transform on it and
its ancestors (translate, scale, rotate, nested), on 2026-11-01; it kept CSS
zoom. Release Firefox 159 still drops transforms, as checked the same day.
Chromium 156 (build 1248) and WebKit 27.2 (build 2370) read the transformed
bounding box. Firefox Nightly 160 reads it too, behind
`layout.css.anchor-positioning.follows-transforms.enabled`, which bug 2059840
enabled in Nightly; bug 2059841 tracks enabling it in release, with no
milestone, blocked on bugs 2055371, 2057633 and 2060883.

`anchorBox` in `browser/runtime/dom/css-anchors.js` measures that laid-out box from
offsets wherever `anchorDropsTransforms()` finds the engine drops transforms, so
pins, rows, key chips, the design label, floating cards and previews stand on a
widened table (translated) and on a reveal.js slide (translated and scaled), and the
block controls (`readInsets` in `browser/runtime/records/block-controls.js`) add the
size difference to their far edges. An engine that keeps transforms, the
Nightly pref included, fails that check, and none of this runs. Offsets are
whole pixels, so a mark can stand up to a pixel off. The walk runs when a box is
placed, so a transform that changes afterwards, as an animation sliding the
target does, leaves the box where it was placed until the next scroll, resize or
layout signal: holding Alt over a paragraph slid 120px down by a 300ms animation,
Playwright Firefox 157 (build 1555) kept the then-anchored aim at its start, after
the slide too, on 2026-11-02. Marks round a box no longer stand in this layer
(surfaces.css draws them on the box), so this reaches only boxes beside a target,
such as pins and chips. Accepted, since no example page slides a target with one
beside it.

A scroll inside a scaled box is a separate gap. Firefox 157 and WebKit 27.2
carry an anchored box by the scroll's layout pixels, not the smaller or larger
distance the words move on screen; Chromium 156 follows the words. Scrolling 60px
in a box scaled to 0.6 left a row 24px off its words in both, until something
else ran a margin pass. Bug 2055371 is Firefox's, and it remains with the
Nightly pref on. A CSS zoom drifts no anchor in any of the three. The margin
now runs a pass at a box's `scrollend` where a row's carrier stands in the box
and the box's on-screen width differs from its zoomed layout width
(`scrollMisplacesAnchors`), so rows stand on their words a frame after it
ends. While the scroll runs, the margin's once-a-frame reading of it places
again a row whose words have left it (`subjectMoved`). In Firefox, whose
anchors `anchorBox` measures without their transforms, that holds the row near
its words: on 2026-11-03 a smooth scroll inside a scaled box ran 26 passes over
72 frames, the row stayed within 7px of its words where it had drifted up to
48px, and no frame took over 15ms on a four-row page. In WebKit the measured
anchor moves with the words, so by that reading its rows still drift until
`scrollend` (not measured). WebKit 27.2's Linux build (Playwright build
2370, which CI runs) has no `currentCSSZoom`, unlike its macOS build of the same
number, so there a zoomed box also gets the pass, which moves no row. Inside a rotated box, a mark anchored to an
SVG drawing or to a scroller's first words stands off by the rotation, since
its place is mapped through the nearest HTML box's bounding rectangle.

`test_marks_stand_on_a_widened_table_in_every_engine` and
`test_marks_stand_on_a_scaled_slide_in_every_engine` fail in Firefox without
the correction, and the second fails in Firefox and WebKit without the
`scrollend` pass. Once bug 2059841 ships in release, delete the offset walk and
the `--lf-block-control-dw`/`dh` pair. Delete the `scrollend` pass once release
Firefox and WebKit both keep a row on its words through a scroll inside a scaled
box. The test passes whatever the engines do while the pass is in place, so
recheck with the `scrollend` listener removed, which left the row 24.1px off in
Firefox 157 and 24.0px off in WebKit 27.2, or by reading the row in the frame
after the scroll, before `scrollend`.

### A `left`-inset anchored control after a resize in Firefox

`.lf-heading-link` in `browser/styles/components/integration.css` carries its
place in its `right` inset because Playwright Firefox 155, on 2026-10-25, left
a `left`-inset link where its heading had stood before the window widened, as
commit 00e03385c records without a reproduction. The same day, a `left` form of
the current arithmetic followed its heading in Firefox 155 when
`leaf-dev probe --browser firefox` narrowed `release-notes`, `review-a-plan`,
`live-progress` and a one-heading page to 440px and widened them to 1200px, so
the gap is unconfirmed. The `right` form costs nothing else. Recheck by
swapping in the `left` form and comparing the link's box after that resize with
a fresh page's at the same width across the corpus; if none differ, drop this
entry and the reason in the stylesheet.

### A keyboard scroll's `scrollend` on every frame in WebKit

On 2026-11-03, Playwright WebKit 27.2 (build 2370) sent a `scrollend` on each
frame of a PageDown's or Space's animation, 12 for one PageDown, where Chromium
156 and Firefox 157 send one as the scroll lands. So in WebKit one keypress makes
a scroll sequence per frame (`dom/arrivals.js`, `watchScrollEnds`), and each reader
of a scroll's end runs on every frame of it. A Leaf step pressed during such a
scroll waits for it to end (`dom/scrolling.js`, `afterBrowserScroll`), which in
WebKit is the first frame's end, so the step moves from where that frame left
the page and the rest of the browser's move is lost, or the step is: Space and
then `d` 40 ms later ended at 651 px, and PageDown and then `d` at 720, PageDown
alone, where Chromium and Firefox end at 1246 and 1254, the landing plus the
step. Waiting a rendering update past each end did not help, since WebKit's
main thread hears its keyboard scroll's frames up to 110 ms apart. To recheck,
count `scrollend` events on the document across one PageDown in WebKit; one
means the gap has closed.

### Native reveal bounded to its scroller

`scrollIntoView(node, {within})` in `browser/runtime/readings/landing-scroll.js` reveals
an item without moving the containing page. On 2026-10-14, Playwright Firefox
155's native `scrollIntoView({container: "nearest"})` also moved an outer
scroller when a horizontal strip's edge extended just beyond its band.
Recheck a partly clipped strip's inner and outer scroll offsets before
replacing Leaf's bounded walk with native reveal.

### A reveal of an anchored fixed box before the next frame in Chromium

A `position: fixed` box anchored to page content takes a scroll at the next
frame: read after a script scrolls the page 200px, it stands where it stood
until a frame passes, in Playwright Chromium 158.0.8127.18 (build 1254) and
Firefox 159 alike on 2026-11-15, as the anchor positioning spec's scroll
snapshot allows. Chromium and WebKit reveal a caret in such a box by scrolling
the page, which carries the box, and Chromium reveals the box itself the same
way (`scrollIntoView`, focus), so in Chromium a reveal made before the next
frame scrolls for where the box stood. Playwright Chromium 156.0.8078.4 (build
1248), on 2026-11-05, scrolled the page again for each such reveal, as if the
first had not moved the box. Give
a 4000px body an absolutely positioned anchor at `top: 2000px`, a 20px fixed
box at `top: anchor(top)` through `position-anchor`, and the root
`scroll-padding-bottom: 100px`; scroll the anchor 830px down an 860px window
and call `scrollIntoView({block: "nearest"})` on the box. One call scrolled
90px, two 180px and three 270px. Typing four keys back to back into such a
box's contenteditable at the window's foot scrolled 240px where one key
scrolled 60px. Playwright WebKit 27.2 (build 2370) scrolled 0px for the calls
and 60px for the keys, however many; Playwright Firefox 157 (build 1555)
reveals no fixed box through the page.

In Leaf the root drops its scroll padding while the user writes in a floating
box (`base.css`, `data-lf-floating-editor`), so only a caret outside the window
is revealed, and each key that lands in the same frame adds another reveal's
scroll; #5417 accepted that overshoot. Tab pressed in the frame `t` sets off
in lands the walk's glide first (dom/scrolling.js, `landForKey`), and Chromium then
reveals the thread card's next control where the card stood before the landing,
scrolling the page on past where the walk leaves it; the glide matrix in
`tests/journeys/navigation/test_reading_place.py` holds that case as known.
Leaf's own readers ask where the glides land instead of reading an anchored box
after a landing (readings/scroll-containers.js, `seenAhead`), and a reading of the whole
scene, as a hint map's, waits until the rendering update after a script's scroll
(dom/arrivals.js, `scrollDrawn`). Recheck the three calls in
Chromium; a 90px scroll means the gap has closed, and the matrix's known case
then passes.

### A fixed box's new default anchor before the next frame in Chromium

A `position: fixed` box whose `position-anchor` changes from one anchor to
another, under a scrolled page, reads off by that scroll until the next
rendering update, though Chromium paints it where the new anchor puts it.
Give a 4000px body two absolutely positioned anchors at `top: 1000px` and
`top: 1100px`, a fixed box at `top: anchor(top)` naming the first, scroll the
page 231px, and name the second in an animation frame callback: the box reads
at 638 in that callback and at 869 in the next frame's, and Chromium's
layout-shift entry records it moving from 769 straight to 869. That was
Playwright Chromium 159.0.8154.6 (build 1255) on 2026-11-21. Playwright Firefox
159.0 (build 1572) reads 869 at once, and both read right at once where the box
takes an anchor from none, drops one, or changes only its insets.

In Leaf it reaches a floating surface whose placement moves it from one
anchor's plane to another's (floating.js), such as a thread card that an answer
grows against a pane's foot. floating.js reads where an answer stands the box
from the answer (`clientBox`), not off the box. `tests/shift_watch.js` reads the
box in an animation frame callback, where the offset shows. A CDP screencast of
such a card showed no frame at the offset spot, so with no user-visible effect
Leaf leaves the gap. Recheck with the reproduction above; 869 in the switching
callback means the gap has closed.

### `calc()` in `overflow-clip-margin` in Chromium

Playwright Chromium 153.0.8010.12 rejected `overflow-clip-margin: calc(2px + 5px)`
on 2026-10-26, leaving the computed margin `0px`, while Playwright Firefox accepted
it. A text field's clip margin (`annotations/composing/text-field.js`, `.lf-field`) therefore
reads one custom property, `var(--lf-field-reach, 2px)`, rather than adding a
motion's reach to the caret's 2px. Recheck by setting the calc value on an element
and reading `getComputedStyle(element).overflowClipMargin`; once it reads `7px`, the
reach can add to the caret's margin.

### Fixed layers missing from Firefox screencast frames

Playwright Firefox 155 screencasts intermittently omitted fixed layers on
2026-10-22, including a stationary marker outside Leaf's chrome. Native
screenshots sampled during the same journeys retained those layers; whether
the omission occurs in native-window paint remains unresolved.
The probe journey in `dev/leaf_dev/panel_paint.py` reports missing mark and
focus-outline paint in Chromium's sampled frames; the functional test checks
their settled paint.
Firefox recordings remain diagnostic
evidence and cannot establish all-frame visibility. Recheck the same
fold/unfold journey with a stationary fixed marker, native screenshots and a
native-window recording when available; filtering missing frames would conceal
the unresolved gap.

### A short body's colour stops above the window's foot in Firefox

A live page with no Layout whose body the page coloured, and which is shorter
than the window, ends above a band of the root's colour in Firefox: the body is
a size container (`lf-shell`), containment keeps its background off the canvas,
and base.css fills the window with `min-height: stretch`, which subtracts the
body's own margins. Playwright Firefox 157 (build 1555) rejected `stretch`
and treated `-moz-available` as `auto` in the block axis on 2026-10-29;
Chromium 156 (build 1248) and WebKit 27.2 (build 2370) filled the window less
the default 8px margin with no scroll. A
Layout's body has no margin, so its `min-height: 100%` (layouts.css) fills the
window there too; 100% would make a body that keeps the browser's margin scroll
by it. Recheck with `leaf-dev probe --browser firefox` on a short page that
colours `body` and keeps its margin, reading the body's bottom against
`innerHeight` and the root's scroll height; once Firefox fills it, the Layout
rule can go.

### A subgrid scroller's `auto` scrollbar

Chromium (156 on macOS, 153 on Linux) and Firefox 155 on Linux lay a subgrid's
items on its parent's tracks without the room an `overflow: auto` scrollbar takes,
against css-grid-2's rule that the subgrid's scrollbar gutter is extra margin on
its edge items. Where the bar takes room (Linux, Windows, macOS with a mouse), a
margin card's transcript, then a subgrid, ran its words under the bar. On
2026-10-30 Linux Chromium's 10px bar left the transcript 10px of sideways travel;
Firefox's 6px bar fit within the transcript's 6px of room, so its words reached the
bar without scrolling sideways. Both engines count the bar of `overflow: scroll`
and a `scrollbar-gutter: stable` gutter. No scroller in Leaf is a subgrid: the
transcript lays out its own track (`annotation-chrome.css`), so its bar takes room
in both. WebKit is unrecorded,
since Playwright's WebKit draws only overlay scrollbars on macOS and Linux. No
Chromium or Firefox bug tracks the `auto` case (searched 2026-10-30), and Leaf
has left it unreported, so only a recheck shows when a browser fixes it.

Recheck with a two-column grid holding an 80px-tall `grid-template-columns:
subgrid` child with `overflow-y: auto` and tall content, comparing its
`scrollWidth` with its `clientWidth` where bars take room: in the Playwright Linux
image (`mcr.microsoft.com/playwright/python`, arm64 on this Mac), Chromium
launched without `--hide-scrollbars`, and Firefox launched headed under
`xvfb-run` with `GTK_OVERLAY_SCROLLING=0` and
`widget.gtk.overlay-scrollbars.enabled` false (headless Firefox draws overlay
bars). Once they match in both, a scroller may be a subgrid.
`test_a_card_that_scrolls_gives_its_scrollbar_room` in
`tests/browser/margin/test_card_reply.py` covers the card in Chromium.

### A grid scroller's end padding beside a sticky item in Firefox

Firefox leaves a grid scroll container's block-end padding, and its last item's
end margin, out of its scroll range whenever one of its items is `position:
sticky`. A block or flex scroller, or a sticky box inside a grid item, keeps the
padding. In the user's Firefox on 2026-11-24 a margin card's transcript, then such
a grid with New reply sticking in it, lost the bottom side of a focus ring a
rewrite of its last turn draws in the room the transcript keeps below its turns as
padding. In Playwright Firefox 159.0 (build 1572), a 100px grid scroller with
8px of end padding holding a 150px item reports a `scrollHeight` of 158, and
170 with a 20px sticky item added; Chromium 159.0.8154.6 (build 1255) and WebKit
27.2 (build 2388) report 178. A playground's controls pane is such a grid too,
and loses its 16px of end padding the same way when a sticky widget, such as
`lf-dial`, stands directly in it, which no page does yet. No Mozilla bug found
matches (searched 2026-11-24), and Leaf has left it unreported.

The transcript is a block scroller (`annotation-chrome.css`), so every engine
keeps its padding. Recheck with that fixture: once Firefox reports 178, a
scroller holding a sticky item may be a grid.
`test_a_rewrite_at_the_foot_of_a_card_that_scrolls_keeps_its_whole_ring` in
`tests/browser/threads/test_rewrites.py` fails in Firefox while the transcript is
such a grid.

### A landing in a skipped `content-visibility: auto` box in Firefox and WebKit

Firefox 157 (Playwright's build, macOS) leaves a `content-visibility: auto` box skipped
after script scrolls to an element inside it until the box itself intersects the view
at a rendering update; it doesn't activate the box for the scroll, and the box keeps
its estimated size meanwhile. Geometry read from inside the skipped box is the drawn
layout's, so where the estimate was off, a landing computed from it showed another
stretch. On 2026-11-02, before a long text document's runs were sized to their lines,
`t` to line 11,000 of a 1 MB wrapped text reported the line 214 px into its listing,
while `elementFromPoint` there found line 11,041, the box showed line 11,035 onwards
with no comment mark, and the run was still skipped 1.5 s later. Setting the run
`content-visibility: visible` drew line 11,000 where it was reported. So travel draws
the box it lands in for the jump and releases it two frames later (`features/anchor-travel.js`,
`drawForLanding`), and the hit-test finds the line because its run is drawn. Runs are
sized to the lines their rows fill (`lf-text-document.js`, `sizeRuns`), but long
tokens, which Firefox also breaks after a slash, fill more lines than that: with the
run left skipped, a jump past them stopped 104 px short and a second scroll followed.
`test_a_long_text_document_draws_the_lines_in_view_and_keeps_the_rest_whole` covers it
in both engines.

A row at the head of its run moves even with the run drawn, in Firefox and WebKit. On
2026-11-20 a plain page held 200 runs of 20 wrapped rows, each run
`content-visibility: auto; contain-intrinsic-size: auto 400px`, never drawn and
several times taller drawn than that estimate, in a 400 by 600 px window. An instant
scroll write put a row 150 px below the window's top, so the run above it stood
partly in view, and the row's top was read over the next five frames. Playwright
Chromium 159.0.8154.6 (build 1255) held every row at 150 px. In Firefox 159.0
(build 1572) a row inside its run moved 2,000 px up at the second frame, and held
with its run drawn for the jump, as `drawForLanding` draws it; the run's first row moved
2,000 px down at the second frame either way. In WebKit 27.2 (build 2388) rows
inside the run held without drawing, and the run's first row moved 1,400 px down at
the first frame either way. A `scrollIntoView` to the window's top landed every row
in all three engines. Whether a text document's landings, with its runs sized to
their lines, meet the head-row case was not assessed. To recheck, drop
`drawForLanding` and travel past long tokens in Firefox, and run that page in
Firefox and WebKit: the first gap stands while a row inside an undrawn run moves, and
the second while the run's first row moves with its run drawn.

### A skipped `content-visibility: auto` box keeps its drawn height

Chromium 156, Firefox 157 and WebKit (Playwright's builds, macOS) keep the height a
`content-visibility: auto` box was drawn at for as long as it is skipped, whatever its
`contain-intrinsic-size` says: written without `auto`, or never given `auto`, the box
still stood at its drawn height frames later. They drop it only when the box's style
resolves with neither `auto` nor `content-visibility: auto`, which a `getComputedStyle`
read does within the same task. css-sizing-4 ("Last Remembered Size") keeps a
remembered size only while `contain-intrinsic-size` has `auto`, and removes it at
ResizeObserver timing once `auto` is gone; no engine does either. On 2026-11-02 a long
text document narrowed from 718 to 460 px after its last runs were drawn left End
240 px short in Chromium, 1,700 px in Firefox and 1,834 px in WebKit. So when its line
length changes, `lf-text-document.js` (`sizeRuns`) resolves each drawn, skipped run's
style once as `hidden` without `auto`, then takes both back in the same task, and End
and a drag to the bottom land in all three. The forgetting rests on that uniform but
unspecified behaviour: should an engine keep the height through that resolution, or
drop it only as specified, the drag after the narrowing in
`test_a_long_text_document_draws_the_lines_in_view_and_keeps_the_rest_whole` stops
short. To recheck, draw a `content-visibility: auto` box with
`contain-intrinsic-size: auto 100px`, scroll it out of view, write
`contain-intrinsic-size: 300px` and read its height a few frames later: 300 px is the
specified behaviour.

### A row moved to the head of a skipped run in Chromium

Playwright Chromium 158.0.8127.18 (build 1254) builds no `::before` box for a row that
`moveBefore` moves to the head of a `content-visibility: auto` box it is skipping, so
where the head row resets a counter for the rows after it, as a text document's first
row in each run does (`text-document.css`), that row draws no line number and the
rows after it count from 1, also once the box comes into view. The same move made with
`insertBefore` or `prepend`, or while the box is drawn, numbers right. On 2026-11-15
#5916's reproduction (three such boxes of 40 rows, each drawn once and scrolled back
out of view, then each box's last row moved to the head of the next with `moveBefore`)
drew no number on the moved row in the third box and numbered the rows after it from
1; with `insertBefore`, every row read its line. A text document moves a row only onto
the end of a run or into a run a split has just made (`lf-text-document.js`,
`regroup`). Recheck by running that reproduction: once the moved row reads its line
number, a text document may move rows to a run's head again.

### A style read lays out a size container's contents

Playwright Chromium 158.0.8127.18 (build 1254) answers `getComputedStyle` for an
element whose style is out of date inside a size container by laying out everything out
of date in that container, once a size query is evaluated against the container,
whether it matches or not; a style query doesn't do it. Playwright Firefox 159 does it
for the size container alone. Leaf's `body` is the `lf-shell` inline-size container
(base.css), and `@container lf-shell (width < 640px)` queries it (`layouts.css`,
`packages/default/styles/tabs.css`), so on a Leaf page a script's style read inside
`body` pays for layout too, inside a closed tab's `hidden="until-found"` panel as well,
which the read unlocks. On 2026-11-16, 20,000 `div` rows in such a panel, shown again
after `display: none`, took 20 ms of style and 46 ms of the layout the read forced in
Chromium (a trace's `UpdateLayoutTree` and `Layout`), and 6.5 ms for the whole read
with no Leaf sheets. Page search's first read inside a closed tab pays it for the
whole panel (`readings/passages.js`, `searchableWords`). Leaf leaves it for now, since the
container gives a narrow column and a widget's `100cqi` the shell's width. Rewriting
the two `lf-shell` size queries would cost less than giving up the container and may
lift it in Chromium, though not in Firefox; it is untested on a Leaf page, where the
`cqi` lengths read the same container. Recheck on a plain page of 20,000 `div` rows
under `body { container-type: inline-size }`, timing `getComputedStyle(lastRow).color`
after toggling the rows' parent's `display`: in Chromium, 46 to 47 ms with
`@container (max-width: 1px) { div { color: red } }`, which matches nothing, and 7.5 ms with
`@container style(--x: 1) { div { color: red } }` in its place; in Firefox, 33 to 35
ms with either rule or none, against 6 ms without the container.

### Styling content Firefox skips

Firefox 157 (Playwright build 1555, macOS) styles every element inside a box whose
content it skips, a `content-visibility: auto` run out of view and a closed tab's
`hidden="until-found"` panel included, on each restyle that reaches it. Chromium 156
leaves skipped content unstyled until it is drawn. So in Firefox a restyle that
reaches a long text document's listing styles every row and its line number. On
2026-11-04 the Firefox Profiler's `Styles` marker counted 194,514 elements when the
runtime's scroll mark changed three inherited values on a listing of 97,000 rows (250
to 330 ms; 25 to 45 in Chromium), and 2.1 million when a page of 30 documents of
50,000 lines presented (2.6 s).

Leaf keeps its own writes off the rows while a page loads: a listing states its slot
restart from the first paint (`text-document.css`), and a closed tab's document draws
after the page presents (`lf-text-document.js`, `drawLater`). Two restyles still reach
every row in Firefox. A newly started Firefox restyles every page on each
`font-info-updated` in its first seconds, 1.4 s each on the page of 30 documents. And
Gecko answers an insertion into an element whose children a `+`, `~` or
`:nth-*(… of …)` selector has been matched against by restyling every later
sibling's subtree. The frame-edge trims in `reading.css` are matched against every
element, as are `.lf-inspection-body :is(h2, h3) + *` (`chrome.css`) and the reading
theme's `.eyebrow + :is(h1, h2, h3)` against every heading, so a paragraph added at
the top of `main` restyled the whole page: 280 to 310 ms over 97,000 rows, and 24 ms
with the trims written as `:first-child` and `:last-child` and the two sibling rules
taken out. The first is Firefox's to change. The eyebrow rules (`reading.css`) now end at an
`hgroup` or a heading's place in it, and rewriting the others is open (#5194).

To recheck, build a `pre` of 97,000 `div` rows in runs of 128 with
`content-visibility: auto`, each row numbered by a `::before` counter, let it paint,
then set an inherited custom property on the `pre` and time the next frame: 70 to 77
ms in Firefox, 17 to 19 in Chromium.

### A traversal's own scroll restoration under the Navigation API

Firefox 157 (Playwright build 1555, macOS) applies a same-document traversal after
its `navigate` event, and restores the destination entry's saved offset just after
the traversal's `popstate` even when a handler intercepted it with
`scroll: "manual"`: `nsDocShell::HandleSameDocumentNavigation` never reads the
`mSuppressNormalScrollRestorationDuringOngoingNavigation` flag `Navigation.cpp` sets.
It can also blur the focused element then. Firefox and WebKit 27.2 (build 2370) both
reveal the fragment's `hidden="until-found"` target as they apply the traversal,
firing `beforematch`, and WebKit scrolls to it; Chromium 156 does none of this. On
2026-11-02, Back to a code block in a tab the user had closed since, with a
disclosure opened above it, landed it 471 px down in Firefox, at the offset the entry
was left at, where Chromium landed it at 59. So `browser/runtime/records/history.js` places
the page before the browser applies the traversal, reading what is hidden before the
browser reveals it. In the rendering update after the traversal's `popstate`
(`traversalApplied`), it scrolls the first block on screen back to where its
placement stood it; Firefox's blur still leaves focus on `body` after Back.
`test_back_to_a_fragment_the_page_has_hidden_since_lands_on_it` covers it in Chromium
and Firefox. To recheck, intercept a traversal with `scroll: "manual"`, scroll in the
handler, and read the offset after `popstate`; once Firefox keeps the handler's offset
and neither engine reveals or scrolls to the target, that step can go.

### Forward to a same-document entry names no destination in Playwright's Firefox

In Playwright's Firefox 159.0 (build 1572, macOS), after Back from a same-document
entry a followed fragment link added, `navigation.entries()` no longer lists that
entry, and Forward to it fires a `traverse` navigate event whose `destination.key` is
empty and `destination.index` is -1; once applied, `navigation.currentEntry` is null.
Stock Firefox 160.0 (macOS) and Chromium 156 name the entry. Observed 2026-11-21 on
the installed test engine, and 2026-11-22 in stock Firefox 160 through Marionette;
disposition: no longer reproduces. On 2026-11-22 a probe of the same steps in build
1572 (`leaf-dev probe --browser firefox`, a followed fragment link, Back, Forward)
named Forward's destination, `key` set and `index` 1, and returned the record history
wrote to it, and `browser/runtime/records/history.js` now reads an entry's record from
`destination.getState()` rather than by key.
`tests/browser/navigation/test_threads.py::test_back_and_forward_show_the_thread_each_entry_names`
asserts focus after Forward in Chromium and Firefox. To recheck, follow a fragment
link, go Back, and read `destination.key` and `destination.getState()` in Forward's
`navigate` event.

### Firefox drops focus as it applies a same-document traversal

Stock Firefox 160.0 (macOS) blurs the focused element, leaving focus on `body`, as it
applies a same-document traversal, in the task that fires `popstate`, though Leaf
intercepts the traversal with `focusReset: "manual"`. Leaf returns the user's place
before the browser applies the traversal (`records/history.js`), so after Forward to a
followed link's target, focus was on `body` rather than on the target, and the next
command started from the top of the page. Observed 2026-11-22 through Marionette;
disposition: corrected, since Back and Forward are a path users take often:
`records/history.js` puts focus back on the node the return placed it on once the traversal
has applied. To recheck, log `focusout` during Forward in stock Firefox: a
`focusout` with no script on its stack just before `popstate` is the drop.

### Highlight hit testing

`CSS.highlights.highlightsFromPoint(x, y, {shadowRoots})` (CSS Custom Highlight API)
names the highlights under a point and the ranges of each there, and Playwright's
Chromium headless shell 156.0.8078.4, Firefox 157 and WebKit 27.2 all ship it. On
2026-11-05 it answered correctly at a range's edges and inside a shadow tree passed in
`shadowRoots`, which it needs in every engine. Two things keep a thread's passage
marks from using it to say which mark the pointer is on
(`browser/runtime/annotations/anchor-paint.js`, `markHit`):

- Its cost grows with the ranges the page's highlights hold, every one of them read
  on each call. At the last of a paragraph's marks, one call took 20 µs at 32 and
  320 µs at 512 in Chromium, and 15 µs and 100 µs in Firefox. Read again on
  2026-11-06 over a mark in the middle of a page of 32 and of 512 paragraphs, one
  thread each, it took 15 µs and 235 µs in Chromium 156.0.8078.4 and 15 µs and 80 µs
  in Firefox 157, against 1 µs and 5 µs for `caretPositionFromPoint` at both sizes.
  A hover's work must not grow with the page (root `AGENTS.md`, "Responsiveness").
- Firefox and WebKit name a highlight under a box covering its words, as the chrome
  over the page is; Chromium names none there.

So `markHit` takes the caret lookup's text node and offset, reads the one or two
characters' boxes around the offset, and finds the marks covering that character in
an index of the marks' live ranges, the ones the highlight paints. After a change to
the page's words, anchor placement places again only the threads whose quotes the
page's index of quotes says changed (readings/passages.js, `quotesChanged`), and the index reads
again only those threads' ranges. Recheck by timing
`highlightsFromPoint` over a mark on pages of 32 and 512 marks, and at a point under a
covering box; once its cost holds still and every engine names nothing under a cover,
`markHit` can ask it instead of keeping its own index.

### A popover's implicit anchor after a hide and show in one task in Firefox

Firefox bug. On 2026-11-05, Playwright Firefox 157 (build 1555, macOS), in a fresh
context with no Leaf code, stood a popover by the source it was last shown with when it
was hidden and shown again by another source in one task
(`showPopover({source: b})`): it stood by `a`. A frame between the hide and the show
stood it by `b`, as did any change to the popover itself before the show, such as its
words. Chromium 156.0.8078.4 (headless shell build 1248) stood it by `b` every time. On
this page the manual and auto popovers stand 380 px off and the hint one, there, did not;
on a Leaf page the hint one does:

```html
<style>
  .tip {
    position: fixed;
    inset: auto;
    margin: 0;
    position-anchor: auto;
    position-area: block-end span-inline-end;
  }
  button {
    position: fixed;
  }
</style>
<button id="a" style="left: 20px; top: 20px">A</button>
<button id="b" style="left: 400px; top: 200px">B</button>
<div class="tip" popover="manual">Words</div>
<script type="module">
  const tip = document.querySelector(".tip");
  tip.showPopover({ source: a });
  await new Promise(requestAnimationFrame);
  tip.hidePopover();
  tip.showPopover({ source: b }); // with a frame before this line, it stands by B
  await new Promise(requestAnimationFrame);
  console.log(tip.getBoundingClientRect().left - b.getBoundingClientRect().left);
</script>
```

The preview (`browser/runtime/annotations/preview.js`, `open`) is one popover a warm switch hides
and shows again by its next target in one task, so two targets with the same words in
turn would stand the second preview by the first. Where a new source comes with the
words the last one had, it moves the preview to the other side of a sibling, its
stage's mark, which re-lays it out and which the page's write watch reads as a change,
as a re-insertion at the same place it would not.

On 2026-11-20 the page above logged 0 in Playwright Firefox 159.0 (build 1572) when it
ran more than a few frames after load, but holding the first show for half a second
before the hide and show, as a preview is held, still stood the popover 380 px off by
`a`, a second after load and with or without a read of its box between; Chromium
159.0.8154.6 and WebKit 27.2 stood it by `b`. To recheck, run the page a second after
load with `await new Promise((r) => setTimeout(r, 500))` in place of the first frame;
once Firefox logs 0, drop the move in `open`.

### A touch long press in WebKit

WebKit gap. A WebKit touch engine, iOS and iPadOS Safari and every iOS browser, sends no
event as a touch press becomes a long press: no `contextmenu`
([WebKit bug 213953](https://bugs.webkit.org/show_bug.cgi?id=213953), open, its last
comment 2026-03-28), where Chromium on Android sends one at the long-press timeout the
user set and Gecko on Android one at its own. Read in WebKit's source at main 58fe6ea4b
(2026-11-05), `Source/WebKit/UIProcess/ios/WKContentViewInteraction.mm`: the long press
WebKit recognizes is UIKit's, at 0.12 s for its highlight (`highlightDelay`, line 539)
and 0.75 s for its sheet (`tapAndHoldDelay`, line 540), and neither reaches the page as
an event. The highlight one, enabled only where an app uses no context menus or allows no
link previews (line 1849), sends a click when the touch ends, however long it was held
(lines 3787–3790), unless a touch event the page cancelled cleared it (lines
2496–2502). Safari uses context menus, so its click after a long hold is UIKit's tap
recognizer's to give, which WebKit sets no duration on.

So a held finger reads a preview (`browser/runtime/annotations/preview.js`, the hold) at
`contextmenu` where the engine sends it, and after 500 ms, UIKit's default for a long
press, where `GestureEvent` says the engine is WebKit, which exposes it in desktop
Safari too, where only a touch starts a hold and no touch comes; the touch's end is
cancelled there as everywhere, which stops WebKit's own click. The cost: on iOS a press
held past 500 ms reads rather than presses whatever the user set in Touch
Accommodations, which no page can read. To recheck, hold a finger on an element with a
`contextmenu` listener in Safari on an iPhone or the simulator; once it logs, drop the
timer and `holdsUntold` in `annotations/preview.js`.

### Two spellings of position-visibility

Firefox gap. The CSS working group renamed `position-visibility: anchors-visible` to
`anchor-visible` ([Chrome Platform Status
5136123851571200](https://chromestatus.com/feature/5136123851571200), which plans to
remove the plural later). On 2026-11-10, `CSS.supports("position-visibility", …)`
and the computed value read:

| Engine                                                    | `anchors-visible`            | `anchor-visible` |
| --------------------------------------------------------- | ---------------------------- | ---------------- |
| Chromium headless shell 158.0.8127.18 (Playwright 1.65.0) | read, with a console warning | read             |
| Google Chrome 157.0.8103.50, installed                    | read                         | read             |
| WebKit 27.2 (Playwright build 2388)                       | read                         | read             |
| Firefox 159.0 (Playwright 1.65.0)                         | read                         | refused          |

Chromium 158 warns on the plural wherever it parses it, a second declaration after it
or a false `@supports` block included, and `page check --render` reports that warning
as a finding against the page. So Leaf names the value once, as `--lf-anchor-visible`
(`browser/styles/tokens.css`), set to the singular where `@supports` reads it, and every
`position-visibility` that hides a box with its anchor reads the property. A custom
property's value is parsed only where a declaration uses it, so Chromium never parses
the plural and Firefox never the singular. To recheck, read
`CSS.supports("position-visibility", "anchor-visible")` in Playwright's Firefox; once it
is true, spell `anchor-visible` in each declaration and drop the property.

### A stroked line's box in Chromium

Leaf stands the ⌥ aim on a drawing's part only where the part's box has area
(`placement` in `browser/runtime/readings/target-paint-geometry.js`, from `shownBox`).
Chromium measures an SVG shape's box by its geometry alone, without its stroke, so a
part drawn as one straight stroked line, such as a bar matplotlib draws with
`ax.plot(…, lw=6)`, is 0px tall: on 2026-11-17, HeadlessChrome 158.0.8127.18
(Playwright 1.65.0) gave such a horizontal `<path>` and its `<g>` a box 0px tall, and
Playwright Firefox 159.0 one 8.5px tall. Holding ⌥ over the bar in Chromium draws no
aim, though an ⌥-click still comments on it. Bars drawn as rectangles and curves have
area and aim in both. Recorded rather than corrected, since a chart's bars are usually
rectangles. Recheck with `uv run leaf-dev probe` of a page whose inline `<svg>` holds
`<g id="bar"><path d="M0 10 L100 10" stroke="black" stroke-width="6"/></g>`, reading
`document.querySelector('#bar').getBoundingClientRect().height` in Chromium.

### Deleting in an editing host after `body` in Firefox

Firefox types into a `contenteditable` that stands after `body`, as Leaf's chrome
does, but deletes nothing from it: Backspace and Delete do nothing, in a shadow root
or not, with `true` or `plaintext-only`. On 2026-11-18, Playwright Firefox 159.0
(Playwright 1.65.0) kept "abcd" after two Backspaces in such a host, and "ab" in the
same host inside `body`; HeadlessChrome 158.0.8127.18 gave "ab" in both, and a
`textarea` after `body` gave "ab" in both engines. A text field's box before
CodeMirror loads (`annotations/composing/text-field.js`, `#rest`) and the served row's field
(`bootstrap.js`, `standRow`) are textareas for this, which edit the same way in
every engine. CodeMirror deletes from the keyboard by its own commands, but
`document.execCommand("delete")` on a selection in a loaded panel editor still
returns false and deletes nothing in Firefox; standing the chrome inside `body`
would cure both, at the cost of the isolation it has after `body`. Recheck by
appending `<div contenteditable>` after `body` in Firefox, typing "abcd" into it and
pressing Backspace twice.

### Pretty line breaking in Firefox

The reading face breaks a paragraph's lines with `text-wrap-style: pretty`
(`browser/styles/components/reading.css`, `p`), so a paragraph doesn't end on one
word alone. Firefox doesn't accept the value and breaks greedily, as it did before,
so a paragraph there can still end on one word. On
2026-11-26 the installed Firefox 160.0.1 and Playwright Firefox 159.0 (build 1572)
both answered `CSS.supports("text-wrap-style", "pretty")` with false, and the
`review-a-plan` example at 1280×800 ended its lede on "Codex." and its close on
"harnesses."; Playwright Chromium 159.0.8154.6 and WebKit 27.2 ended neither on one
word. Left as it is: nothing breaks, and Firefox takes the value once it ships it.
Recheck with `uv run leaf-dev probe review-a-plan --browser firefox --viewport
desktop --js "CSS.supports('text-wrap-style', 'pretty')"`.
