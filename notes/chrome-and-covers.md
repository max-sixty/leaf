# Workspace scrolling and chrome

The sticky-header foundation landed in [PR #1472](https://github.com/max-sixty/leaf/pull/1472).
The banner has a stated height, sticky headers stack through `--lf-top`, and the
workspace row rule applies to pane grids without squeezing a widget's own rows.
These contracts live in [layouts.css](../skills/leaf/assets/layouts.css),
[theme.css](../skills/leaf/assets/theme.css), and the
[module reading-region contract](../skills/leaf/references/module-authoring.md#reading-regions).

## Decided: a workspace is a screen

A full-height workspace stays a screen whose regions hold their own overflow. Some
pages behave like a TUI or a dashboard rather than a document, and the workspace
Layout exists for them; a long read beside a panel kept in view is a `layout-sidebar`
document whose aside sticks (`page-authoring.md`, A workspace).

Option E, a workspace whose main region flows with the root while its other regions
stick, is rejected. It kept native page scrolling at the cost of reworking the
full-height widgets, footers, margin lanes and phone stacking, all to make workspaces
scroll better, which is not what they are for.

The aim is pages that need little scrolling, composed simply, rather than better
scrolling inside regions. `page check --render` names each pane or body of a screen
that runs past its room, so an author trims or splits it (`overflowing_region_advice`).

A branch that made a side list (`lf-tabs list="side"`) a screen was built and
abandoned (`screen-workspace-review`, October 2026): it gave the list and the open
item separate scrollers, routed the reading keys to the item, and stacked queue and
item on a phone. It bound the workspace's behavior to one widget and spent its
weight on scrolling, so none of it shipped except the overflow advice and the
instructions above.

## Still open

- **The phone banner,** decided and not built: one 53px row holding the status in
  words, cut short with an ellipsis, with a passing notice taking that slot for a few
  seconds; then Threads as an icon with its count; then More. Approve moves into More,
  which wears a dot while approval is open.
- **The desktop bottom bar,** undecided. Removing it deletes `--lf-bottom-bar-h` and
  its readers (`theme.css`, whose `--lf-view-height` the contents map reads,
  `chrome.css`, `shortcut-bar.js`), `declareBottomBar`, and the bottom edge in
  `shownWindow`; its key hints would move to `?` and its status (notices, the Go-to
  sequence, the walk position) to the banner. The bar is how a desktop user learns the
  keys without asking. A middle path keeps the hints at the foot and moves the status
  into the banner.
- **Two gaps in the sticky headers.** A box the theme makes scroll starts `--lf-top`
  again; one an author makes scroll does not, so an `lf-diff` inside it pins its file
  header that far below the box's top. And a diff's file header is one line whose path
  gives way from its folders, with the whole path in its title, which a keyboard user
  focusing the header does not see.

## Evidence

The original review ran on 29 September 2026 at `5ed41df4b`. On a plain Chrome page
it found:

| Gesture | Root scroller | Inner page box |
|---|---|---|
| PageDown or Space before a click | Scrolled | Stayed still |
| PageDown after clicking body text | Scrolled | Scrolled |
| PageDown after clicking the header | Scrolled | Stayed still |
| Back after `pushState` | Restored position | Kept the later position |
| Back from another document, or reload | Restored position | Returned to top |

Use `leaf-dev stills` against the merge base for changed first viewports and banner
states, on a phone too.
