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
build.

Minor visual differences are acceptable when content remains readable and
controls remain usable. Lost drafts, broken actions, inaccessible controls, and
movement that disrupts a gesture need a fix or an explicit support decision.
An unsupported API alone does not justify blocking the whole browser: record
what fails and what still works.

## Known gaps

### Tab underline travel between anchors

The selected-tab underline in `packages/default/styles/tabs.css` follows its
label with CSS anchors. Playwright Firefox 155.0, build 1543, moved directly to
the new anchor on 2026-10-26, without a transition or `transitionrun` event;
Chromium 153.0.8010.12 interpolated its position and width. Instant selection
is an accepted visual difference: the selected label, panel, keyboard routes
and nested strips remain usable. Recheck by opening `lost-update` with
`leaf-dev probe --firefox --motion no-preference`, selecting the adjacent tab
with the pointer and inspecting `.lf-tab-selection` across animation frames.
The Chromium behavior and interruption contract are covered by
`test_pointer_tab_underline_moves_without_delaying_the_view` in
`tests/browser/widgets/test_tabs.py`.

### Scroll-state containers

Firefox 157 and Playwright Firefox and WebKit 26.6 lacked CSS scroll-state
containers on 2026-10-14. `browser/layouts.css` declares `normal` before
`scroll-state` so breakout tables keep their intended width in those engines;
other tables keep the `inline-size` container from
`browser/styles/components/reading.css`. Recheck table width with
`test_a_table_of_prose_wraps_inside_its_box_in_every_engine` in
`tests/browser/test_render_pages.py` before removing the fallback.

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

### A restyle skipped under a nested container in Chromium

Playwright Chromium 153.0.8010.12 left the visual review's case buttons in the
wide layout's padding (`14px 4px`, not `10px 8px`) when the window crossed the
review's 58rem container query, while the case list between them was an
inline-size container, as the theme makes a pane's body. On 2026-10-25,
narrowing `visual-review-gallery` from 1200px to 880px reproduced it on every
crossing; Firefox 155 took the narrow padding. `.lf-vr-case-list` in
`packages/visual-review/defaults.css` declares `container-type: normal`,
since nothing in the list queries it. Recheck by deleting that declaration,
narrowing the page with `leaf-dev probe` and reading a case button's computed
padding; `test_page_fixture_renders[visual-review-gallery]` in
`tests/journeys/test_render_gate.py` reads the same difference in its resize
journey.

### Contents spine lens

`packages/default/widgets/lf-toc.js` uses a paused animation updated on scroll
where `ScrollTimeline` is absent. The lens still marks the visible part of the
page, but follows scrolling a frame later than the native timeline.
Installed Firefox 157.0.1 lacked the API on 2026-10-10; Chrome 155 exposed it.
Revisit the fallback when supported engines provide it.
`test_the_lens_follows_the_scroll_without_a_scroll_timeline` in
`tests/browser/widgets/test_contents_and_glosses.py` checks the fallback against
the native timeline with the API removed.

### Highlight style inheritance

Playwright Firefox 155 accepted `:root::highlight()` and `:host::highlight()`
on 2026-10-22 but painted no highlight on nested syntax spans in either light
or shadow DOM. Universal highlight rules paint those ranges correctly; retain
them in `browser/runtime/annotation-overlay/annotation-marks.css` and
`browser/runtime/marks.css`. Revisit root-scoped rules when
`test_highlight_paint_reaches_nested_syntax_in_the_widgets_theme` in
`tests/browser/navigation/test_comment_marks.py` passes with them in supported
engines. Chromium 153.0.8010.12 passed both forms in that check.

### Intrinsic block retirement motion

`browser/runtime/motion.js` (`foldBlock`) animates block retirement, a decided
block suggestion and a resolved inline thread, with `calc-size()`. Where
intrinsic-size interpolation is missing it folds from the block's measured pixel
height, and where `display` can't be animated it keeps an already-retired slot
drawn with an inline `display` the effect's end removes. Playwright Firefox 155
needed both on 2026-10-25 and folded the same curve as Chromium.
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

`browser/runtime/composing/dictation.js` offers dictation when
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
too (`runtime/widget-elements.js`, `reveal`). WebKit's reported gap is that finding a match reveals folded content without
scrolling to the match. [WebKit 304174](https://webkit.org/b/304174) remained
open when checked on 2026-10-22; this is published evidence, not a local Safari
reproduction. Recheck native find-in-page on text inside a closed panel before
removing this entry.

### Native focus and scrolling inside samples

An opaque sample's sandbox isolates DOM and storage, but authored JavaScript's
native focus and reveal calls can still move focus or scroll its containing
page. Leaf contains its own placements through `browser/runtime/focus.js`,
`keyboard/layer-stack.js`, `landing-scroll.js` and `editor-view.js`; this is a
cooperative runtime contract, not a security boundary for authored scripts.
Chrome 155 and Chromium 153.0.8010.12 allowed autonomous child focus transfers
on 2026-10-09. On 2026-10-10, typing into an already focused offscreen native
editor also revealed its frame without a JavaScript reveal call.
Reproduce by focusing the parent, then invoking native focus or reveal from a
child message handler; separately type into an offscreen focused child editor.

### A selection written during focus in WebKit

Playwright WebKit 26.6 revealed an editor's selection written inside its
`focus` event, before the platform finished its focus steps, although the focus
call prevented scrolling, and the reveal crossed a sample's frame: on
2026-10-25 the containing page scrolled 1,386px to a sample's editor. Chromium
153 kept the page still. `LeafEditorView` in `browser/runtime/editor-view.js`
writes the caret after native focus returns when its own `focus()` moved focus,
and inside the focus event only for arrivals that bypass it, such as Tab;
whether WebKit reveals those across a frame is unverified. Recheck
`test_sample_editor_focus_preserves_outer_scroll_and_the_caret[webkit_browser]`
in `tests/journeys/test_render_controls.py` with the focus listener writing the
selection on every arrival (`#focusing` never set).

### Sample document admission and native navigation

`browser/runtime/sample.js` admits the initial document with a credentialless
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

### Page cache

The local page server sends `no-cache`; leaf.page keeps `no-store`. On
2026-10-20, Chromium 153.0.8010.12 and installed Firefox 158.0.1 restored a local
`release-notes` page on Back and applied state changes made while away.
Firefox loaded a page containing samples afresh. Safari remains unverified.
The leaf.page cache-policy decision is tracked in
[issue #4024](https://github.com/max-sixty/leaf/issues/4024).

Playwright disables back/forward caching in its normal test browsers.
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
`test_frame_edges_pass_through_whatever_stands_at_them` and
`test_a_row_at_a_frame_edge_holds_the_trim_by_declaring_it` in
`tests/browser/test_render_gate.py`.

### State-preserving content reordering

`browser/runtime/dom-move.js` uses `moveBefore` for retained nodes within one
composed root. In engines without it, ordinary insertion restores focus and
caret but still blurs the descendant and reloads an iframe. Playwright WebKit
26.6 lacked the API on 2026-10-10. Recheck native state preservation before
removing the fallback; `test_retained_moves_keep_native_editor_and_frame_state`
in `tests/browser/controls/test_focus.py` exercises native and forced-fallback
paths in Chromium. API presence alone does not prove preservation.

Chromium 153.0.8010.12 also left a focused node unmatched by its own
`:focus-within` after moves through a hidden parent on 2026-10-12. Leaf's focus
marks follow rendered ancestry; selectors for the focused editor use `:focus`.
Recheck with a focused input moved into a hidden parent and back out.

### Clearing a shadow host unloads its frames in WebKit

In Playwright WebKit 26.6 on 2026-10-24, `replaceChildren()` on an element
with a shadow root unloaded every iframe in that shadow tree, leaving it
connected with a null `contentWindow`, even when the host had no children to
remove; `textContent = ""` did the same when it had some. Removing each child
with `remove()` kept the frames, as Chromium 153.0.8010.12 and Firefox 155.0
did for all three. `shadowStage` (`browser/runtime/shadow-stage.js`) removes a host's
light children child by child, the one place a widget clears its host, since a thread
outlet in a stage can hold a frame. Recheck with `test_a_diff_revision_leaves_a_line_thread_where_it_stands`
in `tests/browser/widgets/test_diffs.py`.

### Area capture rendering

`browser/runtime/composing/page-image.js` reconstructs the DOM with SnapDOM.
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

`browser/runtime/css-anchors.js` names boxes through document `::part()` rules.
Boxes deeper than the first shadow tree anchor through their host: Playwright
Firefox 155 failed to anchor through re-exported `exportparts` on 2026-10-14.
WebKit 26.6 failed to resolve a typed `attr()` anchor name inside `::part()`, so
the runtime writes one rule per name.
Recheck a fixed anchored box against a part-named child after scrolling its
shadow scroller, then repeat one host deeper through `exportparts` and with a
name read through `attr()` before lifting those limits.

### A stuck sticky anchor in Firefox

An anchored margin row, highlight, aim or floating card can disappear or stay
at its target's unstuck position while the target is sticky. Playwright Firefox
155 ignored the stuck offset on 2026-10-14; Chromium 153, Chrome 155 and WebKit
26.6 placed the box on the stuck target. `browser/runtime/css-anchors.js`
accepts this gap; Threads and the Page Map keep controls reachable.
Recheck a fixed box anchored to a sticky header after its scroller passes the
header's initial position, comparing their rectangle tops.

### A stuck sticky box bounces with the page

Firefox on macOS bounced a sticky column with trackpad overscroll on
2026-10-20. The page-of-parts column in `browser/layouts.css` uses fixed
positioning to stay still; other root-sticky boxes can still bounce.
Recheck with a native trackpad fling at the document's end; headless Playwright
supplies no overscroll. If engines hold sticky boxes still, the column can
return to sticky positioning. Its current cost is the WebKit anchor drift below.

### An anchor under a fixed box in WebKit

A mark, margin row or floating card targeting a fixed panel drifts as the
page scrolls. Playwright WebKit 26.6 applied the root scroll twice on
2026-10-14; Chromium 153, Chrome 155 and Firefox 155 placed it on the target.
`browser/runtime/css-anchors.js` accepts this gap; Leaf's page-of-parts column
is an affected surface. Recheck a fixed anchored box against a target in a
fixed scrolling panel while scrolling both the document and panel.

### An anchor's transforms in Firefox

Playwright Firefox 155 resolved anchors before transforms on 2026-10-16.
`anchorBox` in `browser/runtime/css-anchors.js` compensates for translations,
including wide tables; scale, rotation and CSS zoom remain unsupported by that
correction. Chromium 153 and WebKit 26.6 included transforms.
Recheck a fixed box anchored to a translated target by comparing their left
edges before removing the compensation; test other transforms separately.

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

### Native reveal bounded to its scroller

`scrollIntoView(node, {within})` in `browser/runtime/landing-scroll.js` reveals
an item without moving the containing page. On 2026-10-14, Playwright Firefox
155's native `scrollIntoView({container: "nearest"})` also moved an outer
scroller when a horizontal strip's edge extended just beyond its band.
Recheck a partly clipped strip's inner and outer scroll offsets before
replacing Leaf's bounded walk with native reveal.

### `calc()` in `overflow-clip-margin` in Chromium

Playwright Chromium 153.0.8010.12 rejected `overflow-clip-margin: calc(2px + 5px)`
on 2026-10-26, leaving the computed margin `0px`, while Playwright Firefox accepted
it. A text field's clip margin (`composing/text-field.js`, `.lf-field`) therefore
reads one custom property, `var(--lf-field-reach, 2px)`, rather than adding a
motion's reach to the caret's 2px. Recheck by setting the calc value on an element
and reading `getComputedStyle(element).overflowClipMargin`; once it reads `7px`, the
reach can add to the caret's margin.

### Fixed layers missing from Firefox screencast frames

Playwright Firefox 155 screencasts intermittently omitted fixed layers on
2026-10-22, including a stationary marker outside Leaf's chrome. Native
screenshots sampled during the same journeys retained those layers; whether
the omission occurs in native-window paint remains unresolved.
`leaf-dev bench-panel-motion` reports missing mark and focus-outline paint in
Chromium's sampled frames; the functional test checks their settled paint.
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
margin card's transcript, a subgrid, ran its words under the bar. On 2026-10-30
Linux Chromium's 10px bar left the transcript 10px of sideways travel; Firefox's
6px bar fit within the transcript's 6px of room, so its words reached the bar
without scrolling sideways. Both engines count the bar of `overflow: scroll` and a
`scrollbar-gutter: stable` gutter, so the transcript holds a gutter once its turns
overflow (`data-lf-overflows`, `annotation-chrome.css`; `thread-preview.js` says
until when). WebKit is unrecorded,
since Playwright's WebKit draws only overlay scrollbars on macOS and Linux.

Recheck with a two-column grid holding an 80px-tall `grid-template-columns:
subgrid` child with `overflow-y: auto` and tall content, comparing its
`scrollWidth` with its `clientWidth` where bars take room: in the Playwright Linux
image (`mcr.microsoft.com/playwright/python`, arm64 on this Mac), Chromium
launched without `--hide-scrollbars`, and Firefox launched headed under
`xvfb-run` with `GTK_OVERLAY_SCROLLING=0` and
`widget.gtk.overlay-scrollbars.enabled` false (headless Firefox draws overlay
bars). Once they match in both, the attribute and its rule can go.
`test_a_card_that_scrolls_gives_its_scrollbar_room` in
`tests/browser/margin/test_card_reply.py` covers the card in Chromium.
